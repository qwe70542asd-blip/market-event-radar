(async () => {
  "use strict";
  const { $, $$, escapeHtml, finite, loadData, fetchTaiwanLiveQuotes, fetchTaiwanIndicesLive, fetchYahooChart,
    mergeQuoteItems, mergeAssets, loadPortfolio, migratePortfolio, findTwQuote, formatPrice,
    formatPercent, direction, formatTime, safeNewsLink, diversifyNews } = MR;
  const DAY = ["日","一","二","三","四","五","六"];
  const state = {events:[], filtered:[], month:new Date(new Date().getFullYear(),new Date().getMonth(),1), focus:"all"};

  const [assetPayload,eventPayload,newsPayload,initialTwPayload,initialMarketPayload] = await Promise.all([
    loadData("assets.json", window.__ASSET_SEED__ || {assets:[]}),
    loadData("events.json", window.__EVENT_SEED__ || {events:[]}),
    loadData("news.json", window.__NEWS_SEED__ || {items:[]}),
    loadData("tw-market.json", window.__TW_MARKET_SEED__ || {items:[]}),
    loadData("market-snapshot.json", window.__MARKET_SNAPSHOT_SEED__ || {items:[]})
  ]);
  let twPayload = initialTwPayload;
  let marketPayload = initialMarketPayload;
  let liveRefreshBusy = false;
  let lastDirectRefresh = 0;

  const assets = mergeAssets(assetPayload.assets || [], (window.__ASSET_SEED__ || {}).assets || []);
  const entries = migratePortfolio(loadPortfolio(), assets);
  state.events = (eventPayload.events || []).map(event => {
    const start = new Date(event.start);
    return {...event,startDate:start,key:`${start.getFullYear()}-${String(start.getMonth()+1).padStart(2,"0")}-${String(start.getDate()).padStart(2,"0")}`};
  });

  function quoteForEntry(entry) {
    return entry.market === "TW"
      ? findTwQuote(entry, twPayload)
      : (marketPayload.items || []).find(item => String(item.symbol || "").toUpperCase() === String(entry.symbol || "").toUpperCase()) || null;
  }

  function renderPortfolio() {
    const strip = $("#portfolioStrip");
    $("#portfolioCount").textContent = `${entries.length} 個標的`;
    if (!entries.length) {
      strip.innerHTML = '<div class="empty" style="min-width:100%">尚未加入投資標的，到個人頁面新增即可。</div>';
      $("#portfolioStatus").textContent = "尚無標的";
      return;
    }

    const ranked = entries.map((entry, originalIndex) => {
      const quote = quoteForEntry(entry);
      const price = finite(quote?.price);
      const shares = finite(entry.shares);
      const avgCost = finite(entry.avg_cost);
      const marketValue = shares !== null
        ? (price !== null ? price * shares : avgCost !== null ? avgCost * shares : 0)
        : 0;
      return {entry, quote, marketValue, originalIndex};
    }).sort((a, b) => b.marketValue - a.marketValue || a.originalIndex - b.originalIndex);

    const visible = ranked.slice(0, 7);
    const hiddenCount = Math.max(0, ranked.length - visible.length);
    const available = ranked.filter(row => finite(row.quote?.price) !== null).length;

    const cards = visible.map(({entry, quote}) => {
      const pct = finite(quote?.change_percent);
      const href = `asset.html?id=${encodeURIComponent(entry.asset_id || `${entry.market}:${entry.symbol}`)}`;
      return `<a class="quote-card" href="${href}">
        <div class="quote-top"><span class="asset-badge">${entry.asset_class === "etf" ? "ETF" : entry.asset_class === "crypto" ? "幣" : "股票"}</span>
        <span><strong>${escapeHtml(entry.name)}</strong><small>${escapeHtml(entry.symbol)} · ${escapeHtml(entry.exchange || entry.market)}</small></span>
        <b class="${direction(pct)}">${formatPercent(pct)}</b></div>
        <div class="quote-body"><span><strong>${formatPrice(quote?.price,entry.currency)}</strong><small>前收 ${formatPrice(quote?.previous_close,entry.currency)}</small></span><span class="${direction(pct)}">${quote ? "●" : "—"}</span></div>
        <div class="quote-foot"><span>${quote?.status === "mis" ? "盤中／延遲" : quote ? "最後交易日" : "官方行情暫時不可用"}</span><span>${quote?.quote_time || ""}</span></div>
      </a>`;
    });
    if (hiddenCount > 0) {
      cards.push(`<a class="quote-card portfolio-more-card" href="portfolio.html" aria-label="查看其餘 ${hiddenCount} 個標的"><strong>…</strong><span>其餘 ${hiddenCount} 個標的</span><small>依資產配置排序後未顯示</small></a>`);
    }
    strip.innerHTML = cards.join("");
    $("#portfolioStatus").textContent = available ? `${available} 項有行情` : "等待官方行情";
  }

  function eventGroup(event) {
    if (event.event_group) return event.event_group;
    if (event.category === "breaking") return "breaking";
    if (["macro","central-bank","policy"].includes(event.category)) return "macro";
    if (["earnings","monthly-revenue"].includes(event.category)) return "earnings";
    if (["dividend","ex-dividend","etf-distribution"].includes(event.category)) return "dividend";
    return "corporate";
  }
  function focusMatch(event) {
    if (state.focus === "all") return true;
    const text = `${event.title || ""} ${event.description || ""} ${(event.tags || []).join(" ")}`;
    if (state.focus === "technology") return /科技|AI|半導體|晶片|伺服器|電子|軟體/i.test(text);
    if (state.focus === "finance") return /金融|金控|銀行|保險|利率/i.test(text);
    if (state.focus === "shipping") return /航運|海運|貨櫃|航空|運價/i.test(text);
    if (state.focus === "rates") return /CPI|PPI|PMI|利率|聯準會|央行|通膨|GDP/i.test(text);
    if (state.focus === "earnings") return /財報|營收|法說|業績/i.test(text);
    return true;
  }
  function applyEventFilters() {
    const query = String($("#eventSearch").value || "").toLowerCase();
    const region = $("#eventRegion").value;
    const type = $("#eventType").value;
    const impact = $("#eventImpact").value;
    state.filtered = state.events.filter(event => {
      const text = `${event.title || ""} ${event.description || ""} ${(event.tags || []).join(" ")}`.toLowerCase();
      if (query && !text.includes(query)) return false;
      if (region !== "all" && event.region !== region) return false;
      if (type !== "all" && eventGroup(event) !== type) return false;
      if (impact !== "all" && event.impact !== impact) return false;
      return focusMatch(event);
    });
    renderCalendar();
  }
  function monthDays(base) {
    const first = new Date(base.getFullYear(),base.getMonth(),1);
    const last = new Date(base.getFullYear(),base.getMonth()+1,0);
    const start = new Date(first); start.setDate(start.getDate()-start.getDay());
    const end = new Date(last); end.setDate(end.getDate()+(6-end.getDay()));
    const days=[];
    for (let cur=new Date(start);cur<=end;cur.setDate(cur.getDate()+1)) days.push(new Date(cur));
    return days;
  }
  function openDay(day, events) {
    $("#dayDialogTitle").textContent = `${day.getMonth()+1} 月 ${day.getDate()} 日（週${DAY[day.getDay()]}）`;
    $("#dayDialogBody").innerHTML = events.length ? events.sort((a,b)=>a.startDate-b.startDate).map(event => `<a class="day-event" href="event.html?id=${encodeURIComponent(event.id)}"><time>${event.all_day ? "全天" : event.startDate.toLocaleTimeString("zh-TW",{hour:"2-digit",minute:"2-digit",hour12:false})}</time><span><strong>${escapeHtml(event.title)}</strong><p>${escapeHtml(event.description || event.market_effect || "")}</p></span></a>`).join("") : '<div class="empty">這一天沒有符合篩選的事件。</div>';
    $("#dayDialog").showModal();
  }
  function renderCalendar() {
    const grid = $("#calendarGrid");
    const days = monthDays(state.month);
    const rows = days.length/7;
    grid.style.setProperty("--calendar-rows",rows);
    $("#calendarTitle").textContent = `${state.month.getFullYear()} 年 ${state.month.getMonth()+1} 月`;
    const map = new Map();
    state.filtered.forEach(event => {
      if (!map.has(event.key)) map.set(event.key,[]);
      map.get(event.key).push(event);
    });
    const today = new Date();
    grid.innerHTML = days.map(day => {
      const key = `${day.getFullYear()}-${String(day.getMonth()+1).padStart(2,"0")}-${String(day.getDate()).padStart(2,"0")}`;
      const events = map.get(key) || [];
      const groups = {};
      events.forEach(event => groups[eventGroup(event)] = (groups[eventGroup(event)] || 0)+1);
      return `<article class="calendar-day ${day.getMonth() !== state.month.getMonth() ? "muted" : ""} ${day.toDateString() === today.toDateString() ? "today" : ""}" data-day="${key}">
        <div class="day-head"><strong>${day.getDate()}</strong><small>${events.length ? `${events.length} 件` : ""}</small></div>
        <div class="day-events">${Object.entries(groups).map(([group,count]) => `<button class="event-dot ${group}" data-group="${group}"><i></i><span>${{breaking:"突發",macro:"總經",earnings:"財報",dividend:"股利",corporate:"公司"}[group] || group}</span><b>${count}</b></button>`).join("")}</div>
      </article>`;
    }).join("");
    $$(".calendar-day").forEach((cell,index) => cell.addEventListener("click", event => {
      event.preventDefault();
      openDay(days[index], map.get(cell.dataset.day) || []);
    }));
  }

  function marketClock(item) {
    const seconds = finite(item?.market_at);
    if (seconds !== null) {
      return new Date(seconds * 1000).toLocaleString("zh-TW", {
        timeZone:"Asia/Taipei", month:"numeric", day:"numeric",
        hour:"2-digit", minute:"2-digit", hour12:false
      });
    }
    return formatTime(marketPayload?.metadata?.updated_at);
  }

  function renderTaiwanIndices() {
    const renderOne = (symbol, ids) => {
      const item = (marketPayload.items || []).find(row => row.symbol === symbol);
      const priceNode = $(ids.price);
      const changeNode = $(ids.change);
      const rangeNode = $(ids.range);
      const timeNode = $(ids.time);
      if (!item || finite(item.price) === null) {
        priceNode.textContent = "等待行情";
        changeNode.textContent = "—";
        rangeNode.textContent = "高低 —";
        timeNode.textContent = "排程更新中";
        return;
      }
      priceNode.textContent = Number(item.price).toLocaleString("zh-TW", {maximumFractionDigits:2});
      changeNode.className = direction(item.change_percent);
      changeNode.textContent = `${finite(item.change) !== null ? `${item.change > 0 ? "+" : ""}${Number(item.change).toLocaleString("zh-TW",{maximumFractionDigits:2})}` : "—"}　${formatPercent(item.change_percent)}`;
      const high = finite(item.high), low = finite(item.low);
      rangeNode.textContent = high !== null && low !== null
        ? `高 ${high.toLocaleString("zh-TW",{maximumFractionDigits:2})}　低 ${low.toLocaleString("zh-TW",{maximumFractionDigits:2})}`
        : "高低資料等待更新";
      timeNode.textContent = `${marketClock(item)} · ${item.market_state === "REGULAR" ? "盤中" : "近即時／延遲"}`;
    };
    renderOne("^TWII", {price:"#taiexPrice",change:"#taiexChange",range:"#taiexRange",time:"#taiexTime"});
    renderOne("^TWOII", {price:"#tpexIndexPrice",change:"#tpexIndexChange",range:"#tpexIndexRange",time:"#tpexIndexTime"});
  }

  function renderMarket() {
    const items = (marketPayload.items || []).filter(item => !["^TWII","^TWOII"].includes(item.symbol)).slice(0,9);
    $("#marketUpdated").textContent = formatTime(marketPayload?.metadata?.updated_at);
    $("#marketSource").textContent = marketPayload?.metadata?.source || "公開行情";
    $("#marketList").innerHTML = items.length ? items.map(item => `<div class="market-row"><span><strong>${escapeHtml(item.name || item.symbol)}</strong><small>${escapeHtml(item.symbol || item.market || "")}</small></span><b>${formatPrice(item.price,item.currency || "")}</b><em class="${direction(item.change_percent)}">${formatPercent(item.change_percent)}</em></div>`).join("") : '<div class="empty">等待市場行情排程。</div>';
  }

  async function renderCrypto() {
    const fallback = [
      {symbol:"BTC",name:"Bitcoin",current_price:63547,price_change_percentage_24h:1.23,total_volume:15890000000},
      {symbol:"ETH",name:"Ethereum",current_price:1883,price_change_percentage_24h:2.11,total_volume:5100000000},
      {symbol:"SOL",name:"Solana",current_price:73.58,price_change_percentage_24h:2.35,total_volume:1050000000},
      {symbol:"XRP",name:"XRP",current_price:1.085,price_change_percentage_24h:2.3,total_volume:770000000},
      {symbol:"ADA",name:"Cardano",current_price:.1888,price_change_percentage_24h:8.51,total_volume:640000000}
    ];
    let rows = fallback;
    try {
      const response = await fetch("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=8&page=1&sparkline=false&price_change_percentage=24h",{cache:"no-store"});
      if (response.ok) rows = (await response.json()).filter(row => !["usdt","usdc"].includes(String(row.symbol).toLowerCase())).slice(0,5);
      $("#cryptoStatus").textContent = "近即時";
    } catch { $("#cryptoStatus").textContent = "備援資料"; }
    $("#cryptoList").innerHTML = rows.map(row => `<div class="crypto-row"><span><strong>${escapeHtml(row.name)}</strong><small>${String(row.symbol).toUpperCase()} · 24H量 ${(Number(row.total_volume || 0)/1e8).toFixed(1)}億</small></span><b>$${Number(row.current_price).toLocaleString("en-US",{maximumFractionDigits:row.current_price<10?4:2})}</b><em class="${direction(row.price_change_percentage_24h)}">${formatPercent(row.price_change_percentage_24h)}</em></div>`).join("");
    $("#cryptoTime").textContent = new Date().toLocaleTimeString("zh-TW",{hour:"2-digit",minute:"2-digit",hour12:false});
    syncCalendarToSideRail();
  }

  function renderNews() {
    const items = diversifyNews(newsPayload.items || [], 6);
    const first = items[0];
    if (first) {
      $("#breakingLink").textContent = first.title;
      $("#breakingLink").href = safeNewsLink(first);
    }
    $("#homeNews").innerHTML = items.length ? items.map(item => {
      const related = Number(item.duplicate_count || item.related_count || 0);
      return `<a class="news-card" href="${escapeHtml(safeNewsLink(item))}" target="_blank" rel="noreferrer noopener"><div class="news-source"><span>${escapeHtml(item.source || "財經新聞")}</span><time>${formatTime(item.published_at)}</time></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.summary || "點擊前往原始來源閱讀全文。")}</p><div class="tag-row"><span class="tag">${escapeHtml(item.region || "GLOBAL")}</span><span class="tag">${escapeHtml(item.topic || "market")}</span>${related ? `<span class="tag">另有 ${related} 篇相關</span>` : ""}<span class="tag">原始文章</span></div></a>`;
    }).join("") : '<div class="empty" style="grid-column:1/-1">第一次新聞排程完成後，這裡會顯示 Yahoo、鉅亨、MoneyDJ 與券商來源。</div>';
  }

  async function refreshLiveMarket() {
    if (liveRefreshBusy || document.hidden) return;
    liveRefreshBusy = true;
    const refreshStarted = Date.now();
    try {
      const twEntries = entries.filter(entry => entry.market === "TW");
      const [liveTwResult, officialIndexResult] = await Promise.allSettled([
        fetchTaiwanLiveQuotes(twEntries),
        fetchTaiwanIndicesLive()
      ]);

      const liveTw = liveTwResult.status === "fulfilled" ? liveTwResult.value : [];
      let indexUpdates = officialIndexResult.status === "fulfilled" ? officialIndexResult.value : [];
      if (indexUpdates.length < 2) {
        const yahooResults = await Promise.allSettled([fetchYahooChart("^TWII"), fetchYahooChart("^TWOII")]);
        indexUpdates = [
          ...indexUpdates,
          ...yahooResults.filter(result => result.status === "fulfilled" && result.value).map(result => result.value)
        ];
      }

      if (liveTw.length) {
        twPayload = {
          ...twPayload,
          metadata: {
            ...(twPayload.metadata || {}),
            updated_at: new Date().toISOString(),
            source: "TWSE MIS 瀏覽器每分鐘刷新",
            refresh_interval_seconds: 60
          },
          items: mergeQuoteItems(twPayload.items || [], liveTw)
        };
        lastDirectRefresh = refreshStarted;
      } else {
        const latest = await loadData("tw-market.json", twPayload);
        if (latest?.items?.length) twPayload = latest;
      }

      if (indexUpdates.length) {
        marketPayload = {
          ...marketPayload,
          metadata: {
            ...(marketPayload.metadata || {}),
            updated_at: new Date().toISOString(),
            source: indexUpdates.some(row => row.source === "TWSE MIS") ? "TWSE MIS 每分鐘刷新" : "Yahoo chart 1m 瀏覽器刷新",
            refresh_interval_seconds: 60
          },
          items: mergeQuoteItems(marketPayload.items || [], indexUpdates)
        };
        lastDirectRefresh = refreshStarted;
      } else {
        const latest = await loadData("market-snapshot.json", marketPayload);
        if (latest?.items?.length) marketPayload = latest;
      }

      renderPortfolio();
      renderTaiwanIndices();
      renderMarket();
      $("#portfolioStatus").title = lastDirectRefresh
        ? `最近每分鐘刷新：${new Date(lastDirectRefresh).toLocaleTimeString("zh-TW",{hour12:false})}`
        : "直接行情連線失敗時使用 GitHub 排程備援";
    } catch (error) {
      console.warn("One-minute market refresh failed:", error);
    } finally {
      liveRefreshBusy = false;
    }
  }

  function syncCalendarToSideRail() {
    const calendar = document.querySelector(".calendar-card");
    const side = document.querySelector(".side-rail");
    if (!calendar || !side || window.innerWidth <= 1100) {
      calendar?.style.removeProperty("height");
      return;
    }
    requestAnimationFrame(() => {
      const sideHeight = Math.ceil(side.scrollHeight);
      if (sideHeight > 0) calendar.style.height = `${sideHeight}px`;
    });
  }

  if ("ResizeObserver" in window) {
    const observer = new ResizeObserver(syncCalendarToSideRail);
    const side = document.querySelector(".side-rail");
    if (side) observer.observe(side);
  }
  window.addEventListener("resize", syncCalendarToSideRail);

  $("#prevMonth").addEventListener("click",()=>{state.month=new Date(state.month.getFullYear(),state.month.getMonth()-1,1);renderCalendar()});
  $("#nextMonth").addEventListener("click",()=>{state.month=new Date(state.month.getFullYear(),state.month.getMonth()+1,1);renderCalendar()});
  $("#todayMonth").addEventListener("click",()=>{const n=new Date();state.month=new Date(n.getFullYear(),n.getMonth(),1);renderCalendar()});
  ["eventSearch","eventRegion","eventType","eventImpact"].forEach(id => $(`#${id}`).addEventListener(id==="eventSearch"?"input":"change",applyEventFilters));
  $$("[data-focus]").forEach(btn => btn.addEventListener("click",()=>{state.focus=btn.dataset.focus;$$("[data-focus]").forEach(b=>b.classList.toggle("active",b===btn));applyEventFilters()}));
  $("#closeDayDialog").addEventListener("click",()=>$("#dayDialog").close());
  $("#dayDialog").addEventListener("click",e=>{if(e.target===$("#dayDialog"))$("#dayDialog").close()});

  $("#eventUpdated").textContent = formatTime(eventPayload?.metadata?.updated_at);
  state.filtered = [...state.events];
  renderPortfolio(); renderCalendar(); renderTaiwanIndices(); renderMarket(); renderCrypto(); renderNews(); syncCalendarToSideRail();
  setTimeout(refreshLiveMarket, 2500);
  setInterval(refreshLiveMarket, 60_000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden && Date.now() - lastDirectRefresh > 55_000) refreshLiveMarket();
  });
})();
