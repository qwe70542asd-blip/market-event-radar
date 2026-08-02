(async()=>{"use strict";
const{$,$$,escapeHtml,finite,loadData,formatMoney,formatPercent,formatTime,direction}=MR;
const payload=await loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{markets:{},items:{}});
let market="twse";
const money=v=>finite(v)===null?"官方資料待更新":formatMoney(v,true);
function card(label,value,cls=""){return`<article class="info-card"><span>${label}</span><strong class="${cls}">${value}</strong></article>`}
function render(){
 const row=payload.markets?.[market]||{},inst=row.institutional||{};
 $("#institutionalGrid").innerHTML=[
  card("外資",money(inst.foreign_net),direction(inst.foreign_net)),
  card("投信",money(inst.trust_net),direction(inst.trust_net)),
  card("自營商",money(inst.dealer_net),direction(inst.dealer_net)),
  card("三大法人合計",money(inst.total_net),direction(inst.total_net))
 ].join("");
 $("#marginGrid").innerHTML=[
  card("當沖比",finite(row.day_trading?.ratio_percent)!==null?formatPercent(row.day_trading.ratio_percent):"官方資料待更新"),
  card("當沖成交值",finite(row.day_trading?.trade_value)!==null?formatMoney(row.day_trading.trade_value):"官方資料待更新"),
  card("融資餘額",finite(row.margin?.balance_shares)!==null?`${row.margin.balance_shares.toLocaleString("zh-TW")} 股`:"官方資料待更新"),
  card("融券餘額",finite(row.short?.balance_shares)!==null?`${row.short.balance_shares.toLocaleString("zh-TW")} 股`:"官方資料待更新")
 ].join("");
 const items=Object.values(payload.items||{}).filter(item=>(item.market||"twse")===market).sort((a,b)=>(b.total_net||0)-(a.total_net||0)).slice(0,30);
 $("#flowRows").innerHTML=items.length?items.map(item=>`<tr><td><a href="asset.html?id=TW:${escapeHtml(item.symbol)}"><strong>${escapeHtml(item.symbol)}</strong></a></td><td>${escapeHtml(item.name||"")}</td><td class="${direction(item.foreign_net)}">${money(item.foreign_net)}</td><td class="${direction(item.trust_net)}">${money(item.trust_net)}</td><td class="${direction(item.dealer_net)}">${money(item.dealer_net)}</td><td class="${direction(item.total_net)}">${money(item.total_net)}</td></tr>`).join(""):'<tr><td colspan="6"><div class="empty">等待官方個股法人資料排程。</div></td></tr>';
}
$("#chipDate").textContent=payload.metadata?.trading_date||"最後交易日";$("#chipUpdated").textContent=formatTime(payload.metadata?.updated_at);
$$("[data-market]").forEach(btn=>btn.addEventListener("click",()=>{market=btn.dataset.market;$$("[data-market]").forEach(b=>b.classList.toggle("active",b===btn));render()}));render();
})();
