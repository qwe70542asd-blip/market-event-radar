(async()=>{
  "use strict";
  const {$,escapeHtml,formatTime,loadData}=MR;
  const BAD=new Set(["failed","error","unavailable","circuit-open"]),WARN=new Set(["partial","degraded","stale","pending","warning","fallback","loading","waiting","seeded","seed"]);
  const label=status=>({fresh:"正常",partial:"部分資料",degraded:"來源異常",stale:"資料過期",pending:"等待更新",failed:"失敗",unavailable:"無資料"}[status]||status||"未知");
  const css=status=>BAD.has(status)?"badge-warn":WARN.has(status)?"badge-warn":"badge-ok";
  const age=value=>{const n=Number(value);if(!Number.isFinite(n))return"—";if(n<60)return`${n} 秒`;if(n<3600)return`${Math.round(n/60)} 分`;if(n<86400)return`${(n/3600).toFixed(n<10800?1:0)} 小時`;return`${(n/86400).toFixed(1)} 天`};
  const reasons=row=>(row.reasons||[]).slice(0,2).join("；")||"—";
  const empty={metadata:{version:"v11.4.57",status:"unavailable",counts:{}},channels:[]};
  let payload=empty;
  try{payload=await loadData("channel-health.json",empty,{force:true})}catch(error){payload={...empty,metadata:{...empty.metadata,error:String(error)}}}
  const meta=payload.metadata||{},counts=meta.counts||{},verification=meta.verification_summary||{},channels=Array.isArray(payload.channels)?payload.channels:[];
  const mount=document.querySelector(".data-quality-summary");
  const trust=verification.trust_counts||{},complete=verification.completeness_counts||{},coverage=Number(verification.average_field_coverage_percent);
  const summary=`<section class="panel content data-quality-summary"><div class="section-head"><div><p class="eyebrow">LIGHTWEIGHT HEALTH INDEX</p><h2>資料健康摘要</h2></div><small>${escapeHtml(formatTime(meta.updated_at))}</small></div><div class="stat-grid"><article class="stat"><small>正常通道</small><strong>${Number(counts.fresh||0)}</strong></article><article class="stat"><small>部分／異常</small><strong class="${Number(meta.bad_count||0)?"down":"flat"}">${Number(meta.bad_count||0)}</strong></article><article class="stat"><small>等待更新</small><strong>${Number(counts.pending||0)}</strong></article><article class="stat"><small>平均欄位覆蓋</small><strong>${Number.isFinite(coverage)?coverage.toFixed(1)+"%":"—"}</strong></article><article class="stat"><small>資料衝突</small><strong class="${Number(trust.conflict||0)?"down":"flat"}">${Number(trust.conflict||0).toLocaleString("zh-TW")}</strong></article><article class="stat"><small>欄位完整</small><strong>${Number(complete.complete||0).toLocaleString("zh-TW")}</strong></article><article class="stat"><small>部分完整</small><strong>${Number(complete.partial||0).toLocaleString("zh-TW")}</strong></article><article class="stat"><small>過期來源</small><strong class="${Number(counts.stale||0)?"down":"flat"}">${Number(counts.stale||0)}</strong></article></div><p class="status-warning">此頁只下載小型健康索引，不再一次載入所有行情、新聞、財報與歷史資料；舊資料只顯示狀態，不會塞滿畫面或記憶體。</p></section>`;
  if(mount)mount.outerHTML=summary;else $("#channelGrid").insertAdjacentHTML("beforebegin",summary);
  $("#channelGrid").innerHTML=channels.map(row=>{const status=String(row.status||"pending").toLowerCase(),details=[`筆數：${Number(row.item_count||0).toLocaleString("zh-TW")}`,`更新：${formatTime(row.updated_at)}`,`資料年齡：${age(row.age_seconds)}`];if(row.stale_item_count)details.push(`過期項目：${row.stale_item_count}`);return `<article class="panel content"><h3>${escapeHtml(row.label||row.file)}</h3><p>${escapeHtml(row.file)}</p><p>${details.map(escapeHtml).join(" · ")}</p><p class="muted">${escapeHtml(reasons(row))}</p><span class="${css(status)}">${escapeHtml(label(status))}</span></article>`}).join("")||'<div class="empty">健康索引尚未產生；不會改用大量歷史資料硬撐畫面。</div>';
})();
