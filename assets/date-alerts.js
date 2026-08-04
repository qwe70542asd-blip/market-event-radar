(async()=>{
  "use strict";
  const {escapeHtml,loadData,formatTime}=MR;
  const panel=document.querySelector("#dateAlertPanel");
  const list=document.querySelector("#dateAlertList");
  const count=document.querySelector("#dateAlertCount");
  const updated=document.querySelector("#dateAlertUpdated");
  if(!panel||!list||!count)return;

  const dayKey=value=>{
    const parts=new Intl.DateTimeFormat("en-US",{
      timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"
    }).formatToParts(new Date(value));
    const map=Object.fromEntries(parts.map(part=>[part.type,part.value]));
    return `${map.year}-${map.month}-${map.day}`;
  };
  const payload=await loadData("events.json",window.__EVENT_SEED__||{events:[]});
  const today=dayKey(Date.now());
  const rows=(payload.events||[])
    .filter(event=>event.announced_at&&dayKey(event.announced_at)===today&&["new-date","date-changed"].includes(event.announcement_kind))
    .sort((a,b)=>Date.parse(b.announced_at)-Date.parse(a.announced_at));

  count.textContent=`${rows.length} 件`;
  updated.textContent=payload?.metadata?.updated_at?`最近掃描 ${formatTime(payload.metadata.updated_at)}`:"等待第一次掃描";
  if(!rows.length){
    list.innerHTML='<div class="date-alert-empty"><strong>今天尚無新公布的確切日期</strong><span>官方來源每 10 分鐘掃描；只有新日期或日期異動才會出現在這裡。</span></div>';
    return;
  }

  list.innerHTML=rows.slice(0,12).map(event=>{
    const changed=event.announcement_kind==="date-changed";
    const source=event.source_url
      ? `<a href="${escapeHtml(event.source_url)}" target="_blank" rel="noreferrer noopener">官方來源 ↗</a>`
      : `<span>${escapeHtml(event.source_name||"官方來源")}</span>`;
    return `<article class="date-alert-item ${changed?"changed":"new"}">
      <div class="date-alert-label">${changed?"日期異動":"今日新公布"}</div>
      <a class="date-alert-main" href="event.html?id=${encodeURIComponent(event.id)}">
        <strong>${escapeHtml(event.title)}</strong>
        <span>事件日期：${escapeHtml(formatTime(event.start))}</span>
        ${changed&&event.previous_start?`<small>原日期：${escapeHtml(formatTime(event.previous_start))}</small>`:""}
      </a>
      <div class="date-alert-meta"><span>確認 ${escapeHtml(formatTime(event.announced_at))}</span>${source}</div>
    </article>`;
  }).join("");
})();
