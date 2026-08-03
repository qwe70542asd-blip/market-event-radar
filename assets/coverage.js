(async()=>{
  "use strict";
  const {$,escapeHtml,loadData,formatTime}=MR;
  const payload=await loadData("asset-coverage.json",{summary:{},missing_stocks:[],partial_stocks:[]});
  const summary=payload.summary||{};
  $("#coverageUpdated").textContent=payload.metadata?.updated_at?`更新 ${formatTime(payload.metadata.updated_at)}`:"等待官方資料排程";
  $("#coverageStats").innerHTML=[
    ["全部股票",summary.total_stocks??0],
    ["完整 6/8 以上",summary.complete??0],
    ["部分資料",summary.partial_or_basic??0],
    ["完全缺漏",summary.missing??0]
  ].map(([label,value])=>`<article class="stat"><span>${label}</span><strong>${Number(value).toLocaleString("zh-TW")}</strong></article>`).join("");
  const labels={eps:"EPS",pe:"本益比",pb:"股價淨值比",dividend_yield:"殖利率",roe:"ROE",debt_ratio:"負債比",current_ratio:"流動比率",net_margin:"淨利率"};
  $("#fieldCoverage").innerHTML=Object.entries(summary.field_counts||{}).map(([field,count])=>{
    const pct=summary.total_stocks?Number(count)/Number(summary.total_stocks)*100:0;
    return `<article class="info-card"><span>${escapeHtml(labels[field]||field)}</span><strong>${Number(count).toLocaleString("zh-TW")} 檔 · ${pct.toFixed(1)}%</strong></article>`;
  }).join("")||'<div class="empty">等待第一次官方覆蓋稽核。</div>';
  const rows=[
    ...(payload.missing_stocks||[]).map(row=>({...row,coverage:0,status:"缺漏"})),
    ...(payload.partial_stocks||[]).map(row=>({...row,status:"部分"}))
  ];
  function render(){
    const q=String($("#coverageSearch").value||"").trim().toLowerCase();
    const filtered=rows.filter(row=>!q||`${row.symbol||""} ${row.name||""}`.toLowerCase().includes(q));
    $("#coverageRows").innerHTML=filtered.length?filtered.slice(0,1000).map(row=>`<tr><td><a href="asset.html?id=TW:${escapeHtml(row.symbol)}"><strong>${escapeHtml(row.symbol)}</strong></a></td><td>${escapeHtml(row.name||"")}</td><td><small>${escapeHtml(row.exchange||"")}</small><strong>${escapeHtml(row.industry||"")}</strong></td><td>${row.status==="缺漏"?"0 / 8":`${Number(row.coverage||0)} / 8`}</td><td>${escapeHtml((row.missing||[]).map(field=>labels[field]||field).join("、"))}</td></tr>`).join(""):'<tr><td colspan="5"><div class="empty">目前沒有符合搜尋的缺漏資料。</div></td></tr>';
  }
  $("#coverageSearch").addEventListener("input",render);render();
})();