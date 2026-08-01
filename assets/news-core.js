(() => {
  "use strict";

  const FALLBACK_ITEMS = [
    {
      id: "fallback-cna",
      title: "中央社產經證券最新消息",
      link: "https://www.cna.com.tw/list/aie.aspx",
      source: "中央社產經",
      summary: "新聞資料暫時無法同步時，可先前往官方新聞來源。",
      published_at: null,
      region: "TW",
      topic: "market",
      origin: "fallback"
    },
    {
      id: "fallback-cnyes",
      title: "鉅亨網全球市場與即時財經快訊",
      link: "https://www.cnyes.com/",
      source: "鉅亨網",
      summary: "查看台股、美股、總經與產業快訊。",
      published_at: null,
      region: "TW",
      topic: "market",
      origin: "fallback"
    },
    {
      id: "fallback-money",
      title: "經濟日報台股、產業與國際財經",
      link: "https://money.udn.com/",
      source: "經濟日報",
      summary: "查看台灣產業、企業與國際市場新聞。",
      published_at: null,
      region: "TW",
      topic: "market",
      origin: "fallback"
    },
    {
      id: "fallback-reuters",
      title: "Reuters 全球市場最新消息",
      link: "https://www.reuters.com/markets/",
      source: "Reuters",
      summary: "查看全球市場、總經與企業消息。",
      published_at: null,
      region: "GLOBAL",
      topic: "market",
      origin: "fallback"
    }
  ];

  const state = {
    payload: { metadata: {}, source: {}, sources: [], items: [] },
    status: "loading",
    error: null
  };

  function normalizePayload(payload) {
    const items = Array.isArray(payload?.items) ? payload.items.filter(x => x?.title && x?.link) : [];
    return {
      metadata: payload?.metadata || {},
      source: payload?.source || {},
      sources: Array.isArray(payload?.sources) ? payload.sources : [],
      items
    };
  }

  function mergeItems(primary, secondary) {
    const seen = new Set();
    const merged = [];
    [...primary, ...secondary].forEach(item => {
      const key = String(item.link || item.title || "").trim().toLowerCase();
      if (!key || seen.has(key)) return;
      seen.add(key);
      merged.push(item);
    });
    return merged;
  }

  function emit() {
    window.MarketNews = {
      payload: state.payload,
      items: state.payload.items,
      status: state.status,
      error: state.error,
      reload: load
    };
    window.dispatchEvent(new CustomEvent("market-news-loaded", {
      detail: window.MarketNews
    }));
  }

  async function fetchWithTimeout(url, timeoutMs = 12000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(url, {
        cache: "no-store",
        headers: { "Accept": "application/json" },
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      return normalizePayload(payload);
    } finally {
      clearTimeout(timer);
    }
  }

  async function load() {
    state.status = "loading";
    state.error = null;

    const seed = normalizePayload(window.__MARKET_NEWS_SEED__ || {});
    try {
      const network = await fetchWithTimeout(`data/news.json?refresh=${Date.now()}`);
      const merged = mergeItems(network.items, seed.items);
      state.payload = {
        ...network,
        items: merged.length ? merged : FALLBACK_ITEMS
      };
      state.status = network.items.length ? "live" : (seed.items.length ? "cached" : "fallback");
    } catch (error) {
      state.error = error;
      state.payload = {
        ...seed,
        items: seed.items.length ? seed.items : FALLBACK_ITEMS
      };
      state.status = seed.items.length ? "cached" : "fallback";
    }
    emit();
    return state.payload;
  }

  window.MarketNewsLoader = { load, state };
  load();
})();