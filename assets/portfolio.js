(async()=>{"use strict";
const {$,escapeHtml,fmt,pct,cls,finite,loadData,loadPortfolio,savePortfolio,loadWatchlist,saveWatchlist}=MR;
let assets=window.__ASSET_SEED__||{assets:[]},tw=window.__TW_MARKET_SEED__||{items:[]},global=window.__MARKET_SNAPSHOT_SEED__||{items:[]};
let quotes=new Map(),rows=loadPortfolio(),candidateMap=new Map(),candidates=[];
const addCandidate=(row,priority=0)=>{
  const symbol=String(row?.symbol||"").toUpperCase().trim();if(!symbol)return;
  const old=candidateMap.get(symbol)||{};
  const merged={...old,...row,symbol,_priority:Math.max(priority,old._priority||0)};
  merged.name=String(merged.name||merged.short_name||merged.company_name||symbol).trim();
  merged.asset_class=merged.asset_class||old.asset_class||"stock";
  merged.exchange=merged.exchange||merged.market_label||old.exchange||"";
  candidateMap.set(symbol,merged);
};
function rebuildMarketData(){quotes=new Map([...(tw.items||[]),...(global.items||[])].map(x=>[String(x.symbol||"").toUpperCase(),x]));candidateMap=new Map();for(const row of assets.assets||[])addCandidate(row,3);for(const row of tw.items||[])if(["stock","etf"].includes(row.asset_class))addCandidate(row,4);for(const row of global.items||[])if(row.asset_class||!/^[\^A-Z].*/.test(String(row.symbol||"")))addCandidate(row,1);candidates=[...candidateMap.values()]}
rebuildMarketData();
let matches=[],activeIndex=-1,selectedSymbol="";
const suggestions=$("#holdingSuggestions"),symbolInput=$("#holdingSymbol"),nameInput=$("#holdingName");
const marketLabel=row=>row.exchange||row.market_label||row.market||"";
const typeLabel=row=>row.asset_class==="etf"?"ETF":row.asset_class==="stock"?"股票":"標的";
function searchCandidates(raw){
  const q=String(raw||"").trim().toUpperCase();if(!q)return[];
  const nq=q.toLowerCase();
  return candidates.map(row=>{
    const symbol=String(row.symbol||"").toUpperCase(),name=String(row.name||"");let score=0;
    if(symbol===q)score=1000;else if(symbol.startsWith(q))score=800-Math.min(symbol.length-q.length,30);else if(symbol.includes(q))score=620;
    if(name.toLowerCase()===nq)score=Math.max(score,950);else if(name.toLowerCase().startsWith(nq))score=Math.max(score,720);else if(name.toLowerCase().includes(nq))score=Math.max(score,520);
    return score?{row,score:score+(row._priority||0)*5}:null;
  }).filter(Boolean).sort((a,b)=>b.score-a.score||String(a.row.symbol).localeCompare(String(b.row.symbol),"zh-Hant")).slice(0,10).map(x=>x.row);
}
function closeSuggestions(){matches=[];activeIndex=-1;suggestions.innerHTML="";suggestions.classList.remove("open");symbolInput.setAttribute("aria-expanded","false")}
function applyCandidate(row){if(!row)return;symbolInput.value=row.symbol;nameInput.value=row.name||row.symbol;selectedSymbol=row.symbol;closeSuggestions();symbolInput.focus()}
function renderSuggestions(){
  const query=symbolInput.value.trim();matches=searchCandidates(query);activeIndex=-1;selectedSymbol="";
  if(!query||!matches.length){closeSuggestions();return}
  suggestions.innerHTML=matches.map((row,index)=>`<button type="button" class="portfolio-suggestion" role="option" data-index="${index}" aria-selected="false"><span><b>${escapeHtml(row.symbol)}</b><strong>${escapeHtml(row.name||row.symbol)}</strong></span><small>${escapeHtml(typeLabel(row))}${marketLabel(row)?` · ${escapeHtml(marketLabel(row))}`:""}</small></button>`).join("");
  suggestions.classList.add("open");symbolInput.setAttribute("aria-expanded","true");
}
function setActive(index){
  if(!matches.length)return;activeIndex=(index+matches.length)%matches.length;
  suggestions.querySelectorAll(".portfolio-suggestion").forEach((node,i)=>{node.classList.toggle("active",i===activeIndex);node.setAttribute("aria-selected",i===activeIndex?"true":"false")});
  suggestions.querySelector(`[data-index="${activeIndex}"]`)?.scrollIntoView({block:"nearest"});
}
symbolInput.addEventListener("input",()=>{renderSuggestions();const exact=candidateMap.get(symbolInput.value.trim().toUpperCase());if(exact&&String(exact.symbol)===symbolInput.value.trim().toUpperCase()){nameInput.value=exact.name||exact.symbol;selectedSymbol=exact.symbol}});
symbolInput.addEventListener("keydown",event=>{
  if(event.key==="ArrowDown"&&matches.length){event.preventDefault();setActive(activeIndex+1)}
  else if(event.key==="ArrowUp"&&matches.length){event.preventDefault();setActive(activeIndex-1)}
  else if(event.key==="Enter"&&matches.length){event.preventDefault();applyCandidate(matches[activeIndex>=0?activeIndex:0])}
  else if(event.key==="Escape")closeSuggestions();
});
suggestions.addEventListener("pointerdown",event=>{const button=event.target.closest("[data-index]");if(!button)return;event.preventDefault();applyCandidate(matches[Number(button.dataset.index)])});
document.addEventListener("pointerdown",event=>{if(!event.target.closest(".portfolio-symbol-search"))closeSuggestions()});
const standardBrokerFeeRate=.001425;
function renderRetailCalculator(){
  const price=finite($("#retailToolPrice")?.value),qty=Math.floor(finite($("#retailToolQty")?.value)||0),budget=finite($("#retailToolBudget")?.value),type=$("#retailToolType")?.value||"stock",taxRate=type==="etf"?.001:.003;
  const gross=price!=null&&qty>0?price*qty:null,buy=gross==null?null:gross*(1+standardBrokerFeeRate),sell=gross==null?null:gross*(1-standardBrokerFeeRate-taxRate),breakEven=((1+standardBrokerFeeRate)/(1-standardBrokerFeeRate-taxRate)-1)*100,maxQty=price!=null&&price>0&&budget!=null&&budget>0?Math.floor(budget/(price*(1+standardBrokerFeeRate))):null;
  if($("#retailBuyAmount"))$("#retailBuyAmount").textContent=buy==null?"—":`NT$ ${fmt(buy,0)}`;
  if($("#retailSellNet"))$("#retailSellNet").textContent=sell==null?"—":`NT$ ${fmt(sell,0)}`;
  if($("#retailBreakEven"))$("#retailBreakEven").textContent=`${fmt(breakEven,2)}%`;
  if($("#retailMaxQty"))$("#retailMaxQty").textContent=maxQty==null?"—":`${fmt(maxQty,0)} 股`;
}
function renderWatchlist(){
  const root=$("#watchlistRows");if(!root)return;
  const list=loadWatchlist();
  root.innerHTML=list.map(item=>{const symbol=String(item.symbol).toUpperCase(),q=quotes.get(symbol),candidate=candidateMap.get(symbol)||{},price=finite(q?.price),change=finite(q?.change_percent),assetClass=item.asset_class||candidate.asset_class||q?.asset_class||"stock",lot=price==null?null:price*1000*(1+standardBrokerFeeRate);return `<article class="watchlist-card"><a href="asset.html?symbol=${encodeURIComponent(symbol)}"><small>${escapeHtml(assetClass==="etf"?"ETF":"股票")}</small><strong>${escapeHtml(symbol)} ${escapeHtml(item.name||candidate.name||q?.name||"")}</strong><span>${price==null?"等待行情":`NT$ ${fmt(price,2)}`} <em class="${cls(change)}">${change==null?"":pct(change)}</em></span><b>${lot==null?"1 張金額待行情":`1 張約 NT$ ${fmt(lot,0)}`}</b></a><div><button class="btn" type="button" data-watch-calc="${escapeHtml(symbol)}">試算</button><button class="btn" type="button" data-watch-del="${escapeHtml(symbol)}">移除</button></div></article>`}).join("")||'<div class="empty">尚未加入自選標的；到個股／ETF 詳情頁按「加入自選」。</div>';
  root.querySelectorAll("[data-watch-del]").forEach(button=>button.addEventListener("click",()=>{const symbol=button.dataset.watchDel;saveWatchlist(loadWatchlist().filter(item=>String(item.symbol).toUpperCase()!==symbol));renderWatchlist()}));
  root.querySelectorAll("[data-watch-calc]").forEach(button=>button.addEventListener("click",()=>{const symbol=button.dataset.watchCalc,q=quotes.get(symbol),candidate=candidateMap.get(symbol)||{},price=finite(q?.price);if(price!=null)$("#retailToolPrice").value=String(price);$("#retailToolType").value=(candidate.asset_class||q?.asset_class)==="etf"?"etf":"stock";renderRetailCalculator();$("#retailTools")?.scrollIntoView({behavior:"smooth",block:"start"})}));
}
for(const id of ["retailToolPrice","retailToolQty","retailToolType","retailToolBudget"]){$("#"+id)?.addEventListener("input",renderRetailCalculator);$("#"+id)?.addEventListener("change",renderRetailCalculator)}
window.addEventListener("watchlistchange",renderWatchlist);

function render(){
  const usdTwd=finite(quotes.get("TWD=X")?.price);
  const fxToTwd=currency=>{const code=String(currency||"TWD").toUpperCase();if(code==="TWD")return 1;if(code==="USD")return usdTwd&&usdTwd>0?usdTwd:null;const usdCross=finite(quotes.get(`${code}=X`)?.price);return usdTwd&&usdCross&&usdTwd>0&&usdCross>0?usdTwd/usdCross:null};
  let totalCost=0,totalValue=0,valuedRows=0,unconverted=0;
  $("#portfolioRows").innerHTML=rows.map((h,i)=>{
    const q=quotes.get(String(h.symbol).toUpperCase()),candidate=candidateMap.get(String(h.symbol).toUpperCase())||{},price=finite(q?.price),qty=Number(h.quantity||0),cost=Number(h.cost||0),currency=String(h.currency||q?.currency||candidate.currency||"TWD").toUpperCase(),fx=fxToTwd(currency),value=price==null?null:price*qty,pl=value==null?null:value-cost*qty,plPct=price==null||cost<=0?null:(price-cost)/cost*100;
    if(fx==null)unconverted++;else{totalCost+=cost*qty*fx;if(value!=null){totalValue+=value*fx;valuedRows++}}
    const money=value=>value==null?"—":`${currency==="TWD"?"":`${escapeHtml(currency)} `}${fmt(value,0)}`;
    return`<tr><td><a href="asset.html?symbol=${encodeURIComponent(h.symbol)}"><b>${escapeHtml(h.symbol)}</b><br><small>${escapeHtml(h.name||"")}${currency?` · ${escapeHtml(currency)}`:""}</small></a></td><td>${fmt(qty,4)}</td><td>${money(cost)}</td><td>${money(price)}</td><td>${money(value)}</td><td class="${cls(pl)}">${money(pl)}</td><td class="${cls(plPct)}">${plPct==null?"—":pct(plPct)}</td><td><button class="btn" data-del="${i}">刪除</button></td></tr>`
  }).join("")||'<tr><td colspan="8" class="empty">尚未加入標的</td></tr>';
  const complete=rows.length>0&&valuedRows===rows.length&&unconverted===0;
  $("#totalCost").textContent=complete?`NT$ ${fmt(totalCost,0)}`:"—";
  $("#totalValue").textContent=complete?`NT$ ${fmt(totalValue,0)}`:"—";
  $("#totalPL").textContent=complete?`${totalValue-totalCost>=0?"+":"-"}NT$ ${fmt(Math.abs(totalValue-totalCost),0)}`:"—";
  $("#totalPL").className=complete?cls(totalValue-totalCost):"flat";
  const totalReturn=complete&&totalCost>0?(totalValue-totalCost)/totalCost*100:null;
  $("#totalReturn").textContent=totalReturn==null?"—":pct(totalReturn);$("#totalReturn").className=totalReturn==null?"flat":cls(totalReturn);
  document.querySelectorAll("[data-del]").forEach(b=>b.onclick=()=>{rows.splice(Number(b.dataset.del),1);savePortfolio(rows);render()});
  renderWatchlist();renderRetailCalculator();
}
$("#addHolding").onclick=()=>{const symbol=symbolInput.value.trim().toUpperCase(),quantity=Number($("#holdingQty").value),cost=Number($("#holdingCost").value),candidate=candidateMap.get(symbol);if(!candidate){alert("找不到正式標的，請從搜尋選單選取股票或 ETF");symbolInput.focus();renderSuggestions();return}if(!Number.isFinite(quantity)||quantity<=0||!Number.isFinite(cost)){alert("請填入正確數量與平均成本");return}const existing=rows.find(row=>String(row.symbol).toUpperCase()===symbol);if(existing){const oldQty=Number(existing.quantity||0),newQty=oldQty+quantity;existing.cost=newQty?((oldQty*Number(existing.cost||0))+(quantity*cost))/newQty:cost;existing.quantity=newQty;existing.name=candidate.name||existing.name||symbol;existing.currency=existing.currency||candidate.currency||quotes.get(symbol)?.currency||"TWD"}else rows.push({symbol,name:candidate.name||symbol,quantity,cost,currency:candidate.currency||quotes.get(symbol)?.currency||"TWD"});savePortfolio(rows);render();selectedSymbol="";["holdingSymbol","holdingName","holdingQty","holdingCost"].forEach(id=>$("#"+id).value="");closeSuggestions()};
$("#exportPortfolio").onclick=()=>{const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([JSON.stringify({version:2,items:rows},null,2)],{type:"application/json"}));a.download="market-radar-portfolio.json";a.click()};
const normalizeImportedPortfolio=input=>{if(!Array.isArray(input)||input.length>500)throw Error("items");const merged=new Map();for(const raw of input){if(!raw||typeof raw!=="object")throw Error("row");const symbol=String(raw.symbol||"").trim().toUpperCase(),candidate=candidateMap.get(symbol),quantity=Number(raw.quantity??raw.qty),cost=Number(raw.cost??raw.average_cost);if(!candidate)throw Error(`unknown symbol ${symbol}`);if(!Number.isFinite(quantity)||quantity<=0||quantity>1e12)throw Error("quantity");if(!Number.isFinite(cost)||cost<0||cost>1e12)throw Error("cost");const currency=String(candidate.currency||quotes.get(symbol)?.currency||raw.currency||"TWD").trim().toUpperCase();if(!/^[A-Z]{3,5}$/.test(currency))throw Error("currency");const prior=merged.get(symbol);if(prior){const total=prior.quantity+quantity;prior.cost=((prior.quantity*prior.cost)+(quantity*cost))/total;prior.quantity=total}else merged.set(symbol,{symbol,name:candidate.name||symbol,quantity,cost,currency})}return [...merged.values()]};
$("#importPortfolio").onchange=async e=>{const file=e.target.files?.[0];try{if(!file||file.size>1024*1024)throw Error("size");const js=JSON.parse(await file.text()),input=Array.isArray(js)?js:js?.items;rows=normalizeImportedPortfolio(input);savePortfolio(rows);render()}catch(err){console.warn("portfolio import rejected",err);alert("匯入檔格式錯誤、內容不安全或包含不存在的標的") }finally{e.target.value=""}};
render();
loadData("assets.json",assets).then(fresh=>{if(Array.isArray(fresh?.assets)&&fresh.assets.length){assets=fresh;rebuildMarketData();render()}}).catch(()=>{});
loadData("tw-market.json",tw).then(fresh=>{if(Array.isArray(fresh?.items)&&fresh.items.length){tw=fresh;rebuildMarketData();render()}}).catch(()=>{});
loadData("market-snapshot.json",global).then(fresh=>{if(Array.isArray(fresh?.items)&&fresh.items.length){global=fresh;rebuildMarketData();render()}}).catch(()=>{});
})();
