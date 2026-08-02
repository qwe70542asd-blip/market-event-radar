(() => {
  "use strict";

  const $ = selector => document.querySelector(selector);
  const root = $("#cryptoLiveList");
  if (!root) return;

  const statusNode = $("#cryptoLiveStatus");
  const titleNode = $("#cryptoGroupTitle");
  const noteNode = $("#cryptoGroupNote");
  const counterNode = $("#cryptoGroupCounter");
  const capNode = $("#cryptoGlobalCap");
  const dominanceNode = $("#cryptoBtcDominance");
  const timeNode = $("#cryptoDataTime");
  const viewport = $("#cryptoLiveViewport");

  const STABLE_IDS = new Set(["tether","usd-coin","dai","ethena-usde","first-digital-usd","paypal-usd","true-usd","frax","usdd","pax-dollar"]);
  const WRAPPED_TERMS = /wrapped|staked|liquid staked|bridged|wormhole|binance-peg|restaked/i;
  const LEVERAGED_SYMBOL = /(UP|DOWN|BULL|BEAR|[235]L|[235]S)$/i;
  const QUOTE_STABLES = new Set(["USDT","USDC","FDUSD","TUSD","DAI","USDP","BUSD"]);

  const state = {
    groups: [],
    groupIndex: 0,
    paused: false,
    rotationTimer: null,
    refreshTimer: null,
    socket: null,
    binance: new Map(),
    volumeSamples: new Map(),
    burstReady: false,
    lastUiRender: 0,
    source: "CoinGecko",
  };

  const escapeHtml = value => String(value ?? "").replace(/[&<>\"]/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[char]));
  const finite = value => Number.isFinite(Number(value)) ? Number(value) : null;

  async function fetchJson(url, timeout = 12000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(url, {cache:"no-store", signal:controller.signal, headers:{Accept:"application/json"}});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally {
      clearTimeout(timer);
    }
  }

  function formatPrice(value) {
    const number = finite(value);
    if (number === null) return "—";
    const digits = number >= 1000 ? 0 : number >= 100 ? 1 : number >= 1 ? 3 : number >= .01 ? 4 : 7;
    return `$${number.toLocaleString("en-US", {maximumFractionDigits:digits})}`;
  }

  function formatCompact(value) {
    const number = finite(value);
    if (number === null) return "—";
    return new Intl.NumberFormat("zh-TW", {notation:"compact", maximumFractionDigits:1}).format(number);
  }

  function formatPercent(value) {
    const number = finite(value);
    if (number === null) return "—";
    return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
  }

  function direction(value) {
    const number = finite(value);
    return number === null || number === 0 ? "flat" : number > 0 ? "up" : "down";
  }

  function normalizeCoin(row, extra = {}) {
    return {
      id: row.id || extra.id || row.symbol,
      symbol: String(row.symbol || extra.symbol || "—").toUpperCase(),
      name: row.name || extra.name || row.baseToken?.name || row.baseToken?.symbol || "未知幣種",
      price: finite(row.current_price ?? row.priceUsd ?? extra.price),
      change: finite(row.price_change_percentage_24h ?? row.priceChange?.h24 ?? extra.change),
      marketCap: finite(row.market_cap ?? row.marketCap ?? extra.marketCap),
      volume: finite(row.total_volume ?? row.volume?.h24 ?? extra.volume),
      image: row.image || extra.image || "",
      link: extra.link || (row.id ? `https://www.coingecko.com/en/coins/${encodeURIComponent(row.id)}` : "https://www.coingecko.com/"),
      meta: extra.meta || "",
      score: finite(extra.score),
      chain: extra.chain || "",
    };
  }

  function rowHtml(item, groupType) {
    const live = state.binance.get(`${item.symbol}USDT`);
    const price = live?.price ?? item.price;
    const change = live?.change ?? item.change;
    const dir = direction(change);
    let secondary = groupType === "marketcap" ? `市值 ${formatCompact(item.marketCap)}`
      : groupType === "volume" ? `24H 量 ${formatCompact(item.volume)}`
      : groupType === "stable" ? `偏離 ${(Math.abs((price || 1) - 1) * 100).toFixed(2)}%`
      : groupType === "burst" ? `${item.score ? `${item.score.toFixed(1)} 倍` : "偵測中"} · 24H量 ${formatCompact(item.volume)}`
      : `${item.chain || "鏈上"}${item.meta ? ` · ${item.meta}` : ""}`;
    const status = groupType === "stable" ? (Math.abs((price || 1) - 1) > .01 ? "脫鉤" : Math.abs((price || 1) - 1) > .003 ? "注意" : "正常") : formatPercent(change);
    return `<a class="crypto-rank-row ${dir} type-${groupType}" href="${escapeHtml(item.link)}" target="_blank" rel="noreferrer noopener">
      <span class="crypto-rank-symbol">${escapeHtml(item.symbol)}</span>
      <div><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(secondary)}</small></div>
      <b>${formatPrice(price)}</b>
      <em>${escapeHtml(status)}</em>
    </a>`;
  }

  function render() {
    const group = state.groups[state.groupIndex];
    if (!group) {
      root.innerHTML = '<div class="crypto-loading">即時幣圈資料同步中…</div>';
      return;
    }
    titleNode.textContent = group.title;
    noteNode.textContent = group.note;
    counterNode.textContent = `${state.groupIndex + 1}/${state.groups.length}`;
    root.innerHTML = group.items.length
      ? group.items.slice(0,5).map(item => rowHtml(item, group.type)).join("")
      : '<div class="crypto-loading">這個排行等待下一次資料更新。</div>';
    root.classList.remove("crypto-swap");
    void root.offsetWidth;
    root.classList.add("crypto-swap");
  }

  function setGroup(index) {
    if (!state.groups.length) return;
    state.groupIndex = (index + state.groups.length) % state.groups.length;
    render();
    restartRotation();
  }

  function restartRotation() {
    clearInterval(state.rotationTimer);
    if (state.paused) return;
    state.rotationTimer = setInterval(() => setGroup(state.groupIndex + 1), 15000);
  }

  function fallbackBurst(markets) {
    return markets
      .filter(row => !STABLE_IDS.has(row.id) && row.market_cap > 20_000_000 && row.total_volume > 5_000_000)
      .map(row => normalizeCoin(row, {score:(row.total_volume / Math.max(row.market_cap,1)) * (1 + Math.abs(row.price_change_percentage_24h || 0) / 15)}))
      .sort((a,b) => (b.score || 0) - (a.score || 0))
      .slice(0,5);
  }

  function dynamicBurst(markets) {
    const bySymbol = new Map(markets.map(row => [String(row.symbol || "").toUpperCase(), row]));
    const rows = [];
    const now = Date.now();
    state.volumeSamples.forEach((samples, symbol) => {
      const current = state.binance.get(symbol);
      if (!current || !symbol.endsWith("USDT") || QUOTE_STABLES.has(symbol.replace(/USDT$/,""))) return;
      const cutoff = now - 5 * 60_000;
      const recent = samples.filter(sample => sample.time >= cutoff);
      if (recent.length < 2) return;
      const first = recent[0], last = recent.at(-1);
      const elapsed = Math.max(30_000, last.time - first.time);
      const delta = Math.max(0, last.quoteVolume - first.quoteVolume);
      const estimated5m = delta * (300_000 / elapsed);
      const baseline5m = Math.max(1, current.quoteVolume / 288);
      const ratio = estimated5m / baseline5m;
      const base = symbol.replace(/USDT$/,"");
      const market = bySymbol.get(base.toUpperCase());
      if (ratio < 1.5 || current.quoteVolume < 5_000_000) return;
      rows.push(normalizeCoin(market || {}, {
        id: market?.id || base,
        symbol: base,
        name: market?.name || base,
        price: current.price,
        change: current.change,
        volume: current.quoteVolume,
        marketCap: market?.market_cap,
        score: ratio,
        link: market?.id ? `https://www.coingecko.com/en/coins/${encodeURIComponent(market.id)}` : `https://www.binance.com/en/trade/${base}_USDT`
      }));
    });
    return rows.sort((a,b)=>(b.score||0)-(a.score||0)).slice(0,5);
  }

  async function latestProfiles() {
    try {
      const profiles = await fetchJson("https://api.dexscreener.com/token-profiles/latest/v1", 10000);
      const selected = Array.isArray(profiles) ? profiles.slice(0,8) : [];
      const details = await Promise.all(selected.map(async profile => {
        try {
          const payload = await fetchJson(`https://api.dexscreener.com/latest/dex/tokens/${encodeURIComponent(profile.tokenAddress)}`, 8000);
          const pair = (payload?.pairs || []).sort((a,b)=>(b.liquidity?.usd||0)-(a.liquidity?.usd||0))[0];
          if (!pair) return null;
          return normalizeCoin(pair, {
            id:`${profile.chainId}:${profile.tokenAddress}`,
            symbol:pair.baseToken?.symbol,
            name:pair.baseToken?.name,
            chain:profile.chainId,
            price:pair.priceUsd,
            change:pair.priceChange?.h24,
            volume:pair.volume?.h24,
            marketCap:pair.marketCap || pair.fdv,
            meta:"最新資料檔",
            link:pair.url || profile.url || "https://dexscreener.com/"
          });
        } catch { return null; }
      }));
      return details.filter(Boolean).slice(0,5);
    } catch {
      return [];
    }
  }

  async function refreshRankings() {
    statusNode.textContent = "更新中";
    statusNode.dataset.state = "loading";
    try {
      const [markets, stable, global, latest] = await Promise.all([
        fetchJson("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&sparkline=false&price_change_percentage=24h"),
        fetchJson("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&category=stablecoins&order=market_cap_desc&per_page=30&page=1&sparkline=false&price_change_percentage=24h"),
        fetchJson("https://api.coingecko.com/api/v3/global"),
        latestProfiles(),
      ]);
      const marketRows = Array.isArray(markets) ? markets : [];
      const capItems = marketRows.filter(row => !STABLE_IDS.has(row.id) && !WRAPPED_TERMS.test(`${row.name} ${row.id}`)).slice(0,5).map(normalizeCoin);
      const volumeItems = marketRows.filter(row => !STABLE_IDS.has(row.id) && !WRAPPED_TERMS.test(`${row.name} ${row.id}`) && row.total_volume > 1_000_000).sort((a,b)=>(b.total_volume||0)-(a.total_volume||0)).slice(0,5).map(normalizeCoin);
      const stableItems = (Array.isArray(stable) ? stable : []).slice(0,5).map(normalizeCoin);
      const burst = dynamicBurst(marketRows);
      state.burstReady = burst.length >= 3;
      state.groups = [
        {type:"marketcap", title:"市值前 5 大", note:"排除穩定幣與包裝資產", items:capItems},
        {type:"volume", title:"24H 交易量前 5 大", note:"非穩定幣美元成交量", items:volumeItems},
        {type:"stable", title:"穩定幣前 5 大", note:"依市值排序並監控美元脫鉤", items:stableItems},
        {type:"burst", title:state.burstReady ? "突發爆量前 5 大" : "爆量異動暖機", note:state.burstReady ? "最近 5 分鐘相對 24H 平均" : "即時串流累積後自動切換突發爆量", items:state.burstReady ? burst : fallbackBurst(marketRows)},
        {type:"latest", title:"最新幣種觀察", note:"DEX Screener 最新資料檔，風險較高", items:latest},
      ];
      const globalData = global?.data || {};
      capNode.textContent = globalData.total_market_cap?.usd ? `$${formatCompact(globalData.total_market_cap.usd)}` : "—";
      dominanceNode.textContent = finite(globalData.market_cap_percentage?.btc) !== null ? `${Number(globalData.market_cap_percentage.btc).toFixed(1)}%` : "—";
      timeNode.textContent = `台灣時間 ${new Date().toLocaleTimeString("zh-TW",{timeZone:"Asia/Taipei",hour:"2-digit",minute:"2-digit",hour12:false})}`;
      statusNode.textContent = state.socket?.readyState === WebSocket.OPEN ? "即時連線" : "近即時";
      statusNode.dataset.state = state.socket?.readyState === WebSocket.OPEN ? "live" : "fallback";
      render();
    } catch (error) {
      statusNode.textContent = "使用前次資料";
      statusNode.dataset.state = "stale";
      if (!state.groups.length) root.innerHTML = `<div class="crypto-loading">幣圈資料暫時無法連線，稍後自動重試。</div>`;
    }
  }

  function trimSamples() {
    const cutoff = Date.now() - 6 * 60_000;
    state.volumeSamples.forEach((samples,key) => {
      const trimmed = samples.filter(sample => sample.time >= cutoff).slice(-400);
      if (trimmed.length) state.volumeSamples.set(key, trimmed); else state.volumeSamples.delete(key);
    });
  }

  function connectBinance() {
    try { state.socket?.close(); } catch {}
    let reconnectTimer;
    try {
      const socket = new WebSocket("wss://data-stream.binance.vision/ws/!miniTicker@arr");
      state.socket = socket;
      socket.addEventListener("open", () => {
        statusNode.textContent = "即時連線";
        statusNode.dataset.state = "live";
      });
      socket.addEventListener("message", event => {
        let payload;
        try { payload = JSON.parse(event.data); } catch { return; }
        if (!Array.isArray(payload)) return;
        const now = Date.now();
        payload.forEach(row => {
          const symbol = String(row.s || "").toUpperCase();
          if (!symbol.endsWith("USDT") || LEVERAGED_SYMBOL.test(symbol.replace(/USDT$/,""))) return;
          const price = finite(row.c), open = finite(row.o), quoteVolume = finite(row.q);
          if (price === null || quoteVolume === null) return;
          const change = open ? (price - open) / open * 100 : null;
          state.binance.set(symbol,{price,change,quoteVolume,time:now});
          const samples = state.volumeSamples.get(symbol) || [];
          const last = samples.at(-1);
          if (!last || now - last.time >= 5000) samples.push({time:now,quoteVolume});
          state.volumeSamples.set(symbol,samples);
        });
        trimSamples();
        if (now-state.lastUiRender>=1500) {
          state.lastUiRender=now;
          render();
        }
      });
      socket.addEventListener("close", () => {
        statusNode.textContent = "重新連線";
        statusNode.dataset.state = "stale";
        clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(connectBinance,5000);
      });
      socket.addEventListener("error", () => socket.close());
    } catch {
      statusNode.textContent = "延遲備援";
      statusNode.dataset.state = "fallback";
      setTimeout(connectBinance,10000);
    }
  }

  $("#cryptoPrev")?.addEventListener("click",()=>setGroup(state.groupIndex-1));
  $("#cryptoNext")?.addEventListener("click",()=>setGroup(state.groupIndex+1));
  $("#cryptoPause")?.addEventListener("click",event=>{
    state.paused=!state.paused;
    event.currentTarget.textContent=state.paused ? "▶" : "Ⅱ";
    restartRotation();
  });
  viewport?.addEventListener("mouseenter",()=>{state.paused=true;restartRotation();});
  viewport?.addEventListener("mouseleave",()=>{state.paused=false;restartRotation();});

  connectBinance();
  refreshRankings();
  restartRotation();
  state.refreshTimer=setInterval(refreshRankings,60_000);
})();
