(async()=>{
  "use strict";

  const {
    $,escapeHtml,finite,loadData,mergeAssets,searchAssets,resolveAsset,findTwQuote,
    formatPrice,formatPercent,formatTime,direction,formatVolume,safeNewsLink,
    fetchTaiwanLiveQuotes,fetchTaiwanSeries,fetchBestTaiwanHistory,
    fetchOfficialValuation,fetchOfficialAssetProfile,
    seriesReturn,buildPriceDistribution,calculateTechnicalIndicators,
    scheduleAdaptiveRefresh,taiwanQuoteRefreshDelay
  }=MR;

  const [chipPayload,assetPayload,marketPayload,newsPayload]=await Promise.all([
    loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{markets:{},items:{}}),
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]}),
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),
    loadData("news.json",window.__NEWS_SEED__||{items:[]})
  ]);

  const assets=mergeAssets(assetPayload.assets||[],(window.__ASSET_SEED__||{}).assets||[])
    .filter(asset=>asset.market==="TW");
  const state={
    market:"twse",
    date:"",
    selectedAsset:null,
    activeTab:"overview",
    liveQuote:null,
    intradaySeries:null,
    historySeries:null,
    historyLoading:false,
    officialValuation:null,
    officialProfile:null,
    officialEtf:null,
    officialBasicsLoading:false,
    refreshStop:null,
    requestToken:0
  };

  function legacySnapshot(payload){
    const date=payload?.metadata?.trading_date||"";
    return {date,markets:payload?.markets||{},items:payload?.items||{}};
  }

  const history={...(chipPayload.history||{})};
  const latestDate=chipPayload?.metadata?.trading_date||"";
  if(latestDate&&!history[latestDate])history[latestDate]=legacySnapshot(chipPayload);
  const dates=[...new Set([
    ...(chipPayload.available_dates||[]),...Object.keys(history),latestDate
  ].filter(Boolean))].sort().reverse();
  state.date=dates[0]||latestDate;

  const tabs=[
    ["overview","總覽"],["trend","走勢"],["technical","技術"],["orderbook","五檔"],["distribution","分價"],
    ["institutional","法人"],["margin","融資券"],["daytrade","當沖"],["basic","基本"],
    ["financials","財報"],["dividend","股利"],["news","新聞"],["announcements","公告"]
  ];

  function snapshot(){return history[state.date]||legacySnapshot(chipPayload)}
  function marketLabel(market){return market==="tpex"?"上櫃 TPEx":"上市 TWSE"}
  function marketForAsset(asset){
    return String(asset?.exchange||"").toUpperCase().includes("TPEX")?"tpex":"twse";
  }
  function tradingViewSymbol(asset){
    return`${marketForAsset(asset)==="tpex"?"TPEX":"TWSE"}:${String(asset?.symbol||"").toUpperCase()}`;
  }

  function tradingViewShell(kind){
    return`<div class="tv-widget-shell" data-tv-widget="${kind}">
      <div class="tv-widget-loading">正在載入 ${kind==="chart"?"互動走勢圖":"技術分析"}…</div>
      <div class="tradingview-widget-container"><div class="tradingview-widget-container__widget"></div></div>
    </div>`;
  }

  function mountTradingViewWidget(asset,kind){
    const shell=document.querySelector(`[data-tv-widget="${kind}"]`);
    if(!shell||shell.dataset.mounted==="1")return;
    shell.dataset.mounted="1";
    const container=shell.querySelector(".tradingview-widget-container");
    const script=document.createElement("script");
    script.type="text/javascript";
    script.async=true;
    if(kind==="chart"){
      script.src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
      script.text=JSON.stringify({
        autosize:true,
        symbol:tradingViewSymbol(asset),
        interval:"D",
        timezone:"Asia/Taipei",
        theme:"dark",
        backgroundColor:"#081629",
        gridColor:"rgba(130,165,194,0.12)",
        style:"1",
        locale:"zh_TW",
        withdateranges:true,
        hide_side_toolbar:false,
        hide_top_toolbar:false,
        hide_legend:false,
        hide_volume:false,
        allow_symbol_change:false,
        save_image:false,
        studies:[
          "MASimple@tv-basicstudies",
          "MAExp@tv-basicstudies",
          "RSI@tv-basicstudies",
          "MACD@tv-basicstudies"
        ],
        support_host:"https://www.tradingview.com"
      });
    }else{
      script.src="https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js";
      script.text=JSON.stringify({
        interval:"1D",
        width:"100%",
        height:"100%",
        isTransparent:true,
        symbol:tradingViewSymbol(asset),
        showIntervalTabs:true,
        displayMode:"multiple",
        locale:"zh_TW",
        colorTheme:"dark"
      });
    }
    container.appendChild(script);
    setTimeout(()=>{
      const loading=shell.querySelector(".tv-widget-loading");
      if(loading)loading.hidden=true;
    },3500);
  }

  function numberText(value,unit="股"){
    const parsed=finite(value);
    return parsed===null?"官方未回傳":`${Math.round(parsed).toLocaleString("zh-TW")} ${unit}`;
  }
  function compactNumber(value,unit=""){
    const parsed=finite(value);
    if(parsed===null)return"—";
    const abs=Math.abs(parsed);
    if(abs>=1e12)return`${(parsed/1e12).toFixed(2)}兆${unit}`;
    if(abs>=1e8)return`${(parsed/1e8).toFixed(2)}億${unit}`;
    if(abs>=1e4)return`${(parsed/1e4).toFixed(2)}萬${unit}`;
    return`${Math.round(parsed).toLocaleString("zh-TW")}${unit}`;
  }
  function signedText(value,unit="股"){
    const parsed=finite(value);
    if(parsed===null)return"官方未回傳";
    const prefix=parsed>0?"+":"";
    return`${prefix}${Math.round(parsed).toLocaleString("zh-TW")} ${unit}`;
  }
  function pctText(value){
    const parsed=finite(value);
    return parsed===null?"官方未回傳":`${parsed.toFixed(2)}%`;
  }
  function infoCard(label,value,cls="",note=""){
    return`<article class="info-card query-info-card"><span>${escapeHtml(label)}</span>
      <strong class="${cls}">${escapeHtml(String(value))}</strong>
      ${note?`<small>${escapeHtml(note)}</small>`:""}</article>`;
  }
  function detailMetric(label,value,cls="",note=""){
    return`<div class="stock-detail-metric"><span>${escapeHtml(label)}</span>
      <strong class="${cls}">${escapeHtml(String(value))}</strong>
      ${note?`<small>${escapeHtml(note)}</small>`:""}</div>`;
  }
  function currentItems(){
    return Object.values(snapshot().items||{}).filter(item=>(item.market||"twse")===state.market);
  }
  function findChipRow(asset){
    const market=marketForAsset(asset);
    const symbol=String(asset.symbol||"").toUpperCase();
    return Object.values(snapshot().items||{}).find(item=>
      String(item.symbol||"").toUpperCase()===symbol&&(item.market||"twse")===market
    )||null;
  }
  function quoteFor(asset){
    const fallback=findTwQuote(asset,marketPayload)||null;
    if(!state.liveQuote)return fallback;
    const live=state.liveQuote;
    return{
      ...(fallback||{}),
      ...live,
      bid_prices:live.bid_prices?.length?live.bid_prices:(fallback?.bid_prices||[]),
      bid_volumes:live.bid_volumes?.length?live.bid_volumes:(fallback?.bid_volumes||[]),
      ask_prices:live.ask_prices?.length?live.ask_prices:(fallback?.ask_prices||[]),
      ask_volumes:live.ask_volumes?.length?live.ask_volumes:(fallback?.ask_volumes||[])
    };
  }
  function stockNews(asset,officialOnly=false){
    const terms=[String(asset.symbol||"").toLowerCase(),String(asset.name||"").toLowerCase()]
      .filter(term=>term.length>=2);
    return(newsPayload.items||[]).filter(item=>{
      const hay=`${item.title||""} ${item.summary||""} ${(item.tags||[]).join(" ")} ${item.source||""}`.toLowerCase();
      const match=terms.some(term=>hay.includes(term));
      if(!match)return false;
      if(!officialOnly)return true;
      return/(證交所|臺灣證券交易所|櫃買|公開資訊觀測站|mops|twse|tpex)/i.test(`${item.source||""} ${item.tags||""}`);
    }).slice(0,12);
  }

  function renderDateOptions(){
    const select=$("#dateSelect");
    select.innerHTML=dates.length
      ?dates.map(date=>`<option value="${date}">${date.slice(0,4)}/${date.slice(4,6)}/${date.slice(6,8)}</option>`).join("")
      :'<option value="">等待官方資料</option>';
    select.value=state.date||"";
  }

  function renderMarketResult(){
    const snap=snapshot();
    const row=snap.markets?.[state.market]||{};
    const institutional=row.institutional||{};
    const margin=row.margin||{};
    const short=row.short||{};
    const day=row.day_trading||{};
    const items=currentItems();

    $("#chipDate").textContent=state.date?`${state.date.slice(0,4)}/${state.date.slice(4,6)}/${state.date.slice(6,8)}`:"—";
    $("#chipMarket").textContent=marketLabel(state.market);
    $("#chipCount").textContent=Number(row.stock_count||items.length||0).toLocaleString("zh-TW");
    $("#chipUpdated").textContent=formatTime(chipPayload?.metadata?.updated_at);

    $("#institutionalGrid").innerHTML=[
      infoCard("外資買賣超",signedText(institutional.foreign_net),direction(institutional.foreign_net),"外資及陸資"),
      infoCard("投信買賣超",signedText(institutional.trust_net),direction(institutional.trust_net),"國內投信"),
      infoCard("自營商買賣超",signedText(institutional.dealer_net),direction(institutional.dealer_net),"自行買賣＋避險"),
      infoCard("三大法人合計",signedText(institutional.total_net),direction(institutional.total_net),"市場總計")
    ].join("");

    $("#marginGrid").innerHTML=[
      infoCard("融資餘額",numberText(margin.balance),direction(margin.change),"最新盤後餘額"),
      infoCard("融資增減",signedText(margin.change),direction(margin.change),"相較前一交易日"),
      infoCard("融券餘額",numberText(short.balance),direction(short.change),"最新盤後餘額"),
      infoCard("當沖成交股數",compactNumber(day.volume," 股"),"","官方盤後統計")
    ].join("");

    const hasData=items.length||Object.values(institutional).some(value=>finite(value)!==null)||
      finite(margin.balance)!==null||finite(short.balance)!==null;
    $("#marketQueryStatus").textContent=hasData
      ?`${marketLabel(state.market)} · ${state.date||"最後交易日"} · ${items.length.toLocaleString("zh-TW")} 檔個股`
      :"此日期尚無可驗證資料，請改選其他日期。";

    if(state.selectedAsset)renderSelectedAsset();
  }

  function renderTabs(){
    return`<div class="stock-detail-tabs" role="tablist">${tabs.map(([key,label])=>
      `<button type="button" data-stock-tab="${key}" class="${state.activeTab===key?"active":""}">${label}</button>`
    ).join("")}</div>`;
  }

  function lineChart(rows){
    const usable=(rows||[]).filter(row=>finite(row.close)!==null);
    if(usable.length<2)return'<div class="empty">目前沒有可繪製的走勢資料。</div>';
    const width=900,height=260,pad=22;
    const values=usable.map(row=>row.close);
    const min=Math.min(...values),max=Math.max(...values);
    const span=max-min||Math.max(max*.01,1);
    const points=usable.map((row,index)=>{
      const x=pad+index/(usable.length-1)*(width-pad*2);
      const y=height-pad-(row.close-min)/span*(height-pad*2);
      return`${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    const first=values[0],last=values[values.length-1];
    return`<div class="inline-chart"><svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
      <defs><linearGradient id="stockLineFill" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="rgba(95,235,190,.32)"/><stop offset="100%" stop-color="rgba(95,235,190,0)"/>
      </linearGradient></defs>
      <polyline class="inline-chart-line" points="${points}"/>
      <polygon class="inline-chart-fill" points="${pad},${height-pad} ${points} ${width-pad},${height-pad}"/>
      </svg><div class="inline-chart-labels"><span>${formatPrice(first,"TWD")}</span><strong>${formatPrice(last,"TWD")}</strong><span>${usable.length} 個資料點</span></div></div>`;
  }

  function technicalContent(asset){
    const indicator=calculateTechnicalIndicators(state.historySeries?.rows||[]);
    const rows=state.historySeries?.rows||[];
    const dataStatus=state.historyLoading
      ?'<div class="data-loading-banner">正在從官方歷史行情與備援來源讀取資料…</div>'
      :rows.length?`<div class="data-source-banner">技術指標使用 ${escapeHtml(state.historySeries?.source||"日線資料")}，共 ${rows.length} 筆。</div>`
      :'<div class="data-warning-banner">官方歷史資料暫時無法取得；下方 TradingView 技術分析仍可使用。</div>';
    const signalClass=(value,reference)=>value===null||reference===null?"":value>=reference?"up":"down";
    const cards=[
      ["綜合判讀",indicator.count?indicator.rating:"等待資料",indicator.score>0?"up":indicator.score<0?"down":"flat",`有效日線 ${indicator.count} 筆／訊號分數 ${indicator.score}`],
      ["MA5",formatPrice(indicator.ma5,"TWD"),signalClass(indicator.latest,indicator.ma5),"至少 5 筆日線"],
      ["MA20",formatPrice(indicator.ma20,"TWD"),signalClass(indicator.latest,indicator.ma20),"至少 20 筆日線"],
      ["MA60",formatPrice(indicator.ma60,"TWD"),signalClass(indicator.latest,indicator.ma60),"至少 60 筆日線"],
      ["RSI 14",indicator.rsi14===null?"—":indicator.rsi14.toFixed(1),indicator.rsi14===null?"":indicator.rsi14>=70?"up":indicator.rsi14<=30?"down":"flat","70 以上偏熱／30 以下偏弱"],
      ["MACD",indicator.macd===null?"—":indicator.macd.toFixed(2),direction(indicator.histogram),`柱狀 ${indicator.histogram===null?"—":indicator.histogram.toFixed(2)}`],
      ["KD-K",indicator.k===null?"—":indicator.k.toFixed(1),indicator.k===null||indicator.d===null?"":indicator.k>=indicator.d?"up":"down",`D ${indicator.d===null?"—":indicator.d.toFixed(1)}`],
      ["布林上軌",formatPrice(indicator.bollingerUpper,"TWD"),"","20 日＋2σ"],
      ["布林中軌",formatPrice(indicator.bollingerMid,"TWD"),"","20 日均線"],
      ["布林下軌",formatPrice(indicator.bollingerLower,"TWD"),"","20 日－2σ"],
      ["20日壓力",formatPrice(indicator.recentHigh,"TWD"),"","可用日線範圍最高"],
      ["20日支撐",formatPrice(indicator.recentLow,"TWD"),"","可用日線範圍最低"]
    ];
    return`${dataStatus}
      <div class="technical-card-grid">${cards.map(([label,value,cls,note])=>detailMetric(label,value,cls,note)).join("")}</div>
      <div class="tv-technical-wrap">${tradingViewShell("technical")}</div>`;
  }

  function financingTable(title,section,type){
    const row=section||{};
    const fields=type==="margin"
      ?[["前日餘額",row.previous_balance],["買進",row.buy],["賣出",row.sell],
        ["現金償還",row.cash_repayment],["今日餘額",row.balance],["使用率",row.utilization_percent,"percent"]]
      :[["前日餘額",row.previous_balance],["賣出",row.sell],["買進",row.buy],
        ["現券償還",row.repayment],["今日餘額",row.balance],["使用率",row.utilization_percent,"percent"]];
    const available=fields.some(([,value])=>finite(value)!==null);
    return`<section class="stock-detail-block"><div class="stock-detail-block-head"><h3>${escapeHtml(title)}</h3>
      <span>${available?"官方盤後資料":"非信用交易標的或官方未回傳"}</span></div>
      <div class="stock-detail-grid">${fields.map(([label,value,kind])=>detailMetric(
        label,kind==="percent"?pctText(value):numberText(value),"",kind==="percent"?"額度使用比例":""
      )).join("")}</div></section>`;
  }

  function overviewContent(asset,chip,quote){
    const metrics={...(asset.metrics||{}),...(state.officialValuation||{})};
    const etf={...(asset.etf||{}),...(state.officialEtf||{})};
    const rows=state.historySeries?.rows||[];
    const validHighs=rows.map(row=>finite(row.high)).filter(value=>value!==null);
    const validLows=rows.map(row=>finite(row.low)).filter(value=>value!==null);
    const high52=validHighs.length?Math.max(...validHighs):null;
    const low52=validLows.length?Math.min(...validLows):null;
    const amplitude=finite(quote?.high)!==null&&finite(quote?.low)!==null&&finite(quote?.previous_close)
      ?(quote.high-quote.low)/quote.previous_close*100:null;
    const estimatedValue=finite(quote?.price)!==null&&finite(quote?.volume)!==null
      ?quote.price*quote.volume*1000:null;
    const profile={...(asset.profile||{}),...(state.officialProfile||{})};
    const issuedShares=finite(profile.issued_shares);
    const marketCap=finite(quote?.price)!==null&&issuedShares!==null?quote.price*issuedShares:null;
    const turnover=finite(quote?.volume)!==null&&issuedShares
      ?quote.volume*1000/issuedShares*100:null;
    const isEtf=asset.asset_class==="etf";
    const historyStatus=state.historyLoading
      ?"歷史資料讀取中"
      :rows.length?`${state.historySeries?.source||"歷史資料"} · ${rows.length} 筆`:"歷史資料尚未取得";
    const valuationCards=isEtf?[
      detailMetric("基金淨值",finite(etf.nav)===null?"官方基金資料待更新":formatPrice(etf.nav,"TWD")),
      detailMetric("折溢價",finite(etf.premium_discount)===null?"官方基金資料待更新":formatPercent(etf.premium_discount)),
      detailMetric("基金規模",etf.aum||"官方基金資料待更新"),
      detailMetric("內扣費用",etf.expense_ratio||"公開說明書"),
      detailMetric("配息頻率",etf.distribution||"依官方公告"),
      detailMetric("基金經理人",etf.manager||"官方基金資料待更新")
    ]:[
      detailMetric("本益比",finite(metrics.pe)===null?"官方未回傳":Number(metrics.pe).toFixed(2)),
      detailMetric("股價淨值比",finite(metrics.pb)===null?"官方未回傳":Number(metrics.pb).toFixed(2)),
      detailMetric("殖利率",finite(metrics.dividend_yield)===null?"官方未回傳":`${Number(metrics.dividend_yield).toFixed(2)}%`),
      detailMetric("EPS",finite(metrics.eps)===null?"官方未回傳":Number(metrics.eps).toFixed(2)),
      detailMetric("市值",marketCap===null?"官方未回傳發行股數":compactNumber(marketCap,"元")),
      detailMetric("發行股數",issuedShares===null?"官方未回傳":compactNumber(issuedShares,"股"))
    ];
    return`<div class="stock-data-status"><strong>${escapeHtml(historyStatus)}</strong>
      <span>即時行情：${escapeHtml(quote?.source||"備援資料")}</span></div>
    <div class="stock-app-grid">
      ${detailMetric("最高",formatPrice(quote?.high,"TWD"))}
      ${detailMetric("最低",formatPrice(quote?.low,"TWD"))}
      ${detailMetric("昨收",formatPrice(quote?.previous_close,"TWD"))}
      ${detailMetric("成交量",`${formatVolume(quote?.volume)} 張`)}
      ${detailMetric("成交值",estimatedValue===null?"—":compactNumber(estimatedValue,"元"),"","依成交價×張數估算")}
      ${detailMetric("振幅",amplitude===null?"—":`${amplitude.toFixed(2)}%`)}
      ${detailMetric("漲停",formatPrice(quote?.upper_limit,"TWD"))}
      ${detailMetric("跌停",formatPrice(quote?.lower_limit,"TWD"))}
      ${valuationCards.join("")}
      ${detailMetric("52週最高",formatPrice(high52,"TWD"))}
      ${detailMetric("52週最低",formatPrice(low52,"TWD"))}
      ${detailMetric("週轉率",turnover===null?"—":`${turnover.toFixed(2)}%`)}
      ${detailMetric("當沖成交",numberText(chip?.day_trading?.volume))}
      ${detailMetric("融資餘額",numberText(chip?.margin?.balance))}
      ${detailMetric("融券餘額",numberText(chip?.short?.balance))}
    </div>
    <section class="stock-return-section"><div class="stock-detail-block-head"><h3>區間報酬</h3><span>依日線收盤價計算</span></div>
      <div class="stock-return-grid">${[
        ["一週",seriesReturn(rows,7)],["一個月",seriesReturn(rows,30)],["三個月",seriesReturn(rows,90)],
        ["六個月",seriesReturn(rows,180)],["一年",seriesReturn(rows,365)]
      ].map(([label,value])=>detailMetric(label,formatPercent(value),direction(value))).join("")}</div></section>`;
  }

  function orderbookContent(quote){
    const bids=quote?.bid_prices||[],asks=quote?.ask_prices||[];
    if(!bids.length&&!asks.length)return'<div class="empty">休市或 MIS 尚未回傳五檔資料；盤中會每 5 秒更新。</div>';
    const rows=Array.from({length:5},(_,index)=>({
      bidPrice:bids[index],bidVolume:quote?.bid_volumes?.[index],
      askPrice:asks[index],askVolume:quote?.ask_volumes?.[index]
    }));
    return`<div class="orderbook-wrap"><table class="orderbook-table"><thead><tr>
      <th>買量</th><th>買價</th><th>檔位</th><th>賣價</th><th>賣量</th>
      </tr></thead><tbody>${rows.map((row,index)=>`<tr>
      <td>${compactNumber(row.bidVolume,"張")}</td><td class="up">${formatPrice(row.bidPrice,"TWD")}</td>
      <td>第 ${index+1} 檔</td><td class="down">${formatPrice(row.askPrice,"TWD")}</td>
      <td>${compactNumber(row.askVolume,"張")}</td></tr>`).join("")}</tbody></table>
      <p class="section-note">TWSE MIS 最佳五檔；盤中每 5 秒重新取得。休市後可能只保留最後揭示值。</p></div>`;
  }

  function distributionContent(){
    const rows=buildPriceDistribution(state.intradaySeries?.rows||[],{buckets:12});
    if(!rows.length)return'<div class="empty">目前沒有分鐘成交量可建立分價圖。</div>';
    const max=Math.max(...rows.map(row=>row.volume),1);
    return`<div class="price-distribution">${rows.map(row=>`<div class="price-volume-row">
      <strong>${formatPrice(row.price,"TWD")}</strong><span><i style="width:${(row.volume/max*100).toFixed(1)}%"></i></span>
      <b>${compactNumber(row.volume,"股")}</b></div>`).join("")}</div>
      <p class="section-note">以分鐘 K 線成交量依收盤價聚合，供趨勢參考；不是券商逐筆成交分價。</p>`;
  }

  function institutionalContent(chip){
    if(!chip)return'<div class="empty">此日期沒有查到個股法人明細。</div>';
    return`<div class="stock-app-grid">
      ${detailMetric("外資",signedText(chip.foreign_net),direction(chip.foreign_net),
        `買 ${numberText(chip.foreign_buy)}／賣 ${numberText(chip.foreign_sell)}`)}
      ${detailMetric("投信",signedText(chip.trust_net),direction(chip.trust_net),
        `買 ${numberText(chip.trust_buy)}／賣 ${numberText(chip.trust_sell)}`)}
      ${detailMetric("自營商",signedText(chip.dealer_net),direction(chip.dealer_net),
        `買 ${numberText(chip.dealer_buy)}／賣 ${numberText(chip.dealer_sell)}`)}
      ${detailMetric("合計",signedText(chip.total_net),direction(chip.total_net),"三大法人買賣超")}
    </div>`;
  }

  function marginContent(chip){
    if(!chip)return'<div class="empty">此日期沒有查到融資融券明細。</div>';
    return`<div class="stock-financing-layout">${financingTable("融資",chip.margin,"margin")}
      ${financingTable("融券",chip.short,"short")}</div>
      <div class="stock-query-footer"><span>資券互抵：${numberText(chip.offset_shares)}</span>
      <span>${chip.note?`備註：${escapeHtml(chip.note)}`:"缺值不以 0 顯示"}</span></div>`;
  }

  function dayTradeContent(chip){
    const row=chip?.day_trading||{};
    const available=Object.values(row).some(value=>value!==null&&value!==undefined);
    if(!available)return'<div class="empty">官方當沖統計尚未回傳，或此標的沒有當沖資料。</div>';
    return`<div class="stock-app-grid">
      ${detailMetric("可否當沖",row.eligible===null?"官方未回傳":row.eligible?"可當沖":"不可當沖")}
      ${detailMetric("當沖成交股數",numberText(row.volume))}
      ${detailMetric("當沖買進金額",compactNumber(row.buy_amount,"元"))}
      ${detailMetric("當沖賣出金額",compactNumber(row.sell_amount,"元"))}
      ${detailMetric("成交股數占比",pctText(row.volume_ratio_percent))}
      ${detailMetric("成交金額占比",pctText(row.amount_ratio_percent))}
    </div><p class="section-note">當沖資料為交易所／櫃買中心盤後統計，最終數字可能於 T+1、T+2 調整。</p>`;
  }

  function basicContent(asset,quote){
    const etf={...(asset.etf||{}),...(state.officialEtf||{})};
    const profile={...(asset.profile||{}),...(state.officialProfile||{})};
    const metrics={...(asset.metrics||{}),...(state.officialValuation||{})};
    const fields=asset.asset_class==="etf"?[
      ["標的類型","ETF"],["發行公司",etf.issuer],["基金經理人",etf.manager],
      ["基金類型",etf.category],["追蹤指數／績效指標",etf.benchmark],["投資策略",etf.strategy],
      ["成立日期",etf.inception_date],["上市日期",etf.listing_date],["保管機構",etf.custodian]
    ]:[
      ["市場",marketLabel(marketForAsset(asset))],["產業",asset.official_industry||asset.sub_industry],
      ["子產業",asset.sub_industry],["公司全名",profile.full_name||quote?.full_name||asset.name],
      ["上市／上櫃日期",profile.listing_date],["實收資本額",finite(profile.paid_in_capital)===null?null:compactNumber(profile.paid_in_capital,"元")],
      ["發行股數",finite(profile.issued_shares)===null?null:compactNumber(profile.issued_shares,"股")],
      ["幣別",asset.currency||"TWD"],["分析覆蓋",`${asset.analysis_coverage?.count||0} / 8`],
      ["本益比",finite(metrics.pe)===null?null:Number(metrics.pe).toFixed(2)],
      ["股價淨值比",finite(metrics.pb)===null?null:Number(metrics.pb).toFixed(2)],
      ["殖利率",finite(metrics.dividend_yield)===null?null:`${Number(metrics.dividend_yield).toFixed(2)}%`]
    ];
    return`<div class="stock-basic-grid">${fields.map(([label,value])=>infoCard(label,value||"官方尚未回傳")).join("")}</div>`;
  }

  function financialContent(asset){
    const rows=(asset.financials||[]).slice(0,8);
    if(!rows.length)return'<div class="empty">官方財報解析尚未取得可用季度欄位；資料覆蓋頁會列出缺漏原因。</div>';
    return`<div class="table-wrap"><table class="financial-inline-table"><thead><tr>
      <th>年度／季度</th><th>營收</th><th>營業利益</th><th>淨利</th><th>EPS</th><th>資產</th><th>負債</th><th>權益</th>
      </tr></thead><tbody>${rows.map(row=>`<tr>
      <td>${escapeHtml(`${row.year||"—"} Q${row.quarter||"—"}`)}</td>
      <td>${compactNumber(row.revenue)}</td><td>${compactNumber(row.operating_income)}</td>
      <td>${compactNumber(row.net_income)}</td><td>${finite(row.eps)===null?"—":Number(row.eps).toFixed(2)}</td>
      <td>${compactNumber(row.total_assets)}</td><td>${compactNumber(row.total_liabilities)}</td>
      <td>${compactNumber(row.equity)}</td></tr>`).join("")}</tbody></table></div>`;
  }

  function dividendContent(asset){
    const row=asset.dividend||{};
    const etf=asset.etf||{};
    return`<div class="stock-app-grid">
      ${detailMetric("現金股利",finite(row.cash_dividend)===null?"官方未回傳":`${row.cash_dividend} 元`)}
      ${detailMetric("股票股利",finite(row.stock_dividend)===null?"官方未回傳":`${row.stock_dividend} 元`)}
      ${detailMetric("除息日期",row.ex_dividend_date||"官方未回傳")}
      ${detailMetric("除權日期",row.ex_right_date||"官方未回傳")}
      ${detailMetric("董事會決議",row.announcement_date||"官方未回傳")}
      ${detailMetric("ETF 配息頻率",etf.distribution||"依官方公告")}
    </div>`;
  }

  function newsContent(asset,officialOnly=false){
    const rows=stockNews(asset,officialOnly);
    if(!rows.length){
      const mops=`https://mopsov.twse.com.tw/mops/web/ezsearch?co_id=${encodeURIComponent(asset.symbol)}`;
      return`<div class="empty">目前新聞資料庫沒有符合內容。<a class="btn" href="${mops}" target="_blank" rel="noreferrer">到公開資訊觀測站查詢 ↗</a></div>`;
    }
    return`<div class="inline-news-list">${rows.map(item=>`<article>
      <div><small>${escapeHtml(item.source||"來源")} · ${escapeHtml(formatTime(item.published_at||item.date))}</small>
      <h3>${escapeHtml(item.title||"")}</h3><p>${escapeHtml(item.summary||"")}</p></div>
      <a href="${safeNewsLink(item.link)}" target="_blank" rel="noreferrer">閱讀原文 ↗</a>
    </article>`).join("")}</div>`;
  }

  function tabContent(asset,chip,quote){
    switch(state.activeTab){
      case"trend":return`${tradingViewShell("chart")}
        <details class="fallback-chart-details" ${state.historySeries?.rows?.length?"":"open"}><summary>本站歷史資料備援</summary>
        ${state.historyLoading?'<div class="data-loading-banner">正在讀取官方歷史行情…</div>':lineChart(state.historySeries?.rows||state.intradaySeries?.rows||[])}
        <p class="section-note">主圖由 TradingView 提供；本站同時嘗試 TWSE／TPEx 官方歷史行情，失敗時再使用 Yahoo 備援。</p></details>`;
      case"technical":return technicalContent(asset);
      case"orderbook":return orderbookContent(quote);
      case"distribution":return distributionContent();
      case"institutional":return institutionalContent(chip);
      case"margin":return marginContent(chip);
      case"daytrade":return dayTradeContent(chip);
      case"basic":return basicContent(asset,quote);
      case"financials":return financialContent(asset);
      case"dividend":return dividendContent(asset);
      case"news":return newsContent(asset,false);
      case"announcements":return newsContent(asset,true);
      default:return overviewContent(asset,chip,quote);
    }
  }

  function bindTabs(){
    document.querySelectorAll("[data-stock-tab]").forEach(button=>button.addEventListener("click",()=>{
      state.activeTab=button.dataset.stockTab;
      renderSelectedAsset();
    }));
  }

  function renderSelectedAsset(){
    const asset=state.selectedAsset;
    if(!asset)return;
    const chip=findChipRow(asset);
    const quote=quoteFor(asset);
    const result=$("#stockQueryResult");
    const price=finite(quote?.price),pct=finite(quote?.change_percent);
    const market=marketForAsset(asset);

    $("#stockQueryStatus").textContent=`${state.date||"最後交易日"} ${marketLabel(market)}；行情盤中每 5 秒更新。`;
    result.hidden=false;
    result.innerHTML=`<article class="stock-query-card expanded-stock-card">
      <div class="stock-query-heading">
        <div><span class="asset-badge">${market==="tpex"?"上櫃":"上市"}</span>
          <h2>${escapeHtml(asset.name)} <em>${escapeHtml(asset.symbol)}</em></h2>
          <p>${escapeHtml(asset.asset_class==="etf"?"ETF":asset.official_industry||asset.sub_industry||"產業分類待更新")} · ${state.date||"最後交易日"}</p>
        </div>
        <div class="stock-query-price"><span>即時參考行情</span>
          <strong>${price===null?"—":formatPrice(price,"TWD")}</strong>
          <em class="${direction(pct)}">${formatPercent(pct)}</em>
          <small>${escapeHtml(quote?.quote_time||"等待行情")} · ${escapeHtml(quote?.source||"備援資料")}</small>
        </div>
      </div>
      ${renderTabs()}
      <div class="stock-tab-content" data-active-tab="${state.activeTab}">
        ${tabContent(asset,chip,quote)}
      </div>
    </article>`;
    bindTabs();
    if(state.activeTab==="trend")mountTradingViewWidget(asset,"chart");
    if(state.activeTab==="technical")mountTradingViewWidget(asset,"technical");
  }

  async function refreshSelectedQuote(){
    const asset=state.selectedAsset;
    if(!asset||document.hidden)return;
    try{
      const rows=await fetchTaiwanLiveQuotes([asset],7000);
      if(rows[0]){
        state.liveQuote=rows[0];
        renderSelectedAsset();
      }
    }catch(error){console.warn("Selected stock live quote failed:",error)}
  }

  async function loadSelectedOfficialBasics(asset,token){
    state.officialBasicsLoading=true;
    const [valuation,profile]=await Promise.allSettled([
      fetchOfficialValuation(asset,{timeout:8500}),
      fetchOfficialAssetProfile(asset,{timeout:8500})
    ]);
    if(token!==state.requestToken)return;
    state.officialValuation=valuation.status==="fulfilled"?(valuation.value||null):null;
    const profileValue=profile.status==="fulfilled"?(profile.value||null):null;
    state.officialProfile=profileValue?.profile||null;
    state.officialEtf=profileValue?.etf||null;
    state.officialBasicsLoading=false;
    renderSelectedAsset();
  }

  async function loadSelectedSeries(asset,token){
    state.historyLoading=true;
    renderSelectedAsset();
    const [intraday,historyRows]=await Promise.allSettled([
      fetchTaiwanSeries(asset,{range:"1d",interval:"1m",timeout:8500}),
      fetchBestTaiwanHistory(asset,{months:13,timeout:8500})
    ]);
    if(token!==state.requestToken)return;
    state.intradaySeries=intraday.status==="fulfilled"?intraday.value:null;
    state.historySeries=historyRows.status==="fulfilled"?historyRows.value:null;
    state.historyLoading=false;
    renderSelectedAsset();
  }

  function selectAsset(asset){
    state.selectedAsset=asset;
    state.activeTab="overview";
    state.liveQuote=null;
    state.intradaySeries=null;
    state.historySeries=null;
    state.historyLoading=true;
    state.officialValuation=null;
    state.officialProfile=null;
    state.officialEtf=null;
    state.officialBasicsLoading=true;
    state.requestToken+=1;
    if(state.refreshStop)state.refreshStop();
    renderSelectedAsset();
    refreshSelectedQuote();
    loadSelectedSeries(asset,state.requestToken);
    loadSelectedOfficialBasics(asset,state.requestToken);
    state.refreshStop=scheduleAdaptiveRefresh(refreshSelectedQuote,taiwanQuoteRefreshDelay,5000);
    $("#stockQueryResult").scrollIntoView({behavior:"smooth",block:"start"});
  }

  function renderSuggestions(){
    const query=$("#stockQueryInput").value.trim();
    const box=$("#stockQuerySuggestions");
    if(!query){box.hidden=true;box.innerHTML="";return}
    const rows=searchAssets(assets,query,{market:"TW",asset_class:"all"}).slice(0,8);
    if(!rows.length){
      box.hidden=false;
      box.innerHTML='<div class="empty">找不到符合的台股代碼或名稱。</div>';
      return;
    }
    box.hidden=false;
    box.innerHTML=rows.map(asset=>`<button type="button" data-asset-id="${escapeHtml(asset.id)}">
      <strong>${escapeHtml(asset.symbol)}</strong><span>${escapeHtml(asset.name)}</span>
      <small>${marketForAsset(asset)==="tpex"?"上櫃":"上市"} · ${asset.asset_class==="etf"?"ETF":"股票"}</small>
    </button>`).join("");
    box.querySelectorAll("button").forEach(button=>button.addEventListener("click",()=>{
      const asset=assets.find(row=>row.id===button.dataset.assetId);
      if(!asset)return;
      $("#stockQueryInput").value=`${asset.symbol} ${asset.name}`;
      box.hidden=true;
      selectAsset(asset);
    }));
  }

  function queryStock(){
    const value=$("#stockQueryInput").value.trim();
    const asset=resolveAsset(assets,value,{market:"TW",asset_class:"all"});
    if(!asset){
      $("#stockQueryStatus").textContent="找不到這個台股代碼或名稱，請重新輸入。";
      $("#stockQueryResult").hidden=true;
      return;
    }
    $("#stockQuerySuggestions").hidden=true;
    selectAsset(asset);
  }

  renderDateOptions();
  renderMarketResult();

  $("#marketSelect").addEventListener("change",event=>{state.market=event.target.value});
  $("#dateSelect").addEventListener("change",event=>{state.date=event.target.value});
  $("#marketQueryButton").addEventListener("click",renderMarketResult);
  $("#stockQueryInput").addEventListener("input",renderSuggestions);
  $("#stockQueryInput").addEventListener("keydown",event=>{
    if(event.key==="Enter"){event.preventDefault();queryStock()}
  });
  $("#stockQueryButton").addEventListener("click",queryStock);
  document.addEventListener("click",event=>{
    if(!event.target.closest(".stock-search-box"))$("#stockQuerySuggestions").hidden=true;
  });
  document.addEventListener("visibilitychange",()=>{
    if(!document.hidden&&state.selectedAsset)refreshSelectedQuote();
  });
})();