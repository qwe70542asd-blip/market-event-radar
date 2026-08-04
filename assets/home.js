(async()=>{
  "use strict";
  const {$,escapeHtml,fmt,pct,cls,formatTime,loadData,loadPortfolio,finite}=MR;
  const [assets,events,news,tw,chips,snapshot]=await Promise.all([
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]}),
    loadData("events.json",window.__EVENT_SEED__||{events:[]}),
    loadData("news.json",window.__NEWS_SEED__||{items:[]}),
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),
    loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{markets:{},items:{}}),
    loadData("market-snapshot.json",window.__MARKET_SNAPSHOT_SEED__||{items:[]})
  ]);
  const quotes=new Map([...(tw.items||[]),...(snapshot.items||[])].map(x=>[String(x.symbol).toUpperCase(),x]));
  const strip=v=>String(v||"").replace(/<[^>]*>/g," ").replace(/\s+/g," ").trim();
  const localKey=value=>{
    const d=value instanceof Date?value:new Date(value);
    if(Number.isNaN(+d))return"";
    const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(d);
    const m=Object.fromEntries(parts.map(x=>[x.type,x.value]));
    return `${m.year}-${m.month}-${m.day}`;
  };
  const eventGroup=e=>{
    const group=String(e.event_group||"").toLowerCase(),cat=String(e.category||e.type||"").toLowerCase(),type=String(e.event_type||"").toLowerCase();
    if(group==="dividend"||/dividend|ex-right|ex-div|distribution/.test(`${cat} ${type}`))return"dividend";
    if(group==="corporate"||/earnings|corporate|conference|shareholder|financial-report/.test(`${cat} ${type}`))return"company";
    return"major";
  };
  const uniqueEvents=rows=>{
    const map=new Map();
    for(const e of rows){
      const key=e.tracking_key||`${localKey(e.start)}|${e.symbol||""}|${strip(e.title).toLowerCase()}`;
      const old=map.get(key);
      if(!old||String(e.source_url||"").length>String(old.source_url||"").length)map.set(key,e);
    }
    return[...map.values()];
  };
  function setIndex(sym,p,c,r,t){const q=quotes.get(sym);$(p).textContent=fmt(q?.price);const el=$(c);el.textContent=pct(q?.change_percent);el.className=cls(q?.change_percent);$(r).textContent=q?`高 ${fmt(q.high)}／低 ${fmt(q.low)}`:"高低 —";$(t).textContent=q?.market_at||q?.quote_time||"等待行情"}
  setIndex("^TWII","#taiexPrice","#taiexChange","#taiexRange","#taiexTime");setIndex("^TWOII","#tpexIndexPrice","#tpexIndexChange","#tpexIndexRange","#tpexIndexTime");
  const marketRows=(snapshot.items||[]).filter(x=>!["BTCUSDT","ETHUSDT"].includes(x.symbol));
  $("#marketList").innerHTML=marketRows.length?marketRows.slice(0,10).map(x=>`<div class="market-row"><span><strong>${escapeHtml(x.name||x.symbol)}</strong><small>${escapeHtml(x.symbol)}</small></span><b>${fmt(x.price)}</b><em class="${cls(x.change_percent)}">${pct(x.change_percent)}</em></div>`).join(""):'<div class="empty">等待全球行情更新</div>';
  $("#marketUpdated").textContent=snapshot.metadata?.updated_at?formatTime(snapshot.metadata.updated_at):"等待資料";
  function renderPortfolio(){const rows=loadPortfolio();$("#portfolioCount").textContent=`${rows.length} 個標的`;$("#portfolioStatus").textContent=rows.length?"使用最新行情":"尚未設定";$("#portfolioStrip").innerHTML=rows.length?rows.map(h=>{const q=quotes.get(String(h.symbol).toUpperCase()),price=Number(q?.price),qty=Number(h.quantity||h.qty||0),cost=Number(h.cost||h.average_cost||0),pl=Number.isFinite(price)&&qty?(price-cost)*qty:null;return`<a class="portfolio-card" href="asset.html?symbol=${encodeURIComponent(h.symbol)}"><span class="symbol">${escapeHtml(h.symbol)}</span><small>${escapeHtml(h.name||"")}</small><strong>${fmt(price)}</strong><div class="${cls(pl)}">損益 ${fmt(pl,0)}</div></a>`}).join(""):'<div class="empty" style="min-width:100%">尚未加入投資標的，請到「我的組合」新增。</div>'}renderPortfolio();window.addEventListener("portfoliochange",renderPortfolio);

  const safeNews=(news.items||[]).filter(n=>n.url_valid!==false&&/^https?:\/\//i.test(String(n.url||""))&&!/<a\b/i.test(`${n.title||""} ${n.summary||""}`));
  const majorNews=safeNews.filter(n=>n.impact==="high"||n.topic==="material"||n.is_major).slice(0,6);
  const latest=majorNews[0]||safeNews[0];if(latest){$("#breakingLink").textContent=strip(latest.title);$("#breakingLink").href=latest.url}
  $("#homeNews").innerHTML=(majorNews.length?majorNews:safeNews.slice(0,6)).map(n=>`<a class="news-card" href="${escapeHtml(n.url)}" target="_blank" rel="noreferrer noopener"><div class="news-meta"><span>${escapeHtml(n.source||"市場消息")}</span><time>${escapeHtml(formatTime(n.published_at||n.date))}</time></div><div class="ai-badges"><span class="tag">${escapeHtml(n.ai_category||n.topic||"市場")}</span><span class="impact-badge ${escapeHtml(n.impact||"medium")}">${n.impact==="high"?"高影響":n.impact==="low"?"低影響":"中影響"}</span><span class="direction-badge">${escapeHtml(n.market_direction||"中性")}</span></div><h3>${escapeHtml(strip(n.title))}</h3><p>${escapeHtml(strip(n.ai_summary||n.summary||"").slice(0,150))}</p></a>`).join("")||'<div class="empty">等待重大資訊更新</div>';

  const todayKey=localKey(new Date()),todayEvents=uniqueEvents((events.events||[]).filter(e=>localKey(e.start)===todayKey));
  const majorToday=todayEvents.filter(e=>eventGroup(e)==="major").sort((a,b)=>(b.impact==="high")-(a.impact==="high"));
  const breadth=tw.breadth||{};const up=Number(breadth.up||0),down=Number(breadth.down||0);let tone="資料不足";
  if(up+down){const ratio=up/(up+down);tone=ratio>=.62?"偏多":ratio<=.38?"偏空":"震盪"}
  $("#marketTone").textContent=tone;$("#marketTone").className=tone==="偏多"?"up":tone==="偏空"?"down":"flat";
  $("#breadthSummary").textContent=up+down?`${up} 漲／${down} 跌`:"—";
  const markets=chips.markets||{},foreign=[markets.twse?.institutional?.foreign_net,markets.tpex?.institutional?.foreign_net].map(finite).filter(v=>v!=null);const foreignNet=foreign.length?foreign.reduce((a,b)=>a+b,0):null;
  $("#foreignDirection").textContent=foreignNet==null?"—":foreignNet>0?"買超":"賣超";$("#foreignDirection").className=cls(foreignNet);
  const margin=[markets.twse?.margin?.change,markets.tpex?.margin?.change].map(finite).filter(v=>v!=null);const marginNet=margin.length?margin.reduce((a,b)=>a+b,0):null;
  $("#marginDirection").textContent=marginNet==null?"—":`${marginNet>0?"增加":"減少"} ${fmt(Math.abs(marginNet),0)}`;$("#marginDirection").className=cls(marginNet);
  $("#todayFocusList").innerHTML=majorToday.length?majorToday.slice(0,6).map(e=>`<a class="today-focus-item" href="event.html?id=${encodeURIComponent(e.id)}"><span class="impact-dot ${escapeHtml(e.impact||"medium")}"></span><span><strong>${escapeHtml(strip(e.title))}</strong><small>${escapeHtml(formatTime(e.start))}</small></span></a>`).join(""):'<div class="empty">今天沒有已確認的重大事件</div>';
  $("#focusUpdated").textContent=events.metadata?.updated_at?formatTime(events.metadata.updated_at):"等待資料";

  let current=new Date(),focus="all";const cal=$("#calendarGrid"),dialog=$("#dayDialog");
  const filters=()=>({q:$("#eventSearch").value.trim().toLowerCase(),region:$("#eventRegion").value,type:$("#eventType").value,impact:$("#eventImpact").value});
  function relevant(e,f){const hay=`${e.title||""} ${e.description||e.summary||""} ${(e.assets||e.symbols||[]).join(" ")}`.toLowerCase(),group=eventGroup(e);const impactOk=f.impact==="all"||e.impact==="high"||(f.impact==="medium"&&["high","medium"].includes(e.impact));return(!f.q||hay.includes(f.q))&&(f.region==="all"||e.region===f.region)&&(f.type==="all"||group===f.type)&&impactOk&&(focus==="all"||(e.focus||e.category||e.type)===focus||(e.tags||[]).includes(focus))}
  function monthEvents(y,m){const f=filters();return uniqueEvents((events.events||[]).filter(e=>{const d=new Date(e.start);if(Number.isNaN(+d))return false;const parts=localKey(d).split("-").map(Number);return parts[0]===y&&parts[1]-1===m&&relevant(e,f)}))}
  const eventCard=e=>`<article class="event-detail"><div class="event-detail-top"><span class="tag">${escapeHtml(e.region||"GLOBAL")}</span><span class="impact-badge ${escapeHtml(e.impact||"medium")}">${e.impact==="high"?"高影響":e.impact==="low"?"低影響":"中影響"}</span></div><h3><a href="event.html?id=${encodeURIComponent(e.id)}">${escapeHtml(strip(e.title))}</a></h3><p>${escapeHtml(strip(e.description||e.summary||""))}</p><small>${escapeHtml(formatTime(e.start))} · ${escapeHtml(e.source_name||"")}</small></article>`;
  const dividendCard=e=>`<article class="dividend-detail"><div><strong>${escapeHtml(e.symbol||"")}</strong><span>${escapeHtml(e.asset_name||strip(e.title))}</span></div><div><b>${/除權/.test(e.title||"")?"除權息":"除息"}</b><span>${e.cash_dividend!=null?`現金 ${fmt(e.cash_dividend)} 元`:"金額依公告"}</span></div><a href="event.html?id=${encodeURIComponent(e.id)}">詳細資料 →</a></article>`;
  function openDay(date,rows){const groups={major:[],company:[],dividend:[]};for(const e of uniqueEvents(rows))groups[eventGroup(e)].push(e);$("#dayDialogTitle").textContent=`${date.toLocaleDateString("zh-TW")} 事件`;$("#dayDialogBody").innerHTML=`<div class="dialog-tabs"><button class="chip active" data-day-tab="major">重大事件 ${groups.major.length}</button><button class="chip" data-day-tab="company">公司資訊 ${groups.company.length}</button><button class="chip" data-day-tab="dividend">除權息 ${groups.dividend.length}</button></div><div class="day-tab-panel" data-day-panel="major">${groups.major.length?groups.major.map(eventCard).join(""):'<div class="empty">當日沒有重大事件</div>'}</div><div class="day-tab-panel" data-day-panel="company" hidden>${groups.company.length?groups.company.map(eventCard).join(""):'<div class="empty">當日沒有公司資訊</div>'}</div><div class="day-tab-panel" data-day-panel="dividend" hidden>${groups.dividend.length?groups.dividend.map(dividendCard).join(""):'<div class="empty">當日沒有除權息資訊</div>'}</div>`;document.querySelectorAll("[data-day-tab]").forEach(b=>b.onclick=()=>{document.querySelectorAll("[data-day-tab]").forEach(x=>x.classList.toggle("active",x===b));document.querySelectorAll("[data-day-panel]").forEach(x=>x.hidden=x.dataset.dayPanel!==b.dataset.dayTab)});dialog.showModal()}
  function renderCalendar(){const y=current.getFullYear(),m=current.getMonth(),first=new Date(y,m,1),start=new Date(y,m,1-first.getDay()),all=monthEvents(y,m);$("#calendarTitle").textContent=`${y} 年 ${m+1} 月`;$("#eventUpdated").textContent=events.metadata?.updated_at?formatTime(events.metadata.updated_at):"等待排程";cal.innerHTML="";for(let i=0;i<42;i++){const d=new Date(start);d.setDate(start.getDate()+i);const key=localKey(d),rows=all.filter(e=>localKey(e.start)===key),major=rows.filter(e=>eventGroup(e)==="major"),company=rows.filter(e=>eventGroup(e)==="company"),dividend=rows.filter(e=>eventGroup(e)==="dividend"),cell=document.createElement("div");cell.className=`calendar-day ${d.getMonth()!==m?"other":""} ${localKey(d)===todayKey?"today":""}`;const pills=[...major.slice(0,2).map(e=>`<span class="event-pill ${escapeHtml(e.impact||"")}">${escapeHtml(strip(e.title))}</span>`),company.length?`<span class="event-pill company-summary">公司資訊共 ${company.length} 件</span>`:"",dividend.length?`<span class="event-pill dividend-summary">除權息共 ${new Set(dividend.map(e=>e.symbol||e.id)).size} 家</span>`:""].filter(Boolean);cell.innerHTML=`<span class="day-num">${d.getDate()}</span>${pills.join("")}${rows.length&&!pills.length?`<span class="event-pill">共 ${rows.length} 件資訊</span>`:""}`;cell.onclick=()=>openDay(d,rows);cal.appendChild(cell)}}
  ["eventSearch","eventRegion","eventType","eventImpact"].forEach(id=>$("#"+id).addEventListener("input",renderCalendar));document.querySelectorAll("[data-focus]").forEach(b=>b.onclick=()=>{document.querySelectorAll("[data-focus]").forEach(x=>x.classList.remove("active"));b.classList.add("active");focus=b.dataset.focus;renderCalendar()});$("#prevMonth").onclick=()=>{current.setMonth(current.getMonth()-1);renderCalendar()};$("#nextMonth").onclick=()=>{current.setMonth(current.getMonth()+1);renderCalendar()};$("#todayMonth").onclick=()=>{current=new Date();renderCalendar()};$("#closeDayDialog").onclick=()=>dialog.close();renderCalendar();
})();
