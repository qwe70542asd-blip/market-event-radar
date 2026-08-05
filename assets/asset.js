(async()=>{
  "use strict";
  const {$,$$,escapeHtml,fmt,pct,cls,formatTime,loadData,loadStockBasics,loadNewsChannels,loadStockNews,finite,stripHtml,normalizeText,renderNewsThumb}=MR;
  const symbol=(new URLSearchParams(location.search).get("symbol")||"2330").toUpperCase();
  const [assetPayload,marketPayload,chipPayload,eventPayload,newsPayload,stockNewsPayload,revenuePayload,dividendPayload,secondaryPayload,verificationPayload,yahooPayload,etfPayload,stockBasicsPayload]=await Promise.all([
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]}),
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),
    loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{items:{},history:{}}),
    loadData("events.json",window.__EVENT_SEED__||{events:[]}),
    loadNewsChannels(),
    loadStockNews(),
    loadData("monthly-revenue.json",window.__MONTHLY_REVENUE_SEED__||{metadata:{status:"waiting"},items:{}}),
    loadData("dividend-history.json",window.__DIVIDEND_HISTORY_SEED__||{metadata:{status:"waiting"},items:{}}),
    loadData("secondary-reference.json",window.__SECONDARY_REFERENCE_SEED__||{metadata:{status:"waiting"},items:{}}),
    loadData("data-verification.json",window.__DATA_VERIFICATION_SEED__||{metadata:{status:"waiting"},items:{}}),
    loadData("yahoo-details.json",window.__YAHOO_DETAILS_SEED__||{metadata:{status:"waiting"},items:{}}),
    loadData("etf-details.json",window.__ETF_DETAILS_SEED__||{metadata:{status:"waiting"},items:{}}),
    loadStockBasics()
  ]);
  const officialQuote=(marketPayload.items||[]).find(row=>String(row.symbol||"").toUpperCase()===symbol)||{};
  const secondaryQuote=(secondaryPayload.items||{})[symbol]||{};
  const quote=Object.keys(officialQuote).length?officialQuote:(secondaryQuote.price!=null?{symbol,name:symbol,price:secondaryQuote.price,previous_close:secondaryQuote.previous_close,status:"secondary-reference",quote_time:secondaryQuote.updated_at,quote_date:secondaryQuote.updated_at}:{});
  const found=(assetPayload.assets||[]).find(row=>String(row.symbol||"").toUpperCase()===symbol);
  const yahoo=(yahooPayload.items||{})[symbol]||{};
  const etfReference=(etfPayload.items||{})[symbol]||{};
  const stockBasic=(stockBasicsPayload.items||{})[symbol]||{};
  const yahooProfile={...stockBasic,...(yahoo.profile||{})},yahooMetrics={...(stockBasic.metrics||{}),...(yahoo.metrics||{})},yahooEtf=yahoo.etf||{},yahooMetricMeta=yahoo.metrics_meta||{};
  const asset={...(stockBasic||{}),...(found||{}),id:(found||{}).id||`TW:${symbol}`,symbol,name:(found||{}).name||stockBasic.short_name||stockBasic.company_name||yahooProfile.company_name||quote.name||symbol,exchange:(found||{}).exchange||stockBasic.exchange||yahooProfile.exchange||quote.exchange,asset_class:(found||{}).asset_class||stockBasic.asset_class||yahoo.asset_class||yahooProfile.asset_class||quote.asset_class||"stock",market:"TW"};
  const isEtf=asset.asset_class==="etf"||quote.asset_class==="etf";
  const verification=(verificationPayload.items||{})[symbol]||{};
  const chip=chipPayload.items?.[symbol]||{};
  const officialEtf=asset.etf||{};
  const cleanObject=value=>Object.fromEntries(Object.entries(value||{}).filter(([,v])=>v!==null&&v!==undefined&&String(v).trim()!==""));
  const etf={...cleanObject(yahooEtf),...cleanObject(etfReference),...cleanObject(officialEtf)};
  const officialMetrics=asset.metrics||{};
  const metrics={...yahooMetrics,...Object.fromEntries(Object.entries(officialMetrics).filter(([,v])=>v!==null&&v!==undefined&&String(v).trim()!==""))};
  const sourceDate=value=>value?formatTime(value,{dateOnly:true}):"";
  const has=value=>value!==null&&value!==undefined&&String(value).trim()!=="";
  const prefer=(official,reference)=>has(official)?official:reference;
  const metricSource=(key,fallback)=>asset.metric_sources?.[key]||(yahooMetricMeta[key]?.source)||(has(yahooMetrics[key])?"Yahoo 參考資料":fallback);
  const metricTrust=key=>asset.metric_sources?.[key]?verification.fields?.metrics?.status:(yahooMetricMeta[key]?.status|| (has(yahooMetrics[key])?"reference":verification.fields?.metrics?.status));
  const nonEmpty=value=>Array.isArray(value)?value.length>0:has(value);
  const safeUrl=value=>/^https?:\/\//i.test(String(value||""))?String(value):"";
  const formatDate=value=>{
    const raw=String(value||"").trim();
    if(!raw)return "";
    if(/^\d{8}$/.test(raw))return `${raw.slice(0,4)}/${raw.slice(4,6)}/${raw.slice(6,8)}`;
    const roc=raw.match(/^(\d{2,3})[\/-](\d{1,2})[\/-](\d{1,2})$/);
    if(roc)return `${Number(roc[1])+1911}/${String(roc[2]).padStart(2,"0")}/${String(roc[3]).padStart(2,"0")}`;
    const d=new Date(raw);
    return Number.isNaN(+d)?raw:formatTime(d,{dateOnly:true});
  };
  const INDUSTRIES={
    "01":"水泥工業","02":"食品工業","03":"塑膠工業","04":"紡織纖維","05":"電機機械","06":"電器電纜","07":"化學生技醫療","08":"玻璃陶瓷","09":"造紙工業","10":"鋼鐵工業","11":"橡膠工業","12":"汽車工業","13":"電子工業","14":"建材營造","15":"航運業","16":"觀光餐旅","17":"金融保險業","18":"貿易百貨","20":"其他業","21":"化學工業","22":"生技醫療業","23":"油電燃氣業","24":"半導體業","25":"電腦及週邊設備業","26":"光電業","27":"通信網路業","28":"電子零組件業","29":"電子通路業","30":"資訊服務業","31":"其他電子業","32":"文化創意業","33":"農業科技業","34":"電子商務","35":"綠能環保","36":"數位雲端","37":"運動休閒","38":"居家生活"
  };
  const industryName=value=>INDUSTRIES[String(value||"").padStart(2,"0")]||value||"";
  const compactNumber=(value,unit="")=>finite(value)==null?"":`${fmt(value,0)}${unit}`;
  const trustLabel=status=>status==="multi_source"?"多來源一致":status==="official"?"官方確認":status==="calculated"?"計算值":status==="estimated"?"估算值":status==="reference"?"參考資料":status==="conflict"?"資料衝突":status==="expired"?"資料過期":"";
  const trustClass=status=>status==="multi_source"?"confirmed":status==="official"?"official":status==="calculated"?"calculated":status==="estimated"?"estimated":status==="reference"?"reference":status==="conflict"?"conflict":"";
  const metricCard=(label,value,source="",options={})=>{
    if(!has(value)&&finite(value)==null)return "";
    const display=(options.percent?`${fmt(value,2)}%`:options.money?`${fmt(value,2)} ${options.money}`:options.integer?fmt(value,0):String(value))+String(options.suffix||"");
    const trust=options.verification?trustLabel(options.verification):"";
    return `<article class="stat metric-card"><small>${escapeHtml(label)}</small><strong class="${options.className||""}">${escapeHtml(display)}</strong>${source?`<span>${escapeHtml(source)}</span>`:""}${trust?`<em class="verification-badge ${trustClass(options.verification)}">${escapeHtml(trust)}</em>`:""}</article>`;
  };
  const infoGrid=rows=>`<div class="asset-info-grid detailed">${rows.filter(row=>has(row.value)).map(row=>{
    const value=row.url?`<a href="${escapeHtml(row.url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(row.value)} ↗</a>`:escapeHtml(row.value);
    return `<div><small>${escapeHtml(row.label)}</small><p>${value}</p>${row.note?`<em>${escapeHtml(row.note)}</em>`:""}</div>`;
  }).join("")}</div>`;
  const showSection=(id,label)=>{
    const section=$(id);if(!section)return;
    section.hidden=false;
    const anchor=id.replace(/^#/,"");
    const nav=$("#assetNav");
    const link=document.createElement("a");link.href=`#${anchor}`;link.textContent=label;nav.appendChild(link);
  };

  const displayName=(asset.name&&asset.name!==symbol)?asset.name:(yahooProfile.company_name&&yahooProfile.company_name!==symbol?yahooProfile.company_name:(quote.name&&quote.name!==symbol?quote.name:symbol));
  document.title=`${displayName}｜市場事件雷達`;
  $("#assetTitle").textContent=`${symbol}${displayName&&displayName!==symbol?` ${displayName}`:""}`;
  $("#assetKindLabel").textContent=isEtf?"ETF DETAIL":"STOCK DETAIL";
  $("#assetSub").textContent=[asset.exchange||quote.exchange,industryName(asset.official_industry||asset.sub_industry),isEtf?"ETF":"股票"].filter(Boolean).join(" · ");
  $("#assetPrice").textContent=fmt(quote.price);
  $("#assetChange").textContent=pct(quote.change_percent);
  $("#assetChange").className=cls(quote.change_percent);
  $("#assetQuoteTime").textContent=quote.quote_date?`${formatDate(quote.quote_date)} ${quote.quote_time||""}`:marketPayload.metadata?.updated_at?formatTime(marketPayload.metadata.updated_at):"";
  const overallTrust=Number(stockBasic.basic_coverage_percent||0)>=90?"multi_source":(verification.overall||"missing");
  const trustText=trustLabel(overallTrust)||"資料驗證中";
  $("#assetTrust").innerHTML=`<span class="verification-badge ${trustClass(overallTrust)}">${escapeHtml(trustText)}</span><span>官方資料優先；Yahoo、MoneyDJ、HiStock 僅補空白欄位，計算值會標示公式。</span>${stockBasic.basic_coverage_percent?`<span class="verification-badge official">公司主檔 ${escapeHtml(stockBasic.basic_coverage_percent)}%</span>`:""}${stockBasic.financial_coverage_percent!=null?`<span class="verification-badge reference">財務資料 ${escapeHtml(stockBasic.financial_coverage_percent)}%</span>`:""}${yahoo.updated_at?`<span class="verification-badge reference">Yahoo 已補充</span>`:""}${etfReference.updated_at?`<span class="verification-badge reference">ETF 多來源已補充</span>`:""}${(verification.reference_links?.yahoo||yahoo.source_url)?`<a href="${escapeHtml(verification.reference_links?.yahoo||yahoo.source_url)}" target="_blank" rel="noreferrer noopener">Yahoo 查閱 ↗</a>`:""}${verification.reference_links?.goodinfo?`<a href="${escapeHtml(verification.reference_links.goodinfo)}" target="_blank" rel="noreferrer noopener">Goodinfo 查閱 ↗</a>`:""}`;

  const overview=[];
  const pushCard=(label,value,source,options={})=>{const html=metricCard(label,value,source,options);if(html)overview.push(html)};
  pushCard("成交價",finite(quote.price),quote.status||"市場行情",{money:"元",verification:verification.fields?.quote?.status});
  pushCard("漲跌幅",finite(quote.change_percent),"市場行情",{percent:true,className:cls(quote.change_percent),verification:verification.fields?.quote?.status});
  pushCard("開盤",finite(quote.open),"市場行情",{money:"元"});
  pushCard("最高",finite(quote.high),"市場行情",{money:"元"});
  pushCard("最低",finite(quote.low),"市場行情",{money:"元"});
  pushCard("成交量",finite(quote.volume),"市場行情",{integer:true});
  pushCard("成交金額",finite(quote.trade_value),"市場行情",{integer:true});
  const amplitude=finite(quote.high)!=null&&finite(quote.low)!=null&&finite(quote.previous_close)!=null&&Number(quote.previous_close)!==0?(Number(quote.high)-Number(quote.low))/Number(quote.previous_close)*100:null;
  pushCard("振幅",amplitude,"依高低價與昨收計算",{percent:true});
  if(isEtf){
    pushCard("淨值",finite(etf.nav),etf.nav_source||"基金揭露",{money:"元"});
    pushCard("折溢價",finite(etf.premium_discount),etf.nav_source||"基金揭露",{percent:true,className:cls(etf.premium_discount)});
    pushCard("基金規模",finite(etf.aum),etf.aum_source||etf.field_sources?.aum||"基金資料",{integer:true,suffix:etf.aum_unit?` ${etf.aum_unit}`:""});
    pushCard("受益人數",finite(etf.beneficiary_count),etf.beneficiary_source||etf.field_sources?.beneficiary_count||"基金資料",{integer:true,suffix:" 人"});
    pushCard("受益權單位數",finite(etf.units),etf.units_source||"基金資料",{integer:true});
  }else{
    pushCard("本益比",finite(metrics.pe),metricSource("pe","官方估值"),{verification:metricTrust("pe")});
    pushCard("股價淨值比",finite(metrics.pb),metricSource("pb","官方估值"),{verification:metricTrust("pb")});
    pushCard("殖利率",finite(metrics.dividend_yield),metricSource("dividend_yield","官方估值"),{percent:true,verification:metricTrust("dividend_yield")});
    pushCard("EPS",finite(metrics.eps),metricSource("eps","官方財報"),{money:"元",verification:metricTrust("eps")});
    pushCard("ROE",finite(metrics.roe),metricSource("roe","官方財報計算"),{percent:true,verification:metricTrust("roe")});
    pushCard("ROA",finite(metrics.roa),metricSource("roa","官方財報計算"),{percent:true,verification:metricTrust("roa")});
    pushCard("負債比",finite(metrics.debt_ratio),metricSource("debt_ratio","官方財報計算"),{percent:true,verification:metricTrust("debt_ratio")});
    pushCard("淨利率",finite(metrics.net_margin),metricSource("net_margin","官方財報計算"),{percent:true,verification:metricTrust("net_margin")});
    pushCard("流動比率",finite(metrics.current_ratio),metricSource("current_ratio","官方財報計算"),{percent:true,verification:metricTrust("current_ratio")});
  }
  if(overview.length){
    $("#assetMetrics").innerHTML=overview.join("");
    $("#overviewTitle").textContent=isEtf?"行情與基金重點數據":"行情、估值與財務指標";
    $("#overviewUpdated").textContent=asset.metrics_updated_at?`指標更新 ${formatTime(asset.metrics_updated_at)}`:marketPayload.metadata?.updated_at?`行情更新 ${formatTime(marketPayload.metadata.updated_at)}`:"";
    showSection("#overviewSection","總覽");
  }

  const basicRows=isEtf?[]:[
    {label:"公司全名",value:prefer(asset.company_name,yahooProfile.company_name),note:!asset.company_name&&yahooProfile.company_name?"Yahoo 參考資料":""},
    {label:"公司簡稱",value:displayName!==symbol?displayName:""},
    {label:"產業類別",value:prefer(industryName(asset.official_industry||asset.sub_industry),yahooProfile.industry||yahooProfile.sector)},
    {label:"統一編號",value:prefer(asset.tax_id,yahooProfile.tax_id)},
    {label:"董事長",value:prefer(asset.chairperson,yahooProfile.chairperson)},
    {label:"總經理",value:prefer(asset.general_manager,yahooProfile.general_manager)},
    {label:"發言人",value:prefer(asset.spokesperson,yahooProfile.spokesperson)},
    {label:"成立日期",value:formatDate(prefer(asset.established_date,yahooProfile.established_date))},
    {label:"上市／上櫃日期",value:formatDate(prefer(asset.listed_date,yahooProfile.listed_date))},
    {label:"實收資本額",value:compactNumber(prefer(asset.paid_in_capital,yahooProfile.paid_in_capital)," 元")},
    {label:"發行股數",value:compactNumber(prefer(asset.issued_shares,prefer(yahooProfile.issued_shares,yahooMetrics.shares_outstanding))," 股"),note:!asset.issued_shares&&(yahooProfile.issued_shares||yahooMetrics.shares_outstanding)?"基本資料／Yahoo 參考":""},
    {label:"員工人數",value:compactNumber(prefer(asset.employee_count,yahooProfile.employees)," 人")},
    {label:"公司電話",value:prefer(asset.phone,yahooProfile.phone)},
    {label:"公司地址",value:prefer(asset.address,yahooProfile.address)},
    {label:"官方網站",value:prefer(asset.website||asset.official_url,yahooProfile.website),url:safeUrl(prefer(asset.website||asset.official_url,yahooProfile.website))},
    {label:"主要經營業務",value:prefer(asset.business_scope,prefer(yahooProfile.business_scope,yahooProfile.business_summary))},
    {label:"簽證會計師／事務所",value:asset.accounting_firm}
  ];
  if(basicRows.some(row=>has(row.value))){
    $("#assetInfo").innerHTML=infoGrid(basicRows);
    $("#basicUpdated").textContent=asset.master_updated_at?`公司主檔更新 ${formatTime(asset.master_updated_at)}`:"";
    showSection("#basicSection","公司資料");
  }

  if(isEtf){
    const isActive=/主動/i.test(`${etf.category||""} ${etf.management_style||""} ${displayName}`);
    const fundRows=[
      {label:"ETF 完整名稱",value:etf.formal_name||asset.company_name||displayName},
      {label:"發行投信",value:etf.issuer},
      {label:"基金經理人",value:etf.manager},
      {label:"保管銀行",value:etf.custodian},
      {label:"基金成立日",value:formatDate(etf.inception_date)},
      {label:"上市／上櫃日",value:formatDate(etf.listing_date||asset.listed_date)},
      {label:"管理方式",value:etf.management_style||(isActive?"主動式管理":"被動式管理")},
      {label:"基金類型",value:etf.category||asset.sub_industry||"ETF"},
      {label:"投資區域",value:etf.region},
      {label:"投資產業／主題",value:etf.focus},
      {label:"計價幣別",value:etf.currency||asset.currency||"TWD"},
      {label:"追蹤指數／績效指標",value:etf.benchmark||(isActive?"主動式管理，不追蹤特定指數":"")},
      {label:"投資策略",value:etf.strategy},
      {label:"經理費",value:etf.management_fee},
      {label:"保管費",value:etf.custody_fee},
      {label:"配息頻率",value:etf.distribution_frequency||etf.distribution},
      {label:"風險等級",value:etf.risk_level},
      {label:"槓桿／反向倍數",value:etf.leverage},
      {label:"申購買回方式",value:etf.creation_redemption},
      {label:"持股資料日期",value:formatDate(etf.holdings_date)},
      {label:"資料驗證",value:etf.verification?.holdings?.status==="official"?"官方確認":etf.verification?.holdings?.status==="multi_source"?"多來源一致":etf.updated_at?"次級來源補充":""},
      {label:"官方資料",value:etf.official_url?"查看基金官方資料":"",url:safeUrl(etf.official_url)},
      {label:"MoneyDJ",value:(etf.sources||[]).find(row=>String(row.source||"").includes("MoneyDJ"))?"查看ETF資料":"",url:safeUrl((etf.sources||[]).find(row=>String(row.source||"").includes("MoneyDJ"))?.source_url)},
      {label:"HiStock",value:(etf.sources||[]).find(row=>String(row.source||"").includes("HiStock"))?"查看主動式ETF觀測":"",url:safeUrl((etf.sources||[]).find(row=>String(row.source||"").includes("HiStock"))?.source_url)}
    ];
    if(fundRows.some(row=>has(row.value))){
      $("#fundInfo").innerHTML=infoGrid(fundRows);
      $("#fundUpdated").textContent=etf.updated_at?`基金資料更新 ${formatTime(etf.updated_at)}`:asset.master_updated_at?`基金主檔更新 ${formatTime(asset.master_updated_at)}`:"";
      showSection("#fundSection","基金資料");
    }
    const holdings=etf.holdings||yahooEtf.holdings||[];
    if(holdings.length){
      $("#holdingRows").innerHTML=holdings.map(row=>`<tr><td>${escapeHtml(row.symbol||"—")}</td><td>${escapeHtml(row.name||"—")}</td><td>${escapeHtml(row.industry||"—")}</td><td>${finite(row.shares)==null?"—":fmt(row.shares,0)}</td><td>${finite(row.change_shares)==null?"—":fmt(row.change_shares,0)}</td><td>${finite(row.weight)==null?"—":`${fmt(row.weight,2)}%`}</td></tr>`).join("");
      const allocation=etf.allocations||etf.sector_allocation||yahooEtf.allocations||yahooEtf.sector_allocation||[];
      if(allocation.length)$("#allocationGrid").innerHTML=allocation.map(row=>`<div><span>${escapeHtml(row.name||row.industry||"其他")}</span><strong>${finite(row.weight)==null?"—":`${fmt(row.weight,2)}%`}</strong></div>`).join("");
      $("#holdingsUpdated").textContent=etf.holdings_date?`持股資料日 ${formatDate(etf.holdings_date)} · ${etf.field_sources?.holdings||"來源已標示"}`:"依投信、TWSE、MoneyDJ、HiStock、Yahoo 與 ETF 資訊來源交叉整理";
      showSection("#holdingsSection","持股");
    }
  }

  const financialMap=new Map();
  for(const row of (stockBasic.financials||[])){const key=String(row.period||row.date||"");if(key)financialMap.set(key,row)}
  for(const row of (yahoo.financials||[])){const key=String(row.period||row.date||"");if(key)financialMap.set(key,{...(financialMap.get(key)||{}),...row})}
  for(const row of (asset.financials||[])){const key=String(row.period||row.date||"");if(key)financialMap.set(key,{...(financialMap.get(key)||{}),...row})}
  const financials=!isEtf?[...financialMap.values()].sort((a,b)=>String(b.period||b.date||"").localeCompare(String(a.period||a.date||""))).slice(0,20):[];
  if(financials.length){
    const ratio=(n,d)=>finite(n)!=null&&finite(d)!=null&&Number(d)!==0?Number(n)/Number(d)*100:null;
    $("#financialRows").innerHTML=financials.map(row=>{
      const roe=finite(row.roe)??ratio(row.net_income,row.total_equity),debt=finite(row.debt_ratio)??ratio(row.total_liabilities,row.total_assets),margin=finite(row.net_margin)??ratio(row.net_income,row.revenue),current=finite(row.current_ratio)??ratio(row.current_assets,row.current_liabilities);
      const epsNote=row.eps_status==="estimated"?'<br><em class="verification-badge estimated">估算</em>':row.eps_status==="calculated"?'<br><em class="verification-badge calculated">計算</em>':"";
      return `<tr><td><b>${escapeHtml(row.period||"—")}</b><br><small>${escapeHtml(row.source||"官方財報")}</small></td><td>${fmt(row.revenue,0)}</td><td>${fmt(row.gross_profit,0)}</td><td>${fmt(row.operating_income,0)}</td><td>${fmt(row.net_income_common??row.net_income,0)}</td><td>${fmt(row.eps,2)}${epsNote}</td><td>${finite(roe)==null?"—":`${fmt(roe,2)}%`}</td><td>${finite(debt)==null?"—":`${fmt(debt,2)}%`}</td><td>${finite(margin)==null?"—":`${fmt(margin,2)}%`}</td><td>${finite(current)==null?"—":`${fmt(current,2)}%`}</td></tr>`;
    }).join("");
    $("#financialUpdated").textContent=asset.financial_updated_at?`財報更新 ${formatTime(asset.financial_updated_at)}`:"依官方最新已申報季度";
    showSection("#financialSection","財務");
  }

  const revenueSourceRows=(revenuePayload.items?.[symbol]||asset.monthly_revenue||yahoo.monthly_revenue||[]);
  const revenues=!isEtf?revenueSourceRows.filter(row=>finite(row.revenue)!=null).sort((a,b)=>String(b.period||"").localeCompare(String(a.period||""))):[];
  if(revenues.length){
    const revenueStreak=()=>{let count=0;for(const row of revenues){if((finite(row.yoy)||0)>0)count++;else break}return count};
    const renderRevenue=(months=24)=>{
      const selected=months?revenues.slice(0,months):revenues.slice();
      $("#revenueRows").innerHTML=selected.map(row=>`<tr><td>${escapeHtml(row.period||row.month||"—")}</td><td>${fmt(row.revenue,0)}</td><td class="${cls(row.mom)}">${pct(row.mom)}</td><td class="${cls(row.yoy)}">${pct(row.yoy)}</td><td>${fmt(row.cumulative_revenue,0)}</td><td class="${cls(row.cumulative_yoy)}">${pct(row.cumulative_yoy)}</td></tr>`).join("");
      const chartRows=selected.slice(0,Math.min(24,selected.length)).reverse();
      if(chartRows.length===1){
        const row=chartRows[0];
        $("#revenueChart").innerHTML=`<div class="single-history-value"><small>${escapeHtml(row.period||"最新月份")}</small><strong>${fmt(row.revenue,0)} 千元</strong><span class="${cls(row.yoy)}">年增 ${pct(row.yoy)}</span><em>歷史資料持續回補中</em></div>`;
      }else{
        const values=chartRows.map(row=>finite(row.revenue)).filter(value=>value!=null),max=Math.max(...values,1);
        $("#revenueChart").innerHTML=chartRows.map(row=>`<div title="${escapeHtml(row.period||"")} ${fmt(row.revenue,0)} 千元"><i style="height:${Math.max(3,finite(row.revenue)/max*100)}%"></i><span>${escapeHtml(String(row.period||"").slice(-5))}</span></div>`).join("");
      }
    };
    const latest=revenues[0],historyMax=Math.max(...revenues.map(row=>finite(row.revenue)||0));
    $("#revenueSummary").innerHTML=[
      metricCard("最新月營收",finite(latest.revenue),latest.unit||"千元",{integer:true}),
      metricCard("最新年增率",finite(latest.yoy),latest.period||"",{percent:true,className:cls(latest.yoy)}),
      metricCard("收錄月份",revenues.length,"官方歷史資料",{integer:true}),
      metricCard("連續年增為正",revenueStreak(),"個月",{integer:true}),
      metricCard("區間最高月營收",historyMax,"千元",{integer:true})
    ].join("");
    renderRevenue(24);
    $$("#revenuePeriods button").forEach(button=>button.addEventListener("click",()=>{$$("#revenuePeriods button").forEach(item=>item.classList.remove("active"));button.classList.add("active");renderRevenue(Number(button.dataset.months||0))}));
    const revenueMeta=revenuePayload.metadata||{},progress=revenueMeta.covered_period_count?` · 歷史通道 ${revenueMeta.covered_period_count}/${revenueMeta.history_months||60} 個月份（${revenueMeta.backfill_percent||0}%）`:"";
    $("#revenueUpdated").dataset.verification=verification.fields?.monthly_revenue?.status||"";
    $("#revenueUpdated").textContent=revenueMeta.updated_at?`獨立營收通道更新 ${formatTime(revenueMeta.updated_at)} · ${revenueMeta.status||"等待"} · 此公司已收錄 ${revenues.length} 個月${progress}`:asset.revenue_updated_at?`營收資料更新 ${formatTime(asset.revenue_updated_at)} · 已收錄 ${revenues.length} 個月`:`依公開資訊觀測站 · 已收錄 ${revenues.length} 個月`;
    showSection("#revenueSection","月營收");
  }

  const chipCards=[];
  const addChip=(label,value,source,options={})=>{if(finite(value)==null)return;chipCards.push(metricCard(label,finite(value),source,options))};
  addChip("外資買賣超",chip.foreign?.net??chip.institutional?.foreign_net,"官方法人資料",{integer:true,className:cls(chip.foreign?.net??chip.institutional?.foreign_net)});
  addChip("投信買賣超",chip.trust?.net??chip.institutional?.trust_net,"官方法人資料",{integer:true,className:cls(chip.trust?.net??chip.institutional?.trust_net)});
  addChip("自營商買賣超",chip.dealer?.net??chip.institutional?.dealer_net,"官方法人資料",{integer:true,className:cls(chip.dealer?.net??chip.institutional?.dealer_net)});
  addChip("三大法人合計",chip.institutional?.total_net,"官方法人資料",{integer:true,className:cls(chip.institutional?.total_net)});
  addChip("融資餘額",chip.margin?.balance,"信用交易",{integer:true});
  addChip("融資增減",chip.margin?.change,"信用交易",{integer:true,className:cls(chip.margin?.change)});
  addChip("融券餘額",chip.short?.balance,"信用交易",{integer:true});
  addChip("融券增減",chip.short?.change,"信用交易",{integer:true,className:cls(chip.short?.change)});
  addChip("當沖量",chip.day_trade?.volume,"當沖統計",{integer:true});
  addChip("當沖比例",chip.day_trade?.ratio,"當沖統計",{percent:true});
  addChip("借券賣出",chip.borrowed_short?.balance,"借券資料",{integer:true});
  const holderPercent=value=>{const number=finite(value);if(number==null)return null;return Math.abs(number)<=1?number*100:number};
  addChip("機構持股比例",holderPercent(yahoo.holders?.institutionsPercentHeld),"Yahoo 補充資料",{percent:true});
  addChip("內部人持股比例",holderPercent(yahoo.holders?.insidersPercentHeld),"Yahoo 補充資料",{percent:true});
  addChip("機構持有流通股",holderPercent(yahoo.holders?.institutionsFloatPercentHeld),"Yahoo 補充資料",{percent:true});
  addChip("機構持有人數",yahoo.holders?.institutionsCount,"Yahoo 補充資料",{integer:true});
  if(chipCards.length){
    $("#chipMetrics").innerHTML=chipCards.join("");
    const history=Object.values(chipPayload.history||{}).map(day=>({date:day.date||day.trading_date,row:day.items?.[symbol]})).filter(x=>x.row).sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0,10);
    if(history.length){
      $("#chipTrendRows").innerHTML=history.map(({date,row})=>`<tr><td>${escapeHtml(formatDate(date))}</td><td>${fmt(row.institutional?.foreign_net,0)}</td><td>${fmt(row.institutional?.trust_net,0)}</td><td>${fmt(row.institutional?.dealer_net,0)}</td><td>${fmt(row.institutional?.total_net,0)}</td><td>${fmt(row.margin?.change,0)}</td><td>${fmt(row.short?.change,0)}</td><td>${finite(row.day_trade?.ratio)==null?"—":`${fmt(row.day_trade.ratio,2)}%`}</td></tr>`).join("");
      $("#chipTrendWrap").hidden=false;
    }
    $("#chipUpdated").textContent=chipPayload.metadata?.trading_date?`資料日 ${formatDate(chipPayload.metadata.trading_date)}`:chipPayload.metadata?.updated_at?`更新 ${formatTime(chipPayload.metadata.updated_at)}`:"";
    showSection("#chipSection","籌碼");
  }

  const isolatedDistributions=dividendPayload.items?.[symbol]||[];
  const distributionMap=new Map();
  const distributionRows=[...(yahoo.dividends||[]),...(isEtf?(etf.distributions||asset.dividends||[]):(asset.dividends||[])),...isolatedDistributions];
  for(const row of distributionRows){const key=`${row.ex_date||row.ex_dividend_date||row.date||row.period||row.year||""}|${row.cash??row.amount??row.cash_dividend??""}`;if(key!=="|")distributionMap.set(key,{...(distributionMap.get(key)||{}),...row})}
  const distributions=[...distributionMap.values()].sort((a,b)=>String(b.period||b.year||"").localeCompare(String(a.period||a.year||"")));
  if(distributions.length){
    const periodYear=row=>{const text=String(row.period||row.year||row.period_raw||"").trim();const ad=text.match(/(?:^|\D)(20\d{2})(?=\D|$)/);if(ad)return Number(ad[1]);const compact=text.match(/^(\d{3})\d{4}(?:[~至-]|$)/);if(compact)return Number(compact[1])+1911;const roc=text.match(/(?:^|\D)(\d{2,3})(?:年|(?=\D|$))/);if(!roc)return null;const year=Number(roc[1]);return year>=1911?year:year+1911};
    const periodLabel=row=>{
      let text=String(row.period||row.year||row.period_raw||row.record_date||"—").trim();
      const range=text.match(/^(\d{3})(\d{2})(\d{2})[~至-](\d{3})(\d{2})(\d{2})$/);
      if(range)return `${Number(range[1])+1911}/${range[2]}/${range[3]}－${Number(range[4])+1911}/${range[5]}/${range[6]}`;
      text=text.replace(/(\d{2,3})年/g,(_,year)=>`${Number(year)+1911}年`).replace(/^(\d{2,3})(?=\s|$)/,(_,year)=>String(Number(year)+1911));
      return text;
    };
    const renderDistributions=(years=5)=>{
      const cutoff=years?new Date().getFullYear()-years+1:null;
      const selected=distributions.filter(row=>!cutoff||periodYear(row)==null||periodYear(row)>=cutoff).slice(0,40);
      $("#distributionRows").innerHTML=selected.map(row=>`<tr><td>${escapeHtml(periodLabel(row))}</td><td>${finite(row.cash)==null&&finite(row.amount)==null&&finite(row.cash_dividend)==null?"—":fmt(row.cash??row.amount??row.cash_dividend,4)}</td><td>${finite(row.stock)==null?"—":fmt(row.stock,4)}</td><td>${escapeHtml(formatDate(row.board_date)||"—")}</td><td>${escapeHtml(formatDate(row.shareholder_meeting_date)||"—")}</td><td>${escapeHtml(formatDate(row.ex_date||row.ex_dividend_date||row.date)||"—")}</td><td>${escapeHtml(formatDate(row.payment_date)||"—")}</td><td>${row.url?`<a href="${escapeHtml(row.url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(row.source||"官方公告")} ↗</a>`:escapeHtml(row.source||"官方公告")}</td></tr>`).join("")||'<tr><td colspan="8" class="empty">此期間沒有股利紀錄</td></tr>';
    };
    $("#distributionTitle").textContent=isEtf?"配息歷史":"股利與除權息歷史";
    renderDistributions(5);
    $$("#distributionPeriods button").forEach(button=>button.addEventListener("click",()=>{$$("#distributionPeriods button").forEach(item=>item.classList.remove("active"));button.classList.add("active");renderDistributions(Number(button.dataset.years||0))}));
    $("#distributionUpdated").dataset.verification=verification.fields?.dividends?.status||"";
    $("#distributionUpdated").textContent=(dividendPayload.metadata?.updated_at?`獨立股利通道更新 ${formatTime(dividendPayload.metadata.updated_at)} · ${dividendPayload.metadata.status||"等待"}`:asset.dividend_updated_at?`股利資料更新 ${formatTime(asset.dividend_updated_at)}`:etf.distribution_updated_at?`配息資料更新 ${formatTime(etf.distribution_updated_at)}`:"")+` · 已收錄 ${distributions.length} 筆`;
    showSection("#distributionSection",isEtf?"配息":"股利");
  }

  const assetNames=[symbol,displayName,asset.company_name,etf.formal_name].filter(Boolean).map(normalizeText);
  const relatedEvents=(eventPayload.events||[]).filter(event=>{
    const symbols=[event.symbol,...(event.symbols||[]),...(event.assets||[])].filter(Boolean).map(value=>String(value).toUpperCase());
    const text=normalizeText(`${event.title||""} ${event.description||event.summary||""}`);
    return symbols.includes(symbol)||assetNames.some(name=>name&&text.includes(name));
  }).sort((a,b)=>Date.parse(b.start||0)-Date.parse(a.start||0)).slice(0,20);
  if(relatedEvents.length){
    $("#assetEvents").innerHTML=relatedEvents.map(event=>`<article class="asset-event-card"><div><span class="tag">${escapeHtml(event.category||event.kind||"公司資訊")}</span><time>${escapeHtml(formatTime(event.start))}</time></div><h3>${escapeHtml(event.title||"公司事件")}</h3>${event.summary||event.description?`<p>${escapeHtml(stripHtml(event.summary||event.description).slice(0,220))}</p>`:""}${event.source_url?`<a href="${escapeHtml(event.source_url)}" target="_blank" rel="noreferrer noopener">查看官方來源 ↗</a>`:""}</article>`).join("");
    showSection("#eventsSection","事件公告");
  }

  const relatedNews=[...(stockNewsPayload.items||[]),...(newsPayload.items||[])].filter(item=>{
    if(item.url_valid===false||item.source_id==="company-disclosures"||item.source_id==="official-notices")return false;
    const itemSymbols=(item.symbols||[]).map(value=>String(value).toUpperCase());
    const text=normalizeText(`${item.title||""} ${item.ai_summary||item.summary||""}`);
    return itemSymbols.includes(symbol)||assetNames.some(name=>name&&text.includes(name));
  }).filter((item,index,list)=>list.findIndex(x=>x.url===item.url||x.id===item.id)===index).slice(0,12);
  if(relatedNews.length){
    $("#assetNews").innerHTML=relatedNews.map(item=>`<article class="asset-media-card">${renderNewsThumb(item,"asset",{alt:item.title}).replace('class="news-thumb asset','class="asset-media-image news-thumb asset')}<div><div class="news-meta"><span>${escapeHtml(item.source||"")}</span><time>${escapeHtml(formatTime(item.published_at))}</time></div><div class="ai-badges"><span class="tag">${escapeHtml(item.ai_category||"個股新聞")}</span>${item.impact?`<span class="impact-badge ${escapeHtml(item.impact)}">${item.impact==="high"?"高影響":item.impact==="low"?"低影響":"中影響"}</span>`:""}<span class="direction-badge">${escapeHtml(item.market_direction||"中性")}</span></div><h3><a href="${escapeHtml(item.url||"#")}" target="_blank" rel="noreferrer noopener">${escapeHtml(item.title)}</a></h3><p>${escapeHtml(stripHtml(item.ai_summary||item.summary||"").slice(0,190))}</p>${(item.other_reports||[]).length?`<small>另有 ${item.other_reports.length} 家媒體報導同一事件</small>`:""}</div></article>`).join("");
    showSection("#newsSection","個股新聞");
  }

  const parseRocDate=value=>{
    const match=String(value||"").match(/(\d{2,3})\/(\d{1,2})\/(\d{1,2})/);if(!match)return null;
    return `${Number(match[1])+1911}-${String(match[2]).padStart(2,"0")}-${String(match[3]).padStart(2,"0")}`;
  };
  const num=value=>{const n=Number(String(value??"").replace(/,/g,""));return Number.isFinite(n)?n:null};
  const fetchJson=async(url,timeout=9000)=>{const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),timeout);try{const res=await fetch(url,{cache:"no-store",signal:ctl.signal});if(!res.ok)throw Error(res.status);return await res.json()}finally{clearTimeout(timer)}};
  const monthStarts=(count=12)=>{const out=[],now=new Date();for(let i=0;i<count;i++){const d=new Date(now.getFullYear(),now.getMonth()-i,1);out.push(`${d.getFullYear()}${String(d.getMonth()+1).padStart(2,"0")}01`)}return out};
  const rocMonths=(count=12)=>monthStarts(count).map(value=>`${Number(value.slice(0,4))-1911}/${value.slice(4,6)}`);
  const fetchTwseHistory=async()=>{
    const jobs=monthStarts().map(date=>fetchJson(`https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY?date=${date}&stockNo=${encodeURIComponent(symbol)}&response=json`).catch(()=>null));
    const payloads=await Promise.all(jobs),rows=[];
    for(const payload of payloads){for(const row of payload?.data||[]){const date=parseRocDate(row[0]);if(!date)continue;rows.push({date,volume:num(row[1]),value:num(row[2]),open:num(row[3]),high:num(row[4]),low:num(row[5]),close:num(row[6])})}}
    return rows;
  };
  const fetchTpexHistory=async()=>{
    const jobs=rocMonths().map(month=>fetchJson(`https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/st43_result.php?l=zh-tw&d=${encodeURIComponent(month)}&stkno=${encodeURIComponent(symbol)}`).catch(()=>null));
    const payloads=await Promise.all(jobs),rows=[];
    for(const payload of payloads){for(const row of payload?.aaData||payload?.data||[]){const date=parseRocDate(row[0]);if(!date)continue;rows.push({date,volume:num(row[1]),value:num(row[2]),open:num(row[3]),high:num(row[4]),low:num(row[5]),close:num(row[6])})}}
    return rows;
  };
  const fetchYahooHistory=async()=>{
    const suffix=(asset.exchange||quote.exchange)==="TPEx"?"TWO":"TW";
    const payload=await fetchJson(`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}.${suffix}?range=1y&interval=1d`,11000);
    const result=payload?.chart?.result?.[0],times=result?.timestamp||[],q=result?.indicators?.quote?.[0]||{};
    return times.map((time,index)=>({date:new Date(time*1000).toISOString().slice(0,10),open:q.open?.[index],high:q.high?.[index],low:q.low?.[index],close:q.close?.[index],volume:q.volume?.[index]})).filter(row=>finite(row.close)!=null);
  };
  let history=[];
  try{history=(asset.exchange||quote.exchange)==="TPEx"?await fetchTpexHistory():await fetchTwseHistory()}catch(e){}
  if(history.length<15){try{history=await fetchYahooHistory()}catch(e){}}
  history=[...new Map(history.filter(row=>row.date&&finite(row.close)!=null).map(row=>[row.date,row])).values()].sort((a,b)=>a.date.localeCompare(b.date));
  const sma=(rows,index,days)=>{if(index+1<days)return null;const values=rows.slice(index-days+1,index+1).map(row=>finite(row.close)).filter(value=>value!=null);return values.length===days?values.reduce((a,b)=>a+b,0)/days:null};
  const drawChart=(days=30)=>{
    const rows=history.slice(-days);if(!rows.length){$("#assetChart").innerHTML='<div class="empty">目前無法取得歷史行情。最新成交資料仍會保留在頁面上方。</div>';return}
    const width=1100,height=470,margin={left:58,right:22,top:24,bottom:45},priceBottom=330,volumeTop=350,volumeBottom=425;
    const lows=rows.map(row=>finite(row.low)??finite(row.close)),highs=rows.map(row=>finite(row.high)??finite(row.close)),min=Math.min(...lows),max=Math.max(...highs),pad=(max-min||1)*.08,lo=min-pad,hi=max+pad,maxVol=Math.max(...rows.map(row=>finite(row.volume)||0),1),plotW=width-margin.left-margin.right,step=plotW/rows.length,candle=Math.max(2,Math.min(10,step*.62));
    const x=i=>margin.left+step*i+step/2,y=value=>margin.top+(hi-value)/(hi-lo)*(priceBottom-margin.top),vy=value=>volumeBottom-(value/maxVol)*(volumeBottom-volumeTop);
    const priceTicks=Array.from({length:5},(_,i)=>lo+(hi-lo)*i/4);
    let svg=`<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(displayName)} K線與成交量">`;
    for(const tick of priceTicks){svg+=`<line class="chart-grid-line" x1="${margin.left}" x2="${width-margin.right}" y1="${y(tick)}" y2="${y(tick)}"></line><text class="chart-axis-text" x="${margin.left-8}" y="${y(tick)+4}" text-anchor="end">${fmt(tick,2)}</text>`}
    rows.forEach((row,i)=>{const o=finite(row.open)??finite(row.close),c=finite(row.close),h=finite(row.high)??Math.max(o,c),l=finite(row.low)??Math.min(o,c),up=c>=o,klass=up?"up":"down",cx=x(i),top=Math.min(y(o),y(c)),body=Math.max(1,Math.abs(y(o)-y(c)));svg+=`<line class="chart-wick ${klass}" x1="${cx}" x2="${cx}" y1="${y(h)}" y2="${y(l)}"></line><rect class="chart-candle ${klass}" x="${cx-candle/2}" y="${top}" width="${candle}" height="${body}"></rect><rect class="chart-volume ${klass}" x="${cx-candle/2}" y="${vy(finite(row.volume)||0)}" width="${candle}" height="${volumeBottom-vy(finite(row.volume)||0)}"></rect>`});
    const line=(days,klass)=>{const points=rows.map((row,i)=>{const value=sma(rows,i,days);return value==null?null:`${x(i)},${y(value)}`}).filter(Boolean);return points.length>1?`<polyline class="chart-ma ${klass}" points="${points.join(" ")}"></polyline>`:""};
    svg+=line(5,"ma5")+line(20,"ma20")+line(60,"ma60");
    const labels=[0,Math.floor((rows.length-1)/2),rows.length-1];for(const index of labels){if(rows[index])svg+=`<text class="chart-axis-text" x="${x(index)}" y="${height-12}" text-anchor="middle">${rows[index].date.slice(5)}</text>`}
    svg+=`<line class="chart-separator" x1="${margin.left}" x2="${width-margin.right}" y1="${volumeTop-10}" y2="${volumeTop-10}"></line></svg>`;
    $("#assetChart").innerHTML=svg;
    const first=rows[0],last=rows.at(-1),change=finite(first.close)!=null&&finite(last.close)!=null&&Number(first.close)!==0?(Number(last.close)-Number(first.close))/Number(first.close)*100:null;
    $("#chartSummary").innerHTML=`<span>區間 ${escapeHtml(first.date)}－${escapeHtml(last.date)}</span><span>最高 <b>${fmt(Math.max(...highs),2)}</b></span><span>最低 <b>${fmt(Math.min(...lows),2)}</b></span><span>區間漲跌 <b class="${cls(change)}">${pct(change)}</b></span>`;
  };
  if(history.length||finite(quote.price)!=null){
    showSection("#chartSection","K 線");drawChart(30);
    $("#chartSource").textContent=history.length?`資料來源：${(asset.exchange||quote.exchange)==="TPEx"?"TPEx／Yahoo 備援":"TWSE／Yahoo 備援"}；最近 ${history.length} 個交易日。`:`目前僅有最新行情。`;
    $$("#chartPeriods button").forEach(button=>button.addEventListener("click",()=>{$$("#chartPeriods button").forEach(item=>item.classList.remove("active"));button.classList.add("active");drawChart(Number(button.dataset.days||30))}));
  }

  const navOrder=[...document.querySelectorAll(".asset-section")].map(section=>section.id);
  [...$("#assetNav").children].sort((a,b)=>navOrder.indexOf(a.getAttribute("href").slice(1))-navOrder.indexOf(b.getAttribute("href").slice(1))).forEach(link=>$("#assetNav").appendChild(link));
  if(!$("#assetNav").children.length)$("#assetNav").hidden=true;
})();
