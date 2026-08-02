(() => {
  "use strict";

  const $=selector=>document.querySelector(selector);
  const $$=selector=>[...document.querySelectorAll(selector)];
  const escapeHtml=value=>String(value??"").replace(/[&<>\"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[char]));
  const state={payload:{institutional:{},items:[]},market:"twse"};

  function fmt(value,{dateOnly=false}={}) {
    if (!value) return "—";
    const date=new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const options=dateOnly
      ? {timeZone:"Asia/Taipei",month:"numeric",day:"numeric"}
      : {timeZone:"Asia/Taipei",month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false};
    return date.toLocaleString("zh-TW",options);
  }

  function formatTradingDate(value) {
    if (!value) return "尚無交易日資料";
    const date=new Date(`${value}T12:00:00+08:00`);
    if (Number.isNaN(date.getTime())) return value;
    return `${date.getMonth()+1}/${date.getDate()}（週${["日","一","二","三","四","五","六"][date.getDay()]}）`;
  }

  function isSafeUrl(value) {
    try {
      const url=new URL(String(value||""),location.href);
      return ["http:","https:"].includes(url.protocol) && !/(^|\.)google\./i.test(url.hostname) && url.hostname!=="news.google.com";
    } catch { return false; }
  }

  function articleLink(item) {
    return [item?.direct_link,item?.safe_link,item?.link,item?.source_url,item?.source_home].find(isSafeUrl)||"";
  }

  function amount(value) {
    if (value===null||value===undefined||value==="") return "—";
    const number=Number(value);
    return Number.isFinite(number)?`${number>=0?"+":""}${number.toFixed(1)} 億`:"—";
  }

  function valueClass(value) {
    const number=Number(value);
    if (!Number.isFinite(number)||number===0) return "flat";
    return number>0?"positive":"negative";
  }

  function renderInstitutional() {
    const root=$("#institutionalCards");
    if (!root) return;
    const institutional=state.payload.institutional||{};
    const market=state.market;
    const values=institutional[market]||{};
    const dateValue=institutional[`${market}_date`]||institutional.date;
    const dateText=formatTradingDate(dateValue);
    const dateNode=$("#institutionalTradingDate");
    if (dateNode) dateNode.textContent=`${market==="twse"?"上市":"上櫃"} · ${dateText}`;
    $$(`[data-institutional-market]`).forEach(button=>button.classList.toggle("active",button.dataset.institutionalMarket===market));

    const rows=[
      ["foreign","外資",values.foreign],
      ["investment_trust","投信",values.investment_trust],
      ["dealer","自營商",values.dealer],
      ["total","合計",values.total],
    ];
    const hasData=rows.some(([, ,value])=>value!==null&&value!==undefined&&value!=="");
    if (!hasData) {
      root.innerHTML='<div class="announcement-unified-empty institutional-empty"><strong>等待法人盤後資料</strong><span>第一次完整更新成功後，會顯示最近交易日的官方數值。</span></div>';
      return;
    }

    const officialUrl=market==="twse"?institutional.twse_url:institutional.tpex_url;
    root.innerHTML=rows.map(([type,label,value])=>{
      const internal=market==="twse";
      const href=internal?`institutional.html?market=twse&type=${encodeURIComponent(type)}`:(isSafeUrl(officialUrl)?officialUrl:"institutional.html");
      return `<a class="institutional-card ${valueClass(value)}" href="${escapeHtml(href)}"${internal?"":' target="_blank" rel="noreferrer noopener"'}>
        <span>${escapeHtml(label)}</span><strong>${amount(value)}</strong><small>${escapeHtml(dateText)}</small>
      </a>`;
    }).join("");
  }

  function renderAnnouncements() {
    const root=$("#announcementList");
    if (!root) return;
    const items=(state.payload.items||[])
      .filter(item=>articleLink(item))
      .sort((a,b)=>new Date(b.published_at||0)-new Date(a.published_at||0))
      .slice(0,5);
    const count=$("#announcementCount");
    if (count) count.textContent=items.length?`最新 ${items.length} 則`:"尚無有效公告";
    if (!items.length) {
      root.innerHTML='<div class="announcement-unified-empty"><strong>尚未取得官方公告</strong><span>更新流程若抓取失敗會在 Actions 顯示錯誤，不再用占位資料冒充成功。</span></div>';
      return;
    }
    root.innerHTML=items.map(item=>`
      <a class="official-announcement-row" href="${escapeHtml(articleLink(item))}" target="_blank" rel="noreferrer noopener">
        <time>${escapeHtml(fmt(item.published_at,{dateOnly:true}))}</time>
        <span><b>${escapeHtml(item.source||item.region||"官方")}</b><strong>${escapeHtml(item.title_zh||item.title_original||"官方公告")}</strong></span>
        <em>↗</em>
      </a>`).join("");
  }

  function render(payload) {
    state.payload=payload||{institutional:{},items:[]};
    renderInstitutional();
    renderAnnouncements();
    const updated=$("#announcementUpdatedAt");
    if (updated) updated.textContent=payload?.metadata?.updated_at?fmt(payload.metadata.updated_at):"等待第一次排程";
  }

  async function load() {
    const seed=window.__MARKET_ANNOUNCEMENT_SEED__||{institutional:{},items:[]};
    let payload=seed;
    try {
      payload=window.MarketDataSource?.loadJson
        ? await window.MarketDataSource.loadJson("data/announcements.json",seed)
        : seed;
    } catch {}
    render(payload);
  }

  $$(`[data-institutional-market]`).forEach(button=>button.addEventListener("click",()=>{
    state.market=button.dataset.institutionalMarket;
    renderInstitutional();
  }));
  load();
  setInterval(load,30_000);
})();
