(async()=>{
  "use strict";
  const {$,escapeHtml,fmt,pct,cls,formatTime,loadData,loadNewsChannels,loadStockNews,loadPortfolio,finite,renderNewsThumb}=MR;
  const [assets,events,news,stockNews,tw,chips,snapshot]=await Promise.all([
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]}),
    loadData("events.json",window.__EVENT_SEED__||{events:[]}),
    loadNewsChannels(),
    loadStockNews(),
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),
    loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{markets:{},items:{}}),
    loadData("market-snapshot.json",window.__MARKET_SNAPSHOT_SEED__||{items:[]})
  ]);

  const assetMap=new Map((assets.assets||[]).map(row=>[String(row.symbol||"").toUpperCase(),row]));
  const quotes=new Map([...(tw.items||[]),...(snapshot.items||[])].map(row=>[String(row.symbol||"").toUpperCase(),row]));
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
  const LEADING_SECTOR_RE=/AI\s*伺服器|人工智慧|半導體|晶圓代工|記憶體|HBM|封裝測試|散熱|PCB|電源供應|雲端|資料中心|金融|航運|能源|原物料|機器人/i;
  const EXECUTIVE_RE=/執行長|董事長|財務長|總經理|基金經理人|分析師|首席經濟學家|央行總裁|官員|法說會|投資人會議|發表會|開發者大會|展覽|論壇|供應鏈會議/i;
  const BUSINESS_RE=/財報|財測|展望|營收|獲利|EPS|訂單|資本支出|擴產|漲價|降價|新品|新產品|合作|併購|投資/i;
  const SYSTEMIC_RE=/FOMC|聯準會|央行|CPI|PCE|GDP|非農|JOLTS|PMI|升息|降息|關稅|制裁|戰爭|金融危機|熔斷|重大法規|銀行危機|債務危機|財政危機|信用危機/i;
  const ASIA_RISK_RE=/日本銀行|日銀|BOJ|日圓|日債|日本國債|日本政府債務|日本企業倒閉|日本企業破產|匯市干預|韓國央行|韓元|KOSPI|KOSDAQ|中國房地產|中國房企|地方債|人民幣|亞洲貨幣|亞洲資金外流|貨幣競貶/i;
  const ASIA_STRESS_RE=/(?:創|跌至|貶至|升至|突破|失守).{0,10}(?:年|低點|高點)|暴跌|重貶|急貶|干預匯市|企業倒閉.{0,8}(?:增加|創高|突破)|破產.{0,8}(?:增加|創高)|債務.{0,8}(?:危機|失控|惡化)|房企.{0,8}(?:違約|倒閉)|地方債.{0,8}(?:風險|危機)|資金外流|信用風險/i;
  const ASIA_CROSS_BORDER_RE=/亞洲|台灣|台股|出口|供應鏈|半導體|觀光|航空|壽險|金融|匯率|資金流向/i;
  const majorScore=item=>{
    const text=`${item.title||""} ${item.summary||""} ${item.ai_summary||""}`;
    let score=0;
    if(SYSTEMIC_RE.test(text))score+=42;
    if(ASIA_RISK_RE.test(text))score+=18;
    if(ASIA_RISK_RE.test(text)&&ASIA_STRESS_RE.test(text))score+=26;
    if(ASIA_RISK_RE.test(text)&&ASIA_CROSS_BORDER_RE.test(text))score+=10;
    if(LEADER_RE.test(text))score+=24;
    if(LEADING_SECTOR_RE.test(text))score+=18;
    if(EXECUTIVE_RE.test(text))score+=16;
    if(BUSINESS_RE.test(text))score+=14;
    if(["official-notices","company-disclosures","cna"].includes(item.source_id))score+=12;
    if((item.other_reports||[]).length)score+=Math.min(14,(item.other_reports||[]).length*5);
    if(item.impact==="high")score+=12; else if(item.impact==="medium")score+=5;
    const age=(Date.now()-Date.parse(item.published_at||item.date||0))/86400000;
    if(Number.isFinite(age)&&age<=1)score+=10;else if(Number.isFinite(age)&&age<=3)score+=6;
    return Math.max(score,Number(item.importance_score||0));
  };
  const verificationLabel=item=>item.source_id==="official-notices"||item.source_id==="company-disclosures"?"官方來源":(item.other_reports||[]).length?"多來源佐證":item.source_id==="cna"?"主要媒體":"單一來源";

  const marketRows=(snapshot.items||[]).filter(row=>!["BTCUSDT","ETHUSDT","NVDA"].includes(String(row.symbol||"").toUpperCase()));
  $("#marketList").innerHTML=marketRows.length?marketRows.slice(0,10).map(row=>`<div class="market-row"><span><strong>${escapeHtml(row.name||row.symbol)}</strong><small>${escapeHtml(row.symbol)}</small></span><b>${fmt(row.price)}${escapeHtml(row.display_suffix||"")}</b><em class="${cls(row.change_percent)}">${pct(row.change_percent)}</em></div>`).join(""):'<div class="empty">等待全球行情更新</div>';
  $("#marketUpdated").textContent=snapshot.metadata?.updated_at?formatTime(snapshot.metadata.updated_at):"等待資料";

  function renderPortfolioSummary(){
    const rows=loadPortfolio();
    let totalCost=0,valuedCost=0,totalValue=0,dayPL=0,valued=0,dayValued=0;
    const allocation=new Map();
    for(const holding of rows){
      const symbol=String(holding.symbol||"").toUpperCase(),quote=quotes.get(symbol),asset=assetMap.get(symbol)||{};
      const qty=finite(holding.quantity??holding.qty),cost=finite(holding.cost??holding.average_cost),price=finite(quote?.price),previous=finite(quote?.previous_close);
      if(qty!=null&&cost!=null)totalCost+=qty*cost;
      if(qty!=null&&price!=null){
        const value=qty*price;totalValue+=value;valued++;if(cost!=null)valuedCost+=qty*cost;
        const category=asset.asset_class==="etf"?"ETF":asset.asset_class==="stock"?"個股":"其他";
        allocation.set(category,(allocation.get(category)||0)+value);
        if(previous!=null){dayPL+=(price-previous)*qty;dayValued++}
      }
    }
    const cumulative=valued?totalValue-valuedCost:null,returnPct=cumulative!=null&&valuedCost?cumulative/valuedCost*100:null;
    const dayBase=dayValued?totalValue-dayPL:null,dayPct=dayBase?dayPL/dayBase*100:null;
    $("#portfolioTotalValue").textContent=valued?`NT$ ${fmt(totalValue,0)}`:"—";
    $("#portfolioTotalCost").textContent=rows.length?`NT$ ${fmt(totalCost,0)}`:"—";
    $("#portfolioTotalPL").textContent=cumulative==null?"—":`${cumulative>=0?"+":"-"}NT$ ${fmt(Math.abs(cumulative),0)}`;
    $("#portfolioTotalPL").className=cls(cumulative);
    $("#portfolioReturn").textContent=pct(returnPct);$("#portfolioReturn").className=cls(returnPct);
    $("#portfolioDayPL").textContent=dayValued?`${dayPL>=0?"+":"-"}NT$ ${fmt(Math.abs(dayPL),0)}`:"—";$("#portfolioDayPL").className=cls(dayPL);
    $("#portfolioDayReturn").textContent=dayValued?pct(dayPct):"—";$("#portfolioDayReturn").className=cls(dayPct);
    $("#portfolioStatus").textContent=!rows.length?"尚未設定":valued===rows.length?"行情完整":`暫估 ${valued}/${rows.length}`;
    const totalAllocated=[...allocation.values()].reduce((a,b)=>a+b,0);
    $("#portfolioAllocation").innerHTML=totalAllocated?`<div class="allocation-bar">${[...allocation.entries()].map(([name,value])=>`<span style="flex:${Math.max(value,1)}" title="${escapeHtml(name)} ${((value/totalAllocated)*100).toFixed(1)}%"></span>`).join("")}</div><div class="allocation-labels">${[...allocation.entries()].sort((a,b)=>b[1]-a[1]).map(([name,value])=>`<span><i></i>${escapeHtml(name)} <b>${((value/totalAllocated)*100).toFixed(1)}%</b></span>`).join("")}</div>`:'<div class="empty">尚未加入投資標的。</div>';
    $("#portfolioEstimateNote").textContent=rows.length&&valued<rows.length?`${rows.length-valued} 項資產尚未取得最新行情；總資產與損益為已取得行情部分的暫估值。`:"";
  }
  renderPortfolioSummary();window.addEventListener("portfoliochange",renderPortfolioSummary);

  const marketKlineSymbols=["^TWII","^KS11","^N225","^IXIC","^SOX","^GSPC"];
  const marketKlineMap=new Map((snapshot.items||[]).map(item=>[String(item.symbol||"").toUpperCase(),item]));
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
  function renderMarketKlines(){
    const rows=marketKlineSymbols.map(symbol=>marketKlineMap.get(symbol)).filter(Boolean);
    $("#marketKlineUpdated").textContent=snapshot.metadata?.updated_at?`${formatTime(snapshot.metadata.updated_at)} · 日 K` :"等待資料";
    $("#marketKlineGrid").innerHTML=rows.length?rows.map(row=>{
      const candles=normalizedCandles(row),latest=candles.at(-1)||candleFallback(row).at(-1)||{};
      const open=safeNumber(latest.open??row.open),high=safeNumber(latest.high??row.high),low=safeNumber(latest.low??row.low),close=safeNumber(row.price??latest.close),changePct=safeNumber(row.change_percent),change=safeNumber(row.change);
      const priceLabel=close!=null?`${fmt(close)}${escapeHtml(row.display_suffix||"")}`:"—";
      const changeLabel=change!=null?`${change>=0?'+':''}${fmt(change)}${escapeHtml(row.display_suffix||"")}`:"—";
      const cached=row.data_status==="cached",cachedKline=row.data_status==="cached-kline",statusLabel=cached?"整筆使用快取":cachedKline?"K 線使用上次成功資料":candles.length>=10?"K 線已更新":"等待完整資料",statusClass=(cached||cachedKline)?"cached":candles.length>=10?"live":"waiting";
      const source=row.candle_source||row.source||"資料來源待更新";
      return `<article class="market-kline-card"><div class="market-kline-head"><div><small>${escapeHtml(row.market||"MARKET")}</small><h3>${escapeHtml(row.name||row.symbol)}</h3></div><div class="market-kline-price"><strong>${priceLabel}</strong><span class="${cls(changePct)}">${pct(changePct)}</span></div></div><div class="market-kline-status"><span class="kline-status ${statusClass}">${statusLabel}</span><small>近 ${candles.length||0} 個交易日</small></div><div class="market-kline-visual">${buildCandlestickSvg(row)}</div><div class="market-kline-stats"><span><small>開</small><b>${open!=null?fmt(open):"—"}</b></span><span><small>高</small><b>${high!=null?fmt(high):"—"}</b></span><span><small>低</small><b>${low!=null?fmt(low):"—"}</b></span><span><small>差</small><b class="${cls(change)}">${changeLabel}</b></span></div><div class="market-kline-source"><span>${escapeHtml(source)}</span><time>${escapeHtml(formatTime(row.market_at))}</time></div></article>`;
    }).join(""):'<div class="empty">等待大盤資料更新</div>';
  }
  renderMarketKlines();


  const mediaItems=[...(news.items||[]),...(stockNews.items||[])];
  const safeNews=[];const seenNews=new Set();
  for(const item of mediaItems){
    if(item.source_id==="company-disclosures"||item.source_id==="official-notices")continue;
    const title=strip(item.title),key=strip(`${title}|${item.url||""}`).toLowerCase();
    if(!title||!/^https?:\/\//i.test(String(item.url||""))||seenNews.has(key))continue;
    seenNews.add(key);safeNews.push({...item,title,_majorScore:majorScore(item)});
  }
  safeNews.sort((a,b)=>b._majorScore-a._majorScore||Date.parse(b.published_at||0)-Date.parse(a.published_at||0));
  const majorNews=safeNews.filter(item=>item._majorScore>=45).slice(0,6);
  const latest=majorNews[0]||safeNews[0];
  if(latest){$("#breakingLink").textContent=strip(latest.title);$("#breakingLink").href=latest.url}
  $("#homeNews").innerHTML=(majorNews.length?majorNews:safeNews.slice(0,6)).map(item=>{const image=renderNewsThumb(item,"large",{alt:item.title}).replace('class="news-thumb large','class="home-news-thumb large-thumb');const brief=truncate(item.ai_summary||item.summary||item.title,58)||"查看完整內容。";return `<a class="news-card home-news-card home-news-card-brief" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener">${image}<div class="home-news-copy"><div class="news-meta"><span>${escapeHtml(item.ai_category||item.topic||"市場")}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(brief)}</p></div></a>`}).join("")||'<div class="empty">等待重大資訊更新</div>';

  const todayKey=localKey(new Date());
  const todayEvents=uniqueEvents((events.events||[]).filter(event=>eventDateKey(event)===todayKey));
  const majorToday=todayEvents.filter(event=>eventGroup(event)==="major").sort((a,b)=>Number(b.impact==="high")-Number(a.impact==="high"));
  const breadth=tw.breadth||{},up=Number(breadth.up||0),down=Number(breadth.down||0);
  let tone="資料不足";
  if(up+down){const ratio=up/(up+down);tone=ratio>=.62?"偏多":ratio<=.38?"偏空":"震盪"}
  $("#marketTone").textContent=tone;$("#marketTone").className=tone==="偏多"?"up":tone==="偏空"?"down":"flat";
  $("#breadthSummary").textContent=up+down?`${up} 漲／${down} 跌`:"—";
  const markets=chips.markets||{};
  const foreignNet=finite(markets.twse?.institutional?.foreign_net);
  $("#foreignDirection").textContent=foreignNet==null?"尚未公布":foreignNet>0?"買超":"賣超";$("#foreignDirection").className=cls(foreignNet);
  const volumeRatio=finite(tw.metadata?.volume_ratio_20d),totalTrade=finite(tw.metadata?.total_trade_value),avgTrade=finite(tw.metadata?.average_20d_trade_value),volumeSessions=finite(tw.metadata?.volume_history_sessions);
  let volumeLabel="資料更新中",volumeNote="";
  if(volumeRatio!=null){volumeLabel=volumeRatio>=1.3?"明顯放量":volumeRatio>=1.1?"溫和放量":volumeRatio<.85?"量縮觀望":"量能正常";volumeNote=`近 20 日均量的 ${(volumeRatio*100).toFixed(0)}% · 網路歷史資料`;}
  else if(totalTrade!=null){volumeLabel="歷史成交資料回補中";volumeNote=`今日 ${fmt(totalTrade/100000000,0)} 億元${volumeSessions!=null?` · 已取得 ${fmt(volumeSessions,0)} 個交易日`:""}`;}
  $("#volumeMomentum").textContent=volumeLabel;$("#volumeMomentumNote").textContent=volumeNote;
  $("#todayFocusList").innerHTML=majorToday.length?majorToday.slice(0,6).map(event=>`<a class="today-focus-item" href="event.html?id=${encodeURIComponent(event.id)}"><span class="impact-dot ${escapeHtml(event.impact||"medium")}"></span><span><strong>${escapeHtml(strip(event.title))}</strong><small>${escapeHtml(formatTime(event.start))}</small></span></a>`).join(""):'<div class="empty">今天沒有已確認的重大事件</div>';
  $("#focusUpdated").textContent=events.metadata?.updated_at?formatTime(events.metadata.updated_at):"等待資料";

  let current=new Date(),focus="all",calendarMode=localStorage.getItem("mr-calendar-mode-v11.4.20")==="dividend"?"dividend":"market",pendingJumpDate="";
  const calendar=$("#calendarGrid"),dialog=$("#dayDialog");
  const marketFilters=()=>({q:$("#eventSearch").value.trim().toLowerCase(),region:$("#eventRegion").value,type:$("#eventType").value,impact:$("#eventImpact").value});
  const dividendFilters=()=>({q:$("#eventSearch").value.trim().toLowerCase(),kind:$("#dividendKind").value,asset:$("#dividendAsset").value,amount:$("#dividendAmount").value});
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
    return (!filter.q||hay.includes(filter.q))&&(filter.region==="all"||event.region===filter.region)&&(filter.type==="all"||group===filter.type)&&impactOk&&(focus==="all"||(event.focus||event.category||event.type)===focus||(event.tags||[]).includes(focus));
  }
  function dividendRelevant(event,filter){
    if(eventGroup(event)!=="dividend")return false;
    const hay=searchableText(event),kind=dividendKind(event),assetClass=dividendAssetClass(event);
    const amountOk=filter.amount==="all"||(filter.amount==="cash"&&finite(event.cash_dividend)!=null&&finite(event.cash_dividend)!==0)||(filter.amount==="stock"&&(finite(event.stock_dividend)!=null&&finite(event.stock_dividend)!==0||finite(event.stock_dividend_ratio)!=null&&finite(event.stock_dividend_ratio)!==0));
    return (!filter.q||hay.includes(filter.q))&&(filter.kind==="all"||kind===filter.kind)&&(filter.asset==="all"||assetClass===filter.asset)&&amountOk;
  }
  function monthEvents(year,month){
    const filter=calendarMode==="market"?marketFilters():dividendFilters();
    return uniqueEvents((events.events||[]).filter(event=>{
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
    return `<div class="event-related-news"><strong>相關新聞</strong>${related.map(item=>`<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener"><span>${escapeHtml(item.source||"市場消息")}</span><b>${escapeHtml(truncate(item.title,76))}</b><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></a>`).join("")}</div>`;
  };
  const eventCard=event=>{
    const group=eventGroup(event),description=strip(event.description||event.summary||""),facts=factRows(event);
    const source=event.source_url?`<a href="${escapeHtml(event.source_url)}" target="_blank" rel="noreferrer noopener">官方來源 ↗</a>`:`<span>${escapeHtml(event.source_name||"官方來源")}</span>`;
    return `<article class="event-detail ${group}"><div class="event-detail-top"><div><span class="tag">${escapeHtml(event.region||"GLOBAL")}</span><span class="event-kind">${group==="company"?"公司資訊":"重大事件"}</span></div><span class="impact-badge ${escapeHtml(event.impact||"medium")}">${impactLabel(event.impact)}</span></div><h3><a href="event.html?id=${encodeURIComponent(event.id)}">${escapeHtml(strip(event.title))}</a></h3>${description?`<p>${escapeHtml(truncate(description,220))}</p>`:""}${facts.length?`<dl class="event-fact-grid">${facts.map(row=>`<div><dt>${escapeHtml(row.label)}</dt><dd>${escapeHtml(row.value)}</dd></div>`).join("")}</dl>`:""}<div class="event-detail-foot"><time>${escapeHtml(formatTime(event.start))}</time>${source}</div>${relatedNewsHtml(event)}${description.length>220?`<details class="event-full"><summary>查看完整說明</summary><p>${escapeHtml(description)}</p></details>`:""}</article>`;
  };
  const dividendEventLabel=event=>({"ex-dividend":"除息","ex-right":"除權／除權息",decision:"股利方案",payment:"股利發放",other:"股利事件"})[dividendKind(event)]||"股利事件";
  const dividendCash=event=>finite(event.cash_dividend);
  const dividendStock=event=>finite(event.stock_dividend??event.stock_dividend_ratio);
  const dividendTable=rows=>{
    if(!rows.length)return '<div class="empty">當日沒有符合篩選的股利股息資訊</div>';
    return `<div class="table-wrap dividend-table-wrap"><table class="dividend-table"><thead><tr><th>標的</th><th>事件</th><th>現金股利</th><th>股票股利</th><th>發放日期</th><th>來源</th></tr></thead><tbody>${rows.map(event=>`<tr><td><a href="asset.html?symbol=${encodeURIComponent(event.symbol||"")}"><b>${escapeHtml(event.symbol||"—")}</b><br><small>${escapeHtml(event.asset_name||event.name||strip(event.title).replace(/^\S+\s*/,""))}</small></a></td><td>${escapeHtml(dividendEventLabel(event))}</td><td>${dividendCash(event)!=null?`${fmt(dividendCash(event),4)} 元`:"—"}</td><td>${dividendStock(event)!=null?fmt(dividendStock(event),4):"—"}</td><td>${escapeHtml(event.payment_date||event.pay_date||"—")}</td><td>${event.source_url?`<a href="${escapeHtml(event.source_url)}" target="_blank" rel="noreferrer noopener">官方公告 ↗</a>`:escapeHtml(event.source_name||"—")}</td></tr>`).join("")}</tbody></table></div>`;
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
    $("#dayDialogBody").innerHTML=`<div class="day-summary market-day-summary"><div><strong>${groups.major.length}</strong><span>重大事件</span></div><div><strong>${groups.company.length}</strong><span>公司資訊</span></div></div><div class="dialog-tabs"><button class="chip active" data-day-tab="major">重大事件 <b>${groups.major.length}</b></button><button class="chip" data-day-tab="company">公司資訊 <b>${groups.company.length}</b></button></div><div class="day-tab-panel" data-day-panel="major">${groups.major.length?groups.major.map(eventCard).join(""):'<div class="empty">當日沒有重大事件</div>'}</div><div class="day-tab-panel" data-day-panel="company" hidden>${groups.company.length?groups.company.map(eventCard).join(""):'<div class="empty">當日沒有公司資訊</div>'}</div>`;
    document.querySelectorAll("[data-day-tab]").forEach(button=>button.onclick=()=>{
      document.querySelectorAll("[data-day-tab]").forEach(item=>item.classList.toggle("active",item===button));
      document.querySelectorAll("[data-day-panel]").forEach(panel=>panel.hidden=panel.dataset.dayPanel!==button.dataset.dayTab);
    });
    dialog.showModal();
  }
  function renderMarketPills(rows){
    const major=rows.filter(event=>eventGroup(event)==="major"),company=rows.filter(event=>eventGroup(event)==="company"),pills=[];
    if(major.length){
      pills.push(`<span class="event-pill ${escapeHtml(major[0].impact||"")}">${escapeHtml(truncate(major[0].title,38))}</span>`);
      if(major.length>1)pills.push(`<span class="event-pill major-summary">另有重大事件 ${major.length-1} 件</span>`);
    }
    if(company.length)pills.push(`<span class="event-pill company-summary">公司資訊 ${company.length} 件</span>`);
    return pills;
  }
  function renderDividendPills(rows){
    const sorted=[...rows].sort((a,b)=>String(a.symbol||"").localeCompare(String(b.symbol||""),"zh-Hant"));
    const companyCount=new Set(sorted.map(event=>event.symbol||event.asset_id||event.id)).size;
    const pills=sorted.slice(0,2).map(event=>{const cash=dividendCash(event);return `<span class="event-pill dividend-symbol-pill"><b>${escapeHtml(event.symbol||"股利")}</b><span>${escapeHtml(dividendEventLabel(event))}${cash!=null?` · ${fmt(cash,4)} 元`:""}</span></span>`});
    if(companyCount>2)pills.push(`<span class="event-pill dividend-summary">另有 ${companyCount-2} 家</span>`);
    return pills;
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
      cell.innerHTML=`<span class="day-num">${date.getDate()}</span>${pills.join("")}${rows.length&&!pills.length?`<span class="event-pill">共 ${rows.length} 件資訊</span>`:""}`;
      cell.onclick=()=>openDay(date,rows);
      calendar.appendChild(cell);
    }
    if(pendingJumpDate){const target=calendar.querySelector(`[data-date="${pendingJumpDate}"]`);if(target)setTimeout(()=>target.scrollIntoView({behavior:"smooth",block:"center",inline:"center"}),60)}
  }
  function setCalendarMode(mode,{render=true}={}){
    calendarMode=mode==="dividend"?"dividend":"market";
    localStorage.setItem("mr-calendar-mode-v11.4.20",calendarMode);
    document.querySelectorAll("[data-calendar-mode]").forEach(button=>{const active=button.dataset.calendarMode===calendarMode;button.classList.toggle("active",active);button.setAttribute("aria-selected",String(active))});
    document.querySelectorAll("[data-calendar-filter]").forEach(panel=>panel.hidden=panel.dataset.calendarFilter!==calendarMode);
    $("#calendarHeading").textContent=calendarMode==="market"?"市場事件月曆":"股利股息月曆";
    $("#calendarModeDescription").textContent=calendarMode==="market"?"總經、央行、財報與公司重要日期。":"除權、除息、股利方案與發放日期分開整理。";
    $("#eventSearch").placeholder=calendarMode==="market"?"搜尋：CPI、台積電、財報、法說會…":"搜尋：代碼、公司、ETF、除息或股利金額…";
    $("#calendarMetaText").textContent=calendarMode==="market"?"點日期查看重大事件與公司資訊":"點日期查看股利類型、每股金額與發放日期";
    $("#calendarPanel").dataset.mode=calendarMode;
    if(render)renderCalendar();
  }
  $("#eventSearch").addEventListener("input",renderCalendar);
  ["eventRegion","eventType","eventImpact","dividendKind","dividendAsset","dividendAmount"].forEach(id=>$("#"+id).addEventListener("change",renderCalendar));
  document.querySelectorAll("[data-focus]").forEach(button=>button.onclick=()=>{document.querySelectorAll("[data-focus]").forEach(item=>item.classList.remove("active"));button.classList.add("active");focus=button.dataset.focus;renderCalendar()});
  document.querySelectorAll("[data-calendar-mode]").forEach(button=>button.onclick=()=>setCalendarMode(button.dataset.calendarMode));
  $("#prevMonth").onclick=()=>{current.setMonth(current.getMonth()-1);pendingJumpDate="";renderCalendar()};
  $("#nextMonth").onclick=()=>{current.setMonth(current.getMonth()+1);pendingJumpDate="";renderCalendar()};
  $("#todayMonth").onclick=()=>{current=new Date();pendingJumpDate="";renderCalendar()};
  $("#closeDayDialog").onclick=()=>dialog.close();
  window.addEventListener("market-radar:calendar-jump",event=>{
    const detail=event.detail||{},target=String(detail.date||"").match(/^\d{4}-\d{2}-\d{2}/)?.[0]||"";
    if(target){const [year,month,day]=target.split("-").map(Number);current=new Date(year,month-1,day);pendingJumpDate=target}
    setCalendarMode(detail.mode==="dividend"?"dividend":"market");
    $("#calendarPanel").scrollIntoView({behavior:"smooth",block:"start"});
  });
  setCalendarMode(calendarMode,{render:false});
  renderCalendar();
})();
