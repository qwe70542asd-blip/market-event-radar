(() => {
  "use strict";
  const rail = document.getElementById("headlineRail");
  const breakingLink = document.getElementById("breakingNewsLink");
  const breakingSource = document.getElementById("breakingNewsSource");
  const breakingTitle = document.getElementById("breakingNewsTitle");
  const breakingCounter = document.getElementById("breakingCounter");
  const prev = document.getElementById("breakingPrev");
  const next = document.getElementById("breakingNext");
  const health = document.getElementById("newsLoadState");
  const retry = document.getElementById("newsRetryBtn");
  const escapeHtml = (v) => String(v || "").replace(/[&<>\"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));

  let items = [];
  let current = 0;
  let timer = null;

  function score(item) {
    let value = Number(item.quality_score || 0);
    if (item.language === "zh-Hant") value += 18;
    if (item.source_group === "official-tw") value += 10;
    if (item.is_breaking) value += 40;
    if (item.origin === "direct-rss" || item.origin === "official") value += 15;
    const age = item.published_at ? Date.now() - new Date(item.published_at).getTime() : Infinity;
    if (age < 6 * 3600e3) value += 25;
    else if (age < 24 * 3600e3) value += 12;
    return value;
  }

  function show(index) {
    if (!items.length || !breakingTitle) return;
    current = (index + items.length) % items.length;
    const item = items[current];
    breakingSource.textContent = item.source || "財經新聞";
    breakingTitle.textContent = item.title || "查看最新財經新聞";
    breakingLink.href = window.MarketNewsLink?.safeLink?.(item) || window.MarketNews?.safeLink?.(item) || item.link || "news.html";
    breakingLink.target = /^https?:/.test(item.link || "") ? "_blank" : "_self";
    breakingLink.rel = "noreferrer noopener";
    breakingCounter.textContent = `${current + 1}/${items.length}`;
    breakingTitle.classList.remove("ticker-swap");
    void breakingTitle.offsetWidth;
    breakingTitle.classList.add("ticker-swap");
  }

  function resetTimer() {
    clearInterval(timer);
    timer = setInterval(() => show(current + 1), 60000);
  }

  function pickDiverseHeadlines(allItems, limit = 3) {
    const selected = [];
    const usedIndustries = new Set();
    const usedSources = new Set();
    for (const item of allItems) {
      const industry = item.primary_industry || "other";
      const source = item.source || "";
      if (selected.length < limit && !usedIndustries.has(industry) && !usedSources.has(source)) {
        selected.push(item);
        usedIndustries.add(industry);
        usedSources.add(source);
      }
    }
    for (const item of allItems) {
      if (selected.length >= limit) break;
      if (!selected.includes(item)) selected.push(item);
    }
    return selected;
  }

  function renderRail() {
    if (!rail) return;
    const visible = pickDiverseHeadlines(items, 3);
    rail.innerHTML = visible.map(item => `
      <a class="headline-card" href="${window.MarketNewsLink?.safeLink?.(item) || window.MarketNews?.safeLink?.(item) || item.link}" target="_blank" rel="noreferrer noopener">
        <div><span>${escapeHtml(item.source || "財經新聞")}${item.duplicate_count ? ` · 另 ${item.duplicate_count} 來源` : ""}</span><small>${escapeHtml(item.industry_label || item.region || "市場")} · ${window.MarketNewsLink?.linkMode?.(item) === "direct" ? "原文" : "搜尋"}</small></div>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.summary || item.event_title || "點擊前往原始來源")}</p>
      </a>`).join("");
  }

  function updateState(detail) {
    if (!health) return;
    const map = {
      live: "即時資料",
      cached: "上次成功資料",
      fallback: "備援來源",
      loading: "同步中"
    };
    health.textContent = map[detail.status] || "資料狀態";
    health.dataset.state = detail.status;
  }

  window.addEventListener("market-news-loaded", (event) => {
    const detail = event.detail;
    items = [...(detail.items || [])].sort((a, b) => score(b) - score(a));
    renderRail();
    show(0);
    resetTimer();
    updateState(detail);
  });

  prev?.addEventListener("click", () => { show(current - 1); resetTimer(); });
  next?.addEventListener("click", () => { show(current + 1); resetTimer(); });
  retry?.addEventListener("click", async () => {
    health.textContent = "重新同步中";
    await window.MarketNewsLoader?.load();
  });

  if (window.MarketNews) {
    window.dispatchEvent(new CustomEvent("market-news-loaded", { detail: window.MarketNews }));
  }
})();