(() => {
  "use strict";

  const TZ = "Asia/Taipei";
  const state = {
    payload: null,
    events: [],
    filtered: [],
    calendarDate: new Date(),
    view: "agenda",
  };

  const els = {
    updatedAt: document.querySelector("#updatedAt"),
    todayLabel: document.querySelector("#todayLabel"),
    clockLabel: document.querySelector("#clockLabel"),
    todayCount: document.querySelector("#todayCount"),
    todayRisk: document.querySelector("#todayRisk"),
    weekCount: document.querySelector("#weekCount"),
    highCount: document.querySelector("#highCount"),
    nextCountdown: document.querySelector("#nextCountdown"),
    nextTitle: document.querySelector("#nextTitle"),
    searchInput: document.querySelector("#searchInput"),
    rangeFilter: document.querySelector("#rangeFilter"),
    regionFilter: document.querySelector("#regionFilter"),
    categoryFilter: document.querySelector("#categoryFilter"),
    highOnly: document.querySelector("#highOnly"),
    agendaViewBtn: document.querySelector("#agendaViewBtn"),
    calendarViewBtn: document.querySelector("#calendarViewBtn"),
    agendaSection: document.querySelector("#agendaSection"),
    calendarSection: document.querySelector("#calendarSection"),
    eventList: document.querySelector("#eventList"),
    eventTemplate: document.querySelector("#eventTemplate"),
    emptyState: document.querySelector("#emptyState"),
    resultCount: document.querySelector("#resultCount"),
    calendarTitle: document.querySelector("#calendarTitle"),
    calendarGrid: document.querySelector("#calendarGrid"),
    prevMonth: document.querySelector("#prevMonth"),
    nextMonth: document.querySelector("#nextMonth"),
    refreshBtn: document.querySelector("#refreshBtn"),
    sourceStatus: document.querySelector("#sourceStatus"),
    eventDialog: document.querySelector("#eventDialog"),
    dialogContent: document.querySelector("#dialogContent"),
    yearLabel: document.querySelector("#yearLabel"),
  };

  const impactMap = {
    high: { label: "高影響", color: "#ff6d7a", weight: 3 },
    medium: { label: "中影響", color: "#ffc866", weight: 2 },
    low: { label: "低影響", color: "#68a8ff", weight: 1 },
  };

  const categoryMap = {
    "central-bank": "央行政策",
    macro: "總經數據",
    earnings: "企業財報",
    tech: "科技活動",
    taiwan: "台股公告",
    policy: "政策／地緣",
  };

  const regionMap = { TW: "台灣", US: "美國", JP: "日本", KR: "韓國", EU: "歐洲", GLOBAL: "全球" };
  const weekday = ["週日", "週一", "週二", "週三", "週四", "週五", "週六"];

  function dateParts(date = new Date()) {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: TZ,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    }).formatToParts(date);
    return Object.fromEntries(parts.map((p) => [p.type, p.value]));
  }

  function dateKey(date = new Date()) {
    const p = dateParts(date);
    return `${p.year}-${p.month}-${p.day}`;
  }

  function eventDateKey(event) {
    return dateKey(new Date(event.start));
  }

  function formatDateTime(value, options = {}) {
    return new Intl.DateTimeFormat("zh-TW", {
      timeZone: TZ,
      month: "numeric",
      day: "numeric",
      weekday: options.weekday ? "short" : undefined,
      hour: options.dateOnly ? undefined : "2-digit",
      minute: options.dateOnly ? undefined : "2-digit",
      hourCycle: "h23",
    }).format(new Date(value));
  }

  function formatUpdated(value) {
    if (!value) return "未知";
    return new Intl.DateTimeFormat("zh-TW", {
      timeZone: TZ,
      month: "numeric",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(new Date(value));
  }

  function taipeiMidnight(date = new Date()) {
    const p = dateParts(date);
    return new Date(`${p.year}-${p.month}-${p.day}T00:00:00+08:00`);
  }

  function startOfEventDay(event) {
    return new Date(`${eventDateKey(event)}T00:00:00+08:00`);
  }

  function daysFromToday(event) {
    return Math.floor((startOfEventDay(event) - taipeiMidnight()) / 86400000);
  }

  function eventTimeLabel(event) {
    if (event.all_day) return "全天／時間待定";
    return new Intl.DateTimeFormat("zh-TW", {
      timeZone: TZ,
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(new Date(event.start));
  }

  function countdownLabel(event, now = new Date()) {
    const target = new Date(event.start);
    const diff = target - now;
    if (event.all_day) {
      const days = daysFromToday(event);
      if (days < 0) return "已結束";
      if (days === 0) return "今天";
      if (days === 1) return "明天";
      return `${days} 天後`;
    }
    if (diff < -3600000) return "已公布";
    if (diff <= 0) return "進行中";
    const days = Math.floor(diff / 86400000);
    const hours = Math.floor((diff % 86400000) / 3600000);
    const mins = Math.floor((diff % 3600000) / 60000);
    if (days > 0) return `${days}天 ${hours}小時`;
    if (hours > 0) return `${hours}小時 ${mins}分`;
    return `${Math.max(1, mins)}分鐘`;
  }

  function safeText(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
    }[char]));
  }

  function showSkeletons() {
    els.eventList.innerHTML = '<div class="skeleton"></div>'.repeat(4);
  }

  async function loadData(force = false) {
    showSkeletons();
    els.refreshBtn.querySelector("svg")?.classList.add("spin");
    try {
      const url = `data/events.json${force ? `?v=${Date.now()}` : ""}`;
      const response = await fetch(url, { cache: force ? "no-store" : "default" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.payload = await response.json();
    } catch (error) {
      console.warn("events.json 讀取失敗，改用內建資料。", error);
      state.payload = window.__MARKET_EVENT_SEED__;
    } finally {
      els.refreshBtn.querySelector("svg")?.classList.remove("spin");
    }

    if (!state.payload || !Array.isArray(state.payload.events)) {
      state.payload = { metadata: {}, sources: [], events: [] };
    }

    state.events = state.payload.events
      .filter((e) => e && e.start && e.title)
      .sort((a, b) => new Date(a.start) - new Date(b.start));

    const firstUpcoming = state.events.find((e) => new Date(e.start) >= new Date());
    if (firstUpcoming) state.calendarDate = new Date(firstUpcoming.start);

    renderAll();
  }

  function updateClock() {
    const now = new Date();
    const p = dateParts(now);
    els.todayLabel.textContent = new Intl.DateTimeFormat("zh-TW", {
      timeZone: TZ,
      year: "numeric",
      month: "long",
      day: "numeric",
      weekday: "long",
    }).format(now);
    els.clockLabel.textContent = `${p.hour}:${p.minute}:${p.second}`;
    updateCountdowns();
  }

  function updateStats() {
    const now = new Date();
    const today = dateKey(now);
    const inDays = (e, days) => {
      const diff = new Date(e.start) - now;
      return diff >= -3600000 && diff <= days * 86400000;
    };
    const todayEvents = state.events.filter((e) => eventDateKey(e) === today);
    const weekEvents = state.events.filter((e) => inDays(e, 7));
    const monthEvents = state.events.filter((e) => inDays(e, 30));
    const highEvents = monthEvents.filter((e) => e.impact === "high");

    els.todayCount.textContent = todayEvents.length;
    const todayHigh = todayEvents.filter((e) => e.impact === "high").length;
    els.todayRisk.textContent = todayHigh ? `${todayHigh} 個高影響事件` : "尚無高風險事件";
    els.weekCount.textContent = weekEvents.length;
    els.highCount.textContent = highEvents.length;

    const upcoming = state.events.filter((e) => new Date(e.start) >= now);
    const next = upcoming.find((e) => e.impact === "high") || upcoming[0];
    if (next) {
      els.nextCountdown.textContent = countdownLabel(next, now);
      els.nextTitle.textContent = next.title;
    } else {
      els.nextCountdown.textContent = "—";
      els.nextTitle.textContent = "目前沒有未來事件";
    }
  }

  function applyFilters() {
    const query = els.searchInput.value.trim().toLocaleLowerCase("zh-TW");
    const range = els.rangeFilter.value;
    const region = els.regionFilter.value;
    const category = els.categoryFilter.value;
    const onlyHigh = els.highOnly.checked;
    const now = new Date();

    state.filtered = state.events.filter((event) => {
      const eventTime = new Date(event.start);
      const withinPastGrace = eventTime >= new Date(now.getTime() - 12 * 3600000);
      const rangeMatch = range === "all" || (withinPastGrace && eventTime <= new Date(now.getTime() + Number(range) * 86400000));
      const regionMatch = region === "all" || event.region === region;
      const categoryMatch = category === "all" || event.category === category;
      const impactMatch = !onlyHigh || event.impact === "high";
      const haystack = [event.title, event.description, event.market_effect, event.region, ...(event.assets || []), ...(event.tags || [])]
        .join(" ")
        .toLocaleLowerCase("zh-TW");
      const searchMatch = !query || haystack.includes(query);
      return rangeMatch && regionMatch && categoryMatch && impactMatch && searchMatch;
    });

    renderAgenda();
    renderCalendar();
  }

  function renderAgenda() {
    els.eventList.innerHTML = "";
    els.resultCount.textContent = `${state.filtered.length} 筆事件`;
    els.emptyState.hidden = state.filtered.length !== 0;
    if (!state.filtered.length) return;

    for (const event of state.filtered) {
      const fragment = els.eventTemplate.content.cloneNode(true);
      const card = fragment.querySelector(".event-card");
      const d = new Date(event.start);
      const local = dateParts(d);
      const impact = impactMap[event.impact] || impactMap.low;

      card.style.setProperty("--impact-color", impact.color);
      fragment.querySelector(".weekday").textContent = new Intl.DateTimeFormat("zh-TW", { timeZone: TZ, weekday: "short" }).format(d);
      fragment.querySelector(".day").textContent = local.day;
      fragment.querySelector(".month").textContent = `${Number(local.month)}月`;
      fragment.querySelector(".impact-pill").textContent = impact.label;
      fragment.querySelector(".category-pill").textContent = categoryMap[event.category] || event.category;
      fragment.querySelector(".region-pill").textContent = regionMap[event.region] || event.region;
      fragment.querySelector(".event-time").textContent = `${eventTimeLabel(event)} 台灣時間`;
      fragment.querySelector(".event-title").textContent = event.title;
      fragment.querySelector(".event-description").textContent = event.description || "等待更多官方資訊。";
      fragment.querySelector(".event-countdown").textContent = countdownLabel(event);

      const tags = fragment.querySelector(".asset-tags");
      for (const asset of (event.assets || []).slice(0, 6)) {
        const tag = document.createElement("span");
        tag.className = "asset-tag";
        tag.textContent = asset;
        tags.appendChild(tag);
      }

      fragment.querySelector(".detail-btn").addEventListener("click", () => openEvent(event));
      card.addEventListener("dblclick", () => openEvent(event));
      els.eventList.appendChild(fragment);
    }
  }

  function renderCalendar() {
    const year = state.calendarDate.getFullYear();
    const month = state.calendarDate.getMonth();
    els.calendarTitle.textContent = `${year} 年 ${month + 1} 月`;
    els.calendarGrid.innerHTML = "";

    const first = new Date(year, month, 1);
    const start = new Date(year, month, 1 - first.getDay());
    const today = dateKey();

    for (let i = 0; i < 42; i += 1) {
      const day = new Date(start);
      day.setDate(start.getDate() + i);
      const key = dateKey(day);
      const cell = document.createElement("div");
      cell.className = "calendar-day";
      if (day.getMonth() !== month) cell.classList.add("outside");
      if (key === today) cell.classList.add("today");

      const head = document.createElement("div");
      head.className = "calendar-date-number";
      head.innerHTML = `<strong>${day.getDate()}</strong>`;
      cell.appendChild(head);

      const events = state.filtered.filter((e) => eventDateKey(e) === key);
      const items = document.createElement("div");
      items.className = "calendar-items";
      for (const event of events.slice(0, 3)) {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "calendar-item";
        item.style.setProperty("--impact-color", (impactMap[event.impact] || impactMap.low).color);
        item.textContent = `${event.all_day ? "" : `${eventTimeLabel(event)} `}${event.title}`;
        item.title = event.title;
        item.addEventListener("click", () => openEvent(event));
        items.appendChild(item);
      }
      if (events.length > 3) {
        const more = document.createElement("span");
        more.className = "calendar-more";
        more.textContent = `+${events.length - 3} 更多`;
        items.appendChild(more);
      }
      cell.appendChild(items);
      els.calendarGrid.appendChild(cell);
    }
  }

  function renderSources() {
    const sources = state.payload.sources || [];
    els.sourceStatus.innerHTML = `
      <div class="source-item">
        <div><strong>TradingView 市場行情</strong><small>依交易所授權提供即時或延遲資料</small></div>
        <span class="source-state"><i></i>嵌入行情</span>
      </div>`;
    if (!sources.length) return;
    for (const source of sources) {
      const item = document.createElement("div");
      item.className = "source-item";
      const stateClass = source.status === "ok" ? "" : source.status === "warning" ? "warn" : "error";
      const label = source.status === "ok" ? "正常" : source.status === "warning" ? "備援資料" : "讀取失敗";
      item.innerHTML = `
        <div><strong>${safeText(source.name)}</strong><small>${safeText(source.last_success ? formatUpdated(source.last_success) : "尚未更新")}</small></div>
        <span class="source-state ${stateClass}"><i></i>${label}</span>`;
      els.sourceStatus.appendChild(item);
    }
  }

  function openEvent(event) {
    const impact = impactMap[event.impact] || impactMap.low;
    const assets = (event.assets || []).map((a) => `<span class="asset-tag">${safeText(a)}</span>`).join("");
    const statusText = event.is_estimated ? "時間尚未完全確認" : "官方時間／已確認";
    els.dialogContent.style.setProperty("--impact-color", impact.color);
    els.dialogContent.innerHTML = `
      <span class="dialog-impact">${impact.label}</span>
      <h2>${safeText(event.title)}</h2>
      <div class="dialog-meta">${safeText(formatDateTime(event.start, { weekday: true }))} · ${safeText(regionMap[event.region] || event.region)} · ${safeText(categoryMap[event.category] || event.category)} · ${statusText}</div>
      <p class="dialog-copy">${safeText(event.description || "等待更多官方資訊。")}</p>
      <div class="dialog-section">
        <h3>可能影響</h3>
        <p class="dialog-copy" style="margin:0">${safeText(event.market_effect || "實際影響仍取決於數據與市場預期的落差。")}</p>
      </div>
      <div class="dialog-section">
        <h3>關聯市場</h3>
        <div class="dialog-assets">${assets || '<span class="asset-tag">廣泛市場</span>'}</div>
      </div>
      ${event.source_url ? `<a class="dialog-source" href="${safeText(event.source_url)}" target="_blank" rel="noreferrer">查看來源：${safeText(event.source_name || "官方頁面")} ↗</a>` : ""}
    `;
    els.eventDialog.showModal();
  }

  function updateCountdowns() {
    document.querySelectorAll(".event-card").forEach((card, index) => {
      const event = state.filtered[index];
      if (event) card.querySelector(".event-countdown").textContent = countdownLabel(event);
    });
    updateStats();
  }

  function renderAll() {
    els.updatedAt.textContent = formatUpdated(state.payload.metadata?.updated_at);
    els.yearLabel.textContent = new Intl.DateTimeFormat("en", { timeZone: TZ, year: "numeric" }).format(new Date());
    updateStats();
    renderSources();
    applyFilters();
    updateClock();
  }

  function switchView(view) {
    state.view = view;
    const agenda = view === "agenda";
    els.agendaSection.hidden = !agenda;
    els.calendarSection.hidden = agenda;
    els.agendaViewBtn.classList.toggle("active", agenda);
    els.calendarViewBtn.classList.toggle("active", !agenda);
    if (!agenda) renderCalendar();
  }

  [els.searchInput, els.rangeFilter, els.regionFilter, els.categoryFilter, els.highOnly]
    .forEach((el) => el.addEventListener(el.tagName === "INPUT" ? "input" : "change", applyFilters));

  els.agendaViewBtn.addEventListener("click", () => switchView("agenda"));
  els.calendarViewBtn.addEventListener("click", () => switchView("calendar"));
  els.prevMonth.addEventListener("click", () => {
    state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() - 1, 1);
    renderCalendar();
  });
  els.nextMonth.addEventListener("click", () => {
    state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() + 1, 1);
    renderCalendar();
  });
  els.refreshBtn.addEventListener("click", () => loadData(true));
  els.eventDialog.addEventListener("click", (event) => {
    const rect = els.eventDialog.getBoundingClientRect();
    const outside = event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom;
    if (outside) els.eventDialog.close();
  });

  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    navigator.serviceWorker.register("service-worker.js").catch(() => {});
  }

  loadData();
  setInterval(updateClock, 1000);
})();
