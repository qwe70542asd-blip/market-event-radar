(() => {
  "use strict";
  const $=selector=>document.querySelector(selector);
  const $$=selector=>[...document.querySelectorAll(selector)];
  const escapeHtml=value=>String(value??"").replace(/[&<>\"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[char]));

  const breakingLink=$("#breakingNewsLink");
  const breakingSource=$("#breakingNewsSource");
  const breakingTitle=$("#breakingNewsTitle");
  const breakingCounter=$("#breakingCounter");
  const health=$("#newsLoadState");
  const todayList=$("#todayNewsList");

  const state={items:[],breaking:[],breakingIndex:0,breakingTimer:null,filter:"all",newsOffset:0,newsTimer:null};

  function fmt(value) {
    const date=new Date(value || 0);
    if (Number.isNaN(date.getTime())) return "—";
    return date.toLocaleString("zh-TW",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false});
  }

  function category(item) {
    if (item.is_breaking) return "breaking";
    if (String(item.source_group || "").includes("broker") || /投顧|證券|券商|研究/i.test(`${item.source||""} ${item.query_source||""}`)) return "broker";
    if (String(item.source_group || "").startsWith("official") || item.topic === "official") return "official";
    if (item.region === "TW") return "TW";
    if (item.region === "US") return "US";
    return "GLOBAL";
  }

  function categoryLabel(item) {
    return {breaking:"突發",broker:"券商",official:"官方",TW:"台股",US:"美股",GLOBAL:"國際"}[category(item)] || "市場";
  }

  function score(item) {
    let value=Number(item.quality_score || 0);
    const age=Date.now()-new Date(item.published_at || 0).getTime();
    if (item.is_breaking) value+=50;
    if (category(item)==="broker") value+=14;
    if (category(item)==="official") value+=12;
    if (item.language==="zh-Hant") value+=15;
    if (age<3*3600e3) value+=35;
    else if (age<12*3600e3) value+=22;
    else if (age<36*3600e3) value+=10;
    return value;
  }

  function directLink(item) {
    return window.MarketNewsLink?.safeLink?.(item) || "";
  }

  function visibleNews() {
    const filtered=state.items.filter(item=>state.filter==="all" || category(item)===state.filter);
    const recent=filtered.filter(item=>Date.now()-new Date(item.published_at || 0).getTime()<48*3600e3);
    return (recent.length>=4?recent:filtered).sort((a,b)=>new Date(b.published_at||0)-new Date(a.published_at||0) || score(b)-score(a));
  }

  function renderToday() {
    if (!todayList) return;
    const rows=visibleNews();
    if (!rows.length) {
      todayList.innerHTML='<div class="today-news-empty"><strong>等待新聞排程</strong><span>目前沒有可直接開啟原文的新聞；GitHub Action 更新後會自動補入。</span></div>';
      return;
    }
    const count=Math.min(6,rows.length);
    const selected=Array.from({length:count},(_,index)=>rows[(state.newsOffset+index)%rows.length]);
    todayList.innerHTML=selected.map(item=>`
      <a class="today-news-row type-${category(item)}" href="${escapeHtml(directLink(item))}" target="_blank" rel="noreferrer noopener">
        <time>${escapeHtml(fmt(item.published_at))}</time>
        <span class="today-news-badge">${escapeHtml(categoryLabel(item))}</span>
        <strong>${escapeHtml(item.title)}</strong>
        <em>${escapeHtml(item.source || "新聞來源")}</em>
      </a>`).join("");
    todayList.classList.remove("news-swap");
    void todayList.offsetWidth;
    todayList.classList.add("news-swap");
  }

  function restartNewsTimer() {
    clearInterval(state.newsTimer);
    state.newsTimer=setInterval(()=>{
      const rows=visibleNews();
      if (rows.length>6) {
        state.newsOffset=(state.newsOffset+1)%rows.length;
        renderToday();
      }
    },5000);
  }

  function showBreaking(index) {
    if (!state.breaking.length || !breakingLink) {
      if (breakingTitle) breakingTitle.textContent="等待可直接開啟原文的重要新聞…";
      if (breakingCounter) breakingCounter.textContent="0/0";
      return;
    }
    state.breakingIndex=(index+state.breaking.length)%state.breaking.length;
    const item=state.breaking[state.breakingIndex];
    breakingSource.textContent=item.source || categoryLabel(item);
    breakingTitle.textContent=item.title;
    breakingLink.href=directLink(item);
    breakingLink.target="_blank";
    breakingLink.rel="noreferrer noopener";
    breakingCounter.textContent=`${state.breakingIndex+1}/${state.breaking.length}`;
    breakingTitle.classList.remove("ticker-swap");
    void breakingTitle.offsetWidth;
    breakingTitle.classList.add("ticker-swap");
  }

  function restartBreakingTimer() {
    clearInterval(state.breakingTimer);
    state.breakingTimer=setInterval(()=>showBreaking(state.breakingIndex+1),10000);
  }

  function updateState(detail) {
    if (!health) return;
    const map={live:"直接原文",cached:"上次成功資料",empty:"等待資料",loading:"同步中"};
    health.textContent=map[detail.status] || "資料狀態";
    health.dataset.state=detail.status;
  }

  window.addEventListener("market-news-loaded",event=>{
    const detail=event.detail || {};
    state.items=(detail.items || []).filter(item=>directLink(item)).sort((a,b)=>score(b)-score(a));
    state.breaking=state.items.filter(item=>item.is_breaking || ["policy","macro","market"].includes(item.topic)).slice(0,30);
    if (!state.breaking.length) state.breaking=state.items.slice(0,20);
    state.newsOffset=0;
    renderToday();
    showBreaking(0);
    restartNewsTimer();
    restartBreakingTimer();
    updateState(detail);
  });

  $("#breakingPrev")?.addEventListener("click",()=>{showBreaking(state.breakingIndex-1);restartBreakingTimer();});
  $("#breakingNext")?.addEventListener("click",()=>{showBreaking(state.breakingIndex+1);restartBreakingTimer();});
  $("#newsRetryBtn")?.addEventListener("click",()=>window.MarketNewsLoader?.load?.());
  $$("[data-news-filter]").forEach(button=>button.addEventListener("click",()=>{
    state.filter=button.dataset.newsFilter;
    state.newsOffset=0;
    $$("[data-news-filter]").forEach(node=>node.classList.toggle("active",node===button));
    renderToday();
    restartNewsTimer();
  }));
})();
