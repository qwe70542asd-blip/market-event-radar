(()=>{
  "use strict";
  const {escapeHtml,loadData,formatTime}=MR;
  const list=document.querySelector("#dateAlertList"),count=document.querySelector("#dateAlertCount"),updated=document.querySelector("#dateAlertUpdated");
  if(!list||!count||!updated)return;
  const fallback=window.__EVENT_SEED__||{metadata:{status:"seed"},events:[]};
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
  const dayDistance=(a,b)=>Math.abs((Date.parse(`${a}T00:00:00+08:00`)-Date.parse(`${b}T00:00:00+08:00`))/86400000);
  const trustedAnnouncement=event=>{
    if(!event?.announced_at||dayKey(event.announced_at)!==today||!["new-date","date-changed"].includes(event.announcement_kind))return false;
    const origin=String(event.origin||"").toLowerCase(),tracking=String(event.tracking_key||"").toLowerCase();
    if(["bea","bls"].includes(origin)&&!tracking.match(/^(bea|bls)\|[^|]+\|(?:20\d{2}[-|]|[^|]+\|20\d{2}[-|])/))return false; // reject legacy recurring-series keys
    const next=eventDate(event);
    if(!next||next<today)return false; // newly discovered historical rows are backfill, not today's new dates
    if(event.announcement_kind==="new-date")return true;
    const previous=dayKey(event.previous_start);
    return !!previous&&previous>=today&&dayDistance(previous,next)<=183;
  };
  const render=payload=>{
    const rows=(payload?.events||[]).filter(trustedAnnouncement).sort((a,b)=>Date.parse(b.announced_at)-Date.parse(a.announced_at));
    updated.textContent=payload?.metadata?.updated_at?`最近掃描 ${formatTime(payload.metadata.updated_at)}`:"線上事件同步中・先顯示內建資料";
    count.textContent=`${rows.length} 件`;
    if(!rows.length){
      list.innerHTML='<div class="date-alert-empty"><strong>今日尚無可信的新公布日期</strong><span>只列出今天新確認的未來日期與真正改期；歷史回補或週期性同名事件不再計入。</span></div>';
      return;
    }
    const limit=window.matchMedia?.("(max-width: 720px)")?.matches?6:12;
    const visible=rows.slice(0,limit);
    list.innerHTML=visible.map(event=>{
      const changed=event.announcement_kind==="date-changed",date=eventDate(event),mode=calendarMode(event);
      return `<article class="date-alert-item ${changed?"changed":"new"}"><div class="date-alert-label">${changed?"日期異動":"今日新確認"}</div><a class="date-alert-main" href="event.html?id=${encodeURIComponent(event.id)}"><strong>${escapeHtml(event.title||"未命名事件")}</strong><span>新日期：${escapeHtml(date||formatTime(event.start))}</span>${changed&&event.previous_start?`<small>原日期：${escapeHtml(dayKey(event.previous_start)||formatTime(event.previous_start))}</small>`:""}</a><div class="date-alert-meta"><span>確認 ${escapeHtml(formatTime(event.announced_at))}</span><span class="date-alert-actions"><button type="button" data-calendar-jump data-calendar-mode="${mode}" data-calendar-date="${escapeHtml(date)}">在月曆查看</button>${event.source_url?`<a href="${escapeHtml(event.source_url)}" target="_blank" rel="noreferrer noopener">官方來源 ↗</a>`:""}</span></div></article>`;
    }).join("")+(rows.length>visible.length?`<div class="date-alert-more">另有 ${rows.length-visible.length} 件今日新公布日期，請使用月曆搜尋查看。</div>`:"");
  };
  list.addEventListener("click",event=>{
    const button=event.target.closest("[data-calendar-jump]");
    if(!button)return;
    event.preventDefault();
    window.dispatchEvent(new CustomEvent("market-radar:calendar-jump",{detail:{mode:button.dataset.calendarMode,date:button.dataset.calendarDate}}));
  });
  // Never leave this panel on a permanent loading placeholder.  Seed data is
  // rendered immediately; verified live data replaces it when available.
  render(fallback);
  const livePromise=window.__MR_EVENT_LIVE_PROMISE__||loadData("events.json",fallback);
  livePromise.then(render).catch(()=>render(fallback));
})();
