(async () => {
  "use strict";
  const {$,escapeHtml,loadData,safeNewsLink,formatTime,diversifyNews}=MR;
  let payload=await loadData("news.json",window.__NEWS_SEED__||{items:[],sources:[]});
  let items=payload.items||[];
  const sources=[...new Set(items.map(item=>item.source).filter(Boolean))].sort();
  $("#newsSource").innerHTML='<option value="all">全部來源</option>'+sources.map(s=>`<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
  $("#newsCount").textContent=items.length.toLocaleString("zh-TW");$("#sourceCount").textContent=sources.length.toLocaleString("zh-TW");$("#newsUpdated").textContent=formatTime(payload?.metadata?.updated_at);
  const statusMap=new Map((payload.sources||[]).map(s=>[s.name||s.source,s]));
  $("#sourceGrid").innerHTML=sources.length?sources.map(name=>{const row=statusMap.get(name)||{};return`<article class="source-card"><strong>${escapeHtml(name)}</strong><small class="${row.status==="warning"?"":"source-ok"}">${row.status==="warning"?"備援／待更新":"正常"} · ${escapeHtml(row.message||row.group||"新聞來源")}</small></article>`}).join(""):'<div class="empty" style="grid-column:1/-1">第一次新聞排程完成後顯示來源狀態。</div>';
  function render(){
    const q=String($("#newsSearch").value||"").toLowerCase(),region=$("#newsRegion").value,topic=$("#newsTopic").value,source=$("#newsSource").value;
    const filteredBase=items.filter(item=>{
      const text=`${item.title||""} ${item.summary||""} ${item.source||""}`.toLowerCase();
      return(!q||text.includes(q))&&(region==="all"||item.region===region)&&(topic==="all"||item.topic===topic)&&(source==="all"||item.source===source);
    });
    const filtered=source==="all"?diversifyNews(filteredBase):filteredBase.sort((a,b)=>Date.parse(b.published_at||0)-Date.parse(a.published_at||0));
    $("#newsList").innerHTML=filtered.length?filtered.map(item=>{
      const related=Number(item.duplicate_count||item.related_count||0);
      return `<a class="news-card" href="${escapeHtml(safeNewsLink(item))}" target="_blank" rel="noreferrer noopener"><div class="news-source"><span>${escapeHtml(item.source||"財經新聞")}</span><time>${formatTime(item.published_at)}</time></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.summary||"點擊前往原始來源閱讀全文。")}</p><div class="tag-row"><span class="tag">${escapeHtml(item.region||"GLOBAL")}</span><span class="tag">${escapeHtml(item.topic||"market")}</span>${item.source_group?`<span class="tag">${escapeHtml(item.source_group)}</span>`:""}${related?`<span class="tag">另有 ${related} 篇相關</span>`:""}<span class="tag">原始文章 ↗</span></div></a>`;
    }).join(""):'<div class="empty" style="grid-column:1/-1">目前沒有符合篩選的新聞。</div>';
  }
  ["newsSearch","newsRegion","newsTopic","newsSource"].forEach(id=>$("#"+id).addEventListener(id==="newsSearch"?"input":"change",render));render();
  let refreshBusy=false;
  async function refreshNews(){
    if(refreshBusy||document.hidden)return;
    refreshBusy=true;
    try{
      const latest=await loadData("news.json",payload);
      if(Date.parse(latest?.metadata?.updated_at||0)>Date.parse(payload?.metadata?.updated_at||0)){
        location.reload();
      }
    }catch(error){console.warn("News page refresh failed:",error)}
    finally{refreshBusy=false}
  }
  setInterval(refreshNews,5*60_000);
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshNews()});
})();
