(() => {
  "use strict";
  const $ = s => document.querySelector(s);
  const escapeHtml = v => String(v || "").replace(/[&<>\"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
  const fmt = v => {
    if (!v) return "等待更新";
    const d = new Date(v);
    return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("zh-TW",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false});
  };
  async function load(){
    let payload = window.__MARKET_ANNOUNCEMENT_SEED__ || {institutional:{},items:[]};
    try {
      const response=await fetch(`data/announcements.json?t=${Date.now()}`,{cache:"no-store"});
      if(response.ok) payload=await response.json();
    } catch {}
    render(payload);
  }
  function amount(v){
    if(v===null||v===undefined) return "—";
    const n=Number(v); if(!Number.isFinite(n)) return String(v);
    return `${n>=0?"+":""}${n.toFixed(1)} 億`;
  }
  function render(payload){
    const inst=payload.institutional||{};
    const cards=$("#institutionalCards");
    if(cards){
      const twse=inst.twse||{},tpex=inst.tpex||{};
      cards.innerHTML=`
        <article><span>上市外資</span><strong>${amount(twse.foreign)}</strong><small>${escapeHtml(inst.date||"等待盤後資料")}</small></article>
        <article><span>上市投信</span><strong>${amount(twse.investment_trust)}</strong><small>官方三大法人</small></article>
        <article><span>上市自營商</span><strong>${amount(twse.dealer)}</strong><small>含自行與避險</small></article>
        <article><span>上櫃三大法人</span><strong>${amount(tpex.total)}</strong><small>櫃買中心</small></article>`;
    }
    const list=$("#importantAnnouncementList");
    if(list){
      list.innerHTML=(payload.items||[]).slice(0,8).map(item=>`
        <a class="announcement-row" href="${item.link}" target="_blank" rel="noreferrer noopener">
          <span class="announcement-region">${escapeHtml(item.region||"GLOBAL")}</span>
          <div><strong>${escapeHtml(item.title_zh||item.title_original)}</strong><small>${escapeHtml(item.source||"官方來源")} · ${fmt(item.published_at)}${item.translation_status==="rule-based"?" · 規則翻譯":""}</small></div>
          <b>${item.importance==="high"?"重要":"公告"}</b>
        </a>`).join("");
    }
    const updated=$("#announcementUpdatedAt"); if(updated) updated.textContent=fmt(payload.metadata?.updated_at);
  }
  load();
})();