(() => {
  "use strict";
  const state = { assets: [], loaded: false, status: "loading" };
  const normalize = value => String(value || "").normalize("NFKC").toLowerCase().replace(/[\s._\-\/]+/g, "");

  function enrich(asset) {
    return {
      aliases: [], themes: [], ...asset,
      search_blob: normalize([
        asset.symbol, asset.name, asset.market, asset.exchange, asset.sector,
        asset.sub_industry, asset.official_industry, ...(asset.aliases || [])
      ].join(" "))
    };
  }

  function merge(primary, secondary) {
    const map = new Map();
    [...secondary, ...primary].forEach(raw => {
      if (!raw?.id) return;
      map.set(raw.id, enrich({ ...(map.get(raw.id) || {}), ...raw }));
    });
    return [...map.values()];
  }

  async function load() {
    const seedPayload = window.__MARKET_ASSET_SEED__ || { assets: [] };
    const seed = seedPayload.assets || [];
    try {
      const payload = window.MarketDataSource?.loadJson
        ? await window.MarketDataSource.loadJson("data/assets.json", seedPayload)
        : seedPayload;
      state.assets = merge(payload.assets || [], seed);
      state.status = payload.__data_source === "live-data" ? "live" : "seed";
    } catch (error) {
      state.assets = merge([], seed);
      state.status = "seed";
    }
    state.loaded = true;
    window.dispatchEvent(new CustomEvent("market-assets-loaded", { detail: state }));
    return state.assets;
  }

  function search(query, options = {}) {
    const q = normalize(query);
    if (!q) return [];
    const assetClass = options.asset_class || "all";
    const market = options.market || "all";
    return state.assets
      .filter(asset => assetClass === "all" || asset.asset_class === assetClass || (assetClass === "stock" && asset.asset_class === "etf"))
      .filter(asset => market === "all" || asset.market === market)
      .map(asset => {
        let score = 0;
        const symbol = normalize(asset.symbol);
        const name = normalize(asset.name);
        if (symbol === q) score += 1000;
        else if (symbol.startsWith(q)) score += 500;
        if (name === q) score += 900;
        else if (name.startsWith(q)) score += 450;
        if (asset.search_blob.includes(q)) score += 120;
        return { asset, score };
      })
      .filter(row => row.score > 0)
      .sort((a,b) => b.score - a.score || a.asset.symbol.localeCompare(b.asset.symbol))
      .slice(0, 12)
      .map(row => row.asset);
  }

  function resolve(value, options = {}) {
    const results = search(value, options);
    const q = normalize(value);
    return results.find(asset => normalize(asset.symbol) === q || normalize(asset.name) === q || (asset.aliases || []).some(x => normalize(x) === q)) || results[0] || null;
  }

  function byId(id) { return state.assets.find(asset => asset.id === id) || null; }

  window.MarketAssets = { state, load, search, resolve, byId, normalize };
  load();
})();