(() => {
  "use strict";

  const PREF_KEY = "market-event-radar-v9";
  const state = {
    payload: { metadata: {}, sources: [], events: [] },
    newsPayload: { metadata: {}, source: {}, items: [] },
    events: [],
    filtered: [],
    focus: "all",
    calendarDate: new Date(),
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const DAY_NAMES = ["日", "一", "二", "三", "四", "五", "六"];
  const REGION_MAP = { TW: "台灣", US: "美國", JP: "日本", KR: "韓國", EU: "歐洲", GLOBAL: "全球" };
  const CATEGORY_MAP = { "central-bank": "央行政策", macro: "總經數據", earnings: "企業財報", tech: "科技活動", taiwan: "台股公告", policy: "政策／地緣" };
  const IMPACT_MAP = { high: "高影響", medium: "中影響", low: "低影響" };

  function pad(num) { return String(num).padStart(2, "0"); }
  function formatDate(date) { return `${date.getMonth() + 1}/${date.getDate()}（週${DAY_NAMES[date.getDay()]}）`; }
  function formatDateTime(value) {
    const date = new Date(value);
    return `${date.getMonth() + 1}/${date.getDate()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }
  function formatDateTimeLong(value) {
    const date = new Date(value);
    return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日（週${DAY_NAMES[date.getDay()]}） ${pad(date.getHours())}:${pad(date.getMinutes())}`;
  }
  function formatRelative(ms) {
    if (ms <= 0) return "進行中／已公布";
    const min = Math.floor(ms / 60000);
    const d = Math.floor(min / 1440);
    const h = Math.floor((min % 1440) / 60);
    const m = min % 60;
    const parts = [];
    if (d) parts.push(`${d}天`);
    if (h) parts.push(`${h}小時`);
    if (!d && m) parts.push(`${m}分`);
    return parts.join(" ") || "即將公布";
  }
  function slug(text) { return String(text || "").toLowerCase(); }
  function escapeHtml(value) {
    return String(value || "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': '&quot;' }[char]));
  }

  function loadPrefs() {
    try { return JSON.parse(localStorage.getItem(PREF_KEY) || "{}"); }
    catch { return {}; }
  }
  function savePrefs() {
    const prefs = {
      focus: state.focus,
      range: $("#rangeFilter")?.value || "30",
      region: $("#regionFilter")?.value || "all",
      category: $("#categoryFilter")?.value || "all",
      highOnly: $("#highOnly")?.checked || false,
      search: $("#searchInput")?.value || "",
      month: state.calendarDate.toISOString(),
    };
    localStorage.setItem(PREF_KEY, JSON.stringify(prefs));
  }

  async function loadJson(path, fallback) {
    try {
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) throw new Error(path);
      return response.json();
    } catch {
      return fallback;
    }
  }

  function normalizeEvent(raw) {
    const startDate = new Date(raw.start);
    const searchBlob = [raw.title, raw.description, raw.market_effect, raw.region, raw.category, ...(raw.assets || []), ...(raw.tags || [])].join(" ").toLowerCase();
    return { ...raw, startDate, dayKey: `${startDate.getFullYear()}-${pad(startDate.getMonth() + 1)}-${pad(startDate.getDate())}`, searchBlob, timestamp: startDate.getTime() };
  }

  function focusMatch(event, focus) {
    if (focus === "all") return true;
    const hay = `${event.title} ${event.description} ${(event.assets || []).join(" ")} ${(event.tags || []).join(" ")}`;
    if (focus === "taiwan") return event.region === "TW" || /台積電|台股|AI|半導體|聯發科|鴻海/i.test(hay);
    if (focus === "rates") return ["central-bank", "macro"].includes(event.category) || /CPI|PPI|通膨|利率|聯準會|日銀|ECB|央行|非農/i.test(hay);
    if (focus === "earnings") return event.category === "earnings" || /財報|營收|法說|AMD|NVIDIA|台積電/i.test(hay);
    if (focus === "asia") return ["TW", "JP", "KR"].includes(event.region) || /日本|韓國|台灣|日銀/i.test(hay);
    return true;
  }

  function applyFilters() {
    const search = slug($("#searchInput").value.trim());
    const region = $("#regionFilter").value;
    const category = $("#categoryFilter").value;
    const range = $("#rangeFilter").value;
    const highOnly = $("#highOnly").checked;
    const now = new Date();
    let maxTs = Infinity;
    if (range !== "all") maxTs = now.getTime() + Number(range) * 86400000;

    state.filtered = state.events.filter((event) => {
      if (event.timestamp < now.getTime() - 24 * 3600000) return false;
      if (event.timestamp > maxTs) return false;
      if (region !== "all" && event.region !== region) return false;
      if (category !== "all" && event.category !== category) return false;
      if (highOnly && event.impact !== "high") return false;
      if (search && !event.searchBlob.includes(search)) return false;
      if (!focusMatch(event, state.focus)) return false;
      return true;
    }).sort((a, b) => a.timestamp - b.timestamp);

    renderStats();
    renderCalendar();
    renderAgenda();
    savePrefs();
  }

  function renderStats() {
    const now = new Date();
    const todayKey = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    const todayEvents = state.filtered.filter((event) => event.dayKey === todayKey);
    const weekEvents = state.filtered.filter((event) => event.timestamp <= now.getTime() + 7 * 86400000);
    const highEvents = state.filtered.filter((event) => event.impact === "high" && event.timestamp <= now.getTime() + 30 * 86400000);
    const nextHigh = state.events.filter((event) => event.impact === "high" && event.timestamp >= now.getTime()).sort((a, b) => a.timestamp - b.timestamp)[0];
    $("#todayCount").textContent = String(todayEvents.length);
    $("#todayRisk").textContent = todayEvents.some((event) => event.impact === "high") ? "今天有高影響事件" : "今天無高風險事件";
    $("#weekCount").textContent = String(weekEvents.length);
    $("#highCount").textContent = String(highEvents.length);
    $("#nextTitle").textContent = nextHigh ? nextHigh.title : "近期沒有高影響事件";
    const nextLink = $("#nextEventLink");
    if (nextLink) nextLink.href = nextHigh ? `event.html?id=${encodeURIComponent(nextHigh.id)}` : "#calendarSection";
    $("#nextCountdown").textContent = nextHigh ? formatRelative(nextHigh.timestamp - now.getTime()) : "—";
    let hintTitle = "穩定";
    let hintText = "本週事件壓力偏低";
    if (highEvents.length >= 5) { hintTitle = "高波動"; hintText = "高影響事件偏多，留意倉位與夜盤"; }
    else if (highEvents.length >= 2) { hintTitle = "偏熱"; hintText = "未來 30 天有多個關鍵催化"; }
    $("#marketHintValue").textContent = hintTitle;
    $("#marketHintText").textContent = hintText;
    $("#updatedAt").textContent = state.payload.metadata.updated_at ? formatDateTime(state.payload.metadata.updated_at) : "—";
    $("#newsUpdatedAt").textContent = state.newsPayload.metadata.updated_at ? formatDateTime(state.newsPayload.metadata.updated_at) : "尚未更新";
  }

  function eventChip(event) {
    const link = document.createElement("a");
    link.href = `event.html?id=${encodeURIComponent(event.id)}`;
    link.className = `calendar-event-chip impact-${event.impact}`;
    link.innerHTML = `<span>${escapeHtml(event.all_day ? "全天" : `${pad(event.startDate.getHours())}:${pad(event.startDate.getMinutes())}`)}</span><strong>${escapeHtml(event.title)}</strong>`;
    link.title = `${event.title}\n${event.description || event.market_effect || ""}`;
    link.addEventListener("mouseenter", (ev) => showPreview(ev.currentTarget, event));
    link.addEventListener("focus", (ev) => showPreview(ev.currentTarget, event));
    link.addEventListener("mouseleave", hidePreview);
    link.addEventListener("blur", hidePreview);
    return link;
  }

  function getMonthMatrix(baseDate) {
    const year = baseDate.getFullYear();
    const month = baseDate.getMonth();
    const first = new Date(year, month, 1);
    const last = new Date(year, month + 1, 0);
    const start = new Date(first); start.setDate(start.getDate() - start.getDay());
    const end = new Date(last); end.setDate(end.getDate() + (6 - end.getDay()));
    const days = [];
    for (let cursor = new Date(start); cursor <= end; cursor.setDate(cursor.getDate() + 1)) days.push(new Date(cursor));
    return days;
  }

  function isMobileCalendar() {
    return window.matchMedia("(max-width: 820px)").matches;
  }

  function openDayEvents(day, events) {
    const dialog = $("#dayEventsDialog");
    const title = $("#dayEventsTitle");
    const list = $("#dayEventsList");
    if (!dialog || !title || !list) return;
    title.textContent = `${day.getMonth() + 1} 月 ${day.getDate()} 日（週${DAY_NAMES[day.getDay()]}）`;
    if (!events.length) {
      list.innerHTML = '<div class="day-events-empty">這一天沒有市場事件。</div>';
    } else {
      list.innerHTML = events.map((event) => `
        <a class="day-event-row impact-${event.impact}" href="event.html?id=${encodeURIComponent(event.id)}">
          <div class="day-event-time">${event.all_day ? "全天" : `${pad(event.startDate.getHours())}:${pad(event.startDate.getMinutes())}`}</div>
          <div><strong>${escapeHtml(event.title)}</strong><small>${REGION_MAP[event.region] || event.region} · ${CATEGORY_MAP[event.category] || event.category} · ${IMPACT_MAP[event.impact]}</small></div>
          <span>›</span>
        </a>`).join("");
    }
    if (!dialog.open) dialog.showModal();
  }

  function renderCalendar() {
    const grid = $("#calendarGrid");
    grid.innerHTML = "";
    const baseDate = state.calendarDate;
    $("#calendarTitle").textContent = `${baseDate.getFullYear()} 年 ${baseDate.getMonth() + 1} 月`;
    const eventMap = new Map();
    state.filtered.forEach((event) => {
      if (!eventMap.has(event.dayKey)) eventMap.set(event.dayKey, []);
      eventMap.get(event.dayKey).push(event);
    });
    const days = getMonthMatrix(baseDate);
    const today = new Date();
    const todayKey = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;

    days.forEach((day) => {
      const key = `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`;
      const cellEvents = (eventMap.get(key) || []).sort((a, b) => a.timestamp - b.timestamp);
      const cell = document.createElement("article");
      cell.className = "calendar-day";
      if (day.getMonth() !== baseDate.getMonth()) cell.classList.add("muted");
      if (key === todayKey) cell.classList.add("today");
      const mobile = isMobileCalendar();
      const extra = !mobile && cellEvents.length > 3 ? `<button class="more-link" data-day="${key}">+${cellEvents.length - 3} 更多</button>` : "";
      cell.innerHTML = `<div class="calendar-day-head"><strong>${day.getDate()}</strong><small>${cellEvents.length ? `${cellEvents.length} 件` : ""}</small></div><div class="calendar-events"></div>${extra}`;
      const box = cell.querySelector(".calendar-events");
      if (mobile) {
        box.innerHTML = cellEvents.length
          ? `<div class="mobile-event-dots">${cellEvents.slice(0, 4).map((event) => `<i class="impact-${event.impact}"></i>`).join("")}</div>`
          : '<div class="calendar-empty-mini"></div>';
        cell.classList.add("mobile-day-cell");
        cell.tabIndex = 0;
        cell.setAttribute("role", "button");
        cell.setAttribute("aria-label", `${day.getMonth()+1}月${day.getDate()}日，${cellEvents.length}件事件`);
        cell.addEventListener("click", () => openDayEvents(day, cellEvents));
        cell.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openDayEvents(day, cellEvents); }
        });
      } else {
        cellEvents.slice(0, 3).forEach((event) => box.appendChild(eventChip(event)));
        if (!cellEvents.length) box.innerHTML = '<div class="calendar-empty-mini"></div>';
      }
      grid.appendChild(cell);
    });
    $$(".more-link").forEach((button) => button.addEventListener("click", () => {
      const first = state.filtered.find((event) => event.dayKey === button.dataset.day);
      if (first) window.location.href = `event.html?id=${encodeURIComponent(first.id)}`;
    }));
  }

  function renderAgenda() {
    const list = $("#eventList");
    list.innerHTML = "";
    const upcoming = state.filtered.filter((event) => event.impact === "high").slice(0, 8);
    $("#resultCount").textContent = `${upcoming.length} 筆事件`;
    $("#emptyState").hidden = !!upcoming.length;
    upcoming.forEach((event) => {
      const node = document.createElement("a");
      node.href = `event.html?id=${encodeURIComponent(event.id)}`;
      node.className = `compact-event-card impact-${event.impact}`;
      node.innerHTML = `
        <div class="compact-event-head"><span>${formatDate(event.startDate)}</span><div><b>${IMPACT_MAP[event.impact]}</b><button class="favorite-inline" type="button" data-favorite-id="${escapeHtml(event.id)}" aria-label="收藏事件">☆</button></div></div>
        <h3>${escapeHtml(event.title)}</h3>
        <p>${escapeHtml(event.description || event.market_effect || "")}</p>
        <div class="compact-event-meta"><span>${CATEGORY_MAP[event.category] || event.category}</span><span>${REGION_MAP[event.region] || event.region}</span><span>${event.all_day ? "全天" : `${pad(event.startDate.getHours())}:${pad(event.startDate.getMinutes())}`}</span></div>`;
      list.appendChild(node);
    });
  }

  function renderSources() {
    const sources = [{ name: "TradingView 市場代理跑馬燈", status: "ok", message: "ETF / ADR / 匯率 / 風險指標" }, ...(state.payload.sources || []), state.newsPayload.source?.name ? { ...state.newsPayload.source, last_success: state.newsPayload.metadata.updated_at } : null].filter(Boolean);
    $("#sourceCount").textContent = `${sources.length} 個來源`;
    const wrapper = $("#sourceStatus");
    wrapper.innerHTML = "";
    sources.forEach((source) => {
      const row = document.createElement("div");
      row.className = "source-row";
      row.innerHTML = `<div><strong>${escapeHtml(source.name)}</strong><small>${escapeHtml(source.message || (source.last_success ? formatDateTime(source.last_success) : "—"))}</small></div><span class="source-pill ${source.status || 'warning'}">${source.status === 'ok' ? '正常' : '備援中'}</span>`;
      wrapper.appendChild(row);
    });
  }

  function showPreview(target, event) {
    const preview = $("#eventPreview");
    preview.hidden = false;
    preview.innerHTML = `<div class="preview-top"><span class="impact-pill impact-${event.impact}">${IMPACT_MAP[event.impact]}</span><span>${REGION_MAP[event.region] || event.region}</span><span>${CATEGORY_MAP[event.category] || event.category}</span></div><strong>${escapeHtml(event.title)}</strong><p>${escapeHtml(event.description || event.market_effect || "")}</p><small>${formatDateTimeLong(event.start)} · 點擊查看詳情頁</small>`;
    const rect = target.getBoundingClientRect();
    const top = window.scrollY + rect.top - preview.offsetHeight - 10;
    const left = window.scrollX + Math.min(rect.left, window.innerWidth - 340);
    preview.style.top = `${Math.max(window.scrollY + 10, top)}px`;
    preview.style.left = `${Math.max(12, left)}px`;
  }
  function hidePreview() { $("#eventPreview").hidden = true; }

  function updateClock() {
    const now = new Date();
    $("#todayLabel").textContent = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日（週${DAY_NAMES[now.getDay()]}）`;
    $("#clockLabel").textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  }

  function restorePrefs() {
    const prefs = loadPrefs();
    if (prefs.focus) state.focus = prefs.focus;
    if (prefs.month) state.calendarDate = new Date(prefs.month);
    if (prefs.range) $("#rangeFilter").value = prefs.range;
    if (prefs.region) $("#regionFilter").value = prefs.region;
    if (prefs.category) $("#categoryFilter").value = prefs.category;
    $("#highOnly").checked = !!prefs.highOnly;
    if (prefs.search) $("#searchInput").value = prefs.search;
    $$(".focus-chip").forEach((button) => button.classList.toggle("active", button.dataset.focus === state.focus));
  }

  function bind() {
    $("#refreshBtn").addEventListener("click", () => window.location.reload());
    $("#closeDayEventsBtn")?.addEventListener("click", () => $("#dayEventsDialog")?.close());
    $("#dayEventsDialog")?.addEventListener("click", (event) => {
      if (event.target === $("#dayEventsDialog")) $("#dayEventsDialog").close();
    });
    $("#prevMonth").addEventListener("click", () => { state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() - 1, 1); renderCalendar(); savePrefs(); });
    $("#nextMonth").addEventListener("click", () => { state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() + 1, 1); renderCalendar(); savePrefs(); });
    $("#todayMonth").addEventListener("click", () => { const now = new Date(); state.calendarDate = new Date(now.getFullYear(), now.getMonth(), 1); renderCalendar(); savePrefs(); });
    ["#searchInput", "#rangeFilter", "#regionFilter", "#categoryFilter", "#highOnly"].forEach((selector) => $(selector).addEventListener(selector === "#searchInput" ? "input" : "change", applyFilters));
    $$(".focus-chip").forEach((button) => button.addEventListener("click", () => {
      state.focus = button.dataset.focus;
      $$(".focus-chip").forEach((node) => node.classList.toggle("active", node === button));
      applyFilters();
    }));
  }


  function userData() {
    return window.MarketAuth?.getData?.() || { watchSymbols: [], favoriteEventIds: [], reminders: {}, preferences: {} };
  }

  function openAccountDialog() {
    const dialog = $("#accountDialog");
    if (dialog && !dialog.open) dialog.showModal();
  }

  function updateAuthUI(detail = {}) {
    const user = detail.user || window.MarketAuth?.getUser?.();
    const enabled = detail.enabled ?? window.MarketAuth?.firebaseEnabled;
    const label = $("#accountLabel");
    const avatar = $("#accountAvatar");
    const status = $("#authStatus");
    const logout = $("#logoutBtn");
    if (user) {
      if (label) label.textContent = user.displayName || user.email || "已登入";
      if (avatar) {
        avatar.textContent = (user.displayName || user.email || "G").trim().slice(0, 1).toUpperCase();
        if (user.photoURL) {
          avatar.style.backgroundImage = `url("${user.photoURL}")`;
          avatar.classList.add("has-photo");
        }
      }
      if (status) status.textContent = "已登入 Google，個人資料會同步到其他裝置。";
      if (logout) logout.hidden = false;
      if ($("#syncTitle")) $("#syncTitle").textContent = "已登入同步";
      if ($("#syncDescription")) $("#syncDescription").textContent = "Google 跨裝置同步";
      if ($("#syncActionBtn")) $("#syncActionBtn").textContent = "帳號設定";
      if ($("#drawerSyncState")) $("#drawerSyncState").textContent = "已啟用 Google 跨裝置同步";
    } else {
      if (label) label.textContent = "登入／訪客";
      if (avatar) { avatar.textContent = "訪"; avatar.style.backgroundImage = ""; avatar.classList.remove("has-photo"); }
      if (status) status.textContent = enabled ? "可使用 Google 登入，或繼續使用訪客模式。" : "Google 登入尚未啟用：請先設定 Firebase。訪客模式仍可正常使用。";
      if (logout) logout.hidden = true;
      if ($("#syncTitle")) $("#syncTitle").textContent = "帳號同步";
      if ($("#syncDescription")) $("#syncDescription").textContent = "登入 Google 跨裝置";
      if ($("#syncActionBtn")) $("#syncActionBtn").textContent = "登入同步";
      if ($("#drawerSyncState")) $("#drawerSyncState").textContent = "訪客資料只保存在本機";
    }
    const googleBtn = $("#googleLoginBtn");
    if (googleBtn) googleBtn.disabled = !enabled;
  }

  function openWatchlist() {
    $("#watchlistDrawer").classList.add("open");
    $("#watchlistDrawer").setAttribute("aria-hidden", "false");
    $("#drawerBackdrop").hidden = false;
    renderWatchlist();
  }

  function closeWatchlist() {
    $("#watchlistDrawer").classList.remove("open");
    $("#watchlistDrawer").setAttribute("aria-hidden", "true");
    $("#drawerBackdrop").hidden = true;
  }

  async function addWatchSymbol() {
    const input = $("#watchSymbolInput");
    const symbol = String(input.value || "").trim().toUpperCase();
    if (!symbol) return;
    const data = userData();
    const symbols = [...new Set([...(data.watchSymbols || []), symbol])].slice(0, 50);
    await window.MarketAuth.saveData({ watchSymbols: symbols });
    input.value = "";
    renderWatchlist();
  }

  async function removeWatchSymbol(symbol) {
    const data = userData();
    await window.MarketAuth.saveData({ watchSymbols: (data.watchSymbols || []).filter((item) => item !== symbol) });
    renderWatchlist();
  }

  async function toggleFavorite(eventId) {
    const data = userData();
    const set = new Set(data.favoriteEventIds || []);
    if (set.has(eventId)) set.delete(eventId); else set.add(eventId);
    await window.MarketAuth.saveData({ favoriteEventIds: [...set] });
    renderWatchlist();
    updateFavoriteButtons();
  }

  function updateFavoriteButtons() {
    const favorites = new Set(userData().favoriteEventIds || []);
    $$("[data-favorite-id]").forEach((button) => {
      const active = favorites.has(button.dataset.favoriteId);
      button.textContent = active ? "★" : "☆";
      button.classList.toggle("active", active);
    });
    if ($("#watchlistCount")) $("#watchlistCount").textContent = String((userData().watchSymbols || []).length + favorites.size);
  }

  function renderWatchlist() {
    const data = userData();
    const symbolBox = $("#watchSymbols");
    const favoriteBox = $("#favoriteEvents");
    if (symbolBox) {
      symbolBox.innerHTML = (data.watchSymbols || []).length
        ? (data.watchSymbols || []).map((symbol) => `<div class="watch-item"><strong>${escapeHtml(symbol)}</strong><button type="button" data-remove-symbol="${escapeHtml(symbol)}">移除</button></div>`).join("")
        : '<div class="watch-empty">尚未加入股票或 ETF。</div>';
      $$("[data-remove-symbol]").forEach((button) => button.addEventListener("click", () => removeWatchSymbol(button.dataset.removeSymbol)));
    }
    if (favoriteBox) {
      const eventsById = new Map(state.events.map((event) => [event.id, event]));
      const favorites = (data.favoriteEventIds || []).map((id) => eventsById.get(id)).filter(Boolean);
      favoriteBox.innerHTML = favorites.length
        ? favorites.map((event) => `<a class="watch-item event-watch-item" href="event.html?id=${encodeURIComponent(event.id)}"><span><strong>${escapeHtml(event.title)}</strong><small>${formatDateTime(event.start)}</small></span><button type="button" data-remove-favorite="${escapeHtml(event.id)}">移除</button></a>`).join("")
        : '<div class="watch-empty">尚未收藏事件。</div>';
      $$("[data-remove-favorite]").forEach((button) => button.addEventListener("click", (ev) => { ev.preventDefault(); toggleFavorite(button.dataset.removeFavorite); }));
    }
    updateFavoriteButtons();
  }

  async function enableNotifications() {
    if (!("Notification" in window)) return alert("此瀏覽器不支援通知。");
    const permission = await Notification.requestPermission();
    if (permission === "granted") {
      new Notification("市場事件雷達", { body: "通知已開啟。真正的關閉 App 推播需再設定 Firebase Cloud Messaging。" });
      $("#notificationBtn").textContent = "通知已開啟";
    }
  }

  function bindPersonalTools() {
    ["#accountBtn", "#syncActionBtn"].forEach((selector) => $(selector)?.addEventListener("click", openAccountDialog));
    ["#watchlistBtn", "#openWatchlistBtn"].forEach((selector) => $(selector)?.addEventListener("click", openWatchlist));
    $("#closeWatchlistBtn")?.addEventListener("click", closeWatchlist);
    $("#drawerBackdrop")?.addEventListener("click", closeWatchlist);
    $("#addWatchSymbolBtn")?.addEventListener("click", addWatchSymbol);
    $("#watchSymbolInput")?.addEventListener("keydown", (event) => { if (event.key === "Enter") addWatchSymbol(); });
    $("#notificationBtn")?.addEventListener("click", enableNotifications);
    $("#guestModeBtn")?.addEventListener("click", () => { window.MarketAuth?.useGuest?.(); $("#accountDialog")?.close(); });
    $("#googleLoginBtn")?.addEventListener("click", async () => {
      try { await window.MarketAuth.signInGoogle(); }
      catch (error) { $("#authStatus").textContent = error.message; }
    });
    $("#logoutBtn")?.addEventListener("click", async () => { await window.MarketAuth.signOut(); $("#accountDialog")?.close(); });
    document.addEventListener("click", (event) => {
      const button = event.target.closest("[data-favorite-id]");
      if (!button) return;
      event.preventDefault();
      event.stopPropagation();
      toggleFavorite(button.dataset.favoriteId);
    });
    window.addEventListener("market-auth-changed", (event) => updateAuthUI(event.detail));
    window.addEventListener("market-user-data-changed", () => { renderWatchlist(); updateFavoriteButtons(); });
    setTimeout(() => { updateAuthUI({ enabled: window.MarketAuth?.firebaseEnabled, user: window.MarketAuth?.getUser?.() }); renderWatchlist(); }, 250);
  }

  async function bootstrap() {
    const [payload, newsPayload] = await Promise.all([
      loadJson("data/events.json", window.__MARKET_EVENT_SEED__ || { events: [], metadata: {}, sources: [] }),
      loadJson("data/news.json", window.__MARKET_NEWS_SEED__ || { items: [], metadata: {}, source: {} }),
    ]);
    state.payload = payload;
    state.newsPayload = newsPayload;
    state.events = (payload.events || []).map(normalizeEvent).sort((a, b) => a.timestamp - b.timestamp);
    restorePrefs();
    renderSources();
    bind();
    bindPersonalTools();
    applyFilters();
    updateClock();
    setInterval(updateClock, 1000);
    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(renderCalendar, 120);
    });
    $("#yearLabel").textContent = String(new Date().getFullYear());
  }

  bootstrap();
})();
