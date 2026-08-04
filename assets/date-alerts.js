(async()=>{
  "use strict";
  const {escapeHtml,loadData,formatTime}=MR;
  const list=document.querySelector("#dateAlertList"),count=document.querySelector("#dateAlertCount"),updated=document.querySelector("#dateAlertUpdated");
  if(!list||!count)return;
  const [payload,news]=await Promise.all([loadData("events.json",window.__EVENT_SEED__||{events:[]}),loadData("news.json",window.__NEWS_SEED__||{items:[]})]);
  const dayKey=value=>{const p=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(new Date(value)),m=Object.fromEntries(p.map(x=>[x.type,x.value]));return`${m.year}-${m.month}-${m.day}`};
  const today=dayKey(Date.now());
  const rows=(payload.events||[]).filter(e=>e.announced_at&&dayKey(e.announced_at)===today&&["new-date","date-changed"].includes(e.announcement_kind)).sort((a,b)=>Date.parse(b.announced_at)-Date.parse(a.announced_at));
  updated.textContent=payload?.metadata?.updated_at?`最近掃描 ${formatTime(payload.metadata.updated_at)}`:"等待第一次掃描";
  if(rows.length){count.textContent=`${rows.length} 件`;list.innerHTML=rows.slice(0,10).map(e=>`<article class="date-alert-item ${e.announcement_kind==="date-changed"?"changed":"new"}"><div class="date-alert-label">${e.announcement_kind==="date-changed"?"日期異動":"今日新確認"}</div><a class="date-alert-main" href="event.html?id=${encodeURIComponent(e.id)}"><strong>${escapeHtml(e.title)}</strong><span>事件日期：${escapeHtml(formatTime(e.start))}</span>${e.previous_start?`<small>原日期：${escapeHtml(formatTime(e.previous_start))}</small>`:""}</a><div class="date-alert-meta"><span>確認 ${escapeHtml(formatTime(e.announced_at))}</span>${e.source_url?`<a href="${escapeHtml(e.source_url)}" target="_blank" rel="noreferrer noopener">官方來源 ↗</a>`:""}</div></article>`).join("");return}
  const major=(news.items||[]).filter(n=>n.url_valid!==false&&(n.impact==="high"||n.topic==="material"||n.is_major)&&/^https?:\/\//i.test(String(n.url||""))).slice(0,5);
  const upcoming=(payload.events||[]).filter(e=>e.impact==="high"&&Date.parse(e.start)>=Date.now()-86400000).sort((a,b)=>Date.parse(a.start)-Date.parse(b.start)).slice(0,5);
  const fallbacks=major.length?major.map(n=>({kind:"重大資訊",title:n.title,time:n.published_at||n.date,url:n.url,summary:n.ai_summary||n.summary})):upcoming.map(e=>({kind:"近期重大事件",title:e.title,time:e.start,url:`event.html?id=${encodeURIComponent(e.id)}`,summary:e.description||e.summary}));
  count.textContent=fallbacks.length?`${fallbacks.length} 則`:"0 件";
  list.innerHTML=fallbacks.length?fallbacks.map(x=>`<article class="date-alert-item latest"><div class="date-alert-label">${escapeHtml(x.kind)}</div><a class="date-alert-main" href="${escapeHtml(x.url)}" ${/^https?:/.test(x.url)?'target="_blank" rel="noreferrer noopener"':""}><strong>${escapeHtml(String(x.title||"").replace(/<[^>]*>/g," "))}</strong><span>${escapeHtml(formatTime(x.time))}</span><small>${escapeHtml(String(x.summary||"").replace(/<[^>]*>/g," ").slice(0,140))}</small></a></article>`).join(""):'<div class="date-alert-empty"><strong>目前沒有新日期或重大資訊</strong><span>官方來源仍會每 10 分鐘掃描，出現新日期或改期時會自動更新。</span></div>';
})();
