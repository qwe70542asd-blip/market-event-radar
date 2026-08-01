(() => {
  "use strict";

  const TZ = "Asia/Taipei";
  const PREF_KEY = "market-event-radar-v6";
  const state = {
    payload: { metadata: {}, sources: [], events: [] },
    newsPayload: { metadata: {}, source: {}, items: [] },
    events: [],
    filtered: [],
    focus: "all",
    view: "week",
    calendarDate: new Date(),
    weekOffset: 0,
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const els = {
    updatedAt: $("#updatedAt"), newsUpdatedAt: $("#newsUpdatedAt"), todayLabel: $("#todayLabel"), clockLabel: $("#clockLabel"),
    todayCount: $("#todayCount"), todayRisk: $("#todayRisk"), weekCount: $("#weekCount"), highCount: $("#highCount"),
    nextCountdown: $("#nextCountdown"), nextTitle: $("#nextTitle"), refreshBtn: $("#refreshBtn"),
    focusChips: $$(".focus-chip"), weekSection: $("#weekSection"), weekBoard: $("#weekBoard"),
    weekPrev: $("#weekPrev"), weekToday: $("#weekToday"), weekNext: $("#weekNext"),
    searchInput: $("#searchInput"), rangeFilter: $("#rangeFilter"), regionFilter: $("#regionFilter"),
    categoryFilter: $("#categoryFilter"), highOnly: $("#highOnly"),
    weekViewBtn: $("#weekViewBtn"), calendarViewBtn: $("#calendarViewBtn"), agendaViewBtn: $("#agendaViewBtn"),
    calendarSection: $("#calendarSection"), calendarTitle: $("#calendarTitle"), calendarGrid: $("#calendarGrid"), prevMonth: $("#prevMonth"), nextMonth: $("#nextMonth"),
    agendaSection: $("#agendaSection"), eventList: $("#eventList"), eventTemplate: $("#eventTemplate"), emptyState: $("#emptyState"), resultCount: $("#resultCount"),
    newsGrid: $("#newsGrid"), newsCount: $("#newsCount"), newsEmpty: $("#newsEmpty"), sourceStatus: $("#sourceStatus"), yearLabel: $("#yearLabel"),
    eventPreview: $("#eventPreview"), eventDialog: $("#eventDialog"), dialogContent: $("#dialogContent"),
    commandBtn: $("#commandBtn"), commandDialog: $("#commandDialog"), commandInput: $("#commandInput"), commandResults: $("#commandResults"),
  };

  const impactMap = {
    high: { label: "高影響", color: "#ff6d7a", weight: 3 },
    medium: { label: "中影響", color: "#ffc866", weight: 2 },
    low: { label: "低影響", color: "#68a8ff", weight: 1 },
  };
  const categoryMap = { "central-bank": "央行政策", macro: "總經數據", earnings: "企業財報", tech: "科技活動", taiwan: "台股公告", policy: "政策／地緣" };
  const regionMap = { TW: "台灣", US: "美國", JP: "日本", KR: "韓國", EU: "歐洲", GLOBAL: "全球" };

  function safeText(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  }

  function dateParts(date = new Date()) {
    const parts = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" }).formatToParts(date);
    return Object.fromEntries(parts.map((part) => [part.type, part.value]));
  }
  function dateKey(date = new Date()) { const p = dateParts(date); return `${p.year}-${p.month}-${p.day}`; }
  function eventDateKey(event) { return dateKey(new Date(event.start)); }
  function taipeiMidnight(date = new Date()) { const p = dateParts(date); return new Date(`${p.year}-${p.month}-${p.day}T00:00:00+08:00`); }
  function addDays(date, days) { const next = new Date(date); next.setDate(next.getDate() + days); return next; }
  function formatUpdated(value) {
    if (!value) return "尚未更新";
    return new Intl.DateTimeFormat("zh-TW", { timeZone: TZ, month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(value));
  }
  function formatDateTime(value, includeWeekday = true) {
    return new Intl.DateTimeFormat("zh-TW", { timeZone: TZ, month: "numeric", day: "numeric", weekday: includeWeekday ? "short" : undefined, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(value));
  }
  function eventTimeLabel(event) {
    if (event.all_day) return "全天／時間待定";
    return new Intl.DateTimeFormat("zh-TW", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(new Date(event.start));
  }
  function countdownLabel(event, now = new Date()) {
    const diff = new Date(event.start) - now;
    if (event.all_day) {
      const days = Math.floor((taipeiMidnight(new Date(event.start)) - taipeiMidnight(now)) / 86400000);
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
    if (days) return `${days}天 ${hours}小時`;
    if (hours) return `${hours}小時 ${mins}分`;
    return `${Math.max(1, mins)}分鐘`;
  }

  function loadPreferences() {
    try {
      const pref = JSON.parse(localStorage.getItem(PREF_KEY) || "{}");
      state.focus = pref.focus || "all";
      state.view = ["week", "calendar", "agenda"].includes(pref.view) ? pref.view : "week";
      if (pref.region) els.regionFilter.value = pref.region;
      if (pref.category) els.categoryFilter.value = pref.category;
      if (typeof pref.highOnly === "boolean") els.highOnly.checked = pref.highOnly;
      if (pref.range) els.rangeFilter.value = pref.range;
    } catch (_) { /* ignore corrupt preferences */ }
  }
  function savePreferences() {
    localStorage.setItem(PREF_KEY, JSON.stringify({ focus: state.focus, view: state.view, region: els.regionFilter.value, category: els.categoryFilter.value, highOnly: els.highOnly.checked, range: els.rangeFilter.value }));
  }

  async function fetchJson(url, fallback, force) {
    try {
      const response = await fetch(`${url}${force ? `?v=${Date.now()}` : ""}`, { cache: force ? "no-store" : "default" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn(`${url} 讀取失敗，使用內建備援資料。`, error);
      return fallback;
    }
  }

  async function loadData(force = false) {
    els.refreshBtn.querySelector("svg")?.classList.add("spin");
    els.weekBoard.innerHTML = '<div class="week-loading">正在整理事件與報導…</div>';
    const [eventPayload, newsPayload] = await Promise.all([
      fetchJson("data/events.json", window.__MARKET_EVENT_SEED__ || { events: [] }, force),
      fetchJson("data/news.json", window.__MARKET_NEWS_SEED__ || { items: [] }, force),
    ]);
    state.payload = eventPayload && Array.isArray(eventPayload.events) ? eventPayload : { metadata: {}, sources: [], events: [] };
    state.newsPayload = newsPayload && Array.isArray(newsPayload.items) ? newsPayload : { metadata: {}, source: {}, items: [] };
    state.events = state.payload.events.filter((event) => event?.start && event?.title).sort((a, b) => new Date(a.start) - new Date(b.start));
    const firstUpcoming = state.events.find((event) => new Date(event.start) >= new Date());
    if (firstUpcoming) state.calendarDate = new Date(firstUpcoming.start);
    els.refreshBtn.querySelector("svg")?.classList.remove("spin");
    renderAll();
  }

  function focusMatch(event) {
    if (state.focus === "all") return true;
    const text = [event.title, event.description, event.market_effect, event.region, ...(event.assets || []), ...(event.tags || [])].join(" ").toLowerCase();
    if (state.focus === "taiwan") return event.region === "TW" || /(台股|台積電|tsmc|ai|半導體|伺服器|00631l|費半)/i.test(text);
    if (state.focus === "rates") return event.category === "central-bank" || /(利率|升息|降息|通膨|cpi|pce|ppi|fed|fomc|央行|殖利率|非農)/i.test(text);
    if (state.focus === "earnings") return event.category === "earnings" || /(財報|財測|營收|毛利率|nvidia|amd|meta|microsoft|apple)/i.test(text);
    if (state.focus === "asia") return ["JP", "KR"].includes(event.region) || /(日本|日銀|日圓|韓國|kospi|亞洲)/i.test(text);
    return true;
  }

  function matchesFilters(event, ignoreRange = false) {
    const query = els.searchInput.value.trim().toLocaleLowerCase("zh-TW");
    const eventTime = new Date(event.start);
    const now = new Date();
    const range = els.rangeFilter.value;
    const rangeMatch = ignoreRange || range === "all" || (eventTime >= new Date(now.getTime() - 12 * 3600000) && eventTime <= new Date(now.getTime() + Number(range) * 86400000));
    const regionMatch = els.regionFilter.value === "all" || event.region === els.regionFilter.value;
    const categoryMatch = els.categoryFilter.value === "all" || event.category === els.categoryFilter.value;
    const impactMatch = !els.highOnly.checked || event.impact === "high";
    const haystack = [event.title, event.description, event.market_effect, event.region, ...(event.assets || []), ...(event.tags || [])].join(" ").toLocaleLowerCase("zh-TW");
    return rangeMatch && regionMatch && categoryMatch && impactMatch && focusMatch(event) && (!query || haystack.includes(query));
  }

  function applyFilters() {
    state.filtered = state.events.filter((event) => matchesFilters(event));
    renderWeekBoard();
    renderAgenda();
    renderCalendar();
    renderNews();
    savePreferences();
  }

  function updateStats() {
    const now = new Date();
    const today = dateKey(now);
    const upcoming = state.events.filter((event) => new Date(event.start) >= new Date(now.getTime() - 3600000));
    const todayEvents = state.events.filter((event) => eventDateKey(event) === today);
    const weekEvents = upcoming.filter((event) => new Date(event.start) <= new Date(now.getTime() + 7 * 86400000));
    const highEvents = upcoming.filter((event) => event.impact === "high" && new Date(event.start) <= new Date(now.getTime() + 30 * 86400000));
    const next = upcoming.find((event) => event.impact === "high") || upcoming[0];
    els.todayCount.textContent = todayEvents.length;
    const todayHigh = todayEvents.filter((event) => event.impact === "high").length;
    els.todayRisk.textContent = todayHigh ? `${todayHigh} 個高影響事件` : "尚無高風險事件";
    els.weekCount.textContent = weekEvents.length;
    els.highCount.textContent = highEvents.length;
    els.nextCountdown.textContent = next ? countdownLabel(next, now) : "—";
    els.nextTitle.textContent = next ? next.title : "目前沒有未來事件";
  }

  function showPreview(event, anchor) {
    const impact = impactMap[event.impact] || impactMap.low;
    const reports = newsForEvent(event).slice(0, 2);
    els.eventPreview.style.setProperty("--impact-color", impact.color);
    els.eventPreview.innerHTML = `<div class="preview-top"><span>${impact.label}</span><strong>${safeText(event.title)}</strong></div><p>${safeText(event.market_effect || event.description || "等待更多資訊。")}</p><small>${safeText(formatDateTime(event.start))} · ${safeText(regionMap[event.region] || event.region)}</small>${reports.length ? `<div class="preview-news">${reports.map((item) => `<span>・${safeText(item.title)}</span>`).join("")}</div>` : ""}`;
    els.eventPreview.hidden = false;
    const rect = anchor.getBoundingClientRect();
    const width = Math.min(380, window.innerWidth - 24);
    const left = Math.min(Math.max(12, rect.left), window.innerWidth - width - 12);
    const top = rect.bottom + 8 + 260 > window.innerHeight ? Math.max(12, rect.top - 230) : rect.bottom + 8;
    Object.assign(els.eventPreview.style, { width: `${width}px`, left: `${left}px`, top: `${top}px` });
  }
  function hidePreview() { els.eventPreview.hidden = true; }
  function bindEventInteraction(element, event) {
    element.addEventListener("mouseenter", () => showPreview(event, element));
    element.addEventListener("mouseleave", hidePreview);
    element.addEventListener("focus", () => showPreview(event, element));
    element.addEventListener("blur", hidePreview);
    element.addEventListener("click", () => { hidePreview(); openEvent(event); });
  }

  function renderWeekBoard() {
    els.weekBoard.innerHTML = "";
    const start = addDays(taipeiMidnight(), state.weekOffset * 7);
    const events = state.events.filter((event) => matchesFilters(event, true));
    for (let i = 0; i < 7; i += 1) {
      const day = addDays(start, i);
      const key = dateKey(day);
      const dayEvents = events.filter((event) => eventDateKey(event) === key);
      const column = document.createElement("article");
      column.className = `week-day${key === dateKey() ? " today" : ""}`;
      const label = new Intl.DateTimeFormat("zh-TW", { timeZone: TZ, weekday: "short", month: "numeric", day: "numeric" }).format(day);
      column.innerHTML = `<header><strong>${safeText(label)}</strong><span>${dayEvents.length} 件</span></header><div class="week-event-stack"></div>`;
      const stack = column.querySelector(".week-event-stack");
      if (!dayEvents.length) stack.innerHTML = '<span class="no-event">無重大事件</span>';
      dayEvents.slice(0, 5).forEach((event) => {
        const impact = impactMap[event.impact] || impactMap.low;
        const button = document.createElement("button");
        button.type = "button";
        button.className = "week-event-chip";
        button.style.setProperty("--impact-color", impact.color);
        button.innerHTML = `<span>${event.all_day ? "全天" : eventTimeLabel(event)}</span><strong>${safeText(event.title)}</strong>`;
        bindEventInteraction(button, event);
        stack.appendChild(button);
      });
      if (dayEvents.length > 5) {
        const more = document.createElement("button");
        more.type = "button";
        more.className = "week-more";
        more.textContent = `還有 ${dayEvents.length - 5} 件`;
        more.addEventListener("click", () => { state.calendarDate = day; switchView("calendar"); });
        stack.appendChild(more);
      }
      els.weekBoard.appendChild(column);
    }
  }

  function renderAgenda() {
    els.eventList.innerHTML = "";
    els.resultCount.textContent = `${state.filtered.length} 筆事件`;
    els.emptyState.hidden = state.filtered.length !== 0;
    for (const event of state.filtered) {
      const fragment = els.eventTemplate.content.cloneNode(true);
      const card = fragment.querySelector(".event-card");
      const impact = impactMap[event.impact] || impactMap.low;
      const p = dateParts(new Date(event.start));
      card.style.setProperty("--impact-color", impact.color);
      fragment.querySelector(".weekday").textContent = new Intl.DateTimeFormat("zh-TW", { timeZone: TZ, weekday: "short" }).format(new Date(event.start));
      fragment.querySelector(".day").textContent = p.day;
      fragment.querySelector(".month").textContent = `${Number(p.month)}月`;
      fragment.querySelector(".impact-pill").textContent = impact.label;
      fragment.querySelector(".category-pill").textContent = categoryMap[event.category] || event.category;
      fragment.querySelector(".region-pill").textContent = regionMap[event.region] || event.region;
      fragment.querySelector(".event-time").textContent = `${eventTimeLabel(event)} 台灣時間`;
      fragment.querySelector(".event-title").textContent = event.title;
      fragment.querySelector(".event-description").textContent = event.description || "等待更多官方資訊。";
      fragment.querySelector(".event-countdown").textContent = countdownLabel(event);
      const tags = fragment.querySelector(".asset-tags");
      (event.assets || []).slice(0, 5).forEach((asset) => { const tag = document.createElement("span"); tag.className = "asset-tag"; tag.textContent = asset; tags.appendChild(tag); });
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
    for (let i = 0; i < 42; i += 1) {
      const day = addDays(start, i);
      const key = dateKey(day);
      const dayEvents = state.events.filter((event) => eventDateKey(event) === key && matchesFilters(event, true));
      const cell = document.createElement("div");
      cell.className = `calendar-day${day.getMonth() !== month ? " outside" : ""}${key === dateKey() ? " today" : ""}`;
      cell.innerHTML = `<div class="calendar-date-number"><strong>${day.getDate()}</strong><span>${dayEvents.length || ""}</span></div><div class="calendar-items"></div>`;
      const items = cell.querySelector(".calendar-items");
      dayEvents.slice(0, 4).forEach((event) => {
        const item = document.createElement("button");
        item.type = "button";
        item.className = "calendar-item";
        item.style.setProperty("--impact-color", (impactMap[event.impact] || impactMap.low).color);
        item.textContent = `${event.all_day ? "" : `${eventTimeLabel(event)} `}${event.title}`;
        bindEventInteraction(item, event);
        items.appendChild(item);
      });
      if (dayEvents.length > 4) { const more = document.createElement("span"); more.className = "calendar-more"; more.textContent = `+${dayEvents.length - 4} 更多`; items.appendChild(more); }
      els.calendarGrid.appendChild(cell);
    }
  }

  function newsForEvent(event) {
    const direct = state.newsPayload.items.filter((item) => item.event_id === event.id);
    if (direct.length) return direct;
    const terms = [event.title, ...(event.assets || []).slice(0, 2)].join(" ").toLowerCase();
    return state.newsPayload.items.filter((item) => terms.split(/\s+/).some((term) => term.length > 2 && `${item.title} ${item.event_title || ""}`.toLowerCase().includes(term)));
  }

  function newsFallbackLinks(event) {
    const query = encodeURIComponent(event.title);
    return [
      { title: `Google 新聞：${event.title}`, link: `https://news.google.com/search?q=${query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant`, source: "Google 新聞搜尋" },
      { title: `Reuters 搜尋：${event.title}`, link: `https://www.reuters.com/site-search/?query=${query}`, source: "Reuters 搜尋" },
    ];
  }

  function renderNews() {
    const relatedIds = new Set(state.events.filter((event) => matchesFilters(event, true) && new Date(event.start) >= new Date(Date.now() - 86400000) && new Date(event.start) <= new Date(Date.now() + 30 * 86400000)).map((event) => event.id));
    let items = state.newsPayload.items.filter((item) => relatedIds.has(item.event_id));
    if (!items.length) items = state.newsPayload.items;
    const unique = [];
    const seen = new Set();
    for (const item of items) { if (!item?.title || !item?.link || seen.has(item.link)) continue; seen.add(item.link); unique.push(item); if (unique.length >= 8) break; }
    let displayItems = unique;
    if (!displayItems.length) {
      const upcoming = state.events
        .filter((event) => new Date(event.start) >= new Date() && focusMatch(event))
        .sort((a, b) => (impactMap[b.impact]?.weight || 0) - (impactMap[a.impact]?.weight || 0) || new Date(a.start) - new Date(b.start))
        .slice(0, 4);
      displayItems = upcoming.map((event) => ({ ...newsFallbackLinks(event)[0], event_title: event.title, is_fallback: true }));
    }
    els.newsGrid.innerHTML = "";
    els.newsCount.textContent = unique.length ? `${unique.length} 則報導` : `${displayItems.length} 個新聞搜尋入口`;
    els.newsEmpty.hidden = displayItems.length !== 0;
    displayItems.forEach((item) => {
      const card = document.createElement("a");
      card.className = `news-card${item.is_fallback ? " fallback-news" : ""}`;
      card.href = item.link;
      card.target = "_blank";
      card.rel = "noreferrer";
      card.innerHTML = `<div class="news-meta"><span>${safeText(item.source || "公開新聞")}</span><time>${safeText(item.published_at ? formatUpdated(item.published_at) : item.is_fallback ? "即時搜尋" : "")}</time></div><h3>${safeText(item.title)}</h3><p>${safeText(item.event_title || "市場相關報導")}</p>`;
      els.newsGrid.appendChild(card);
    });
  }

  function openEvent(event) {
    const impact = impactMap[event.impact] || impactMap.low;
    const reports = newsForEvent(event).slice(0, 4);
    const links = reports.length ? reports : newsFallbackLinks(event);
    const reportHtml = links.map((item) => `<a class="report-link" href="${safeText(item.link)}" target="_blank" rel="noreferrer"><span>${safeText(item.source || "相關報導")}</span><strong>${safeText(item.title)}</strong></a>`).join("");
    const assets = (event.assets || []).map((asset) => `<span class="asset-tag">${safeText(asset)}</span>`).join("");
    els.dialogContent.style.setProperty("--impact-color", impact.color);
    els.dialogContent.innerHTML = `<span class="dialog-impact">${impact.label}</span><h2>${safeText(event.title)}</h2><div class="dialog-meta">${safeText(formatDateTime(event.start))} · ${safeText(regionMap[event.region] || event.region)} · ${safeText(categoryMap[event.category] || event.category)} · ${event.is_estimated ? "時間待確認" : "官方時間／已確認"}</div><p class="dialog-copy">${safeText(event.description || "等待更多官方資訊。")}</p><div class="dialog-section"><h3>為什麼重要</h3><p class="dialog-copy compact-copy">${safeText(event.market_effect || "實際影響仍取決於公布值與市場預期的落差。")}</p></div><div class="dialog-section"><h3>關聯市場</h3><div class="dialog-assets">${assets || '<span class="asset-tag">廣泛市場</span>'}</div></div><div class="dialog-section"><h3>相關報導</h3><div class="report-list">${reportHtml}</div></div><div class="dialog-actions">${event.source_url ? `<a class="dialog-source" href="${safeText(event.source_url)}" target="_blank" rel="noreferrer">官方來源：${safeText(event.source_name || "查看公告")} ↗</a>` : ""}</div>`;
    els.eventDialog.showModal();
  }

  function renderSources() {
    els.sourceStatus.innerHTML = "";
    const rows = [
      { name: "TradingView 市場代理跑馬燈", status: "ok", last_success: null, message: "ETF／ADR／匯率／風險指標" },
      { name: state.newsPayload.source?.name || "公開新聞 RSS", status: state.newsPayload.source?.status || "warning", last_success: state.newsPayload.metadata?.updated_at, message: state.newsPayload.source?.message || "等待首次排程" },
      ...(state.payload.sources || []),
    ];
    rows.forEach((source) => {
      const item = document.createElement("div");
      item.className = "source-item";
      const status = source.status || "warning";
      const label = status === "ok" ? "正常" : status === "warning" ? "使用備援" : "需檢查";
      item.innerHTML = `<div><strong>${safeText(source.name)}</strong><small>${safeText(source.last_success ? formatUpdated(source.last_success) : source.message || "公開嵌入")}</small></div><span class="source-state ${status === "warning" ? "warn" : status === "error" ? "error" : ""}"><i></i>${label}</span>`;
      els.sourceStatus.appendChild(item);
    });
  }

  function switchView(view) {
    state.view = view;
    els.weekSection.hidden = view !== "week";
    els.calendarSection.hidden = view !== "calendar";
    els.agendaSection.hidden = view !== "agenda";
    els.weekViewBtn.classList.toggle("active", view === "week");
    els.calendarViewBtn.classList.toggle("active", view === "calendar");
    els.agendaViewBtn.classList.toggle("active", view === "agenda");
    if (view === "week") renderWeekBoard();
    if (view === "calendar") renderCalendar();
    if (view === "agenda") renderAgenda();
    savePreferences();
  }

  function renderCommandResults(query = "") {
    const q = query.trim().toLowerCase();
    const actions = [
      { label: "切換到週曆", hint: "W", run: () => switchView("week") },
      { label: "切換到月曆", hint: "M", run: () => switchView("calendar") },
      { label: "切換到完整清單", hint: "L", run: () => switchView("agenda") },
      { label: els.highOnly.checked ? "取消只看高影響" : "只看高影響事件", hint: "H", run: () => { els.highOnly.checked = !els.highOnly.checked; applyFilters(); } },
    ].filter((action) => !q || action.label.toLowerCase().includes(q));
    const events = state.events.filter((event) => !q || [event.title, ...(event.assets || [])].join(" ").toLowerCase().includes(q)).slice(0, 7);
    els.commandResults.innerHTML = "";
    actions.forEach((action) => {
      const button = document.createElement("button"); button.type = "button"; button.className = "command-result"; button.innerHTML = `<span>${safeText(action.label)}</span><kbd>${action.hint}</kbd>`; button.addEventListener("click", () => { action.run(); els.commandDialog.close(); }); els.commandResults.appendChild(button);
    });
    events.forEach((event) => {
      const button = document.createElement("button"); button.type = "button"; button.className = "command-result event-command"; button.innerHTML = `<span><strong>${safeText(event.title)}</strong><small>${safeText(formatDateTime(event.start))}</small></span><em>${safeText(impactMap[event.impact]?.label || "事件")}</em>`; button.addEventListener("click", () => { els.commandDialog.close(); openEvent(event); }); els.commandResults.appendChild(button);
    });
    if (!actions.length && !events.length) els.commandResults.innerHTML = '<div class="command-empty">找不到相符內容</div>';
  }

  function openCommand() { renderCommandResults(""); els.commandDialog.showModal(); requestAnimationFrame(() => els.commandInput.focus()); }

  function updateClock() {
    const now = new Date(); const p = dateParts(now);
    els.todayLabel.textContent = new Intl.DateTimeFormat("zh-TW", { timeZone: TZ, year: "numeric", month: "long", day: "numeric", weekday: "long" }).format(now);
    els.clockLabel.textContent = `${p.hour}:${p.minute}:${p.second}`;
    updateStats();
    $$(".event-countdown").forEach((node, index) => { const event = state.filtered[index]; if (event) node.textContent = countdownLabel(event, now); });
  }

  function renderAll() {
    els.updatedAt.textContent = formatUpdated(state.payload.metadata?.updated_at);
    els.newsUpdatedAt.textContent = formatUpdated(state.newsPayload.metadata?.updated_at);
    els.yearLabel.textContent = new Intl.DateTimeFormat("en", { timeZone: TZ, year: "numeric" }).format(new Date());
    els.focusChips.forEach((chip) => chip.classList.toggle("active", chip.dataset.focus === state.focus));
    updateStats();
    renderSources();
    applyFilters();
    switchView(state.view);
    updateClock();
  }

  loadPreferences();
  els.focusChips.forEach((chip) => chip.addEventListener("click", () => { state.focus = chip.dataset.focus; els.focusChips.forEach((item) => item.classList.toggle("active", item === chip)); applyFilters(); }));
  [els.searchInput, els.rangeFilter, els.regionFilter, els.categoryFilter, els.highOnly].forEach((element) => element.addEventListener(element.tagName === "INPUT" ? "input" : "change", applyFilters));
  els.weekPrev.addEventListener("click", () => { state.weekOffset -= 1; renderWeekBoard(); });
  els.weekToday.addEventListener("click", () => { state.weekOffset = 0; renderWeekBoard(); });
  els.weekNext.addEventListener("click", () => { state.weekOffset += 1; renderWeekBoard(); });
  els.weekViewBtn.addEventListener("click", () => switchView("week"));
  els.calendarViewBtn.addEventListener("click", () => switchView("calendar"));
  els.agendaViewBtn.addEventListener("click", () => switchView("agenda"));
  els.prevMonth.addEventListener("click", () => { state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() - 1, 1); renderCalendar(); });
  els.nextMonth.addEventListener("click", () => { state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() + 1, 1); renderCalendar(); });
  els.refreshBtn.addEventListener("click", () => loadData(true));
  els.commandBtn.addEventListener("click", openCommand);
  els.commandInput.addEventListener("input", () => renderCommandResults(els.commandInput.value));
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); openCommand(); }
    if (event.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) { event.preventDefault(); els.searchInput.focus(); }
  });
  els.eventDialog.addEventListener("click", (event) => { const rect = els.eventDialog.getBoundingClientRect(); if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) els.eventDialog.close(); });
  els.commandDialog.addEventListener("close", () => { els.commandInput.value = ""; });

  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) navigator.serviceWorker.register("service-worker.js").catch(() => {});
  loadData();
  setInterval(updateClock, 1000);
})();
