(() => {
  "use strict";
  const $ = id => document.getElementById(id);
  const rail = $("headlineRail");
  const breakingLink = $("breakingNewsLink");
  const breakingSource = $("breakingNewsSource");
  const breakingTitle = $("breakingNewsTitle");
  const breakingCounter = $("breakingCounter");
  const health = $("newsLoadState");
  const retry = $("newsRetryBtn");
  const escapeHtml = value => String(value ?? "").replace(/[&<>\"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  let items=[];
  let current=0;
  let timer=null;
  let lastSignature="";

  function score(item) {
    let value=Number(item.quality_score||0);
    if (item.language === "zh-Hant") value += 18;
    if (["official-tw","official-global"].includes(item.source_group)) value += 18;
    if (item.is_breaking) value += 38;
    if (["direct-rss","official","direct-page"].includes(item.origin)) value += 18;
    const age=item.published_at ? Date.now()-new Date(item.published_at).getTime() : Infinity;
    if (age<6*3600e3) value+=25; else if (age<24*3600e3) value+=12;
    return value;
  }

  function linkFor(item) {
    return window.MarketNewsLink?.safeLink?.(item) || item.source_home || "news.html";
  }
  function modeFor(item) {
    return window.MarketNewsLink?.linkMode?.(item) || "source";
  }

  function show(index) {
    if (!items.length || !breakingTitle || !breakingLink) return;
    current=(index+items.length)%items.length;
    const item=items[current];
    breakingSource.textContent=item.source||"財經新聞";
    breakingTitle.textContent=item.title||"查看最新財經新聞";
    breakingLink.href=linkFor(item);
    breakingLink.target=/^https?:/i.test(breakingLink.href)?"_blank":"_self";
    breakingLink.rel="noreferrer noopener";
    if (breakingCounter) breakingCounter.textContent=`${current+1}/${items.length}`;
    breakingTitle.classList.remove("ticker-swap");
    void breakingTitle.offsetWidth;
    breakingTitle.classList.add("ticker-swap");
  }

  function resetTimer() {
    clearInterval(timer);
    if (items.length>1) timer=setInterval(()=>show(current+1),12000);
  }

  function pickDiverse(all,limit=4) {
    const selected=[]; const sources=new Set(); const industries=new Set();
    for (const item of all) {
      const source=item.source||""; const industry=item.primary_industry||item.industry_label||"other";
      if (!sources.has(source) && !industries.has(industry)) { selected.push(item); sources.add(source); industries.add(industry); }
      if (selected.length>=limit) break;
    }
    for (const item of all) { if (selected.length>=limit) break; if (!selected.includes(item)) selected.push(item); }
    return selected;
  }

  function renderRail() {
    if (!rail) return;
    const visible=pickDiverse(items,4);
    rail.innerHTML=visible.length ? visible.map(item=>`
      <a class="headline-card" href="${escapeHtml(linkFor(item))}" target="_blank" rel="noreferrer noopener">
        <div><span>${escapeHtml(item.source||"財經新聞")}</span><small>${escapeHtml(item.industry_label||item.region||"市場")} · ${modeFor(item)==="direct"?"原文":"來源"}</small></div>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.summary||item.event_title||"點擊前往新聞來源")}</p>
      </a>`).join("") : '<div class="headline-empty">新聞來源正在同步；目前不顯示無法驗證出處的連結。</div>';
  }

  function updateState(detail) {
    if (!health) return;
    const labels={live:"即時資料",cached:"上次成功資料",fallback:"備援來源",loading:"同步中"};
    health.textContent=labels[detail.status]||"資料狀態";
    health.dataset.state=detail.status||"loading";
  }

  function applyDetail(detail) {
    if (!detail) return;
    const signature=`${detail.status}|${detail.items?.length||0}|${detail.payload?.metadata?.updated_at||""}`;
    if (signature===lastSignature && items.length) return;
    lastSignature=signature;
    const all=[...(detail.items||[])].sort((a,b)=>score(b)-score(a));
    const verified=all.filter(item=>["direct","source"].includes(modeFor(item)));
    const direct=verified.filter(item=>modeFor(item)==="direct");
    items=direct.length>=4 ? direct : verified;
    renderRail(); show(0); resetTimer(); updateState(detail);
  }

  window.addEventListener("market-news-loaded", event=>applyDetail(event.detail));
  $("breakingPrev")?.addEventListener("click",()=>{show(current-1);resetTimer();});
  $("breakingNext")?.addEventListener("click",()=>{show(current+1);resetTimer();});
  retry?.addEventListener("click",async()=>{ if(health) health.textContent="重新同步中"; await window.MarketNewsLoader?.load(); });
  setTimeout(()=>{ if(window.MarketNews) applyDetail(window.MarketNews); },0);
})();
