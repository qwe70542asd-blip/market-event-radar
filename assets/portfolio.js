(() => {
  "use strict";

  const STORAGE_KEY = "market-radar-portfolio-v10";
  const THEME_KEYWORDS = {
    "tw-equity": ["台股","台灣","加權","台積電","聯電","鴻海","廣達","新台幣","TWSE","櫃買"],
    "us-tech": ["美股","NASDAQ","科技股","AI","人工智慧","半導體","NVIDIA","AMD","Microsoft","Apple","Meta","Amazon","Google"],
    "jp-equity": ["日本","日股","日經","日圓","日本銀行","BOJ","Toyota","Sony","Tokyo Electron"],
    "kr-equity": ["韓國","韓股","KOSPI","三星","Samsung","SK hynix","海力士","韓元"],
    "global-equity": ["全球股市","MSCI","S&P 500","經濟成長","企業獲利"],
    "bond": ["債券","殖利率","公債","聯準會","Fed","利率","通膨","信用利差"],
    "high-yield": ["高收益債","垃圾債","信用風險","違約","信用利差"],
    "emerging": ["新興市場","中國","印度","巴西","東南亞","美元"],
    "energy": ["能源","原油","天然氣","OPEC","石油","EIA"],
    "gold": ["黃金","金價","美元","實質利率","避險"]
  };

  const state = {
    entries: [],
    news: [],
    events: []
  };

  const $ = (s, root = document) => root.querySelector(s);
  const $$ = (s, root = document) => [...root.querySelectorAll(s)];
  const escapeHtml = (v) => String(v || "").replace(/[&<>\"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));

  function load() {
    try {
      const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      state.entries = Array.isArray(value) ? value : [];
    } catch {
      state.entries = [];
    }
  }

  function save() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.entries));
    window.dispatchEvent(new CustomEvent("market-portfolio-changed", { detail: state.entries }));
    renderEverywhere();
  }

  function normalize(text) {
    return String(text || "").toLowerCase().replace(/\s+/g, "");
  }

  function entryKeywords(entry) {
    const keys = new Set();
    [entry.symbol, entry.name, ...(entry.aliases || [])].forEach(x => {
      if (x) keys.add(normalize(x));
    });
    (THEME_KEYWORDS[entry.theme] || []).forEach(x => keys.add(normalize(x)));
    return [...keys].filter(x => x.length >= 2);
  }

  function relevanceForNews(item, entry) {
    const text = normalize(`${item.title || ""} ${item.summary || ""} ${item.source || ""}`);
    let score = 0;
    const direct = [entry.symbol, entry.name, ...(entry.aliases || [])].filter(Boolean).map(normalize);
    direct.forEach(key => {
      if (key.length >= 2 && text.includes(key)) score += key === normalize(entry.symbol) ? 100 : 80;
    });
    (THEME_KEYWORDS[entry.theme] || []).forEach(keyword => {
      if (text.includes(normalize(keyword))) score += 18;
    });
    if (entry.type === "etf" && /(etf|指數|成分股|殖利率|央行|通膨|pmi|非農)/i.test(text)) score += 8;
    if (entry.type === "fund" && /(基金|淨值|利率|匯率|央行|通膨|市場)/i.test(text)) score += 8;
    return score;
  }

  function relevanceForEvent(event, entry) {
    const text = normalize(`${event.title || ""} ${event.description || ""} ${(event.assets || []).join(" ")} ${(event.tags || []).join(" ")}`);
    let score = 0;
    entryKeywords(entry).forEach(key => {
      if (text.includes(key)) score += 24;
    });
    const marketMap = {
      TW: ["台股","台灣","新台幣"],
      US: ["美國","聯準會","美元","美債"],
      JP: ["日本","日銀","日圓"],
      KR: ["韓國","韓元","韓國銀行"]
    };
    (marketMap[entry.market] || []).forEach(k => {
      if (text.includes(normalize(k))) score += 8;
    });
    if (entry.type === "fund" && event.impact === "high") score += 5;
    return score;
  }

  function newsForPortfolio(limit = 8) {
    const scored = [];
    state.news.forEach(item => {
      let best = 0;
      let reason = null;
      state.entries.forEach(entry => {
        const score = relevanceForNews(item, entry);
        if (score > best) {
          best = score;
          reason = entry;
        }
      });
      if (best > 0) scored.push({ item, score: best, reason });
    });
    scored.sort((a,b) => b.score - a.score || new Date(b.item.published_at || 0) - new Date(a.item.published_at || 0));
    return scored.slice(0, limit);
  }

  function eventsForPortfolio(limit = 6) {
    const now = Date.now() - 6 * 3600e3;
    const scored = [];
    state.events.forEach(event => {
      const when = new Date(event.start).getTime();
      if (!Number.isFinite(when) || when < now) return;
      let best = 0, reason = null;
      state.entries.forEach(entry => {
        const score = relevanceForEvent(event, entry);
        if (score > best) { best = score; reason = entry; }
      });
      if (best > 0) scored.push({ event, score: best, reason });
    });
    scored.sort((a,b) => b.score - a.score || new Date(a.event.start) - new Date(b.event.start));
    return scored.slice(0, limit);
  }

  function typeLabel(type) {
    return ({ stock:"股票", etf:"ETF", fund:"基金" })[type] || "標的";
  }

  function renderEntryList(target) {
    if (!target) return;
    if (!state.entries.length) {
      target.innerHTML = '<div class="portfolio-empty-mini">尚未加入股票、ETF 或基金。</div>';
      return;
    }
    target.innerHTML = state.entries.map(entry => `
      <article class="portfolio-entry">
        <div class="portfolio-entry-main">
          <span class="asset-type ${entry.type}">${typeLabel(entry.type)}</span>
          <div><strong>${escapeHtml(entry.name || entry.symbol)}</strong><small>${escapeHtml(entry.symbol || "")}${entry.market ? ` · ${escapeHtml(entry.market)}` : ""}</small></div>
        </div>
        <button type="button" data-remove-entry="${entry.id}" aria-label="移除">×</button>
      </article>`).join("");
    $$("[data-remove-entry]", target).forEach(btn => btn.addEventListener("click", () => remove(btn.dataset.removeEntry)));
  }

  function renderHome() {
    const empty = $("#portfolioFocusEmpty");
    const content = $("#portfolioFocusContent");
    const count = $("#portfolioAssetCount");
    const newsGrid = $("#portfolioNewsGrid");
    const eventList = $("#portfolioEventFocus");
    if (!empty || !content) return;

    count.textContent = `${state.entries.length} 個持有／追蹤標的`;
    empty.hidden = state.entries.length > 0;
    content.hidden = state.entries.length === 0;
    if (!state.entries.length) return;

    const relatedNews = newsForPortfolio(4);
    newsGrid.innerHTML = relatedNews.length ? relatedNews.map(({item, reason, score}) => `
      <a class="portfolio-news-card" href="${item.link}" target="_blank" rel="noreferrer noopener">
        <div><span>${escapeHtml(item.source || "財經新聞")}</span><b>關聯：${escapeHtml(reason.name || reason.symbol)}</b></div>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.summary || "點擊前往原始新聞")}</p>
      </a>`).join("") : '<div class="portfolio-empty-mini">目前新聞中尚未找到直接相關內容，系統會在下一次新聞更新後重新比對。</div>';

    const relatedEvents = eventsForPortfolio(4);
    eventList.innerHTML = relatedEvents.length ? relatedEvents.map(({event, reason}) => `
      <a class="portfolio-event-row" href="event.html?id=${encodeURIComponent(event.id)}">
        <time>${new Date(event.start).toLocaleString("zh-TW",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false})}</time>
        <span><strong>${escapeHtml(event.title)}</strong><small>可能影響：${escapeHtml(reason.name || reason.symbol)}</small></span>
        <b class="impact-${event.impact || "low"}">${event.impact === "high" ? "高" : event.impact === "medium" ? "中" : "低"}</b>
      </a>`).join("") : '<div class="portfolio-empty-mini">未來事件尚未與目前標的建立明確關聯。</div>';
  }

  function renderPage() {
    const list = $("#portfolioPageEntries");
    if (!list) return;
    renderEntryList(list);
    const stats = $("#portfolioPageStats");
    const fundCount = state.entries.filter(x => x.type === "fund").length;
    const etfCount = state.entries.filter(x => x.type === "etf").length;
    stats.innerHTML = `
      <article><span>全部</span><strong>${state.entries.length}</strong></article>
      <article><span>股票</span><strong>${state.entries.filter(x=>x.type==="stock").length}</strong></article>
      <article><span>ETF</span><strong>${etfCount}</strong></article>
      <article><span>基金</span><strong>${fundCount}</strong></article>`;

    const feed = $("#portfolioPageNews");
    const related = newsForPortfolio(12);
    feed.innerHTML = related.length ? related.map(({item, reason}) => `
      <a class="portfolio-page-news" href="${item.link}" target="_blank" rel="noreferrer noopener">
        <div><span>${escapeHtml(item.source || "財經新聞")}</span><b>${escapeHtml(reason.name || reason.symbol)}</b></div>
        <h2>${escapeHtml(item.title)}</h2>
        <p>${escapeHtml(item.summary || "點擊前往原始來源")}</p>
      </a>`).join("") : '<div class="portfolio-empty-mini">加入標的後，這裡會優先顯示與持倉相關的新聞。</div>';
  }

  function renderDialog() {
    renderEntryList($("#portfolioDialogList"));
  }

  function renderEverywhere() {
    renderHome();
    renderPage();
    renderDialog();
  }

  function add(entry) {
    const name = String(entry.name || "").trim();
    const symbol = String(entry.symbol || "").trim().toUpperCase();
    if (!name && !symbol) throw new Error("請輸入名稱或代碼");
    const key = `${entry.market || ""}:${symbol || normalize(name)}:${entry.type}`;
    if (state.entries.some(x => x.key === key)) throw new Error("這個標的已經加入");
    state.entries.push({
      id: crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
      key,
      type: entry.type || "stock",
      market: entry.market || "",
      symbol,
      name: name || symbol,
      aliases: [],
      theme: entry.theme || "",
      quantity: entry.quantity || "",
      cost: entry.cost || ""
    });
    save();
  }

  function remove(id) {
    state.entries = state.entries.filter(x => x.id !== id);
    save();
  }

  function bindForms() {
    const forms = ["#portfolioAddForm", "#portfolioPageAddForm"];
    forms.forEach(selector => {
      const form = $(selector);
      if (!form) return;
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const fd = new FormData(form);
        const status = $(".portfolio-form-status", form);
        try {
          add(Object.fromEntries(fd.entries()));
          form.reset();
          if (status) status.textContent = "已加入";
        } catch (error) {
          if (status) status.textContent = error.message;
        }
      });
      const type = $('[name="type"]', form);
      const theme = $('[name="theme"]', form);
      const syncTheme = () => {
        if (!theme) return;
        theme.closest(".fund-theme-field").hidden = type.value !== "fund";
      };
      type?.addEventListener("change", syncTheme);
      syncTheme();
    });
  }

  function bindDialog() {
    const dialog = $("#portfolioDialog");
    ["#portfolioSetupBtn","#portfolioManageBtn"].forEach(selector => {
      $(selector)?.addEventListener("click", () => {
        renderDialog();
        dialog?.showModal();
      });
    });
    $("#closePortfolioDialog")?.addEventListener("click", () => dialog?.close());
  }

  window.addEventListener("market-news-loaded", event => {
    state.news = event.detail.items || [];
    renderEverywhere();
  });

  load();
  state.events = window.__MARKET_EVENT_SEED__?.events || [];
  bindForms();
  bindDialog();
  renderEverywhere();

  window.MarketPortfolio = { state, add, remove, save, newsForPortfolio, eventsForPortfolio };
})();