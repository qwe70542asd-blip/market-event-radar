(async()=>{
  "use strict";
  const {escapeHtml,loadData,formatTime}=MR;
  const list=document.querySelector("#dateAlertList"),count=document.querySelector("#dateAlertCount"),updated=document.querySelector("#dateAlertUpdated");
  if(!list||!count||!updated)return;
  const payload=await loadData("events.json",window.__EVENT_SEED__||{events:[]});
  const dayKey=value=>{
    const date=new Date(value);
    if(Number.isNaN(+date))return"";
    const parts=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(date);
    const map=Object.fromEntries(parts.map(part=>[part.type,part.value]));
    return`${map.year}-${map.month}-${map.day}`;
  };
  const eventDate=event=>String(event.local_date||event.target_date||event.ex_date||"").match(/^\d{4}-\d{2}-\d{2}/)?.[0]||dayKey(event.start);
  const calendarMode=event=>{
    const group=String(event.event_group||"").toLowerCase(),type=String(event.category||event.event_type||"").toLowerCase();
    return group==="dividend"||/dividend|ex-right|ex-div|distribution/.test(type)?"dividend":"market";
  };
  const today=dayKey(Date.now());
  const rows=(payload.events||[]).filter(event=>event.announced_at&&dayKey(event.announced_at)===today&&["new-date","date-changed"].includes(event.announcement_kind)).sort((a,b)=>Date.parse(b.announced_at)-Date.parse(a.announced_at));
  updated.textContent=payload?.metadata?.updated_at?`最近掃描 ${formatTime(payload.metadata.updated_at)}`:"等待第一次官方事件掃描";
  count.textContent=`${rows.length} 件`;
  if(!rows.length){
    list.innerHTML='<div class="date-alert-empty"><strong>今日尚無新公布日期</strong><span>官方來源仍會定期掃描；新確認日期或改期時會自動列出新舊日期。</span></div>';
    return;
  }
  const visible=rows.slice(0,12);
  list.innerHTML=visible.map(event=>{
    const changed=event.announcement_kind==="date-changed",date=eventDate(event),mode=calendarMode(event);
    return `<article class="date-alert-item ${changed?"changed":"new"}"><div class="date-alert-label">${changed?"日期異動":"今日新確認"}</div><a class="date-alert-main" href="event.html?id=${encodeURIComponent(event.id)}"><strong>${escapeHtml(event.title||"未命名事件")}</strong><span>新日期：${escapeHtml(date||formatTime(event.start))}</span>${changed&&event.previous_start?`<small>原日期：${escapeHtml(dayKey(event.previous_start)||formatTime(event.previous_start))}</small>`:""}</a><div class="date-alert-meta"><span>確認 ${escapeHtml(formatTime(event.announced_at))}</span><span class="date-alert-actions"><button type="button" data-calendar-jump data-calendar-mode="${mode}" data-calendar-date="${escapeHtml(date)}">在月曆查看</button>${event.source_url?`<a href="${escapeHtml(event.source_url)}" target="_blank" rel="noreferrer noopener">官方來源 ↗</a>`:""}</span></div></article>`;
  }).join("")+(rows.length>visible.length?`<div class="date-alert-more">另有 ${rows.length-visible.length} 件今日新公布日期，請使用月曆搜尋查看。</div>`:"");
  list.addEventListener("click",event=>{
    const button=event.target.closest("[data-calendar-jump]");
    if(!button)return;
    event.preventDefault();
    window.dispatchEvent(new CustomEvent("market-radar:calendar-jump",{detail:{mode:button.dataset.calendarMode,date:button.dataset.calendarDate}}));
  });
})();
