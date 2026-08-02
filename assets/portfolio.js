(() => {
  "use strict";

  const STORAGE_KEY = "market-radar-portfolio-v10-3";
  const LEGACY_KEYS = ["market-radar-portfolio-v10"];
  const state = { entries: [], news: [], events: [], assetsReady: false, quotes: new Map(), quoteLoading: false, quoteTimer: null };

  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const escapeHtml = v => String(v || "").replace(/[&<>\"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
  const normalize = v => window.MarketAssets?.normalize(v) || String(v || "").toLowerCase().replace(/\s+/g,"");
  const QUOTE_CACHE_KEY = "market-radar-portfolio-quotes-v10-5";
  const QUOTE_REFRESH_MS = 30000;

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
    startQuoteLoop();
    refreshQuotes(true);
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


  function quoteKey(entry) {
    return entry.asset_id || `${entry.market || "GLOBAL"}:${entry.symbol || entry.name}`;
  }

  function loadQuoteCache() {
    try {
      const raw = JSON.parse(localStorage.getItem(QUOTE_CACHE_KEY) || "{}");
      Object.entries(raw).forEach(([key, value]) => {
        if (value && Number.isFinite(Number(value.price))) state.quotes.set(key, value);
      });
    } catch {}
  }

  function saveQuoteCache() {
    try {
      const serializable = {};
      state.quotes.forEach((value, key) => { serializable[key] = value; });
      localStorage.setItem(QUOTE_CACHE_KEY, JSON.stringify(serializable));
    } catch {}
  }

  function yahooSymbol(entry) {
    const symbol = String(entry.symbol || "").trim().toUpperCase();
    if (!symbol || symbol === "FUND") return "";
    if (entry.asset_class === "crypto") return `${symbol}-USD`;
    if (entry.market === "TW") return `${symbol}${String(entry.exchange || "").toUpperCase().includes("TPEX") ? ".TWO" : ".TW"}`;
    return symbol;
  }

  function coinGeckoId(entry) {
    return ({BTC:"bitcoin",ETH:"ethereum",USDT:"tether",USDC:"usd-coin",BNB:"binancecoin",SOL:"solana",XRP:"ripple",DOGE:"dogecoin",ADA:"cardano",AVAX:"avalanche-2",LINK:"chainlink",UNI:"uniswap"})[String(entry.symbol || "").toUpperCase()] || "";
  }

  async function fetchJson(url, timeout = 9000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, { cache:"no-store", signal:controller.signal, headers:{"Accept":"application/json"} });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally { clearTimeout(timer); }
  }

  function finite(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function normalizePoints(timestamps, closes, limit = 55) {
    const rows = [];
    (timestamps || []).forEach((timestamp, index) => {
      const value = finite(closes?.[index]);
      if (value !== null) rows.push({ t:Number(timestamp) * 1000, v:value });
    });
    return rows.slice(-limit);
  }

  async function fetchYahooQuote(entry) {
    const symbol = yahooSymbol(entry);
    if (!symbol) throw new Error("沒有公開行情代碼");
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=5d&interval=5m&includePrePost=false&events=div%2Csplits`;
    const payload = await fetchJson(url);
    const result = payload?.chart?.result?.[0];
    if (!result) throw new Error(payload?.chart?.error?.description || "行情不存在");
    const meta = result.meta || {};
    const closes = result?.indicators?.quote?.[0]?.close || [];
    const points = normalizePoints(result.timestamp || [], closes);
    const price = finite(meta.regularMarketPrice) ?? points.at(-1)?.v ?? null;
    const previous = finite(meta.chartPreviousClose) ?? finite(meta.previousClose) ?? (points.length > 1 ? points.at(-2).v : null);
    if (price === null) throw new Error("行情價格空白");
    const change = previous !== null ? price - previous : null;
    const changePercent = previous ? change / previous * 100 : null;
    const latestAt = finite(meta.regularMarketTime) ? Number(meta.regularMarketTime) * 1000 : (points.at(-1)?.t || Date.now());
    const age = Math.max(0, Date.now() - latestAt);
    const isCrypto = entry.asset_class === "crypto";
    const liveWindow = isCrypto ? 3 * 60e3 : 12 * 60e3;
    return {
      price, previous, change, changePercent, points,
      currency: meta.currency || entry.currency || (isCrypto ? "USD" : ""),
      source: "Yahoo 公開行情", fetchedAt:Date.now(), marketAt:latestAt,
      mode: age <= liveWindow ? (isCrypto ? "近即時" : "盤中／延遲") : "前次收盤",
      status:"ok", symbol
    };
  }

  async function fetchCoinGeckoQuote(entry) {
    const id = coinGeckoId(entry);
    if (!id) throw new Error("CoinGecko 未收錄對照");
    const payload = await fetchJson(`https://api.coingecko.com/api/v3/simple/price?ids=${encodeURIComponent(id)}&vs_currencies=usd&include_24hr_change=true&include_last_updated_at=true`);
    const row = payload?.[id];
    const price = finite(row?.usd);
    const changePercent = finite(row?.usd_24h_change);
    if (price === null) throw new Error("CoinGecko 價格空白");
    const previous = changePercent !== null && changePercent > -100 ? price / (1 + changePercent / 100) : null;
    return {
      price, previous, change:previous !== null ? price - previous : null, changePercent,
      points:[], currency:"USD", source:"CoinGecko 備援", fetchedAt:Date.now(),
      marketAt:finite(row?.last_updated_at) ? Number(row.last_updated_at) * 1000 : Date.now(),
      mode:"延遲備援", status:"fallback", symbol:String(entry.symbol || "")
    };
  }

  async function fetchQuote(entry) {
    try { return await fetchYahooQuote(entry); }
    catch (primaryError) {
      if (entry.asset_class === "crypto") {
        try { return await fetchCoinGeckoQuote(entry); }
        catch {}
      }
      const cached = state.quotes.get(quoteKey(entry));
      if (cached) return { ...cached, mode:"上次成功資料", status:"stale", error:String(primaryError?.message || primaryError) };
      return { price:null, previous:null, change:null, changePercent:null, points:[], currency:entry.currency || "", source:"", fetchedAt:Date.now(), marketAt:null, mode:"等待行情", status:"pending", error:String(primaryError?.message || primaryError) };
    }
  }

  function formatPrice(value, currency = "") {
    if (!Number.isFinite(Number(value))) return "—";
    const number = Number(value);
    const digits = number >= 1000 ? 0 : number >= 10 ? 2 : number >= 1 ? 3 : 5;
    const prefix = currency === "USD" ? "$" : currency === "TWD" ? "NT$" : "";
    return `${prefix}${number.toLocaleString("zh-TW", { maximumFractionDigits:digits, minimumFractionDigits: number < 1 ? Math.min(2,digits) : 0 })}`;
  }

  function formatPercent(value) {
    if (!Number.isFinite(Number(value))) return "—";
    const number = Number(value);
    return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
  }

  function formatQuoteTime(value) {
    if (!value) return "尚無時間";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "尚無時間";
    return date.toLocaleString("zh-TW", { month:"numeric", day:"numeric", hour:"2-digit", minute:"2-digit", hour12:false });
  }

  function sparkline(points, direction = "flat") {
    const values = (points || []).map(point => Number(point.v)).filter(Number.isFinite);
    if (values.length < 2) return `<svg class="portfolio-sparkline ${direction}" viewBox="0 0 180 52" aria-label="尚無盤中走勢"><path class="sparkline-flat" d="M4 27 L176 27"/></svg>`;
    const min = Math.min(...values), max = Math.max(...values), spread = max - min || 1;
    const path = values.map((value, index) => {
      const x = 4 + index / Math.max(1, values.length - 1) * 172;
      const y = 47 - (value - min) / spread * 42;
      return `${index ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
    }).join(" ");
    return `<svg class="portfolio-sparkline ${direction}" viewBox="0 0 180 52" role="img" aria-label="近期價格走勢"><path class="sparkline-area" d="${path} L176 50 L4 50 Z"/><path class="sparkline-line" d="${path}"/></svg>`;
  }

  function quoteCard(entry) {
    const quote = state.quotes.get(quoteKey(entry)) || {};
    const pct = finite(quote.changePercent);
    const direction = pct === null ? "flat" : pct > 0 ? "up" : pct < 0 ? "down" : "flat";
    const href = `asset.html?id=${encodeURIComponent(entry.asset_id || entry.id)}`;
    return `<a class="portfolio-quote-card ${direction} status-${escapeHtml(quote.status || "pending")}" href="${href}">
      <div class="portfolio-quote-top">
        <span class="asset-type ${escapeHtml(entry.asset_class)}">${typeLabel(entry)}</span>
        <div><strong>${escapeHtml(entry.name)}</strong><small>${escapeHtml(entry.symbol || "—")} · ${escapeHtml(entry.exchange || entry.market || "自訂")}</small></div>
        <b>${formatPercent(pct)}</b>
      </div>
      <div class="portfolio-quote-body">
        <div><strong>${formatPrice(quote.price, quote.currency || entry.currency)}</strong><small>前收 ${formatPrice(quote.previous, quote.currency || entry.currency)}</small></div>
        ${sparkline(quote.points, direction)}
      </div>
      <div class="portfolio-quote-foot"><span>${escapeHtml(quote.mode || "等待行情")} · ${formatQuoteTime(quote.marketAt)}</span><em>${escapeHtml(quote.source || "尚無來源")}</em></div>
    </a>`;
  }

  function renderQuoteGrid() {
    const grid = $("#portfolioQuoteGrid");
    if (!grid) return;
    grid.innerHTML = state.entries.map(quoteCard).join("");
  }

  function setQuoteStatus() {
    const node = $("#portfolioQuoteStatus");
    if (!node) return;
    if (state.quoteLoading) { node.textContent = "行情更新中"; node.dataset.state = "loading"; return; }
    const quotes = state.entries.map(entry => state.quotes.get(quoteKey(entry))).filter(Boolean);
    const live = quotes.filter(quote => ["近即時","盤中／延遲"].includes(quote.mode)).length;
    const stale = quotes.filter(quote => ["前次收盤","上次成功資料"].includes(quote.mode)).length;
    node.textContent = live ? `${live} 項盤中／近即時` : stale ? `${stale} 項前次收盤` : "等待行情";
    node.dataset.state = live ? "live" : stale ? "close" : "pending";
  }

  async function refreshQuotes(force = false) {
    if (state.quoteLoading || !state.entries.length || document.hidden) return;
    state.quoteLoading = true;
    setQuoteStatus();
    const entries = [...state.entries];
    const workers = [];
    let cursor = 0;
    const worker = async () => {
      while (cursor < entries.length) {
        const entry = entries[cursor++];
        const key = quoteKey(entry);
        const existing = state.quotes.get(key);
        if (!force && existing && Date.now() - Number(existing.fetchedAt || 0) < QUOTE_REFRESH_MS - 2000) continue;
        const quote = await fetchQuote(entry);
        state.quotes.set(key, quote);
        renderQuoteGrid();
        setQuoteStatus();
      }
    };
    for (let i = 0; i < Math.min(4, entries.length); i++) workers.push(worker());
    await Promise.all(workers);
    state.quoteLoading = false;
    saveQuoteCache();
    renderQuoteGrid();
    setQuoteStatus();
  }

  function startQuoteLoop() {
    clearInterval(state.quoteTimer);
    if (!state.entries.length) return;
    refreshQuotes(false);
    state.quoteTimer = setInterval(() => refreshQuotes(false), QUOTE_REFRESH_MS);
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
    const empty = $("#portfolioFocusEmpty"), content = $("#portfolioFocusContent"), count = $("#portfolioAssetCount");
    if (!empty || !content) return;
    if (count) count.textContent = `${state.entries.length} 個標的`;
    empty.hidden = state.entries.length > 0;
    content.hidden = state.entries.length === 0;
    renderQuoteGrid();
    setQuoteStatus();
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

  window.addEventListener("market-assets-loaded",()=>{state.assetsReady=true;migrateEntries();renderEverywhere();startQuoteLoop();});
  window.addEventListener("market-news-loaded",event=>{state.news=event.detail.items||[];renderEverywhere();});
  loadQuoteCache();
  load();
  state.events=window.__MARKET_EVENT_SEED__?.events||[];
  bindForms(); bindDialog(); renderEverywhere(); startQuoteLoop();
  window.addEventListener("online",()=>refreshQuotes(true));
  document.addEventListener("visibilitychange",()=>{ if(!document.hidden) refreshQuotes(true); });

  window.MarketPortfolio={state,addResolved,remove,save,newsForPortfolio,eventsForPortfolio};
})();