(async()=>{
  "use strict";
  const {$,escapeHtml,formatTime,loadData}=MR,p=await loadData("events.json",window.__EVENT_SEED__||{events:[]}),id=new URLSearchParams(location.search).get("id"),e=(p.events||[]).find(x=>x.id===id);
  if(!e){$("#eventDetail").innerHTML='<div class="empty">找不到事件，可能尚未由官方排程更新。</div>';return}
  document.title=`${e.title}｜市場事件雷達`;
  const type=e.event_type||e.category||e.type||"event",description=e.description||e.summary||"尚無說明";
  const source=/^https?:\/\//i.test(String(e.source_url||""))?`<p><a class="btn" href="${escapeHtml(e.source_url)}" target="_blank" rel="noreferrer noopener">查看官方來源 →</a></p>`:"";
  $("#eventDetail").innerHTML=`<p class="eyebrow">${escapeHtml(e.region||"GLOBAL")} · ${escapeHtml(type)}</p><h1>${escapeHtml(e.title)}</h1><div class="stat-grid"><article class="stat"><small>事件時間</small><strong>${escapeHtml(formatTime(e.start))}</strong></article><article class="stat"><small>影響程度</small><strong>${escapeHtml(e.impact||"—")}</strong></article><article class="stat"><small>公布確認</small><strong>${e.announced_at?escapeHtml(formatTime(e.announced_at)):"既有日期"}</strong></article><article class="stat"><small>日期狀態</small><strong>${escapeHtml(e.announcement_kind==="date-changed"?"日期異動":e.announcement_kind==="new-date"?"新確認日期":"既有日期")}</strong></article></div><h2>事件說明</h2><p>${escapeHtml(description)}</p>${e.market_effect?`<h2>可能影響</h2><p>${escapeHtml(e.market_effect)}</p>`:""}${e.previous_start?`<p class="notice">原日期：${escapeHtml(formatTime(e.previous_start))}</p>`:""}${source}`;
})();
