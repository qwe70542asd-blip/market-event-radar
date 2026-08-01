(() => {
  "use strict";
  const $ = s => document.querySelector(s);
  const escapeHtml = v => String(v || "").replace(/[&<>\"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
  let payload = { metadata: {}, items: [] };

  function fmt(value) {
    if (!value) return "—";
    const d = new Date(value);
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
    const items = (payload.items || []).filter(item => {
      const blob = `${item.title||""} ${item.summary||""} ${item.source||""}`.toLowerCase();
      return (!q || blob.includes(q))
        && (region === "all" || item.region === region)
        && (topic === "all" || item.topic === topic)
        && (source === "all" || item.source === source);
    });
    $("#newsPageGrid").innerHTML = items.map(item => `
      <a class="news-page-card" href="${item.link}" target="_blank" rel="noreferrer noopener">
        <div class="news-card-top"><span>${escapeHtml(item.source || "財經新聞")}</span><small>${fmt(item.published_at)}</small></div>
        <h2>${escapeHtml(item.title)}</h2>
        <p>${escapeHtml(item.summary || item.event_title || "")}</p>
        <div class="news-card-tags"><span>${escapeHtml(item.region || "GLOBAL")}</span><span>${escapeHtml(item.topic || "market")}</span></div>
      </a>`).join("");
    $("#newsPageEmpty").hidden = items.length > 0;
    $("#newsPageCount").textContent = `${items.length} 則`;
  }
  async function load() {
    payload = window.__MARKET_NEWS_SEED__ || { metadata: {}, items: [] };
    try {
      const res = await fetch("data/news.json", { cache: "no-store" });
      if (res.ok) payload = await res.json();
    } catch {}
    $("#newsPageUpdatedAt").textContent = fmt(payload.metadata?.updated_at);
    renderSources(); render();
  }
  ["#newsSearchInput","#newsRegionFilter","#newsTopicFilter","#newsSourceFilter"].forEach(s => {
    $(s).addEventListener(s.includes("Input") ? "input" : "change", render);
  });

  const account = $("#accountBtn"), dialog = $("#accountDialog");
  account?.addEventListener("click", () => dialog.showModal());
  $("#guestModeBtn")?.addEventListener("click", () => dialog.close());
  $("#googleLoginBtn")?.addEventListener("click", async () => {
    try { await window.MarketAuth.signInGoogle(); }
    catch (e) { $("#authStatus").textContent = e.message; }
  });
  $("#logoutBtn")?.addEventListener("click", async () => { await window.MarketAuth.signOut(); dialog.close(); });
  window.addEventListener("market-auth-changed", ev => {
    const { user, enabled } = ev.detail;
    $("#accountLabel").textContent = user ? (user.displayName || user.email || "已登入") : "登入／訪客";
    $("#accountAvatar").textContent = user ? (user.displayName || user.email || "G").slice(0,1) : "訪";
    $("#authStatus").textContent = user ? "已登入 Google。" : enabled ? "可使用 Google 登入。" : "尚未設定 Firebase，訪客模式可正常使用。";
    $("#googleLoginBtn").disabled = !enabled;
    $("#logoutBtn").hidden = !user;
  });
  load();
})();