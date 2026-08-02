(() => {
  "use strict";

  const PORTFOLIO_KEY = "market-radar-portfolio-v10-3";
  const REFRESH_MS = 30000;
  const state = {
    payload: window.__TW_MARKET_SEED__ || { metadata: {}, breadth: {}, items: [] },
    items: [],
    exchange: "ALL",
    assetClass: "all",
    limit: 20,
    selectedSymbol: "",
    editingId: "",
    timer: null,
    loading: false,
  };

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const finite = value => value === null || value === undefined || value === ""
    ? null
    : Number.isFinite(Number(value)) ? Number(value) : null;
  const escapeHtml = value => String(value ?? "").replace(/[&<>\"]/g, character => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[character]));
  const normalize = value => String(value || "").normalize("NFKC").toLowerCase().replace(/[\s._\-\/]+/g, "");

  function loadPortfolio() {
    try {
      const parsed = JSON.parse(localStorage.getItem(PORTFOLIO_KEY) || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }

  function savePortfolio(entries) {
    localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(entries));
    window.dispatchEvent(new CustomEvent("market-portfolio-changed", { detail: entries }));
  }

  function quoteMap() {
    return new Map(state.items.map(item => [String(item.symbol).toUpperCase(), item]));
  }

  function twEntries() {
    return loadPortfolio().filter(entry => entry.market === "TW" || String(entry.asset_id || entry.key || "").startsWith("TW:"));
  }

  function formatPrice(value) {
    const number = finite(value);
    if (number === null) return "—";
    const digits = number >= 1000 ? 0 : number >= 100 ? 1 : number >= 10 ? 2 : 3;
    return number.toLocaleString("zh-TW", { maximumFractionDigits: digits });
  }

  function formatMoney(value, signed = false) {
    const number = finite(value);
    if (number === null) return "—";
    const sign = signed && number > 0 ? "+" : "";
    return `${sign}NT$${Math.round(number).toLocaleString("zh-TW")}`;
  }

  function formatPercent(value) {
    const number = finite(value);
    if (number === null) return "—";
    return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
  }

  function formatVolume(value) {
    const number = finite(value);
    if (number === null) return "—";
    if (number >= 10000) return `${(number / 10000).toFixed(1)}萬`;
    return Math.round(number).toLocaleString("zh-TW");
  }

  function direction(value) {
    const number = finite(value);
    return number === null || number === 0 ? "flat" : number > 0 ? "up" : "down";
  }

  function statusLabel(status) {
    return ({ trading: "盤中／延遲", preopen: "開盤前", closed: "最後交易日", pending: "等待第一次更新" })[status] || "行情資料";
  }

  function renderClock() {
    const formatter = new Intl.DateTimeFormat("zh-TW", { timeZone: "Asia/Taipei", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
    $("#twClock").textContent = formatter.format(new Date());
  }

  function renderMeta() {
    const metadata = state.payload.metadata || {};
    const pill = $("#twSessionPill");
    pill.textContent = statusLabel(metadata.market_status);
    pill.className = `tw-session-pill ${escapeHtml(metadata.market_status || "pending")}`;
    $("#twTradingDate").textContent = metadata.trading_date || "等待更新";
    const updated = metadata.updated_at ? new Date(metadata.updated_at) : null;
    $("#twUpdatedAt").textContent = updated && !Number.isNaN(updated.getTime())
      ? updated.toLocaleString("zh-TW", { timeZone: "Asia/Taipei", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false })
      : "等待第一次排程";
    $("#twDataSource").textContent = metadata.source || "官方行情";
    const ageMinutes = updated ? Math.max(0, Math.round((Date.now() - updated.getTime()) / 60000)) : null;
    $("#twFreshness").textContent = ageMinutes === null ? "尚未取得線上行情" : ageMinutes <= 1 ? "剛剛完成更新" : `${ageMinutes} 分鐘前完成更新`;

    const usable = state.items.filter(item => finite(item.price) !== null && finite(item.previous_close) !== null);
    const up = usable.filter(item => finite(item.change_percent) > 0).length;
    const down = usable.filter(item => finite(item.change_percent) < 0).length;
    $("#twUpCount").textContent = up.toLocaleString("zh-TW");
    $("#twDownCount").textContent = down.toLocaleString("zh-TW");
    $("#twFlatCount").textContent = Math.max(0, usable.length - up - down).toLocaleString("zh-TW");
    $("#twQuoteCount").textContent = usable.length.toLocaleString("zh-TW");
  }

  function filteredItems() {
    return state.items.filter(item => state.exchange === "ALL" || item.exchange === state.exchange)
      .filter(item => state.assetClass === "all" || item.asset_class === state.assetClass)
      .filter(item => finite(item.price) !== null && finite(item.previous_close) !== null && finite(item.change_percent) !== null)
      .filter(item => finite(item.volume) === null || finite(item.volume) > 0);
  }

  function rankingRow(item, index) {
    const move = direction(item.change_percent);
    return `<tr class="${move}">
      <td><span class="tw-rank-number">${index + 1}</span></td>
      <td><a class="tw-symbol-cell" href="asset.html?id=${encodeURIComponent(`TW:${item.symbol}`)}"><strong>${escapeHtml(item.symbol)}</strong><span>${escapeHtml(item.name)}</span><small>${item.exchange === "TPEx" ? "上櫃" : "上市"}${item.asset_class === "etf" ? " · ETF" : ""}</small></a></td>
      <td><strong class="tw-price">${formatPrice(item.price)}</strong><small class="tw-change-value">${formatPrice(item.change)}</small></td>
      <td><strong class="tw-change-percent">${formatPercent(item.change_percent)}</strong></td>
      <td><span>${formatVolume(item.volume)}</span><small>張</small></td>
      <td><button aria-label="加入 ${escapeHtml(item.name)} 到我的組合" class="tw-row-add" data-add-symbol="${escapeHtml(item.symbol)}" type="button">＋</button></td>
    </tr>`;
  }

  function renderRankings() {
    const rows = filteredItems();
    const gainers = rows.filter(item => finite(item.change_percent) > 0)
      .sort((a, b) => finite(b.change_percent) - finite(a.change_percent) || (finite(b.volume) || 0) - (finite(a.volume) || 0))
      .slice(0, state.limit);
    const losers = rows.filter(item => finite(item.change_percent) < 0)
      .sort((a, b) => finite(a.change_percent) - finite(b.change_percent) || (finite(b.volume) || 0) - (finite(a.volume) || 0))
      .slice(0, state.limit);
    $("#twGainersBody").innerHTML = gainers.length ? gainers.map(rankingRow).join("") : '<tr><td colspan="6" class="tw-table-empty">此篩選目前沒有上漲資料。</td></tr>';
    $("#twLosersBody").innerHTML = losers.length ? losers.map(rankingRow).join("") : '<tr><td colspan="6" class="tw-table-empty">此篩選目前沒有下跌資料。</td></tr>';
    $$('[data-add-symbol]').forEach(button => button.addEventListener("click", () => selectForPortfolio(button.dataset.addSymbol, true)));
  }

  function portfolioEntryQuote(entry, quotes) {
    return quotes.get(String(entry.symbol || "").toUpperCase()) || null;
  }

  function renderPortfolio() {
    const entries = twEntries();
    const quotes = quoteMap();
    let value = 0;
    let cost = 0;
    let unrealized = 0;
    let dayPnl = 0;
    let hasUnrealized = false;
    let hasDayPnl = false;

    const rows = entries.map(entry => {
      const quote = portfolioEntryQuote(entry, quotes);
      const price = finite(quote?.price);
      const previous = finite(quote?.previous_close);
      const shares = finite(entry.shares);
      const avgCost = finite(entry.avg_cost);
      const holdingValue = price !== null && shares !== null ? price * shares : null;
      const holdingCost = avgCost !== null && shares !== null ? avgCost * shares : null;
      const pnl = holdingValue !== null && holdingCost !== null ? holdingValue - holdingCost : null;
      const daily = price !== null && previous !== null && shares !== null ? (price - previous) * shares : null;
      if (holdingValue !== null) value += holdingValue;
      if (holdingCost !== null) cost += holdingCost;
      if (pnl !== null) { unrealized += pnl; hasUnrealized = true; }
      if (daily !== null) { dayPnl += daily; hasDayPnl = true; }
      const move = direction(quote?.change_percent);
      return `<tr class="${move}">
        <td><div class="tw-holding-symbol"><strong>${escapeHtml(entry.symbol)}</strong><span>${escapeHtml(entry.name || quote?.name || entry.symbol)}</span><small>${quote?.exchange === "TPEx" ? "上櫃" : "上市"}${entry.asset_class === "etf" ? " · ETF" : ""}</small></div></td>
        <td><strong>${formatPrice(price)}</strong><small class="tw-holding-move">${formatPercent(quote?.change_percent)}</small></td>
        <td><strong>${shares === null ? "觀察" : `${shares.toLocaleString("zh-TW")} 股`}</strong><small>${avgCost === null ? "未填成本" : `均價 ${formatPrice(avgCost)}`}</small></td>
        <td><strong>${formatMoney(holdingValue)}</strong></td>
        <td><strong class="${direction(pnl)}">${formatMoney(pnl, true)}</strong><small>${pnl !== null && holdingCost ? formatPercent(pnl / holdingCost * 100) : "—"}</small></td>
        <td><div class="tw-row-actions"><button data-edit-id="${escapeHtml(entry.id)}" type="button">編輯</button><button data-remove-id="${escapeHtml(entry.id)}" type="button">移除</button></div></td>
      </tr>`;
    });

    $("#twPortfolioValue").textContent = formatMoney(value);
    $("#twPortfolioCost").textContent = formatMoney(cost);
    const pnlNode = $("#twPortfolioPnl");
    pnlNode.textContent = hasUnrealized ? formatMoney(unrealized, true) : "—";
    pnlNode.className = direction(hasUnrealized ? unrealized : null);
    const dayNode = $("#twPortfolioDayPnl");
    dayNode.textContent = hasDayPnl ? formatMoney(dayPnl, true) : "—";
    dayNode.className = direction(hasDayPnl ? dayPnl : null);
    $("#twHoldingCount").textContent = `${entries.length} 個標的`;
    $("#twHoldingsBody").innerHTML = rows.length ? rows.join("") : '<tr><td colspan="6" class="tw-table-empty">尚未加入台股；上方排行按「＋」即可加入。</td></tr>';
    $$('[data-edit-id]').forEach(button => button.addEventListener("click", () => startEdit(button.dataset.editId)));
    $$('[data-remove-id]').forEach(button => button.addEventListener("click", () => removeHolding(button.dataset.removeId)));
  }

  function suggestions(query) {
    const value = normalize(query);
    if (!value) return [];
    const seen = new Set();
    const ranked = state.items.map(item => {
      const symbol = normalize(item.symbol);
      const name = normalize(item.name);
      let score = 0;
      if (symbol === value) score += 1000;
      else if (symbol.startsWith(value)) score += 500;
      if (name === value) score += 900;
      else if (name.startsWith(value)) score += 450;
      else if (name.includes(value)) score += 120;
      return { item, score };
    }).filter(row => row.score > 0).sort((a, b) => b.score - a.score).slice(0, 10);
    return ranked.map(row => row.item).filter(item => !seen.has(item.symbol) && seen.add(item.symbol));
  }

  function renderSuggestions(query) {
    const box = $("#twAssetSuggestions");
    const items = suggestions(query);
    box.innerHTML = items.map(item => `<button data-select-symbol="${escapeHtml(item.symbol)}" type="button"><strong>${escapeHtml(item.symbol)}</strong><span>${escapeHtml(item.name)}</span><small>${item.exchange === "TPEx" ? "上櫃" : "上市"}${item.asset_class === "etf" ? " · ETF" : ""}</small></button>`).join("");
    box.hidden = !items.length;
    $$('[data-select-symbol]', box).forEach(button => button.addEventListener("click", () => selectForPortfolio(button.dataset.selectSymbol)));
  }

  function selectForPortfolio(symbol, scroll = false) {
    const item = quoteMap().get(String(symbol).toUpperCase());
    if (!item) return;
    state.selectedSymbol = item.symbol;
    $("#twAssetQuery").value = `${item.symbol} ${item.name}`;
    $("#twAssetSuggestions").hidden = true;
    $("#twHoldingStatus").textContent = `已選擇：${item.name}（${item.symbol}）`;
    if (scroll) {
      $("#twHoldingsSection").scrollIntoView({ behavior: "smooth", block: "start" });
      setTimeout(() => $("#twHoldingForm [name=shares]").focus(), 350);
    }
  }

  function clearForm() {
    state.selectedSymbol = "";
    state.editingId = "";
    $("#twHoldingForm").reset();
    $("#twAssetSuggestions").hidden = true;
    $("#twHoldingFormTitle").textContent = "加入台股";
    $("#twCancelEdit").hidden = true;
  }

  function startEdit(id) {
    const entry = loadPortfolio().find(item => item.id === id);
    if (!entry) return;
    state.editingId = id;
    state.selectedSymbol = String(entry.symbol || "").toUpperCase();
    $("#twAssetQuery").value = `${entry.symbol} ${entry.name}`;
    $("#twHoldingForm [name=shares]").value = finite(entry.shares) ?? "";
    $("#twHoldingForm [name=avg_cost]").value = finite(entry.avg_cost) ?? "";
    $("#twHoldingFormTitle").textContent = `編輯 ${entry.name}`;
    $("#twCancelEdit").hidden = false;
    $("#twHoldingStatus").textContent = "修改後按下儲存。";
    $("#twHoldingForm").scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function removeHolding(id) {
    const entries = loadPortfolio();
    const target = entries.find(entry => entry.id === id);
    if (!target || !window.confirm(`確定從組合移除「${target.name || target.symbol}」？`)) return;
    savePortfolio(entries.filter(entry => entry.id !== id));
    renderPortfolio();
  }

  function submitHolding(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const status = $("#twHoldingStatus");
    const exactText = String($("#twAssetQuery").value || "").trim().split(/\s+/)[0].toUpperCase();
    const symbol = state.selectedSymbol || (quoteMap().has(exactText) ? exactText : "");
    const quote = quoteMap().get(symbol);
    if (!quote) {
      status.textContent = "請先從搜尋結果選擇正確的股票或 ETF。";
      return;
    }
    const sharesText = String(form.elements.shares.value || "").trim();
    const costText = String(form.elements.avg_cost.value || "").trim();
    const shares = sharesText === "" ? null : finite(sharesText);
    const avgCost = costText === "" ? null : finite(costText);
    if (shares !== null && shares < 0) { status.textContent = "持有股數不能小於 0。"; return; }
    if (avgCost !== null && avgCost < 0) { status.textContent = "平均成本不能小於 0。"; return; }

    const entries = loadPortfolio();
    const existingIndex = state.editingId
      ? entries.findIndex(entry => entry.id === state.editingId)
      : entries.findIndex(entry => (entry.market === "TW" || String(entry.asset_id || "").startsWith("TW:")) && String(entry.symbol).toUpperCase() === symbol);
    const base = existingIndex >= 0 ? entries[existingIndex] : {};
    const asset = window.MarketAssets?.byId?.(`TW:${symbol}`) || {};
    const next = {
      ...base,
      ...asset,
      id: base.id || (window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`),
      asset_id: `TW:${symbol}`,
      key: `TW:${symbol}`,
      asset_class: quote.asset_class || asset.asset_class || "stock",
      market: "TW",
      exchange: quote.exchange || asset.exchange || "TWSE",
      symbol,
      name: quote.name || asset.name || symbol,
      currency: "TWD",
      shares,
      avg_cost: avgCost,
    };
    if (existingIndex >= 0) entries[existingIndex] = next;
    else entries.push(next);
    savePortfolio(entries);
    clearForm();
    status.textContent = existingIndex >= 0 ? "組合資料已更新。" : "已加入我的台股組合。";
    renderPortfolio();
  }

  async function loadMarket(force = false) {
    if (state.loading) return;
    state.loading = true;
    $("#twRefreshBtn").classList.add("loading");
    try {
      const seed = window.__TW_MARKET_SEED__ || state.payload;
      const payload = window.MarketDataSource?.loadJson
        ? await window.MarketDataSource.loadJson("data/tw-market.json", seed)
        : seed;
      if (Array.isArray(payload?.items) && payload.items.length) {
        state.payload = payload;
        state.items = payload.items;
      }
      renderMeta();
      renderRankings();
      renderPortfolio();
      if (force) $("#twFreshness").textContent = "已重新檢查最新行情。";
    } catch (error) {
      $("#twFreshness").textContent = "暫時無法更新，保留上次資料。";
    } finally {
      state.loading = false;
      $("#twRefreshBtn").classList.remove("loading");
    }
  }

  function bind() {
    $("#twExchangeFilter").addEventListener("click", event => {
      const button = event.target.closest("[data-exchange]");
      if (!button) return;
      state.exchange = button.dataset.exchange;
      $$('[data-exchange]', event.currentTarget).forEach(node => node.classList.toggle("active", node === button));
      renderRankings();
    });
    $("#twClassFilter").addEventListener("change", event => { state.assetClass = event.target.value; renderRankings(); });
    $("#twRankLimit").addEventListener("change", event => { state.limit = Number(event.target.value) || 20; renderRankings(); });
    $("#twAssetQuery").addEventListener("input", event => { state.selectedSymbol = ""; renderSuggestions(event.target.value); });
    $("#twHoldingForm").addEventListener("submit", submitHolding);
    $("#twCancelEdit").addEventListener("click", () => { clearForm(); $("#twHoldingStatus").textContent = "已取消編輯。"; });
    $("#twRefreshBtn").addEventListener("click", () => loadMarket(true));
    window.addEventListener("storage", event => { if (event.key === PORTFOLIO_KEY) renderPortfolio(); });
    document.addEventListener("visibilitychange", () => { if (!document.hidden) loadMarket(false); });
  }

  state.items = state.payload.items || [];
  bind();
  renderClock();
  setInterval(renderClock, 1000);
  renderMeta();
  renderRankings();
  renderPortfolio();
  loadMarket(false);
  state.timer = setInterval(() => loadMarket(false), REFRESH_MS);
})();
