(async()=>{
  "use strict";
  const {$,escapeHtml,loadData,formatTime,mergeAssets,finite}=MR;
  const [auditPayload,assetPayload]=await Promise.all([
    loadData("asset-audit.json",window.__ASSET_AUDIT_SEED__||{summary:{},assets:[]}),
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]})
  ]);
  const assets=mergeAssets(assetPayload.assets||[],(window.__ASSET_SEED__||{}).assets||[]);
  const assetMap=new Map(assets.map(asset=>[String(asset.id||`TW:${asset.symbol}`),asset]));
  const summary=auditPayload.summary||{};
  const rows=auditPayload.assets||[];
  const reasonLabels={
    master_parse_missing:"主檔欄位解析失敗",
    awaiting_filing_or_parser_mismatch:"等待公告或財報格式尚未解析",
    valuation_source_missing:"估值來源尚未取得",
    balance_sheet_parser_mismatch:"資產負債表格式尚未解析",
    no_parsed_financial_statement:"沒有成功解析最近財報",
    quarter_history_incomplete:"歷季財報尚未完整",
    etf_master_or_prospectus_missing:"ETF 主檔或公開說明書尚未取得",
    etf_master_missing:"ETF 主檔尚未取得",
    market_source_missing:"行情來源尚未取得",
    chip_source_missing:"法人資料尚未取得",
    non_credit_or_source_missing:"非信用交易標的或融資券來源未取得",
    not_eligible_or_source_missing:"不可當沖或當沖來源未取得",
    no_recent_matching_news:"最近新聞沒有成功配對",
    no_dividend_record_or_parser_missing:"無股利紀錄或股利格式尚未解析",
    not_applicable_financial_industry:"金融業不適用一般流動比率",
    not_applicable_non_positive_eps:"EPS 非正數，本益比不適用"
  };

  const updateStatus=auditPayload.metadata?.asset_update_status||"unknown";
  const updateMessage=auditPayload.metadata?.asset_update_message||"";
  $("#coverageUpdated").textContent=auditPayload.metadata?.updated_at
    ?`更新 ${formatTime(auditPayload.metadata.updated_at)} · ${updateStatus==="ok"?"資料更新成功":"沿用上次成功資料"}`
    :"等待第一次完整排程";
  $("#coverageUpdated").title=updateMessage;

  $("#coverageStats").innerHTML=[
    ["已檢查標的",summary.audited_assets??0,"全部逐檔"],
    ["上市櫃股票",summary.stock_count??0,"不抽查"],
    ["台灣 ETF",summary.etf_count??0,"不抽查"],
    ["必要欄位完整",summary.complete??0,"無必要缺漏"],
    ["仍需補齊",Number(summary.partial||0)+Number(summary.unresolved||0),"會逐項列出"]
  ].map(([label,value,note])=>`<article class="stat"><span>${escapeHtml(label)}</span><strong>${Number(value).toLocaleString("zh-TW")}</strong><small>${escapeHtml(note)}</small></article>`).join("");

  const fieldStats=summary.field_stats||{};
  $("#fieldCoverage").innerHTML=Object.entries(fieldStats).map(([field,row])=>{
    const applicable=Number(row.applicable||0);
    const available=Number(row.available||0);
    const pct=row.coverage_percent===null||row.coverage_percent===undefined?null:Number(row.coverage_percent);
    return`<article class="audit-field-card">
      <span>${escapeHtml(row.label||field)}</span>
      <strong>${pct===null?"不列入必要分母":`${pct.toFixed(1)}%`}</strong>
      <p>${available.toLocaleString("zh-TW")} / ${applicable.toLocaleString("zh-TW")} 個適用標的</p>
      <small>缺少 ${Number(row.missing||0).toLocaleString("zh-TW")} · 不適用／選配 ${Number(row.not_applicable||0).toLocaleString("zh-TW")}</small>
    </article>`;
  }).join("")||'<div class="empty">等待第一次完整稽核。</div>';

  const reasons=Object.entries(summary.reason_counts||{});
  $("#reasonGrid").innerHTML=reasons.length?reasons.map(([reason,count])=>`<article class="reason-card"><span>${escapeHtml(reasonLabels[reason]||reason)}</span><strong>${Number(count).toLocaleString("zh-TW")}</strong><small>${escapeHtml(reason)}</small></article>`).join(""):'<div class="empty">目前沒有必要欄位缺漏。</div>';

  function checkValue(check){
    if(check.available){
      if(typeof check.value==="number")return Number(check.value).toLocaleString("zh-TW",{maximumFractionDigits:2});
      if(typeof check.value==="string")return check.value;
      if(check.value&&typeof check.value==="object"){
        if(check.value.periods!==undefined)return`${check.value.periods} / 預期 ${check.value.expected}`;
        return"已取得";
      }
      return"已取得";
    }
    return reasonLabels[check.reason]||check.reason||"尚未取得";
  }

  function showDetail(id){
    const row=rows.find(item=>String(item.id)===String(id));
    const asset=assetMap.get(String(id));
    const container=$("#coverageDetail");
    container.hidden=false;
    if(!row){container.innerHTML='<div class="empty">找不到這個稽核項目。</div>';return}
    const required=row.checks.filter(check=>check.required);
    const optional=row.checks.filter(check=>!check.required);
    const financials=asset?.financials||[];
    const periods=financials.map(item=>`${item.year||"—"} Q${item.quarter||"—"}`).join("、")||"尚未解析";
    const mops=`https://mopsov.twse.com.tw/mops/web/ezsearch?co_id=${encodeURIComponent(row.symbol||"")}`;
    container.innerHTML=`<article class="coverage-detail-card full-audit-detail">
      <div class="coverage-detail-head"><div><span class="asset-badge">${escapeHtml(row.exchange||"TW")}</span><h2>${escapeHtml(row.symbol||"")} ${escapeHtml(row.name||"")}</h2><p>${escapeHtml(row.industry||row.asset_class||"")}</p></div><strong>${Number(row.coverage_percent||0).toFixed(1)}%</strong></div>
      <div class="audit-detail-summary"><span>狀態：<b>${row.status==="complete"?"完整":row.status==="partial"?"部分缺漏":"嚴重缺漏"}</b></span><span>必要欄位：${row.available_required_count} / ${row.required_count}</span><span>已保存財報：${financials.length} 期</span></div>
      <h3>必要欄位逐項檢查</h3><div class="audit-check-grid">${required.map(check=>`<div class="audit-check ${check.available?"check-ok":"check-missing"}"><span>${escapeHtml(check.label)}</span><strong>${escapeHtml(checkValue(check))}</strong><small>${check.available?"已取得":escapeHtml(check.reason||"")}</small></div>`).join("")}</div>
      <h3>選配／可能不適用欄位</h3><div class="audit-check-grid">${optional.map(check=>`<div class="audit-check ${check.available?"check-ok":"check-optional"}"><span>${escapeHtml(check.label)}</span><strong>${escapeHtml(checkValue(check))}</strong><small>${check.available?"已取得":"不阻塞完整狀態"}</small></div>`).join("")}</div>
      <div class="coverage-explanation"><h3>歷季財報</h3><p>${escapeHtml(periods)}</p><h3>尚缺必要內容</h3><p>${row.missing_required.length?row.missing_required.map(item=>`${item.label}（${reasonLabels[item.reason]||item.reason}）`).join("、"):"無"}</p></div>
      <div class="official-links"><a href="${mops}" target="_blank" rel="noreferrer">公開資訊觀測站查詢 ↗</a></div>
    </article>`;
    container.scrollIntoView({behavior:"smooth",block:"nearest"});
  }

  function render(){
    const query=String($("#coverageSearch").value||"").trim().toLowerCase();
    const cls=$("#coverageClass").value;
    const status=$("#coverageStatus").value;
    const filtered=rows.filter(row=>{
      const hay=`${row.symbol||""} ${row.name||""} ${row.industry||""}`.toLowerCase();
      return(!query||hay.includes(query))&&(cls==="all"||row.asset_class===cls)&&(status==="all"||row.status===status);
    });
    $("#auditResultNote").textContent=`顯示 ${filtered.length.toLocaleString("zh-TW")} / ${rows.length.toLocaleString("zh-TW")} 檔；完整稽核覆蓋率 ${Number(summary.audit_coverage_percent||0).toFixed(1)}%。`;
    $("#coverageRows").innerHTML=filtered.length?filtered.map(row=>`<tr>
      <td><button class="coverage-stock-button" type="button" data-audit-id="${escapeHtml(row.id)}"><strong>${escapeHtml(row.symbol||"")}</strong></button></td>
      <td>${escapeHtml(row.name||"")}</td>
      <td><small>${escapeHtml(row.asset_class==="etf"?"ETF":"股票")}</small><strong>${escapeHtml(row.exchange||"")}</strong></td>
      <td>${Number(row.available_required_count||0)} / ${Number(row.required_count||0)}</td>
      <td><span class="audit-status ${escapeHtml(row.status||"")}">${Number(row.coverage_percent||0).toFixed(1)}%</span></td>
      <td>${row.missing_required.length?escapeHtml(row.missing_required.slice(0,4).map(item=>item.label).join("、"))+(row.missing_required.length>4?`＋${row.missing_required.length-4}`:""):"完整"}</td>
    </tr>`).join(""):'<tr><td colspan="6"><div class="empty">沒有符合篩選條件的標的。</div></td></tr>';
    document.querySelectorAll("[data-audit-id]").forEach(button=>button.addEventListener("click",()=>showDetail(button.dataset.auditId)));
  }

  ["coverageSearch","coverageClass","coverageStatus"].forEach(id=>$("#"+id).addEventListener(id==="coverageSearch"?"input":"change",render));
  render();
})();
