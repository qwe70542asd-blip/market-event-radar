(() => {
  "use strict";

  const state = {
    payload: {metadata:{}, source:{}, sources:[], items:[]},
    status: "loading",
    error: null,
    timer: null,
  };
  const RETENTION_MS=20*24*60*60*1000;

  function isHttpUrl(value) {
    try {
      const url = new URL(String(value || ""), location.href);
      return ["http:","https:"].includes(url.protocol);
    } catch { return false; }
  }

  function parsed(value) {
    try { return new URL(String(value || ""), location.href); }
    catch { return null; }
  }

  function isGoogleLink(value) {
    const url = parsed(value);
    if (!url) return false;
    return /(^|\.)google\./i.test(url.hostname) || url.hostname === "news.google.com";
  }

  function isLikelyHomepage(value) {
    const url = parsed(value);
    if (!url) return true;
    const path = url.pathname.replace(/\/+$/,"");
    if (!path || path === "/") return true;
    return ["/news","/markets","/market","/finance","/tw-market","/intl-markets","/list/aie.aspx","/zh/about/news/news/list.html"]
      .some(home => path.toLowerCase() === home.toLowerCase());
  }

  function directCandidate(item) {
    const candidates = [item?.direct_link,item?.publisher_link,item?.safe_link,item?.link,item?.original_link];
    for (const value of candidates) {
      if (!isHttpUrl(value) || isGoogleLink(value) || isLikelyHomepage(value)) continue;
      return new URL(value, location.href).href;
    }
    return "";
  }

  function sourceHome(item) {
    const value = item?.source_home;
    return isHttpUrl(value) && !isGoogleLink(value) ? new URL(value,location.href).href : "";
  }

  function normalizeItem(raw) {
    const link = directCandidate(raw);
    if (!raw?.title || !link) return null;
    const published=new Date(raw.published_at||0).getTime();
    if (Number.isFinite(published) && published>0 && published<Date.now()-RETENTION_MS) return null;
    return {
      ...raw,
      link,
      direct_link: link,
      link_status: "direct",
      link_type: raw.link_type || "publisher-article",
    };
  }

  function canonicalTitle(value) {
    return String(value || "").normalize("NFKC").toLowerCase()
      .replace(/^(快訊|速報|即時|獨家)\s*[：:｜|／/\- ]*/u,"")
      .replace(/[\s\u3000]+/gu,"")
      .replace(/[^\p{L}\p{N}]+/gu,"");
  }

  function itemRank(item) {
    let score=Number(item.quality_score || 0);
    if (item.language === "zh-Hant") score += 15;
    if (item.is_breaking) score += 30;
    if (/^official/.test(item.source_group || "")) score += 10;
    const age=Date.now()-new Date(item.published_at || 0).getTime();
    if (Number.isFinite(age) && age < 6*3600e3) score += 25;
    else if (Number.isFinite(age) && age < 24*3600e3) score += 12;
    return score;
  }

  function dedupe(items) {
    const map=new Map();
    for (const item of items) {
      const key=canonicalTitle(item.title);
      if (!key) continue;
      const old=map.get(key);
      if (!old || itemRank(item)>itemRank(old)) map.set(key,item);
    }
    return [...map.values()].sort((a,b)=>{
      const time=new Date(b.published_at || 0)-new Date(a.published_at || 0);
      return time || itemRank(b)-itemRank(a);
    });
  }

  function normalizePayload(payload) {
    const items=dedupe((Array.isArray(payload?.items)?payload.items:[]).map(normalizeItem).filter(Boolean));
    return {
      metadata:{...(payload?.metadata || {}), direct_display_count:items.length},
      source:payload?.source || {},
      sources:Array.isArray(payload?.sources)?payload.sources:[],
      items,
    };
  }

  function merge(primary,seed) {
    const items=dedupe([...(primary?.items||[]),...(seed?.items||[])]);
    const primaryHasItems=Boolean(primary?.items?.length);
    return {
      ...primary,
      metadata: primaryHasItems ? primary.metadata : {...(primary?.metadata||{}),...(seed?.metadata||{})},
      source: primaryHasItems ? primary.source : (seed?.source||primary?.source||{}),
      sources: [...new Map([...(primary?.sources||[]),...(seed?.sources||[])].map(source=>[source.name,source])).values()],
      items,
    };
  }

  function emit() {
    window.MarketNews={
      payload:state.payload,
      items:state.payload.items,
      status:state.status,
      error:state.error,
      safeLink:directCandidate,
      isDirectArticle:item=>Boolean(directCandidate(item)),
      reload:load,
    };
    window.dispatchEvent(new CustomEvent("market-news-loaded",{detail:window.MarketNews}));
  }

  async function load() {
    state.status="loading";
    state.error=null;
    const seed=normalizePayload(window.__MARKET_NEWS_SEED__ || {});
    try {
      const raw=window.MarketDataSource?.loadJson
        ? await window.MarketDataSource.loadJson("data/news.json", seed)
        : seed;
      const network=normalizePayload(raw);
      state.payload=merge(network,seed);
      const source=raw?.__data_source;
      state.status=network.items.length
        ? (source === "live-data" ? "live" : "cached")
        : seed.items.length ? "cached" : "empty";
    } catch (error) {
      state.error=error;
      state.payload=seed;
      state.status=seed.items.length ? "cached" : "empty";
    }
    emit();
    return state.payload;
  }

  window.MarketNewsLink={
    safeLink:directCandidate,
    sourceHome,
    linkMode:item=>directCandidate(item)?"direct":"unavailable",
    linkLabel:item=>directCandidate(item)?"閱讀原文":"原文不可用",
  };
  window.MarketNewsLoader={load,state,isDirectArticle:item=>Boolean(directCandidate(item))};
  load();
  clearInterval(state.timer);
  state.timer=setInterval(load,30_000);
  window.addEventListener("online",load);
  document.addEventListener("visibilitychange",()=>{ if (!document.hidden) load(); });
})();
