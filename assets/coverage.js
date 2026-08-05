(async()=>{
  "use strict";
  const {$,escapeHtml,fmt,loadData}=MR;
  const [audit,coverage,yahooPayload,etfPayload]=await Promise.all([
    loadData("asset-audit.json",window.__ASSET_AUDIT_SEED__||{assets:[],summary:{}}),
    loadData("asset-coverage.json",{summary:{}}),
    loadData("yahoo-details.json",window.__YAHOO_DETAILS_SEED__||{items:{},metadata:{}}),
    loadData("etf-details.json",window.__ETF_DETAILS_SEED__||{items:{},metadata:{}})
  ]);
  const summary=audit.summary||coverage.summary||{},yahoo=yahooPayload.items||{},etfs=etfPayload.items||{};
  const has=value=>value!==null&&value!==undefined&&String(value).trim()!=="";
  const patched=row=>{
    const ref=yahoo[row.symbol]||{},metrics=ref.metrics||{},financials=ref.financials||[],etf={...(ref.etf||{}),...(etfs[row.symbol]||{})};
    const missing=(row.missing_fields||[]).filter(label=>{
      if(label==="發行股數")return !has(metrics.shares_outstanding);
      if(["本益比狀態","股價淨值比狀態","殖利率狀態"].includes(label))return !has(metrics[label==="本益比狀態"?"pe":label==="股價淨值比狀態"?"pb":"dividend_yield"]);
      if(["EPS","ROE","負債比","淨利率"].includes(label))return !has(metrics[label==="EPS"?"eps":label==="ROE"?"roe":label==="負債比"?"debt_ratio":"net_margin"]);
      if(label==="最近季度財報")return !financials.length;
      if(label==="歷季財報")return financials.length<4;
      if(label==="發行投信")return !has(etf.issuer||etf.family);
      if(label==="投資策略")return !has(etf.strategy||etf.category);
      if(label==="配息資訊")return !(etf.distributions||ref.dividends||[]).length;
      if(label==="成分股揭露狀態")return !(etf.holdings||[]).length;
      return true;
    });
    const total=Math.max(1,(row.missing_fields||[]).length+Math.round(Number(row.coverage_percent||0)/100*14));
    const effective=Math.min(100,Math.round((total-missing.length)/total*100));
    const categories=row.asset_class==="etf"?[
      ["基金主檔",has(etf.issuer||etf.family)&&has(etf.formal_name||row.name)],
      ["配息",Boolean((etf.distributions||ref.dividends||[]).length)],
      ["持股",Boolean((etf.holdings||[]).length)],
      ["產業配置",Boolean((etf.allocations||etf.sector_allocation||[]).length)]
    ]:[
      ["估值",has(metrics.pe)||has(metrics.pb)||has(metrics.dividend_yield)],
      ["財務報表",financials.length>=4],
      ["財務比率",has(metrics.roe)&&has(metrics.debt_ratio)&&has(metrics.net_margin)],
      ["歷史財報",financials.length>=12]
    ];
    return {...row,missing_fields:missing,effective,reference:Boolean(ref.updated_at||etf.updated_at),categories};
  };
  const rows=(audit.assets||[]).map(patched),avg=rows.length?rows.reduce((sum,row)=>sum+row.effective,0)/rows.length:0;
  $("#coverageStats").innerHTML=[
    ["稽核標的",summary.audited_assets||summary.total_assets],
    ["股票",summary.stock_count||summary.total_stocks],
    ["ETF",summary.etf_count||summary.total_etfs],
    ["官方平均",`${fmt(summary.average_field_coverage_percent||0)}%`],
    ["補充後平均",`${fmt(avg)}%`],
    ["Yahoo／ETF 已補",new Set([...Object.keys(yahoo),...Object.keys(etfs)]).size]
  ].map(([key,value])=>`<article class="stat"><small>${key}</small><strong>${typeof value==="number"?fmt(value,0):escapeHtml(value)}</strong></article>`).join("");
  $("#coverageRows").innerHTML=rows.map(row=>{
    const summaryText=row.categories.map(([name,ok])=>`${name}${ok?"✓":"待補"}`).join(" · ");
    return `<tr><td><a href="asset.html?symbol=${encodeURIComponent(row.symbol)}">${escapeHtml(row.symbol)}</a></td><td>${escapeHtml(row.name||"")}</td><td>${escapeHtml(row.asset_class||"")}</td><td>${fmt(row.effective)}% ${row.reference?'<span class="verification-badge reference">多來源補充</span>':""}</td><td>${escapeHtml(summaryText)}</td><td>${row.missing_fields?.length?`尚缺 ${row.missing_fields.length} 項；點入標的查看來源與公式`:`已達目前可驗證範圍`}</td></tr>`;
  }).join("")||'<tr><td colspan="6" class="empty">等待完整資料稽核</td></tr>';
})();
