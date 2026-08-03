(async()=>{
  "use strict";

  const {
    $,escapeHtml,finite,loadData,mergeAssets,searchAssets,resolveAsset,findTwQuote,
    formatPrice,formatPercent,formatMoney,formatTime,direction
  }=MR;

  const [chipPayload,assetPayload,marketPayload]=await Promise.all([
    loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{markets:{},items:{}}),
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]}),
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]})
  ]);

  const assets=mergeAssets(assetPayload.assets||[],(window.__ASSET_SEED__||{}).assets||[])
    .filter(asset=>asset.market==="TW");
  const state={
    market:"twse",
    date:"",
    selectedAsset:null
  };

  function legacySnapshot(payload){
    const date=payload?.metadata?.trading_date||"";
    return {
      date,
      markets:payload?.markets||{},
      items:payload?.items||{}
    };
  }

  const history={...(chipPayload.history||{})};
  const latestDate=chipPayload?.metadata?.trading_date||"";
  if(latestDate&&!history[latestDate]){
    history[latestDate]=legacySnapshot(chipPayload);
  }
  const dates=[...new Set([
    ...(chipPayload.available_dates||[]),
    ...Object.keys(history),
    latestDate
  ].filter(Boolean))].sort().reverse();
  state.date=dates[0]||latestDate;

  function snapshot(){
    return history[state.date]||legacySnapshot(chipPayload);
  }

  function marketLabel(market){
    return market==="tpex"?"上櫃 TPEx":"上市 TWSE";
  }

  function numberText(value,unit="股"){
    const parsed=finite(value);
    return parsed===null?"官方未回傳":`${Math.round(parsed).toLocaleString("zh-TW")} ${unit}`;
  }

  function signedText(value){
    const parsed=finite(value);
    if(parsed===null)return"官方未回傳";
    const prefix=parsed>0?"+":"";
    return `${prefix}${Math.round(parsed).toLocaleString("zh-TW")} 股`;
  }

  function pctText(value){
    const parsed=finite(value);
    return parsed===null?"官方未回傳":`${parsed.toFixed(2)}%`;
  }

  function infoCard(label,value,cls="",note=""){
    return `<article class="info-card query-info-card">
      <span>${escapeHtml(label)}</span>
      <strong class="${cls}">${escapeHtml(String(value))}</strong>
      ${note?`<small>${escapeHtml(note)}</small>`:""}
    </article>`;
  }

  function currentItems(){
    const values=Object.values(snapshot().items||{});
    return values.filter(item=>(item.market||"twse")===state.market);
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
      infoCard("融券增減",signedText(short.change),direction(short.change),"相較前一交易日")
    ].join("");

    const hasData=items.length||Object.values(institutional).some(value=>finite(value)!==null)||
      finite(margin.balance)!==null||finite(short.balance)!==null;
    $("#marketQueryStatus").textContent=hasData
      ?`${marketLabel(state.market)} · ${state.date||"最後交易日"} · ${items.length.toLocaleString("zh-TW")} 檔個股`
      :"此日期尚無可驗證資料，請改選其他日期。";

    if(state.selectedAsset)renderStockResult(state.selectedAsset);
  }

  function marketForAsset(asset){
    return String(asset.exchange||"").toUpperCase().includes("TPEX")?"tpex":"twse";
  }

  function findChipRow(asset){
    const market=marketForAsset(asset);
    const symbol=String(asset.symbol||"").toUpperCase();
    return Object.values(snapshot().items||{}).find(item=>
      String(item.symbol||"").toUpperCase()===symbol&&(item.market||"twse")===market
    )||null;
  }

  function detailMetric(label,value,cls="",note=""){
    return `<div class="stock-detail-metric">
      <span>${escapeHtml(label)}</span>
      <strong class="${cls}">${escapeHtml(String(value))}</strong>
      ${note?`<small>${escapeHtml(note)}</small>`:""}
    </div>`;
  }

  function financingTable(title,section,type){
    const row=section||{};
    const fields=type==="margin"
      ?[
        ["前日餘額",row.previous_balance],
        ["買進",row.buy],
        ["賣出",row.sell],
        ["現金償還",row.cash_repayment],
        ["今日餘額",row.balance],
        ["使用率",row.utilization_percent,"percent"]
      ]
      :[
        ["前日餘額",row.previous_balance],
        ["賣出",row.sell],
        ["買進",row.buy],
        ["現券償還",row.repayment],
        ["今日餘額",row.balance],
        ["使用率",row.utilization_percent,"percent"]
      ];
    const available=fields.some(([,value])=>finite(value)!==null);
    return `<section class="stock-detail-block">
      <div class="stock-detail-block-head"><h3>${escapeHtml(title)}</h3>
        <span>${available?"官方盤後資料":"非信用交易標的或官方未回傳"}</span></div>
      <div class="stock-detail-grid">
        ${fields.map(([label,value,kind])=>detailMetric(
          label,
          kind==="percent"?pctText(value):numberText(value),
          "",
          kind==="percent"?"額度使用比例":""
        )).join("")}
      </div>
    </section>`;
  }

  function renderStockResult(asset){
    state.selectedAsset=asset;
    const chip=findChipRow(asset);
    const quote=findTwQuote(asset,marketPayload);
    const result=$("#stockQueryResult");
    const status=$("#stockQueryStatus");
    const market=marketForAsset(asset);

    if(!chip){
      status.textContent=`${asset.symbol} ${asset.name} 在 ${state.date||"目前日期"} 尚無法人或融資融券明細。`;
      result.hidden=false;
      result.innerHTML=`<div class="empty stock-query-empty">
        <strong>${escapeHtml(asset.symbol)} ${escapeHtml(asset.name)}</strong>
        <span>可能是非信用交易標的、ETF 尚無該欄位，或官方資料尚未發布。</span>
        <a class="btn" href="asset.html?id=${encodeURIComponent(asset.id||`TW:${asset.symbol}`)}">查看個股完整頁 →</a>
      </div>`;
      return;
    }

    status.textContent=`已顯示 ${state.date||"最後交易日"} 的 ${marketLabel(market)} 官方資料。`;
    const price=finite(quote?.price);
    const pct=finite(quote?.change_percent);
    result.hidden=false;
    result.innerHTML=`<article class="stock-query-card">
      <div class="stock-query-heading">
        <div>
          <span class="asset-badge">${market==="tpex"?"上櫃":"上市"}</span>
          <h2>${escapeHtml(asset.name)} <em>${escapeHtml(asset.symbol)}</em></h2>
          <p>${escapeHtml(asset.official_industry||asset.sub_industry||"產業分類待更新")} · ${state.date||"最後交易日"}</p>
        </div>
        <div class="stock-query-price">
          <span>參考行情</span>
          <strong>${price===null?"—":formatPrice(price,"TWD")}</strong>
          <em class="${direction(pct)}">${formatPercent(pct)}</em>
        </div>
      </div>

      <section class="stock-detail-block">
        <div class="stock-detail-block-head"><h3>三大法人</h3><span>單位：股</span></div>
        <div class="stock-detail-grid">
          ${detailMetric("外資",signedText(chip.foreign_net),direction(chip.foreign_net),
            `買 ${numberText(chip.foreign_buy)}／賣 ${numberText(chip.foreign_sell)}`)}
          ${detailMetric("投信",signedText(chip.trust_net),direction(chip.trust_net),
            `買 ${numberText(chip.trust_buy)}／賣 ${numberText(chip.trust_sell)}`)}
          ${detailMetric("自營商",signedText(chip.dealer_net),direction(chip.dealer_net),
            `買 ${numberText(chip.dealer_buy)}／賣 ${numberText(chip.dealer_sell)}`)}
          ${detailMetric("合計",signedText(chip.total_net),direction(chip.total_net),"三大法人買賣超")}
        </div>
      </section>

      <div class="stock-financing-layout">
        ${financingTable("融資",chip.margin,"margin")}
        ${financingTable("融券",chip.short,"short")}
      </div>

      <div class="stock-query-footer">
        <span>資券互抵：${numberText(chip.offset_shares)}</span>
        <span>${chip.note?`備註：${escapeHtml(chip.note)}`:"缺值不以 0 顯示"}</span>
        <a class="btn" href="asset.html?id=${encodeURIComponent(asset.id||`TW:${asset.symbol}`)}">查看個股完整頁 →</a>
      </div>
    </article>`;
  }

  function renderSuggestions(){
    const query=$("#stockQueryInput").value.trim();
    const box=$("#stockQuerySuggestions");
    if(!query){
      box.hidden=true;
      box.innerHTML="";
      return;
    }
    const rows=searchAssets(assets,query,{market:"TW",asset_class:"all"}).slice(0,8);
    if(!rows.length){
      box.hidden=false;
      box.innerHTML='<div class="empty">找不到符合的台股代碼或名稱。</div>';
      return;
    }
    box.hidden=false;
    box.innerHTML=rows.map(asset=>`<button type="button" data-asset-id="${escapeHtml(asset.id)}">
      <strong>${escapeHtml(asset.symbol)}</strong>
      <span>${escapeHtml(asset.name)}</span>
      <small>${marketForAsset(asset)==="tpex"?"上櫃":"上市"} · ${asset.asset_class==="etf"?"ETF":"股票"}</small>
    </button>`).join("");
    box.querySelectorAll("button").forEach(button=>button.addEventListener("click",()=>{
      const asset=assets.find(row=>row.id===button.dataset.assetId);
      if(!asset)return;
      $("#stockQueryInput").value=`${asset.symbol} ${asset.name}`;
      box.hidden=true;
      renderStockResult(asset);
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
    renderStockResult(asset);
  }

  renderDateOptions();
  renderMarketResult();

  $("#marketSelect").addEventListener("change",event=>{
    state.market=event.target.value;
  });
  $("#dateSelect").addEventListener("change",event=>{
    state.date=event.target.value;
  });
  $("#marketQueryButton").addEventListener("click",renderMarketResult);
  $("#stockQueryInput").addEventListener("input",renderSuggestions);
  $("#stockQueryInput").addEventListener("keydown",event=>{
    if(event.key==="Enter"){
      event.preventDefault();
      queryStock();
    }
  });
  $("#stockQueryButton").addEventListener("click",queryStock);
  document.addEventListener("click",event=>{
    if(!event.target.closest(".stock-search-box"))$("#stockQuerySuggestions").hidden=true;
  });
})();
