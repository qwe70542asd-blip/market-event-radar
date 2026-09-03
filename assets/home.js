// v11.5.1 sealed performance + strict industry normalization
(async()=>{
  "use strict";
  const {$,escapeHtml,fmt,pct,cls,formatTime,formatEventTime,loadData,loadMarketKline,startNewsChannels,loadStockNews,loadPortfolio,finite,renderNewsThumb,newsHasImage,safeExternalHref,getLiveMarketEndpoint}=MR;
  const assetFallback=window.__ASSET_SEED__||{assets:[]};
  const eventFallback=window.__EVENT_SEED__||{metadata:{status:"seed"},events:[]};
  const twFallback=window.__TW_MARKET_SEED__||{items:[]};
  const chipsFallback=window.__TW_CHIPS_SEED__||{markets:{},items:{}};
  const snapshotFallback=window.__MARKET_SNAPSHOT_SEED__||{items:[]};
  const stockNewsFallback=window.__STOCK_NEWS_SEED__||{metadata:{status:"seed"},items:[]};

  // Homepage state mounts immediately from bundled/last-known-good data. Every
  // channel then upgrades the mounted section independently when verified live
  // data arrives; no 4.5 second boot race can permanently freeze an empty card.
  let assets=assetFallback,events=eventFallback,stockNews=stockNewsFallback,tw=twFallback,chips=chipsFallback,snapshot=snapshotFallback;
  let news={metadata:{status:"seed"},channels:[],items:[]};
  let assetMap=new Map();
  let quotes=new Map();
  const rebuildAssets=()=>{assetMap=new Map((assets.assets||[]).map(row=>[String(row.symbol||"").toUpperCase(),row]));};
  const rebuildQuotes=()=>{quotes=new Map([...(tw.items||[]),...(snapshot.items||[])].map(row=>[String(row.symbol||"").toUpperCase(),row]));};
  rebuildAssets();rebuildQuotes();

  const eventLivePromise=window.__MR_EVENT_LIVE_PROMISE__||(window.__MR_EVENT_LIVE_PROMISE__=loadData("home-events.json",eventFallback).catch(()=>eventFallback));
  const assetLivePromise=loadData("home-assets.json",assetFallback).catch(()=>assetFallback);
  const twLivePromise=loadData("tw-market-compact.json",twFallback).catch(()=>twFallback);
  const chipsLivePromise=loadData("tw-chips-compact.json",chipsFallback).catch(()=>chipsFallback);
  const snapshotLivePromise=loadData("market-snapshot.json",snapshotFallback).catch(()=>snapshotFallback);
  const stockNewsLivePromise=loadStockNews().catch(()=>stockNewsFallback);
  const newsStream=startNewsChannels({concurrency:1,startDelay:1200,staggerMs:120,onUpdate:payload=>{news=payload;queueMicrotask(()=>{renderFeaturedInfo?.();renderCalendar?.();renderTodayFocus?.();renderTodayBrief?.()})}});
  news=newsStream.initial;
  const strip=value=>String(value||"").replace(/<[^>]*>/g," ").replace(/&nbsp;/gi," ").replace(/\s+/g," ").trim();
  const truncate=(value,max=180)=>{const text=strip(value);return text.length>max?`${text.slice(0,max).trim()}…`:text};
  const localKey=value=>{
    const date=value instanceof Date?value:new Date(value);
    if(Number.isNaN(+date))return"";
    const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(date);
    const map=Object.fromEntries(parts.map(part=>[part.type,part.value]));
    return `${map.year}-${map.month}-${map.day}`;
  };
  const eventDateKey=event=>{
    const exact=String(event?.local_date||event?.target_date||event?.ex_date||"").match(/^\d{4}-\d{2}-\d{2}/);
    return exact?exact[0]:localKey(event?.start);
  };
  const eventGroup=event=>{
    const group=String(event.event_group||"").toLowerCase();
    const category=String(event.category||event.type||"").toLowerCase();
    const type=String(event.event_type||"").toLowerCase();
    if(group==="dividend"||/dividend|ex-right|ex-div|distribution/.test(`${category} ${type}`))return"dividend";
    if(group==="corporate"||/earnings|corporate|conference|shareholder|financial-report|corporate-action|material/.test(`${category} ${type}`))return"company";
    return"major";
  };
  const eventIdentity=event=>{
    const day=eventDateKey(event),group=eventGroup(event),symbol=String(event.symbol||event.asset_id||"").toUpperCase();
    if(group==="dividend"){
      const kind=/除權/.test(event.title||"")?"ex-right":"ex-dividend";
      return `${day}|${group}|${symbol}|${kind}`;
    }
    const normalized=strip(event.title).toLowerCase().replace(/[（(][^）)]*(?:元|%)[^）)]*[）)]/g,"").replace(/[^0-9a-z\u4e00-\u9fff]+/gi,"").slice(0,150);
    return `${day}|${group}|${symbol}|${normalized}`;
  };
  const uniqueEvents=rows=>{
    const map=new Map();
    for(const event of rows){
      const key=eventIdentity(event),old=map.get(key);
      const score=row=>[row.source_url,row.source_name,row.description,row.market_effect,row.cash_dividend,row.payment_date].filter(Boolean).length;
      if(!old||score(event)>score(old))map.set(key,event);
    }
    return [...map.values()];
  };
  const impactLabel=impact=>impact==="high"?"高影響":impact==="low"?"低影響":"中影響";

  const LEADER_RE=/台積電|鴻海|聯發科|廣達|緯創|國巨|川湖|日月光|台達電|中華電|長榮|陽明|NVIDIA|輝達|Microsoft|微軟|Apple|蘋果|Amazon|亞馬遜|Meta|Google|Alphabet|AMD|Intel|Tesla|三星|SK\s*海力士|海力士|Sony|Toyota/i;
  // v11.5.1: a bare regulator/exchange mention is not a market-structure event.
  // Direct trading-rule terms qualify on their own; institution names qualify only
  // when paired with an actual rule/change signal.
  const MARKET_STRUCTURE_RE=/零股|整股|盤中零股|盤後零股|撮合|集合競價|逐筆交易|交易時間|開盤時間|收盤時間|漲跌幅|升降單位|當沖|融資融券|融券|融資|交割|T\+?1|T\+?2|交易制度|市場制度/i;
  const MARKET_STRUCTURE_INSTITUTION_RE=/證交所|櫃買中心|金管會|交易所|TWSE|TPEx|FSC/i;
  const MARKET_STRUCTURE_CHANGE_RE=/新制|新規|規則|制度|措施|辦法|修正|調整|變更|改革|上路|生效|實施|開放|啟用|延長|縮短|取消|新增|限制|放寬/i;
  const isMarketStructure=text=>MARKET_STRUCTURE_RE.test(text)||(MARKET_STRUCTURE_INSTITUTION_RE.test(text)&&MARKET_STRUCTURE_CHANGE_RE.test(text));
  const BREAKING_RE=/突發|緊急|臨時|意外|暫停交易|停止交易|系統異常|交易中斷|熔斷|救市|干預|制裁|禁令|出口管制|關稅|停產|召回|破產|違約|併購|收購|下市|倒閉/i;
  const AI_SECTOR_RE=/AI|人工智慧|半導體|晶圓代工|先進製程|先進封裝|CoWoS|HBM|GPU|ASIC|伺服器|資料中心|散熱|PCB|載板|光通訊|矽光子|CPO|記憶體|DRAM|NAND|電源供應|雲端/i;
  const FINANCE_RE=/金融|銀行|金控|壽險|產險|保險|證券|券商|信用卡|金融監理|資本適足|匯率|外匯/i;
  const SHIPPING_RE=/航運|貨櫃|散裝|海運|航空|空運|物流|運價|BDI|SCFI/i;
  const ENERGY_RE=/能源|電力|電價|綠能|太陽能|風電|核能|天然氣|LNG|石油|原油|OPEC/i;
  const MATERIALS_RE=/鋼鐵|水泥|塑化|化工|原物料|銅價|鋁價|金價|黃金|稀土|礦業/i;
  const AUTO_RE=/汽車|電動車|EV|電池|充電樁|自駕|車用|特斯拉/i;
  const BIOTECH_RE=/生技|醫療|製藥|新藥|藥證|FDA|醫材|健保/i;
  const REAL_ESTATE_RE=/房地產|房市|營建|建商|房貸|不動產|預售屋/i;
  const CONSUMER_RE=/消費|零售|百貨|餐飲|觀光|旅遊|飯店|食品|超商|電商/i;
  const TELECOM_RE=/電信|5G|衛星通訊|媒體|串流/i;
  const DEFENSE_RE=/軍工|國防|航太|無人機|軍售/i;
  const ROBOTICS_RE=/機器人|自動化|人形機器人|機械手臂/i;
  const CENTRAL_BANK_RE=/FOMC|聯準會|Fed|央行|日本銀行|日銀|BOJ|歐洲央行|ECB|英國央行|BOE|韓國央行|中國人民銀行|PBOC|升息|降息|利率決策|量化寬鬆|量化緊縮/i;
  const MACRO_RE=/CPI|PCE|GDP|非農|JOLTS|PMI|PPI|失業率|就業|通膨|通縮|零售銷售|工業生產/i;
  const GEOPOLITICAL_RE=/戰爭|衝突|地緣政治|制裁|關稅|出口管制|禁運|封鎖|停火|軍事|海峽|紅海/i;
  const EXECUTIVE_RE=/執行長|董事長|財務長|總經理|基金經理人|分析師|首席經濟學家|央行總裁|官員|法說會|投資人會議|發表會|開發者大會|展覽|論壇|供應鏈會議/i;
  const BUSINESS_RE=/財報|財測|展望|營收|獲利|EPS|訂單|資本支出|擴產|漲價|降價|新品|新產品|合作|併購|投資/i;
  const SYSTEMIC_RE=/金融危機|銀行危機|債務危機|財政危機|信用危機|熔斷|重大法規|救市/i;
  const ASIA_RISK_RE=/日本銀行|日銀|BOJ|日圓|日債|日本國債|日本政府債務|日本企業倒閉|日本企業破產|匯市干預|韓國央行|韓元|KOSPI|KOSDAQ|中國房地產|中國房企|地方債|人民幣|亞洲貨幣|亞洲資金外流|貨幣競貶/i;
  const ASIA_STRESS_RE=/(?:創|跌至|貶至|升至|突破|失守).{0,10}(?:年|低點|高點)|暴跌|重貶|急貶|干預匯市|企業倒閉.{0,8}(?:增加|創高|突破)|破產.{0,8}(?:增加|創高)|債務.{0,8}(?:危機|失控|惡化)|房企.{0,8}(?:違約|倒閉)|地方債.{0,8}(?:風險|危機)|資金外流|信用風險/i;
  const ASIA_CROSS_BORDER_RE=/亞洲|台灣|台股|出口|供應鏈|半導體|觀光|航空|壽險|金融|匯率|資金流向/i;
  const majorCategory=item=>{
    const text=`${item.title||""} ${item.summary||""} ${item.ai_summary||""} ${item.topic||""} ${item.ai_category||""}`;
    if(isMarketStructure(text))return"市場制度";
    if(CENTRAL_BANK_RE.test(text))return"央行政策";
    if(GEOPOLITICAL_RE.test(text))return"地緣政治";
    if(AI_SECTOR_RE.test(text))return"AI／半導體";
    if(FINANCE_RE.test(text))return"金融";
    if(SHIPPING_RE.test(text))return"航運／物流";
    if(ENERGY_RE.test(text))return"能源／電力";
    if(MATERIALS_RE.test(text))return"原物料";
    if(AUTO_RE.test(text))return"汽車／電動車";
    if(BIOTECH_RE.test(text))return"生技醫療";
    if(REAL_ESTATE_RE.test(text))return"房市營建";
    if(CONSUMER_RE.test(text))return"消費／觀光";
    if(TELECOM_RE.test(text))return"電信媒體";
    if(DEFENSE_RE.test(text))return"軍工航太";
    if(ROBOTICS_RE.test(text))return"機器人／自動化";
    if(BUSINESS_RE.test(text))return"企業財報";
    if(MACRO_RE.test(text))return"總體經濟";
    return"市場焦點";
  };
  const majorScore=item=>{
    const text=`${item.title||""} ${item.summary||""} ${item.ai_summary||""}`;
    let score=0;
    if(isMarketStructure(text))score+=52;
    if(BREAKING_RE.test(text))score+=34;
    if(SYSTEMIC_RE.test(text))score+=45;
    if(CENTRAL_BANK_RE.test(text)||MACRO_RE.test(text))score+=34;
    if(GEOPOLITICAL_RE.test(text))score+=28;
    if(ASIA_RISK_RE.test(text))score+=18;
    if(ASIA_RISK_RE.test(text)&&ASIA_STRESS_RE.test(text))score+=26;
    if(ASIA_RISK_RE.test(text)&&ASIA_CROSS_BORDER_RE.test(text))score+=10;
    if(LEADER_RE.test(text))score+=22;
    // AI remains the highest-normal-priority industry, but every major sector can qualify.
    if(AI_SECTOR_RE.test(text))score+=22;
    else if([FINANCE_RE,SHIPPING_RE,ENERGY_RE,MATERIALS_RE,AUTO_RE,BIOTECH_RE,REAL_ESTATE_RE,CONSUMER_RE,TELECOM_RE,DEFENSE_RE,ROBOTICS_RE].some(pattern=>pattern.test(text)))score+=16;
    if(EXECUTIVE_RE.test(text))score+=14;
    if(BUSINESS_RE.test(text))score+=14;
    if(["official-notices","company-disclosures","cna"].includes(item.source_id))score+=12;
    if((item.other_reports||[]).length)score+=Math.min(18,(item.other_reports||[]).length*5);
    if(item.impact==="high")score+=12; else if(item.impact==="medium")score+=5;
    const age=(Date.now()-Date.parse(item.published_at||item.date||0))/86400000;
    if(Number.isFinite(age)&&age<=.25)score+=14;else if(Number.isFinite(age)&&age<=1)score+=10;else if(Number.isFinite(age)&&age<=3)score+=5;
    return Math.max(score,Number(item.importance_score||0));
  };
  const slugCategory=value=>String(value||"market").toLowerCase().replace(/[^0-9a-z\u4e00-\u9fff]+/gi,"-").replace(/^-|-$/g,"");
  const verificationLabel=item=>item.source_id==="official-notices"||item.source_id==="company-disclosures"?"官方來源":(item.other_reports||[]).length?"多來源佐證":item.source_id==="cna"?"主要媒體":"單一來源";
  const quoteAgeMinutes=()=>{const stamp=Date.parse(tw.metadata?.updated_at||0);return Number.isFinite(stamp)?Math.max(0,(Date.now()-stamp)/60000):null;};

  function renderMarketList(){
    const updated=tw.metadata?.updated_at,age=quoteAgeMinutes();
    const updatedNode=$("#marketUpdated"),freshNode=$("#marketFreshness");
    if(updatedNode)updatedNode.textContent=updated?`資料時間 ${formatTime(updated)}`:"等待資料";
    if(freshNode){
      const tradeDate=String(tw.metadata?.trading_date||"");
      const closed=["latest-close","official-close","market-closed"].includes(String(tw.metadata?.market_status||""));
      const fresh=age!=null&&age<=2,delayed=age!=null&&age>8;
      freshNode.textContent=closed&&tradeDate?`最新交易日 ${tradeDate.slice(5)}`:delayed?`官方排程快照延遲 ${Math.round(age)} 分鐘`:fresh?"官方排程快照":"最近官方快照";
      freshNode.className=`status-pill ${!closed&&delayed?"stale":""}`;
    }
  }
  renderMarketList();

  function renderPortfolioSummary(){
    const rows=loadPortfolio();
    const usdTwd=finite(quotes.get("TWD=X")?.price);
    const fxToTwd=currency=>{
      const code=String(currency||"TWD").toUpperCase();
      if(code==="TWD")return 1;
      if(code==="USD")return usdTwd&&usdTwd>0?usdTwd:null;
      const usdCross=finite(quotes.get(`${code}=X`)?.price);
      return usdTwd&&usdCross&&usdTwd>0&&usdCross>0?usdTwd/usdCross:null;
    };
    let totalCost=0,valuedCost=0,totalValue=0,dayPL=0,valued=0,dayValued=0,unconverted=0;
    const allocation=new Map();
    for(const holding of rows){
      const symbol=String(holding.symbol||"").toUpperCase(),quote=quotes.get(symbol),asset=assetMap.get(symbol)||{};
      const qty=finite(holding.quantity??holding.qty),cost=finite(holding.cost??holding.average_cost),price=finite(quote?.price),previous=finite(quote?.previous_close);
      const currency=String(holding.currency||quote?.currency||asset.currency||"TWD").toUpperCase(),fx=fxToTwd(currency);
      if(fx==null){if(qty!=null&&(cost!=null||price!=null))unconverted++;continue}
      if(qty!=null&&cost!=null)totalCost+=qty*cost*fx;
      if(qty!=null&&price!=null){
        const value=qty*price*fx;totalValue+=value;valued++;if(cost!=null)valuedCost+=qty*cost*fx;
        const category=asset.asset_class==="etf"?"ETF":asset.asset_class==="stock"?"個股":"其他";
        allocation.set(category,(allocation.get(category)||0)+value);
        if(previous!=null){dayPL+=(price-previous)*qty*fx;dayValued++}
      }
    }
    // Aggregate NT$ totals fail closed when any holding lacks a quote or usable FX conversion.
    const totalsComplete=rows.length>0&&valued===rows.length&&unconverted===0;
    const dayComplete=totalsComplete&&dayValued===rows.length;
    const cumulative=totalsComplete?totalValue-valuedCost:null,returnPct=cumulative!=null&&valuedCost?cumulative/valuedCost*100:null;
    const dayBase=dayComplete?totalValue-dayPL:null,dayPct=dayBase?dayPL/dayBase*100:null;
    $("#portfolioTotalValue").textContent=totalsComplete?`NT$ ${fmt(totalValue,0)}`:"—";
    $("#portfolioTotalCost").textContent=totalsComplete?`NT$ ${fmt(totalCost,0)}`:"—";
    $("#portfolioTotalPL").textContent=cumulative==null?"—":`${cumulative>=0?"+":"-"}NT$ ${fmt(Math.abs(cumulative),0)}`;
    $("#portfolioTotalPL").className=cumulative==null?"flat":cls(cumulative);
    $("#portfolioReturn").textContent=totalsComplete?pct(returnPct):"—";$("#portfolioReturn").className=totalsComplete?cls(returnPct):"flat";
    $("#portfolioDayPL").textContent=dayComplete?`${dayPL>=0?"+":"-"}NT$ ${fmt(Math.abs(dayPL),0)}`:"—";$("#portfolioDayPL").className=dayComplete?cls(dayPL):"flat";
    $("#portfolioDayReturn").textContent=dayComplete?pct(dayPct):"—";$("#portfolioDayReturn").className=dayComplete?cls(dayPct):"flat";
    $("#portfolioStatus").textContent=!rows.length?"尚未設定":unconverted?`未換匯 ${unconverted} 項`:totalsComplete?"行情完整":`行情不完整 ${valued}/${rows.length}`;
    const totalAllocated=[...allocation.values()].reduce((a,b)=>a+b,0);
    $("#portfolioAllocation").innerHTML=totalsComplete&&totalAllocated?`<div class="allocation-bar">${[...allocation.entries()].map(([name,value])=>`<span style="flex:${Math.max(value,1)}" title="${escapeHtml(name)} ${((value/totalAllocated)*100).toFixed(1)}%"></span>`).join("")}</div><div class="allocation-labels">${[...allocation.entries()].sort((a,b)=>b[1]-a[1]).map(([name,value])=>`<span><i></i>${escapeHtml(name)} <b>${((value/totalAllocated)*100).toFixed(1)}%</b></span>`).join("")}</div>`:rows.length?'<div class="empty">資料不完整時不顯示部分配置比例。</div>':'<div class="empty">尚未加入投資標的。</div>';
    const missingQuote=Math.max(0,rows.length-valued-unconverted);
    const notes=[];
    if(unconverted)notes.push(`${unconverted} 項資產缺少可用匯率，因此 NT$ 總資產與損益暫不顯示`);
    if(missingQuote)notes.push(`${missingQuote} 項資產尚未取得最新行情`);
    $("#portfolioEstimateNote").textContent=notes.length?`${notes.join("；")}。`:"";
  }
  renderPortfolioSummary();window.addEventListener("portfoliochange",renderPortfolioSummary);

  const marketKlineSymbols=["^TWII","^DJI","^IXIC","^SOX","^GSPC","^N225"];
  const safeNumber=value=>finite(value);
  const normalizedCandles=row=>(Array.isArray(row?.candles)?row.candles:[]).map(candle=>({
    date:String(candle?.date||""),open:safeNumber(candle?.open),high:safeNumber(candle?.high),low:safeNumber(candle?.low),close:safeNumber(candle?.close),volume:safeNumber(candle?.volume)
  })).filter(candle=>candle.date&&[candle.open,candle.high,candle.low,candle.close].every(value=>value!=null)).slice(-60);
  const candleFallback=row=>{
    const candle={date:String(row?.market_at||"").slice(0,10),open:safeNumber(row?.open),high:safeNumber(row?.high),low:safeNumber(row?.low),close:safeNumber(row?.close??row?.price),volume:safeNumber(row?.volume)};
    return candle.date&&[candle.open,candle.high,candle.low,candle.close].every(value=>value!=null)?[candle]:[];
  };
  const buildCandlestickSvg=row=>{
    const candles=normalizedCandles(row);const series=candles.length?candles:candleFallback(row);
    if(series.length<2)return '<div class="market-kline-empty-plot"><strong>等待歷史 K 線</strong><span>資料排程更新後會自動顯示。</span></div>';
    const width=520,height=160,pad={top:12,right:12,bottom:22,left:12};
    const highs=series.map(candle=>candle.high),lows=series.map(candle=>candle.low),max=Math.max(...highs),min=Math.min(...lows),span=Math.max(max-min,Math.abs(max)*0.002,1e-6);
    const chartHeight=height-pad.top-pad.bottom,chartWidth=width-pad.left-pad.right,step=chartWidth/series.length,bodyWidth=Math.max(2,Math.min(8,step*.62));
    const y=value=>pad.top+((max-value)/span)*chartHeight;
    const grid=[0,.25,.5,.75,1].map(ratio=>{const lineY=pad.top+ratio*chartHeight;return `<line class="kline-grid-line" x1="${pad.left}" x2="${width-pad.right}" y1="${lineY.toFixed(2)}" y2="${lineY.toFixed(2)}"></line>`}).join("");
    const bodies=series.map((candle,index)=>{
      const x=pad.left+step*(index+.5),openY=y(candle.open),closeY=y(candle.close),highY=y(candle.high),lowY=y(candle.low),top=Math.min(openY,closeY),bodyHeight=Math.max(1.5,Math.abs(closeY-openY)),tone=candle.close>=candle.open?"up":"down";
      const title=`${escapeHtml(candle.date)} 開 ${fmt(candle.open)} 高 ${fmt(candle.high)} 低 ${fmt(candle.low)} 收 ${fmt(candle.close)}`;
      return `<g class="market-candle ${tone}"><title>${title}</title><line x1="${x.toFixed(2)}" x2="${x.toFixed(2)}" y1="${highY.toFixed(2)}" y2="${lowY.toFixed(2)}"></line><rect x="${(x-bodyWidth/2).toFixed(2)}" y="${top.toFixed(2)}" width="${bodyWidth.toFixed(2)}" height="${bodyHeight.toFixed(2)}" rx="1"></rect></g>`;
    }).join("");
    const last=series.at(-1),lastY=y(last.close),firstDate=series[0].date.slice(5),lastDate=last.date.slice(5);
    return `<svg viewBox="0 0 ${width} ${height}" class="market-kline-svg" role="img" aria-label="${escapeHtml(row.name||row.symbol)} 最近 ${series.length} 個交易日日 K">${grid}${bodies}<line class="kline-last-line" x1="${pad.left}" x2="${width-pad.right}" y1="${lastY.toFixed(2)}" y2="${lastY.toFixed(2)}"></line><text class="kline-date-label" x="${pad.left}" y="${height-5}">${escapeHtml(firstDate)}</text><text class="kline-date-label end" x="${width-pad.right}" y="${height-5}">${escapeHtml(lastDate)}</text></svg>`;
  };

  const timeframeOptions=[
    ["5m","5分"],["15m","15分"],["30m","30分"],["60m","1小時"],["4h","4小時"],["1d","日"],["1wk","週"],["1mo","月"]
  ];
  const klineCharts=new Map();
  function destroyKlineCharts(){for(const value of klineCharts.values()){try{value.resizeObserver?.disconnect();value.chart?.remove()}catch(e){}}klineCharts.clear()}
  function snapshotChartRows(row){return normalizedCandles(row).map(candle=>({time:candle.date,open:candle.open,high:candle.high,low:candle.low,close:candle.close,volume:candle.volume}));}
  function attachInteractiveChart(row,interval="1d",providedRows=null){
    const symbol=String(row.symbol||"").toUpperCase(),container=document.querySelector(`[data-kline-chart="${CSS.escape(symbol)}"]`),tooltip=document.querySelector(`[data-kline-tooltip="${CSS.escape(symbol)}"]`);
    if(!container)return;
    const old=klineCharts.get(symbol);if(old){try{old.resizeObserver?.disconnect();old.chart?.remove()}catch(e){}klineCharts.delete(symbol)}
    const rows=providedRows||snapshotChartRows(row);
    if(!window.LightweightCharts||rows.length<2){container.innerHTML=buildCandlestickSvg({...row,candles:rows.map(x=>({...x,date:String(x.time).slice(0,10)}))});if(tooltip)tooltip.textContent=`${interval} · 滑鼠停在 K 棒查看 OHLC`;return}
    container.innerHTML="";
    const chart=LightweightCharts.createChart(container,{width:container.clientWidth||460,height:190,layout:{background:{color:"transparent"},textColor:"#8fb4d1"},grid:{vertLines:{color:"rgba(113,164,198,.10)"},horzLines:{color:"rgba(113,164,198,.10)"}},rightPriceScale:{borderColor:"rgba(113,164,198,.25)"},timeScale:{borderColor:"rgba(113,164,198,.25)",timeVisible:!["1d","1wk","1mo"].includes(interval),secondsVisible:false},crosshair:{mode:LightweightCharts.CrosshairMode.Normal},handleScroll:{mouseWheel:true,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},handleScale:{axisPressedMouseMove:true,mouseWheel:true,pinch:true}});
    const series=chart.addCandlestickSeries({upColor:"#27d3a2",downColor:"#ff5e78",borderUpColor:"#27d3a2",borderDownColor:"#ff5e78",wickUpColor:"#27d3a2",wickDownColor:"#ff5e78"});
    series.setData(rows.map(x=>({time:x.time,open:x.open,high:x.high,low:x.low,close:x.close})));
    chart.timeScale().fitContent();
    chart.subscribeCrosshairMove(param=>{const data=param.seriesData.get(series);if(!tooltip)return;if(!data||!param.time){tooltip.textContent=`${interval} · 移動游標查看 OHLC`;return}tooltip.textContent=`${typeof param.time==="string"?param.time:new Date(Number(param.time)*1000).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false})}　開 ${fmt(data.open)}　高 ${fmt(data.high)}　低 ${fmt(data.low)}　收 ${fmt(data.close)}`});
    const resizeObserver=new ResizeObserver(()=>chart.applyOptions({width:container.clientWidth||460}));resizeObserver.observe(container);
    klineCharts.set(symbol,{chart,series,resizeObserver,interval});
  }
  async function switchKlineInterval(button,row){
    const symbol=String(row.symbol||"").toUpperCase(),interval=button.dataset.klineInterval;
    document.querySelectorAll(`[data-kline-symbol="${CSS.escape(symbol)}"] [data-kline-interval]`).forEach(item=>item.classList.toggle("active",item===button));
    const status=document.querySelector(`[data-kline-tooltip="${CSS.escape(symbol)}"]`);if(status)status.textContent=`正在載入 ${button.textContent} K…`;
    try{const payload=interval==="1d"?{candles:snapshotChartRows(row),source:row.candle_source}:await loadMarketKline(symbol,interval);attachInteractiveChart(row,interval,payload.candles);if(status)status.textContent=`${button.textContent} K · ${payload.source||"行情來源"} · 游標查看 OHLC`}
    catch(error){button.disabled=true;button.title=String(error.message||error);if(status)status.textContent=`${button.textContent} K 尚未同步；下一次行情更新後會自動重試`}
  }
  function mountInteractiveCharts(rows){
    rows.forEach(row=>{attachInteractiveChart(row,"1d");const symbol=String(row.symbol||"").toUpperCase();document.querySelectorAll(`[data-kline-symbol="${CSS.escape(symbol)}"] [data-kline-interval]`).forEach(button=>button.onclick=()=>switchKlineInterval(button,row));});
  }
  function renderMarketKlines(){
    const marketKlineMap=new Map((snapshot.items||[]).map(item=>[String(item.symbol||"").toUpperCase(),item]));
    const rows=marketKlineSymbols.map(symbol=>marketKlineMap.get(symbol)).filter(Boolean);
    const liveEndpoint=getLiveMarketEndpoint?.()||"";
    const loadSource=String(snapshot.metadata?.frontend_load_source||"");
    const workerActive=!!liveEndpoint&&loadSource==="worker";
    const sourceLabel=workerActive?"Worker 即時通道・盤中每分鐘刷新":"GitHub 備援・非即時・每分鐘重試";
    $("#marketKlineUpdated").textContent=snapshot.metadata?.updated_at?`${formatTime(snapshot.metadata.updated_at)} · ${sourceLabel}` :"等待資料";
    destroyKlineCharts();
    $("#marketKlineGrid").innerHTML=rows.length?rows.map(row=>{
      const candles=normalizedCandles(row),latest=candles.at(-1)||candleFallback(row).at(-1)||{};
      const open=safeNumber(latest.open??row.open),high=safeNumber(latest.high??row.high),low=safeNumber(latest.low??row.low),close=safeNumber(row.price??latest.close),changePct=safeNumber(row.change_percent),change=safeNumber(row.change);
      const priceLabel=close!=null?`${fmt(close)}${escapeHtml(row.display_suffix||"")}`:"—";
      const changeLabel=change!=null?`${change>=0?'+':''}${fmt(change)}${escapeHtml(row.display_suffix||"")}`:"—";
      const cached=row.data_status==="cached",cachedKline=row.data_status==="cached-kline",stale=row.freshness_status==="stale"||row.data_status==="stale",unconfirmed=row.freshness_status==="unconfirmed";
      const statusLabel=stale?(row.stale_reason||`資料停留於 ${row.session_date||"舊交易日"}`):unconfirmed?(row.stale_reason||"尚未確認今日交易資料"):cached?"整筆使用快取":cachedKline?"K 線使用上次成功資料":row.market_open?(workerActive?"Worker 盤中每分鐘刷新":"GitHub 備援・非即時"):"收盤資料已驗證";
      const statusClass=stale?"waiting":(cached||cachedKline)?"cached":candles.length>=10?"live":"waiting";
      const source=row.candle_source||row.source||"資料來源待更新";
      return `<article class="market-kline-card"><div class="market-kline-head"><div><small>${escapeHtml(row.market||"MARKET")}</small><h3>${escapeHtml(row.name||row.symbol)}</h3></div><div class="market-kline-price"><strong>${priceLabel}</strong><span class="${cls(changePct)}">${pct(changePct)}</span></div></div><div class="market-kline-status"><span class="kline-status ${statusClass}">${escapeHtml(statusLabel)}</span><small>近 ${candles.length||0} 個交易日</small></div><div class="kline-timeframes" data-kline-symbol="${escapeHtml(String(row.symbol||"").toUpperCase())}">${timeframeOptions.map(([value,label])=>`<button type="button" class="${value==="1d"?"active":""}" data-kline-interval="${value}">${label}</button>`).join("")}</div><div class="kline-hover-readout" data-kline-tooltip="${escapeHtml(String(row.symbol||"").toUpperCase())}">日 K · 滑鼠停在 K 棒查看 OHLC</div><div class="market-kline-visual market-kline-interactive" data-kline-chart="${escapeHtml(String(row.symbol||"").toUpperCase())}">${buildCandlestickSvg(row)}</div><div class="market-kline-stats"><span><small>開</small><b>${open!=null?fmt(open):"—"}</b></span><span><small>高</small><b>${high!=null?fmt(high):"—"}</b></span><span><small>低</small><b>${low!=null?fmt(low):"—"}</b></span><span><small>差</small><b class="${cls(change)}">${changeLabel}</b></span></div><div class="market-kline-source"><span>${escapeHtml(source)}${row.session_date?` · 交易日 ${escapeHtml(row.session_date)}`:""}</span><time>${escapeHtml(formatTime(row.market_at))}</time></div></article>`;
    }).join(""):'<div class="empty">等待大盤資料更新</div>';
    if(rows.length)requestAnimationFrame(()=>mountInteractiveCharts(rows));
  }
  renderMarketKlines();

  const anyTrackedMarketOpen=()=>{
    const now=new Date();
    const parts=(tz)=>Object.fromEntries(new Intl.DateTimeFormat("en-US",{timeZone:tz,weekday:"short",hour:"2-digit",minute:"2-digit",hour12:false}).formatToParts(now).map(part=>[part.type,part.value]));
    const within=(tz,start,end)=>{const p=parts(tz),week=!['Sat','Sun'].includes(p.weekday),minutes=Number(p.hour)*60+Number(p.minute);return week&&minutes>=start&&minutes<=end};
    return within("Asia/Taipei",535,815)||within("Asia/Tokyo",535,930)||within("America/New_York",565,965);
  };
  let liveRefreshTimer=null,refreshInFlight=false,lastLiveRefreshAt=Date.now();
  const liveRefreshGap=()=>anyTrackedMarketOpen()?45000:300000;
  async function refreshLiveMarketData({force=false}={}){
    if(refreshInFlight||document.hidden)return;
    if(!force&&Date.now()-lastLiveRefreshAt<liveRefreshGap())return;
    refreshInFlight=true;lastLiveRefreshAt=Date.now();
    try{
      const [freshSnapshot,freshTw,freshChips]=await Promise.all([
        loadData("market-snapshot.json",snapshot||window.__MARKET_SNAPSHOT_SEED__||{items:[]},{force:true}),
        loadData("tw-market-compact.json",tw||window.__TW_MARKET_SEED__||{items:[]},{force:true}),
        loadData("tw-chips-compact.json",chips||window.__TW_CHIPS_SEED__||{markets:{},items:{}},{force:true})
      ]);
      snapshot=freshSnapshot;tw=freshTw;chips=freshChips;
      rebuildQuotes();
      renderMarketList();renderTaiwanStatus();renderMarketKlines();renderPortfolioSummary();renderTodayBrief();
    }catch(error){console.warn("live market refresh failed",error)}finally{
      refreshInFlight=false;
      clearTimeout(liveRefreshTimer);
      liveRefreshTimer=setTimeout(()=>refreshLiveMarketData({force:true}),anyTrackedMarketOpen()?60000:900000);
    }
  }
  liveRefreshTimer=setTimeout(()=>refreshLiveMarketData({force:true}),anyTrackedMarketOpen()?60000:900000);
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshLiveMarketData()});
  window.addEventListener("focus",()=>refreshLiveMarketData());


  let safeNews=[];
  let todayKey="",tomorrowKey="",afterTomorrowKey="";
  const datePlus=days=>{const d=new Date();d.setDate(d.getDate()+days);return localKey(d)};
  const refreshDayKeys=()=>{todayKey=localKey(new Date());tomorrowKey=datePlus(1);afterTomorrowKey=datePlus(2)};
  refreshDayKeys();
  const eventWhenLabel=event=>{
    if(event?.all_day===true||event?.time_status==="date-only"){
      const day=eventDateKey(event);return day?`${day} · 時間未公告`:"日期已確認 · 時間未公告";
    }
    return formatEventTime(event);
  };
  const eventFeedReady=()=>{
    const source=String(events?.metadata?.frontend_load_source||"");
    return ["raw-live-branch","jsdelivr-live-branch","statically-live-branch","github-api-live-branch","browser-last-good"].includes(source)||Number(events?.metadata?.full_event_count||0)>500;
  };
  const featureCard=(item,kind)=>{const image=renderNewsThumb(item,kind==="lead"?"large":"small",{alt:item.title,eager:true}).replace('class="news-thumb large','class="home-news-thumb large-thumb').replace('class="news-thumb small','class="home-news-thumb side-thumb');const brief=truncate(item.ai_summary||item.summary||item.title,kind==="lead"?92:52)||"查看完整內容。";const external=item._featureKind==="news"?' target="_blank" rel="noreferrer noopener"':'';const category=item._majorCategory||majorCategory(item);return `<a class="${kind==="lead"?"home-feature-lead":"home-feature-side"}" href="${escapeHtml(item._featureKind==="event"?String(item.url||"#"):(safeExternalHref(item.url)||"#"))}"${external}>${image}<div class="home-feature-copy"><div class="news-meta"><span class="feature-time-label">${escapeHtml(item._featureLabel)}</span><span class="feature-category cat-${escapeHtml(slugCategory(category))}">${escapeHtml(category)}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(brief)}</p></div></a>`};
  const featuredEvent=event=>eventGroup(event)==="major"||(eventGroup(event)==="company"&&event.impact==="high");
  function rebuildSafeNews(){
    const mediaItems=[...(news.items||[]),...(stockNews.items||[])],next=[],seenNews=new Set();
    for(const item of mediaItems){
      if(item.source_id==="company-disclosures")continue;
      const title=strip(item.title),key=strip(item.canonical_url||item.url||title).toLowerCase();
      if(!title||!/^https:\/\//i.test(String(item.url||""))||seenNews.has(key))continue;
      const normalized={...item,title},score=majorScore(normalized),category=majorCategory(normalized);
      // Raw official notices are noisy; surface them only when they qualify as major/systemic/market-structure information.
      if(item.source_id==="official-notices"&&score<45)continue;
      seenNews.add(key);next.push({...normalized,_majorScore:score,_majorCategory:category});
    }
    next.sort((a,b)=>Date.parse(b.published_at||0)-Date.parse(a.published_at||0)||b._majorScore-a._majorScore);
    safeNews=next;
  }
  const selectDiverseNews=(rows,limit)=>{
    const sorted=[...rows].sort((a,b)=>b._majorScore-a._majorScore||b._featureTime-a._featureTime),chosen=[],counts=new Map();
    for(const item of sorted){
      const category=item._majorCategory||majorCategory(item),used=counts.get(category)||0;
      // A true breaking/systemic item may bypass the normal two-per-industry cap.
      if(used>=2&&item._majorScore<88)continue;
      chosen.push(item);counts.set(category,used+1);
      if(chosen.length>=limit)break;
    }
    if(chosen.length<limit){for(const item of sorted){if(!chosen.includes(item)){chosen.push(item);if(chosen.length>=limit)break}}}
    return chosen;
  };
  const explicitNewsDate=(item)=>{
    const text=strip(`${item.title||""} ${item.summary||""} ${item.ai_summary||""}`),published=new Date(item.published_at||item.date||Date.now());
    let match=text.match(/(?<!\d)(20\d{2})[\/.\-年](\d{1,2})[\/.\-月](\d{1,2})日?(?!\d)/);
    let year,month,day;
    if(match){year=Number(match[1]);month=Number(match[2]);day=Number(match[3])}
    else{
      match=text.match(/(?<!\d)(\d{1,2})[\/.](\d{1,2})(?!\d)|(?<!\d)(\d{1,2})月(\d{1,2})日/);
      if(!match)return"";
      year=Number.isFinite(+published.getFullYear())?published.getFullYear():new Date().getFullYear();month=Number(match[1]||match[3]);day=Number(match[2]||match[4]);
    }
    const date=new Date(year,month-1,day,9,0,0);if(Number.isNaN(+date)||date.getMonth()!==month-1||date.getDate()!==day)return"";
    const pub=Number.isNaN(+published)?Date.now():+published,delta=(+date-pub)/86400000;
    if(delta<-2||delta>370)return"";
    return localKey(date);
  };
  const NEWS_EVENT_ACTION_RE=/上路|生效|實施|開放|啟用|正式交易|掛牌|截止|決策|利率|財報|法說|發表會|開幕|展開|禁令|關稅|出口管制|停產|恢復交易|暫停交易/i;
  const derivedNewsEvents=()=>safeNews.filter(item=>item._majorScore>=50&&NEWS_EVENT_ACTION_RE.test(`${item.title||""} ${item.summary||""}`)).map(item=>{
    const day=explicitNewsDate(item);if(!day)return null;
    const reports=(item.other_reports||[]).length,sourceId=String(item.source_id||"");
    const corroborated=reports>0||["cna","official-notices"].includes(sourceId);
    if(!corroborated)return null; // single-media dates remain news, not confirmed calendar facts
    const category=item._majorCategory||majorCategory(item),id=`news-date-${day}-${slugCategory(item.canonical_url||item.url||item.title).slice(-72)}`;
    return {id,tracking_key:id,title:strip(item.title),start:`${day}T00:00:00+08:00`,local_date:day,category:"major-news-date",event_type:"news-confirmed-date",event_group:"macro",region:item.region||"GLOBAL",impact:item._majorScore>=78?"high":"medium",description:strip(item.ai_summary||item.summary||"新聞已明確報導此日期。"),market_effect:"此日期由重大新聞明確指出並具多來源／主要媒體佐證；仍應以主管機關或公司後續正式公告為最終依據。",source_name:item.source||item.publisher||"多來源重大新聞",source_url:item.url,origin:"news-derived",all_day:true,tags:[category,"重大新聞日期"],verification_status:"reported-corroborated",time_status:"date-only",date_basis:"explicit-date-in-corroborated-news"};
  }).filter(Boolean);
  const calendarEvents=()=>uniqueEvents([...(events.events||[]),...derivedNewsEvents()]);
  function renderFeaturedInfo(){
    rebuildSafeNews();
    const nowMs=Date.now();
    const majorRetentionMs=item=>{
      const text=`${item.title||""} ${item.summary||""} ${item.ai_summary||""}`;
      if(isMarketStructure(text)||SYSTEMIC_RE.test(text)||CENTRAL_BANK_RE.test(text)||GEOPOLITICAL_RE.test(text))return 72*3600000;
      if(BREAKING_RE.test(text))return 48*3600000;
      return 24*3600000;
    };
    const validRecentNews=item=>{const published=Date.parse(item.published_at||item.date||0),age=nowMs-published;return Number.isFinite(age)&&age>=-300000&&age<=majorRetentionMs(item)};
    const recentMajorNews=safeNews.filter(item=>validRecentNews(item)&&item._majorScore>=45).map(item=>{
      const retention=majorRetentionMs(item),storyText=`${item.title||""} ${item.summary||""} ${item.ai_summary||""}`,label=BREAKING_RE.test(storyText)&&item._majorScore>=70?"突發／關鍵":retention>24*3600000?"持續重大":"近24小時重大";
      return {...item,_featureKind:"news",_featureTime:Date.parse(item.published_at||item.date||0),_featureLabel:label};
    });
    const recentPhotoNews=safeNews.filter(item=>{const published=Date.parse(item.published_at||item.date||0),age=nowMs-published;return Number.isFinite(age)&&age>=-300000&&age<=86400000&&newsHasImage(item)&&item._majorScore>=35}).map(item=>({...item,_featureKind:"news",_featureTime:Date.parse(item.published_at||item.date||0),_featureLabel:"今日焦點"}));
    const upcomingMajorEvents=uniqueEvents((events.events||[]).filter(event=>{const day=eventDateKey(event);return featuredEvent(event)&&[todayKey,tomorrowKey,afterTomorrowKey].includes(day)})).map(event=>{
      const day=eventDateKey(event),start=Date.parse(event.start||0),dateOnly=event.all_day===true||event.time_status==="date-only",label=day===todayKey?(dateOnly?"今日日期事件":start>nowMs?"今日稍後":"今日已公布"):day===tomorrowKey?"明日":"後天";
      const featureAt=dateOnly?Date.parse(`${day}T12:00:00+08:00`):start;
      return {id:event.id,title:event.title,summary:event.description||event.market_effect||"查看重大事件內容。",ai_summary:event.description||event.market_effect,ai_category:event.region||"重大事件",topic:event.category||"macro",impact:event.impact,is_major:true,_majorScore:event.impact==="high"?100:72,_featureKind:"event",_featureTime:Number.isFinite(featureAt)?featureAt:nowMs,_featureLabel:label,url:`event.html?id=${encodeURIComponent(event.id)}`,published_at:event.start,source:event.source_name||"官方行事曆",fallback_image_slug:/利率|央行|FOMC/i.test(event.title||"")?"rates":"macro"};
    });
    const featureRank={"突發／關鍵":0,"今日日期事件":1,"今日稍後":2,"今日已公布":3,"近24小時重大":4,"持續重大":5,"今日焦點":6,"明日":7,"後天":8,"近期事件":9,"最近可用":10};
    const visualNews=selectDiverseNews([...recentMajorNews,...recentPhotoNews].filter((item,index,rows)=>rows.findIndex(row=>row.url===item.url)===index),3);
    const eventSlots=upcomingMajorEvents.sort((a,b)=>(featureRank[a._featureLabel]??99)-(featureRank[b._featureLabel]??99)||b._majorScore-a._majorScore||a._featureTime-b._featureTime).slice(0,2);
    // If today's media channels are slow/empty, keep the homepage useful with the
    // next confirmed major dates, then the latest verified major stories.  The
    // labels make the fallback age explicit instead of pretending it is breaking.
    const futureLimit=new Date();futureLimit.setDate(futureLimit.getDate()+14);const futureLimitKey=localKey(futureLimit);
    const fallbackEvents=uniqueEvents((events.events||[]).filter(event=>{const day=eventDateKey(event);return featuredEvent(event)&&day>=todayKey&&day<=futureLimitKey})).map(event=>{
      const day=eventDateKey(event),start=Date.parse(event.start||0),dateOnly=event.all_day===true||event.time_status==="date-only",featureAt=dateOnly?Date.parse(`${day}T12:00:00+08:00`):start;
      return {id:event.id,title:event.title,summary:event.description||event.market_effect||"查看重大事件內容。",ai_summary:event.description||event.market_effect,ai_category:event.region||"重大事件",topic:event.category||"macro",impact:event.impact,is_major:true,_majorScore:event.impact==="high"?88:68,_featureKind:"event",_featureTime:Number.isFinite(featureAt)?featureAt:nowMs,_featureLabel:"近期事件",url:`event.html?id=${encodeURIComponent(event.id)}`,published_at:event.start,source:event.source_name||"官方行事曆",fallback_image_slug:/利率|央行|FOMC/i.test(event.title||"")?"rates":"macro"};
    }).sort((a,b)=>a._featureTime-b._featureTime).slice(0,6);
    const fallbackNews=safeNews.filter(item=>{const published=Date.parse(item.published_at||item.date||0),age=nowMs-published;return Number.isFinite(age)&&age>=-300000&&age<=7*86400000&&item._majorScore>=35}).map(item=>({...item,_featureKind:"news",_featureTime:Date.parse(item.published_at||item.date||0),_featureLabel:"最近可用"})).sort((a,b)=>b._majorScore-a._majorScore||b._featureTime-a._featureTime).slice(0,8);
    const candidates=[...visualNews,...eventSlots,...fallbackEvents,...fallbackNews].sort((a,b)=>(featureRank[a._featureLabel]??99)-(featureRank[b._featureLabel]??99)||b._majorScore-a._majorScore||b._featureTime-a._featureTime);
    const featured=[],featureSeen=new Set();
    for(const item of candidates){const key=String(item.url||item.id||item.title||"").toLowerCase();if(!key||featureSeen.has(key))continue;featureSeen.add(key);featured.push(item);if(featured.length>=4)break}
    const latest=featured[0];
    const breaking=$("#breakingLink");if(latest&&breaking){const cat=latest._majorCategory||majorCategory(latest);breaking.textContent=`${latest._featureLabel}｜${cat}｜${strip(latest.title)}`;breaking.href=latest.url}else if(breaking){breaking.textContent="重大資訊持續同步中…";breaking.href="news.html"}
    const homeNews=$("#homeNews");if(!homeNews)return;
    homeNews.className="home-news-feature-layout";
    if(featured.length){const lead=featured[0],side=featured.slice(1,4);homeNews.innerHTML=`${featureCard(lead,"lead")}<div class="home-feature-side-list">${side.map(item=>featureCard(item,"side")).join("")}</div>`}
    else homeNews.innerHTML='<div class="empty">重大資訊同步中；已有來源會先顯示，不等待全部新聞通道。</div>';
  }
  function renderTodayFocus(){
    const todayEvents=uniqueEvents(calendarEvents().filter(event=>eventDateKey(event)===todayKey));
    const majorToday=todayEvents.filter(featuredEvent).sort((a,b)=>Number(b.impact==="high")-Number(a.impact==="high"));
    const node=$("#todayFocusList");if(node)node.innerHTML=majorToday.length?majorToday.slice(0,6).map(event=>`<a class="today-focus-item" href="event.html?id=${encodeURIComponent(event.id)}"><span class="impact-dot ${escapeHtml(event.impact||"medium")}"></span><span><strong>${escapeHtml(strip(event.title))}</strong><small>${escapeHtml(eventWhenLabel(event))}</small></span></a>`).join(""):(eventFeedReady()?'<div class="empty">今天沒有已確認的高影響事件</div>':'<div class="empty">線上事件資料同步中</div>');
  }
  const isMacroCalendarEvent=event=>{
    const text=`${event?.title||""} ${event?.description||event?.summary||""} ${event?.category||""} ${event?.event_type||""}`;
    return CENTRAL_BANK_RE.test(text)||MACRO_RE.test(text);
  };
  const median=values=>{
    const rows=(values||[]).filter(Number.isFinite).sort((a,b)=>a-b);if(!rows.length)return null;
    const mid=Math.floor(rows.length/2);return rows.length%2?rows[mid]:(rows[mid-1]+rows[mid])/2;
  };
  const HOME_INDUSTRY_NAMES={"01":"水泥工業","02":"食品工業","03":"塑膠工業","04":"紡織纖維","05":"電機機械","06":"電器電纜","07":"化學生技醫療","08":"玻璃陶瓷","09":"造紙工業","10":"鋼鐵工業","11":"橡膠工業","12":"汽車工業","13":"電子工業","14":"建材營造","15":"航運業","16":"觀光餐旅","17":"金融保險業","18":"貿易百貨","20":"其他業","21":"化學工業","22":"生技醫療業","23":"油電燃氣業","24":"半導體業","25":"電腦及週邊設備業","26":"光電業","27":"通信網路業","28":"電子零組件業","29":"電子通路業","30":"資訊服務業","31":"其他電子業","32":"文化創意業","33":"農業科技業","34":"電子商務","35":"綠能環保","36":"數位雲端","37":"運動休閒","38":"居家生活"};
  const normalizeHomeIndustry=value=>{
    const raw=String(value||"").trim();if(!raw)return"";
    const numeric=raw.match(/^0?(\d{1,3})$/);
    if(numeric)return HOME_INDUSTRY_NAMES[String(numeric[1]).padStart(2,"0")]||"";
    // Numeric taxonomy values such as 91 are source codes, never user-facing labels.
    if(/^\d+(?:[.\-]\d+)?$/.test(raw))return"";
    return raw;
  };
  const validHomeIndustryLabel=value=>{const label=normalizeHomeIndustry(value);return label&&!/^\d/.test(label)&&!/ETF|基金/.test(label)?label:"";};
  function renderMarketInsights(){
    const breadth=tw.breadth||{},up=Math.max(0,finite(breadth.up)||0),down=Math.max(0,finite(breadth.down)||0),flat=Math.max(0,finite(breadth.flat)||0),total=up+down+flat;
    const heat=total?Math.round(up/total*100):null,heatLabel=heat==null?"等待資料":heat>=75?"全面偏強":heat>=60?"偏強":heat>=45?"均衡":heat>=30?"偏弱":"低迷";
    const heatScore=$("#marketHeatScore"),heatText=$("#marketHeatLabel"),heatFill=$("#marketHeatFill");
    if(heatScore)heatScore.textContent=heat==null?"—":String(heat);if(heatText)heatText.textContent=heatLabel;if(heatFill)heatFill.style.width=`${heat==null?0:Math.max(0,Math.min(100,heat))}%`;
    const heatValues={marketHeatUp:total?up:"—",marketHeatDown:total?down:"—",marketHeatFlat:total?flat:"—"};for(const [id,value] of Object.entries(heatValues)){const node=$("#"+id);if(node)node.textContent=value}
    const marketDate=String(tw.metadata?.trading_date||"");const heatDate=$("#marketHeatDate");if(heatDate)heatDate.textContent=marketDate?`交易日 ${marketDate}`:"等待官方交易日";

    const chipDate=String(chips.metadata?.trading_date||""),chipsCurrent=!marketDate||!chipDate||marketDate===chipDate,foreignParts=[finite(chips.markets?.twse?.institutional?.foreign_net),finite(chips.markets?.tpex?.institutional?.foreign_net)].filter(value=>value!=null),foreignNet=chipsCurrent&&foreignParts.length?foreignParts.reduce((sum,value)=>sum+value,0):null;
    const directional=up+down?up/(up+down):null,eventReady=eventFeedReady(),highEvents=eventReady?calendarEvents().filter(event=>eventDateKey(event)===todayKey&&event.impact==="high"&&eventGroup(event)!=="dividend").length:0,volumeRatio=finite(tw.metadata?.volume_ratio_20d);
    let riskPoints=0;const reasons=[];
    if(directional!=null&&(directional<=.30||directional>=.75)){riskPoints+=2;reasons.push(directional>=.75?"盤面過熱":"盤面偏弱")}
    if(highEvents>=2){riskPoints+=2;reasons.push(`${highEvents} 件高影響事件`)}else if(highEvents===1){riskPoints+=1;reasons.push("1 件高影響事件")}
    if(foreignNet!=null&&foreignNet<0&&directional!=null&&directional<.5){riskPoints+=1;reasons.push("外資偏賣")}
    if(volumeRatio!=null&&volumeRatio>=1.35){riskPoints+=1;reasons.push("成交明顯放大")}
    const riskWaiting=directional==null||!eventReady,riskLabel=riskWaiting?"資料同步中":riskPoints>=4?"高":riskPoints>=2?"中":"低",riskPct=riskWaiting?0:Math.min(100,Math.round(riskPoints/6*100));
    const riskPanel=$("#todayRiskPanel"),riskNode=$("#todayRiskLabel"),riskFill=$("#todayRiskFill"),riskDetail=$("#todayRiskDetail");
    if(riskPanel)riskPanel.dataset.risk=riskWaiting?"waiting":riskLabel==="高"?"high":riskLabel==="中"?"medium":"low";if(riskNode)riskNode.textContent=riskLabel;if(riskFill)riskFill.style.width=`${riskPct}%`;if(riskDetail)riskDetail.textContent=riskWaiting?(directional==null?"等待最新市場廣度後再判定。":"市場行情已到，但完整事件資料仍在同步。"):(reasons.length?reasons.join(" · "):"市場廣度、法人與事件暫無明顯風險訊號。");

    const groups=new Map();
    for(const row of tw.items||[]){
      if(String(row.asset_class||"").toLowerCase()!=="stock")continue;const change=finite(row.change_percent);if(change==null)continue;
      const asset=assetMap.get(String(row.symbol||"").toUpperCase())||{},industry=validHomeIndustryLabel(asset.official_industry||row.official_industry||asset.sub_industry||row.sub_industry||"");if(!industry)continue;
      if(!groups.has(industry))groups.set(industry,[]);groups.get(industry).push(change);
    }
    let sectors=[...groups].map(([name,values])=>({name,count:values.length,move:median(values)})).filter(row=>row.move!=null&&row.count>=3);
    if(sectors.length<4)sectors=[...groups].map(([name,values])=>({name,count:values.length,move:median(values)})).filter(row=>row.move!=null&&row.count>=2);
    sectors.sort((a,b)=>b.move-a.move||b.count-a.count);const top=sectors.slice(0,3),topNames=new Set(top.map(row=>row.name)),bottom=[...sectors].reverse().filter(row=>!topNames.has(row.name)).slice(0,3);
    const sectorNode=$("#sectorMomentum"),sectorUpdated=$("#sectorMomentumUpdated");
    const sectorRows=rows=>rows.length?rows.map((row,index)=>`<div class="sector-momentum-row"><span><b>${index+1}</b><strong>${escapeHtml(row.name)}</strong><small>${row.count} 檔</small></span><em class="${cls(row.move)}">${pct(row.move)}</em></div>`).join(""):'<div class="empty">資料不足</div>';
    if(sectorNode)sectorNode.innerHTML=sectors.length?`<div class="sector-momentum-group"><h3>強勢 TOP 3</h3>${sectorRows(top)}</div><div class="sector-momentum-group"><h3>弱勢 TOP 3</h3>${sectorRows(bottom)}</div>`:'<div class="empty">等待完整台股行情與產業分類資料</div>';
    if(sectorUpdated)sectorUpdated.textContent=marketDate&&sectors.length?`交易日 ${marketDate} · ${sectors.length} 個產業`:marketDate?`交易日 ${marketDate} · 產業資料同步中`:"等待完整台股行情";
  }
  function renderTodayBrief(){
    const node=$("#todayBriefSentence");if(!node)return;
    const breadth=tw.breadth||{},up=finite(breadth.up)||0,down=finite(breadth.down)||0,ratio=up+down?up/(up+down):null;
    const tone=ratio==null?"資料同步中":ratio>=.62?"偏多":ratio<=.38?"偏空":"震盪";
    const marketDate=String(tw.metadata?.trading_date||""),chipDate=String(chips.metadata?.trading_date||""),chipsCurrent=!marketDate||!chipDate||marketDate===chipDate;
    const foreignParts=[finite(chips.markets?.twse?.institutional?.foreign_net),finite(chips.markets?.tpex?.institutional?.foreign_net)].filter(value=>value!=null);
    const foreignNet=chipsCurrent&&foreignParts.length?foreignParts.reduce((sum,value)=>sum+value,0):null,foreign=!chipsCurrent?`法人資料停在 ${chipDate||"舊交易日"}`:foreignNet==null?"法人待更新":foreignNet>0?"外資買超":foreignNet<0?"外資賣超":"外資持平";
    const todayMajor=calendarEvents().filter(event=>eventDateKey(event)===todayKey&&featuredEvent(event));
    const future=calendarEvents().filter(featuredEvent).map(event=>{const day=eventDateKey(event),dateOnly=event.all_day===true||event.time_status==="date-only",at=Date.parse(event.start||0),eligible=day>todayKey||day===todayKey&&(dateOnly||Number.isFinite(at)&&at>=Date.now()-3600000);return eligible?{...event,_at:dateOnly?Date.parse(`${day}T12:00:00+08:00`):at}:null}).filter(Boolean).sort((a,b)=>String(eventDateKey(a)).localeCompare(String(eventDateKey(b)))||a._at-b._at)[0];
    const nowMs=Date.now();
    const focusCandidates=safeNews.map(item=>({...item,_focusAge:nowMs-Date.parse(item.published_at||item.date||0)})).filter(item=>Number.isFinite(item._focusAge)&&item._focusAge>=-300000&&item._focusAge<=72*3600000);
    const focus24=focusCandidates.filter(item=>item._focusAge<=24*3600000);
    const topNews=[...(focus24.length?focus24:focusCandidates)].sort((a,b)=>b._majorScore-a._majorScore)[0],industry=topNews?topNews._majorCategory||majorCategory(topNews):"暫無明確焦點";
    const next=future?`${eventDateKey(future)===todayKey?"下一事件":"近期事件"} ${strip(future.title)}`:"近期無已確認高影響事件";
    const eventCountText=eventFeedReady()?`${todayMajor.length} 件`:"同步中";
    node.textContent=`台股${tone} · 今日重大事件 ${eventCountText} · ${foreign} · 焦點 ${industry} · ${next}`;
    const values={briefMarketTone:tone,briefEventCount:eventCountText,briefForeign:foreign,briefIndustry:industry};
    for(const [id,value] of Object.entries(values)){const target=$("#"+id);if(target)target.textContent=value}
    renderMarketInsights();
  }
  function renderTaiwanStatus(){
    const breadth=tw.breadth||{},up=finite(breadth.up)||0,down=finite(breadth.down)||0;
    let tone="資料同步中";if(up+down){const ratio=up/(up+down);tone=ratio>=.62?"偏多":ratio<=.38?"偏空":"震盪"}
    const toneNode=$("#marketTone");if(toneNode){toneNode.textContent=tone;toneNode.className=tone==="偏多"?"up":tone==="偏空"?"down":"flat"}
    const breadthNode=$("#breadthSummary");if(breadthNode)breadthNode.textContent=up+down?`${fmt(up,0)} 漲／${fmt(down,0)} 跌`:"同步中";
    const markets=chips.markets||{},marketDate=String(tw.metadata?.trading_date||""),chipDate=String(chips.metadata?.trading_date||""),chipsCurrent=!marketDate||!chipDate||marketDate===chipDate;
    const twseForeign=finite(markets.twse?.institutional?.foreign_net),tpexForeign=finite(markets.tpex?.institutional?.foreign_net),foreignParts=[twseForeign,tpexForeign].filter(value=>value!=null),foreignNet=chipsCurrent&&foreignParts.length?foreignParts.reduce((sum,value)=>sum+value,0):null,foreignNode=$("#foreignDirection"),foreignDetail=$("#foreignDirectionDetail");
    if(foreignNode){foreignNode.textContent=!chipsCurrent?"待更新":foreignNet==null?"同步中":foreignNet>0?"買超":foreignNet<0?"賣超":"持平";foreignNode.className=cls(foreignNet)}
    if(foreignDetail)foreignDetail.textContent=!chipsCurrent?`法人 ${chipDate||"未確認"}／行情 ${marketDate||"未確認"}`:foreignNet==null?"等待法人盤後資料":`上市 ${twseForeign==null?"—":`${twseForeign>=0?"+":""}${fmt(twseForeign,0)}`} 張 · 上櫃 ${tpexForeign==null?"—":`${tpexForeign>=0?"+":""}${fmt(tpexForeign,0)}`} 張`;
    const volumeRatio=finite(tw.metadata?.volume_ratio_20d),totalTrade=finite(tw.metadata?.total_trade_value),volumeSessions=finite(tw.metadata?.volume_history_sessions);let volumeLabel="資料同步中",volumeNote="";
    if(volumeRatio!=null){volumeLabel=volumeRatio>=1.3?"明顯放量":volumeRatio>=1.1?"溫和放量":volumeRatio<.85?"量縮觀望":"量能正常";volumeNote=`近 20 日均量的 ${(volumeRatio*100).toFixed(0)}% · ${fmt(volumeSessions,0)} 個交易日`;}
    else if(totalTrade!=null){volumeLabel="歷史成交資料回補中";volumeNote=`最新成交 ${fmt(totalTrade/100000000,0)} 億元${volumeSessions!=null?` · 已取得 ${fmt(volumeSessions,0)} 個交易日`:""}`;}
    const momentum=$("#volumeMomentum"),momentumNote=$("#volumeMomentumNote");if(momentum)momentum.textContent=volumeLabel;if(momentumNote)momentumNote.textContent=volumeNote;
    const twStamp=tw.metadata?.updated_at,chipsStamp=chips.metadata?.updated_at,parts=[];if(twStamp)parts.push(`行情 ${formatTime(twStamp)}`);if(chipsStamp)parts.push(`籌碼 ${formatTime(chipsStamp)}`);const foot=$("#focusUpdated");if(foot)foot.textContent=parts.join(" · ")||"等待台股與法人資料";
  }
  renderFeaturedInfo();renderTodayFocus();renderTaiwanStatus();renderTodayBrief();

  const storedCalendarMode=localStorage.getItem("mr-calendar-mode-v1")||localStorage.getItem("mr-calendar-mode-v11.4.49")||localStorage.getItem("mr-calendar-mode-v11.5.1")||"market";
  if(!localStorage.getItem("mr-calendar-mode-v1"))localStorage.setItem("mr-calendar-mode-v1",storedCalendarMode);
  let current=new Date(),calendarMode=storedCalendarMode==="dividend"?"dividend":"market",pendingJumpDate="";
  const calendar=$("#calendarGrid"),dialog=$("#dayDialog");
  const marketFilters=()=>({q:$("#eventSearch").value.trim().toLowerCase(),region:$("#eventRegion").value,type:$("#eventType").value,impact:$("#eventImpact").value});
  const dividendFilters=()=>({q:$("#eventSearch").value.trim().toLowerCase(),kind:$("#dividendKind").value,asset:$("#dividendAsset").value,amount:$("#dividendAmount").value});
  function updateCalendarFilterLabel(){
    const node=$("#calendarActiveFilterText");if(!node)return;
    const selectIds=calendarMode==="market"?["eventRegion","eventType","eventImpact"]:["dividendKind","dividendAsset","dividendAmount"];
    const active=selectIds.map(id=>$("#"+id)).filter(select=>select&&select.value!=="all").map(select=>select.options[select.selectedIndex]?.textContent||"");
    const searching=!!$("#eventSearch")?.value.trim();
    node.textContent=active.length?active.slice(0,2).join("・")+(active.length>2?` +${active.length-2}`:""):searching?"搜尋中":"全部";
  }
  const searchableText=event=>`${event.title||""} ${event.description||event.summary||""} ${event.symbol||event.asset_id||""} ${event.asset_name||event.name||""} ${Array.isArray(event.assets)?event.assets.join(" "):event.assets||""} ${Array.isArray(event.symbols)?event.symbols.join(" "):event.symbols||""}`.toLowerCase();
  const dividendKind=event=>{
    const title=String(event.title||""),type=String(event.event_type||event.category||"").toLowerCase();
    if(/dividend-payment/.test(type)||/股利發放/.test(title))return"payment";
    if(/dividend-decision/.test(type)||/股利方案|股利案|盈餘分派/.test(title))return"decision";
    if(/除權/.test(title))return"ex-right";
    if(/除息/.test(title)||/ex-dividend|etf-distribution/.test(type))return"ex-dividend";
    return"other";
  };
  const dividendAssetClass=event=>{
    const explicit=String(event.asset_class||"").toLowerCase();
    if(explicit==="etf"||explicit==="stock")return explicit;
    const symbol=String(event.symbol||event.asset_id||"").replace(/^TW:/i,"").toUpperCase();
    return symbol.startsWith("00")||/ETF|基金/i.test(`${event.asset_name||event.name||""} ${event.title||""}`)?"etf":"stock";
  };
  function marketRelevant(event,filter){
    if(eventGroup(event)==="dividend")return false;
    const hay=searchableText(event),group=eventGroup(event);
    const impactOk=filter.impact==="all"||event.impact==="high"||(filter.impact==="medium"&&["high","medium"].includes(event.impact));
    return (!filter.q||hay.includes(filter.q))&&(filter.region==="all"||event.region===filter.region)&&(filter.type==="all"||group===filter.type)&&impactOk;
  }
  function dividendRelevant(event,filter){
    if(eventGroup(event)!=="dividend")return false;
    const hay=searchableText(event),kind=dividendKind(event),assetClass=dividendAssetClass(event);
    const amountOk=filter.amount==="all"||(filter.amount==="cash"&&finite(event.cash_dividend)!=null&&finite(event.cash_dividend)!==0)||(filter.amount==="stock"&&(finite(event.stock_dividend)!=null&&finite(event.stock_dividend)!==0||finite(event.stock_dividend_ratio)!=null&&finite(event.stock_dividend_ratio)!==0));
    return (!filter.q||hay.includes(filter.q))&&(filter.kind==="all"||kind===filter.kind)&&(filter.asset==="all"||assetClass===filter.asset)&&amountOk;
  }
  function monthEvents(year,month){
    const filter=calendarMode==="market"?marketFilters():dividendFilters();
    return uniqueEvents(calendarEvents().filter(event=>{
      const parts=eventDateKey(event).split("-").map(Number);
      return parts[0]===year&&parts[1]-1===month&&(calendarMode==="market"?marketRelevant(event,filter):dividendRelevant(event,filter));
    }));
  }
  function factRows(event){
    const text=strip(event.description||event.summary||"");
    const facts=[];
    const add=(label,value)=>{if(value&&!facts.some(row=>row.label===label))facts.push({label,value})};
    add("股票代碼",event.symbol||event.asset_id);
    add("每股金額",finite(event.cash_dividend)!=null?`${fmt(event.cash_dividend,4)} 元`:null);
    add("發放日期",event.payment_date||event.pay_date);
    const shares=text.match(/(?:發行(?:新股|股數|總股數)|認購股數)[^0-9]{0,15}([0-9][0-9,]*)\s*股/);
    const amount=text.match(/(?:募集資金|發行總額|交易金額|金額)[^0-9]{0,15}([0-9][0-9,.]*(?:億|萬)?元)/);
    const purpose=text.match(/(?:資金用途|用途)[：:]?\s*([^。；;]{4,80})/);
    add("發行股數",shares?.[1]?`${shares[1]} 股`:null);
    add("金額",amount?.[1]);
    add("用途",purpose?.[1]);
    return facts.slice(0,6);
  }
  const relatedNewsHtml=event=>{
    const related=MR.relatedNews(event,safeNews,{limit:3,windowDays:3});
    if(!related.length)return "";
    return `<div class="event-related-news"><strong>相關新聞</strong>${related.map(item=>`<a href="${escapeHtml(safeExternalHref(item.url)||"#")}" target="_blank" rel="noreferrer noopener"><span>${escapeHtml(item.source||"市場消息")}</span><b>${escapeHtml(truncate(item.title,76))}</b><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></a>`).join("")}</div>`;
  };
  const eventCard=event=>{
    const group=eventGroup(event),description=strip(event.description||event.summary||""),facts=factRows(event);
    const source=event.source_url?`<a href="${escapeHtml(safeExternalHref(event.source_url)||"#")}" target="_blank" rel="noreferrer noopener">官方來源 ↗</a>`:`<span>${escapeHtml(event.source_name||"官方來源")}</span>`;
    return `<article class="event-detail ${group}"><div class="event-detail-top"><div><span class="tag">${escapeHtml(event.region||"GLOBAL")}</span><span class="event-kind">${group==="company"?"公司資訊":isMacroCalendarEvent(event)?"經濟／央行":"重大事件"}</span></div><span class="impact-badge ${escapeHtml(event.impact||"medium")}">${impactLabel(event.impact)}</span></div><h3><a href="event.html?id=${encodeURIComponent(event.id)}">${escapeHtml(strip(event.title))}</a></h3>${description?`<p>${escapeHtml(truncate(description,220))}</p>`:""}${facts.length?`<dl class="event-fact-grid">${facts.map(row=>`<div><dt>${escapeHtml(row.label)}</dt><dd>${escapeHtml(row.value)}</dd></div>`).join("")}</dl>`:""}<div class="event-detail-foot"><time>${escapeHtml(eventWhenLabel(event))}</time>${source}</div>${relatedNewsHtml(event)}${description.length>220?`<details class="event-full"><summary>查看完整說明</summary><p>${escapeHtml(description)}</p></details>`:""}</article>`;
  };
  const dividendEventLabel=event=>({"ex-dividend":"除息","ex-right":"除權／除權息",decision:"股利方案",payment:"股利發放",other:"股利事件"})[dividendKind(event)]||"股利事件";
  const matchingDividendRow=event=>event||{};
  const dividendCash=event=>finite(event.cash_dividend??event.amount);
  const dividendStock=event=>finite(event.stock_dividend??event.stock_dividend_ratio);
  const dividendTable=rows=>{
    if(!rows.length)return '<div class="empty">當日沒有符合篩選的股利股息資訊</div>';
    return `<div class="table-wrap dividend-table-wrap"><table class="dividend-table"><thead><tr><th>標的</th><th>事件</th><th>現金股利</th><th>股票股利</th><th>發放日期</th><th>來源</th></tr></thead><tbody>${rows.map(event=>`<tr><td><a href="asset.html?symbol=${encodeURIComponent(event.symbol||"")}"><b>${escapeHtml(event.symbol||"—")}</b><br><small>${escapeHtml(event.asset_name||event.name||strip(event.title).replace(/^\S+\s*/,""))}</small></a></td><td>${escapeHtml(dividendEventLabel(event))}</td><td>${dividendCash(event)!=null?`${fmt(dividendCash(event),4)} 元`:'<span class="pending-value">金額待公告</span>'}</td><td>${dividendStock(event)!=null?fmt(dividendStock(event),4):"—"}</td><td>${escapeHtml(event.payment_date||event.pay_date||matchingDividendRow(event).payment_date||"—")}</td><td><a href="event.html?id=${encodeURIComponent(event.id)}">站內公告 →</a></td></tr>`).join("")}</tbody></table></div>`;
  };
  function openDay(date,rows){
    const unique=uniqueEvents(rows);
    if(calendarMode==="dividend"){
      const dividends=unique.filter(event=>eventGroup(event)==="dividend").sort((a,b)=>String(a.symbol||"").localeCompare(String(b.symbol||""),"zh-Hant"));
      const companies=new Set(dividends.map(event=>event.symbol||event.asset_id||event.id)).size;
      const etfs=new Set(dividends.filter(event=>dividendAssetClass(event)==="etf").map(event=>event.symbol||event.id)).size;
      const knownCash=dividends.map(dividendCash).filter(value=>value!=null);
      const cashTotal=knownCash.reduce((sum,value)=>sum+value,0);
      $("#dayDialogTitle").textContent=`${date.toLocaleDateString("zh-TW")} 股利股息`;
      $("#dayDialogBody").innerHTML=`<div class="day-summary dividend-day-summary"><div><strong>${companies}</strong><span>標的家數</span></div><div><strong>${etfs}</strong><span>ETF 家數</span></div><div><strong>${knownCash.length?fmt(cashTotal,4):"—"}</strong><span>已知每股金額合計</span></div></div>${dividendTable(dividends)}`;
      dialog.showModal();return;
    }
    const groups={major:[],company:[]};
    for(const event of unique){const group=eventGroup(event);if(group==="major"||group==="company")groups[group].push(event)}
    groups.major.sort((a,b)=>Number(b.impact==="high")-Number(a.impact==="high")||Date.parse(a.start)-Date.parse(b.start));
    groups.company.sort((a,b)=>Date.parse(a.start)-Date.parse(b.start));
    $("#dayDialogTitle").textContent=`${date.toLocaleDateString("zh-TW")} 市場事件`;
    const macroCount=groups.major.filter(isMacroCalendarEvent).length,highCount=groups.major.filter(event=>event.impact==="high").length;
    const initialCompany=groups.company.slice(0,36);
    $("#dayDialogBody").innerHTML=`<div class="day-summary market-day-summary"><div><strong>${highCount}</strong><span>高影響</span></div><div><strong>${macroCount}</strong><span>經濟／央行</span></div><div><strong>${groups.company.length}</strong><span>公司資訊</span></div></div><div class="dialog-tabs"><button class="chip active" data-day-tab="major">重大事件 <b>${groups.major.length}</b></button><button class="chip" data-day-tab="company">公司資訊 <b>${groups.company.length}</b></button></div><div class="day-tab-panel" data-day-panel="major">${groups.major.length?groups.major.map(eventCard).join(""):'<div class="empty">當日沒有重大事件</div>'}</div><div class="day-tab-panel" data-day-panel="company" hidden>${initialCompany.length?initialCompany.map(eventCard).join(""):'<div class="empty">當日沒有公司資訊</div>'}${groups.company.length>initialCompany.length?`<button class="btn show-all-company-events" type="button">顯示全部 ${groups.company.length} 筆公司資訊</button>`:""}</div>`;
    document.querySelectorAll("[data-day-tab]").forEach(button=>button.onclick=()=>{
      document.querySelectorAll("[data-day-tab]").forEach(item=>item.classList.toggle("active",item===button));
      document.querySelectorAll("[data-day-panel]").forEach(panel=>panel.hidden=panel.dataset.dayPanel!==button.dataset.dayTab);
    });
    const showAll=$(".show-all-company-events");if(showAll)showAll.onclick=()=>{const panel=document.querySelector('[data-day-panel="company"]');if(panel)panel.innerHTML=groups.company.map(eventCard).join("")};
    dialog.showModal();
  }
  const calendarMarker=(kind,count,label)=>count?`<span class="calendar-marker ${kind}" title="${escapeHtml(label)} ${count} 件" aria-label="${escapeHtml(label)} ${count} 件"><i></i><b>${count}</b></span>`:"";
  function renderMarketPills(rows){
    const company=rows.filter(event=>eventGroup(event)==="company"),majorRows=rows.filter(event=>eventGroup(event)==="major"),macro=majorRows.filter(isMacroCalendarEvent),major=majorRows.filter(event=>!isMacroCalendarEvent(event));
    return [calendarMarker("major",major.length,"重大事件"),calendarMarker("macro",macro.length,"經濟或央行事件"),calendarMarker("company",company.length,"公司資訊")].filter(Boolean);
  }
  function renderDividendPills(rows){
    return [calendarMarker("dividend",rows.length,"股利或除權息")].filter(Boolean);
  }
  function renderCalendar(){
    const year=current.getFullYear(),month=current.getMonth(),first=new Date(year,month,1),start=new Date(year,month,1-first.getDay()),all=monthEvents(year,month);
    $("#calendarTitle").textContent=`${year} 年 ${month+1} 月`;
    $("#eventUpdated").textContent=events.metadata?.updated_at?formatTime(events.metadata.updated_at):"等待排程";
    if(calendarMode==="market"){
      const major=all.filter(event=>eventGroup(event)==="major").length,company=all.filter(event=>eventGroup(event)==="company").length;
      $("#calendarModeSummary").textContent=`本月 ${major} 件重大事件・${company} 件公司資訊`;
    }else{
      const companies=new Set(all.map(event=>event.symbol||event.asset_id||event.id)).size,etfs=new Set(all.filter(event=>dividendAssetClass(event)==="etf").map(event=>event.symbol||event.id)).size;
      $("#calendarModeSummary").textContent=`本月 ${companies} 家標的・其中 ${etfs} 家 ETF`;
    }
    calendar.innerHTML="";
    for(let index=0;index<42;index++){
      const date=new Date(start);date.setDate(start.getDate()+index);
      const key=localKey(date),rows=all.filter(event=>eventDateKey(event)===key),pills=calendarMode==="market"?renderMarketPills(rows):renderDividendPills(rows);
      const cell=document.createElement("button");
      cell.type="button";cell.dataset.date=key;
      cell.className=`calendar-day ${date.getMonth()!==month?"other":""} ${key===todayKey?"today":""} ${pendingJumpDate===key?"calendar-jump-highlight":""} ${calendarMode==="dividend"?"dividend-mode-day":""}`;
      cell.setAttribute("aria-label",`${date.toLocaleDateString("zh-TW")}，${rows.length} 件資訊`);
      cell.innerHTML=`<span class="day-num">${date.getDate()}</span>${pills.length?`<span class="calendar-markers">${pills.join("")}</span>`:""}`;
      cell.onclick=()=>openDay(date,rows);
      calendar.appendChild(cell);
    }
    if(pendingJumpDate){const target=calendar.querySelector(`[data-date="${pendingJumpDate}"]`);if(target)setTimeout(()=>target.scrollIntoView({behavior:"smooth",block:"center",inline:"center"}),60)}
    updateCalendarFilterLabel();
  }
  function setCalendarMode(mode,{render=true}={}){
    calendarMode=mode==="dividend"?"dividend":"market";
    localStorage.setItem("mr-calendar-mode-v1",calendarMode);
    document.querySelectorAll("[data-calendar-mode]").forEach(button=>{const active=button.dataset.calendarMode===calendarMode;button.classList.toggle("active",active);button.setAttribute("aria-selected",String(active))});
    document.querySelectorAll("[data-calendar-filter]").forEach(panel=>panel.hidden=panel.dataset.calendarFilter!==calendarMode);
    $("#calendarHeading").textContent=calendarMode==="market"?"市場事件月曆":"股利股息月曆";
    $("#calendarModeDescription").textContent=calendarMode==="market"?"總經、央行、財報與公司重要日期。":"除權、除息、股利方案與發放日期分開整理。";
    $("#eventSearch").placeholder=calendarMode==="market"?"搜尋：CPI、台積電、財報、法說會…":"搜尋：代碼、公司、ETF、除息或股利金額…";
    $("#calendarMetaText").textContent=calendarMode==="market"?"點日期查看重大事件與公司資訊":"點日期查看股利類型、每股金額與發放日期";
    $("#calendarPanel").dataset.mode=calendarMode;
    updateCalendarFilterLabel();
    if(render)renderCalendar();
  }
  $("#eventSearch").addEventListener("input",()=>{updateCalendarFilterLabel();renderCalendar()});
  ["eventRegion","eventType","eventImpact","dividendKind","dividendAsset","dividendAmount"].forEach(id=>$("#"+id).addEventListener("change",()=>{updateCalendarFilterLabel();renderCalendar()}));
  document.querySelectorAll("[data-calendar-mode]").forEach(button=>button.onclick=()=>setCalendarMode(button.dataset.calendarMode));
  $("#prevMonth").onclick=()=>{current.setMonth(current.getMonth()-1);pendingJumpDate="";renderCalendar()};
  $("#nextMonth").onclick=()=>{current.setMonth(current.getMonth()+1);pendingJumpDate="";renderCalendar()};
  $("#todayMonth").onclick=()=>{current=new Date();pendingJumpDate="";renderCalendar()};
  const closeDayDialog=()=>{if(dialog?.open)dialog.close()};
  $("#closeDayDialog").onclick=closeDayDialog;
  dialog.addEventListener("click",event=>{if(event.target===dialog)closeDayDialog()});
  dialog.addEventListener("cancel",event=>{event.preventDefault();closeDayDialog()});
  document.addEventListener("keydown",event=>{if(event.key==="Escape"&&dialog.open)closeDayDialog()});
  const quickLinks=[...document.querySelectorAll(".floating-quick-nav .quick-tile")];
  if("IntersectionObserver" in window){
    const targets=[document.querySelector("#calendarPanel"),document.querySelector("#latestNews")].filter(Boolean);
    const observer=new IntersectionObserver(entries=>{const visible=entries.filter(entry=>entry.isIntersecting).sort((a,b)=>b.intersectionRatio-a.intersectionRatio)[0];if(!visible)return;quickLinks.forEach(link=>link.classList.toggle("current",link.getAttribute("href")==="#"+visible.target.id))},{rootMargin:"-20% 0px -55%",threshold:[.05,.2,.5]});
    targets.forEach(target=>observer.observe(target));
  }
  window.addEventListener("market-radar:calendar-jump",event=>{
    const detail=event.detail||{},target=String(detail.date||"").match(/^\d{4}-\d{2}-\d{2}/)?.[0]||"";
    if(target){const [year,month,day]=target.split("-").map(Number);current=new Date(year,month-1,day);pendingJumpDate=target;}
    setCalendarMode(detail.mode==="dividend"?"dividend":"market");
    $("#calendarPanel").scrollIntoView({behavior:"smooth",block:"start"});
  });
  setCalendarMode(calendarMode,{render:false});
  renderCalendar();
  // Late-arriving channels independently upgrade the sections they own.
  // A slow optional source can no longer leave the whole homepage frozen on
  // the seed/fallback state after verified data has already arrived.
  assetLivePromise.then(fresh=>{if(Array.isArray(fresh?.assets)&&fresh.assets.length){assets=fresh;rebuildAssets();renderPortfolioSummary();renderMarketInsights()}}).catch(()=>{});
  twLivePromise.then(fresh=>{if(Array.isArray(fresh?.items)&&fresh.items.length){tw=fresh;rebuildQuotes();renderMarketList();renderTaiwanStatus();renderPortfolioSummary();renderTodayBrief()}}).catch(()=>{});
  chipsLivePromise.then(fresh=>{if(fresh?.markets){chips=fresh;renderTaiwanStatus();renderTodayBrief()}}).catch(()=>{});
  snapshotLivePromise.then(fresh=>{if(Array.isArray(fresh?.items)&&fresh.items.length){snapshot=fresh;rebuildQuotes();renderMarketKlines();renderPortfolioSummary()}}).catch(()=>{});
  stockNewsLivePromise.then(fresh=>{if(Array.isArray(fresh?.items)){stockNews=fresh;renderFeaturedInfo();renderCalendar();renderTodayFocus();renderTodayBrief()}}).catch(()=>{});
  newsStream.done.then(fresh=>{news=fresh;renderFeaturedInfo();renderCalendar();renderTodayFocus();renderTodayBrief()}).catch(()=>{});
  let lastRenderedDay=todayKey;
  const checkDayBoundary=()=>{const key=localKey(new Date());if(!key||key===lastRenderedDay)return;refreshDayKeys();lastRenderedDay=todayKey;renderFeaturedInfo();renderTodayFocus();renderCalendar();renderTodayBrief()};
  setInterval(checkDayBoundary,60000);
  window.addEventListener("focus",checkDayBoundary);

  eventLivePromise.then(fresh=>{
    if(!Array.isArray(fresh?.events)||!fresh.events.length)return;
    const oldStamp=String(events?.metadata?.updated_at||""),newStamp=String(fresh?.metadata?.updated_at||"");
    if(fresh!==events&&(oldStamp!==newStamp||Number(events?.events?.length||0)!==fresh.events.length)){events=fresh;renderCalendar()}
    renderFeaturedInfo();renderTodayFocus();renderCalendar();renderTodayBrief();
  }).catch(()=>{});
})();
