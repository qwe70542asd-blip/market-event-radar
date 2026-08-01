(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const escapeHtml = value => String(value || "").replace(/[&<>\"]/g, char => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"
  }[char]));

  const fmt = value => {
    if (!value) return "等待更新";
    const parsed = new Date(value);
    return Number.isNaN(parsed.getTime())
      ? String(value)
      : parsed.toLocaleString("zh-TW",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false});
  };

  function formatTradingDate(value) {
    if (!value) return "等待最近交易日";
    const parsed = new Date(`${value}T12:00:00+08:00`);
    if (Number.isNaN(parsed.getTime())) return value;
    const weekday = ["日","一","二","三","四","五","六"][parsed.getDay()];
    return `${parsed.getMonth()+1}/${parsed.getDate()}（週${weekday}）`;
  }

  function isGoogleNewsRedirect(value) {
    try {
      const url = new URL(String(value || ""));
      return url.hostname === "news.google.com" && /\/(?:rss\/)?(?:articles|read)\//.test(url.pathname);
    } catch {
      return false;
    }
  }

  function safeLink(item) {
    const value = item?.safe_link || item?.link || "";
    if (value && !isGoogleNewsRedirect(value)) return value;
    const query = [`"${item?.title_original || item?.title_zh || ""}"`, item?.source || ""].filter(Boolean).join(" ");
    return `https://www.google.com/search?q=${encodeURIComponent(query)}`;
  }

  async function load() {
    let payload = window.__MARKET_ANNOUNCEMENT_SEED__ || {institutional:{},items:[]};
    try {
      const response = await fetch(`data/announcements.json?t=${Date.now()}`,{cache:"no-store"});
      if (response.ok) payload = await response.json();
    } catch {}
    render(payload);
  }

  function amount(value) {
    if (value === null || value === undefined) return "—";
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value);
    return `${number >= 0 ? "+" : ""}${number.toFixed(1)} 億`;
  }

  function institutionalCard(label, value, dateText, url, note) {
    const href = url || "#";
    return `<a class="institutional-card" href="${escapeHtml(href)}" target="_blank" rel="noreferrer noopener">
      <span>${escapeHtml(label)}</span>
      <strong>${amount(value)}</strong>
      <small>${escapeHtml(dateText)}${note ? ` · ${escapeHtml(note)}` : ""}</small>
    </a>`;
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
        institutionalCard("上市外資", twse.foreign, twseDate, institutional.twse_url, lagNote),
        institutionalCard("上市投信", twse.investment_trust, twseDate, institutional.twse_url, "官方彙總"),
        institutionalCard("上市自營商", twse.dealer, twseDate, institutional.twse_url, "自行＋避險"),
        institutionalCard("上櫃三大法人", tpex.total, tpexDate, institutional.tpex_url, lagNote)
      ].join("");
    }

    const note = $(".announcement-note");
    if (note && institutional.note) note.textContent = institutional.note;

    const list = $("#importantAnnouncementList");
    if (list) {
      const items = (payload.items || []).slice(0,8);
      list.innerHTML = items.length ? items.map(item => `
        <a class="announcement-row" href="${escapeHtml(safeLink(item))}" target="_blank" rel="noreferrer noopener">
          <span class="announcement-region">${escapeHtml(item.region || "GLOBAL")}</span>
          <div>
            <strong>${escapeHtml(item.title_zh || item.title_original)}</strong>
            <small>${escapeHtml(item.source || "官方來源")} · ${fmt(item.published_at)}${item.translation_status === "rule-based" ? " · 規則翻譯" : ""}${item.link_status === "stable-search" ? " · 安全搜尋連結" : ""}</small>
          </div>
          <b>${item.importance === "high" ? "重要" : "公告"}</b>
        </a>`).join("") : '<div class="portfolio-empty-mini">官方公告同步中，暫時保留來源入口。</div>';
    }

    const updated = $("#announcementUpdatedAt");
    if (updated) {
      updated.textContent = payload.metadata?.updated_at ? fmt(payload.metadata.updated_at) : "等待第一次排程";
    }
  }

  load();
})();