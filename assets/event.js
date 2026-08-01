(() => {
  "use strict";

  const DAY_NAMES = ["日", "一", "二", "三", "四", "五", "六"];
  const REGION_MAP = { TW: "台灣", US: "美國", JP: "日本", KR: "韓國", EU: "歐洲", GLOBAL: "全球" };
  const CATEGORY_MAP = {
    "central-bank":"央行政策", macro:"總經數據", policy:"政策／地緣",
    earnings:"企業財報", "monthly-revenue":"月營收", "report-deadline":"財報期限",
    "ex-dividend":"除權息", "dividend-decision":"股利方案", "dividend-payment":"股利發放",
    "etf-distribution":"ETF 配息", "investor-conference":"法人說明會",
    "shareholder-meeting":"股東會", "corporate-action":"公司行動",
    tech:"產業活動", taiwan:"台股公告"
  };
  const IMPACT_MAP = { high: "高影響", medium: "中影響", low: "低影響" };

  function pad(num) { return String(num).padStart(2, "0"); }
  function escapeHtml(value) { return String(value || "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': '&quot;' }[char])); }
  function formatDateTime(value) {
    const date = new Date(value);
    return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日（週${DAY_NAMES[date.getDay()]}） ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }
  function formatRelative(ms) {
    if (ms <= 0) return "已到時程";
    const min = Math.floor(ms / 60000);
    const d = Math.floor(min / 1440);
    const h = Math.floor((min % 1440) / 60);
    const m = min % 60;
    return [d ? `${d}天` : "", h ? `${h}小時` : "", !d && m ? `${m}分` : ""].filter(Boolean).join(" ") || "即將公布";
  }
  function querySearchURL(query) { return `https://news.google.com/search?q=${encodeURIComponent(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant`; }
  async function loadJson(path, fallback) {
    try {
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) throw new Error(path);
      return response.json();
    } catch {
      return fallback;
    }
  }

  function formatEventTime(event) {
    return event.all_day ? `${formatDateTime(event.start).replace(/\s\d{2}:\d{2}$/,"")}（全天）` : formatDateTime(event.start);
  }
  function numberText(value, currency = "") {
    if (value === undefined || value === null || value === "") return "";
    const num = Number(value);
    if (!Number.isFinite(num)) return String(value);
    const suffix = currency === "USD" ? " 美元" : currency === "TWD" ? " 元" : "";
    return `${num.toLocaleString("zh-TW",{maximumFractionDigits:6})}${suffix}`;
  }
  function corporateFields(event) {
    const rows = [];
    const add = (label, value) => { if (value !== undefined && value !== null && value !== "") rows.push([label, value]); };
    add("股票／基金", [event.symbol, event.asset_name].filter(Boolean).join(" · "));
    add("市場", event.market);
    add("事件類型", CATEGORY_MAP[event.category] || event.event_type);
    add("財報期間", event.fiscal_period);
    add("EPS 預期", event.eps_forecast);
    add("現金股利", numberText(event.cash_dividend, event.currency));
    add("股票股利率", event.stock_dividend_ratio);
    add("除權息日", event.ex_date);
    add("停止過戶／基準日", event.record_date);
    add("股利發放日", event.payment_date);
    add("股東會日期", event.shareholder_meeting_date);
    add("股票分割比例", event.split_ratio);
    add("主動型 ETF", event.is_active_etf ? "是" : "");
    return rows;
  }

  function renderNotFound() {
    document.getElementById("detailRoot").innerHTML = `<div class="not-found-card"><h1>找不到這個事件</h1><p>事件可能已過期、資料尚未同步，或網址中的 id 不正確。</p><a class="mini-btn ghost-link" href="index.html">返回首頁</a></div>`;
  }
  function renderEvent(event, relatedNews, newsSourceStatus) {
    document.title = `${event.title}｜全球市場即時雷達`;
    const countdown = formatRelative(new Date(event.start).getTime() - Date.now());
    const assets = (event.assets || []).map((asset) => `<span>${escapeHtml(asset)}</span>`).join("");
    const tags = (event.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("");
    const fields = corporateFields(event);
    const corporateGrid = fields.length
      ? `<section class="detail-box wide-box"><div class="section-heading section-heading-tight"><div><p class="eyebrow">EVENT DATA</p><h2>公司事件細節</h2></div><span>${fields.length} 個欄位</span></div><div class="event-data-grid">${fields.map(([label,value]) => `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`).join("")}</div></section>`
      : "";
    const newsCards = relatedNews.length
      ? relatedNews.map((item) => `<a class="news-card detail-news-card" href="${item.link}" target="_blank" rel="noreferrer noopener"><div class="news-meta"><span>${escapeHtml(item.source || '新聞')}</span><span>${item.published_at ? formatDateTime(item.published_at) : '即時搜尋'}</span></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.event_title || event.title)}</p></a>`).join("")
      : `<div class="news-empty-block"><h3>目前尚未抓到這個事件的報導</h3><p>你可以先用搜尋入口查看最新新聞；等 GitHub Actions 的「Update related news」執行後，這裡會自動補上新聞卡片。</p><a class="mini-btn ghost-link" href="${querySearchURL(event.title)}" target="_blank" rel="noreferrer noopener">搜尋 Google 新聞</a></div>`;
    document.getElementById("detailRoot").innerHTML = `
      <section class="detail-hero">
        <div class="detail-main-card">
          <div class="detail-topline"><button id="detailFavoriteBtn" class="detail-favorite" type="button">☆ 收藏事件</button><span class="impact-pill impact-${event.impact}">${IMPACT_MAP[event.impact] || event.impact}</span><span class="detail-kicker">${REGION_MAP[event.region] || event.region}</span><span class="detail-kicker">${CATEGORY_MAP[event.category] || event.category}</span></div>
          <h1>${escapeHtml(event.title)}</h1>
          <p class="detail-lead">${escapeHtml(event.description || '')}</p>
          <div class="detail-grid-inline">
      <article><span>事件時間</span><strong>${formatEventTime(event)}</strong></article>
      <article><span>發布階段</span><strong>${escapeHtml(event.release_stage || event.category || "—")}</strong></article>
      <article><span>時間狀態</span><strong>${["estimated","deadline-window","time-window"].includes(event.time_status) ? "估計／期限區間" : "官方已確認"}</strong></article>
    </div>
        </div>
        <aside class="detail-side-card"><span class="eyebrow">WHY IT MATTERS</span><h2>這件事為什麼重要？</h2><p>${escapeHtml(event.market_effect || '此事件可能影響主要股市、利率預期、匯率與相關產業評價。')}</p><a class="source-link" href="${event.source_url || '#'}" target="_blank" rel="noreferrer noopener">前往官方來源 ↗</a></aside>
      </section>
      <section class="detail-info-grid"><article class="detail-box"><p class="eyebrow">AFFECTED ASSETS</p><h2>可能影響資產</h2><div class="tag-cloud">${assets || '<span>未提供</span>'}</div></article><article class="detail-box"><p class="eyebrow">KEYWORDS</p><h2>事件標籤</h2><div class="tag-cloud alt">${tags || '<span>未提供</span>'}</div></article></section>
      ${corporateGrid}
      <section class="detail-box wide-box">
      <div class="section-heading section-heading-tight"><div><p class="eyebrow">EVENT BRIEF</p><h2>事件重點整理</h2></div><span>${newsSourceStatus}</span></div>
      ${event.verification_note ? `<div class="verification-note">${escapeHtml(event.verification_note)}</div>` : ""}
      <div class="detail-brief-grid"><article><h3>是什麼</h3><p>${escapeHtml(event.description || '—')}</p></article><article><h3>可能影響</h3><p>${escapeHtml(event.market_effect || '—')}</p></article><article><h3>交易上怎麼看</h3><p>若你有觀察 ${(event.assets || []).slice(0, 3).join('、') || '相關市場'}，可提前在事件前後安排倉位、觀察夜盤與美債、美元等同步反應。</p></article></div>
      ${(event.watch_items || []).length ? `<div class="detail-watch"><h3>公布時要看什麼</h3><div>${event.watch_items.map(x => `<span>${escapeHtml(x)}</span>`).join("")}</div></div>` : ""}
      ${(event.scenarios || []).length ? `<div class="scenario-grid">${event.scenarios.map(x => `<article><strong>${escapeHtml(x.label)}</strong><p>${escapeHtml(x.effect)}</p></article>`).join("")}</div>` : ""}
      </section>
      <section class="detail-box wide-box"><div class="section-heading section-heading-tight"><div><p class="eyebrow">RELATED COVERAGE</p><h2>相關報導</h2></div><span>${relatedNews.length} 則報導</span></div><div class="news-grid detail-news-grid">${newsCards}</div></section>`;
  }

  function bindAccountUI() {
    const accountBtn = document.getElementById("accountBtn");
    const dialog = document.getElementById("accountDialog");
    accountBtn?.addEventListener("click", () => dialog?.showModal());
    document.getElementById("guestModeBtn")?.addEventListener("click", () => dialog?.close());
    document.getElementById("googleLoginBtn")?.addEventListener("click", async () => {
      try { await window.MarketAuth.signInGoogle(); }
      catch (error) { document.getElementById("authStatus").textContent = error.message; }
    });
    document.getElementById("logoutBtn")?.addEventListener("click", async () => { await window.MarketAuth.signOut(); dialog?.close(); });
    window.addEventListener("market-auth-changed", (ev) => {
      const user = ev.detail.user;
      const label = document.getElementById("accountLabel");
      const avatar = document.getElementById("accountAvatar");
      const status = document.getElementById("authStatus");
      const logout = document.getElementById("logoutBtn");
      if (user) {
        label.textContent = user.displayName || user.email || "已登入";
        avatar.textContent = (user.displayName || user.email || "G").slice(0, 1);
        status.textContent = "已登入 Google，收藏與提醒會跨裝置同步。";
        logout.hidden = false;
      } else {
        label.textContent = "訪客模式";
        avatar.textContent = "訪";
        status.textContent = ev.detail.enabled ? "可使用 Google 登入。" : "尚未設定 Firebase，Google 登入暫不可用。";
        logout.hidden = true;
      }
      document.getElementById("googleLoginBtn").disabled = !ev.detail.enabled;
    });
  }

  function bindDetailFavorite(eventId) {
    const button = document.getElementById("detailFavoriteBtn");
    if (!button) return;
    const refresh = () => {
      const active = new Set(window.MarketAuth?.getData?.().favoriteEventIds || []).has(eventId);
      button.textContent = active ? "★ 已收藏" : "☆ 收藏事件";
      button.classList.toggle("active", active);
    };
    button.addEventListener("click", async () => {
      const data = window.MarketAuth.getData();
      const favorites = new Set(data.favoriteEventIds || []);
      if (favorites.has(eventId)) favorites.delete(eventId); else favorites.add(eventId);
      await window.MarketAuth.saveData({ favoriteEventIds: [...favorites] });
      refresh();
    });
    window.addEventListener("market-user-data-changed", refresh);
    setTimeout(refresh, 300);
  }

  async function bootstrap() {
    const params = new URLSearchParams(window.location.search);
    const eventId = params.get("id");
    if (!eventId) return renderNotFound();
    const [payload, newsPayload] = await Promise.all([
      loadJson("data/events.json", window.__MARKET_EVENT_SEED__ || { events: [] }),
      loadJson("data/news.json", window.__MARKET_NEWS_SEED__ || { items: [], source: {} }),
    ]);
    const event = (payload.events || []).find((row) => row.id === eventId);
    if (!event) return renderNotFound();
    const relatedNews = (newsPayload.items || []).filter((item) => item.event_id === eventId).slice(0, 8);
    const status = newsPayload.source?.status === "ok" ? "報導來源正常" : (newsPayload.source?.message || "使用搜尋入口");
    renderEvent(event, relatedNews, status);
    bindDetailFavorite(eventId);
  }
  bindAccountUI();
  bootstrap();
})();
