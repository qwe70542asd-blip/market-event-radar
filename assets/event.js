(() => {
  "use strict";

  const DAY_NAMES = ["日", "一", "二", "三", "四", "五", "六"];
  const REGION_MAP = { TW: "台灣", US: "美國", JP: "日本", KR: "韓國", EU: "歐洲", GLOBAL: "全球" };
  const CATEGORY_MAP = { "central-bank": "央行政策", macro: "總經數據", earnings: "企業財報", tech: "科技活動", taiwan: "台股公告", policy: "政策／地緣" };
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
  function renderNotFound() {
    document.getElementById("detailRoot").innerHTML = `<div class="not-found-card"><h1>找不到這個事件</h1><p>事件可能已過期、資料尚未同步，或網址中的 id 不正確。</p><a class="mini-btn ghost-link" href="index.html">返回首頁</a></div>`;
  }
  function renderEvent(event, relatedNews, newsSourceStatus) {
    document.title = `${event.title}｜全球市場即時雷達`;
    const countdown = formatRelative(new Date(event.start).getTime() - Date.now());
    const assets = (event.assets || []).map((asset) => `<span>${escapeHtml(asset)}</span>`).join("");
    const tags = (event.tags || []).map((tag) => `<span>${escapeHtml(tag)}</span>`).join("");
    const newsCards = relatedNews.length
      ? relatedNews.map((item) => `<a class="news-card detail-news-card" href="${item.link}" target="_blank" rel="noreferrer noopener"><div class="news-meta"><span>${escapeHtml(item.source || '新聞')}</span><span>${item.published_at ? formatDateTime(item.published_at) : '即時搜尋'}</span></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.event_title || event.title)}</p></a>`).join("")
      : `<div class="news-empty-block"><h3>目前尚未抓到這個事件的報導</h3><p>你可以先用搜尋入口查看最新新聞；等 GitHub Actions 的「Update related news」執行後，這裡會自動補上新聞卡片。</p><a class="mini-btn ghost-link" href="${querySearchURL(event.title)}" target="_blank" rel="noreferrer noopener">搜尋 Google 新聞</a></div>`;
    document.getElementById("detailRoot").innerHTML = `
      <section class="detail-hero">
        <div class="detail-main-card">
          <div class="detail-topline"><button id="detailFavoriteBtn" class="detail-favorite" type="button">☆ 收藏事件</button><span class="impact-pill impact-${event.impact}">${IMPACT_MAP[event.impact] || event.impact}</span><span class="detail-kicker">${REGION_MAP[event.region] || event.region}</span><span class="detail-kicker">${CATEGORY_MAP[event.category] || event.category}</span></div>
          <h1>${escapeHtml(event.title)}</h1>
          <p class="detail-lead">${escapeHtml(event.description || '')}</p>
          <div class="detail-grid-inline"><article><span>公布時間</span><strong>${formatDateTime(event.start)}</strong></article><article><span>倒數</span><strong>${countdown}</strong></article><article><span>官方來源</span><strong>${escapeHtml(event.source_name || '官方來源')}</strong></article></div>
        </div>
        <aside class="detail-side-card"><span class="eyebrow">WHY IT MATTERS</span><h2>這件事為什麼重要？</h2><p>${escapeHtml(event.market_effect || '此事件可能影響主要股市、利率預期、匯率與相關產業評價。')}</p><a class="source-link" href="${event.source_url || '#'}" target="_blank" rel="noreferrer noopener">前往官方來源 ↗</a></aside>
      </section>
      <section class="detail-info-grid"><article class="detail-box"><p class="eyebrow">AFFECTED ASSETS</p><h2>可能影響資產</h2><div class="tag-cloud">${assets || '<span>未提供</span>'}</div></article><article class="detail-box"><p class="eyebrow">KEYWORDS</p><h2>事件標籤</h2><div class="tag-cloud alt">${tags || '<span>未提供</span>'}</div></article></section>
      <section class="detail-box wide-box"><div class="section-heading section-heading-tight"><div><p class="eyebrow">EVENT BRIEF</p><h2>事件重點整理</h2></div><span>${newsSourceStatus}</span></div><div class="detail-brief-grid"><article><h3>是什麼</h3><p>${escapeHtml(event.description || '—')}</p></article><article><h3>可能影響</h3><p>${escapeHtml(event.market_effect || '—')}</p></article><article><h3>交易上怎麼看</h3><p>若你有觀察 ${(event.assets || []).slice(0, 3).join('、') || '相關市場'}，可提前在事件前後安排倉位、觀察夜盤與美債、美元等同步反應。</p></article></div></section>
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
