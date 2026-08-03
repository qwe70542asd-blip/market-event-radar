(() => {
  "use strict";

  const VERSION = "11.1.2";
  const OWNER = "qwe70542asd-blip";
  const REPO = "market-event-radar";
  const LIVE_BASE = `https://raw.githubusercontent.com/${OWNER}/${REPO}/live-data/`;
  const MAIN_BASE = `https://raw.githubusercontent.com/${OWNER}/${REPO}/main/`;
  const PORTFOLIO_KEY = "market-radar-portfolio-v11-1";
  const LEGACY_PORTFOLIO_KEYS = ["market-radar-portfolio-v10-3", "market-radar-portfolio-v10"];
  const QUOTE_CACHE_KEY = "market-radar-quote-cache-v11-1";

  const OFFICIAL_OVERRIDES = {
    "TW:00403A": {
      id:"TW:00403A", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"00403A", name:"主動統一升級50", sector:"fund",
      sub_industry:"台灣主動式 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["統一台股升級50主動式ETF","統一升級50","主動統一升級50"],
      etf:{
        issuer:"統一證券投資信託股份有限公司",
        category:"主動式 ETF",
        benchmark:"臺灣證券交易所發行量加權股價報酬指數",
        strategy:"至少六成配置台股市值前 200 大企業，以前 50 大為核心，搭配 51–200 大增強選股池。",
        distribution:"尚無配息資料",
        official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/00403A"
      }
    },
    "TW:00981A": {
      id:"TW:00981A", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"00981A", name:"主動統一台股增長", sector:"fund",
      sub_industry:"台灣主動式 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["統一台股增長主動式ETF","統一台股增長","主動統一台股增長"],
      etf:{
        issuer:"統一證券投資信託股份有限公司",
        category:"主動式 ETF",
        benchmark:"臺灣證券交易所發行量加權股價報酬指數",
        strategy:"以大型、創新、成長為核心選股邏輯，至少六成配置大型股。",
        distribution:"季配；歷史配息依官方公告",
        official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/00981A"
      }
    },
    "TW:009816": {
      id:"TW:009816", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"009816", name:"凱基台灣TOP50", sector:"fund",
      sub_industry:"台灣市值型 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["凱基台灣 TOP 50","凱基TOP50"],
      etf:{
        issuer:"凱基證券投資信託股份有限公司",
        category:"台股 ETF",
        benchmark:"臺灣指數公司特選臺灣 TOP 50 指數",
        strategy:"追蹤特選臺灣 TOP 50 指數，聚焦大型權值企業。",
        distribution:"尚無配息資料",
        official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/009816"
      }
    },
    "TW:00663L": {
      id:"TW:00663L", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"00663L", name:"國泰臺灣加權正2", sector:"fund",
      sub_industry:"台灣槓桿型 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["國泰臺指正2","國泰臺灣加權指數單日正向2倍基金"],
      etf:{
        issuer:"國泰證券投資信託股份有限公司",
        manager:"蘇鼎宇",
        category:"股票槓反ETF",
        benchmark:"臺灣日報酬兩倍指數",
        leverage:"單日正向 2 倍",
        strategy:"追求臺灣加權指數單日報酬的兩倍。",
        distribution:"尚無配息資料",
        official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/00663L"
      }
    },
    "TW:00631L": {
      id:"TW:00631L", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"00631L", name:"元大台灣50正2", sector:"fund",
      sub_industry:"台灣槓桿型 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["台灣50正2","元大台灣50單日正向2倍"],
      etf:{
        issuer:"元大證券投資信託股份有限公司",
        category:"股票槓反 ETF",
        benchmark:"臺灣 50 指數",
        leverage:"單日正向 2 倍",
        strategy:"追求臺灣 50 指數單日報酬的兩倍；不適合以兩倍長期報酬直線推估。",
        distribution:"尚無配息資料",
        official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/00631L"
      }
    },
    "TW:0050": {
      id:"TW:0050", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"0050", name:"元大台灣50", sector:"fund",
      sub_industry:"台灣市值型 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["元大台灣卓越50","台灣50"],
      etf:{issuer:"元大證券投資信託股份有限公司",category:"台股 ETF",benchmark:"臺灣 50 指數",distribution:"依官方公告",official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/0050"}
    },
    "TW:006208": {
      id:"TW:006208", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"006208", name:"富邦台50", sector:"fund",
      sub_industry:"台灣市值型 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["富邦台灣50","富邦台灣釆吉50"],
      etf:{issuer:"富邦證券投資信託股份有限公司",category:"台股 ETF",benchmark:"臺灣 50 指數",distribution:"依官方公告",official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/006208"}
    }
  };

  const $ = (selector, root=document) => root.querySelector(selector);
  const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];
  const normalize = value => String(value || "").normalize("NFKC").toLowerCase().replace(/[\s._\-\/]+/g, "");
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[ch]));
  const finite = value => value === null || value === undefined || value === "" ? null :
    Number.isFinite(Number(value)) ? Number(value) : null;

  function cacheBust(url) {
    return `${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`;
  }

  async function fetchJson(url, timeout=10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(cacheBust(url), {cache:"no-store", signal:controller.signal, headers:{Accept:"application/json"}});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally {
      clearTimeout(timer);
    }
  }

  function scorePayload(payload) {
    return ["assets","items","events","announcements","daily","financials"].reduce((sum,key) =>
      sum + (Array.isArray(payload?.[key]) ? payload[key].length : 0), 0);
  }

  async function loadData(path, fallback={}) {
    const clean = String(path || "").replace(/^\.?\//,"").replace(/^data\//,"");
    const local = path.startsWith("data/") ? path : `data/${clean}`;
    const candidates = [
      ["live", `${LIVE_BASE}${clean}`],
      ["local", local],
      ["main", `${MAIN_BASE}data/${clean}`]
    ];
    const results = await Promise.allSettled(candidates.map(([,url]) => fetchJson(url)));
    const available = results.flatMap((result,index) => result.status === "fulfilled"
      ? [{...result.value, __source:candidates[index][0], __priority:3-index}]
      : []);
    if (!available.length) return {...fallback, __source:"fallback"};
    available.sort((a,b) => scorePayload(b)-scorePayload(a) ||
      Date.parse(b?.metadata?.updated_at || b?.updated_at || 0)-Date.parse(a?.metadata?.updated_at || a?.updated_at || 0) ||
      b.__priority-a.__priority);
    const selected = {...available[0]};
    delete selected.__priority;
    return selected;
  }

  function canonicalAsset(raw={}) {
    const symbol = String(raw.symbol || "").trim().toUpperCase();
    const market = String(raw.market || (symbol.match(/^\d/) ? "TW" : "US")).toUpperCase();
    const id = String(raw.id || `${market}:${symbol}`).toUpperCase();
    const override = OFFICIAL_OVERRIDES[id] || {};
    const merged = {
      aliases:[], themes:[], metrics:{}, financials:[], listing_status:"active",
      ...raw, ...override, id:override.id || id, symbol:override.symbol || symbol, market:override.market || market
    };
    merged.aliases = [...new Set([...(raw.aliases || []), ...(override.aliases || [])].filter(Boolean))];
    if (raw.etf || override.etf) {
      merged.etf = {...(override.etf || {}), ...(raw.etf || {})};
    }
    merged.search_blob = normalize([
      merged.symbol, merged.name, merged.market, merged.exchange, merged.sector,
      merged.sub_industry, merged.official_industry, ...merged.aliases
    ].join(" "));
    return merged;
  }

  function mergeAssets(primary=[], seed=[]) {
    const map = new Map();
    [...seed, ...primary].forEach(raw => {
      const asset = canonicalAsset(raw);
      if (!asset.id || !asset.symbol) return;
      map.set(asset.id, canonicalAsset({...map.get(asset.id), ...asset}));
    });
    Object.values(OFFICIAL_OVERRIDES).forEach(raw => map.set(raw.id, canonicalAsset({...map.get(raw.id), ...raw})));
    return [...map.values()];
  }

  function exactCodeLike(query) {
    return /^[0-9]{4,6}[A-Z]?$/i.test(String(query || "").trim());
  }

  function searchAssets(assets, query, options={}) {
    const raw = String(query || "").trim();
    const q = normalize(raw);
    if (!q) return [];
    const market = options.market || "all";
    const assetClass = options.asset_class || "all";
    const pool = assets.filter(asset => market === "all" || asset.market === market)
      .filter(asset => assetClass === "all" || asset.asset_class === assetClass ||
        (assetClass === "stock" && asset.asset_class === "etf"));

    if (exactCodeLike(raw)) {
      return pool.filter(asset => normalize(asset.symbol) === q);
    }

    return pool.map(asset => {
      const symbol = normalize(asset.symbol);
      const name = normalize(asset.name);
      let score = 0;
      if (symbol === q) score += 1000;
      else if (symbol.startsWith(q)) score += 500;
      if (name === q) score += 900;
      else if (name.startsWith(q)) score += 450;
      else if (name.includes(q)) score += 220;
      if (asset.search_blob.includes(q)) score += 120;
      return {asset, score};
    }).filter(row => row.score > 0)
      .sort((a,b) => b.score-a.score || a.asset.symbol.localeCompare(b.asset.symbol))
      .slice(0,12).map(row => row.asset);
  }

  function resolveAsset(assets, value, options={}) {
    const raw = String(value || "").trim();
    const q = normalize(raw);
    const results = searchAssets(assets, raw, options);
    const exact = results.find(asset => normalize(asset.symbol) === q || normalize(asset.name) === q ||
      (asset.aliases || []).some(alias => normalize(alias) === q));
    return exact || (exactCodeLike(raw) ? null : results[0]) || null;
  }

  function loadPortfolio() {
    let raw = localStorage.getItem(PORTFOLIO_KEY);
    if (!raw) {
      for (const key of LEGACY_PORTFOLIO_KEYS) {
        raw = localStorage.getItem(key);
        if (raw) break;
      }
    }
    let rows = [];
    try { rows = JSON.parse(raw || "[]"); } catch {}
    return Array.isArray(rows) ? rows : [];
  }

  function migratePortfolio(entries, assets) {
    const migrated = entries.map(entry => {
      const symbol = String(entry.symbol || String(entry.asset_id || "").split(":").pop() || "").toUpperCase();
      const market = entry.market || (String(entry.asset_id || "").startsWith("TW:") || /^\d/.test(symbol) ? "TW" : "US");
      const resolved = resolveAsset(assets, symbol, {market, asset_class:"all"}) ||
        canonicalAsset({...entry, symbol, market});
      return {
        ...entry, ...resolved,
        id: entry.id || (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`),
        asset_id: resolved.id || `${market}:${symbol}`,
        symbol: resolved.symbol || symbol,
        name: resolved.name || entry.name || symbol,
        market: resolved.market || market,
        asset_class: resolved.asset_class || entry.asset_class || "stock"
      };
    });
    savePortfolio(migrated);
    return migrated;
  }

  function savePortfolio(entries) {
    localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(entries));
    window.dispatchEvent(new CustomEvent("market-portfolio-changed", {detail:entries}));
  }

  function quoteMap(payload) {
    return new Map((payload?.items || []).map(item => [
      `${String(item.exchange || "TWSE").toUpperCase()}:${String(item.symbol || "").toUpperCase()}`, item
    ]));
  }

  function findTwQuote(entry, payload) {
    const symbol = String(entry.symbol || "").toUpperCase();
    const items = payload?.items || [];
    return items.find(item => String(item.symbol).toUpperCase() === symbol) || null;
  }

  function loadQuoteCache() {
    try { return JSON.parse(localStorage.getItem(QUOTE_CACHE_KEY) || "{}"); }
    catch { return {}; }
  }

  function saveQuoteCache(cache) {
    try { localStorage.setItem(QUOTE_CACHE_KEY, JSON.stringify(cache)); } catch {}
  }

  function formatPrice(value, currency="TWD") {
    const number = finite(value);
    if (number === null) return "—";
    const digits = number >= 1000 ? 0 : number >= 100 ? 1 : number >= 10 ? 2 : number >= 1 ? 3 : 5;
    const prefix = currency === "USD" ? "$" : currency === "TWD" ? "NT$" : "";
    return `${prefix}${number.toLocaleString("zh-TW",{maximumFractionDigits:digits})}`;
  }

  function formatPercent(value) {
    const number = finite(value);
    return number === null ? "—" : `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
  }

  function formatMoney(value, signed=false) {
    const number = finite(value);
    if (number === null) return "—";
    return `${signed && number > 0 ? "+" : ""}NT$${Math.round(number).toLocaleString("zh-TW")}`;
  }

  function formatVolume(value) {
    const number = finite(value);
    if (number === null) return "—";
    if (number >= 100000000) return `${(number/100000000).toFixed(1)}億`;
    if (number >= 10000) return `${(number/10000).toFixed(1)}萬`;
    return Math.round(number).toLocaleString("zh-TW");
  }

  function direction(value) {
    const number = finite(value);
    return number === null || number === 0 ? "flat" : number > 0 ? "up" : "down";
  }

  function formatTime(value) {
    if (!value) return "尚無時間";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "尚無時間";
    return date.toLocaleString("zh-TW",{timeZone:"Asia/Taipei",month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false});
  }

  function safeNewsLink(item) {
    const value = item?.pdf_link || item?.article_link || item?.direct_link || item?.link || item?.url || "";
    try {
      const url = new URL(value, location.href);
      if (!["http:","https:"].includes(url.protocol)) return "#";
      // TWSE /rwd/ newsDetail is a JSON API. Convert legacy live-data
      // links to the readable article route before opening a new tab.
      if (/(^|\.)twse\.com\.tw$/i.test(url.hostname) && /\/rwd\/(?:zh|en)\/news\/newsDetail\//i.test(url.pathname)) {
        url.pathname = url.pathname.replace(/\/rwd\/(zh|en)\/news\/newsDetail\//i, "/$1/news/newsDetail/");
      }
      return url.href;
    } catch { return "#"; }
  }

  function newsIdentity(item) {
    if (item?.cluster_id) return String(item.cluster_id);
    const raw = String(item?.title || "").normalize("NFKC");
    const date = String(item?.published_at || "").slice(0,10);
    if (/(?:排行|排名).*?(?:前|Top)\s*\d+\s*名/i.test(raw)) {
      const market = raw.includes("上市") ? "上市" : raw.includes("上櫃") ? "上櫃" : "市場";
      const family = /外資|投信|自營商|融資|融券|借券/.test(raw) ? "法人籌碼" : "市場排行";
      return `template:${date}:${market}:${family}`;
    }
    const title = raw.toLowerCase()
      .replace(/\bhttps?:\/\/\S+/g, "")
      .replace(/[\s\p{P}\p{S}]+/gu, "");
    return title || String(item?.id || item?.link || "");
  }

  function diversifyNews(items, limit=Infinity) {
    const identityGroups = new Map();
    (items || []).forEach(item => {
      const key = newsIdentity(item);
      if (!key) return;
      if (!identityGroups.has(key)) identityGroups.set(key, []);
      identityGroups.get(key).push(item);
    });
    const unique = [...identityGroups.values()].map(rows => {
      rows.sort((a,b) => Date.parse(b.published_at || 0)-Date.parse(a.published_at || 0));
      const primary = {...rows[0]};
      const existing = Number(primary.duplicate_count || primary.related_count || 0);
      primary.duplicate_count = existing + Math.max(0, rows.length - 1);
      primary.related_sources = [...new Set([
        ...(primary.related_sources || []),
        ...rows.map(row => row.source).filter(Boolean)
      ])];
      return primary;
    });
    const groups = new Map();
    unique
      .sort((a,b) => Date.parse(b.published_at || 0)-Date.parse(a.published_at || 0))
      .forEach(item => {
        const source = String(item.source || "其他來源");
        if (!groups.has(source)) groups.set(source, []);
        groups.get(source).push(item);
      });

    const output = [];
    let lastSource = "";
    while (output.length < limit) {
      const available = [...groups.entries()].filter(([,queue]) => queue.length);
      if (!available.length) break;
      let choices = available.filter(([source]) => source !== lastSource);
      if (!choices.length) choices = available;
      choices.sort((a,b) => Date.parse(b[1][0]?.published_at || 0)-Date.parse(a[1][0]?.published_at || 0));
      const [source, queue] = choices[0];
      output.push(queue.shift());
      lastSource = source;
    }
    return output;
  }

  const SECTOR_TERMS = {
    technology:["科技","AI","人工智慧","半導體","晶片","伺服器","軟體","雲端","電子","CoWoS","先進製程"],
    finance:["金融","金控","銀行","保險","證券","利率","房貸"],
    shipping:["航運","海運","貨櫃","散裝","運價","SCFI","航空","物流"],
    industrial:["機械","工具機","重電","自動化","製造"],
    materials:["鋼鐵","水泥","塑化","化工","原物料","紡織"],
    consumer:["消費","零售","百貨","電商","餐飲","食品"],
    healthcare:["生技","製藥","醫療","新藥","醫材"],
    energy:["能源","原油","天然氣","綠能","太陽能","風電","儲能"],
    fund:["ETF","基金","淨值","折溢價","配息","成分股","資產配置","台股","加權指數"]
  };

  function newsKeywords(asset) {
    const values = new Set([asset.symbol, asset.name, ...(asset.aliases || []), asset.sub_industry, asset.official_industry]);
    (SECTOR_TERMS[asset.sector] || []).forEach(v => values.add(v));
    if (asset.asset_class === "etf") {
      (SECTOR_TERMS.fund || []).forEach(v => values.add(v));
      [asset.etf?.benchmark, asset.etf?.category].filter(Boolean).forEach(v => values.add(v));
      (asset.etf?.holdings || []).slice(0,10).forEach(row => values.add(row.name || row.symbol));
    }
    return [...values].filter(Boolean).map(normalize).filter(v => v.length >= 2);
  }

  function newsScore(item, asset) {
    const text = normalize(`${item.title || ""} ${item.summary || ""} ${item.source || ""} ${(item.tags || []).join(" ")}`);
    let score = 0;
    const symbol = normalize(asset.symbol);
    newsKeywords(asset).forEach(keyword => {
      if (!text.includes(keyword)) return;
      score += keyword === symbol ? 120 : keyword === normalize(asset.name) ? 95 : 15;
    });
    if (asset.asset_class === "etf" && /ETF|基金|指數|成分股/i.test(`${item.title} ${item.summary}`)) score += 12;
    return score;
  }

  window.MR = {
    VERSION, OWNER, REPO, LIVE_BASE, MAIN_BASE, PORTFOLIO_KEY, OFFICIAL_OVERRIDES,
    $, $$, normalize, escapeHtml, finite, fetchJson, loadData, canonicalAsset, mergeAssets,
    searchAssets, resolveAsset, loadPortfolio, migratePortfolio, savePortfolio,
    findTwQuote, loadQuoteCache, saveQuoteCache, formatPrice, formatPercent, formatMoney,
    formatVolume, direction, formatTime, safeNewsLink, diversifyNews, newsKeywords, newsScore
  };
})();
