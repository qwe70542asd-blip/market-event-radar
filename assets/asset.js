(async () => {
  "use strict";
  const { $, $$, escapeHtml, finite, loadData, fetchTaiwanLiveQuotes, mergeAssets,
    canonicalAsset, findTwQuote, formatPrice, formatPercent, formatVolume, direction,
    safeNewsLink, newsScore, formatTime, scheduleAdaptiveRefresh, taiwanQuoteRefreshDelay,
    startCryptoTickerStream } = MR;
  const id = decodeURIComponent(new URLSearchParams(location.search).get("id") || "").toUpperCase();
  const [assetPayload,twPayload,chipsPayload,newsPayload] = await Promise.all([
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]}),
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),
    loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{items:{}}),
    loadData("news.json",window.__NEWS_SEED__||{items:[]})
  ]);
  const assets=mergeAssets(assetPayload.assets||[],(window.__ASSET_SEED__||{}).assets||[]);
  let asset=assets.find(a=>String(a.id).toUpperCase()===id);
  if(!asset&&id){const [market,symbol]=id.split(":");asset=canonicalAsset({id,market,symbol,name:symbol,asset_class:symbol?.startsWith("00")?"etf":"stock",exchange:market==="TW"?"TWSE":"US",currency:market==="TW"?"TWD":"USD"})}
  if(!asset){$("#assetName").textContent="查無標的";$("#assetMeta").textContent="請從投資組合或台股排行重新開啟。";return}
  document.title=`${asset.name}（${asset.symbol}）｜市場事件雷達`;
  let quote=asset.market==="TW"?findTwQuote(asset,twPayload):null;
  const isEtf=asset.asset_class==="etf";
  const isCrypto=asset.asset_class==="crypto";
  const metrics={...(asset.metrics||{})};
  const financials=asset.financials||[];
  const latest=financials[0]||{};
  const chip=(chipsPayload.items||{})[asset.symbol]||{};
  $("#assetName").textContent=asset.name;$("#assetSymbol").textContent=asset.symbol;
  $("#assetClassBadge").textContent=isEtf?"ETF／基金":asset.asset_class==="crypto"?"虛擬貨幣":"股票";
  $("#assetMeta").textContent=`${asset.exchange||asset.market} · ${asset.official_industry||asset.sub_industry||"待分類"} · ${asset.currency||""}`;
  const analysisKeys=["eps","pe","pb","dividend_yield","roe","debt_ratio","current_ratio","net_margin"];
  const analysisCount=analysisKeys.filter(key=>finite(metrics[key])!==null).length;
  const analysisLabel={complete:"完整",partial:"部分",basic:"少量",missing:"缺漏"}[asset.analysis_status] || (analysisCount>=6?"完整":analysisCount>=2?"部分":"缺漏");
  $("#scoreLabel").textContent=isEtf?"ETF 官方資料":"官方分析覆蓋";
  $("#scoreValue").textContent=isEtf?"ETF":`${analysisCount}/8`;
  $("#scoreNote").textContent=isEtf?(asset.etf?.category||"基金資料"): `${analysisLabel} · 全市場自動稽核`;
  $("#scoreNote").title=asset.analysis_note||asset.analysis_source||"TWSE／TPEx 官方資料";

  function metric(label,value,cls=""){return `<article class="metric" data-metric-label="${escapeHtml(label)}"><span>${label}</span><strong class="${cls}">${value}</strong></article>`}
  function updateMetric(label,value,cls=""){
    const node=[...document.querySelectorAll("[data-metric-label]")].find(item=>item.dataset.metricLabel===label);
    if(!node)return;
    const strong=node.querySelector("strong");
    strong.textContent=value;
    strong.className=cls;
  }
  const price=finite(quote?.price??metrics.price),pct=finite(quote?.change_percent);
  const common=[
    metric("最新價格",formatPrice(price,isCrypto?"USD":asset.currency)),
    metric("漲跌幅",formatPercent(pct),direction(pct)),
    metric(isEtf?"淨值":"開盤",isEtf?(asset.etf?.nav?formatPrice(asset.etf.nav):"排程待更新"):formatPrice(quote?.open,isCrypto?"USD":asset.currency)),
    metric(isEtf?"折溢價":"最高",isEtf?(finite(asset.etf?.premium_discount)!==null?formatPercent(asset.etf.premium_discount):"排程待更新"):formatPrice(quote?.high,isCrypto?"USD":asset.currency)),
    metric("最低",formatPrice(quote?.low,isCrypto?"USD":asset.currency)),
    metric("成交量",isCrypto?(finite(quote?.volume)!==null?`$${Number(quote.volume).toLocaleString("en-US",{maximumFractionDigits:0})}`:"—"):`${formatVolume(quote?.volume)} 張`),
    metric(isEtf?"基金規模":isCrypto?"24H 高低":"本益比",isEtf?(asset.etf?.aum||"官方排程待更新"):isCrypto?"秒級串流":(finite(metrics.pe)!==null?metrics.pe.toFixed(2):"財報排程待更新")),
    metric(isEtf?"內扣費用":isCrypto?"資料來源":"EPS",isEtf?(asset.etf?.expense_ratio||"公開說明書"):isCrypto?"Binance WebSocket":(finite(metrics.eps??latest.eps)!==null?Number(metrics.eps??latest.eps).toFixed(2):"財報排程待更新"))
  ];
  $("#metricGrid").innerHTML=common.join("");

  function radar(values,labels){
    const center=150,r=100,n=values.length;
    const point=(index,scale)=>{const a=-Math.PI/2+index*2*Math.PI/n;return`${center+Math.cos(a)*r*scale},${center+Math.sin(a)*r*scale}`};
    const rings=[.25,.5,.75,1].map(scale=>`<polygon class="radar-grid" points="${values.map((_,i)=>point(i,scale)).join(" ")}"/>`).join("");
    const axes=values.map((_,i)=>`<line class="radar-axis" x1="${center}" y1="${center}" x2="${point(i,1).split(",")[0]}" y2="${point(i,1).split(",")[1]}"/>`).join("");
    const area=`<polygon class="radar-area" points="${values.map((v,i)=>point(i,Math.max(.08,Math.min(1,v/100)))).join(" ")}"/>`;
    const text=labels.map((label,i)=>{const [x,y]=point(i,1.2).split(",");return`<text class="radar-label" x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle">${label}</text>`}).join("");
    return `<div class="radar-wrap"><svg class="radar-svg" viewBox="0 0 300 300">${rings}${axes}${area}${text}</svg></div>`;
  }
  function info(label,value){return `<article class="info-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value??"資料不足")}</strong></article>`}

  if(isEtf){
    const etf=asset.etf||{};
    const coverageFields=[etf.issuer,etf.manager,etf.category,etf.benchmark,etf.strategy,etf.inception_date,etf.listing_date,etf.custodian];
    const coverage=Math.round(coverageFields.filter(Boolean).length/coverageFields.length*100);
    $("#primaryChart").innerHTML=`<h2>ETF 官方資料覆蓋</h2>${radar([
      etf.manager?100:20,etf.aum?100:35,etf.benchmark?100:25,
      Array.isArray(etf.holdings)&&etf.holdings.length?100:25,quote?100:30
    ],["經理人","規模","指數","持股","交易"])}<p class="section-note">依證交所基金基本資料與投信公告計算，目前靜態資料覆蓋 ${coverage}%；不代表投資評等。</p>`;
    const sectors=Array.isArray(etf.sectors)?etf.sectors.filter(row=>finite(row.weight)!==null):[];
    $("#secondaryChart").innerHTML=sectors.length
      ? `<h2>官方產業配置</h2><div class="donut-wrap"><div class="donut"></div><div class="legend">${sectors.slice(0,6).map((s,i)=>`<span><i style="background:${["var(--blue)","var(--green)","var(--amber)","var(--violet)","#71889b","#8bdcc7"][i%6]}"></i>${escapeHtml(s.name)} ${s.weight}%</span>`).join("")}</div></div>`
      : `<h2>官方產業配置</h2><div class="empty">投信持股／產業配置排程尚未取得資料；不使用示意成分股代替。</div>`;
    $("#fundamentalTitle").textContent="ETF 核心資料";
    const activeLabel=/主動/i.test(`${etf.category||""} ${asset.name||""}`)?"主動式":etf.leverage||"一般指數型";
    $("#profileGrid").innerHTML=[
      info("發行／經理公司",etf.issuer||"基金基本資料排程待更新"),
      info("基金經理人",etf.manager||"基金基本資料排程待更新"),
      info("ETF 類型",etf.category||"基金基本資料排程待更新"),
      info("標的指數／績效指標",etf.benchmark||(/主動/i.test(activeLabel)?"主動操作，無固定追蹤指數":"基金基本資料排程待更新")),
      info("操作型態",activeLabel),
      info("投資策略",etf.strategy||"公開說明書／投信公告待更新"),
      info("成立日期",etf.inception_date||"基金基本資料排程待更新"),
      info("上市日期",etf.listing_date||"基金基本資料排程待更新"),
      info("保管機構",etf.custodian||"基金基本資料排程待更新"),
      info("基金規模",etf.aum||"官方規模排程待更新"),
      info("配息狀況",etf.distribution||"依投信與證交所公告"),
      info("內扣費用",etf.expense_ratio||"公開說明書")
    ].join("");
    const holdings=Array.isArray(etf.holdings)?etf.holdings.filter(h=>finite(h.weight)!==null):[];
    if(holdings.length){
      const max=Math.max(...holdings.map(h=>Number(h.weight)||0),1);
      $("#holdingBars").innerHTML=`<h2 style="font-size:19px">前十大官方持股</h2>${holdings.slice(0,10).map(h=>`<div class="bar-row"><strong>${escapeHtml(h.symbol||"")} ${escapeHtml(h.name||"")}</strong><span class="bar-track"><i style="width:${(Number(h.weight)/max*100).toFixed(1)}%"></i></span><b>${h.weight}%</b></div>`).join("")}<p class="section-note">主動式 ETF 持股可能每日變動，以經理公司最新公告為準。</p>`;
    }else{
      $("#holdingBars").innerHTML=`<h2 style="font-size:19px">前十大官方持股</h2><div class="empty">尚未取得投信最新持股公告；不以指數成分或猜測權重代替。</div>`;
    }
    $("#returnGrid").innerHTML=[info("一日",formatPercent(pct)),info("一週",etf.returns?.week||"績效排程待更新"),info("一個月",etf.returns?.month||"績效排程待更新"),info("三個月",etf.returns?.quarter||"績效排程待更新")].join("");
    $("#dividendGrid").innerHTML=[info("配息頻率",etf.distribution||"依官方公告"),info("最近配息",etf.last_distribution||"尚無／排程待更新"),info("基金經理人",etf.manager||"基金基本資料排程待更新"),info("適用欄位","ETF 不顯示個股 EPS 與本益比")].join("");
  }else{
    const values=[metrics.net_margin?Math.min(100,50+metrics.net_margin):55,metrics.debt_ratio?Math.max(10,100-metrics.debt_ratio):55,metrics.current_ratio?Math.min(100,metrics.current_ratio*45):55,metrics.pe?Math.max(10,100-Math.min(80,metrics.pe*2)):55,metrics.roe?Math.min(100,40+metrics.roe*2):55];
    $("#primaryChart").innerHTML=`<h2>穩健度模型</h2>${radar(values,["獲利","負債","流動","估值","收益"])}<p class="section-note">模型依官方財報可取得欄位計算；缺值以中性分數顯示。</p>`;
    $("#secondaryChart").innerHTML=`<h2>行業排名</h2><div class="rank-grid">${info("產業 EPS 排名",asset.rankings?.eps||"財報排程待更新")}${info("產業 ROE 排名",asset.rankings?.roe||"財報排程待更新")}${info("產業估值分位",asset.rankings?.valuation||"估值排程待更新")}${info("產業穩健度排名",asset.rankings?.stability||"財報排程待更新")}</div>`;
    const monthly=asset.monthly_revenue||{};
    const dividend=asset.dividend||{};
    $("#profileGrid").innerHTML=[
      info("官方產業",asset.official_industry),info("子產業",asset.sub_industry),
      info("本益比",finite(metrics.pe)!==null?metrics.pe.toFixed(2):"估值排程待更新"),
      info("股價淨值比",finite(metrics.pb)!==null?metrics.pb.toFixed(2):"估值排程待更新"),
      info("ROE",finite(metrics.roe)!==null?`${metrics.roe.toFixed(2)}%`:"財報排程待更新"),
      info("負債比",finite(metrics.debt_ratio)!==null?`${metrics.debt_ratio.toFixed(2)}%`:"財報排程待更新"),
      info("最新月營收",finite(monthly.revenue)!==null?Number(monthly.revenue).toLocaleString("zh-TW"):"月營收排程待更新"),
      info("月營收年增",finite(monthly.monthly_yoy_percent)!==null?`${Number(monthly.monthly_yoy_percent).toFixed(2)}%`:"月營收排程待更新"),
      info("現金股利",finite(dividend.cash_dividend)!==null?`${Number(dividend.cash_dividend).toFixed(2)} 元`:"股利公告待更新"),
      info("資料狀態",asset.analysis_note||"全市場自動稽核")
    ].join("");
    $("#returnGrid").innerHTML=[info("一日",formatPercent(pct)),info("一週","排程待更新"),info("一個月","排程待更新"),info("一年","排程待更新")].join("");
    $("#dividendGrid").innerHTML=[info("殖利率",finite(metrics.dividend_yield)!==null?`${metrics.dividend_yield.toFixed(2)}%`:"資料不足"),info("最近股利","官方公告待更新"),info("除權息日","官方公告待更新"),info("現金股利","官方公告待更新")].join("");
  }
  $("#chipsGrid").innerHTML=[info("外資買賣超",finite(chip.foreign_net)!==null?`${chip.foreign_net.toLocaleString("zh-TW")} 股`:"官方資料待更新"),info("投信買賣超",finite(chip.trust_net)!==null?`${chip.trust_net.toLocaleString("zh-TW")} 股`:"官方資料待更新"),info("當沖比",finite(chip.day_trading_ratio)!==null?`${chip.day_trading_ratio.toFixed(2)}%`:"官方資料待更新"),info("融資餘額",finite(chip.margin_balance)!==null?`${chip.margin_balance.toLocaleString("zh-TW")} 股`:"官方資料待更新")].join("");

  const news=(newsPayload.items||[]).map(item=>({item,score:newsScore(item,asset)})).filter(r=>r.score>0).sort((a,b)=>b.score-a.score||new Date(b.item.published_at)-new Date(a.item.published_at)).slice(0,14);
  $("#assetNews").innerHTML=news.length?news.map(({item})=>`<a href="${escapeHtml(safeNewsLink(item))}" target="_blank" rel="noreferrer noopener"><time>${formatTime(item.published_at)}</time><span><b>${escapeHtml(item.source||"財經新聞")}</b><strong>${escapeHtml(item.title)}</strong><small>${escapeHtml(item.summary||"點擊閱讀原文")}</small></span><span>↗</span></a>`).join(""):'<div class="empty">新聞排程完成後，會用正式名稱、代碼、指數、產業與 ETF 成分股關聯。</div>';

  const official=[];
  if(asset.market==="TW")official.push(`<a href="https://mis.twse.com.tw/stock/fibest.jsp?stock=${encodeURIComponent(asset.symbol)}" target="_blank" rel="noreferrer">證交所即時行情 ↗</a>`);
  if(isEtf&&asset.etf?.official_url)official.push(`<a href="${asset.etf.official_url}" target="_blank" rel="noreferrer">ETF e添富官方頁 ↗</a>`);
  official.push('<a href="https://mops.twse.com.tw/mops/web/index" target="_blank" rel="noreferrer">公開資訊觀測站 ↗</a>');
  official.push('<a href="coverage.html">全市場資料覆蓋稽核 →</a>');
  $("#officialLinks").innerHTML=official.join("");

  let liveQuoteBusy=false;
  async function refreshCurrentQuote(){
    if(liveQuoteBusy||document.hidden||asset.market!=="TW")return;
    liveQuoteBusy=true;
    try{
      const rows=await fetchTaiwanLiveQuotes([asset]);
      const fresh=rows.find(row=>String(row.symbol)===String(asset.symbol));
      if(!fresh)return;
      quote={...(quote||{}),...fresh};
      const freshPrice=finite(quote.price);
      const freshPct=finite(quote.change_percent);
      updateMetric("最新價格",formatPrice(freshPrice,asset.currency));
      updateMetric("漲跌幅",formatPercent(freshPct),direction(freshPct));
      if(isEtf){
        updateMetric("最低",formatPrice(quote.low,asset.currency));
      }else{
        updateMetric("開盤",formatPrice(quote.open,asset.currency));
        updateMetric("最高",formatPrice(quote.high,asset.currency));
        updateMetric("最低",formatPrice(quote.low,asset.currency));
      }
      updateMetric("成交量",`${formatVolume(quote.volume)} 張`);
      $("#assetMeta").textContent=`${asset.exchange||asset.market} · ${asset.official_industry||asset.sub_industry||"待分類"} · ${asset.currency||""} · 5 秒快照 ${quote.quote_time||""}`;
    }catch(error){
      console.warn("Asset fast refresh failed:",error);
    }finally{
      liveQuoteBusy=false;
    }
  }

  $$("[data-tab]").forEach(btn=>btn.addEventListener("click",()=>{$$("[data-tab]").forEach(b=>b.classList.toggle("active",b===btn));$$("[data-panel]").forEach(panel=>panel.hidden=panel.dataset.panel!==btn.dataset.tab)}));
  if(asset.market==="TW"){
    scheduleAdaptiveRefresh(refreshCurrentQuote,taiwanQuoteRefreshDelay,2500);
  }
  if(isCrypto){
    startCryptoTickerStream({
      symbols:[asset.symbol],
      onUpdate:rows=>{
        const row=rows[0];
        if(!row)return;
        quote={
          price:row.current_price,
          change_percent:row.price_change_percentage_24h,
          open:row.current_price/(1+(Number(row.price_change_percentage_24h)||0)/100),
          high:row.high_24h,
          low:row.low_24h,
          volume:row.total_volume,
          quote_time:new Date(row.updated_at||Date.now()).toLocaleTimeString("zh-TW",{hour12:false})
        };
        updateMetric("最新價格",formatPrice(quote.price,"USD"));
        updateMetric("漲跌幅",formatPercent(quote.change_percent),direction(quote.change_percent));
        updateMetric("開盤",formatPrice(quote.open,"USD"));
        updateMetric("最高",formatPrice(quote.high,"USD"));
        updateMetric("最低",formatPrice(quote.low,"USD"));
        updateMetric("成交量",finite(quote.volume)!==null?`$${Number(quote.volume).toLocaleString("en-US",{maximumFractionDigits:0})}`:"—");
        $("#assetMeta").textContent=`CRYPTO · USD · 每秒行情 ${quote.quote_time}`;
      }
    });
  }
  document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshCurrentQuote()});
})();
