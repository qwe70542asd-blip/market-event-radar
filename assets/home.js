(async()=>{
  "use strict";
  const {$,escapeHtml,fmt,pct,cls,formatTime,loadData,loadNewsChannels,loadStockNews,loadPortfolio,finite}=MR;
  const [assets,events,news,stockNews,tw,chips,snapshot]=await Promise.all([
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]}),
    loadData("events.json",window.__EVENT_SEED__||{events:[]}),
    loadNewsChannels(),
    loadStockNews(),
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),
    loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{markets:{},items:{}}),
    loadData("market-snapshot.json",window.__MARKET_SNAPSHOT_SEED__||{items:[]})
  ]);

  const assetMap=new Map((assets.assets||[]).map(row=>[String(row.symbol||"").toUpperCase(),row]));
  const quotes=new Map([...(tw.items||[]),...(snapshot.items||[])].map(row=>[String(row.symbol||"").toUpperCase(),row]));
  const strip=value=>String(value||"").replace(/<[^>]*>/g," ").replace(/&nbsp;/gi," ").replace(/\s+/g," ").trim();
  const truncate=(value,max=180)=>{const text=strip(value);return text.length>max?`${text.slice(0,max).trim()}…`:text};
  const localKey=value=>{
    const date=value instanceof Date?value:new Date(value);
    if(Number.isNaN(+date))return"";
    const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(date);
    const map=Object.fromEntries(parts.map(part=>[part.type,part.value]));
    return `${map.year}-${map.month}-${map.day}`;
  };
  const eventDateKey=event=>{
    const exact=String(event?.local_date||event?.target_date||event?.ex_date||"").match(/^\d{4}-\d{2}-\d{2}/);
    return exact?exact[0]:localKey(event?.start);
  };
  const eventGroup=event=>{
    const group=String(event.event_group||"").toLowerCase();
    const category=String(event.category||event.type||"").toLowerCase();
    const type=String(event.event_type||"").toLowerCase();
    if(group==="dividend"||/dividend|ex-right|ex-div|distribution/.test(`${category} ${type}`))return"dividend";
    if(group==="corporate"||/earnings|corporate|conference|shareholder|financial-report|corporate-action|material/.test(`${category} ${type}`))return"company";
    return"major";
  };
  const eventIdentity=event=>{
    const day=eventDateKey(event),group=eventGroup(event),symbol=String(event.symbol||event.asset_id||"").toUpperCase();
    if(group==="dividend"){
      const kind=/除權/.test(event.title||"")?"ex-right":"ex-dividend";
      return `${day}|${group}|${symbol}|${kind}`;
    }
    const normalized=strip(event.title).toLowerCase().replace(/[（(][^）)]*(?:元|%)[^）)]*[）)]/g,"").replace(/[^0-9a-z\u4e00-\u9fff]+/gi,"").slice(0,150);
    return `${day}|${group}|${symbol}|${normalized}`;
  };
  const uniqueEvents=rows=>{
    const map=new Map();
    for(const event of rows){
      const key=eventIdentity(event),old=map.get(key);
      const score=row=>[row.source_url,row.source_name,row.description,row.market_effect,row.cash_dividend,row.payment_date].filter(Boolean).length;
      if(!old||score(event)>score(old))map.set(key,event);
    }
    return [...map.values()];
  };
  const impactLabel=impact=>impact==="high"?"高影響":impact==="low"?"低影響":"中影響";

  const LEADER_RE=/台積電|鴻海|聯發科|廣達|緯創|國巨|川湖|日月光|台達電|中華電|長榮|陽明|NVIDIA|輝達|Microsoft|微軟|Apple|蘋果|Amazon|亞馬遜|Meta|Google|Alphabet|AMD|Intel|Tesla|三星|SK\s*海力士|海力士|Sony|Toyota/i;
  const LEADING_SECTOR_RE=/AI\s*伺服器|人工智慧|半導體|晶圓代工|記憶體|HBM|封裝測試|散熱|PCB|電源供應|雲端|資料中心|金融|航運|能源|原物料|機器人/i;
  const EXECUTIVE_RE=/執行長|董事長|財務長|總經理|基金經理人|分析師|首席經濟學家|央行總裁|官員|法說會|投資人會議|發表會|開發者大會|展覽|論壇|供應鏈會議/i;
  const BUSINESS_RE=/財報|財測|展望|營收|獲利|EPS|訂單|資本支出|擴產|漲價|降價|新品|新產品|合作|併購|投資/i;
  const SYSTEMIC_RE=/FOMC|聯準會|央行|CPI|PCE|GDP|非農|JOLTS|PMI|升息|降息|關稅|制裁|戰爭|金融危機|熔斷|重大法規/i;
  const majorScore=item=>{
    const text=`${item.title||""} ${item.summary||""} ${item.ai_summary||""}`;
    let score=0;
    if(SYSTEMIC_RE.test(text))score+=42;
    if(LEADER_RE.test(text))score+=24;
    if(LEADING_SECTOR_RE.test(text))score+=18;
    if(EXECUTIVE_RE.test(text))score+=16;
    if(BUSINESS_RE.test(text))score+=14;
    if(["official-notices","company-disclosures","cna"].includes(item.source_id))score+=12;
    if((item.other_reports||[]).length)score+=Math.min(14,(item.other_reports||[]).length*5);
    if(item.impact==="high")score+=12; else if(item.impact==="medium")score+=5;
    const age=(Date.now()-Date.parse(item.published_at||item.date||0))/86400000;
    if(Number.isFinite(age)&&age<=1)score+=10;else if(Number.isFinite(age)&&age<=3)score+=6;
    return Math.max(score,Number(item.importance_score||0));
  };
  const verificationLabel=item=>item.source_id==="official-notices"||item.source_id==="company-disclosures"?"官方來源":(item.other_reports||[]).length?"多來源佐證":item.source_id==="cna"?"主要媒體":"單一來源";

  const marketRows=(snapshot.items||[]).filter(row=>!["BTCUSDT","ETHUSDT","NVDA","^TWOII"].includes(String(row.symbol||"").toUpperCase()));
  $("#marketList").innerHTML=marketRows.length?marketRows.slice(0,10).map(row=>`<div class="market-row"><span><strong>${escapeHtml(row.name||row.symbol)}</strong><small>${escapeHtml(row.symbol)}</small></span><b>${fmt(row.price)}${escapeHtml(row.display_suffix||"")}</b><em class="${cls(row.change_percent)}">${pct(row.change_percent)}</em></div>`).join(""):'<div class="empty">等待全球行情更新</div>';
  $("#marketUpdated").textContent=snapshot.metadata?.updated_at?formatTime(snapshot.metadata.updated_at):"等待資料";

  function renderPortfolioSummary(){
    const rows=loadPortfolio();
    let totalCost=0,valuedCost=0,totalValue=0,dayPL=0,valued=0,dayValued=0;
    const allocation=new Map();
    for(const holding of rows){
      const symbol=String(holding.symbol||"").toUpperCase(),quote=quotes.get(symbol),asset=assetMap.get(symbol)||{};
      const qty=finite(holding.quantity??holding.qty),cost=finite(holding.cost??holding.average_cost),price=finite(quote?.price),previous=finite(quote?.previous_close);
      if(qty!=null&&cost!=null)totalCost+=qty*cost;
      if(qty!=null&&price!=null){
        const value=qty*price;totalValue+=value;valued++;if(cost!=null)valuedCost+=qty*cost;
        const category=asset.asset_class==="etf"?"ETF":asset.asset_class==="stock"?"個股":"其他";
        allocation.set(category,(allocation.get(category)||0)+value);
        if(previous!=null){dayPL+=(price-previous)*qty;dayValued++}
      }
    }
    const cumulative=valued?totalValue-valuedCost:null,returnPct=cumulative!=null&&valuedCost?cumulative/valuedCost*100:null;
    const dayBase=dayValued?totalValue-dayPL:null,dayPct=dayBase?dayPL/dayBase*100:null;
    $("#portfolioTotalValue").textContent=valued?`NT$ ${fmt(totalValue,0)}`:"—";
    $("#portfolioTotalCost").textContent=rows.length?`NT$ ${fmt(totalCost,0)}`:"—";
    $("#portfolioTotalPL").textContent=cumulative==null?"—":`${cumulative>=0?"+":"-"}NT$ ${fmt(Math.abs(cumulative),0)}`;
    $("#portfolioTotalPL").className=cls(cumulative);
    $("#portfolioReturn").textContent=pct(returnPct);$("#portfolioReturn").className=cls(returnPct);
    $("#portfolioDayPL").textContent=dayValued?`${dayPL>=0?"+":"-"}NT$ ${fmt(Math.abs(dayPL),0)}`:"—";$("#portfolioDayPL").className=cls(dayPL);
    $("#portfolioDayReturn").textContent=dayValued?pct(dayPct):"—";$("#portfolioDayReturn").className=cls(dayPct);
    $("#portfolioStatus").textContent=!rows.length?"尚未設定":valued===rows.length?"行情完整":`暫估 ${valued}/${rows.length}`;
    const totalAllocated=[...allocation.values()].reduce((a,b)=>a+b,0);
    $("#portfolioAllocation").innerHTML=totalAllocated?`<div class="allocation-bar">${[...allocation.entries()].map(([name,value])=>`<span style="flex:${Math.max(value,1)}" title="${escapeHtml(name)} ${((value/totalAllocated)*100).toFixed(1)}%"></span>`).join("")}</div><div class="allocation-labels">${[...allocation.entries()].sort((a,b)=>b[1]-a[1]).map(([name,value])=>`<span><i></i>${escapeHtml(name)} <b>${((value/totalAllocated)*100).toFixed(1)}%</b></span>`).join("")}</div>`:'<div class="empty">尚未加入投資標的。</div>';
    $("#portfolioEstimateNote").textContent=rows.length&&valued<rows.length?`${rows.length-valued} 項資產尚未取得最新行情；總資產與損益為已取得行情部分的暫估值。`:"";
  }
  renderPortfolioSummary();window.addEventListener("portfoliochange",renderPortfolioSummary);

  const validNewsImage=item=>/^https?:\/\//i.test(String(item.image_url||""));

  const mediaItems=[...(news.items||[]),...(stockNews.items||[])];
  const safeNews=[];const seenNews=new Set();
  for(const item of mediaItems){
    if(item.source_id==="company-disclosures"||item.source_id==="official-notices")continue;
    const title=strip(item.title),key=strip(`${title}|${item.url||""}`).toLowerCase();
    if(!title||!/^https?:\/\//i.test(String(item.url||""))||seenNews.has(key))continue;
    seenNews.add(key);safeNews.push({...item,title,_majorScore:majorScore(item)});
  }
  safeNews.sort((a,b)=>b._majorScore-a._majorScore||Date.parse(b.published_at||0)-Date.parse(a.published_at||0));
  const majorNews=safeNews.filter(item=>item._majorScore>=45).slice(0,6);
  const latest=majorNews[0]||safeNews[0];
  if(latest){$("#breakingLink").textContent=strip(latest.title);$("#breakingLink").href=latest.url}
  $("#homeNews").innerHTML=(majorNews.length?majorNews:safeNews.slice(0,6)).map(item=>{const image=validNewsImage(item)?`<div class="home-news-thumb"><img src="${escapeHtml(item.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentElement.remove();this.closest('a')?.classList.add('no-image')"></div>`:"";return `<a class="news-card home-news-card${image?"":" no-image"}" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener">${image}<div class="news-meta"><span>${escapeHtml(item.ai_category||item.topic||"市場")}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><div class="ai-badges"><span class="impact-badge ${escapeHtml(item.impact||"medium")}">${impactLabel(item.impact)}</span><span class="verification-badge">${escapeHtml(verificationLabel(item))}</span></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(truncate(item.ai_summary||item.summary,100)||"查看完整事件內容。")}</p></a>`}).join("")||'<div class="empty">等待重大資訊更新</div>';

  const todayKey=localKey(new Date());
  const todayEvents=uniqueEvents((events.events||[]).filter(event=>eventDateKey(event)===todayKey));
  const majorToday=todayEvents.filter(event=>eventGroup(event)==="major").sort((a,b)=>Number(b.impact==="high")-Number(a.impact==="high"));
  const breadth=tw.breadth||{},up=Number(breadth.up||0),down=Number(breadth.down||0);
  let tone="資料不足";
  if(up+down){const ratio=up/(up+down);tone=ratio>=.62?"偏多":ratio<=.38?"偏空":"震盪"}
  $("#marketTone").textContent=tone;$("#marketTone").className=tone==="偏多"?"up":tone==="偏空"?"down":"flat";
  $("#breadthSummary").textContent=up+down?`${up} 漲／${down} 跌`:"—";
  const markets=chips.markets||{};
  const foreignNet=finite(markets.twse?.institutional?.foreign_net);
  $("#foreignDirection").textContent=foreignNet==null?"尚未公布":foreignNet>0?"買超":"賣超";$("#foreignDirection").className=cls(foreignNet);
  const volumeRatio=finite(tw.metadata?.volume_ratio_20d),totalTrade=finite(tw.metadata?.total_trade_value),avgTrade=finite(tw.metadata?.average_20d_trade_value);
  let volumeLabel="資料更新中",volumeNote="";
  if(volumeRatio!=null){volumeLabel=volumeRatio>=1.3?"明顯放量":volumeRatio>=1.1?"溫和放量":volumeRatio<.85?"量縮觀望":"量能正常";volumeNote=`近 20 日均量的 ${(volumeRatio*100).toFixed(0)}%`;}
  else if(totalTrade!=null){volumeLabel="等待歷史均量";volumeNote=`今日成交金額 ${fmt(totalTrade/100000000,0)} 億元`;}
  $("#volumeMomentum").textContent=volumeLabel;$("#volumeMomentumNote").textContent=volumeNote;
  $("#todayFocusList").innerHTML=majorToday.length?majorToday.slice(0,6).map(event=>`<a class="today-focus-item" href="event.html?id=${encodeURIComponent(event.id)}"><span class="impact-dot ${escapeHtml(event.impact||"medium")}"></span><span><strong>${escapeHtml(strip(event.title))}</strong><small>${escapeHtml(formatTime(event.start))}</small></span></a>`).join(""):'<div class="empty">今天沒有已確認的重大事件</div>';
  $("#focusUpdated").textContent=events.metadata?.updated_at?formatTime(events.metadata.updated_at):"等待資料";

  let current=new Date(),focus="all";
  const calendar=$("#calendarGrid"),dialog=$("#dayDialog");
  const filters=()=>({q:$("#eventSearch").value.trim().toLowerCase(),region:$("#eventRegion").value,type:$("#eventType").value,impact:$("#eventImpact").value});
  function relevant(event,filter){
    const hay=`${event.title||""} ${event.description||event.summary||""} ${(event.assets||event.symbols||[]).join(" ")}`.toLowerCase();
    const group=eventGroup(event);
    const impactOk=filter.impact==="all"||event.impact==="high"||(filter.impact==="medium"&&["high","medium"].includes(event.impact));
    return (!filter.q||hay.includes(filter.q))&&(filter.region==="all"||event.region===filter.region)&&(filter.type==="all"||group===filter.type)&&impactOk&&(focus==="all"||(event.focus||event.category||event.type)===focus||(event.tags||[]).includes(focus));
  }
  function monthEvents(year,month){
    const filter=filters();
    return uniqueEvents((events.events||[]).filter(event=>{
      const parts=eventDateKey(event).split("-").map(Number);
      return parts[0]===year&&parts[1]-1===month&&relevant(event,filter);
    }));
  }
  function factRows(event){
    const text=strip(event.description||event.summary||"");
    const facts=[];
    const add=(label,value)=>{if(value&&!facts.some(row=>row.label===label))facts.push({label,value})};
    add("股票代碼",event.symbol||event.asset_id);
    add("每股金額",finite(event.cash_dividend)!=null?`${fmt(event.cash_dividend,4)} 元`:null);
    add("發放日期",event.payment_date||event.pay_date);
    const shares=text.match(/(?:發行(?:新股|股數|總股數)|認購股數)[^0-9]{0,15}([0-9][0-9,]*)\s*股/);
    const amount=text.match(/(?:募集資金|發行總額|交易金額|金額)[^0-9]{0,15}([0-9][0-9,.]*(?:億|萬)?元)/);
    const purpose=text.match(/(?:資金用途|用途)[：:]?\s*([^。；;]{4,80})/);
    add("發行股數",shares?.[1]?`${shares[1]} 股`:null);
    add("金額",amount?.[1]);
    add("用途",purpose?.[1]);
    return facts.slice(0,6);
  }
  const relatedNewsHtml=event=>{
    const related=MR.relatedNews(event,safeNews,{limit:3,windowDays:3});
    if(!related.length)return "";
    return `<div class="event-related-news"><strong>相關新聞</strong>${related.map(item=>`<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener"><span>${escapeHtml(item.source||"市場消息")}</span><b>${escapeHtml(truncate(item.title,76))}</b><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></a>`).join("")}</div>`;
  };
  const eventCard=event=>{
    const group=eventGroup(event),description=strip(event.description||event.summary||""),facts=factRows(event);
    const source=event.source_url?`<a href="${escapeHtml(event.source_url)}" target="_blank" rel="noreferrer noopener">官方來源 ↗</a>`:`<span>${escapeHtml(event.source_name||"官方來源")}</span>`;
    return `<article class="event-detail ${group}"><div class="event-detail-top"><div><span class="tag">${escapeHtml(event.region||"GLOBAL")}</span><span class="event-kind">${group==="company"?"公司資訊":"重大事件"}</span></div><span class="impact-badge ${escapeHtml(event.impact||"medium")}">${impactLabel(event.impact)}</span></div><h3><a href="event.html?id=${encodeURIComponent(event.id)}">${escapeHtml(strip(event.title))}</a></h3>${description?`<p>${escapeHtml(truncate(description,220))}</p>`:""}${facts.length?`<dl class="event-fact-grid">${facts.map(row=>`<div><dt>${escapeHtml(row.label)}</dt><dd>${escapeHtml(row.value)}</dd></div>`).join("")}</dl>`:""}<div class="event-detail-foot"><time>${escapeHtml(formatTime(event.start))}</time>${source}</div>${relatedNewsHtml(event)}${description.length>220?`<details class="event-full"><summary>查看完整說明</summary><p>${escapeHtml(description)}</p></details>`:""}</article>`;
  };
  const dividendTable=rows=>{
    if(!rows.length)return '<div class="empty">當日沒有除權息資訊</div>';
    return `<div class="table-wrap dividend-table-wrap"><table class="dividend-table"><thead><tr><th>標的</th><th>類型</th><th>每股金額</th><th>發放日期</th><th>來源</th></tr></thead><tbody>${rows.map(event=>`<tr><td><a href="asset.html?symbol=${encodeURIComponent(event.symbol||"")}"><b>${escapeHtml(event.symbol||"—")}</b><br><small>${escapeHtml(event.name||strip(event.title).replace(/^\S+\s*/,""))}</small></a></td><td>${/除權/.test(event.title||"")?"除權":"除息"}</td><td>${finite(event.cash_dividend)!=null?`${fmt(event.cash_dividend,4)} 元`:"—"}</td><td>${escapeHtml(event.payment_date||event.pay_date||"—")}</td><td>${event.source_url?`<a href="${escapeHtml(event.source_url)}" target="_blank" rel="noreferrer noopener">官方公告 ↗</a>`:escapeHtml(event.source_name||"—")}</td></tr>`).join("")}</tbody></table></div>`;
  };
  function openDay(date,rows){
    const groups={major:[],company:[],dividend:[]};
    for(const event of uniqueEvents(rows))groups[eventGroup(event)].push(event);
    groups.major.sort((a,b)=>Number(b.impact==="high")-Number(a.impact==="high")||Date.parse(a.start)-Date.parse(b.start));
    groups.company.sort((a,b)=>Date.parse(a.start)-Date.parse(b.start));
    groups.dividend.sort((a,b)=>String(a.symbol||"").localeCompare(String(b.symbol||""),"zh-Hant"));
    $("#dayDialogTitle").textContent=`${date.toLocaleDateString("zh-TW")} 事件`;
    $("#dayDialogBody").innerHTML=`<div class="day-summary"><div><strong>${groups.major.length}</strong><span>重大事件</span></div><div><strong>${groups.company.length}</strong><span>公司資訊</span></div><div><strong>${new Set(groups.dividend.map(event=>event.symbol||event.id)).size}</strong><span>除權息家數</span></div></div><div class="dialog-tabs"><button class="chip active" data-day-tab="major">重大事件 <b>${groups.major.length}</b></button><button class="chip" data-day-tab="company">公司資訊 <b>${groups.company.length}</b></button><button class="chip" data-day-tab="dividend">除權息 <b>${groups.dividend.length}</b></button></div><div class="day-tab-panel" data-day-panel="major">${groups.major.length?groups.major.map(eventCard).join(""):'<div class="empty">當日沒有重大事件</div>'}</div><div class="day-tab-panel" data-day-panel="company" hidden>${groups.company.length?groups.company.map(eventCard).join(""):'<div class="empty">當日沒有公司資訊</div>'}</div><div class="day-tab-panel" data-day-panel="dividend" hidden>${dividendTable(groups.dividend)}</div>`;
    document.querySelectorAll("[data-day-tab]").forEach(button=>button.onclick=()=>{
      document.querySelectorAll("[data-day-tab]").forEach(item=>item.classList.toggle("active",item===button));
      document.querySelectorAll("[data-day-panel]").forEach(panel=>panel.hidden=panel.dataset.dayPanel!==button.dataset.dayTab);
    });
    dialog.showModal();
  }
  function renderCalendar(){
    const year=current.getFullYear(),month=current.getMonth(),first=new Date(year,month,1),start=new Date(year,month,1-first.getDay()),all=monthEvents(year,month);
    $("#calendarTitle").textContent=`${year} 年 ${month+1} 月`;
    $("#eventUpdated").textContent=events.metadata?.updated_at?formatTime(events.metadata.updated_at):"等待排程";
    calendar.innerHTML="";
    for(let index=0;index<42;index++){
      const date=new Date(start);date.setDate(start.getDate()+index);
      const key=localKey(date),rows=all.filter(event=>eventDateKey(event)===key);
      const major=rows.filter(event=>eventGroup(event)==="major"),company=rows.filter(event=>eventGroup(event)==="company"),dividend=rows.filter(event=>eventGroup(event)==="dividend");
      const cell=document.createElement("div");
      cell.className=`calendar-day ${date.getMonth()!==month?"other":""} ${localKey(date)===todayKey?"today":""}`;
      const dividendCount=new Set(dividend.map(event=>event.symbol||event.id)).size;
      const pills=[];
      if(major.length){
        pills.push(`<span class="event-pill ${escapeHtml(major[0].impact||"")}">${escapeHtml(truncate(major[0].title,38))}</span>`);
        if(major.length>1)pills.push(`<span class="event-pill major-summary">另有重大事件 ${major.length-1} 件</span>`);
      }
      if(company.length)pills.push(`<span class="event-pill company-summary">公司資訊 ${company.length} 件</span>`);
      if(dividendCount)pills.push(`<span class="event-pill dividend-summary">除權息 ${dividendCount} 家</span>`);
      cell.innerHTML=`<span class="day-num">${date.getDate()}</span>${pills.join("")}${rows.length&&!pills.length?`<span class="event-pill">共 ${rows.length} 件資訊</span>`:""}`;
      cell.onclick=()=>openDay(date,rows);
      calendar.appendChild(cell);
    }
  }
  ["eventSearch","eventRegion","eventType","eventImpact"].forEach(id=>$("#"+id).addEventListener("input",renderCalendar));
  document.querySelectorAll("[data-focus]").forEach(button=>button.onclick=()=>{document.querySelectorAll("[data-focus]").forEach(item=>item.classList.remove("active"));button.classList.add("active");focus=button.dataset.focus;renderCalendar()});
  $("#prevMonth").onclick=()=>{current.setMonth(current.getMonth()-1);renderCalendar()};
  $("#nextMonth").onclick=()=>{current.setMonth(current.getMonth()+1);renderCalendar()};
  $("#todayMonth").onclick=()=>{current=new Date();renderCalendar()};
  $("#closeDayDialog").onclick=()=>dialog.close();
  renderCalendar();
})();
