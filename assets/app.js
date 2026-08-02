(() => {
  "use strict";

  const PREF_KEY = "market-event-radar-v11-0-0";
  const LEGACY_PREF_KEY = "market-event-radar-v10-6-0";
  const state = {
    payload: { metadata: {}, sources: [], events: [] },
    newsPayload: { metadata: {}, source: {}, items: [] },
    events: [],
    filtered: [],
    calendarFiltered: [],
    dayDialogEvents: [],
    dayDialogGroup: "all",
    focus: "all",
    calendarDate: new Date(),
  };

  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const DAY_NAMES = ["日", "一", "二", "三", "四", "五", "六"];
  const REGION_MAP = { TW: "台灣", US: "美國", JP: "日本", KR: "韓國", EU: "歐洲", GLOBAL: "全球" };
  const CATEGORY_MAP = {
    "central-bank":"央行政策", macro:"總經數據", policy:"政策／地緣",
    earnings:"企業財報", "monthly-revenue":"月營收", "report-deadline":"財報期限",
    "ex-dividend":"除權息", "dividend-decision":"股利方案", "dividend-payment":"股利發放",
    "etf-distribution":"ETF 配息", "investor-conference":"法人說明會",
    "shareholder-meeting":"股東會", "corporate-action":"公司行動",
    breaking:"突發事件", tech:"產業活動", taiwan:"台股公告"
  };
  const IMPACT_MAP = { high: "高影響", medium: "中影響", low: "低影響" };
  const GROUP_MAP = { all:"全部", breaking:"突發事件", macro:"總經／央行", earnings:"財報／營收", dividend:"股利／除權息", corporate:"法說／公司行動" };
  const CATEGORY_GROUP = {
    "central-bank":"macro", macro:"macro", policy:"macro",
    earnings:"earnings", "monthly-revenue":"earnings", "report-deadline":"earnings",
    "ex-dividend":"dividend", "dividend-decision":"dividend", "dividend-payment":"dividend", "etf-distribution":"dividend",
    "investor-conference":"corporate", "shareholder-meeting":"corporate", "corporate-action":"corporate", taiwan:"corporate", tech:"corporate",
    breaking:"breaking"
  };

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
    try {
      const current=localStorage.getItem(PREF_KEY);
      const legacy=localStorage.getItem(LEGACY_PREF_KEY);
      return JSON.parse(current||legacy||"{}");
    }
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
    if (window.MarketDataSource?.loadJson) {
      return window.MarketDataSource.loadJson(path, fallback);
    }
    try {
      const response = await fetch(`${path}${path.includes("?") ? "&" : "?"}t=${Date.now()}`, { cache: "no-store" });
      if (!response.ok) throw new Error(path);
      return response.json();
    } catch {
      return fallback;
    }
  }


  const BREAKING_TERMS = [
    "戰爭","戰火","空襲","飛彈","導彈","攻擊","衝突","停火","軍事","中東","伊朗","以色列",
    "荷姆茲","紅海","制裁","關稅","封鎖","爆炸","政變","緊急狀態","市場暫停","交易中斷",
    "地震","海嘯","颱風","洪水","斷電","供應中斷","war","airstrike","missile","attack",
    "conflict","ceasefire","sanction","tariff","blockade","earthquake","tsunami","market halt"
  ];
  const HIGH_BREAKING_TERMS = [
    "戰爭","戰火","空襲","飛彈","攻擊","中東","伊朗","以色列","荷姆茲","市場暫停","交易中斷",
    "war","airstrike","missile","attack","market halt"
  ];

  function safeNewsHref(item) {
    const value = window.MarketNewsLink?.safeLink?.(item) || item?.direct_link || item?.link || "";
    try {
      const url = new URL(value, location.href);
      if (["http:","https:"].includes(url.protocol) && !/(^|\.)google\./i.test(url.hostname) && url.hostname !== "news.google.com") return url.href;
    } catch {}
    return "";
  }

  function breakingNewsToEvents(payload) {
    const now = Date.now();
    const seen = new Set();
    return (payload?.items || [])
      .filter(item => Boolean(safeNewsHref(item)))
      .filter(item => {
        const published = new Date(item.published_at || 0).getTime();
        if (!Number.isFinite(published) || now - published > 96 * 3600000 || published > now + 3600000) return false;
        const hay = `${item.title || ""} ${item.summary || ""}`.toLowerCase();
        const strong = BREAKING_TERMS.some(term => hay.includes(term.toLowerCase()));
        return strong && (item.is_breaking || ["policy","macro","market"].includes(item.topic) || item.source_group === "official-global");
      })
      .filter(item => {
        const key = String(item.title || "").normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}]+/gu,"");
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 16)
      .map(item => {
        const hay = `${item.title || ""} ${item.summary || ""}`.toLowerCase();
        const high = HIGH_BREAKING_TERMS.some(term => hay.includes(term.toLowerCase()));
        const published = new Date(item.published_at);
        return {
          id: `breaking-${item.id || Math.abs([...String(item.title || "")].reduce((acc,ch)=>((acc<<5)-acc)+ch.charCodeAt(0),0))}`,
          title: `突發｜${item.title}`,
          start: published.toISOString(),
          category: "policy",
          event_group: "breaking",
          event_type: "breaking-news",
          region: item.region || "GLOBAL",
          impact: high ? "high" : "medium",
          description: item.summary || "突發市場消息，請開啟原始來源確認最新進展。",
          market_effect: "突發地緣政治、政策或供應中斷消息可能快速影響原油、黃金、匯率、航運與全球股票風險偏好。",
          source_name: item.source || "新聞來源",
          source_url: safeNewsHref(item),
          external_href: safeNewsHref(item),
          origin: "breaking-news",
          all_day: false,
          is_breaking_news: true,
          assets: item.industries || [],
          tags: ["突發事件", item.topic || "market"],
          published_at: item.published_at
        };
      });
  }

  function normalizeEvent(raw) {
    const startDate = new Date(raw.start);
    const group = raw.event_group || CATEGORY_GROUP[raw.category] || "corporate";
    const searchBlob = [
      raw.title, raw.description, raw.market_effect, raw.region, raw.category,
      raw.symbol, raw.asset_name, raw.market, raw.event_type,
      ...(raw.assets || []), ...(raw.tags || [])
    ].join(" ").toLowerCase();
    return {
      ...raw, group, startDate,
      dayKey: `${startDate.getFullYear()}-${pad(startDate.getMonth() + 1)}-${pad(startDate.getDate())}`,
      searchBlob, timestamp: startDate.getTime()
    };
  }

  function focusMatch(event, focus) {
    if (focus === "all") return true;
    const hay = `${event.title} ${event.description} ${event.market_effect || ""} ${(event.assets || []).join(" ")} ${(event.tags || []).join(" ")}`;
    if (focus === "taiwan") return event.region === "TW" || /台股|台灣|新台幣|上市|上櫃|櫃買/i.test(hay);
    if (focus === "finance") return /金融|金控|銀行|保險|證券|利差|房貸|信用卡/i.test(hay);
    if (focus === "traditional") return /鋼鐵|水泥|塑化|化工|機械|工具機|紡織|原物料|造紙|重電|營建/i.test(hay);
    if (focus === "shipping") return /航運|海運|貨櫃|散裝|運價|SCFI|航空|物流|港口/i.test(hay);
    if (focus === "technology") return /科技|AI|半導體|晶片|伺服器|電子|軟體|雲端|記憶體|面板/i.test(hay);
    if (focus === "consumer-health") return /消費|零售|百貨|餐飲|食品|生技|製藥|醫療|觀光|飯店/i.test(hay);
    if (focus === "rates") return ["central-bank", "macro"].includes(event.category) || /CPI|PPI|PMI|通膨|利率|聯準會|日銀|ECB|央行|非農|GDP/i.test(hay);
    if (focus === "earnings") return event.category === "earnings" || /財報|營收|法說|股東會|業績|財測/i.test(hay);
    if (focus === "asia") return ["TW", "JP", "KR"].includes(event.region) || /日本|韓國|台灣|日銀|韓國銀行/i.test(hay);
    return true;
  }

  function baseFilter(event, { includeRange = true, includePast = true } = {}) {
    const search = slug($("#searchInput")?.value.trim() || "");
    const region = $("#regionFilter")?.value || "all";
    const category = $("#categoryFilter")?.value || "all";
    const range = $("#rangeFilter")?.value || "30";
    const highOnly = $("#highOnly")?.checked || false;
    const now = new Date();

    if (!includePast && event.timestamp < now.getTime() - 24 * 3600000) return false;
    if (includeRange && range !== "all" && event.timestamp > now.getTime() + Number(range) * 86400000) return false;
    if (region !== "all" && event.region !== region) return false;
    if (category !== "all" && event.category !== category && event.group !== category) return false;
    if (highOnly && event.impact !== "high") return false;
    if (search && !event.searchBlob.includes(search)) return false;
    if (!focusMatch(event, state.focus)) return false;
    return true;
  }

  function applyFilters() {
    state.filtered = state.events
      .filter(event => baseFilter(event, { includeRange: true, includePast: false }))
      .sort((a, b) => a.timestamp - b.timestamp);

    // Month view must not disappear merely because an event is yesterday or
    // outside the "next 30 days" agenda range.
    state.calendarFiltered = state.events
      .filter(event => baseFilter(event, { includeRange: false, includePast: true }))
      .sort((a, b) => a.timestamp - b.timestamp);

    renderStats();
    renderMonthSummary();
    renderCalendar();
    renderAgenda();
    savePrefs();
  }


  let portfolioSymbolCache = null;
  function portfolioSymbols() {
    if (portfolioSymbolCache) return portfolioSymbolCache;
    try {
      const rows = JSON.parse(localStorage.getItem("market-radar-portfolio-v10-3") || "[]");
      portfolioSymbolCache = new Set((Array.isArray(rows) ? rows : []).flatMap(row => [
        String(row.symbol || "").toUpperCase(),
        String(row.asset_id || "").split(":").pop().toUpperCase()
      ]).filter(Boolean));
      return portfolioSymbolCache;
    } catch {
      portfolioSymbolCache = new Set();
      return portfolioSymbolCache;
    }
  }

  function eventPriority(event) {
    const owned = portfolioSymbols().has(String(event.symbol || "").toUpperCase()) ? 1000 : 0;
    const impact = { high:300, medium:160, low:40 }[event.impact] || 0;
    const type = {
      breaking:420, earnings:180, "monthly-revenue":150, "report-deadline":150,
      "etf-distribution":145, "ex-dividend":135, "dividend-decision":125,
      "investor-conference":110, "corporate-action":100, "dividend-payment":60
    }[event.category] || 80;
    return owned + impact + type;
  }

  function eventGroup(event) {
    return event.group || CATEGORY_GROUP[event.category] || "corporate";
  }

  function eventTypeShort(event) {
    if (eventGroup(event) === "breaking") return "突發";
    return {
      breaking:"突發", macro:"數據", "central-bank":"央行", policy:"政策",
      earnings:"財報", "monthly-revenue":"營收", "report-deadline":"期限",
      "ex-dividend":"除息", "etf-distribution":"ETF", "dividend-decision":"股利",
      "dividend-payment":"入帳", "investor-conference":"法說",
      "shareholder-meeting":"股東會", "corporate-action":"公司"
    }[event.category] || "事件";
  }

  function formatAmount(event) {
    if (event.cash_dividend !== undefined && event.cash_dividend !== null && event.cash_dividend !== "") {
      const amount = Number(event.cash_dividend);
      if (Number.isFinite(amount) && amount !== 0) return `${amount.toLocaleString("zh-TW",{maximumFractionDigits:6})} ${event.currency === "USD" ? "美元" : "元"}`;
    }
    return "";
  }

  function monthEvents() {
    const y = state.calendarDate.getFullYear();
    const m = state.calendarDate.getMonth();
    return state.calendarFiltered.filter(event => event.startDate.getFullYear() === y && event.startDate.getMonth() === m);
  }

  function renderMonthSummary() {
    const root = $("#monthEventSummary");
    if (!root) return;
    const rows = monthEvents();
    const groups = ["all","breaking","macro","earnings","dividend","corporate"];
    const counts = Object.fromEntries(groups.map(group => [
      group,
      group === "all" ? rows.length : rows.filter(event => eventGroup(event) === group).length
    ]));
    root.innerHTML = [
      ["all","本月全部",counts.all],
      ["breaking","突發事件",counts.breaking],
      ["macro","總經／央行",counts.macro],
      ["earnings","財報／營收",counts.earnings],
      ["dividend","股利／除權息",counts.dividend],
      ["corporate","法說／公司行動",counts.corporate]
    ].map(([group,label,count]) => `<button type="button" class="summary-${group}" data-summary-group="${group}"><span>${label}</span><strong>${count}</strong></button>`).join("");
    $$("[data-summary-group]", root).forEach(button => button.addEventListener("click", () => {
      const group = button.dataset.summaryGroup;
      const select = $("#categoryFilter");
      if (select) select.value = group === "all" ? "all" : group;
      applyFilters();
      $("#calendarSection")?.scrollIntoView({ behavior:"smooth", block:"start" });
    }));
  }

  function renderStats() {
    const now = new Date();
    const todayKey = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
    const todayEvents = state.calendarFiltered.filter(event => event.dayKey === todayKey);
    const weekEvents = state.filtered.filter(event => event.timestamp <= now.getTime() + 7 * 86400000);
    const highEvents = state.filtered.filter(event => event.impact === "high" && event.timestamp <= now.getTime() + 30 * 86400000);
    const nextHigh = state.events
      .filter(event => event.impact === "high" && event.timestamp >= now.getTime())
      .sort((a,b) => a.timestamp - b.timestamp)[0];

    const setText = (selector, value) => { const node = $(selector); if (node) node.textContent = String(value ?? ""); };
    setText("#todayCount", todayEvents.length);
    setText("#todayRisk", todayEvents.some(event => event.impact === "high") ? "今天有高影響事件" : (todayEvents.length ? `今天另有 ${todayEvents.length} 件事件` : "今天暫無事件"));
    setText("#weekCount", weekEvents.length);
    setText("#highCount", highEvents.length);
    setText("#nextTitle", nextHigh ? nextHigh.title : "近期沒有高影響事件");
    const nextLink = $("#nextEventLink");
    if (nextLink) nextLink.href = nextHigh ? `event.html?id=${encodeURIComponent(nextHigh.id)}` : "#calendarSection";
    setText("#nextCountdown", nextHigh ? formatRelative(nextHigh.timestamp - now.getTime()) : "—");
    setText("#marketHintValue", highEvents.length >= 5 ? "高波動" : highEvents.length >= 2 ? "偏熱" : "穩定");
    setText("#marketHintText", highEvents.length >= 5 ? "高影響事件偏多" : highEvents.length >= 2 ? "未來 30 天有多個催化" : "本週事件壓力偏低");
    setText("#updatedAt", state.payload.metadata.updated_at ? formatDateTime(state.payload.metadata.updated_at) : "—");
    setText("#newsUpdatedAt", state.newsPayload.metadata.updated_at ? formatDateTime(state.newsPayload.metadata.updated_at) : "尚未更新");

    const health = $("#calendarDataState");
    if (health) {
      const offline = state.payload.metadata.generation_mode === "offline";
      health.textContent = offline ? "目前顯示安裝包資料；執行資料更新 Action 後會補入完整公司事件。" : `已同步 ${state.payload.metadata.event_count || state.events.length} 件事件`;
      health.classList.toggle("warning", offline);
    }
  }

  function eventChip(event) {
    const link = document.createElement("a");
    link.href = `event.html?id=${encodeURIComponent(event.id)}`;
    link.className = `calendar-event-chip impact-${event.impact} group-${eventGroup(event)}`;
    const symbol = event.symbol ? `<b>${escapeHtml(event.symbol)}</b>` : "";
    const displayTitle = event.symbol
      ? String(event.title || "").replace(new RegExp(`^${String(event.symbol).replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}\\s*`,"i"), "")
      : event.title;
    link.innerHTML = `
      <span>${escapeHtml(event.all_day ? "全天" : `${pad(event.startDate.getHours())}:${pad(event.startDate.getMinutes())}`)}</span>
      <i>${eventTypeShort(event)}</i>
      <strong>${symbol}${escapeHtml(displayTitle)}</strong>`;
    link.title = `${event.title}\n${event.description || event.market_effect || ""}`;
    link.addEventListener("mouseenter", ev => showPreview(ev.currentTarget, event));
    link.addEventListener("focus", ev => showPreview(ev.currentTarget, event));
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

  function renderDayDialogList() {
    const list = $("#dayEventsList");
    const counts = $("#dayEventsCounts");
    if (!list) return;
    const filtered = state.dayDialogGroup === "all"
      ? state.dayDialogEvents
      : state.dayDialogEvents.filter(event => eventGroup(event) === state.dayDialogGroup);

    if (counts) {
      const groups = ["all","breaking","macro","earnings","dividend","corporate"];
      counts.innerHTML = groups.map(group => {
        const count = group === "all"
          ? state.dayDialogEvents.length
          : state.dayDialogEvents.filter(event => eventGroup(event) === group).length;
        return `<button type="button" class="${state.dayDialogGroup === group ? "active" : ""}" data-day-group="${group}">${GROUP_MAP[group]} <b>${count}</b></button>`;
      }).join("");
      $$("[data-day-group]", counts).forEach(button => button.addEventListener("click", () => {
        state.dayDialogGroup = button.dataset.dayGroup;
        renderDayDialogList();
      }));
    }

    if (!filtered.length) {
      list.innerHTML = '<div class="day-events-empty">這個分類沒有事件。</div>';
      return;
    }

    list.innerHTML = filtered
      .sort((a,b) => b.priority - a.priority || a.timestamp - b.timestamp)
      .map(event => {
        const amount = formatAmount(event);
        const href = event.external_href || `event.html?id=${encodeURIComponent(event.id)}`;
        const target = event.external_href ? ' target="_blank" rel="noreferrer noopener"' : "";
        return `
          <a class="day-event-row impact-${event.impact} group-${eventGroup(event)}" href="${escapeHtml(href)}"${target}>
            <div class="day-event-time"><span>${event.all_day ? "全天" : `${pad(event.startDate.getHours())}:${pad(event.startDate.getMinutes())}`}</span><b>${eventTypeShort(event)}</b></div>
            <div>
              <strong>${escapeHtml(event.title)}</strong>
              <small>${REGION_MAP[event.region] || event.region} · ${CATEGORY_MAP[event.category] || event.category}${amount ? ` · ${escapeHtml(amount)}` : ""}${event.is_active_etf ? " · 主動型 ETF" : ""}${event.source_name ? ` · ${escapeHtml(event.source_name)}` : ""}</small>
              <p>${escapeHtml(event.description || "")}</p>
            </div>
            <span>›</span>
          </a>`;
      }).join("");
  }

  function openDayEvents(day, events, initialGroup = "all") {
    const dialog = $("#dayEventsDialog");
    const title = $("#dayEventsTitle");
    if (!dialog || !title) return;
    state.dayDialogEvents = events.map(event => ({ ...event, priority:eventPriority(event) }));
    state.dayDialogGroup = initialGroup;
    title.textContent = `${day.getMonth() + 1} 月 ${day.getDate()} 日（週${DAY_NAMES[day.getDay()]}）`;
    renderDayDialogList();
    if (!dialog.open) dialog.showModal();
  }

  function renderCalendar() {
    const grid = $("#calendarGrid");
    if (!grid) return;
    grid.innerHTML = "";
    const baseDate = state.calendarDate;
    $("#calendarTitle").textContent = `${baseDate.getFullYear()} 年 ${baseDate.getMonth() + 1} 月`;

    const eventMap = new Map();
    state.calendarFiltered.forEach(event => {
      if (!eventMap.has(event.dayKey)) eventMap.set(event.dayKey, []);
      eventMap.get(event.dayKey).push(event);
    });

    const days = getMonthMatrix(baseDate);
    const today = new Date();
    const todayKey = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
    const groupOrder = ["breaking","macro","earnings","dividend","corporate"];
    const shortLabels = { breaking:"突發", macro:"總經", earnings:"財報", dividend:"股利", corporate:"公司" };

    days.forEach(day => {
      const key = `${day.getFullYear()}-${pad(day.getMonth() + 1)}-${pad(day.getDate())}`;
      const cellEvents = (eventMap.get(key) || [])
        .map(event => ({ ...event, priority:eventPriority(event) }))
        .sort((a,b) => b.priority - a.priority || a.timestamp - b.timestamp);

      const cell = document.createElement("article");
      cell.className = "calendar-day compact-dot-day";
      if (day.getMonth() !== baseDate.getMonth()) cell.classList.add("muted");
      if (key === todayKey) cell.classList.add("today");

      const groupRows = groupOrder.map(group => ({
        group,
        count: cellEvents.filter(event => eventGroup(event) === group).length
      })).filter(row => row.count);

      cell.innerHTML = `
        <button type="button" class="calendar-day-open" aria-label="${day.getMonth()+1}月${day.getDate()}日，${cellEvents.length}件事件">
          <span class="calendar-date-number">${day.getDate()}</span>
          <span class="calendar-total-count">${cellEvents.length ? `${cellEvents.length} 件` : ""}</span>
        </button>
        <div class="calendar-dot-summary">
          ${groupRows.map(row => `
            <button type="button" class="calendar-dot-row group-${row.group}" data-group="${row.group}">
              <i></i><span>${shortLabels[row.group]}</span><b>${row.count}</b>
            </button>`).join("")}
        </div>`;

      cell.querySelector(".calendar-day-open")?.addEventListener("click", () => openDayEvents(day, cellEvents, "all"));
      cell.querySelectorAll("[data-group]").forEach(button => button.addEventListener("click", event => {
        event.stopPropagation();
        openDayEvents(day, cellEvents, button.dataset.group);
      }));
      grid.appendChild(cell);
    });

    renderMonthSummary();
  }

  function renderAgenda() {
    const list = $("#eventList");
    if (!list) return;
    const owned = portfolioSymbols();
    const upcoming = state.filtered
      .map(event => ({ ...event, priority:eventPriority(event) }))
      .filter(event => eventGroup(event) === "breaking" || event.impact === "high" || owned.has(String(event.symbol || "").toUpperCase()))
      .sort((a,b) => b.priority - a.priority || a.timestamp - b.timestamp)
      .slice(0,4);

    $("#resultCount").textContent = `${upcoming.length} 筆`;
    $("#emptyState").hidden = !!upcoming.length;
    list.innerHTML = upcoming.map(event => {
      const href = event.external_href || `event.html?id=${encodeURIComponent(event.id)}`;
      const target = event.external_href ? ' target="_blank" rel="noreferrer noopener"' : "";
      return `<a class="agenda-mini-row impact-${event.impact} group-${eventGroup(event)}" href="${escapeHtml(href)}"${target}>
        <time>${formatDate(event.startDate)}${event.all_day ? "" : ` ${pad(event.startDate.getHours())}:${pad(event.startDate.getMinutes())}`}</time>
        <div><strong>${escapeHtml(event.title)}</strong><small>${escapeHtml(event.source_name || CATEGORY_MAP[event.category] || event.category)} · ${IMPACT_MAP[event.impact]}</small></div>
        <span>›</span>
      </a>`;
    }).join("");
  }

  function renderSources() {
    const eventSources = (state.payload.sources || []).map(source => ({...source, kind:"事件"}));
    const newsSources = (state.newsPayload.sources || []).map(source => ({...source, kind:"新聞"}));
    const sources = [...eventSources, ...newsSources];
    const unique = [];
    const seen = new Set();
    for (const source of sources) {
      const key = source.name || source.source || "";
      if (!key || seen.has(key)) continue;
      seen.add(key); unique.push(source);
    }
    const normal = unique.filter(source => source.status === "ok").length;
    const warning = unique.length - normal;
    const count = $("#sourceCount");
    if (count) count.textContent = `${unique.length} 個來源`;
    const summary = $("#sourceHealthSummary");
    if (summary) summary.textContent = `${normal} 正常${warning ? ` · ${warning} 備援／待更新` : ""}`;
    const wrapper = $("#sourceStatus");
    if (!wrapper) return;
    wrapper.innerHTML = unique.length ? unique.map(source => `
      <div class="source-row"><div><strong>${escapeHtml(source.name || source.source)}</strong><small>${escapeHtml(source.message || source.kind || (source.last_success ? formatDateTime(source.last_success) : "—"))}</small></div><span class="source-pill ${source.status === "ok" ? "ok" : "warning"}">${source.status === "ok" ? "正常" : "備援中"}</span></div>`).join("") : '<div class="portfolio-empty-mini">資料來源狀態等待第一次更新。</div>';
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
    const today = $("#todayLabel");
    const clock = $("#clockLabel");
    if (today) today.textContent = `${now.getFullYear()}年${now.getMonth() + 1}月${now.getDate()}日（週${DAY_NAMES[now.getDay()]}）`;
    if (clock) clock.textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
  }

  function restorePrefs() {
    const prefs = loadPrefs();
    if (prefs.focus) state.focus = prefs.focus;
    if (prefs.month) state.calendarDate = new Date(prefs.month);
    if (prefs.range) $("#rangeFilter").value = prefs.range;
    if (prefs.region) $("#regionFilter").value = prefs.region;
    if (prefs.category) {
      const select = $("#categoryFilter");
      if (select && [...select.options].some(option => option.value === prefs.category)) select.value = prefs.category;
    }
    $("#highOnly").checked = !!prefs.highOnly;
    if (prefs.search) $("#searchInput").value = prefs.search;
    $$(".focus-chip").forEach((button) => button.classList.toggle("active", button.dataset.focus === state.focus));
  }

  function bind() {
    $("#refreshBtn")?.addEventListener("click", () => window.location.reload());
    $("#closeDayEventsBtn")?.addEventListener("click", () => $("#dayEventsDialog")?.close());
    $("#dayEventsDialog")?.addEventListener("click", (event) => {
      if (event.target === $("#dayEventsDialog")) $("#dayEventsDialog").close();
    });
    $("#prevMonth").addEventListener("click", () => { state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() - 1, 1); renderCalendar(); renderMonthSummary(); savePrefs(); });
    $("#nextMonth").addEventListener("click", () => { state.calendarDate = new Date(state.calendarDate.getFullYear(), state.calendarDate.getMonth() + 1, 1); renderCalendar(); renderMonthSummary(); savePrefs(); });
    $("#todayMonth").addEventListener("click", () => { const now = new Date(); state.calendarDate = new Date(now.getFullYear(), now.getMonth(), 1); renderCalendar(); renderMonthSummary(); savePrefs(); });
    ["#searchInput", "#rangeFilter", "#regionFilter", "#categoryFilter", "#highOnly"].forEach((selector) => $(selector)?.addEventListener(selector === "#searchInput" ? "input" : "change", applyFilters));
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
    window.addEventListener("market-portfolio-changed", () => { portfolioSymbolCache = null; applyFilters(); });
    window.addEventListener("storage", event => {
      if (event.key === "market-radar-portfolio-v10-3") { portfolioSymbolCache = null; applyFilters(); }
    });
    setTimeout(() => { updateAuthUI({ enabled: window.MarketAuth?.firebaseEnabled, user: window.MarketAuth?.getUser?.() }); renderWatchlist(); }, 250);
  }


  function renderBreakingStrip(rawEvents) {
    const root = $("#breakingEventStrip");
    const list = $("#breakingEventItems");
    const count = $("#breakingEventCount");
    if (!root || !list) return;
    const events = (rawEvents || []).slice(0,4);
    root.hidden = events.length === 0;
    if (count) count.textContent = `${events.length} 件`;
    list.innerHTML = events.map(event => `
      <a href="${escapeHtml(event.external_href || "#")}" target="_blank" rel="noreferrer noopener">
        <span>${formatDateTime(event.start)}</span>
        <strong>${escapeHtml(event.title.replace(/^突發｜/,""))}</strong>
        <small>${escapeHtml(event.source_name || "新聞來源")}</small>
      </a>`).join("");
  }

  async function bootstrap() {
    const [payload, newsPayload] = await Promise.all([
      loadJson("data/events.json", window.__MARKET_EVENT_SEED__ || { events: [], metadata: {}, sources: [] }),
      loadJson("data/news.json", window.__MARKET_NEWS_SEED__ || { items: [], metadata: {}, source: {} }),
    ]);
    state.payload = payload;
    state.newsPayload = newsPayload;
    const suddenEvents = breakingNewsToEvents(newsPayload);
    state.payload.metadata = {
      ...(state.payload.metadata || {}),
      breaking_event_count: suddenEvents.length
    };
    state.events = [...(payload.events || []), ...suddenEvents]
      .map(normalizeEvent)
      .sort((a, b) => a.timestamp - b.timestamp);
    renderBreakingStrip(suddenEvents);
    restorePrefs();
    renderSources();
    bind();
    bindPersonalTools();
    document.querySelectorAll("[data-radar-search],[data-radar-focus]").forEach(button => button.addEventListener("click", () => {
      const input=$("#searchInput");
      if (input) { input.value=button.dataset.radarSearch || ""; input.dispatchEvent(new Event("input",{bubbles:true})); }
      if (button.dataset.radarFocus) document.querySelector(`[data-focus="${button.dataset.radarFocus}"]`)?.click();
      $("#calendarSection")?.scrollIntoView({behavior:"smooth",block:"start"});
    }));
    applyFilters();
    updateClock();
    setInterval(updateClock, 1000);
    let resizeTimer;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(renderCalendar, 120);
    });
    window.addEventListener("market-news-loaded", event => {
      state.newsPayload = event.detail?.payload || state.newsPayload;
      renderSources();
      renderStats();
    });
    if ($("#yearLabel")) $("#yearLabel").textContent = String(new Date().getFullYear());
  }

  bootstrap();
})();
