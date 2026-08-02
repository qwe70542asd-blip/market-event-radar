(() => {
  "use strict";
  const $=selector=>document.querySelector(selector);
  const escapeHtml=value=>String(value??"").replace(/[&<>\"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[char]));
  let payload={metadata:{},sources:[],items:[]};

  function fmt(value, precision="minute") {
    if (!value) return "—";
    const date=new Date(value||0);
    if (Number.isNaN(date.getTime())) return "—";
    const options=precision==="date"
      ? {timeZone:"Asia/Taipei",month:"numeric",day:"numeric"}
      : {timeZone:"Asia/Taipei",month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false};
    return date.toLocaleString("zh-TW",options);
  }

  function renderSources() {
    const select=$("#newsSourceFilter");
    if (!select) return;
    const sources=[...new Set((payload.items||[]).map(item=>item.source).filter(Boolean))].sort();
    select.innerHTML='<option value="all">全部來源</option>'+sources.map(source=>`<option>${escapeHtml(source)}</option>`).join("");
  }

  function render() {
    const q=$("#newsSearchInput")?.value.trim().toLowerCase()||"";
    const region=$("#newsRegionFilter")?.value||"all";
    const topic=$("#newsTopicFilter")?.value||"all";
    const industry=$("#newsIndustryFilter")?.value||"all";
    const assetClass=$("#newsAssetClassFilter")?.value||"all";
    const cryptoCategory=$("#cryptoCategoryFilter")?.value||"all";
    const source=$("#newsSourceFilter")?.value||"all";
    const language=$("#newsLanguageFilter")?.value||"all";
    const group=$("#newsGroupFilter")?.value||"all";
    const items=(payload.items||[]).filter(item=>{
      const blob=`${item.title||""} ${item.summary||""} ${item.source||""}`.toLowerCase();
      return (!q||blob.includes(q))
        &&(region==="all"||item.region===region)
        &&(topic==="all"||item.topic===topic)
        &&(industry==="all"||(item.industries||[item.primary_industry]).includes(industry))
        &&(assetClass==="all"||(item.asset_class||"stock")===assetClass)
        &&(cryptoCategory==="all"||(item.crypto_categories||[]).includes(cryptoCategory))
        &&(source==="all"||item.source===source)
        &&(language==="all"||(item.language||"zh-Hant")===language)
        &&(group==="all"||item.source_group===group);
    });
    const grid=$("#newsPageGrid");
    if (grid) grid.innerHTML=items.map(item=>{
      const link=window.MarketNewsLink?.safeLink?.(item)||item.link;
      return `<article class="news-page-card">
        <a class="news-card-main" href="${escapeHtml(link)}" target="_blank" rel="noreferrer noopener">
          <div class="news-card-top"><span>${escapeHtml(item.source||"財經新聞")}</span><small>${fmt(item.published_at,item.published_precision)}</small></div>
          <h2>${escapeHtml(item.title)}</h2>
          <p>${escapeHtml(item.summary||item.event_title||"點擊前往原始文章")}</p>
          <div class="news-card-tags"><span class="asset-class-badge ${escapeHtml(item.asset_class||"stock")}">${item.asset_class==="crypto"?"虛擬貨幣":item.asset_class==="fund"?"基金":"股票"}</span><span>${escapeHtml(item.region||"GLOBAL")}</span><span>${escapeHtml(item.industry_label||"其他產業")}</span><span>${escapeHtml(item.topic||"market")}</span><span class="link-mode-badge direct">原始文章</span>${item.duplicate_count?`<span>另有 ${item.duplicate_count} 個來源</span>`:""}</div>
        </a>
        <div class="news-card-actions"><a href="${escapeHtml(link)}" target="_blank" rel="noreferrer noopener">閱讀原文 ↗</a></div>
      </article>`;
    }).join("");
    if ($("#newsPageEmpty")) $("#newsPageEmpty").hidden=items.length>0;
    if ($("#newsPageCount")) $("#newsPageCount").textContent=`${items.length} 則可直接開啟原文`;
  }

  function syncAssetFilters(){const crypto=$("#cryptoCategoryWrap");if(crypto)crypto.hidden=$("#newsAssetClassFilter")?.value!=="crypto";}
  ["#newsSearchInput","#newsAssetClassFilter","#cryptoCategoryFilter","#newsLanguageFilter","#newsGroupFilter","#newsRegionFilter","#newsIndustryFilter","#newsTopicFilter","#newsSourceFilter"].forEach(selector=>{
    $(selector)?.addEventListener(selector.includes("Input")?"input":"change",()=>{syncAssetFilters();render();});
  });
  document.querySelectorAll("[data-news-class]").forEach(button=>button.addEventListener("click",()=>{
    document.querySelectorAll("[data-news-class]").forEach(node=>node.classList.toggle("active",node===button));
    const select=$("#newsAssetClassFilter");if(select)select.value=button.dataset.newsClass;syncAssetFilters();render();
  }));
  syncAssetFilters();
  window.addEventListener("market-news-loaded",event=>{
    payload=event.detail.payload;
    if ($("#newsPageUpdatedAt")) $("#newsPageUpdatedAt").textContent=fmt(payload.metadata?.updated_at);
    const status=$("#newsPageState");
    if(status) status.textContent={live:"最新原文資料",cached:"備援資料・自動更新中",empty:"等待更新"}[event.detail.status]||"同步中";
    renderSources();render();
  });
  if (window.MarketNews?.payload) {
    payload=window.MarketNews.payload;
    if ($("#newsPageUpdatedAt")) $("#newsPageUpdatedAt").textContent=fmt(payload.metadata?.updated_at);
    renderSources();render();
  }
})();
