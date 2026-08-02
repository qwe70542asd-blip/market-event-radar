(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const escapeHtml = value => String(value ?? "").replace(/[&<>\"]/g, character => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[character]));
  const finite = value => value === null || value === undefined || value === "" ? null : Number.isFinite(Number(value)) ? Number(value) : null;
  const assetId = new URLSearchParams(location.search).get("id") || "";
  const state = {asset:null, quote:null, institutional:{}, chips:{}, news:{items:[]}};

  function formatNumber(value, digits=2) {
    const number=finite(value);
    return number === null ? "等待資料" : new Intl.NumberFormat("zh-TW",{maximumFractionDigits:digits}).format(number);
  }
  function formatPercent(value, signed=false) {
    const number=finite(value);
    return number === null ? "等待資料" : `${signed&&number>0?"+":""}${number.toFixed(2)}%`;
  }
  function formatLots(value, signed=false, inputShares=true) {
    const number=finite(value);
    if (number === null) return "等待資料";
    const sign=number<0?"-":signed&&number>0?"+":"";
    const absolute=Math.abs(number), lotCount=inputShares?absolute/1000:absolute;
    const label=lotCount>=10000?`${(lotCount/10000).toFixed(1)} 萬張`:lotCount>=1000?`${(lotCount/1000).toFixed(1)} 千張`:`${Math.round(lotCount).toLocaleString("zh-TW")} 張`;
    return sign+label;
  }
  function formatMoney(value) {
    const number=finite(value);
    if (number === null) return "等待資料";
    const absolute=Math.abs(number), sign=number<0?"-":"";
    if (absolute>=1e8) return `${sign}${(absolute/1e8).toFixed(1)} 億`;
    if (absolute>=1e4) return `${sign}${(absolute/1e4).toFixed(1)} 萬`;
    return `${sign}${absolute.toLocaleString("zh-TW")}`;
  }
  function taipeiDate(value) {
    if (!value) return "等待資料";
    const date=new Date(String(value).length===10?`${value}T12:00:00+08:00`:value);
    return Number.isNaN(date.getTime())?String(value):date.toLocaleDateString("zh-TW",{timeZone:"Asia/Taipei",year:"numeric",month:"numeric",day:"numeric"});
  }
  function valueClass(value) {
    const number=finite(value);
    return number===null||number===0?"flat":number>0?"positive":"negative";
  }
  function isSafeUrl(value) {
    try { return ["http:","https:"].includes(new URL(String(value||"")).protocol); } catch { return false; }
  }

  function scoreAsset(asset) {
    const metrics=asset.metrics||{};
    const parts={
      profitability:finite(metrics.roe)!==null?Math.max(0,Math.min(100,50+(finite(metrics.roe)-10)*2.5)):50,
      leverage:finite(metrics.debt_ratio)!==null?Math.max(0,Math.min(100,100-finite(metrics.debt_ratio))):50,
      liquidity:finite(metrics.current_ratio)!==null?Math.max(0,Math.min(100,finite(metrics.current_ratio)*35)):50,
      valuation:finite(metrics.pe)!==null?Math.max(0,Math.min(100,100-finite(metrics.pe)*2)):50,
      income:finite(metrics.dividend_yield)!==null?Math.max(0,Math.min(100,finite(metrics.dividend_yield)*14)):50,
    };
    const available=Object.values(metrics).filter(value=>value!==null&&value!==undefined&&value!=="").length;
    const base=Object.values(parts).reduce((sum,value)=>sum+value,0)/5;
    return {parts,total:available>=3?Math.round(base*Math.min(1,.45+available/12)):null,coverage:Math.min(100,Math.round(available/10*100))};
  }
  function radarSvg(parts) {
    const keys=["profitability","leverage","liquidity","valuation","income"],labels=["獲利","負債","流動","估值","收益"],cx=120,cy=105,r=72;
    const point=(index,value)=>{const angle=-Math.PI/2+index*2*Math.PI/5,radius=r*value/100;return [cx+Math.cos(angle)*radius,cy+Math.sin(angle)*radius];};
    const grid=[25,50,75,100].map(level=>`<polygon points="${keys.map((_,index)=>point(index,level).join(",")).join(" ")}"/>`).join("");
    const axes=keys.map((_,index)=>{const [x,y]=point(index,100);return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/><text x="${x}" y="${y}" dx="${x<cx?-10:x>cx?10:0}" dy="${y<cy?-8:14}">${labels[index]}</text>`;}).join("");
    const data=keys.map((key,index)=>point(index,parts[key]).join(",")).join(" ");
    return `<svg class="model-radar" viewBox="0 0 240 220" role="img" aria-label="穩健度模型雷達圖"><g class="radar-grid">${grid}${axes}</g><polygon class="radar-data" points="${data}"/></svg>`;
  }
  function metricBars(asset) {
    const rows=[["本益比",asset.metrics?.pe,asset.industry_median?.pe],["股價淨值比",asset.metrics?.pb,asset.industry_median?.pb],["股息殖利率",asset.metrics?.dividend_yield,asset.industry_median?.dividend_yield],["ROE",asset.metrics?.roe,asset.industry_median?.roe],["負債比",asset.metrics?.debt_ratio,asset.industry_median?.debt_ratio]];
    return rows.map(([label,value,median])=>{
      const current=finite(value),middle=finite(median),maximum=Math.max(Math.abs(current||0),Math.abs(middle||0),1);
      return `<article class="comparison-row"><b>${label}</b><div><span style="width:${current===null?0:Math.min(100,Math.abs(current)/maximum*100)}%"></span></div><strong>${formatNumber(current)}</strong><small>產業中位 ${formatNumber(middle)}</small></article>`;
    }).join("");
  }

  function metricCard(label,value,kind="flat") {
    return `<article class="${kind}"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></article>`;
  }
  function infoCard(label,value,note="") {
    return `<article><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong>${note?`<small>${escapeHtml(note)}</small>`:""}</article>`;
  }

  function setApplicable(asset) {
    const isEtf=asset.asset_class==="etf"||asset.asset_class==="fund";
    const isTw=asset.market==="TW";
    $$('[data-applicable="stock"]').forEach(node=>node.hidden=isEtf);
    $$('[data-applicable="etf"]').forEach(node=>node.hidden=!isEtf);
    $$('[data-applicable="tw"]').forEach(node=>node.hidden=!isTw);
    $("#stockAnalysisGrid").hidden=isEtf;
    $("#comparisonBars").closest(".analysis-card").hidden=isEtf;
    $("#dividendTitle").textContent=isEtf?"配息紀錄":"股利紀錄";
  }

  function renderOverview(asset) {
    const quote=state.quote||{}, metrics=asset.metrics||{}, isEtf=asset.asset_class==="etf"||asset.asset_class==="fund";
    const change=finite(quote.change_percent);
    const cards=isEtf?[
      ["最新價格",formatNumber(quote.price??metrics.price),valueClass(change)],
      ["漲跌幅",formatPercent(change,true),valueClass(change)],
      ["淨值",formatNumber(asset.nav?.value??metrics.nav)],
      ["折溢價",formatPercent(asset.nav?.premium_discount??metrics.premium_discount,true),valueClass(asset.nav?.premium_discount??metrics.premium_discount)],
      ["成交量",formatLots(quote.volume,false,false)],
      ["基金規模",formatMoney(asset.fund_size??metrics.aum)],
      ["內扣費用",formatPercent(asset.expense_ratio??metrics.expense_ratio)],
      ["配息頻率",asset.distribution_frequency||"等待資料"],
    ]:[
      ["最新價格",formatNumber(quote.price??metrics.price),valueClass(change)],
      ["漲跌幅",formatPercent(change,true),valueClass(change)],
      ["開盤",formatNumber(quote.open)],
      ["最高",formatNumber(quote.high)],
      ["最低",formatNumber(quote.low)],
      ["成交量",formatLots(quote.volume,false,false)],
      ["本益比",formatNumber(metrics.pe)],
      ["EPS",formatNumber(metrics.eps)],
    ];
    $("#assetMetricGrid").innerHTML=cards.map(([label,value,kind])=>metricCard(label,value,kind)).join("");
    const model=scoreAsset(asset);
    $("#stabilityScore").textContent=isEtf?"ETF":model.total===null?"資料不足":model.total;
    $("#dataCoverage").textContent=`資料覆蓋 ${model.coverage}%`;
    $("#stabilityRadar").innerHTML=radarSvg(model.parts);
    $("#comparisonBars").innerHTML=metricBars(asset);
    $("#rankingGrid").innerHTML=[
      ["產業 EPS 排名",asset.rankings?.eps||"資料不足"],["產業 ROE 排名",asset.rankings?.roe||"資料不足"],
      ["產業估值分位",asset.rankings?.valuation||"資料不足"],["產業穩健度排名",asset.rankings?.stability||"資料不足"],
    ].map(([label,value])=>infoCard(label,value)).join("");
    $("#modelNotice").textContent="穩健度是資料型比較模型，會受到資料缺漏與產業差異影響，不是信用評等、目標價或買賣建議。";
  }

  function renderReturns(asset) {
    const returns=asset.returns||asset.return_periods||{};
    const periods=[["今年以來",returns.ytd],["1 個月",returns.one_month??returns["1m"]],["3 個月",returns.three_month??returns["3m"]],["1 年",returns.one_year??returns["1y"]],["3 年",returns.three_year??returns["3y"]],["成立以來",returns.since_inception]];
    const available=periods.some(([,value])=>finite(value)!==null);
    $("#returnPeriodGrid").innerHTML=available?periods.map(([label,value])=>infoCard(label,formatPercent(value,true),"資料來源報酬")).join(""):'<div class="asset-empty"><strong>歷史行情尚未同步</strong><span>目前不會用推算數字補空白；排程加入每日收盤歷史後會自動顯示。</span></div>';
    $("#returnDataDate").textContent=asset.returns_date?`截至 ${taipeiDate(asset.returns_date)}`:"等待歷史行情";
  }

  function renderFinancials(asset) {
    const rows=asset.financials||[];
    $("#financialTable").innerHTML=rows.length?rows.map(row=>`<tr><td>${escapeHtml(row.period)}</td><td>${formatNumber(row.revenue)}</td><td>${formatNumber(row.operating_income)}</td><td>${formatNumber(row.net_income)}</td><td>${formatNumber(row.eps)}</td></tr>`).join(""):'<tr><td colspan="5">官方財報資料尚未同步；可先使用下方公開資訊觀測站連結。</td></tr>';
  }

  function renderEtf(asset) {
    const profile=[
      ["追蹤指數",asset.tracking_index||"等待資料"],["槓桿／反向",asset.leverage_type||"一般"],
      ["最新淨值",formatNumber(asset.nav?.value??asset.metrics?.nav)],["淨值日期",taipeiDate(asset.nav?.date)],
      ["基金規模",formatMoney(asset.fund_size??asset.metrics?.aum)],["內扣費用",formatPercent(asset.expense_ratio??asset.metrics?.expense_ratio)],
      ["幣別",asset.currency||"TWD"],["避險級別",asset.hedged_currency||"未標示"],
    ];
    $("#etfProfileGrid").innerHTML=profile.map(([label,value])=>infoCard(label,value)).join("");
    const holdings=asset.holdings||asset.components||[];
    $("#holdingTable").innerHTML=holdings.length?holdings.map(row=>`<tr><td>${escapeHtml(row.symbol||row.code||"")}</td><td>${escapeHtml(row.name||"")}</td><td>${escapeHtml(row.industry||row.sector||"—")}</td><td>${formatPercent(row.weight)}</td></tr>`).join(""):'<tr><td colspan="4">成分股資料尚未同步；一般個股頁不會顯示此分頁。</td></tr>';
    $("#holdingDataDate").textContent=asset.holdings_date?`截至 ${taipeiDate(asset.holdings_date)}`:"等待官方成分資料";
  }

  function renderChips(asset) {
    const symbol=String(asset.symbol||"").toUpperCase();
    const stock=state.institutional?.stocks?.[symbol]||{};
    const flows=stock.flows||{};
    $("#assetInstitutionalDate").textContent=stock.date?`資料日 ${taipeiDate(stock.date)}`:"尚無個股法人資料";
    const institutionalRows=[["外資",flows.foreign],["投信",flows.investment_trust],["自營商",flows.dealer],["三大法人",flows.total]];
    const hasInstitutional=institutionalRows.some(([,flow])=>finite(flow?.net)!==null);
    $("#assetInstitutionalGrid").innerHTML=hasInstitutional?institutionalRows.map(([label,flow])=>`<article class="${valueClass(flow?.net)}"><span>${label}</span><strong>${formatLots(flow?.net,true)}</strong><small>買 ${formatLots(flow?.buy)}｜賣 ${formatLots(flow?.sell)}</small></article>`).join(""):'<div class="asset-empty"><strong>等待個股法人資料</strong><span>排程成功後顯示外資、投信、自營商買進、賣出與買賣超。</span></div>';

    const exchange=String(asset.exchange||"TWSE").toUpperCase().includes("TPEX")?"TPEx":"TWSE";
    const chip=state.chips?.items?.[`${exchange}:${symbol}`]||{};
    $("#assetChipDate").textContent=chip.date?`資料日 ${taipeiDate(chip.date)}`:"尚無個股籌碼資料";
    const day=chip.day_trading||{},margin=chip.margin||{},short=chip.short||{};
    const chipRows=[
      ["當沖成交量",formatLots(day.volume),null],["當沖占比",formatPercent(day.ratio_percent),null],
      ["融資餘額",formatLots(margin.balance_shares),margin.change_shares],["融券餘額",formatLots(short.balance_shares),short.change_shares],
    ];
    const hasChip=[day.volume,day.ratio_percent,margin.balance_shares,short.balance_shares].some(value=>finite(value)!==null);
    $("#assetChipGrid").innerHTML=hasChip?chipRows.map(([label,value,change])=>`<article class="${valueClass(change)}"><span>${label}</span><strong>${escapeHtml(value)}</strong><small>${change===null||change===undefined?"官方盤後資料":`較前日 ${formatLots(change,true)}`}</small></article>`).join(""):'<div class="asset-empty"><strong>等待當沖與融資券資料</strong><span>無資料時不以 0 冒充有效餘額。</span></div>';

    const brokers=asset.broker_branches||[];
    const official=exchange==="TPEx"?"https://www.tpex.org.tw/zh-tw/mainboard/trading/info/broker.html":"https://bsr.twse.com.tw/bshtm/bsMenu.aspx";
    $("#brokerBranchContent").innerHTML=brokers.length?`<div class="table-scroll"><table class="financial-table"><thead><tr><th>分點</th><th>買進</th><th>賣出</th><th>買賣超</th><th>均價</th></tr></thead><tbody>${brokers.map(row=>`<tr><td>${escapeHtml(row.name)}</td><td>${formatLots(row.buy)}</td><td>${formatLots(row.sell)}</td><td class="${valueClass(row.net)}">${formatLots(row.net,true)}</td><td>${formatNumber(row.average_price)}</td></tr>`).join("")}</tbody></table></div>`:`<div class="broker-limit"><strong>目前沒有可合法自動散布的完整分點授權資料</strong><p>這裡不會填猜測數字。分點成交是該分點客戶加總，不等於券商公司自有持股；可先到官方頁查詢。</p><a href="${official}" target="_blank" rel="noreferrer noopener">開啟官方分點查詢 →</a></div>`;
  }

  function renderDividends(asset) {
    const rows=asset.dividends||asset.distributions||[];
    $("#dividendTable").innerHTML=rows.length?rows.map(row=>`<tr><td>${escapeHtml(row.period||row.date||"")}</td><td>${formatNumber(row.cash??row.amount)}</td><td>${formatNumber(row.stock)}</td><td>${formatPercent(row.yield)}</td></tr>`).join(""):'<tr><td colspan="4">官方股利／配息資料尚未同步；可使用下方官方資料入口查詢。</td></tr>';
  }

  function renderNews(asset) {
    const symbol=String(asset.symbol||"").toUpperCase(), names=[asset.name,...(asset.aliases||[])].filter(Boolean).map(String);
    const symbolPattern=symbol?new RegExp(`(^|[^0-9A-Z])${symbol.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}([^0-9A-Z]|$)`,`i`):null;
    const items=(state.news?.items||[]).filter(item=>{
      const hay=`${item.title||""} ${item.summary||""} ${(item.assets||[]).join(" ")}`;
      return names.some(name=>name.length>=2&&hay.toLowerCase().includes(name.toLowerCase()))||symbolPattern?.test(hay);
    }).filter(item=>isSafeUrl(item.direct_link||item.link)).slice(0,12);
    $("#assetNewsCount").textContent=items.length?`${items.length} 則相關內容`:"目前無相關新聞";
    $("#assetNewsList").innerHTML=items.length?items.map(item=>`<a href="${escapeHtml(item.direct_link||item.link)}" target="_blank" rel="noreferrer noopener"><time>${taipeiDate(item.published_at)}</time><span><b>${escapeHtml(item.source||"新聞")}</b><strong>${escapeHtml(item.title||"")}</strong><small>${escapeHtml(item.ai_summary||item.summary||"")}</small></span><em>↗</em></a>`).join(""):'<div class="asset-empty"><strong>最近 20 天沒有可驗證的相關新聞</strong><span>新聞排程完成後會依代號、公司名稱與別名自動歸入。</span></div>';
  }

  function renderOfficialLinks(asset) {
    const isEtf=asset.asset_class==="etf"||asset.asset_class==="fund", exchange=String(asset.exchange||"").toUpperCase();
    const links=[
      asset.detail?.website&&["公司／投信官網",asset.detail.website],
      asset.market==="TW"&&["公開資訊觀測站","https://mops.twse.com.tw/"],
      asset.market==="TW"&&isEtf&&["證交所 e添富","https://www.twse.com.tw/zh/ETFortune/"],
      asset.market==="TW"&&["三大法人官方資料",exchange.includes("TPEX")?"https://www.tpex.org.tw/zh-tw/mainboard/trading/major-institutional/summary/day.html":"https://www.twse.com.tw/zh/trading/foreign/t86.html"],
      asset.market==="US"&&["SEC EDGAR",`https://www.sec.gov/edgar/search/#/q=${encodeURIComponent(asset.symbol)}`],
    ].filter(Boolean).filter(([,url])=>isSafeUrl(url));
    $("#officialLinks").innerHTML=links.map(([label,url])=>`<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(label)} →</a>`).join("")||'<span class="asset-empty">目前無可驗證的官方連結。</span>';
  }

  function render(asset) {
    state.asset=asset;
    const isEtf=asset.asset_class==="etf"||asset.asset_class==="fund";
    document.title=`${asset.name} ${asset.symbol}｜市場雷達`;
    $("#assetName").textContent=asset.name||"未命名標的";
    $("#assetSymbol").textContent=asset.symbol||"";
    $("#assetMeta").textContent=[asset.exchange||asset.market,asset.official_industry||asset.sub_industry||asset.sector,asset.currency].filter(Boolean).join(" · ")||"等待基本資料";
    $("#assetTypeBadge").textContent=asset.asset_class==="crypto"?"虛擬貨幣":isEtf?"ETF／基金":"股票";
    $("#assetTypeBadge").className=`asset-class-badge ${isEtf?"fund":asset.asset_class||"stock"}`;
    setApplicable(asset);
    renderOverview(asset);renderReturns(asset);renderFinancials(asset);renderEtf(asset);renderChips(asset);renderDividends(asset);renderNews(asset);renderOfficialLinks(asset);
  }

  function activateTab(name) {
    const button=$(`[data-asset-tab="${name}"]:not([hidden])`)||$('[data-asset-tab="overview"]');
    $$('[data-asset-tab]').forEach(node=>node.classList.toggle("active",node===button));
    $$('[data-asset-panel]').forEach(panel=>panel.hidden=panel.dataset.assetPanel!==button.dataset.assetTab);
  }

  async function load() {
    const source=window.MarketDataSource;
    const assetSeed=window.__MARKET_ASSET_SEED__||{assets:[]};
    const quoteSeed=window.__TW_MARKET_SEED__||{items:[]};
    const institutionalSeed=window.__INSTITUTIONAL_HISTORY_SEED__||{};
    const chipSeed=window.__TW_CHIPS_SEED__||{};
    const newsSeed=window.__MARKET_NEWS_SEED__||{items:[]};
    let assets=assetSeed,quotes=quoteSeed;
    try {
      if (source?.loadJson) [assets,quotes,state.institutional,state.chips,state.news]=await Promise.all([
        source.loadJson("data/assets.json",assetSeed),source.loadJson("data/tw-market.json",quoteSeed),
        source.loadJson("data/institutional-history.json",institutionalSeed),source.loadJson("data/tw-chips.json",chipSeed),source.loadJson("data/news.json",newsSeed),
      ]);
      else { state.institutional=institutionalSeed;state.chips=chipSeed;state.news=newsSeed; }
    } catch { state.institutional=institutionalSeed;state.chips=chipSeed;state.news=newsSeed; }
    const requestedSymbol=assetId.startsWith("TW:")?assetId.slice(3).toUpperCase():"";
    state.quote=(quotes.items||[]).find(item=>String(item.symbol).toUpperCase()===requestedSymbol)||null;
    let asset=(assets.assets||[]).find(item=>item.id===assetId)||window.MarketAssets?.byId?.(assetId)||null;
    if (!asset&&state.quote) asset={id:assetId,asset_class:state.quote.asset_class||"stock",market:"TW",exchange:state.quote.exchange,symbol:state.quote.symbol,name:state.quote.name,currency:"TWD",detail:{}};
    if (!asset) { $("#assetName").textContent="找不到標的";$("#assetMeta").textContent="請從台股排行或投資組合重新開啟。";return; }
    try {
      const safeId=String(asset.id).replace(/:/g,"__");
      const detail=source?.loadJson?await source.loadJson(`data/asset-details/${encodeURIComponent(safeId)}.json`,{}):{};
      if (detail&&Object.keys(detail).some(key=>key!=="__data_source")) asset={...asset,...detail};
    } catch {}
    render(asset);
    activateTab("overview");
  }

  $$('[data-asset-tab]').forEach(button=>button.addEventListener("click",()=>activateTab(button.dataset.assetTab)));
  window.addEventListener("market-assets-loaded",load,{once:true});
  if (window.MarketAssets?.state.loaded) load();
})();
