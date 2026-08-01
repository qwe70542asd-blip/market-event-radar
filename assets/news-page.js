(() => {
  "use strict";
  const $ = s => document.querySelector(s);
  const escapeHtml = v => String(v || "").replace(/[&<>\"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
  let payload = { metadata: {}, sources: [], items: [] };

  function fmt(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return "—";
    return `${d.getMonth()+1}/${d.getDate()} ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`;
  }

  function renderSources() {
    const select = $("#newsSourceFilter");
    const sources = [...new Set((payload.items || []).map(x => x.source).filter(Boolean))].sort();
    select.innerHTML = '<option value="all">全部來源</option>' + sources.map(x => `<option>${escapeHtml(x)}</option>`).join("");
  }

  function render() {
    const q = $("#newsSearchInput").value.trim().toLowerCase();
    const region = $("#newsRegionFilter").value;
    const topic = $("#newsTopicFilter").value;
    const source = $("#newsSourceFilter").value;
    const language = $("#newsLanguageFilter")?.value || "all";
    const group = $("#newsGroupFilter")?.value || "all";
    const items = (payload.items || []).filter(item => {
      const blob = `${item.title||""} ${item.summary||""} ${item.source||""}`.toLowerCase();
      return (!q || blob.includes(q))
        && (region === "all" || item.region === region)
        && (topic === "all" || item.topic === topic)
        && (source === "all" || item.source === source)
        && (language === "all" || (item.language || "zh-Hant") === language)
        && (group === "all" || item.source_group === group);
    });
    $("#newsPageGrid").innerHTML = items.map(item => `
      <a class="news-page-card" href="${item.link}" target="_blank" rel="noreferrer noopener">
        <div class="news-card-top"><span>${escapeHtml(item.source || "財經新聞")}</span><small>${fmt(item.published_at)}</small></div>
        <h2>${escapeHtml(item.title)}</h2>
        <p>${escapeHtml(item.summary || item.event_title || "點擊前往原始來源")}</p>
        <div class="news-card-tags"><span>${escapeHtml(item.region || "GLOBAL")}</span><span>${escapeHtml(item.topic || "market")}</span><span>${escapeHtml(item.source_group === "official-tw" ? "官方" : item.source_group === "hk-media" ? "香港中文" : item.language === "zh-Hant" ? "中文" : "英文")}</span>${item.duplicate_count ? `<span>另有 ${item.duplicate_count} 個來源</span>` : ""}${item.origin === "fallback" ? "<span>備援入口</span>" : ""}</div>
      </a>`).join("");
    $("#newsPageEmpty").hidden = items.length > 0;
    $("#newsPageCount").textContent = `${items.length} 則`;
  }

  ["#newsSearchInput","#newsLanguageFilter","#newsGroupFilter","#newsRegionFilter","#newsTopicFilter","#newsSourceFilter"].forEach(s => {
    $(s)?.addEventListener(s.includes("Input") ? "input" : "change", render);
  });

  window.addEventListener("market-news-loaded", event => {
    payload = event.detail.payload;
    $("#newsPageUpdatedAt").textContent = fmt(payload.metadata?.updated_at);
    const state = $("#newsPageState");
    const label = { live:"即時資料", cached:"上次成功資料", fallback:"備援來源" }[event.detail.status] || "同步中";
    if (state) state.textContent = label;
    renderSources();
    render();
  });
})();