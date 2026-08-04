(async()=>{
  "use strict";
  const {$,escapeHtml,formatTime}=MR;
  const payload=await MR.loadData("news.json",window.__NEWS_SEED__||{items:[]});
  let topic="all";
  const genericTitle=/^(?:公文公告|公告查詢|證交所新聞|櫃買中心公告|新聞中心|最新消息|公告|新聞)$/i;
  const companyTerms=/增資|減資|除權|除息|股利|法說|財報|股東會|停牌|復牌|公開收購|併購|合併|處分資產|取得資產|重大合約|融資融券|注意股票|處置股票/i;
  const strip=value=>String(value||"").replace(/<[^>]*>/g," ").replace(/&nbsp;/gi," ").replace(/\s+/g," ").trim();
  const truncate=(value,max=220)=>{const text=strip(value);return text.length>max?`${text.slice(0,max).trim()}…`:text};
  const cleanTitle=value=>strip(value).replace(/\s*(?:[-｜|]\s*)?(?:twse\.com\.tw|tpex\.org\.tw|臺灣證券交易所|台灣證券交易所|櫃買中心|Google News)\s*$/i,"").trim();
  function articleUrl(value){
    try{
      const raw=String(value||"").trim();
      if(!/^https?:\/\//i.test(raw)||/[<>]/.test(raw))return null;
      const url=new URL(raw),path=url.pathname.replace(/\/+$/,"/").toLowerCase(),segments=path.split("/").filter(Boolean);
      if(["/","/index.html","/index.php","/home","/home/","/news","/news/"].includes(path)&&!url.search)return null;
      if(/\/(search|tag|tags|category|categories|topics?|sections?|list|lists|download|downloads)\/?$/.test(path))return null;
      if(/\/(announcement|news|bulletin|material|mops)\/?$/.test(path)&&!/[?&](id|newsid|article|sn|seq|document|post|content_number)=/i.test(url.search))return null;
      if(segments.length===0)return null;
      return url.href;
    }catch{return null}
  }
  const isCompanyNotice=item=>item.scope==="company"||item.company_announcement===true||((item.symbols||[]).length>0&&companyTerms.test(`${item.title||""} ${item.summary||""}`));
  const rows=(payload.items||[]).map(item=>{
    const title=cleanTitle(item.title),summary=strip(item.ai_summary||item.summary),original=strip(item.original_text||item.raw_summary||item.summary),url=articleUrl(item.url),company=isCompanyNotice(item);
    return {...item,title,summary,original,url,company,ai_category:company?"個股公告":item.ai_category};
  }).filter(item=>item.title&&item.url&&!genericTitle.test(item.title)&&!/^<a\b/i.test(item.title));
  const impactLabel=item=>item.impact==="high"?"高影響":item.impact==="low"?"低影響":"中影響";
  const factRows=item=>{
    if(Array.isArray(item.key_facts)&&item.key_facts.length)return item.key_facts.slice(0,6).map(row=>typeof row==="string"?{label:"重點",value:row}:row);
    const text=`${item.title} ${item.original||item.summary}`;
    const facts=[];
    const add=(label,value)=>{if(value&&!facts.some(row=>row.label===label))facts.push({label,value})};
    add("股票代碼",(item.symbols||[])[0]);
    const date=text.match(/(?:民國|中華民國)?\s*(\d{2,3})[年/]\s*(\d{1,2})[月/]\s*(\d{1,2})日?/);
    if(date)add("重要日期",`${Number(date[1])+1911}/${date[2]}/${date[3]}`);
    const shares=text.match(/(?:發行(?:新股|股數|總股數)|認購股數)[^0-9]{0,15}([0-9][0-9,]*)\s*股/);
    const amount=text.match(/(?:募集資金|發行總額|交易金額|每股配息|現金股利|金額)[^0-9]{0,15}([0-9][0-9,.]*(?:億|萬)?元)/);
    const purpose=text.match(/(?:資金用途|用途)[：:]?\s*([^。；;]{4,80})/);
    add("股數",shares?.[1]?`${shares[1]} 股`:null);
    add("金額",amount?.[1]);
    add("用途",purpose?.[1]);
    return facts.slice(0,6);
  };
  const normalCard=item=>`<a class="news-card compact" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener"><div class="news-meta"><span>${escapeHtml(item.source||"市場消息")}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><div class="ai-badges"><span class="tag">${escapeHtml(item.ai_category||item.topic||"市場")}</span><span class="impact-badge ${escapeHtml(item.impact||"medium")}">${impactLabel(item)}</span><span class="direction-badge">${escapeHtml(item.market_direction||"中性")}</span></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(truncate(item.summary,150)||"來源未提供文章大綱。")}</p><small class="affected-market">影響：${escapeHtml((item.affected_markets||["市場"]).join("、"))}</small>${item.why_it_matters?`<small class="analysis-note">${escapeHtml(item.why_it_matters)}</small>`:""}</a>`;
  const majorCard=item=>`<article class="major-news-card"><div class="major-news-side"><span class="impact-badge ${escapeHtml(item.impact||"high")}">${impactLabel(item)}</span><span>${escapeHtml(item.market_direction||"中性")}</span><small>信心 ${escapeHtml(item.confidence||"中")}</small></div><div class="major-news-main"><div class="news-meta"><span>${escapeHtml(item.source||"市場消息")}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(truncate(item.summary,260)||"來源未提供文章大綱。")}</p>${item.why_it_matters?`<div class="why-it-matters"><b>市場判讀</b><span>${escapeHtml(item.why_it_matters)}</span><em>重要度 ${escapeHtml(item.importance_score??"—")}</em></div>`:""}<div class="major-news-foot"><span class="tag">${escapeHtml(item.ai_category||item.topic||"重大資訊")}</span><span>可能影響：${escapeHtml((item.affected_markets||["市場"]).join("、"))}</span><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener">閱讀原文 →</a></div></div></article>`;
  const companyCard=item=>{
    const facts=factRows(item),full=item.original||item.summary;
    return `<article class="company-notice-card"><div class="company-notice-head"><div><span class="tag">${escapeHtml(item.ai_category||"個股公告")}</span><span class="impact-badge ${escapeHtml(item.impact||"medium")}">${impactLabel(item)}</span></div><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(truncate(item.summary,190)||"來源未提供公告摘要。")}</p>${item.why_it_matters?`<p class="notice-impact-note">${escapeHtml(item.why_it_matters)}</p>`:""}${facts.length?`<dl class="notice-facts">${facts.map(row=>`<div><dt>${escapeHtml(row.label||"重點")}</dt><dd>${escapeHtml(row.value||"—")}</dd></div>`).join("")}</dl>`:""}<div class="company-notice-actions">${(item.symbols||[])[0]?`<a href="asset.html?symbol=${encodeURIComponent(item.symbols[0])}">查看個股 →</a>`:""}<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener">官方公告 →</a></div>${full&&full.length>220?`<details class="notice-full"><summary>展開公告內容</summary><p>${escapeHtml(full)}</p></details>`:""}</article>`;
  };
  function render(){
    const query=$("#newsSearch").value.trim().toLowerCase();
    const matches=item=>!query||`${item.title} ${item.summary} ${item.source} ${item.ai_category} ${(item.symbols||[]).join(" ")}`.toLowerCase().includes(query);
    const major=rows.filter(item=>item.is_major===true&&!item.company&&matches(item)).slice(0,5);
    const companies=rows.filter(item=>item.company&&matches(item)).slice(0,12);
    const normal=rows.filter(item=>!item.company&&!major.includes(item)&&(topic==="all"||item.topic===topic||item.ai_topic===topic)&&matches(item));
    $("#majorNews").innerHTML=major.length?major.map(majorCard).join(""):'<div class="empty">目前沒有市場級高影響重大資訊</div>';
    $("#companyNotices").innerHTML=companies.length?companies.map(companyCard).join(""):'<div class="empty">目前沒有符合條件的個股重要公告</div>';
    $("#newsRows").innerHTML=normal.slice(0,90).map(normalCard).join("")||'<div class="empty">沒有符合條件的一般新聞文章</div>';
    $("#newsCount").textContent=`${rows.filter(matches).length} 則`;
    $("#newsUpdated").textContent=payload.metadata?.updated_at?formatTime(payload.metadata.updated_at):"等待排程";
  }
  $("#newsSearch").oninput=render;
  document.querySelectorAll("[data-topic]").forEach(button=>button.onclick=()=>{topic=button.dataset.topic;document.querySelectorAll("[data-topic]").forEach(item=>item.classList.remove("active"));button.classList.add("active");render()});
  render();
})();
