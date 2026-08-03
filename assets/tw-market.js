(async () => {
  "use strict";
  const { $, $$, escapeHtml, finite, loadData, fetchTaiwanLiveQuotes, mergeQuoteItems,
    mergeAssets, loadPortfolio, migratePortfolio, findTwQuote, formatPrice, formatPercent,
    formatMoney, formatVolume, direction, formatTime, scheduleAdaptiveRefresh,
    taiwanQuoteRefreshDelay } = MR;
  const [initialPayload,assetPayload]=await Promise.all([
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]})
  ]);
  const assets=mergeAssets(assetPayload.assets||[],(window.__ASSET_SEED__||{}).assets||[]);
  const entries=migratePortfolio(loadPortfolio(),assets).filter(e=>e.market==="TW");
  const state={exchange:"ALL",assetClass:"all"};
  let payload=initialPayload;
  function validQuote(item){
    const price=finite(item?.price),previous=finite(item?.previous_close),pct=finite(item?.change_percent);
    return price!==null&&price>0&&previous!==null&&previous>0&&pct!==null&&Math.abs(pct)<=50;
  }
  let items=(payload.items||[]).filter(validQuote);
  let visibleRefreshBusy=false;
  let fullRefreshBusy=false;
  function filtered(){return items.filter(i=>state.exchange==="ALL"||i.exchange===state.exchange).filter(i=>state.assetClass==="all"||i.asset_class===state.assetClass)}
  function row(item,index){return `<tr><td>${index+1}</td><td><a href="asset.html?id=${encodeURIComponent(`TW:${item.symbol}`)}"><strong>${escapeHtml(item.symbol)} ${escapeHtml(item.name)}</strong><small>${item.exchange==="TPEx"?"上櫃":"上市"}${item.asset_class==="etf"?" · ETF":""}</small></a></td><td><strong>${formatPrice(item.price,"TWD")}</strong><small>${formatPrice(item.change,"TWD")}</small></td><td><strong class="${direction(item.change_percent)}">${formatPercent(item.change_percent)}</strong></td><td>${formatVolume(item.volume)} 張</td></tr>`}
  function renderRanks(){
    const rows=filtered();
    const gainers=rows.filter(i=>validQuote(i)&&finite(i.change_percent)>0).sort((a,b)=>b.change_percent-a.change_percent||(b.volume||0)-(a.volume||0)).slice(0,20);
    const losers=rows.filter(i=>validQuote(i)&&finite(i.change_percent)<0).sort((a,b)=>a.change_percent-b.change_percent||(b.volume||0)-(a.volume||0)).slice(0,20);
    $("#gainers").innerHTML=gainers.length?gainers.map(row).join(""):'<tr><td colspan="5"><div class="empty">此篩選沒有上漲資料。</div></td></tr>';
    $("#losers").innerHTML=losers.length?losers.map(row).join(""):'<tr><td colspan="5"><div class="empty">此篩選沒有下跌資料。</div></td></tr>';
  }
  function renderMeta(){
    const up=items.filter(i=>i.change_percent>0).length,down=items.filter(i=>i.change_percent<0).length;
    $("#upCount").textContent=up.toLocaleString("zh-TW");$("#downCount").textContent=down.toLocaleString("zh-TW");$("#flatCount").textContent=(items.length-up-down).toLocaleString("zh-TW");$("#quoteCount").textContent=items.length.toLocaleString("zh-TW");
    $("#twUpdated").textContent=`前 40 名與持股 5 秒快照 · 全市場基準 ${formatTime(payload?.metadata?.updated_at)}`;
  }
  function renderPortfolio(){
    let value=0,cost=0,pnl=0,day=0,hasPnl=false,hasDay=false;
    const rows=entries.map(entry=>{
      const quote=findTwQuote(entry,payload),price=finite(quote?.price),prev=finite(quote?.previous_close),shares=finite(entry.shares),avg=finite(entry.avg_cost);
      const val=price!==null&&shares!==null?price*shares:null,cst=avg!==null&&shares!==null?avg*shares:null,profit=val!==null&&cst!==null?val-cst:null,daily=price!==null&&prev!==null&&shares!==null?(price-prev)*shares:null;
      if(val!==null)value+=val;if(cst!==null)cost+=cst;if(profit!==null){pnl+=profit;hasPnl=true}if(daily!==null){day+=daily;hasDay=true}
      return `<tr><td><a href="asset.html?id=${encodeURIComponent(entry.asset_id)}"><strong>${escapeHtml(entry.symbol)} ${escapeHtml(entry.name)}</strong><small>${entry.asset_class==="etf"?"ETF":"股票"}</small></a></td><td><strong>${formatPrice(price)}</strong><small class="${direction(quote?.change_percent)}">${formatPercent(quote?.change_percent)}</small></td><td><strong>${shares===null?"觀察":`${shares.toLocaleString("zh-TW")} 股`}</strong><small>${avg===null?"未填成本":`均價 ${formatPrice(avg)}`}</small></td><td>${formatMoney(val)}</td><td><strong class="${direction(profit)}">${formatMoney(profit,true)}</strong><small>${profit!==null&&cst?formatPercent(profit/cst*100):"—"}</small></td></tr>`;
    });
    $("#twHoldings").innerHTML=rows.length?rows.join(""):'<tr><td colspan="5"><div class="empty">尚未加入台股標的。</div></td></tr>';
    $("#twPortfolioStats").innerHTML=`<article class="stat"><span>持有市值</span><strong>${formatMoney(value)}</strong></article><article class="stat"><span>投入成本</span><strong>${formatMoney(cost)}</strong></article><article class="stat"><span>未實現損益</span><strong class="${direction(hasPnl?pnl:null)}">${hasPnl?formatMoney(pnl,true):"—"}</strong></article><article class="stat"><span>今日損益</span><strong class="${direction(hasDay?day:null)}">${hasDay?formatMoney(day,true):"—"}</strong></article>`;
  }
  function liveTargets(){
    const rows=filtered();
    const gainers=rows.filter(item=>validQuote(item)&&finite(item.change_percent)>0).sort((a,b)=>b.change_percent-a.change_percent||(b.volume||0)-(a.volume||0)).slice(0,20);
    const losers=rows.filter(item=>validQuote(item)&&finite(item.change_percent)<0).sort((a,b)=>a.change_percent-b.change_percent||(b.volume||0)-(a.volume||0)).slice(0,20);
    const holdings=entries.map(entry=>({
      symbol:entry.symbol,
      exchange:entry.exchange,
      market_board:String(entry.exchange||"").toUpperCase().includes("TPEX")?"tpex":"twse"
    }));
    const map=new Map();
    [...gainers,...losers,...holdings].forEach(row=>{
      const symbol=String(row.symbol||"").toUpperCase();
      if(!symbol)return;
      map.set(`${String(row.exchange||"TWSE").toUpperCase()}:${symbol}`,row);
    });
    return [...map.values()];
  }

  async function refreshVisibleQuotes(){
    if(visibleRefreshBusy||document.hidden)return;
    visibleRefreshBusy=true;
    try{
      const rows=await fetchTaiwanLiveQuotes(liveTargets());
      if(rows.length){
        payload={
          ...payload,
          metadata:{...(payload.metadata||{}),updated_at:new Date().toISOString(),source:"TWSE MIS 5 秒快照"},
          items:mergeQuoteItems(payload.items||[],rows)
        };
        items=(payload.items||[]).filter(validQuote);
        renderMeta();renderRanks();renderPortfolio();
      }
    }catch(error){
      console.warn("Visible Taiwan quote refresh failed:",error);
    }finally{
      visibleRefreshBusy=false;
    }
  }

  async function refreshFullSnapshot(){
    if(fullRefreshBusy||document.hidden)return;
    fullRefreshBusy=true;
    try{
      const latest=await loadData("tw-market.json",payload);
      const oldTime=Date.parse(payload?.metadata?.updated_at||0);
      const newTime=Date.parse(latest?.metadata?.updated_at||0);
      if(latest?.items?.length&&newTime>oldTime){
        payload=latest;
        items=(payload.items||[]).filter(validQuote);
        renderMeta();renderRanks();renderPortfolio();
      }
    }catch(error){
      console.warn("Full Taiwan snapshot refresh failed:",error);
    }finally{
      fullRefreshBusy=false;
    }
  }

  $$("[data-exchange]").forEach(btn=>btn.addEventListener("click",()=>{state.exchange=btn.dataset.exchange;$$("[data-exchange]").forEach(b=>b.classList.toggle("active",b===btn));renderRanks()}));
  $$("[data-class]").forEach(btn=>btn.addEventListener("click",()=>{state.assetClass=btn.dataset.class;$$("[data-class]").forEach(b=>b.classList.toggle("active",b===btn));renderRanks()}));
  renderMeta();renderRanks();renderPortfolio();
  scheduleAdaptiveRefresh(refreshVisibleQuotes,taiwanQuoteRefreshDelay,2500);
  setInterval(refreshFullSnapshot,60_000);
  document.addEventListener("visibilitychange",()=>{
    if(!document.hidden){refreshVisibleQuotes();refreshFullSnapshot()}
  });
})();
