(async()=>{
  "use strict";
  const {$,escapeHtml,formatTime,stripHtml}=MR;
  const [payload,stockPayload]=await Promise.all([MR.loadNewsChannels(),MR.loadStockNews()]);
  let topic="all",sourceFilter="all";
  const generic=/^(?:首頁|新聞|最新消息|公文公告|公告查詢|新聞中心|個股資訊|台股新聞|財經新聞|即時新聞)$/i;
  const invalidOfficial=/個人資料|隱私權|網站使用|資訊安全|常見問題|網站導覽|下載專區|系統維護|服務條款/i;
  const truncate=(value,max=180)=>{const text=stripHtml(value);return text.length>max?`${text.slice(0,max).trim()}…`:text};
  const validUrl=value=>{try{const u=new URL(value);return /^https?:$/.test(u.protocol)&&u.pathname!=="/"}catch{return false}};
  const normalize=value=>stripHtml(value).toLowerCase().normalize("NFKC").replace(/[^0-9a-z\u3400-\u9fff]+/g,"");
  const cleanRows=list=>(list||[]).map(item=>({...item,title:stripHtml(item.title),summary:stripHtml(item.ai_summary||item.summary),url:validUrl(item.url)?item.url:null})).filter(item=>item.title&&item.url&&!generic.test(item.title));
  const channels=payload.channels||[];
  const mediaChannels=channels.filter(channel=>channel.channel?.kind==="media");
  const officialRows=cleanRows(payload.items).filter(item=>item.source_id==="official-notices"&&!/櫃買|TPEx/i.test(`${item.source||""} ${item.title||""}`)&&!invalidOfficial.test(item.title));
  const companyRows=cleanRows(payload.items).filter(item=>item.source_id==="company-disclosures");
  const stockRows=cleanRows(stockPayload.items);
  const mediaRaw=cleanRows(payload.items).filter(item=>!['official-notices','company-disclosures'].includes(item.source_id));

  const LEADER_RE=/台積電|鴻海|聯發科|廣達|緯創|國巨|川湖|日月光|台達電|中華電|長榮|陽明|NVIDIA|輝達|Microsoft|微軟|Apple|蘋果|Amazon|亞馬遜|Meta|Google|Alphabet|AMD|Intel|Tesla|三星|SK\s*海力士|海力士|Sony|Toyota/i;
  const LEADING_SECTOR_RE=/AI\s*伺服器|人工智慧|半導體|晶圓代工|記憶體|HBM|封裝測試|散熱|PCB|電源供應|雲端|資料中心|金融|航運|能源|原物料|機器人/i;
  const EXECUTIVE_RE=/執行長|董事長|財務長|總經理|基金經理人|分析師|首席經濟學家|央行總裁|官員|法說會|投資人會議|發表會|開發者大會|展覽|論壇|供應鏈會議/i;
  const BUSINESS_RE=/財報|財測|展望|營收|獲利|EPS|訂單|資本支出|擴產|漲價|降價|新品|新產品|合作|併購|投資/i;
  const SYSTEMIC_RE=/FOMC|聯準會|央行|CPI|PCE|GDP|非農|JOLTS|PMI|升息|降息|關稅|制裁|戰爭|金融危機|熔斷|重大法規/i;
  const GLOBAL_RE=/美股|美國|NASDAQ|S&P|道瓊|韓國|KOSPI|KOSDAQ|日本|日經|歐洲|中國|港股|全球/i;
  const INDUSTRY_RE=/產業|供應鏈|報價|需求|庫存|出貨|產能|製造|零組件|航運|金融|能源|原物料/i;
  const impactLabel=item=>item.impact==="high"?"高影響":item.impact==="low"?"低影響":"中影響";
  const majorScore=item=>{
    const text=`${item.title||""} ${item.summary||""}`;let score=0;
    if(SYSTEMIC_RE.test(text))score+=42;
    if(LEADER_RE.test(text))score+=24;
    if(LEADING_SECTOR_RE.test(text))score+=18;
    if(EXECUTIVE_RE.test(text))score+=16;
    if(BUSINESS_RE.test(text))score+=14;
    if(["official-notices","company-disclosures","cna"].includes(item.source_id))score+=12;
    if((item.other_reports||[]).length)score+=Math.min(14,(item.other_reports||[]).length*5);
    if(item.impact==="high")score+=12;else if(item.impact==="medium")score+=5;
    const age=(Date.now()-Date.parse(item.published_at||item.date||0))/86400000;
    if(Number.isFinite(age)&&age<=1)score+=10;else if(Number.isFinite(age)&&age<=3)score+=6;
    return Math.max(score,Number(item.importance_score||0));
  };
  const verifyInfo=item=>{
    if(item.source_id==="official-notices"||item.source_id==="company-disclosures")return{label:"官方確認",className:"official"};
    if((item.other_reports||[]).length)return{label:"多來源一致",className:"confirmed"};
    if(item.source_id==="cna")return{label:"主要媒體",className:"primary"};
    return{label:"單一來源",className:"reference"};
  };
  const companyLabel=item=>{const companies=item.companies||[];if(companies.length)return companies.slice(0,2).map(x=>`${x.symbol} ${x.name}`).join("、");return (item.symbols||[]).slice(0,2).join("、")||""};
  const imageMarkup=item=>item.image_url?`<div class="stock-news-image"><img src="${escapeHtml(item.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.parentElement.remove()"></div>`:"";
  const unifiedCard=item=>{
    const verify=verifyInfo(item),company=companyLabel(item),stock=company||item.is_stock_news;
    return `<article class="stock-news-card unified-news-card">${imageMarkup(item)}<div class="stock-news-body"><div class="news-meta"><span>${escapeHtml(item.source||"財經媒體")}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><div class="stock-news-labels">${stock&&company?`<a href="asset.html?symbol=${encodeURIComponent((item.symbols||[])[0]||"")}">${escapeHtml(company)}</a>`:""}<span class="tag">${escapeHtml(item.ai_category||item.topic||"財經新聞")}</span><span class="impact-badge ${escapeHtml(item.impact||"medium")}">${impactLabel(item)}</span><span class="direction-badge">${escapeHtml(item.market_direction||"中性")}</span><span class="verification-badge ${verify.className}">${verify.label}</span></div><h3><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(item.title)}</a></h3><p>${escapeHtml(truncate(item.summary,190)||"來源未提供文章大綱。")}</p><small class="affected-market">影響：${escapeHtml((item.companies||[]).map(x=>x.industry).filter(Boolean).slice(0,3).join("、")||(item.affected_markets||["市場"]).join("、"))}</small>${(item.other_reports||[]).length?`<details class="other-reports"><summary>其他媒體報導 ${item.other_reports.length} 則</summary>${item.other_reports.map(row=>`<a href="${escapeHtml(row.url)}" target="_blank" rel="noreferrer noopener">${escapeHtml(row.source||"其他來源")}：${escapeHtml(truncate(row.title,70))}</a>`).join("")}</details>`:""}</div></article>`;
  };
  const majorCard=item=>{const verify=verifyInfo(item);return `<article class="major-news-card"><div class="major-news-side"><span class="impact-badge ${escapeHtml(item.impact||"high")}">${impactLabel(item)}</span><span>${escapeHtml(item.market_direction||"中性")}</span><small class="verification-badge ${verify.className}">${verify.label}</small></div><div class="major-news-main"><div class="news-meta"><span>${escapeHtml(item.source||"市場消息")}</span><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(truncate(item.summary,260)||"來源未提供文章大綱。")}</p><div class="why-it-matters"><b>市場判讀</b><span>${escapeHtml(item.why_it_matters||"此事件可能影響市場風險偏好、產業展望或資金流向。")}</span><em>重要度 ${majorScore(item)}</em></div><div class="major-news-foot"><span class="tag">${escapeHtml(item.ai_category||"重大資訊")}</span><span>可能影響：${escapeHtml((item.affected_markets||["市場"]).join("、"))}</span><a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener">閱讀原文 →</a></div></div></article>`};
  const noticeCard=item=>{const summary=truncate(item.short_summary||item.summary,125)||"來源未提供公告摘要。",full=stripHtml(item.full_text||item.original_text||"");return `<article class="company-notice-card"><div class="company-notice-head"><div><span class="tag">${escapeHtml(item.ai_category||"個股公告")}</span><span class="impact-badge ${escapeHtml(item.impact||"medium")}">${impactLabel(item)}</span><span class="verification-badge official">官方確認</span></div><time>${escapeHtml(formatTime(item.published_at||item.date))}</time></div><h3>${escapeHtml(item.title)}</h3><p class="notice-summary">${escapeHtml(summary)}</p>${Array.isArray(item.key_facts)&&item.key_facts.length?`<dl class="notice-facts">${item.key_facts.slice(0,4).map(row=>`<div><dt>${escapeHtml(row.label||"重點")}</dt><dd>${escapeHtml(row.value||"—")}</dd></div>`).join("")}</dl>`:""}${full&&full.length>summary.length+20?`<details class="notice-details"><summary>查看公告內容</summary><p>${escapeHtml(full)}</p></details>`:""}<div class="company-notice-actions">${(item.symbols||[])[0]?`<a href="asset.html?symbol=${encodeURIComponent(item.symbols[0])}">查看個股 →</a>`:""}<a href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer noopener">官方來源 →</a></div></article>`};

  const stockByKey=new Map();
  for(const item of stockRows){stockByKey.set(normalize(item.title),item)}
  const combined=[];const seen=new Set();
  for(const item of [...stockRows,...mediaRaw]){
    const enriched=stockByKey.get(normalize(item.title))||item;
    const key=normalize(enriched.title)||String(enriched.url||"");
    if(!key||seen.has(key))continue;seen.add(key);combined.push({...enriched,_majorScore:majorScore(enriched)});
  }
  combined.sort((a,b)=>Date.parse(b.published_at||0)-Date.parse(a.published_at||0));

  const majorCandidates=[...combined,...officialRows].map(item=>({...item,_majorScore:majorScore(item)})).filter(item=>item._majorScore>=45).sort((a,b)=>b._majorScore-a._majorScore||Date.parse(b.published_at||0)-Date.parse(a.published_at||0)).slice(0,8);
  $("#majorNews").innerHTML=majorCandidates.length?majorCandidates.map(majorCard).join(""):'<div class="empty">目前沒有達到精選門檻的重大資訊。</div>';

  const sourceOptions=mediaChannels.filter(channel=>channel.channel?.id!=="official-notices");
  $("#sourceFilters").innerHTML=`<button class="chip active" data-source="all">全部來源</button>`+sourceOptions.map(c=>`<button class="chip" data-source="${escapeHtml(c.channel.id)}">${escapeHtml(c.channel.label)}</button>`).join("");
  const topicMatch=(item,value)=>{
    if(value==="all")return true;if(value==="major")return majorScore(item)>=45;
    const text=`${item.title||""} ${item.summary||""}`;
    if(value==="stock")return Boolean((item.symbols||[]).length||item.is_stock_news);
    if(value==="global")return GLOBAL_RE.test(text);
    if(value==="industry")return INDUSTRY_RE.test(text)||LEADING_SECTOR_RE.test(text);
    return item.topic===value||item.ai_topic===value;
  };
  function renderLatest(){
    const query=$("#newsSearch").value.trim().toLowerCase();
    const result=combined.filter(item=>(!query||`${item.title} ${item.summary} ${item.source} ${item.ai_category} ${(item.symbols||[]).join(" ")}`.toLowerCase().includes(query))&&(sourceFilter==="all"||item.source_id===sourceFilter)&&topicMatch(item,topic));
    $("#latestNewsRows").innerHTML=result.slice(0,120).map(unifiedCard).join("")||'<div class="empty">沒有符合條件的繁體中文財經新聞</div>';
  }
  $("#newsSearch").oninput=renderLatest;
  $("#categoryFilters").onclick=event=>{const button=event.target.closest("[data-topic]");if(!button)return;topic=button.dataset.topic;$("#categoryFilters").querySelectorAll("button").forEach(x=>x.classList.remove("active"));button.classList.add("active");renderLatest()};
  $("#sourceFilters").onclick=event=>{const button=event.target.closest("[data-source]");if(!button)return;sourceFilter=button.dataset.source;$("#sourceFilters").querySelectorAll("button").forEach(x=>x.classList.remove("active"));button.classList.add("active");renderLatest()};

  $("#officialNotices").innerHTML=officialRows.length?officialRows.slice(0,9).map(unifiedCard).join(""):'<div class="empty">目前沒有可驗證的官方市場公告。</div>';
  $("#companyNotices").innerHTML=companyRows.length?companyRows.slice(0,16).map(noticeCard).join(""):'<div class="empty">個股重大訊息來源尚未產生資料。</div>';
  const badChannels=channels.filter(channel=>["warning","partial","fallback"].includes(channel.metadata?.status));
  $("#newsHealthNote").textContent=badChannels.length?`· 部分來源暫時未完整更新（${badChannels.length}）`:"";
  $("#newsCount").textContent=`${combined.length+officialRows.length+companyRows.length} 則`;
  $("#newsUpdated").textContent=payload.metadata?.updated_at?formatTime(payload.metadata.updated_at):"等待各來源排程";
  renderLatest();
})();
