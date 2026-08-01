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
    const items = Array.isArray(payload?.items) ? payload.items.filter(x => x?.title).map(normalizeItem) : [];
    return {
      metadata: payload?.metadata || {},
      source: payload?.source || {},
      sources: Array.isArray(payload?.sources) ? payload.sources : [],
      items
    };
  }

  function isHttpUrl(value) {
    try {
      const url = new URL(String(value || ""));
      return url.protocol === "https:" || url.protocol === "http:";
    } catch {
      return false;
    }
  }

  function isGoogleNewsRedirect(value) {
    if (!isHttpUrl(value)) return false;
    const url = new URL(value);
    return url.hostname === "news.google.com" && (
      url.pathname.includes("/rss/articles/") ||
      url.pathname.includes("/articles/") ||
      url.pathname.includes("/read/")
    );
  }

  function searchUrl(item) {
    const query = [`"${String(item?.title || "").trim()}"`, String(item?.source || "").trim()]
      .filter(Boolean).join(" ");
    return `https://www.google.com/search?q=${encodeURIComponent(query)}`;
  }

  function safeLink(item) {
    const preferred = item?.safe_link || item?.direct_link || item?.publisher_link || item?.link;
    if (isHttpUrl(preferred) && !isGoogleNewsRedirect(preferred)) return preferred;
    if (item?.title) return searchUrl(item);
    return "news.html";
  }

  function normalizeItem(raw) {
    const item = { ...raw };
    item.original_link = item.original_link || item.link || "";
    item.link = safeLink(item);
    return item;
  }

  const SOURCE_SUFFIXES = [
    "Yahoo股市","Yahoo 股市","中央社","經濟日報","鉅亨網","Anue鉅亨",
    "MoneyDJ理財網","MoneyDJ","工商時報","中時新聞網","科技新報","財經新報",
    "自由財經","今周刊","商業周刊","財訊","ETtoday財經雲","ETtoday",
    "數位時代","iThome","INSIDE","風傳媒","信傳媒","聯合新聞網","udn",
    "AASTOCKS","經濟通","香港經濟日報","信報財經新聞","明報財經","香港01",
    "Reuters","CNBC","Nikkei Asia"
  ];

  function stripPublisherSuffix(title) {
    let value = String(title || "").trim();
    for (const source of SOURCE_SUFFIXES.sort((a,b) => b.length - a.length)) {
      const escaped = source.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      value = value.replace(new RegExp(`\\s*(?:-|–|—|｜|\\|)\\s*${escaped}\\s*$`, "i"), "");
    }
    return value.replace(/\s*[（(](?:圖|影音|更新|全文)[）)]\s*$/u, "").trim();
  }

  function canonicalTitle(title) {
    return stripPublisherSuffix(title)
      .normalize("NFKC")
      .toLowerCase()
      .replace(/^(?:快訊|速報|即時|獨家)\s*[：:｜|／/\- ]*/u, "")
      .replace(/[\s\u3000]+/gu, "")
      .replace(/[^\p{L}\p{N}]+/gu, "");
  }

  function ngrams(value, size = 3) {
    const result = new Set();
    if (!value) return result;
    if (value.length <= size) {
      result.add(value);
      return result;
    }
    for (let i = 0; i <= value.length - size; i += 1) result.add(value.slice(i, i + size));
    return result;
  }

  function titleSimilarity(left, right) {
    const a = canonicalTitle(left);
    const b = canonicalTitle(right);
    if (!a || !b) return 0;
    if (a === b) return 1;
    const short = a.length <= b.length ? a : b;
    const long = a.length > b.length ? a : b;
    if (short.length >= 14 && long.includes(short) && short.length / long.length >= 0.72) return 0.96;
    const ga = ngrams(a), gb = ngrams(b);
    let intersection = 0;
    ga.forEach(x => { if (gb.has(x)) intersection += 1; });
    const union = new Set([...ga, ...gb]).size;
    return union ? intersection / union : 0;
  }

  function itemRank(item) {
    const groupScore = ({ "official-tw":5, "official-global":5, "tw-media":3, "international":3, "hk-media":2 })[item.source_group] || 0;
    const originScore = ({ official:5, "direct-rss":4, "direct-page":3, "publisher-search":2, "event-search":1 })[item.origin] || 0;
    return groupScore * 1e9 + originScore * 1e8 + Number(item.quality_score || 0) * 1e5 + String(item.summary || "").length;
  }

  function mergeDuplicate(keeper, duplicate) {
    const sources = new Set([...(keeper.duplicate_sources || []), keeper.source, duplicate.source].filter(Boolean));
    keeper.duplicate_sources = [...sources];
    keeper.duplicate_count = Math.max(0, sources.size - 1);
    keeper.is_breaking = Boolean(keeper.is_breaking || duplicate.is_breaking);
    if (!keeper.summary && duplicate.summary) keeper.summary = duplicate.summary;
    return keeper;
  }

  function dedupeItems(input) {
    const byLink = new Map();
    input.forEach(raw => {
      if (!raw?.title || !raw?.link) return;
      const item = { ...raw, title: stripPublisherSuffix(raw.title) };
      const key = String(item.link).trim().toLowerCase();
      const current = byLink.get(key);
      if (!current || itemRank(item) > itemRank(current)) byLink.set(key, item);
    });

    const clusters = [];
    [...byLink.values()].sort((a,b) => itemRank(b) - itemRank(a)).forEach(item => {
      const match = clusters.findIndex(keeper => {
        const exact = canonicalTitle(keeper.title) === canonicalTitle(item.title);
        return exact || titleSimilarity(keeper.title, item.title) >= 0.86;
      });
      if (match < 0) {
        item.duplicate_sources = item.duplicate_sources || (item.source ? [item.source] : []);
        item.duplicate_count = item.duplicate_count || 0;
        clusters.push(item);
      } else if (itemRank(item) > itemRank(clusters[match])) {
        clusters[match] = mergeDuplicate(item, clusters[match]);
      } else {
        clusters[match] = mergeDuplicate(clusters[match], item);
      }
    });
    return clusters;
  }

  function mergeItems(primary, secondary) {
    return dedupeItems([...primary, ...secondary]);
  }

  function emit() {
    window.MarketNews = {
      payload: state.payload,
      items: state.payload.items,
      status: state.status,
      error: state.error,
      safeLink,
      searchUrl,
      isGoogleNewsRedirect,
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

  window.MarketNewsLoader = { load, state, safeLink, searchUrl, isGoogleNewsRedirect };
  load();
})();