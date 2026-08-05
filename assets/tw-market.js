(async()=>{
  "use strict";
  const {$,escapeHtml,fmt,pct,cls,formatTime,loadData,loadStockBasics,finite}=MR;
  const [payload,stockBasicsPayload]=await Promise.all([loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),loadStockBasics()]),rows=payload.items||[],stockBasics=stockBasicsPayload.items||{};
  const allMap=new Map(rows.filter(item=>["stock","etf"].includes(item.asset_class)).map(item=>[String(item.symbol),item]));
  for(const [symbol,basic] of Object.entries(stockBasics))if(!allMap.has(symbol))allMap.set(symbol,{symbol,name:basic.short_name||basic.company_name||symbol,exchange:basic.exchange,asset_class:"stock",price:null,change_percent:null,volume:null,trade_value:null,quote_time:"基本資料已收錄"});
  const searchable=[...allMap.values()];
  $("#marketDate").textContent=payload.metadata?.updated_at?formatTime(payload.metadata.updated_at):"等待更新";
  $("#upCount").textContent=finite(payload.breadth?.up)==null?"—":fmt(payload.breadth.up,0);
  $("#downCount").textContent=finite(payload.breadth?.down)==null?"—":fmt(payload.breadth.down,0);
  $("#flatCount").textContent=finite(payload.breadth?.flat)==null?"—":fmt(payload.breadth.flat,0);
  const valid=rows.filter(item=>["stock","etf"].includes(item.asset_class)&&finite(item.price)!=null&&finite(item.change_percent)!=null);
  const rank=(assetClass,ascending)=>valid.filter(item=>item.asset_class===assetClass).sort((a,b)=>ascending?finite(a.change_percent)-finite(b.change_percent):finite(b.change_percent)-finite(a.change_percent)).slice(0,15);
  const rankHtml=data=>data.map((item,index)=>`<tr><td>${index+1}</td><td><a href="asset.html?symbol=${encodeURIComponent(item.symbol)}"><b>${escapeHtml(item.symbol)}</b><br><small>${escapeHtml(item.name||"")}</small></a></td><td>${fmt(item.price)}</td><td class="${cls(item.change_percent)}">${pct(item.change_percent)}</td><td>${fmt(item.volume,0)}</td><td>${fmt(item.trade_value,0)}</td></tr>`).join("")||'<tr><td colspan="6" class="empty">等待行情資料</td></tr>';
  $("#stockGainers").innerHTML=rankHtml(rank("stock",false));
  $("#stockLosers").innerHTML=rankHtml(rank("stock",true));
  $("#etfGainers").innerHTML=rankHtml(rank("etf",false));
  $("#etfLosers").innerHTML=rankHtml(rank("etf",true));
  function search(){
    const query=$("#marketSearch").value.trim().toLowerCase(),wrap=$("#marketSearchWrap");
    if(!query){wrap.hidden=true;$("#marketSearchRows").innerHTML="";return}
    const data=searchable.filter(item=>`${item.symbol} ${item.name}`.toLowerCase().includes(query)).slice(0,80);
    wrap.hidden=false;
    $("#marketSearchRows").innerHTML=data.map(item=>`<tr><td><a href="asset.html?symbol=${encodeURIComponent(item.symbol)}"><b>${escapeHtml(item.symbol)}</b><br><small>${escapeHtml(item.name||"")}</small></a></td><td>${escapeHtml(item.exchange||"")}</td><td>${fmt(item.price)}</td><td class="${cls(item.change_percent)}">${pct(item.change_percent)}</td><td>${fmt(item.volume,0)}</td><td>${fmt(item.trade_value,0)}</td><td>${escapeHtml(item.quote_time||"")}</td></tr>`).join("")||'<tr><td colspan="7" class="empty">找不到符合的標的</td></tr>';
  }
  $("#marketSearch").oninput=search;
})();
