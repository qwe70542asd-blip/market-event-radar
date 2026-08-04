(async()=>{
  "use strict";
  const {$,escapeHtml,formatTime,stripHtml}=MR;
  const payload=await MR.loadNewsChannels();
  let topic="all",sourceFilter="all";
  const generic=/^(?:首頁|新聞|最新消息|公文公告|公告查詢|新聞中心|個股資訊|台股新聞|財經新聞|即時新聞)$/i;
  const truncate=(value,max=180)=>{const text=stripHtml(value);return text.length>max?`${text.slice(0,max).trim()}…`:text};
  const validUrl=value=>{try{const u=new URL(value);return /^https?:$/.test(u.protocol)&&u.pathname!=="/"}catch{return false}};
  const rows=(payload.items||[]).map(item=>({...item,title:stripHtml(item.title),summary:stripHtml(item.ai_summary||item.summary),url:validUrl(item.url)?item.url:null})).filter(item=>item.title&&item.url&&!generic.test(item.title));
  const channels=payload.channels||[];
  const impactLabel=item=>item.impact==="high"?"高影響":item.impact==="low"?"低影響":"中影響";
  const normalCard=item=>`<a class="news-card compact" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener"><div class="news-meta"><span>${escapeHtml(item.source||"市場消息")}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><div class="ai-badges"><span class="tag">${escapeHtml(item.ai_category||item.topic||"市場")}</span><span class="impact-badge ${escapeHtml(item.impact||"medium")}">${impactLabel(item)}</span><span class="direction-badge">${escapeHtml(item.market_direction||"中性")}</span></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(truncate(item.summary,150)||"來源未提供文章大綱。")}</p><small class="affected-market">影響：${escapeHtml((item.affected_markets||["市場"]).join("、"))}</small></a>`;
  const majorCard=item=>`<article class="major-news-card"><div class="major-news-side"><span class="impact-badge ${escapeHtml(item.impact||"high")}">${impactLabel(item)}</span><span>${escapeHtml(item.market_direction||"中性")}</span><small>信心 ${escapeHtml(item.confidence||"中")}</small></div><div class="major-news-main"><div class="news-meta"><span>${escapeHtml(item.source||"市場消息")}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(truncate(item.summary,260)||"來源未提供文章大綱。")}</p><div class="why-it-matters"><b>市場判讀</b><span>${escapeHtml(item.why_it_matters||"此事件可能影響市場風險偏好與資金流向。")}</span><em>重要度 ${escapeHtml(item.importance_score??"—")}</em></div><div class="major-news-foot"><span class="tag">${escapeHtml(item.ai_category||"重大資訊")}</span><span>可能影響：${escapeHtml((item.affected_markets||["市場"]).join("、"))}</span><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener">閱讀原文 →</a></div></div></article>`;
  const noticeCard=item=>{const summary=truncate(item.short_summary||item.summary,125)||"來源未提供公告摘要。",full=stripHtml(item.full_text||item.original_text||"");return `<article class="company-notice-card"><div class="company-notice-head"><div><span class="tag">${escapeHtml(item.ai_category||"個股公告")}</span><span class="impact-badge ${escapeHtml(item.impact||"medium")}">${impactLabel(item)}</span></div><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><h3>${escapeHtml(item.title)}</h3><p class="notice-summary">${escapeHtml(summary)}</p>${Array.isArray(item.key_facts)&&item.key_facts.length?`<dl class="notice-facts">${item.key_facts.slice(0,4).map(row=>`<div><dt>${escapeHtml(row.label||"重點")}</dt><dd>${escapeHtml(row.value||"—")}</dd></div>`).join("")}</dl>`:""}${full&&full.length>summary.length+20?`<details class="notice-details"><summary>查看公告內容</summary><p>${escapeHtml(full)}</p></details>`:""}<div class="company-notice-actions">${(item.symbols||[])[0]?`<a href="asset.html?symbol=${encodeURIComponent(item.symbols[0])}">查看個股 →</a>`:""}<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener">官方來源 →</a></div></article>`};
  const statusLabel=status=>status==="ok"?"正常":status==="partial"?"部分更新":status==="fallback"?"沿用上次資料":status==="warning"?"來源異常":"等待更新";
  $("#sourceStatus").innerHTML=channels.map(channel=>{const meta=channel.metadata||{},cfg=channel.channel||{};return `<article class="source-status-card ${escapeHtml(meta.status||"waiting")}"><div><strong>${escapeHtml(cfg.label||meta.source_name||cfg.id)}</strong><span>${escapeHtml(statusLabel(meta.status))}</span></div><b>${Number(meta.item_count||0).toLocaleString("zh-TW")} 則</b><small>${meta.updated_at?`更新 ${escapeHtml(formatTime(meta.updated_at))}`:"尚未執行"}</small></article>`}).join("");
  const major=rows.filter(item=>item.is_major===true&&item.source_id!=="company-disclosures").slice(0,5);
  $("#majorNews").innerHTML=major.length?major.map(majorCard).join(""):'<div class="empty">目前沒有達到高影響門檻的市場資訊；各新聞來源仍獨立更新。</div>';
  const official=rows.filter(item=>item.source_id==="official-notices").slice(0,12);
  $("#officialNotices").innerHTML=official.length?official.map(normalCard).join(""):'<div class="empty">官方公告來源尚未產生資料，其他新聞來源不受影響。</div>';
  const companies=rows.filter(item=>item.source_id==="company-disclosures"||item.scope==="company").slice(0,16);
  $("#companyNotices").innerHTML=companies.length?companies.map(noticeCard).join(""):'<div class="empty">個股重大訊息來源尚未產生資料，媒體新聞仍會正常顯示。</div>';
  const mediaChannels=channels.filter(channel=>channel.channel?.kind==="media");
  $("#publisherBlocks").innerHTML=mediaChannels.map(channel=>{const cfg=channel.channel||{},meta=channel.metadata||{},items=rows.filter(item=>item.source_id===cfg.id).slice(0,6);return `<section class="panel publisher-panel"><div class="section-head"><div><p class="eyebrow">${escapeHtml(String(cfg.id||"").toUpperCase())}</p><h2>${escapeHtml(cfg.label||cfg.id)}</h2></div><small>${escapeHtml(statusLabel(meta.status))} · ${Number(meta.item_count||0)} 則 · ${meta.updated_at?escapeHtml(formatTime(meta.updated_at)):"尚未更新"}</small></div><div class="news-grid compact-news-grid">${items.length?items.map(normalCard).join(""):'<div class="empty">此來源本次沒有可用文章；不影響其他來源。</div>'}</div></section>`}).join("");
  $("#sourceFilters").innerHTML=`<button class="chip active" data-source="all">全部來源</button>`+mediaChannels.map(c=>`<button class="chip" data-source="${escapeHtml(c.channel.id)}">${escapeHtml(c.channel.label)}</button>`).join("");
  function renderAll(){
    const query=$("#newsSearch").value.trim().toLowerCase();
    const matches=item=>(!query||`${item.title} ${item.summary} ${item.source} ${item.ai_category} ${(item.symbols||[]).join(" ")}`.toLowerCase().includes(query))&&(sourceFilter==="all"||item.source_id===sourceFilter)&&(topic==="all"||item.topic===topic||item.ai_topic===topic);
    const result=rows.filter(item=>!item.company_announcement&&item.source_id!=="company-disclosures"&&item.source_id!=="official-notices"&&matches(item));
    $("#newsRows").innerHTML=result.slice(0,120).map(normalCard).join("")||'<div class="empty">沒有符合條件的新聞文章</div>';
    $("#newsCount").textContent=`${rows.length} 則／${channels.length} 個獨立來源`;
    $("#newsUpdated").textContent=payload.metadata?.updated_at?formatTime(payload.metadata.updated_at):"等待各來源排程";
  }
  $("#newsSearch").oninput=renderAll;
  document.querySelectorAll("[data-topic]").forEach(button=>button.onclick=()=>{topic=button.dataset.topic;document.querySelectorAll("[data-topic]").forEach(x=>x.classList.remove("active"));button.classList.add("active");renderAll()});
  $("#sourceFilters").onclick=event=>{const button=event.target.closest("[data-source]");if(!button)return;sourceFilter=button.dataset.source;$("#sourceFilters").querySelectorAll("button").forEach(x=>x.classList.remove("active"));button.classList.add("active");renderAll()};
  renderAll();
})();
