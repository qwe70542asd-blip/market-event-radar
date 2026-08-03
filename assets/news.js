(async()=>{
  "use strict";

  const {$,escapeHtml,loadData,safeNewsLink,formatTime,diversifyNews}=MR;
  let payload=await loadData("news.json",window.__NEWS_SEED__||{items:[],sources:[],metadata:{}});
  let items=payload.items||[];
  let sourceRows=payload.sources||[];
  const metadata=payload.metadata||{};

  const topicLabels={
    material:"重大訊息",earnings:"財報／營收",dividend:"股利／除權息",
    fund:"ETF／基金",policy:"政策／總經",industry:"產業",
    market:"市場",crypto:"虛擬貨幣"
  };
  const groupLabels={
    "official-company":"上市櫃重大訊息",official:"官方機關",publisher:"財經／一般媒體",
    technology:"科技媒體",portal:"入口網站",broker:"券商／投顧",
    "fund-house":"投信",broad:"廣域搜尋",discovered:"額外發現媒體"
  };
  const statusLabels={
    ok:"正常",empty:"正常／本輪無新文",warning:"暫時失敗",
    scheduled:"輪替待檢",discovered:"廣域發現",disabled:"停用"
  };

  const itemSources=[...new Set(items.map(item=>item.source).filter(Boolean))].sort((a,b)=>a.localeCompare(b,"zh-Hant"));
  $("#newsSource").innerHTML='<option value="all">全部來源</option>'+
    itemSources.map(source=>`<option value="${escapeHtml(source)}">${escapeHtml(source)}</option>`).join("");

  $("#newsCount").textContent=Number(metadata.item_count??items.length).toLocaleString("zh-TW");
  $("#materialCount").textContent=Number(metadata.material_item_count??items.filter(item=>item.topic==="material").length).toLocaleString("zh-TW");
  $("#activeSourceCount").textContent=Number(metadata.active_source_count??itemSources.length).toLocaleString("zh-TW");
  $("#configuredSourceCount").textContent=Number(metadata.configured_source_count??sourceRows.length).toLocaleString("zh-TW");
  $("#newsUpdated").textContent=`更新 ${formatTime(metadata.updated_at)} · 本輪檢查 ${Number(metadata.checked_source_count||0)} 個來源 · 輪替 ${metadata.rotation_bucket||"—"}/${metadata.rotation_buckets||"—"}`;

  function renderSourceSummary(){
    const configured=Number(metadata.configured_source_count||sourceRows.filter(row=>row.group!=="discovered").length);
    const healthy=Number(metadata.healthy_source_count||sourceRows.filter(row=>["ok","empty"].includes(row.status)).length);
    const warnings=Number(metadata.warning_source_count||sourceRows.filter(row=>row.status==="warning").length);
    const active=Number(metadata.active_source_count||itemSources.length);
    const discovered=Number(metadata.discovered_source_count||sourceRows.filter(row=>row.group==="discovered").length);
    $("#sourceHealthStats").innerHTML=[
      ["設定來源",configured,"官方＋媒體＋券商＋投信"],
      ["正常／可沿用",healthy,"成功或本輪無新文"],
      ["暫時失敗",warnings,"保留上次成功資料"],
      ["活躍媒體",active,"目前新聞資料中有內容"],
      ["額外發現",discovered,"廣域搜尋自動找到"]
    ].map(([label,value,note])=>`<article><span>${escapeHtml(label)}</span><strong>${Number(value).toLocaleString("zh-TW")}</strong><small>${escapeHtml(note)}</small></article>`).join("");
  }

  function sourceCard(row){
    const status=row.status||"scheduled";
    const cls=status==="warning"?"source-warning":status==="ok"?"source-ok":status==="empty"?"source-empty":status==="discovered"?"source-discovered":"source-scheduled";
    const checked=row.last_checked_at?formatTime(row.last_checked_at):"尚未檢查";
    const success=row.last_success_at?`最後成功 ${formatTime(row.last_success_at)}`:"尚無成功紀錄";
    const body=`<article class="source-card ${cls}">
      <div class="source-card-head"><strong>${escapeHtml(row.name||"未命名來源")}</strong><span>${escapeHtml(statusLabels[status]||status)}</span></div>
      <small>${escapeHtml(groupLabels[row.group]||row.group||"其他來源")} · ${escapeHtml(row.method||"來源")}</small>
      <p>${escapeHtml(row.message||"等待更新")}</p>
      <footer><span>${escapeHtml(checked)}</span><span>${escapeHtml(success)}</span></footer>
    </article>`;
    return row.homepage
      ?`<a class="source-card-link" href="${escapeHtml(row.homepage)}" target="_blank" rel="noreferrer noopener">${body}</a>`
      :body;
  }

  function renderSourceHealth(){
    const query=String($("#sourceHealthSearch").value||"").trim().toLowerCase();
    const group=$("#sourceHealthGroup").value;
    const status=$("#sourceHealthStatus").value;
    const rows=sourceRows.filter(row=>{
      const text=`${row.name||""} ${row.group||""} ${row.message||""}`.toLowerCase();
      return(!query||text.includes(query))&&(group==="all"||row.group===group)&&(status==="all"||row.status===status);
    });
    $("#sourceGrid").innerHTML=rows.length
      ?rows.map(sourceCard).join("")
      :'<div class="empty" style="grid-column:1/-1">沒有符合篩選條件的來源。</div>';
  }

  function newsSort(rows){
    const mode=$("#newsSort").value;
    if(mode==="latest"){
      return rows.sort((a,b)=>Date.parse(b.published_at||0)-Date.parse(a.published_at||0));
    }
    return rows.sort((a,b)=>{
      const score=Number(b.importance_score||0)-Number(a.importance_score||0);
      if(score)return score;
      return Date.parse(b.published_at||0)-Date.parse(a.published_at||0);
    });
  }

  function renderNews(){
    const query=String($("#newsSearch").value||"").trim().toLowerCase();
    const region=$("#newsRegion").value;
    const topic=$("#newsTopic").value;
    const source=$("#newsSource").value;

    const filtered=items.filter(item=>{
      const text=`${item.title||""} ${item.summary||""} ${item.source||""} ${(item.asset_symbols||[]).join(" ")} ${(item.tags||[]).join(" ")}`.toLowerCase();
      return(!query||text.includes(query))&&
        (region==="all"||item.region===region)&&
        (topic==="all"||item.topic===topic)&&
        (source==="all"||item.source===source);
    });

    let rows=newsSort([...filtered]);
    if(source==="all"&&$("#newsSort").value==="latest")rows=diversifyNews(rows);

    $("#newsList").innerHTML=rows.length?rows.map(item=>{
      const related=Number(item.duplicate_count||item.related_count||0);
      const importance=Number(item.importance_score||0);
      const importanceTag=importance>=85?'<span class="tag critical-tag">重大</span>':importance>=65?'<span class="tag high-tag">重要</span>':"";
      const symbols=(item.asset_symbols||[]).slice(0,4).map(symbol=>`<span class="tag symbol-tag">${escapeHtml(symbol)}</span>`).join("");
      return`<a class="news-card ${item.topic==="material"?"material-news-card":""}" href="${escapeHtml(safeNewsLink(item))}" target="_blank" rel="noreferrer noopener">
        <div class="news-source"><span>${escapeHtml(item.source||"財經新聞")}</span><time>${formatTime(item.published_at)}</time></div>
        <h3>${escapeHtml(item.title)}</h3>
        <p>${escapeHtml(item.summary||"點擊前往原始來源閱讀全文。")}</p>
        <div class="tag-row">
          ${importanceTag}
          ${symbols}
          <span class="tag">${escapeHtml(item.region||"GLOBAL")}</span>
          <span class="tag">${escapeHtml(topicLabels[item.topic]||item.topic||"市場")}</span>
          ${item.source_group?`<span class="tag">${escapeHtml(groupLabels[item.source_group]||item.source_group)}</span>`:""}
          ${related?`<span class="tag">另有 ${related} 篇相關</span>`:""}
          <span class="tag">原始文章 ↗</span>
        </div>
      </a>`;
    }).join(""):'<div class="empty" style="grid-column:1/-1">目前沒有符合篩選的新聞。</div>';
  }

  renderSourceSummary();
  renderSourceHealth();
  renderNews();

  ["newsSearch","newsRegion","newsTopic","newsSource","newsSort"].forEach(id=>{
    $("#"+id).addEventListener(id==="newsSearch"?"input":"change",renderNews);
  });
  ["sourceHealthSearch","sourceHealthGroup","sourceHealthStatus"].forEach(id=>{
    $("#"+id).addEventListener(id==="sourceHealthSearch"?"input":"change",renderSourceHealth);
  });

  let refreshBusy=false;
  async function refreshNews(){
    if(refreshBusy||document.hidden)return;
    refreshBusy=true;
    try{
      const latest=await loadData("news.json",payload);
      if(Date.parse(latest?.metadata?.updated_at||0)>Date.parse(payload?.metadata?.updated_at||0)){
        location.reload();
      }
    }catch(error){
      console.warn("News page refresh failed:",error);
    }finally{
      refreshBusy=false;
    }
  }
  setInterval(refreshNews,5*60_000);
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshNews()});
})();