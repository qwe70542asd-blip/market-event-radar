(() => {
  "use strict";
  const rail = document.getElementById("headlineRail");
  const breakingLink = document.getElementById("breakingNewsLink");
  const breakingSource = document.getElementById("breakingNewsSource");
  const breakingTitle = document.getElementById("breakingNewsTitle");
  const breakingCounter = document.getElementById("breakingCounter");
  const prev = document.getElementById("breakingPrev");
  const next = document.getElementById("breakingNext");
  const escapeHtml = (v) => String(v || "").replace(/[&<>\"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));

  let items = [];
  let current = 0;
  let timer = null;

  function fallbackItems() {
    return [
      { source: "中央社產經", title: "查看中央社最新產經證券消息", link: "https://www.cna.com.tw/list/aie.aspx", region: "TW" },
      { source: "經濟日報", title: "查看台股、產業與國際財經焦點", link: "https://money.udn.com/", region: "TW" },
      { source: "鉅亨網", title: "查看全球市場與即時財經快訊", link: "https://www.cnyes.com/", region: "TW" },
      { source: "Reuters", title: "查看全球市場最新消息", link: "https://www.reuters.com/markets/", region: "GLOBAL" }
    ];
  }

  function showBreaking(index) {
    if (!items.length || !breakingTitle) return;
    current = (index + items.length) % items.length;
    const item = items[current];
    breakingSource.textContent = item.source || "財經新聞";
    breakingTitle.textContent = item.title || "查看最新財經新聞";
    breakingLink.href = item.link || "news.html";
    breakingLink.target = (item.link || "").startsWith("http") ? "_blank" : "_self";
    breakingLink.rel = "noreferrer noopener";
    breakingCounter.textContent = `${current + 1}/${items.length}`;
    breakingTitle.classList.remove("ticker-swap");
    void breakingTitle.offsetWidth;
    breakingTitle.classList.add("ticker-swap");
  }

  function resetTimer() {
    if (timer) clearInterval(timer);
    // 每 60 秒自動換下一則；新聞資料本身由 GitHub Actions 定時抓取。
    timer = setInterval(() => showBreaking(current + 1), 60000);
  }

  function renderRail() {
    if (!rail) return;
    const visible = items.slice(0, 3);
    rail.innerHTML = visible.map(item => `
      <a class="headline-card" href="${item.link || "news.html"}" target="${(item.link || "").startsWith("http") ? "_blank" : "_self"}" rel="noreferrer noopener">
        <div><span>${escapeHtml(item.source || "財經新聞")}</span><small>${escapeHtml(item.region || "GLOBAL")}</small></div>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.summary || item.event_title || "點擊前往原始新聞來源")}</p>
      </a>`).join("");
  }

  async function load() {
    let payload = window.__MARKET_NEWS_SEED__ || { items: [] };
    try {
      const res = await fetch(`data/news.json?t=${Date.now()}`, { cache: "no-store" });
      if (res.ok) payload = await res.json();
    } catch {}
    items = (payload.items || []).filter(item => item.title && item.link);
    if (!items.length) items = fallbackItems();
    renderRail();
    showBreaking(0);
    resetTimer();
  }

  prev?.addEventListener("click", () => { showBreaking(current - 1); resetTimer(); });
  next?.addEventListener("click", () => { showBreaking(current + 1); resetTimer(); });
  load();
})();