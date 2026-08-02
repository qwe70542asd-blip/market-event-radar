(() => {
  "use strict";

  const STORAGE_KEY = "market-radar-portfolio-v10-3";
  const LEGACY_KEYS = ["market-radar-portfolio-v10"];
  const state = { entries: [], news: [], events: [], assetsReady: false };

  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const escapeHtml = v => String(v || "").replace(/[&<>\"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
  const normalize = v => window.MarketAssets?.normalize(v) || String(v || "").toLowerCase().replace(/\s+/g,"");

  const SECTOR_KEYWORDS = {
    technology:["科技","AI","人工智慧","半導體","晶片","伺服器","軟體","雲端","電子"],
    finance:["金融","金控","銀行","保險","證券","利差","房貸"],
    shipping:["航運","海運","貨櫃","散裝","運價","SCFI","航空","物流"],
    industrial:["機械","工具機","重電","自動化","製造業"],
    materials:["鋼鐵","水泥","塑化","化工","原物料","紡織"],
    consumer:["消費","零售","百貨","電商","餐飲","食品"],
    healthcare:["生技","製藥","醫療","新藥","醫材"],
    energy:["能源","原油","天然氣","綠能","太陽能","風電","儲能"],
    automotive:["汽車","電動車","車用","輪胎"],
    tourism:["觀光","飯店","旅行社","旅遊","休閒"],
    fund:["基金","ETF","淨值","配息","成分股","資產配置"],
    crypto:["加密貨幣","虛擬貨幣","區塊鏈","比特幣","以太坊","穩定幣","DeFi","交易所"]
  };

  function load() {
    let raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      for (const key of LEGACY_KEYS) {
        raw = localStorage.getItem(key);
        if (raw) break;
      }
    }
    try { state.entries = Array.isArray(JSON.parse(raw || "[]")) ? JSON.parse(raw || "[]") : []; }
    catch { state.entries = []; }
    migrateEntries();
  }

  function migrateEntries() {
    state.entries = state.entries.map(entry => {
      const type = entry.asset_class || entry.type || (entry.symbol?.match(/^[A-Z0-9]{2,10}$/) ? "stock" : "fund");
      const resolved = window.MarketAssets?.resolve(entry.symbol || entry.name, {
        asset_class: type === "etf" ? "stock" : type,
        market: entry.market || "all"
      });
      if (resolved) return { ...entry, ...resolved, id: entry.id || crypto.randomUUID(), asset_id: resolved.id, asset_class: resolved.asset_class };
      return {
        ...entry,
        id: entry.id || (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`),
        asset_class: type === "etf" ? "stock" : type,
        symbol: String(entry.symbol || "未提供代碼").toUpperCase(),
        name: entry.name || entry.symbol || "未命名標的",
        sector: entry.sector || entry.theme || (type === "fund" ? "fund" : "other"),
        manual: true
      };
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.entries));
  }

  function save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.entries));
    window.dispatchEvent(new CustomEvent("market-portfolio-changed", { detail: state.entries }));
    renderEverywhere();
  }

  function typeLabel(entry) {
    if (entry.asset_class === "crypto") return "虛擬貨幣";
    if (entry.asset_class === "fund" || entry.asset_class === "etf") return entry.asset_class === "etf" ? "ETF" : "基金";
    return "股票";
  }

  function entryKeywords(entry) {
    const set = new Set([entry.symbol, entry.name, entry.official_industry, entry.sector, entry.sub_industry, ...(entry.aliases || [])]);
    (SECTOR_KEYWORDS[entry.sector] || []).forEach(x => set.add(x));
    if (entry.asset_class === "crypto") (SECTOR_KEYWORDS.crypto || []).forEach(x => set.add(x));
    if (["fund","etf"].includes(entry.asset_class)) (SECTOR_KEYWORDS.fund || []).forEach(x => set.add(x));
    return [...set].filter(Boolean).map(normalize).filter(x => x.length >= 2);
  }

  function relevanceForNews(item, entry) {
    const text = normalize(`${item.title||""} ${item.summary||""} ${item.source||""} ${(item.industries||[]).join(" ")}`);
    let score = 0;
    [entry.symbol, entry.name, ...(entry.aliases||[])].filter(Boolean).map(normalize).forEach(key => {
      if (key.length >= 2 && text.includes(key)) score += key === normalize(entry.symbol) ? 110 : 85;
    });
    entryKeywords(entry).forEach(key => { if (text.includes(key)) score += 15; });
    const itemClass = item.asset_class || "stock";
    if (entry.asset_class === "crypto" && itemClass === "crypto") score += 20;
    if (["fund","etf"].includes(entry.asset_class) && itemClass === "fund") score += 20;
    if (entry.asset_class === "stock" && itemClass === "stock") score += 6;
    return score;
  }

  function relevanceForEvent(event, entry) {
    const text = normalize(`${event.title||""} ${event.description||""} ${event.market_effect||""} ${(event.assets||[]).join(" ")} ${(event.tags||[]).join(" ")}`);
    let score = 0;
    entryKeywords(entry).forEach(key => { if (text.includes(key)) score += 22; });
    if (entry.market === "TW" && /台灣|台股|新台幣/.test(text)) score += 7;
    if (entry.market === "US" && /美國|聯準會|美元|美債/.test(text)) score += 7;
    if (entry.asset_class === "crypto" && /加密|比特幣|以太坊|SEC|穩定幣/.test(text)) score += 12;
    return score;
  }

  function newsForPortfolio(limit = 8) {
    const rows = [];
    state.news.forEach(item => {
      let best = 0, reason = null;
      state.entries.forEach(entry => {
        const score = relevanceForNews(item, entry);
        if (score > best) { best = score; reason = entry; }
      });
      if (best > 0) rows.push({ item, score: best, reason });
    });
    return rows.sort((a,b)=>b.score-a.score || new Date(b.item.published_at||0)-new Date(a.item.published_at||0)).slice(0,limit);
  }

  function eventsForPortfolio(limit = 6) {
    const now = Date.now() - 6*3600e3;
    const rows = [];
    state.events.forEach(event => {
      if (new Date(event.start).getTime() < now) return;
      let best=0, reason=null;
      state.entries.forEach(entry => {
        const score = relevanceForEvent(event, entry);
        if (score > best) { best=score; reason=entry; }
      });
      if (best > 0) rows.push({event,score:best,reason});
    });
    return rows.sort((a,b)=>b.score-a.score || new Date(a.event.start)-new Date(b.event.start)).slice(0,limit);
  }

  function renderEntryList(target) {
    if (!target) return;
    if (!state.entries.length) {
      target.innerHTML = '<div class="portfolio-empty-mini">尚未加入股票、基金或虛擬貨幣。</div>';
      return;
    }
    target.innerHTML = state.entries.map(entry => `
      <article class="portfolio-entry">
        <a class="portfolio-entry-main" href="asset.html?id=${encodeURIComponent(entry.asset_id || entry.id)}">
          <span class="asset-type ${entry.asset_class}">${typeLabel(entry)}</span>
          <div>
            <strong>${escapeHtml(entry.name)}</strong>
            <small>${escapeHtml(entry.symbol || "無公開代碼")} · ${escapeHtml(entry.exchange || entry.market || "自訂")}${entry.sub_industry ? ` · ${escapeHtml(entry.sub_industry)}` : ""}</small>
          </div>
        </a>
        <button type="button" data-remove-entry="${entry.id}" aria-label="移除">×</button>
      </article>`).join("");
    $$("[data-remove-entry]", target).forEach(btn => btn.addEventListener("click", () => remove(btn.dataset.removeEntry)));
  }

  function renderHome() {
    const empty=$("#portfolioFocusEmpty"), content=$("#portfolioFocusContent"), count=$("#portfolioAssetCount");
    const newsGrid=$("#portfolioNewsGrid"), eventList=$("#portfolioEventFocus");
    if (!empty || !content) return;
    count.textContent = `${state.entries.length} 個持有／追蹤標的`;
    empty.hidden = state.entries.length>0; content.hidden = state.entries.length===0;
    if (!state.entries.length) return;
    const relatedNews = newsForPortfolio(4);
    newsGrid.innerHTML = relatedNews.length ? relatedNews.map(({item,reason})=>`
      <a class="portfolio-news-card" href="${window.MarketNewsLink?.safeLink?.(item) || window.MarketNews?.safeLink?.(item) || item.link}" target="_blank" rel="noreferrer noopener">
        <div><span>${escapeHtml(item.source||"財經新聞")}</span><b>關聯：${escapeHtml(reason.name)} ${escapeHtml(reason.symbol||"")}</b></div>
        <h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.summary||"點擊前往原始新聞")}</p>
      </a>`).join("") : '<div class="portfolio-empty-mini">尚未找到直接相關新聞，下一次資料更新後會重新比對。</div>';
    const relatedEvents=eventsForPortfolio(4);
    eventList.innerHTML = relatedEvents.length ? relatedEvents.map(({event,reason})=>`
      <a class="portfolio-event-row" href="event.html?id=${encodeURIComponent(event.id)}">
        <time>${new Date(event.start).toLocaleString("zh-TW",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false})}</time>
        <span><strong>${escapeHtml(event.title)}</strong><small>可能影響：${escapeHtml(reason.name)} ${escapeHtml(reason.symbol||"")}</small></span>
        <b class="impact-${event.impact||"low"}">${event.impact==="high"?"高":event.impact==="medium"?"中":"低"}</b>
      </a>`).join("") : '<div class="portfolio-empty-mini">尚無明確關聯事件。</div>';
  }

  function renderPage() {
    const list=$("#portfolioPageEntries"); if (!list) return;
    renderEntryList(list);
    const stats=$("#portfolioPageStats");
    const counts = {
      stock: state.entries.filter(x=>x.asset_class==="stock").length,
      fund: state.entries.filter(x=>["fund","etf"].includes(x.asset_class)).length,
      crypto: state.entries.filter(x=>x.asset_class==="crypto").length
    };
    stats.innerHTML=`<article><span>全部</span><strong>${state.entries.length}</strong></article>
      <article><span>股票</span><strong>${counts.stock}</strong></article>
      <article><span>基金／ETF</span><strong>${counts.fund}</strong></article>
      <article><span>虛擬貨幣</span><strong>${counts.crypto}</strong></article>`;
    const feed=$("#portfolioPageNews"), related=newsForPortfolio(16);
    feed.innerHTML = related.length ? related.map(({item,reason})=>`
      <a class="portfolio-page-news" href="${window.MarketNewsLink?.safeLink?.(item) || window.MarketNews?.safeLink?.(item) || item.link}" target="_blank" rel="noreferrer noopener">
        <div><span>${escapeHtml(item.source||"財經新聞")}</span><b>${escapeHtml(reason.name)} ${escapeHtml(reason.symbol||"")}</b></div>
        <h2>${escapeHtml(item.title)}</h2><p>${escapeHtml(item.summary||"點擊前往原始來源")}</p>
      </a>`).join("") : '<div class="portfolio-empty-mini">加入標的後，這裡會優先顯示相關新聞。</div>';
  }

  function renderEverywhere() { renderHome(); renderPage(); renderEntryList($("#portfolioDialogList")); }

  function addResolved(asset, manual = {}) {
    const key = asset.id || `${asset.asset_class}:${asset.market}:${asset.symbol}`;
    if (state.entries.some(x => (x.asset_id || x.key) === key)) throw new Error("這個標的已經加入");
    state.entries.push({
      ...asset, ...manual,
      id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
      asset_id: asset.id || key,
      key
    });
    save();
  }

  function remove(id) { state.entries = state.entries.filter(x=>x.id!==id); save(); }

  function renderSuggestions(form, items) {
    const box=$(".asset-search-results",form);
    if (!box) return;
    box.innerHTML = items.map(asset=>`
      <button type="button" data-asset-id="${escapeHtml(asset.id)}">
        <span class="asset-class-badge ${asset.asset_class}">${asset.asset_class==="crypto"?"幣":asset.asset_class==="fund"||asset.asset_class==="etf"?"基金":"股"}</span>
        <b>${escapeHtml(asset.name)}</b><strong>${escapeHtml(asset.symbol)}</strong>
        <small>${escapeHtml(asset.exchange||asset.market)} · ${escapeHtml(asset.sub_industry||asset.official_industry||asset.sector)}</small>
      </button>`).join("");
    box.hidden = !items.length;
    $$("[data-asset-id]",box).forEach(btn=>btn.addEventListener("click",()=>{
      const asset=window.MarketAssets.byId(btn.dataset.assetId);
      form.dataset.selectedAssetId=asset.id;
      $('[name="query"]',form).value=`${asset.symbol} ${asset.name}`;
      box.hidden=true;
      const status=$(".portfolio-form-status",form);
      if(status) status.textContent=`已選擇：${asset.name}（${asset.symbol}）`;
    }));
  }

  function bindForms() {
    ["#portfolioAddForm","#portfolioPageAddForm"].forEach(selector=>{
      const form=$(selector); if(!form) return;
      const type=$('[name="asset_class"]',form), market=$('[name="market"]',form), query=$('[name="query"]',form);
      const codeField=$('[name="manual_code"]',form), nameField=$('[name="manual_name"]',form);
      const manualWrap=$(".manual-fund-fields",form);

      function sync() {
        const cls=type.value;
        market.closest(".market-field").hidden = cls==="crypto";
        manualWrap.hidden = cls!=="fund";
        query.placeholder = cls==="crypto" ? "搜尋 BTC、ETH、比特幣、以太坊…" : cls==="fund" ? "搜尋基金名稱；找不到可在下方手動輸入" : "搜尋代碼或名稱，例如 2330、台積電、NVDA";
        form.dataset.selectedAssetId="";
        renderSuggestions(form,[]);
      }
      type.addEventListener("change",sync); market.addEventListener("change",()=>{form.dataset.selectedAssetId="";});
      query.addEventListener("input",()=>{
        form.dataset.selectedAssetId="";
        const items=window.MarketAssets.search(query.value,{asset_class:type.value,market:type.value==="crypto"?"all":market.value});
        renderSuggestions(form,items);
      });
      form.addEventListener("submit",event=>{
        event.preventDefault();
        const status=$(".portfolio-form-status",form);
        try {
          const selected=form.dataset.selectedAssetId && window.MarketAssets.byId(form.dataset.selectedAssetId);
          if (selected) addResolved(selected);
          else if (type.value==="fund") {
            const name=String(nameField.value||query.value||"").trim();
            const symbol=String(codeField.value||"FUND").trim().toUpperCase();
            if(!name) throw new Error("請輸入基金名稱");
            addResolved({
              id:`FUND:${normalize(symbol)}:${normalize(name)}`, asset_class:"fund", market:market.value||"GLOBAL",
              exchange:"基金", symbol, name, sector:"fund", sub_industry:"共同基金", official_industry:"基金",
              currency:"", aliases:[], manual:true
            });
          } else {
            throw new Error("請從搜尋結果選擇正確的名稱與代碼");
          }
          form.reset(); sync(); if(status) status.textContent="已加入";
        } catch(error) { if(status) status.textContent=error.message; }
      });
      sync();
    });
  }

  function bindDialog() {
    const dialog=$("#portfolioDialog");
    ["#portfolioSetupBtn","#portfolioManageBtn"].forEach(selector=>$(selector)?.addEventListener("click",()=>{renderEntryList($("#portfolioDialogList"));dialog?.showModal();}));
    $("#closePortfolioDialog")?.addEventListener("click",()=>dialog?.close());
  }

  window.addEventListener("market-assets-loaded",()=>{state.assetsReady=true;migrateEntries();renderEverywhere();});
  window.addEventListener("market-news-loaded",event=>{state.news=event.detail.items||[];renderEverywhere();});
  load();
  state.events=window.__MARKET_EVENT_SEED__?.events||[];
  bindForms(); bindDialog(); renderEverywhere();

  window.MarketPortfolio={state,addResolved,remove,save,newsForPortfolio,eventsForPortfolio};
})();