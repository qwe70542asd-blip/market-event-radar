(async()=>{
  "use strict";
  const {$,escapeHtml,fmt,loadData}=MR;
  const [audit,coverage,yahooPayload,etfPayload,assetsPayload,dividendPayload,verificationPayload]=await Promise.all([
    loadData("asset-audit.json",window.__ASSET_AUDIT_SEED__||{assets:[],summary:{}}),
    loadData("asset-coverage.json",{summary:{}}),
    loadData("yahoo-details.json",window.__YAHOO_DETAILS_SEED__||{items:{},metadata:{}}),
    loadData("etf-details.json",window.__ETF_DETAILS_SEED__||{items:{},metadata:{}}),
    loadData("assets.json",window.__ASSETS_SEED__||{assets:[]}),
    loadData("dividend-history.json",window.__DIVIDEND_HISTORY_SEED__||{items:{}}),
    loadData("data-verification.json",window.__DATA_VERIFICATION_SEED__||{items:{}})
  ]);
  const summary=audit.summary||coverage.summary||{},yahoo=yahooPayload.items||{},etfs=etfPayload.items||{},dividends=dividendPayload.items||{},verification=verificationPayload.items||{};
  const assetMap=new Map((assetsPayload.assets||[]).map(asset=>[String(asset.symbol),asset]));
  const has=value=>{
    if(value===null||value===undefined)return false;
    if(typeof value==="string")return Boolean(value.trim());
    if(Array.isArray(value))return value.length>0;
    if(typeof value==="object")return Object.keys(value).length>0;
    return true;
  };
  const list=value=>Array.isArray(value)?value:Array.isArray(value?.rows)?value.rows:[];
  const firstValue=(...values)=>values.find(has);
  const firstList=(...values)=>values.map(list).find(rows=>rows.length)||[];
  const mergeNonempty=(...objects)=>{
    const result={};
    for(const object of objects){
      for(const [key,value] of Object.entries(object||{}))if(has(value)&&!has(result[key]))result[key]=value;
    }
    return result;
  };
  const deriveAllocations=holdings=>{
    const totals=new Map();
    for(const holding of holdings||[]){
      const sector=holding.sector||holding.industry||holding.industry_name;
      const weight=Number(holding.weight);
      if(!sector||!Number.isFinite(weight))continue;
      totals.set(sector,(totals.get(sector)||0)+weight);
    }
    return [...totals].map(([name,weight])=>({name,weight}));
  };
  const fallbackRows=(assetsPayload.assets||[]).filter(asset=>asset.market==="TW"&&["stock","etf"].includes(asset.asset_class)).map(asset=>({
    symbol:asset.symbol,name:asset.name,asset_class:asset.asset_class,exchange:asset.exchange,coverage_percent:0,missing_fields:[]
  }));
  const sourceRows=(audit.assets||[]).length?(audit.assets||[]):fallbackRows;

  const patched=row=>{
    const symbol=String(row.symbol),asset=assetMap.get(symbol)||{},ref=yahoo[symbol]||{},metrics=mergeNonempty(asset.metrics||{},ref.metrics||{}),financials=firstList(asset.financials,ref.financials);
    const officialEtf=asset.etf||{},yahooEtf=ref.etf||{},detailEtf=etfs[symbol]||{};
    const etf=mergeNonempty(officialEtf,detailEtf,yahooEtf);
    const distributionRows=firstList(officialEtf.distributions,detailEtf.distributions,ref.dividends,(dividends[symbol]||{}).rows,dividends[symbol]);
    const holdings=firstList(officialEtf.holdings,detailEtf.holdings,yahooEtf.holdings);
    let allocations=firstList(officialEtf.allocations,officialEtf.sector_allocation,detailEtf.allocations,detailEtf.sector_allocation,yahooEtf.allocations,yahooEtf.sector_allocation);
    if(!allocations.length)allocations=deriveAllocations(holdings);
    const fundProfile={
      formal_name:firstValue(officialEtf.formal_name,asset.name,detailEtf.formal_name,ref.profile?.company_name),
      issuer:firstValue(officialEtf.issuer,officialEtf.family,detailEtf.issuer,detailEtf.family,yahooEtf.issuer,yahooEtf.family),
      manager:firstValue(officialEtf.manager,detailEtf.manager,yahooEtf.manager),
      category:firstValue(officialEtf.category,asset.sub_industry,detailEtf.category,yahooEtf.category),
      strategy:firstValue(officialEtf.strategy,detailEtf.strategy,yahooEtf.strategy),
      benchmark:firstValue(officialEtf.benchmark,detailEtf.benchmark,yahooEtf.benchmark)
    };
    const fundMasterComplete=has(fundProfile.formal_name)&&has(fundProfile.issuer);
    const fundMasterPartial=has(fundProfile.formal_name)&&Object.values(fundProfile).filter(has).length>=2;
    const dividendComplete=distributionRows.length>0;
    const dividendPartial=!dividendComplete&&has(firstValue(officialEtf.distribution_frequency,detailEtf.distribution_frequency,yahooEtf.distribution_frequency));
    const holdingsComplete=holdings.length>=10;
    const holdingsPartial=holdings.length>0;
    const allocationsComplete=allocations.length>0;
    const status=(complete,partial=false)=>complete?"complete":partial?"partial":"missing";
    const categories=row.asset_class==="etf"?[
      ["基金主檔",status(fundMasterComplete,fundMasterPartial)],
      ["配息",status(dividendComplete,dividendPartial)],
      ["持股",status(holdingsComplete,holdingsPartial)],
      ["產業配置",status(allocationsComplete,false)]
    ]:[
      ["估值",status(has(metrics.pe)||has(metrics.pb)||has(metrics.dividend_yield))],
      ["財務報表",status(financials.length>=4,financials.length>0)],
      ["財務比率",status(has(metrics.roe)&&has(metrics.debt_ratio)&&has(metrics.net_margin),Object.keys(metrics).length>0)],
      ["歷史財報",status(financials.length>=12,financials.length>=4)]
    ];
    const missing=(row.missing_fields||[]).filter(label=>{
      if(label==="公司名稱")return !has(asset.company_name||asset.name||ref.profile?.company_name);
      if(label==="產業")return !has(asset.official_industry||asset.sub_industry||ref.profile?.industry||ref.profile?.sector);
      if(label==="上市／上櫃日期")return !has(asset.listed_date||officialEtf.listing_date||detailEtf.listing_date);
      if(label==="發行股數")return !has(asset.issued_shares||metrics.shares_outstanding);
      if(["本益比狀態","股價淨值比狀態","殖利率狀態"].includes(label))return !has(metrics[label==="本益比狀態"?"pe":label==="股價淨值比狀態"?"pb":"dividend_yield"]);
      if(["EPS","ROE","負債比","淨利率"].includes(label))return !has(metrics[label==="EPS"?"eps":label==="ROE"?"roe":label==="負債比"?"debt_ratio":"net_margin"]);
      if(label==="最近季度財報")return !financials.length;
      if(label==="歷季財報")return financials.length<4;
      if(label==="基金名稱")return !has(fundProfile.formal_name);
      if(label==="發行投信")return !has(fundProfile.issuer);
      if(label==="基金經理人")return !has(fundProfile.manager);
      if(label==="基金類型")return !has(fundProfile.category);
      if(label==="追蹤指數／主動式")return !(has(fundProfile.benchmark)||String(fundProfile.category||fundProfile.strategy||"").includes("主動"));
      if(label==="投資策略")return !has(fundProfile.strategy||fundProfile.category);
      if(label==="配息資訊")return !(dividendComplete||dividendPartial);
      if(label==="成分股揭露狀態")return !holdingsPartial;
      if(label==="產業配置")return !allocationsComplete;
      return true;
    });
    const checks=categories.length,completeCount=categories.filter(([,state])=>state==="complete").length,partialCount=categories.filter(([,state])=>state==="partial").length;
    const categoryScore=(completeCount+partialCount*.55)/Math.max(1,checks)*100;
    const baseCoverage=Number(row.coverage_percent||0);
    const effective=Math.min(100,Math.max(baseCoverage,Math.round((baseCoverage*.45)+(categoryScore*.55))));
    const finalVerification=verification[symbol]||{};
    return {...row,name:row.name||asset.name,missing_fields:missing,effective,categories,reference:Boolean(ref.updated_at||detailEtf.updated_at||finalVerification.updated_at),sourceSummary:{holdings:holdings.length,allocations:allocations.length,distributions:distributionRows.length}};
  };
  const rows=sourceRows.map(patched),avg=rows.length?rows.reduce((sum,row)=>sum+row.effective,0)/rows.length:0;
  $("#coverageStats").innerHTML=[
    ["稽核標的",summary.audited_assets||summary.total_assets||rows.length],
    ["股票",summary.stock_count||summary.total_stocks||rows.filter(row=>row.asset_class==="stock").length],
    ["ETF",summary.etf_count||summary.total_etfs||rows.filter(row=>row.asset_class==="etf").length],
    ["官方平均",`${fmt(summary.average_field_coverage_percent||0)}%`],
    ["整合後平均",`${fmt(avg)}%`],
    ["多來源已補",new Set([...Object.keys(yahoo),...Object.keys(etfs)]).size]
  ].map(([key,value])=>`<article class="stat"><small>${key}</small><strong>${typeof value==="number"?fmt(value,0):escapeHtml(value)}</strong></article>`).join("");
  const stateText=state=>state==="complete"?"✓":state==="partial"?"部分":"待補";
  $("#coverageRows").innerHTML=rows.map(row=>{
    const summaryText=row.categories.map(([name,state])=>`${name}${stateText(state)}`).join(" · ");
    const detail=row.asset_class==="etf"&&row.sourceSummary?`持股 ${row.sourceSummary.holdings} 檔、產業 ${row.sourceSummary.allocations} 類、配息 ${row.sourceSummary.distributions} 筆`:"點入標的查看來源、期間與公式";
    return `<tr><td><a href="asset.html?symbol=${encodeURIComponent(row.symbol)}">${escapeHtml(row.symbol)}</a></td><td>${escapeHtml(row.name||"")}</td><td>${escapeHtml(row.asset_class||"")}</td><td>${fmt(row.effective)}% ${row.reference?'<span class="verification-badge reference">多來源整合</span>':""}</td><td>${escapeHtml(summaryText)}</td><td>${row.missing_fields?.length?`尚缺 ${row.missing_fields.length} 項；${escapeHtml(detail)}`:`已達目前可驗證範圍；${escapeHtml(detail)}`}</td></tr>`;
  }).join("")||'<tr><td colspan="6" class="empty">等待完整資料稽核</td></tr>';
})();
