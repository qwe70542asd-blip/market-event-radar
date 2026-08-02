(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const escapeHtml = value => String(value ?? "").replace(/[&<>\"']/g, char => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[char]));

  let tickerItems = [];
  let tickerIndex = 0;
  let tickerTimer = null;

  function fmt(value) {
    if (!value) return "等待更新";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString("zh-TW", {
      month:"numeric", day:"numeric", hour:"2-digit", minute:"2-digit", hour12:false
    });
  }

  function formatTradingDate(value) {
    if (!value) return "等待最近交易日";
    const parsed = new Date(`${value}T12:00:00+08:00`);
    if (Number.isNaN(parsed.getTime())) return value;
    const weekday = ["日","一","二","三","四","五","六"][parsed.getDay()];
    return `${parsed.getMonth()+1}/${parsed.getDate()}（週${weekday}）`;
  }

  function isHttpUrl(value) {
    try { const url = new URL(String(value || ""), location.href); return ["http:","https:"].includes(url.protocol); }
    catch { return false; }
  }

  function isGoogle(value) {
    try { return /(^|\.)google\./i.test(new URL(String(value || ""), location.href).hostname); }
    catch { return false; }
  }

  function safeOfficialLink(item) {
    const candidates = [item?.direct_link, item?.publisher_link, item?.safe_link, item?.link, item?.source_home];
    for (const candidate of candidates) {
      if (isHttpUrl(candidate) && !isGoogle(candidate) && !String(candidate).includes("news.google.com")) return candidate;
    }
    return item?.source_home || "news.html";
  }

  function amount(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    return `${number >= 0 ? "+" : ""}${number.toFixed(1)} 億`;
  }

  function institutionalCard(label, value, dateText, href, note, external = false) {
    const target = external ? ' target="_blank" rel="noreferrer noopener"' : '';
    const direction = Number(value) > 0 ? "positive" : Number(value) < 0 ? "negative" : "";
    return `<a class="institutional-card" href="${escapeHtml(href || '#')}"${target}>
      <span>${escapeHtml(label)}</span>
      <strong class="${direction}">${amount(value)}</strong>
      <small>${escapeHtml(dateText)}${note ? ` · ${escapeHtml(note)}` : ""}</small>
    </a>`;
  }

  function showTicker(index) {
    const link = $("#announcementTickerLink");
    if (!link || !tickerItems.length) return;
    tickerIndex = (index + tickerItems.length) % tickerItems.length;
    const item = tickerItems[tickerIndex];
    const region = $("#announcementTickerRegion");
    const title = $("#announcementTickerTitle");
    const source = $("#announcementTickerSource");
    const counter = $("#announcementCounter");
    link.href = safeOfficialLink(item);
    link.target = /^https?:/i.test(link.href) ? "_blank" : "_self";
    if (region) region.textContent = item.region || "GLOBAL";
    if (title) {
      title.textContent = item.title_zh || item.title_original || "官方公告";
      title.classList.remove("ticker-swap");
      void title.offsetWidth;
      title.classList.add("ticker-swap");
    }
    if (source) source.textContent = `${item.source || "官方來源"} · ${fmt(item.published_at)}`;
    if (counter) counter.textContent = `${tickerIndex + 1}/${tickerItems.length}`;
  }

  function resetTicker() {
    clearInterval(tickerTimer);
    if (tickerItems.length > 1) tickerTimer = setInterval(() => showTicker(tickerIndex + 1), 8500);
  }

  function bindTicker() {
    $("#announcementPrev")?.addEventListener("click", () => { showTicker(tickerIndex - 1); resetTicker(); });
    $("#announcementNext")?.addEventListener("click", () => { showTicker(tickerIndex + 1); resetTicker(); });
    const ticker = document.querySelector(".announcement-ticker");
    ticker?.addEventListener("mouseenter", () => clearInterval(tickerTimer));
    ticker?.addEventListener("mouseleave", resetTicker);
  }

  function render(payload) {
    const institutional = payload.institutional || {};
    const cards = $("#institutionalCards");
    if (cards) {
      const twse = institutional.twse || {};
      const tpex = institutional.tpex || {};
      const twseDate = formatTradingDate(institutional.twse_date || institutional.date);
      const tpexDate = formatTradingDate(institutional.tpex_date || institutional.date);
      const lagNote = institutional.is_previous_trading_day ? "最近交易日" : "當日盤後";
      cards.innerHTML = [
        institutionalCard("上市外資", twse.foreign, twseDate, "institutional.html?market=twse&type=foreign", `${lagNote} · 圖表`),
        institutionalCard("上市投信", twse.investment_trust, twseDate, "institutional.html?market=twse&type=investment_trust", "日／週／月圖表"),
        institutionalCard("上市自營商", twse.dealer, twseDate, "institutional.html?market=twse&type=dealer", "自行＋避險"),
        institutionalCard("上櫃三大法人", tpex.total, tpexDate, institutional.tpex_url || "institutional.html?market=tpex&type=total", "官方彙總", Boolean(institutional.tpex_url))
      ].join("");
    }

    tickerItems = (payload.items || [])
      .filter(item => item && (item.title_zh || item.title_original))
      .sort((a,b) => (a.importance === "high" ? -1 : 0) - (b.importance === "high" ? -1 : 0) || new Date(b.published_at || 0) - new Date(a.published_at || 0))
      .slice(0, 20);

    const hiddenList = $("#importantAnnouncementList");
    if (hiddenList) hiddenList.innerHTML = tickerItems.map(item => `<a href="${escapeHtml(safeOfficialLink(item))}">${escapeHtml(item.title_zh || item.title_original)}</a>`).join("");

    if (tickerItems.length) showTicker(0);
    else {
      $("#announcementTickerTitle") && ($("#announcementTickerTitle").textContent = "官方公告等待第一次同步");
      $("#announcementCounter") && ($("#announcementCounter").textContent = "0/0");
    }
    resetTicker();

    const updated = $("#announcementUpdatedAt");
    if (updated) updated.textContent = payload.metadata?.updated_at ? fmt(payload.metadata.updated_at) : "等待第一次排程";
  }

  async function load() {
    let payload = window.__MARKET_ANNOUNCEMENT_SEED__ || {institutional:{},items:[]};
    try {
      const response = await fetch(`data/announcements.json?t=${Date.now()}`, {cache:"no-store"});
      if (response.ok) payload = await response.json();
    } catch {}
    render(payload);
  }

  bindTicker();
  load();
})();
