(async()=>{
  "use strict";
  const {$,escapeHtml,formatTime,loadData,loadNewsChannels,stripHtml}=MR;
  const [events,news]=await Promise.all([
    loadData("events.json",window.__EVENT_SEED__||{events:[]}),
    loadNewsChannels()
  ]);
  const id=new URLSearchParams(location.search).get("id"),event=(events.events||[]).find(row=>row.id===id);
  if(!event){$("#eventDetail").innerHTML='<div class="empty">找不到事件，可能尚未由官方排程更新。</div>';return}
  document.title=`${event.title}｜市場事件雷達`;
  const type=event.event_type||event.category||event.type||"event",description=stripHtml(event.description||event.summary||"尚無說明");
  const source=/^https?:\/\//i.test(String(event.source_url||""))?`<p><a class="btn" href="${escapeHtml(event.source_url)}" target="_blank" rel="noreferrer noopener">查看官方來源 →</a></p>`:"";
  const related=MR.relatedNews(event,(news.items||[]).filter(item=>item.url_valid!==false&&/^https?:\/\//i.test(String(item.url||""))),{limit:5,windowDays:3});
  const relatedHtml=related.length?`<section class="event-page-related"><h2>相關新聞</h2><div class="related-news-grid">${related.map(item=>`<a class="related-news-card" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener"><div><span class="tag">${escapeHtml(item.ai_category||item.topic||"市場")}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(stripHtml(item.ai_summary||item.summary||"").slice(0,180))}</p><small>${escapeHtml(item.source||"市場消息")} · 閱讀原文 →</small></a>`).join("")}</div></section>`:`<section class="event-page-related"><h2>相關新聞</h2><div class="empty">事件前後三天內尚未找到可確認的相關文章。</div></section>`;
  $("#eventDetail").innerHTML=`<p class="eyebrow">${escapeHtml(event.region||"GLOBAL")} · ${escapeHtml(type)}</p><h1>${escapeHtml(event.title)}</h1><div class="stat-grid"><article class="stat"><small>事件時間</small><strong>${escapeHtml(formatTime(event.start))}</strong></article><article class="stat"><small>影響程度</small><strong>${escapeHtml(event.impact||"—")}</strong></article><article class="stat"><small>公布確認</small><strong>${event.announced_at?escapeHtml(formatTime(event.announced_at)):"既有日期"}</strong></article><article class="stat"><small>日期狀態</small><strong>${escapeHtml(event.announcement_kind==="date-changed"?"日期異動":event.announcement_kind==="new-date"?"新確認日期":"既有日期")}</strong></article></div><h2>事件說明</h2><p>${escapeHtml(description)}</p>${event.market_effect?`<h2>可能影響</h2><p>${escapeHtml(event.market_effect)}</p>`:""}${event.previous_start?`<p class="notice">原日期：${escapeHtml(formatTime(event.previous_start))}</p>`:""}${source}${relatedHtml}`;
})();
