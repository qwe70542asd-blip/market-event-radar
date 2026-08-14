(async()=>{
  "use strict";
  const {$,escapeHtml,formatTime,loadData,stripHtml,renderNewsThumb,safeExternalHref}=MR;
  const id=new URLSearchParams(location.search).get("id"),fallback=window.__EVENT_SEED__||{events:[]};
  let event=(fallback.events||[]).find(row=>row.id===id)||null,newsPayload={items:[]};
  const impactLabel=value=>value==="high"?"高影響":value==="low"?"低影響":"中度影響";
  const cleanSentence=value=>String(value||"").replace(/^\s*\d{1,2}[.、]\s*/,"").trim();
  const FACT_PATTERNS=[
    ["董事會決議日",/董事會(?:或經董事會)?決議日期[:：]?\s*([^\s。；]+)/],["審計委員會通過日",/審計委員會通過日期[:：]?\s*([^\s。；]+)/],["財報期間",/財務報告或年度自結財務資訊期間[^:：]*[:：]?\s*([^。；]+)/],["累計營業收入",/累計營業收入[^:：]*[:：]?\s*([\d,.-]+)/],["累計營業毛利",/累計營業毛利[^:：]*[:：]?\s*([\d,.-]+)/],["累計營業利益",/累計營業利益[^:：]*[:：]?\s*([\d,.-]+)/],["累計稅前淨利",/累計稅前淨利[^:：]*[:：]?\s*([\d,.-]+)/],["累計稅後淨利",/累計稅後淨利[^:：]*[:：]?\s*([\d,.-]+)/],["基本每股盈餘",/基本每股盈餘[^:：]*[:：]?\s*([\d,.-]+)/],["現金股利",/(?:現金股利|每單位配發金額)[^:：]*[:：]?\s*([\d,.]+(?:\s*元)?)/],["股票股利",/股票股利[^:：]*[:：]?\s*([\d,.]+)/],["股息發放日",/(?:現金股利發放日|收益分配發放日|發放日)[^:：]*[:：]?\s*([^\s。；]+)/],
  ];
  function renderRelated(){
    const mount=$("#eventRelatedMount");if(!mount||!event)return;
    const rows=MR.relatedNews(event,(newsPayload.items||[]).filter(item=>item.url_valid!==false&&/^https:\/\//i.test(String(item.url||""))),{limit:6,windowDays:3});
    mount.innerHTML=rows.length?`<section class="event-page-related event-content-card"><h2>相關新聞</h2><div class="related-news-grid">${rows.map((item,index)=>`<a class="related-news-card" href="${escapeHtml(safeExternalHref(item.url)||"#")}" target="_blank" rel="noreferrer noopener">${renderNewsThumb(item,"related",{alt:item.title,eager:index<2})}<div><span class="tag">${escapeHtml(item.ai_category||item.topic||"市場")}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(stripHtml(item.ai_summary||item.summary||"").slice(0,180))}</p><small>${escapeHtml(item.source||"市場消息")} · 閱讀原文 →</small></a>`).join("")}</div></section>`:`<section class="event-page-related event-content-card"><h2>相關新聞</h2><div class="empty">新聞來源同步中；事件內容不會等待新聞載入。</div></section>`;
  }
  function renderEvent(){
    if(!event)return;
    document.title=`${event.title}｜市場事件雷達`;
    const dateStatus=event.announcement_kind==="date-changed"?"日期異動":event.announcement_kind==="new-date"?"新確認日期":"已確認日期",rawDescription=stripHtml(event.description||event.summary||"尚無說明");
    const numbered=rawDescription.split(/(?=\s*\d{1,2}[.、]\s*)/).map(cleanSentence).filter(Boolean),paragraphs=(numbered.length>1?numbered:rawDescription.split(/(?:。|；|;)\s*/)).map(cleanSentence).filter(Boolean),facts=[];const addFact=(label,value)=>{if(value&&!facts.some(row=>row.label===label))facts.push({label,value:String(value).trim()})};
    addFact("股票代碼",event.symbol||String(event.asset_id||"").replace(/^TW:/,""));addFact("公司／標的",event.asset_name||event.name);addFact("統計期間",event.period||event.fiscal_period);addFact("現金股利",event.cash_dividend!=null?`${event.cash_dividend} 元`:null);addFact("股票股利",event.stock_dividend??event.stock_dividend_ratio);addFact("發放日期",event.payment_date||event.pay_date);for(const [label,pattern] of FACT_PATTERNS){const match=rawDescription.match(pattern);addFact(label,match?.[1])}
    const sourceUrl=/^https:\/\//i.test(String(event.source_url||""))?String(event.source_url):"",rawSource=/openapi|exchangeReport|\.json(?:\?|$)|\.txt(?:\?|$)|ajax_/i.test(sourceUrl),sourceActions=sourceUrl&&!rawSource?`<a class="btn" href="${escapeHtml(safeExternalHref(sourceUrl)||"#")}" target="_blank" rel="noreferrer noopener">查看官方網頁 →</a>`:rawSource?'<span class="source-warning">官方原始 API／文字檔已整理成本站內容，不會自動下載。</span>':"";
    $("#eventDetail").classList.add("event-detail-page");
    $("#eventDetail").innerHTML=`<section class="event-hero"><p class="eyebrow">${escapeHtml(event.region||"GLOBAL")} · ${escapeHtml(event.event_type||event.category||"event")}</p><h1>${escapeHtml(event.title)}</h1></section><section class="event-meta-grid"><article class="event-meta-card"><small>事件時間</small><strong>${escapeHtml(formatTime(event.start))}</strong></article><article class="event-meta-card"><small>影響程度</small><strong class="impact-text ${escapeHtml(event.impact||"medium")}">${escapeHtml(impactLabel(event.impact))}</strong></article><article class="event-meta-card"><small>公布確認</small><strong>${event.announced_at?escapeHtml(formatTime(event.announced_at)):"既有官方日期"}</strong></article><article class="event-meta-card"><small>日期狀態</small><strong>${escapeHtml(dateStatus)}</strong></article></section>${facts.length?`<section class="event-content-card"><h2>關鍵資訊</h2><div class="event-facts-grid">${facts.slice(0,12).map(row=>`<article class="event-fact-card"><small>${escapeHtml(row.label)}</small><strong>${escapeHtml(row.value)}</strong></article>`).join("")}</div></section>`:""}<section class="event-content-card"><h2>事件說明</h2><div class="event-description-list">${paragraphs.slice(0,12).map(text=>`<p>${escapeHtml(text)}${/[。！？]$/.test(text)?"":"。"}</p>`).join("")}</div></section>${event.market_effect?`<section class="event-content-card"><h2>可能影響</h2><p>${escapeHtml(stripHtml(event.market_effect))}</p></section>`:""}${event.previous_start?`<p class="notice">原日期：${escapeHtml(formatTime(event.previous_start))}</p>`:""}<section class="event-content-card"><h2>資料來源</h2><p>${escapeHtml(event.source_name||"官方公告")}</p><div class="event-source-actions">${sourceActions}</div>${rawDescription?`<details class="event-raw-details"><summary>查看原始公告文字</summary><pre>${escapeHtml(rawDescription)}</pre></details>`:""}</section><div id="eventRelatedMount"></div>`;
    renderRelated();
  }
  if(event)renderEvent();else $("#eventDetail").innerHTML='<div class="empty">事件資料同步中…</div>';
  const eventPromise=loadData("events.json",fallback).catch(()=>fallback),newsStream=MR.startNewsChannels({onUpdate:fresh=>{newsPayload=fresh;renderRelated()}});
  newsPayload=newsStream.initial;renderRelated();
  const live=await eventPromise,found=(live.events||[]).find(row=>row.id===id);if(found){event=found;renderEvent()}else if(!event)$("#eventDetail").innerHTML='<div class="empty">找不到事件，可能尚未由官方排程更新。</div>';
  newsStream.done.then(fresh=>{newsPayload=fresh;renderRelated()}).catch(()=>{});
})();
