(() => {
  "use strict";
  const root = document.getElementById("cryptoLiveList");
  if (!root) return;

  const $ = selector => document.querySelector(selector);
  const STABLE_IDS = new Set(["tether","usd-coin","dai","ethena-usde","first-digital-usd","paypal-usd","true-usd","usdd","frax","usdb"]);
  const WRAPPED_IDS = new Set(["wrapped-bitcoin","wrapped-steth","staked-ether","coinbase-wrapped-btc","binance-bridged-usdt-bnb-smart-chain"]);
  const GROUPS = [
    {id:"marketCap", title:"市值前 5 大", note:"排除穩定幣與包裝資產"},
    {id:"volume", title:"24H 交易量前 5 大", note:"排除穩定幣，依美元交易量"},
    {id:"stable", title:"穩定幣市值前 5 大", note:"監控價格是否偏離 1 美元"},
    {id:"surge", title:"短線突發爆量前 5 大", note:"最近 5 分鐘量 ÷ 前 12 根中位數"},
    {id:"newest", title:"最新交易所上架 5 種", note:"優先使用 Binance 官方上架公告"}
  ];

  const state = {
    groups:{marketCap:[],volume:[],stable:[],surge:[],newest:[]},
    index:0, paused:false, timer:null, websocket:null, marketRows:[], lastSocketAt:0
  };

  const escapeHtml = value => String(value ?? "").replace(/[&<>\"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const finite = value => Number.isFinite(Number(value)) ? Number(value) : null;
  const median = values => {
    const rows = values.filter(Number.isFinite).sort((a,b)=>a-b);
    if (!rows.length) return null;
    const mid = Math.floor(rows.length/2);
    return rows.length % 2 ? rows[mid] : (rows[mid-1]+rows[mid])/2;
  };

  async function fetchJson(url, timeout = 12000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, {cache:"no-store", signal:controller.signal, headers:{"Accept":"application/json"}});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally { clearTimeout(timer); }
  }

  function formatPrice(value) {
    const num = finite(value);
    if (num === null) return "—";
    const digits = num >= 1000 ? 0 : num >= 10 ? 2 : num >= 1 ? 3 : num >= .01 ? 4 : 7;
    return `$${num.toLocaleString("en-US", {maximumFractionDigits:digits})}`;
  }
  function formatCompact(value) {
    const num = finite(value);
    if (num === null) return "—";
    return new Intl.NumberFormat("zh-TW", {notation:"compact", maximumFractionDigits:1}).format(num);
  }
  function pct(value) {
    const num = finite(value);
    if (num === null) return "—";
    return `${num > 0 ? "+" : ""}${num.toFixed(2)}%`;
  }
  function direction(value) {
    const num = finite(value);
    return num === null || num === 0 ? "flat" : num > 0 ? "up" : "down";
  }

  function coinRow(item, groupId) {
    const change = finite(item.price_change_percentage_24h ?? item.changePercent);
    let metric = item.total_volume ? `量 ${formatCompact(item.total_volume)}` : item.market_cap ? `市值 ${formatCompact(item.market_cap)}` : item.metric || "";
    let alert = "";
    if (groupId === "stable") {
      const deviation = finite(item.current_price) === null ? null : Math.abs(Number(item.current_price)-1)*100;
      metric = deviation === null ? "等待價格" : deviation >= 1 ? `脫鉤 ${deviation.toFixed(2)}%` : deviation >= .3 ? `注意 ${deviation.toFixed(2)}%` : `偏離 ${deviation.toFixed(2)}%`;
      alert = deviation !== null && deviation >= 1 ? " alert" : deviation !== null && deviation >= .3 ? " warn" : "";
    }
    if (groupId === "surge") metric = `${finite(item.surgeRatio)?.toFixed(1) || "—"} 倍 · 5分量 ${formatCompact(item.recentVolume)}`;
    if (groupId === "newest") metric = item.listedAt ? new Date(item.listedAt).toLocaleDateString("zh-TW",{month:"numeric",day:"numeric"}) : (item.metric || "最新上架");
    const href = item.url || (item.id ? `https://www.coingecko.com/en/coins/${encodeURIComponent(item.id)}` : "https://www.binance.com/en/support/announcement/new-cryptocurrency-listing?c=48&navId=48");
    return `<a class="crypto-live-row ${direction(change)}${alert}" href="${escapeHtml(href)}" target="_blank" rel="noreferrer noopener" data-symbol="${escapeHtml(String(item.symbol || "").toUpperCase())}">
      <span class="crypto-rank">${escapeHtml(item.rank || "•")}</span>
      <div class="crypto-identity"><strong>${escapeHtml(String(item.symbol || "—").toUpperCase())}</strong><small>${escapeHtml(item.name || item.title || "Crypto")}</small></div>
      <div class="crypto-metric"><b data-price>${formatPrice(item.current_price)}</b><small>${escapeHtml(metric)}</small></div>
      <em data-change>${pct(change)}</em>
    </a>`;
  }

  function showGroup(index, animate = true) {
    state.index = (index + GROUPS.length) % GROUPS.length;
    const group = GROUPS[state.index];
    const rows = state.groups[group.id] || [];
    $("#cryptoGroupTitle").textContent = group.title;
    $("#cryptoGroupNote").textContent = group.note;
    $("#cryptoGroupCounter").textContent = `${state.index + 1}/${GROUPS.length}`;
    root.classList.toggle("group-swap", animate);
    root.innerHTML = rows.length
      ? rows.slice(0,5).map((item,i) => coinRow({...item,rank:item.rank || i+1},group.id)).join("")
      : `<div class="crypto-loading"><strong>${escapeHtml(group.title)}</strong><span>${group.id === "newest" ? "最新上架資料等待官方來源；其他排行仍會正常輪播。" : "資料來源暫時未回應，保留下一輪自動重試。"}</span></div>`;
    setTimeout(() => root.classList.remove("group-swap"), 420);
  }

  function resetRotation() {
    clearInterval(state.timer);
    if (!state.paused) state.timer = setInterval(() => showGroup(state.index + 1), 8000);
  }

  function bindControls() {
    $("#cryptoPrev")?.addEventListener("click", () => { showGroup(state.index - 1); resetRotation(); });
    $("#cryptoNext")?.addEventListener("click", () => { showGroup(state.index + 1); resetRotation(); });
    $("#cryptoPause")?.addEventListener("click", event => {
      state.paused = !state.paused;
      event.currentTarget.textContent = state.paused ? "▶" : "Ⅱ";
      event.currentTarget.setAttribute("aria-label", state.paused ? "繼續輪播" : "暫停輪播");
      resetRotation();
    });
    document.querySelector(".crypto-live-section")?.addEventListener("mouseenter", () => { clearInterval(state.timer); });
    document.querySelector(".crypto-live-section")?.addEventListener("mouseleave", resetRotation);
  }

  function deriveGroups(rows) {
    state.marketRows = rows;
    const tradable = rows.filter(row => row && !STABLE_IDS.has(row.id) && !WRAPPED_IDS.has(row.id) && finite(row.market_cap) !== null);
    state.groups.marketCap = [...tradable].sort((a,b)=>Number(a.market_cap||0)-Number(b.market_cap||0)).reverse().slice(0,5);
    state.groups.volume = [...tradable].sort((a,b)=>Number(b.total_volume||0)-Number(a.total_volume||0)).slice(0,5);
    state.groups.stable = rows.filter(row => STABLE_IDS.has(row.id)).sort((a,b)=>Number(b.market_cap||0)-Number(a.market_cap||0)).slice(0,5);
  }

  async function loadMarkets() {
    const url = "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h";
    try {
      const rows = await fetchJson(url);
      if (!Array.isArray(rows)) throw new Error("market list invalid");
      deriveGroups(rows);
      $("#cryptoLiveStatus").textContent = "市場排名已更新";
      $("#cryptoLiveStatus").dataset.state = "rest";
    } catch {
      const seedRows = [
        {id:"bitcoin",symbol:"btc",name:"Bitcoin",current_price:null,market_cap:null,total_volume:null},
        {id:"ethereum",symbol:"eth",name:"Ethereum",current_price:null,market_cap:null,total_volume:null},
        {id:"binancecoin",symbol:"bnb",name:"BNB",current_price:null,market_cap:null,total_volume:null},
        {id:"ripple",symbol:"xrp",name:"XRP",current_price:null,market_cap:null,total_volume:null},
        {id:"solana",symbol:"sol",name:"Solana",current_price:null,market_cap:null,total_volume:null},
        {id:"tether",symbol:"usdt",name:"Tether",current_price:1,market_cap:0,total_volume:0},
        {id:"usd-coin",symbol:"usdc",name:"USDC",current_price:1,market_cap:0,total_volume:0},
        {id:"dai",symbol:"dai",name:"Dai",current_price:1,market_cap:0,total_volume:0},
        {id:"ethena-usde",symbol:"usde",name:"USDe",current_price:1,market_cap:0,total_volume:0},
        {id:"first-digital-usd",symbol:"fdusd",name:"FDUSD",current_price:1,market_cap:0,total_volume:0}
      ];
      state.groups.marketCap = seedRows.slice(0,5);
      state.groups.volume = seedRows.slice(0,5);
      state.groups.stable = seedRows.slice(5,10);
      $("#cryptoLiveStatus").textContent = "等待市場來源";
      $("#cryptoLiveStatus").dataset.state = "fallback";
    }
    showGroup(state.index, false);
    connectWebSocket();
  }

  async function loadGlobal() {
    try {
      const payload = await fetchJson("https://api.coingecko.com/api/v3/global");
      const data = payload?.data || {};
      $("#cryptoGlobalCap").textContent = `$${formatCompact(data.total_market_cap?.usd)}`;
      $("#cryptoBtcDominance").textContent = finite(data.market_cap_percentage?.btc) === null ? "—" : `${Number(data.market_cap_percentage.btc).toFixed(1)}%`;
      $("#cryptoDataTime").textContent = `更新 ${new Date().toLocaleTimeString("zh-TW",{hour:"2-digit",minute:"2-digit",hour12:false})}`;
    } catch {
      $("#cryptoDataTime").textContent = "全球統計等待更新";
    }
  }

  async function loadSurge() {
    try {
      const tickers = await fetchJson("https://api.binance.com/api/v3/ticker/24hr", 15000);
      const candidates = (Array.isArray(tickers) ? tickers : [])
        .filter(row => /USDT$/.test(row.symbol) && !/(UP|DOWN|BULL|BEAR)USDT$/.test(row.symbol) && Number(row.quoteVolume) > 10_000_000)
        .sort((a,b)=>Number(b.quoteVolume)-Number(a.quoteVolume)).slice(0,24);
      const rows = await Promise.all(candidates.map(async ticker => {
        try {
          const klines = await fetchJson(`https://api.binance.com/api/v3/klines?symbol=${encodeURIComponent(ticker.symbol)}&interval=5m&limit=14`, 8000);
          const volumes = (klines || []).map(k => Number(k[7])).filter(Number.isFinite);
          const recent = volumes.at(-1), baseline = median(volumes.slice(0,-1));
          if (!baseline || !recent) return null;
          const symbol = ticker.symbol.replace(/USDT$/,"");
          const market = state.marketRows.find(row => String(row.symbol).toUpperCase() === symbol);
          return {
            id:market?.id || symbol.toLowerCase(), symbol, name:market?.name || symbol,
            current_price:Number(ticker.lastPrice), price_change_percentage_24h:Number(ticker.priceChangePercent),
            surgeRatio:recent/baseline, recentVolume:recent,
            url:`https://www.binance.com/en/trade/${symbol}_USDT?type=spot`
          };
        } catch { return null; }
      }));
      state.groups.surge = rows.filter(Boolean).filter(row => row.surgeRatio >= 1.8).sort((a,b)=>b.surgeRatio-a.surgeRatio).slice(0,5);
      if (!state.groups.surge.length) state.groups.surge = rows.filter(Boolean).sort((a,b)=>b.surgeRatio-a.surgeRatio).slice(0,5);
      if (GROUPS[state.index].id === "surge") showGroup(state.index, false);
    } catch {}
  }

  function extractListingSymbols(title) {
    const symbols = new Set();
    for (const match of String(title || "").matchAll(/\(([A-Z0-9]{2,12})\)/g)) symbols.add(match[1]);
    return [...symbols];
  }

  async function loadNewest() {
    try {
      const url = "https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query?type=1&catalogId=48&pageNo=1&pageSize=20";
      const payload = await fetchJson(url, 14000);
      const articles = payload?.data?.catalogs?.[0]?.articles || payload?.data?.articles || [];
      const rows = [];
      for (const article of articles) {
        for (const symbol of extractListingSymbols(article.title)) {
          if (rows.some(row => row.symbol === symbol)) continue;
          const market = state.marketRows.find(row => String(row.symbol).toUpperCase() === symbol);
          rows.push({
            id:market?.id || symbol.toLowerCase(), symbol, name:market?.name || article.title,
            current_price:market?.current_price ?? null, price_change_percentage_24h:market?.price_change_percentage_24h ?? null,
            listedAt:article.releaseDate || article.publishDate || null,
            metric:"官方上架公告", url:article.code ? `https://www.binance.com/en/support/announcement/${article.code}` : "https://www.binance.com/en/support/announcement/new-cryptocurrency-listing?c=48&navId=48"
          });
          if (rows.length >= 5) break;
        }
        if (rows.length >= 5) break;
      }
      state.groups.newest = rows;
      if (GROUPS[state.index].id === "newest") showGroup(state.index, false);
    } catch {
      try {
        const local = await fetch(`data/crypto-new-listings.json?t=${Date.now()}`, {cache:"no-store"}).then(r => r.ok ? r.json() : Promise.reject());
        state.groups.newest = Array.isArray(local?.items) ? local.items.slice(0,5) : [];
      } catch {}
    }
  }

  function connectWebSocket() {
    try { state.websocket?.close(); } catch {}
    const symbols = [...new Set([...state.groups.marketCap,...state.groups.volume,...state.groups.surge].map(row => String(row.symbol||"").toLowerCase()).filter(symbol => /^[a-z0-9]{2,12}$/.test(symbol)))];
    if (!symbols.length || !("WebSocket" in window)) return;
    const streams = symbols.map(symbol => `${symbol}usdt@miniTicker`).join("/");
    try {
      const socket = new WebSocket(`wss://data-stream.binance.vision/stream?streams=${streams}`);
      state.websocket = socket;
      socket.addEventListener("open", () => {
        $("#cryptoLiveStatus").textContent = "即時連線";
        $("#cryptoLiveStatus").dataset.state = "live";
      });
      socket.addEventListener("message", event => {
        try {
          const data = JSON.parse(event.data)?.data || {};
          const symbol = String(data.s || "").replace(/USDT$/,"");
          const price = finite(data.c), open = finite(data.o);
          if (!symbol || price === null) return;
          const change = open ? (price-open)/open*100 : null;
          state.lastSocketAt = Date.now();
          Object.values(state.groups).flat().forEach(row => {
            if (String(row.symbol||"").toUpperCase() === symbol) {
              row.current_price = price;
              if (change !== null) row.price_change_percentage_24h = change;
            }
          });
          document.querySelectorAll(`.crypto-live-row[data-symbol="${CSS.escape(symbol)}"]`).forEach(node => {
            const priceNode=node.querySelector("[data-price]"), changeNode=node.querySelector("[data-change]");
            if (priceNode) priceNode.textContent=formatPrice(price);
            if (changeNode && change !== null) changeNode.textContent=pct(change);
            node.classList.toggle("up", change > 0); node.classList.toggle("down", change < 0); node.classList.toggle("flat", change === 0);
          });
        } catch {}
      });
      socket.addEventListener("close", () => {
        $("#cryptoLiveStatus").textContent = "延遲備援";
        $("#cryptoLiveStatus").dataset.state = "fallback";
        setTimeout(connectWebSocket, 5000);
      });
      socket.addEventListener("error", () => socket.close());
    } catch {}
  }

  async function init() {
    bindControls();
    const initial = [
      {id:"bitcoin",symbol:"btc",name:"Bitcoin",current_price:null},
      {id:"ethereum",symbol:"eth",name:"Ethereum",current_price:null},
      {id:"binancecoin",symbol:"bnb",name:"BNB",current_price:null},
      {id:"ripple",symbol:"xrp",name:"XRP",current_price:null},
      {id:"solana",symbol:"sol",name:"Solana",current_price:null}
    ];
    state.groups.marketCap = initial;
    state.groups.volume = initial;
    state.groups.stable = [
      {id:"tether",symbol:"usdt",name:"Tether",current_price:1},
      {id:"usd-coin",symbol:"usdc",name:"USDC",current_price:1},
      {id:"dai",symbol:"dai",name:"Dai",current_price:1},
      {id:"ethena-usde",symbol:"usde",name:"USDe",current_price:1},
      {id:"first-digital-usd",symbol:"fdusd",name:"FDUSD",current_price:1}
    ];
    showGroup(0, false);
    resetRotation();
    await Promise.allSettled([loadMarkets(), loadGlobal()]);
    await Promise.allSettled([loadSurge(), loadNewest()]);
    showGroup(0, false);
    resetRotation();
    setInterval(() => { loadMarkets(); loadGlobal(); loadSurge(); loadNewest(); }, 60000);
  }

  init().catch(() => {
    $("#cryptoLiveStatus").textContent = "資料暫時中斷";
    showGroup(0, false);
  });
})();
