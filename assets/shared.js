(()=>{"use strict";
const OWNER="qwe70542asd-blip",REPO="market-event-radar";
const CHANNELS={"assets.json":"live-assets","asset-audit.json":"live-assets","asset-coverage.json":"live-assets","events.json":"live-events","event-source-state.json":"live-events","tw-market.json":"live-tw-market","tw-chips.json":"live-tw-chips","market-snapshot.json":"live-global-market","news.json":"live-news"};
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
window.MR={$,$$,escapeHtml,finite,fmt,pct,cls,formatTime,stripHtml,normalizeText,relatedNews,loadData,getJson,loadPortfolio,savePortfolio,mergeAssets,OWNER,REPO};
})();
