(async()=>{"use strict";
const {$,escapeHtml,fmt,cls,finite,loadData,loadPortfolio,savePortfolio}=MR;
const [assets,tw,global]=await Promise.all([
  loadData("assets.json",window.__ASSET_SEED__||{assets:[]}),
  loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),
  loadData("market-snapshot.json",window.__MARKET_SNAPSHOT_SEED__||{items:[]})
]);
const quotes=new Map([...(tw.items||[]),...(global.items||[])].map(x=>[String(x.symbol||"").toUpperCase(),x]));
let rows=loadPortfolio();
const candidateMap=new Map();
const addCandidate=(row,priority=0)=>{
  const symbol=String(row?.symbol||"").toUpperCase().trim();if(!symbol)return;
  const old=candidateMap.get(symbol)||{};
  const merged={...old,...row,symbol,_priority:Math.max(priority,old._priority||0)};
  merged.name=String(merged.name||merged.short_name||merged.company_name||symbol).trim();
  merged.asset_class=merged.asset_class||old.asset_class||"stock";
  merged.exchange=merged.exchange||merged.market_label||old.exchange||"";
  candidateMap.set(symbol,merged);
};
for(const row of assets.assets||[])addCandidate(row,3);
for(const row of tw.items||[])if(["stock","etf"].includes(row.asset_class))addCandidate(row,4);
for(const row of global.items||[])if(row.asset_class||!/^[\^A-Z].*/.test(String(row.symbol||"")))addCandidate(row,1);
const candidates=[...candidateMap.values()];
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
function render(){let totalCost=0,totalValue=0,valuedRows=0;$("#portfolioRows").innerHTML=rows.map((h,i)=>{const q=quotes.get(String(h.symbol).toUpperCase()),price=finite(q?.price),qty=Number(h.quantity||0),cost=Number(h.cost||0),value=price==null?null:price*qty,pl=value==null?null:value-cost*qty;totalCost+=cost*qty;if(value!=null){totalValue+=value;valuedRows++}return`<tr><td><a href="asset.html?symbol=${encodeURIComponent(h.symbol)}"><b>${escapeHtml(h.symbol)}</b><br><small>${escapeHtml(h.name||"")}</small></a></td><td>${fmt(qty,4)}</td><td>${fmt(cost)}</td><td>${fmt(price)}</td><td>${fmt(value,0)}</td><td class="${cls(pl)}">${fmt(pl,0)}</td><td><button class="btn" data-del="${i}">刪除</button></td></tr>`}).join("")||'<tr><td colspan="7" class="empty">尚未加入標的</td></tr>';const complete=rows.length>0&&valuedRows===rows.length;$("#totalCost").textContent=rows.length?fmt(totalCost,0):"—";$("#totalValue").textContent=complete?fmt(totalValue,0):"—";$("#totalPL").textContent=complete?fmt(totalValue-totalCost,0):"—";$("#totalPL").className=complete?cls(totalValue-totalCost):"flat";document.querySelectorAll("[data-del]").forEach(b=>b.onclick=()=>{rows.splice(Number(b.dataset.del),1);savePortfolio(rows);render()})}
$("#addHolding").onclick=()=>{const symbol=symbolInput.value.trim().toUpperCase(),quantity=Number($("#holdingQty").value),cost=Number($("#holdingCost").value),candidate=candidateMap.get(symbol);if(!candidate){alert("找不到正式標的，請從搜尋選單選取股票或 ETF");symbolInput.focus();renderSuggestions();return}if(!Number.isFinite(quantity)||quantity<=0||!Number.isFinite(cost)){alert("請填入正確數量與平均成本");return}const existing=rows.find(row=>String(row.symbol).toUpperCase()===symbol);if(existing){const oldQty=Number(existing.quantity||0),newQty=oldQty+quantity;existing.cost=newQty?((oldQty*Number(existing.cost||0))+(quantity*cost))/newQty:cost;existing.quantity=newQty;existing.name=candidate.name||existing.name||symbol}else rows.push({symbol,name:candidate.name||symbol,quantity,cost});savePortfolio(rows);render();selectedSymbol="";["holdingSymbol","holdingName","holdingQty","holdingCost"].forEach(id=>$("#"+id).value="");closeSuggestions()};
$("#exportPortfolio").onclick=()=>{const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([JSON.stringify({version:2,items:rows},null,2)],{type:"application/json"}));a.download="market-radar-portfolio.json";a.click()};
$("#importPortfolio").onchange=async e=>{try{const js=JSON.parse(await e.target.files[0].text());rows=Array.isArray(js)?js:js.items;if(!Array.isArray(rows))throw Error("items");savePortfolio(rows);render()}catch(err){alert("匯入檔格式錯誤")}};
render();})();
