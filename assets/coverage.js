(async()=>{
  "use strict";
  const {$,escapeHtml,loadData,formatTime,mergeAssets,finite}=MR;
  const [payload,assetPayload]=await Promise.all([
    loadData("asset-coverage.json",{summary:{},missing_stocks:[],partial_stocks:[]}),
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]})
  ]);
  const assets=mergeAssets(assetPayload.assets||[],(window.__ASSET_SEED__||{}).assets||[]);
  const assetMap=new Map(assets.map(asset=>[String(asset.symbol||""),asset]));
  const summary=payload.summary||{};
  const labels={eps:"EPS",pe:"本益比",pb:"股價淨值比",dividend_yield:"殖利率",roe:"ROE",debt_ratio:"負債比",current_ratio:"流動比率",net_margin:"淨利率"};

  $("#coverageUpdated").textContent=payload.metadata?.updated_at?`更新 ${formatTime(payload.metadata.updated_at)}`:"等待官方資料排程";
  $("#coverageStats").innerHTML=[
    ["全部股票",summary.total_stocks??0],["完整 6/8 以上",summary.complete??0],
    ["部分資料",summary.partial_or_basic??0],["完全缺漏",summary.missing??0]
  ].map(([label,value])=>`<article class="stat"><span>${label}</span><strong>${Number(value).toLocaleString("zh-TW")}</strong></article>`).join("");

  $("#fieldCoverage").innerHTML=Object.entries(summary.field_counts||{}).map(([field,count])=>{
    const pct=summary.total_stocks?Number(count)/Number(summary.total_stocks)*100:0;
    return`<article class="info-card"><span>${escapeHtml(labels[field]||field)}</span><strong>${Number(count).toLocaleString("zh-TW")} 檔 · ${pct.toFixed(1)}%</strong></article>`;
  }).join("")||'<div class="empty">等待第一次官方覆蓋稽核。</div>';

  const rows=[
    ...(payload.missing_stocks||[]).map(row=>({...row,coverage:0,status:"缺漏"})),
    ...(payload.partial_stocks||[]).map(row=>({...row,status:"部分"}))
  ];

  function valueText(value,suffix=""){
    return finite(value)===null?"尚未解析":`${Number(value).toLocaleString("zh-TW",{maximumFractionDigits:2})}${suffix}`;
  }

  function showDetail(symbol){
    const asset=assetMap.get(String(symbol));
    const container=$("#coverageDetail");
    container.hidden=false;
    if(!asset){
      container.innerHTML='<div class="empty">主檔尚未找到這個代碼。</div>';
      return;
    }
    const metrics=asset.metrics||{};
    const financials=asset.financials||[];
    const missing=asset.analysis_coverage?.missing||[];
    const mops=`https://mopsov.twse.com.tw/mops/web/ezsearch?co_id=${encodeURIComponent(asset.symbol)}`;
    const valuation=asset.exchange==="TPEx"
      ?"https://www.tpex.org.tw/zh-tw/mainboard/trading/info/peratio.html"
      :"https://www.twse.com.tw/zh/trading/historical/bwibbu-day.html";
    container.innerHTML=`<article class="coverage-detail-card">
      <div class="coverage-detail-head"><div>
        <span class="asset-badge">${escapeHtml(asset.exchange||"TW")}</span>
        <h2>${escapeHtml(asset.symbol)} ${escapeHtml(asset.name)}</h2>
        <p>${escapeHtml(asset.official_industry||asset.sub_industry||"產業待分類")}</p>
      </div><strong>${asset.analysis_coverage?.count||0} / 8</strong></div>
      <div class="coverage-metric-grid">${[
        ["EPS",valueText(metrics.eps)],["本益比",valueText(metrics.pe)],["股價淨值比",valueText(metrics.pb)],
        ["殖利率",valueText(metrics.dividend_yield,"%")],["ROE",valueText(metrics.roe,"%")],
        ["負債比",valueText(metrics.debt_ratio,"%")],["流動比率",valueText(metrics.current_ratio)],
        ["淨利率",valueText(metrics.net_margin,"%")]
      ].map(([label,value])=>`<div><span>${label}</span><strong>${value}</strong></div>`).join("")}</div>
      <div class="coverage-explanation">
        <h3>目前缺少</h3><p>${missing.length?missing.map(field=>labels[field]||field).join("、"):"無"}</p>
        <h3>判讀方式</h3><p>0 / 8 表示更新程式目前沒有從官方欄位成功解析，不等於公司沒有財報。金融業、特殊產業與尚未申報最新季度的公司，欄位格式可能不同。</p>
        <h3>已保存財報季度</h3><p>${financials.length?financials.map(row=>`${row.year||"—"} Q${row.quarter||"—"}`).slice(0,8).join("、"):"目前尚未保存可用季度"}</p>
      </div>
      <div class="official-links">
        <a href="${mops}" target="_blank" rel="noreferrer">公開資訊觀測站查詢 ↗</a>
        <a href="${valuation}" target="_blank" rel="noreferrer">官方估值資料 ↗</a>
      </div>
    </article>`;
    container.scrollIntoView({behavior:"smooth",block:"nearest"});
  }

  function render(){
    const q=String($("#coverageSearch").value||"").trim().toLowerCase();
    const filtered=rows.filter(row=>!q||`${row.symbol||""} ${row.name||""}`.toLowerCase().includes(q));
    $("#coverageRows").innerHTML=filtered.length?filtered.slice(0,1000).map(row=>`<tr>
      <td><button class="coverage-stock-button" type="button" data-coverage-symbol="${escapeHtml(row.symbol)}"><strong>${escapeHtml(row.symbol)}</strong></button></td>
      <td>${escapeHtml(row.name||"")}</td>
      <td><small>${escapeHtml(row.exchange||"")}</small><strong>${escapeHtml(row.industry||"")}</strong></td>
      <td>${row.status==="缺漏"?"0 / 8":`${Number(row.coverage||0)} / 8`}</td>
      <td>${escapeHtml((row.missing||[]).map(field=>labels[field]||field).join("、"))}</td>
    </tr>`).join(""):'<tr><td colspan="5"><div class="empty">目前沒有符合搜尋的缺漏資料。</div></td></tr>';
    document.querySelectorAll("[data-coverage-symbol]").forEach(button=>button.addEventListener("click",()=>showDetail(button.dataset.coverageSymbol)));
  }

  $("#coverageSearch").addEventListener("input",render);
  render();
})();