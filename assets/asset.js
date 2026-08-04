(async()=>{
  "use strict";
  const {$,$$,escapeHtml,fmt,pct,cls,formatTime,loadData,finite,stripHtml,normalizeText}=MR;
  const symbol=(new URLSearchParams(location.search).get("symbol")||"2330").toUpperCase();
  const [assetPayload,marketPayload,chipPayload,eventPayload,newsPayload]=await Promise.all([
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]}),
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),
    loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{items:{},history:{}}),
    loadData("events.json",window.__EVENT_SEED__||{events:[]}),
    loadData("news.json",window.__NEWS_SEED__||{items:[]})
  ]);
  const quote=(marketPayload.items||[]).find(row=>String(row.symbol||"").toUpperCase()===symbol)||{};
  const found=(assetPayload.assets||[]).find(row=>String(row.symbol||"").toUpperCase()===symbol);
  const asset=found||{id:`TW:${symbol}`,symbol,name:quote.name||symbol,exchange:quote.exchange,asset_class:quote.asset_class||"stock",market:"TW"};
  const isEtf=asset.asset_class==="etf"||quote.asset_class==="etf";
  const chip=chipPayload.items?.[symbol]||{};
  const etf=asset.etf||{};
  const metrics=asset.metrics||{};
  const sourceDate=value=>value?formatTime(value,{dateOnly:true}):"";
  const has=value=>value!==null&&value!==undefined&&String(value).trim()!=="";
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
  const metricCard=(label,value,source="",options={})=>{
    if(!has(value)&&finite(value)==null)return "";
    const display=options.percent?`${fmt(value,2)}%`:options.money?`${fmt(value,2)} ${options.money}`:options.integer?fmt(value,0):String(value);
    return `<article class="stat metric-card"><small>${escapeHtml(label)}</small><strong class="${options.className||""}">${escapeHtml(display)}</strong>${source?`<span>${escapeHtml(source)}</span>`:""}</article>`;
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

  const displayName=(asset.name&&asset.name!==symbol)?asset.name:(quote.name&&quote.name!==symbol?quote.name:symbol);
  document.title=`${displayName}｜市場事件雷達`;
  $("#assetTitle").textContent=`${symbol}${displayName&&displayName!==symbol?` ${displayName}`:""}`;
  $("#assetKindLabel").textContent=isEtf?"ETF DETAIL":"STOCK DETAIL";
  $("#assetSub").textContent=[asset.exchange||quote.exchange,industryName(asset.official_industry||asset.sub_industry),isEtf?"ETF":"股票"].filter(Boolean).join(" · ");
  $("#assetPrice").textContent=fmt(quote.price);
  $("#assetChange").textContent=pct(quote.change_percent);
  $("#assetChange").className=cls(quote.change_percent);
  $("#assetQuoteTime").textContent=quote.quote_date?`${formatDate(quote.quote_date)} ${quote.quote_time||""}`:marketPayload.metadata?.updated_at?formatTime(marketPayload.metadata.updated_at):"";

  const overview=[];
  const pushCard=(label,value,source,options)=>{const html=metricCard(label,value,source,options);if(html)overview.push(html)};
  pushCard("成交價",finite(quote.price),quote.status||"市場行情",{money:"元"});
  pushCard("漲跌幅",finite(quote.change_percent),"市場行情",{percent:true,className:cls(quote.change_percent)});
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
    pushCard("基金規模",finite(etf.aum),etf.aum_source||"基金資料",{integer:true});
    pushCard("受益人數",finite(etf.beneficiary_count),etf.beneficiary_source||"基金資料",{integer:true});
    pushCard("受益權單位數",finite(etf.units),etf.units_source||"基金資料",{integer:true});
  }else{
    pushCard("本益比",finite(metrics.pe),asset.metric_sources?.pe||"官方估值",{});
    pushCard("股價淨值比",finite(metrics.pb),asset.metric_sources?.pb||"官方估值",{});
    pushCard("殖利率",finite(metrics.dividend_yield),asset.metric_sources?.dividend_yield||"官方估值",{percent:true});
    pushCard("EPS",finite(metrics.eps),asset.metric_sources?.eps||"官方財報",{money:"元"});
    pushCard("ROE",finite(metrics.roe),asset.metric_sources?.roe||"官方財報計算",{percent:true});
    pushCard("ROA",finite(metrics.roa),asset.metric_sources?.roa||"官方財報計算",{percent:true});
    pushCard("負債比",finite(metrics.debt_ratio),asset.metric_sources?.debt_ratio||"官方財報計算",{percent:true});
    pushCard("淨利率",finite(metrics.net_margin),asset.metric_sources?.net_margin||"官方財報計算",{percent:true});
    pushCard("流動比率",finite(metrics.current_ratio),asset.metric_sources?.current_ratio||"官方財報計算",{percent:true});
  }
  if(overview.length){
    $("#assetMetrics").innerHTML=overview.join("");
    $("#overviewTitle").textContent=isEtf?"行情與基金重點數據":"行情、估值與財務指標";
    $("#overviewUpdated").textContent=asset.metrics_updated_at?`指標更新 ${formatTime(asset.metrics_updated_at)}`:marketPayload.metadata?.updated_at?`行情更新 ${formatTime(marketPayload.metadata.updated_at)}`:"";
    showSection("#overviewSection","總覽");
  }

  const basicRows=isEtf?[]:[
    {label:"公司全名",value:asset.company_name},
    {label:"公司簡稱",value:displayName!==symbol?displayName:""},
    {label:"產業類別",value:industryName(asset.official_industry||asset.sub_industry)},
    {label:"統一編號",value:asset.tax_id},
    {label:"董事長",value:asset.chairperson},
    {label:"總經理",value:asset.general_manager},
    {label:"發言人",value:asset.spokesperson},
    {label:"成立日期",value:formatDate(asset.established_date)},
    {label:"上市／上櫃日期",value:formatDate(asset.listed_date)},
    {label:"實收資本額",value:compactNumber(asset.paid_in_capital," 元")},
    {label:"發行股數",value:compactNumber(asset.issued_shares," 股")},
    {label:"員工人數",value:compactNumber(asset.employee_count," 人")},
    {label:"公司電話",value:asset.phone},
    {label:"公司地址",value:asset.address},
    {label:"官方網站",value:asset.website||asset.official_url,url:safeUrl(asset.website||asset.official_url)},
    {label:"主要經營業務",value:asset.business_scope},
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
      {label:"官方資料",value:etf.official_url?"查看基金官方資料":"",url:safeUrl(etf.official_url)}
    ];
    if(fundRows.some(row=>has(row.value))){
      $("#fundInfo").innerHTML=infoGrid(fundRows);
      $("#fundUpdated").textContent=etf.updated_at?`基金資料更新 ${formatTime(etf.updated_at)}`:asset.master_updated_at?`基金主檔更新 ${formatTime(asset.master_updated_at)}`:"";
      showSection("#fundSection","基金資料");
    }
    const holdings=etf.holdings||[];
    if(holdings.length){
      $("#holdingRows").innerHTML=holdings.map(row=>`<tr><td>${escapeHtml(row.symbol||"—")}</td><td>${escapeHtml(row.name||"—")}</td><td>${escapeHtml(row.industry||"—")}</td><td>${finite(row.shares)==null?"—":fmt(row.shares,0)}</td><td>${finite(row.weight)==null?"—":`${fmt(row.weight,2)}%`}</td></tr>`).join("");
      const allocation=etf.allocations||[];
      if(allocation.length)$("#allocationGrid").innerHTML=allocation.map(row=>`<div><span>${escapeHtml(row.name||row.industry||"其他")}</span><strong>${finite(row.weight)==null?"—":`${fmt(row.weight,2)}%`}</strong></div>`).join("");
      $("#holdingsUpdated").textContent=etf.holdings_date?`持股資料日 ${formatDate(etf.holdings_date)}`:"依投信或官方最新揭露";
      showSection("#holdingsSection","持股");
    }
  }

  const financials=!isEtf?(asset.financials||[]).slice(0,12):[];
  if(financials.length){
    const ratio=(n,d)=>finite(n)!=null&&finite(d)!=null&&Number(d)!==0?Number(n)/Number(d)*100:null;
    $("#financialRows").innerHTML=financials.map(row=>{
      const roe=finite(row.roe)??ratio(row.net_income,row.total_equity),debt=finite(row.debt_ratio)??ratio(row.total_liabilities,row.total_assets),margin=finite(row.net_margin)??ratio(row.net_income,row.revenue),current=finite(row.current_ratio)??ratio(row.current_assets,row.current_liabilities);
      return `<tr><td><b>${escapeHtml(row.period||"—")}</b><br><small>${escapeHtml(row.source||"官方財報")}</small></td><td>${fmt(row.revenue,0)}</td><td>${fmt(row.gross_profit,0)}</td><td>${fmt(row.operating_income,0)}</td><td>${fmt(row.net_income,0)}</td><td>${fmt(row.eps,2)}</td><td>${finite(roe)==null?"—":`${fmt(roe,2)}%`}</td><td>${finite(debt)==null?"—":`${fmt(debt,2)}%`}</td><td>${finite(margin)==null?"—":`${fmt(margin,2)}%`}</td><td>${finite(current)==null?"—":`${fmt(current,2)}%`}</td></tr>`;
    }).join("");
    $("#financialUpdated").textContent=asset.financial_updated_at?`財報更新 ${formatTime(asset.financial_updated_at)}`:"依官方最新已申報季度";
    showSection("#financialSection","財務");
  }

  const revenues=!isEtf?(asset.monthly_revenue||[]).slice(0,24):[];
  if(revenues.length){
    $("#revenueRows").innerHTML=revenues.slice(0,12).map(row=>`<tr><td>${escapeHtml(row.period||row.month||"—")}</td><td>${fmt(row.revenue,0)}</td><td class="${cls(row.mom)}">${pct(row.mom)}</td><td class="${cls(row.yoy)}">${pct(row.yoy)}</td><td>${fmt(row.cumulative_revenue,0)}</td><td class="${cls(row.cumulative_yoy)}">${pct(row.cumulative_yoy)}</td></tr>`).join("");
    const values=revenues.slice().reverse().map(row=>finite(row.revenue)).filter(value=>value!=null),max=Math.max(...values,1);
    $("#revenueChart").innerHTML=revenues.slice().reverse().map(row=>`<div title="${escapeHtml(row.period||"")} ${fmt(row.revenue,0)}"><i style="height:${Math.max(3,finite(row.revenue)/max*100)}%"></i><span>${escapeHtml(String(row.period||"").slice(-5))}</span></div>`).join("");
    $("#revenueUpdated").textContent=asset.revenue_updated_at?`營收資料更新 ${formatTime(asset.revenue_updated_at)}`:"依公開資訊觀測站月營收";
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

  const distributions=(isEtf?(etf.distributions||asset.dividends||[]):(asset.dividends||[]));
  if(distributions.length){
    $("#distributionTitle").textContent=isEtf?"配息紀錄":"股利與除權息";
    $("#distributionRows").innerHTML=distributions.slice(0,24).map(row=>`<tr><td>${escapeHtml(row.period||row.year||row.record_date||"—")}</td><td>${finite(row.cash)==null&&finite(row.amount)==null?"—":fmt(row.cash??row.amount,4)}</td><td>${finite(row.stock)==null?"—":fmt(row.stock,4)}</td><td>${escapeHtml(formatDate(row.ex_date||row.ex_dividend_date||row.date)||"—")}</td><td>${escapeHtml(formatDate(row.payment_date)||"—")}</td><td>${row.url?`<a href="${escapeHtml(row.url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(row.source||"官方公告")} ↗</a>`:escapeHtml(row.source||"官方公告")}</td></tr>`).join("");
    $("#distributionUpdated").textContent=asset.dividend_updated_at?`股利資料更新 ${formatTime(asset.dividend_updated_at)}`:etf.distribution_updated_at?`配息資料更新 ${formatTime(etf.distribution_updated_at)}`:"";
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

  const relatedNews=(newsPayload.items||[]).filter(item=>{
    if(item.url_valid===false)return false;
    const itemSymbols=(item.symbols||[]).map(value=>String(value).toUpperCase());
    const text=normalizeText(`${item.title||""} ${item.ai_summary||item.summary||""}`);
    return itemSymbols.includes(symbol)||assetNames.some(name=>name&&text.includes(name));
  }).slice(0,12);
  if(relatedNews.length){
    $("#assetNews").innerHTML=relatedNews.map(item=>`<a class="news-card compact" href="${escapeHtml(item.url||"#")}" target="_blank" rel="noreferrer noopener"><div class="news-meta"><span>${escapeHtml(item.source||"")}</span><time>${escapeHtml(formatTime(item.published_at))}</time></div><div class="ai-badges"><span class="tag">${escapeHtml(item.ai_category||item.topic||"市場")}</span>${item.impact?`<span class="impact-badge ${escapeHtml(item.impact)}">${item.impact==="high"?"高影響":item.impact==="low"?"低影響":"中影響"}</span>`:""}</div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(stripHtml(item.ai_summary||item.summary||"").slice(0,170))}</p></a>`).join("");
    showSection("#newsSection","相關新聞");
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
