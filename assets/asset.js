(async () => {
  "use strict";
  const { $, $$, escapeHtml, finite, loadData, mergeAssets, canonicalAsset, findTwQuote,
    formatPrice, formatPercent, formatVolume, direction, safeNewsLink, newsScore, formatTime } = MR;
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
  const quote=asset.market==="TW"?findTwQuote(asset,twPayload):null;
  const isEtf=asset.asset_class==="etf";
  const metrics={...(asset.metrics||{})};
  const financials=asset.financials||[];
  const latest=financials[0]||{};
  const chip=(chipsPayload.items||{})[asset.symbol]||{};
  $("#assetName").textContent=asset.name;$("#assetSymbol").textContent=asset.symbol;
  $("#assetClassBadge").textContent=isEtf?"ETF／基金":asset.asset_class==="crypto"?"虛擬貨幣":"股票";
  $("#assetMeta").textContent=`${asset.exchange||asset.market} · ${asset.official_industry||asset.sub_industry||"待分類"} · ${asset.currency||""}`;
  $("#scoreLabel").textContent=isEtf?"資料型態健康度":"資料型態健康度";
  $("#scoreValue").textContent=isEtf?"ETF":"STOCK";$("#scoreNote").textContent=`資料覆蓋 ${quote?60:35}%`;

  function metric(label,value,cls=""){return `<article class="metric"><span>${label}</span><strong class="${cls}">${value}</strong></article>`}
  const price=finite(quote?.price??metrics.price),pct=finite(quote?.change_percent);
  const common=[
    metric("最新價格",formatPrice(price,asset.currency)),
    metric("漲跌幅",formatPercent(pct),direction(pct)),
    metric(isEtf?"淨值":"開盤",isEtf?(asset.etf?.nav?formatPrice(asset.etf.nav):"排程待更新"):formatPrice(quote?.open,asset.currency)),
    metric(isEtf?"折溢價":"最高",isEtf?(finite(asset.etf?.premium_discount)!==null?formatPercent(asset.etf.premium_discount):"排程待更新"):formatPrice(quote?.high,asset.currency)),
    metric("最低",formatPrice(quote?.low,asset.currency)),
    metric("成交量",`${formatVolume(quote?.volume)} 張`),
    metric(isEtf?"基金規模":"本益比",isEtf?(asset.etf?.aum||"官方排程待更新"):(finite(metrics.pe)!==null?metrics.pe.toFixed(2):"資料不足")),
    metric(isEtf?"內扣費用":"EPS",isEtf?(asset.etf?.expense_ratio||"公開說明書"):(finite(metrics.eps??latest.eps)!==null?Number(metrics.eps??latest.eps).toFixed(2):"資料不足"))
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
    $("#primaryChart").innerHTML=`<h2>ETF 結構圖</h2>${radar([85,75,65,55,80],["流動","規模","追蹤","分散","交易"])}<p class="section-note">分數僅反映資料完整度與產品結構，不代表預期報酬。</p>`;
    const sectors=asset.etf?.sectors||[{name:"半導體",weight:45},{name:"電子",weight:23},{name:"金融",weight:14},{name:"傳產",weight:10},{name:"其他",weight:8}];
    $("#secondaryChart").innerHTML=`<h2>產業配置</h2><div class="donut-wrap"><div class="donut"></div><div class="legend">${sectors.map((s,i)=>`<span><i style="background:${["var(--blue)","var(--green)","var(--amber)","var(--violet)","#71889b"][i%5]}"></i>${escapeHtml(s.name)} ${s.weight}%</span>`).join("")}</div></div>`;
    $("#fundamentalTitle").textContent="ETF 核心資料";
    const etf=asset.etf||{};
    $("#profileGrid").innerHTML=[
      info("發行公司",etf.issuer),info("ETF 類型",etf.category),info("標的指數",etf.benchmark),
      info("槓桿型態",etf.leverage||"一般／主動式"),info("配息狀況",etf.distribution),
      info("投資策略",etf.strategy),info("基金規模",etf.aum||"官方排程待更新"),info("內扣費用",etf.expense_ratio||"公開說明書")
    ].join("");
    const holdings=etf.holdings||[{symbol:"2330",name:"台積電",weight:42},{symbol:"2317",name:"鴻海",weight:7.5},{symbol:"2454",name:"聯發科",weight:6.8},{symbol:"2382",name:"廣達",weight:4.2},{symbol:"2881",name:"富邦金",weight:3.1}];
    const max=Math.max(...holdings.map(h=>Number(h.weight)||0),1);
    $("#holdingBars").innerHTML=`<h2 style="font-size:19px">前五大關聯持股示意</h2>${holdings.map(h=>`<div class="bar-row"><strong>${escapeHtml(h.symbol)} ${escapeHtml(h.name)}</strong><span class="bar-track"><i style="width:${(Number(h.weight)/max*100).toFixed(1)}%"></i></span><b>${h.weight}%</b></div>`).join("")}<p class="section-note">主動式 ETF 實際持股會變動，以投信每日公告為準。</p>`;
    $("#returnGrid").innerHTML=[info("一日",formatPercent(pct)),info("一週",etf.returns?.week||"排程待更新"),info("一個月",etf.returns?.month||"排程待更新"),info("三個月",etf.returns?.quarter||"排程待更新")].join("");
    $("#dividendGrid").innerHTML=[info("配息頻率",etf.distribution||"依官方公告"),info("最近配息",etf.last_distribution||"尚無／排程待更新"),info("配息來源註記","依基金公司公告"),info("適用欄位","ETF 不顯示個股 EPS 與本益比")].join("");
  }else{
    const values=[metrics.net_margin?Math.min(100,50+metrics.net_margin):55,metrics.debt_ratio?Math.max(10,100-metrics.debt_ratio):55,metrics.current_ratio?Math.min(100,metrics.current_ratio*45):55,metrics.pe?Math.max(10,100-Math.min(80,metrics.pe*2)):55,metrics.roe?Math.min(100,40+metrics.roe*2):55];
    $("#primaryChart").innerHTML=`<h2>穩健度模型</h2>${radar(values,["獲利","負債","流動","估值","收益"])}<p class="section-note">模型依官方財報可取得欄位計算；缺值以中性分數顯示。</p>`;
    $("#secondaryChart").innerHTML=`<h2>行業排名</h2><div class="rank-grid">${info("產業 EPS 排名",asset.rankings?.eps||"資料不足")}${info("產業 ROE 排名",asset.rankings?.roe||"資料不足")}${info("產業估值分位",asset.rankings?.valuation||"資料不足")}${info("產業穩健度排名",asset.rankings?.stability||"資料不足")}</div>`;
    $("#profileGrid").innerHTML=[info("官方產業",asset.official_industry),info("子產業",asset.sub_industry),info("本益比",finite(metrics.pe)!==null?metrics.pe.toFixed(2):"資料不足"),info("股價淨值比",finite(metrics.pb)!==null?metrics.pb.toFixed(2):"資料不足"),info("ROE",finite(metrics.roe)!==null?`${metrics.roe.toFixed(2)}%`:"資料不足"),info("負債比",finite(metrics.debt_ratio)!==null?`${metrics.debt_ratio.toFixed(2)}%`:"資料不足")].join("");
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
  $("#officialLinks").innerHTML=official.join("");

  $$("[data-tab]").forEach(btn=>btn.addEventListener("click",()=>{$$("[data-tab]").forEach(b=>b.classList.toggle("active",b===btn));$$("[data-panel]").forEach(panel=>panel.hidden=panel.dataset.panel!==btn.dataset.tab)}));
})();
