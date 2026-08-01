(() => {
  "use strict";
  const rail = document.getElementById("headlineRail");
  if (!rail) return;
  const escapeHtml = (v) => String(v || "").replace(/[&<>\"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
  async function load() {
    let payload = window.__MARKET_NEWS_SEED__ || { items: [] };
    try {
      const res = await fetch("data/news.json", { cache: "no-store" });
      if (res.ok) payload = await res.json();
    } catch {}
    const items = (payload.items || []).slice(0, 3);
    rail.innerHTML = items.length ? items.map(item => `
      <a class="headline-card" href="${item.link}" target="_blank" rel="noreferrer noopener">
        <div><span>${escapeHtml(item.source || "財經新聞")}</span><small>${escapeHtml(item.region || "GLOBAL")}</small></div>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.summary || item.event_title || "")}</p>
      </a>`).join("") :
      '<div class="headline-empty">新聞排程尚未抓到內容。可先前往「財經新聞」頁查看外部媒體入口。</div>';
  }
  load();
})();