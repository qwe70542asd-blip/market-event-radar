(()=>{"use strict";
const OWNER="qwe70542asd-blip",REPO="market-event-radar";
const CHANNELS={"assets.json":"live-assets","asset-audit.json":"live-assets","asset-coverage.json":"live-assets","events.json":"live-events","event-source-state.json":"live-events","tw-market.json":"live-tw-market","tw-chips.json":"live-tw-chips","market-snapshot.json":"live-global-market","news-cna.json":"live-news-cna","news-moneydj.json":"live-news-moneydj","news-cnyes.json":"live-news-cnyes","news-udn.json":"live-news-udn","news-ltn.json":"live-news-ltn","news-wealth.json":"live-news-wealth","news-yahoo.json":"live-news-yahoo","news-technews.json":"live-news-technews","news-ctee.json":"live-news-ctee","stock-news.json":"live-stock-news","official-market-notices.json":"live-official-notices","company-disclosures.json":"live-company-disclosures","monthly-revenue.json":"live-monthly-revenue","dividend-history.json":"live-dividend-history","market-volume-history.json":"live-tw-market","secondary-reference.json":"live-secondary-reference","data-verification.json":"live-data-verification","yahoo-details.json":"live-yahoo-details","etf-details.json":"live-etf-details"};
const NEWS_FILES=[{"file":"news-cna.json","id":"cna","label":"中央社","seed":"__NEWS_CNA_SEED__","kind":"media"},{"file":"news-moneydj.json","id":"moneydj","label":"MoneyDJ","seed":"__NEWS_MONEYDJ_SEED__","kind":"media"},{"file":"news-cnyes.json","id":"cnyes","label":"鉅亨網","seed":"__NEWS_CNYES_SEED__","kind":"media"},{"file":"news-udn.json","id":"udn","label":"經濟日報","seed":"__NEWS_UDN_SEED__","kind":"media"},{"file":"news-ltn.json","id":"ltn","label":"自由財經","seed":"__NEWS_LTN_SEED__","kind":"media"},{"file":"news-wealth.json","id":"wealth","label":"財富自由","seed":"__NEWS_WEALTH_SEED__","kind":"media"},{"file":"news-yahoo.json","id":"yahoo","label":"Yahoo股市","seed":"__NEWS_YAHOO_SEED__","kind":"media"},{"file":"news-technews.json","id":"technews","label":"科技新報／財經新報","seed":"__NEWS_TECHNEWS_SEED__","kind":"media"},{"file":"news-ctee.json","id":"ctee","label":"工商時報","seed":"__NEWS_CTEE_SEED__","kind":"media"},{"file":"official-market-notices.json","id":"official-notices","label":"官方市場公告","seed":"__OFFICIAL_NOTICE_SEED__","kind":"official"},{"file":"company-disclosures.json","id":"company-disclosures","label":"個股重大訊息","seed":"__COMPANY_DISCLOSURE_SEED__","kind":"company"}];
const $=(q,r=document)=>r.querySelector(q),$$=(q,r=document)=>[...r.querySelectorAll(q)];
const escapeHtml=v=>String(v??"").replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const finite=v=>{if(v===null||v===undefined)return null;if(typeof v==="string"&&!v.trim())return null;const n=Number(String(v).replace(/,/g,""));return Number.isFinite(n)?n:null};
const fmt=(v,d=2)=>finite(v)==null?"—":Number(finite(v)).toLocaleString("zh-TW",{maximumFractionDigits:d,minimumFractionDigits:0});
const pct=v=>finite(v)==null?"—":`${Number(v)>0?"+":""}${Number(v).toFixed(2)}%`;
const cls=v=>finite(v)==null||Number(v)===0?"flat":Number(v)>0?"up":"down";
const formatTime=(v,opts={})=>{if(!v)return"—";const d=new Date(v);if(Number.isNaN(+d))return String(v);return new Intl.DateTimeFormat("zh-TW",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:opts.dateOnly?undefined:"2-digit",minute:opts.dateOnly?undefined:"2-digit",hour12:false}).format(d)};
const stripHtml=value=>String(value??"").replace(/<[^>]*>/g," ").replace(/&nbsp;/gi," ").replace(/\s+/g," ").trim();
const normalizeText=value=>stripHtml(value).toLowerCase().normalize("NFKC").replace(/[^0-9a-z\u3400-\u9fff]+/g," ").trim();
async function getJson(url,timeout=9000){const ctl=new AbortController(),id=setTimeout(()=>ctl.abort(),timeout);try{const r=await fetch(url,{cache:"no-store",signal:ctl.signal});if(!r.ok)throw Error(r.status);return await r.json()}finally{clearTimeout(id)}}
async function loadData(name,fallback={}){const branch=CHANNELS[name];if(branch){try{return await getJson(`https://raw.githubusercontent.com/${OWNER}/${REPO}/${branch}/${name}?t=${Date.now()}`)}catch(e){}}
try{return await getJson(`data/${name}?t=${Date.now()}`)}catch(e){return typeof structuredClone==="function"?structuredClone(fallback):JSON.parse(JSON.stringify(fallback))}}
async function loadNewsChannels(){
 const channels=await Promise.all(NEWS_FILES.map(async cfg=>{
  const fallback=window[cfg.seed]||{metadata:{source_id:cfg.id,source_name:cfg.label,status:"waiting",item_count:0},items:[]};
  const payload=await loadData(cfg.file,fallback);
  return {...payload,channel:cfg,items:(payload.items||[]).map(item=>({...item,source_id:item.source_id||cfg.id,source:item.source||cfg.label,channel_kind:cfg.kind}))};
 }));
 const seen=new Set(),items=[];
 for(const channel of channels){for(const item of channel.items||[]){const key=String(item.id||`${item.title||""}|${item.url||""}`);if(!key||seen.has(key))continue;seen.add(key);items.push(item)}}
 items.sort((a,b)=>Date.parse(b.published_at||b.date||0)-Date.parse(a.published_at||a.date||0));
 const updated=channels.map(c=>c.metadata?.updated_at).filter(Boolean).sort().pop()||null;
 return {metadata:{version:"v11.4.10",updated_at:updated,item_count:items.length,channel_count:channels.length},channels,items};
}
async function loadStockNews(){
 const fallback=window.__STOCK_NEWS_SEED__||{metadata:{version:"v11.4.10",status:"waiting",item_count:0},items:[]};
 return await loadData("stock-news.json",fallback);
}

const portfolioKeys=["marketRadarPortfolioV2","marketRadarPortfolio","market-radar-portfolio","portfolio"];
function loadPortfolio(){for(const k of portfolioKeys){try{const v=JSON.parse(localStorage.getItem(k)||"null");if(Array.isArray(v))return v;if(Array.isArray(v?.items))return v.items}catch(e){}}return[]}
function savePortfolio(rows){localStorage.setItem(portfolioKeys[0],JSON.stringify(rows));window.dispatchEvent(new CustomEvent("portfoliochange"))}
function mergeAssets(...payloads){const map=new Map();for(const p of payloads){for(const a of p?.assets||p?.items||[]){const key=String(a.id||`${a.market||""}:${a.symbol||""}`);map.set(key,{...(map.get(key)||{}),...a})}}return[...map.values()]}

const EVENT_ALIASES=[
  [/(?:jolts|職缺|離職率)/i,["jolts","職缺","離職率","job openings"]],
  [/(?:cpi|消費者物價)/i,["cpi","消費者物價","consumer price"]],
  [/(?:pce|個人消費支出)/i,["pce","個人消費支出","personal consumption expenditures"]],
  [/(?:fomc|聯準會|fed\b|利率決策)/i,["fomc","聯準會","fed","利率決策","federal reserve"]],
  [/(?:日本銀行|日銀|boj)/i,["日本銀行","日銀","boj","bank of japan"]],
  [/(?:非農|nonfarm|payroll)/i,["非農","nonfarm","payroll","就業報告"]],
  [/(?:gdp|國內生產毛額)/i,["gdp","國內生產毛額","gross domestic product"]],
  [/(?:pmi|採購經理人)/i,["pmi","採購經理人","purchasing managers"]],
  [/(?:財報|earnings|法說)/i,["財報","earnings","法說","財測","展望"]],
  [/(?:除息|除權|股利)/i,["除息","除權","股利","dividend"]]
];
const COMMON_EVENT_WORDS=new Set(["美國","台灣","日本","韓國","公布","會議","資料","報告","事件","公司","市場","最新","季度","月份","主要","摘要","以及","相關","資訊"]);
function relatedNews(event,items,options={}){
  const limit=options.limit||3,windowDays=options.windowDays??3;
  const title=normalizeText(`${event?.title||""} ${event?.description||event?.summary||""}`);
  const symbols=[event?.symbol,event?.asset_id,...(event?.symbols||[]),...(event?.assets||[])].filter(Boolean).map(v=>String(v).toUpperCase());
  const terms=new Set();
  for(const token of title.split(/\s+/)){if(token.length>=2&&!COMMON_EVENT_WORDS.has(token))terms.add(token)}
  for(const [pattern,aliases] of EVENT_ALIASES){if(pattern.test(`${event?.title||""} ${event?.description||event?.summary||""}`))aliases.forEach(alias=>terms.add(normalizeText(alias)))}
  const eventAt=Date.parse(event?.start||event?.local_date||event?.target_date||"");
  return (items||[]).map(item=>{
    const text=normalizeText(`${item.title||""} ${item.ai_summary||item.summary||""} ${(item.event_terms||[]).join(" ")}`);
    const itemSymbols=(item.symbols||[]).map(v=>String(v).toUpperCase());
    let score=0;
    const exactSymbols=symbols.filter(symbol=>itemSymbols.includes(symbol)||new RegExp(`(^|\\D)${symbol.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}(\\D|$)`).test(text));
    if(exactSymbols.length)score+=100+exactSymbols.length*10;
    for(const term of terms){if(term&&text.includes(term))score+=term.length>=5?8:4}
    const published=Date.parse(item.published_at||item.date||"");
    if(Number.isFinite(eventAt)&&Number.isFinite(published)){
      const days=Math.abs(published-eventAt)/86400000;
      if(days>windowDays)return null;
      score+=Math.max(0,12-days*3);
    }
    if(item.is_major)score+=2;
    return score>=10?{...item,_relatedScore:score}:null;
  }).filter(Boolean).sort((a,b)=>b._relatedScore-a._relatedScore||Date.parse(b.published_at||0)-Date.parse(a.published_at||0)).slice(0,limit);
}
window.MR={$,$$,escapeHtml,finite,fmt,pct,cls,formatTime,stripHtml,normalizeText,relatedNews,loadData,loadNewsChannels,loadStockNews,getJson,loadPortfolio,savePortfolio,mergeAssets,NEWS_FILES,OWNER,REPO};
})();
