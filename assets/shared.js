(()=>{"use strict";
const OWNER="qwe70542asd-blip",REPO="market-event-radar",APP_VERSION="v11.4.58";
let LIVE_MARKET_ENDPOINT=String(window.MR_RUNTIME?.liveMarketEndpoint||"").replace(/\/$/,"");
let runtimeReadyPromise=null;
async function ensureRuntimeEndpoint(){
 if(runtimeReadyPromise)return await runtimeReadyPromise;
 runtimeReadyPromise=(async()=>{
  try{if(window.MR_RUNTIME_READY)await window.MR_RUNTIME_READY}catch(e){}
  const value=String(window.MR_RUNTIME?.liveMarketEndpoint||"").trim().replace(/\/$/,"");
  if(/^https:\/\//i.test(value)){
   try{const url=new URL(value);LIVE_MARKET_ENDPOINT=(!url.username&&!url.password)?url.origin+url.pathname.replace(/\/$/,""):""}catch(e){LIVE_MARKET_ENDPOINT=""}
  }else LIVE_MARKET_ENDPOINT="";
  return LIVE_MARKET_ENDPOINT;
 })();
 return await runtimeReadyPromise;
}
const getLiveMarketEndpoint=()=>LIVE_MARKET_ENDPOINT;
const CHANNELS={"assets.json":"live-assets","asset-audit.json":"live-assets","asset-coverage.json":"live-assets","events.json":"live-events","event-source-state.json":"live-events","tw-market.json":"live-tw-market","tw-chips.json":"live-tw-chips","market-snapshot.json":"live-global-market","market-kline.json":"live-global-market","news-cna.json":"live-news-cna","news-moneydj.json":"live-news-moneydj","news-cnyes.json":"live-news-cnyes","news-udn.json":"live-news-udn","news-ltn.json":"live-news-ltn","news-wealth.json":"live-news-wealth","news-yahoo.json":"live-news-yahoo","news-technews.json":"live-news-technews","news-ctee.json":"live-news-ctee","news-asia-risk.json":"live-news-asia-risk","stock-news.json":"live-stock-news","official-market-notices.json":"live-official-notices","company-disclosures.json":"live-company-disclosures","monthly-revenue.json":"live-monthly-revenue","dividend-history.json":"live-dividend-history","market-volume-history.json":"live-tw-market","secondary-reference.json":"live-secondary-reference","data-verification.json":"live-data-verification","channel-health.json":"live-data-verification","asset-detail-shard-0.json":"live-data-verification","asset-detail-shard-1.json":"live-data-verification","asset-detail-shard-2.json":"live-data-verification","asset-detail-shard-3.json":"live-data-verification","asset-detail-shard-4.json":"live-data-verification","asset-detail-shard-5.json":"live-data-verification","asset-detail-shard-6.json":"live-data-verification","asset-detail-shard-7.json":"live-data-verification","asset-detail-shard-8.json":"live-data-verification","asset-detail-shard-9.json":"live-data-verification","yahoo-details.json":"live-yahoo-details","etf-details.json":"live-etf-details","stock-basics.json":"live-stock-basics"};
const NEWS_FILES=[{"file":"news-cna.json","id":"cna","label":"中央社","seed":"__NEWS_CNA_SEED__","kind":"media"},{"file":"news-moneydj.json","id":"moneydj","label":"MoneyDJ","seed":"__NEWS_MONEYDJ_SEED__","kind":"media"},{"file":"news-cnyes.json","id":"cnyes","label":"鉅亨網","seed":"__NEWS_CNYES_SEED__","kind":"media"},{"file":"news-udn.json","id":"udn","label":"經濟日報","seed":"__NEWS_UDN_SEED__","kind":"media"},{"file":"news-ltn.json","id":"ltn","label":"自由財經","seed":"__NEWS_LTN_SEED__","kind":"media"},{"file":"news-wealth.json","id":"wealth","label":"財富自由","seed":"__NEWS_WEALTH_SEED__","kind":"media"},{"file":"news-yahoo.json","id":"yahoo","label":"Yahoo股市","seed":"__NEWS_YAHOO_SEED__","kind":"media"},{"file":"news-technews.json","id":"technews","label":"科技新報／財經新報","seed":"__NEWS_TECHNEWS_SEED__","kind":"media"},{"file":"news-ctee.json","id":"ctee","label":"工商時報","seed":"__NEWS_CTEE_SEED__","kind":"media"},{"file":"news-asia-risk.json","id":"asia-risk","label":"亞洲總體風險","seed":"__NEWS_ASIA_RISK_SEED__","kind":"media"},{"file":"official-market-notices.json","id":"official-notices","label":"官方市場公告","seed":"__OFFICIAL_NOTICE_SEED__","kind":"official"},{"file":"company-disclosures.json","id":"company-disclosures","label":"個股重大訊息","seed":"__COMPANY_DISCLOSURE_SEED__","kind":"company"}];
const $=(q,r=document)=>r.querySelector(q),$$=(q,r=document)=>[...r.querySelectorAll(q)];
const escapeHtml=v=>String(v??"").replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const finite=v=>{if(v===null||v===undefined)return null;if(typeof v==="string"&&!v.trim())return null;const n=Number(String(v).replace(/,/g,""));return Number.isFinite(n)?n:null};
const fmt=(v,d=2)=>finite(v)==null?"—":Number(finite(v)).toLocaleString("zh-TW",{maximumFractionDigits:d,minimumFractionDigits:0});
const pct=v=>finite(v)==null?"—":`${Number(v)>0?"+":""}${Number(v).toFixed(2)}%`;
const cls=v=>finite(v)==null||Number(v)===0?"flat":Number(v)>0?"up":"down";
const formatTime=(v,opts={})=>{if(!v)return"—";const d=new Date(v);if(Number.isNaN(+d))return String(v);return new Intl.DateTimeFormat("zh-TW",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:opts.dateOnly?undefined:"2-digit",minute:opts.dateOnly?undefined:"2-digit",hour12:false}).format(d)};
const formatEventTime=event=>{
 const dateOnly=event?.all_day===true||event?.time_status==="date-only";
 const local=String(event?.local_date||event?.target_date||event?.ex_date||"").match(/^\d{4}-\d{2}-\d{2}/)?.[0]||"";
 if(dateOnly&&local)return formatTime(`${local}T12:00:00+08:00`,{dateOnly:true});
 return formatTime(event?.start||local,{dateOnly});
};
const stripHtml=value=>String(value??"").replace(/<[^>]*>/g," ").replace(/&nbsp;/gi," ").replace(/\s+/g," ").trim();
const normalizeText=value=>stripHtml(value).toLowerCase().normalize("NFKC").replace(/[^0-9a-z\u3400-\u9fff]+/g," ").trim();
const safeHttpUrl=(value,{allowHttp=false}={})=>{
 const text=String(value||"").trim();if(!text)return "";
 try{const url=new URL(text,location.href);if(url.username||url.password)return "";if(url.origin===location.origin)return url.href;if(url.protocol==="https:"||(allowHttp&&url.protocol==="http:"))return url.href}catch(e){}
 return "";
};
const safeExternalHref=value=>safeHttpUrl(value);
const GENERIC_NEWS_IMAGE_RE=/(?:og-image|default(?:_og)?|logo|placeholder|no[-_]?image|blank|icon|avatar|sprite|favicon|google-prefer(?:ed|red)-source-illustration|pic_fb|line-ad)(?:[._/-]|$)/i;
const newsImageCandidates=item=>[item?.image_url,...(Array.isArray(item?.image_candidates)?item.image_candidates:[])].map(value=>String(value||"").trim()).filter((url,index,rows)=>/^https:\/\//i.test(url)&&!GENERIC_NEWS_IMAGE_RE.test(url)&&rows.indexOf(url)===index);
const newsHasImage=item=>newsImageCandidates(item).length>0;
function advanceNewsImage(img){try{const candidates=JSON.parse(decodeURIComponent(img.dataset.candidates||"%5B%5D"));const next=Number(img.dataset.candidateIndex||0)+1;if(next<candidates.length){img.dataset.candidateIndex=String(next);img.src=candidates[next];return}img.style.display="none";img.parentElement?.classList.add("fallback","remote-image-failed")}catch(e){img.style.display="none";img.parentElement?.classList.add("fallback","remote-image-failed")}}
function pickNewsFallbackSlug(item={}){
 const text=`${item.title||""} ${item.ai_summary||item.summary||""} ${item.ai_category||item.topic||""} ${item.ai_topic||""}`;
 if(/台積電|鴻海|聯發科|廣達|緯創|半導體|晶圓|記憶體|AI|伺服器|NVIDIA|輝達|AMD|Intel|科技/.test(text))return"technology";
 if(/財報|EPS|營收|獲利|法說|展望|毛利|淨利/.test(text))return"earnings";
 if(/聯準會|央行|升息|降息|利率|殖利率|債券|FOMC|BOJ|日銀/.test(text))return"rates";
 if(/關稅|政策|法案|行政命令|監管|禁令|財政部|商務部|白宮/.test(text))return"policy";
 if(/戰爭|以伊|中東|俄烏|制裁|地緣|軍事/.test(text))return"geopolitics";
 if(/原油|石油|金價|黃金|銅價|天然氣|原物料|運價/.test(text))return"commodities";
 if(/GDP|CPI|PCE|非農|PMI|景氣|通膨|衰退|失業|總經/.test(text))return"macro";
 if(/美股|日股|韓股|歐股|中國|全球|國際|亞股|道瓊|NASDAQ|S&P/.test(text))return"global";
 if(/台股|加權|大盤|指數|成交量|盤中|開高走低|創高|跌點/.test(text))return"market";
 return"stock";
}
function renderNewsThumb(item,kind="tile",options={}){
 const alt=escapeHtml(options.alt||item?.title||item?.ai_category||"新聞配圖");
 const slug=escapeHtml(item?.fallback_image_slug||pickNewsFallbackSlug(item));
 const label=escapeHtml(item?.ai_category||item?.topic||"市場資訊");
 const fallback=`assets/news-fallback/${slug}.svg`,loading=options.eager?"eager":"lazy",priority=options.eager?' fetchpriority="high"':'';
 const candidates=newsImageCandidates(item);
 if(candidates.length){const encoded=escapeHtml(encodeURIComponent(JSON.stringify(candidates)));return `<div class="news-thumb ${kind}" data-fallback="${slug}" style="background-image:url('${fallback}')"><img src="${escapeHtml(candidates[0])}" data-news-remote="1" data-candidates="${encoded}" data-candidate-index="0" data-fallback-src="${fallback}" alt="${alt}" loading="${loading}"${priority} decoding="async" referrerpolicy="no-referrer"><span class="fallback-label">${label}</span></div>`;}
 return `<div class="news-thumb ${kind} fallback" data-fallback="${slug}" style="background-image:url('${fallback}')"><img src="${fallback}" alt="${alt}" loading="${loading}"${priority} decoding="async"><span class="fallback-label">${label}</span></div>`;
}
document.addEventListener("load",event=>{const img=event.target;if(img instanceof HTMLImageElement&&img.dataset.newsRemote==="1"){img.dataset.loaded="true";img.parentElement?.classList.add("remote-image-loaded")}},true);
document.addEventListener("error",event=>{const img=event.target;if(img instanceof HTMLImageElement&&img.dataset.newsRemote==="1")advanceNewsImage(img)},true);
async function getJson(url,timeout=9000){const ctl=new AbortController(),id=setTimeout(()=>ctl.abort(),timeout);try{const r=await fetch(url,{cache:"no-store",headers:{Accept:"application/json"},signal:ctl.signal});if(!r.ok)throw Error(r.status);return await r.json()}finally{clearTimeout(id)}}
const FRESH_BRANCH_FILES=new Set(["market-snapshot.json","market-kline.json","tw-market.json","market-volume-history.json","events.json"]);
const cloneValue=value=>typeof structuredClone==="function"?structuredClone(value):JSON.parse(JSON.stringify(value));
function decodeGitHubContent(value){const binary=atob(String(value||"").replace(/\s+/g,"")),bytes=Uint8Array.from(binary,char=>char.charCodeAt(0));return JSON.parse(new TextDecoder("utf-8").decode(bytes))}
async function loadBranchApi(name,branch){
 const url=`https://api.github.com/repos/${OWNER}/${REPO}/contents/${encodeURIComponent(name)}?ref=${encodeURIComponent(branch)}&_=${Date.now()}`;
 const meta=await getJson(url,11000);
 if(meta?.encoding==="base64"&&meta?.content)return decodeGitHubContent(meta.content);
 if(meta?.download_url)return await getJson(`${meta.download_url}${meta.download_url.includes("?")?"&":"?"}sha=${encodeURIComponent(meta.sha||Date.now())}`,11000);
 throw Error("GitHub contents API returned no JSON content");
}
const snapshotCacheKeys=["mr-market-snapshot-last-good-v1","mr-market-snapshot-last-good-v11.4.46","mr-market-snapshot-last-good-v11.4.31","mr-market-snapshot-last-good-v11.4.28","mr-market-snapshot-last-good-v11.4.27"];
const snapshotCacheKey=snapshotCacheKeys[0];
const DATA_MEMORY=new Map();
// Small hot-path session cache stays in Web Storage.  Durable last-known-good
// snapshots for every live channel use IndexedDB so a multi-megabyte events or
// news archive never competes with localStorage's small quota.
const WEB_STORAGE_CACHE_FILES=new Set(["market-snapshot.json","tw-market.json"]);
// News and diagnostic archives are intentionally session-only.  Keeping old
// full copies in IndexedDB caused storage growth without improving the live UI.
const EPHEMERAL_LARGE_FILES=new Set(["stock-news.json","official-market-notices.json","company-disclosures.json","data-verification.json",...NEWS_FILES.map(row=>row.file)]);
const dataCacheKey=name=>`mr-data-cache-v1:${name}`;
const lastGoodKey=name=>`mr-data-last-good-v1:${name}`;
const STORAGE_CLEANUP_KEY="mr-storage-cleanup-v2";
const LAST_GOOD_DB="market-radar-last-good-v1",LAST_GOOD_STORE="payloads";
let lastGoodDbPromise=null;
function openLastGoodDb(){
 if(!("indexedDB" in window))return Promise.resolve(null);
 if(lastGoodDbPromise)return lastGoodDbPromise;
 lastGoodDbPromise=new Promise(resolve=>{try{const request=indexedDB.open(LAST_GOOD_DB,1);request.onupgradeneeded=()=>{const db=request.result;if(!db.objectStoreNames.contains(LAST_GOOD_STORE))db.createObjectStore(LAST_GOOD_STORE)};request.onsuccess=()=>resolve(request.result);request.onerror=()=>resolve(null)}catch(e){resolve(null)}});
 return lastGoodDbPromise;
}
async function idbGet(name){const db=await openLastGoodDb();if(!db)return null;return await new Promise(resolve=>{try{const tx=db.transaction(LAST_GOOD_STORE,"readonly"),req=tx.objectStore(LAST_GOOD_STORE).get(name);req.onsuccess=()=>resolve(req.result||null);req.onerror=()=>resolve(null)}catch(e){resolve(null)}})}
async function idbPut(name,value){const db=await openLastGoodDb();if(!db)return;await new Promise(resolve=>{try{const tx=db.transaction(LAST_GOOD_STORE,"readwrite");tx.objectStore(LAST_GOOD_STORE).put(value,name);tx.oncomplete=()=>resolve();tx.onerror=()=>resolve();tx.onabort=()=>resolve()}catch(e){resolve()}})}
async function idbDelete(name){const db=await openLastGoodDb();if(!db)return;await new Promise(resolve=>{try{const tx=db.transaction(LAST_GOOD_STORE,"readwrite");tx.objectStore(LAST_GOOD_STORE).delete(name);tx.oncomplete=()=>resolve();tx.onerror=()=>resolve();tx.onabort=()=>resolve()}catch(e){resolve()}})}
void Promise.all([...EPHEMERAL_LARGE_FILES].map(name=>idbDelete(name)));
try{
 if(localStorage.getItem(STORAGE_CLEANUP_KEY)!=="1"){
  for(const name of Object.keys(CHANNELS)){
   if(!WEB_STORAGE_CACHE_FILES.has(name)){localStorage.removeItem(lastGoodKey(name));sessionStorage.removeItem(dataCacheKey(name))}
   for(const version of ["v11.4.46","v11.4.31","v11.4.28","v11.4.27","v11.4.26"])sessionStorage.removeItem(`mr-data-cache-${version}:${name}`);
  }
  localStorage.setItem(STORAGE_CLEANUP_KEY,"1");
 }
}catch(e){}
const dataCacheTtl=name=>["market-snapshot.json","market-kline.json","tw-market.json","events.json"].includes(name)?30000:300000;
const DATA_MAX_AGE_MS={"assets.json":36*60*60*1000,"asset-audit.json":36*60*60*1000,"official-market-notices.json":12*60*60*1000,"company-disclosures.json":12*60*60*1000,"market-snapshot.json":20*60*1000,"market-kline.json":2*60*60*1000,"tw-market.json":3*60*60*1000,"tw-chips.json":72*60*60*1000,"events.json":12*60*60*1000,"stock-news.json":3*60*60*1000,"monthly-revenue.json":18*60*60*1000,"dividend-history.json":18*60*60*1000,"yahoo-details.json":96*60*60*1000,"etf-details.json":72*60*60*1000,"stock-basics.json":36*60*60*1000,"secondary-reference.json":36*60*60*1000,"data-verification.json":3*60*60*1000,"channel-health.json":45*60*1000,"asset-detail-shard-0.json":45*60*1000,"asset-detail-shard-1.json":45*60*1000,"asset-detail-shard-2.json":45*60*1000,"asset-detail-shard-3.json":45*60*1000,"asset-detail-shard-4.json":45*60*1000,"asset-detail-shard-5.json":45*60*1000,"asset-detail-shard-6.json":45*60*1000,"asset-detail-shard-7.json":45*60*1000,"asset-detail-shard-8.json":45*60*1000,"asset-detail-shard-9.json":45*60*1000};
const NEWS_RETENTION_MS=20*86400000,NEWS_CHANNEL_MEMORY_LIMIT=180,NEWS_MERGED_MEMORY_LIMIT=800;
const metadataAgeMs=payload=>{const at=Date.parse(payload?.metadata?.updated_at||0);return Number.isFinite(at)?Math.max(0,Date.now()-at):Infinity};
function annotateFrontendFreshness(name,payload,source){
 if(!payload||typeof payload!=="object")return payload;
 const max=DATA_MAX_AGE_MS[name]||(/^news-/.test(name)?3*60*60*1000:null),age=metadataAgeMs(payload),raw=String(payload?.metadata?.status||"").toLowerCase();
 const explicitBad=["failed","error","unavailable","circuit-open","stale"].includes(raw),tooOld=Number.isFinite(max)&&age>max,lastGood=source==="browser-last-good";
 if(!payload.metadata)return payload;
 const frontendStatus=explicitBad?raw:tooOld?"stale":lastGood?"fallback":raw||"unknown";
 return {...payload,metadata:{...payload.metadata,frontend_status:frontendStatus,frontend_stale:tooOld,frontend_age_seconds:Number.isFinite(age)?Math.round(age/1000):null,frontend_max_age_seconds:Number.isFinite(max)?Math.round(max/1000):null,frontend_last_good:lastGood,frontend_load_source:source||payload.metadata.frontend_load_source}};
}
const snapshotCandleCount=row=>(Array.isArray(row?.candles)?row.candles:[]).filter(candle=>candle?.date&&[candle.open,candle.high,candle.low,candle.close].every(value=>finite(value)!=null)).length;
const loadStored=(keys=[])=>{for(const key of keys){try{const value=JSON.parse(localStorage.getItem(key)||"null");if(value)return value}catch(e){}}return null};
const isUsablePayload=(name,payload)=>{
 if(!payload||typeof payload!=="object")return false;
 if(name==="market-snapshot.json")return (payload.items||[]).filter(row=>finite(row?.price)!=null&&snapshotCandleCount(row)>=10).length>=4;
 if(name==="tw-market.json")return (payload.items||[]).filter(row=>finite(row?.price)!=null).length>=10;
 if(name==="market-kline.json"){const items=payload.items||{};return !!payload.metadata?.updated_at&&typeof items==="object"&&Object.keys(items).length>0;}
 if(name==="events.json")return Array.isArray(payload.events)&&payload.events.length>0;
 // An updated_at timestamp is not evidence that a collection is complete.
 // Empty/accidentally truncated live files must fall through to last-known-good.
 if(Array.isArray(payload.items))return payload.items.length>0;
 if(payload.items&&typeof payload.items==="object")return Object.keys(payload.items).length>0;
 if(Array.isArray(payload.assets))return payload.assets.length>0;
 return !!payload.metadata?.updated_at||Object.keys(payload).length>1;
};
const payloadCardinality=(name,payload)=>{
 if(!payload||typeof payload!=="object")return 0;
 if(name==="events.json")return Array.isArray(payload.events)?payload.events.length:0;
 if(Array.isArray(payload.items))return payload.items.length;
 if(payload.items&&typeof payload.items==="object")return Object.keys(payload.items).length;
 if(Array.isArray(payload.assets))return payload.assets.length;
 return 0;
};
const ARCHIVE_REGRESSION_FILES=new Set(["events.json","assets.json","stock-basics.json","yahoo-details.json","etf-details.json","monthly-revenue.json","dividend-history.json","data-verification.json","market-kline.json","market-volume-history.json","tw-chips.json","secondary-reference.json",...Array.from({length:10},(_,index)=>`asset-detail-shard-${index}.json`)]);
function isCatastrophicPayloadRegression(name,candidate,lastGood){
 if(!ARCHIVE_REGRESSION_FILES.has(name)||!lastGood)return false;
 const before=payloadCardinality(name,lastGood),after=payloadCardinality(name,candidate);
 if(before<25)return false;
 // Event history is an append/retain archive, so even a 30% collapse is invalid.
 // Other master/history channels use a wider 55% loss threshold to avoid blocking
 // ordinary membership churn while still catching a broken one-page/partial scrape.
 const floor=name==="events.json"?Math.max(25,Math.floor(before*0.70)):before>=100?Math.max(25,Math.floor(before*0.45)):0;
 return floor>0&&after<floor;
}
function mergeSnapshotCache(payload){
 const cached=loadStored(snapshotCacheKeys);
 if(!cached?.items?.length)return payload;
 const oldMap=new Map(cached.items.map(row=>[String(row.symbol||"").toUpperCase(),row]));
 const items=(payload?.items||[]).map(row=>{const old=oldMap.get(String(row.symbol||"").toUpperCase());if(snapshotCandleCount(row)>=10||!old)return row;return {...old,...row,candles:old.candles||[],candle_count:snapshotCandleCount(old),candle_source:`${row.candle_source||row.source||"線上行情"}／瀏覽器上次成功 K 線`,data_status:row.data_status==="live"?"cached-kline":row.data_status};});
 return {...payload,items};
}
async function rememberLastGood(name,payload){
 if(EPHEMERAL_LARGE_FILES.has(name)||!isUsablePayload(name,payload))return;
 // Yield before cloning/writing multi-megabyte payloads so last-good persistence
 // can never hold up the live-data promise that drives mounted UI rerenders.
 await new Promise(resolve=>setTimeout(resolve,0));
 const entry={at:Date.now(),payload:cloneValue(payload)};
 // IndexedDB is the durable cache for all channels.  Keep the compact market
 // snapshot in localStorage as a compatibility path for older installations.
 await idbPut(name,entry);
 if(WEB_STORAGE_CACHE_FILES.has(name)){try{const serialized=JSON.stringify(payload);localStorage.setItem(lastGoodKey(name),serialized);if(name==="market-snapshot.json")localStorage.setItem(snapshotCacheKey,serialized)}catch(e){}}
}
async function readLastGood(name){
 if(EPHEMERAL_LARGE_FILES.has(name))return null;
 const indexed=await idbGet(name);if(isUsablePayload(name,indexed?.payload))return indexed.payload;
 if(WEB_STORAGE_CACHE_FILES.has(name)){try{const value=JSON.parse(localStorage.getItem(lastGoodKey(name))||"null");if(isUsablePayload(name,value))return value}catch(e){}}
 for(const legacy of [`mr-data-cache-v11.4.46:${name}`,`mr-data-cache-v11.4.31:${name}`,`mr-data-cache-v11.4.28:${name}`,`mr-data-cache-v11.4.27:${name}`,`mr-data-cache-v11.4.26:${name}`]){try{const entry=JSON.parse(sessionStorage.getItem(legacy)||"null");if(isUsablePayload(name,entry?.payload)){await rememberLastGood(name,entry.payload);return entry.payload}}catch(e){}}
 if(name==="market-snapshot.json"){const value=loadStored(snapshotCacheKeys);if(isUsablePayload(name,value))return value}
 return null;
}
async function loadRawBranch(name,branch,timeout=6200){return await getJson(`https://raw.githubusercontent.com/${OWNER}/${REPO}/${branch}/${name}?t=${Date.now()}`,timeout)}
async function loadJsDelivr(name,branch,timeout=6200){return await getJson(`https://cdn.jsdelivr.net/gh/${OWNER}/${REPO}@${branch}/${name}?t=${Date.now()}`,timeout)}
async function loadStatically(name,branch,timeout=6200){return await getJson(`https://cdn.statically.io/gh/${OWNER}/${REPO}/${branch}/${name}?t=${Date.now()}`,timeout)}
// GitHub Contents API is rate-limited for anonymous clients and is a poor
// fallback for large generated JSON.  Large channels use three direct/CDN
// mirrors instead; smaller payloads keep the API as a final metadata-aware
// fallback.
const LARGE_BRANCH_FILES=new Set(["events.json","market-kline.json","assets.json","asset-audit.json","stock-basics.json","yahoo-details.json","etf-details.json","data-verification.json","company-disclosures.json","stock-news.json"]);
async function loadLiveBranchFast(name,branch){
 // Hedged mirrors: Raw starts immediately, CDN mirrors are started only when
 // the first path is slow.  This avoids the old 15-20 second sequential worst
 // case without going back to firing every mirror at once on a healthy path.
 const candidates=[
  ["raw-live-branch",()=>loadRawBranch(name,branch)],
  ["jsdelivr-live-branch",()=>loadJsDelivr(name,branch)],
  ["statically-live-branch",()=>loadStatically(name,branch)],
 ];
 if(!LARGE_BRANCH_FILES.has(name))candidates.push(["github-api-live-branch",()=>loadBranchApi(name,branch)]);
 return await new Promise((resolve,reject)=>{
  let settled=false,finished=0,lastError=Error("live branch unavailable");
  const launch=(entry,index)=>setTimeout(async()=>{if(settled)return;const [source,loader]=entry;try{const payload=await loader();if(settled)return;if(isUsablePayload(name,payload)){settled=true;resolve({payload,source});return}lastError=Error(`${source} unusable`)}catch(error){lastError=error}finally{finished++;if(!settled&&finished===candidates.length)reject(lastError)}},index*850);
  candidates.forEach(launch);
 });
}
const DATA_INFLIGHT=new Map();
async function _loadData(name,fallback={},options={}){
 const ttl=dataCacheTtl(name),now=Date.now();
 if(!options.force){
  const memory=DATA_MEMORY.get(name);if(memory&&now-memory.at<ttl&&isUsablePayload(name,memory.payload))return cloneValue(memory.payload);
  if(WEB_STORAGE_CACHE_FILES.has(name)){try{const cached=JSON.parse(sessionStorage.getItem(dataCacheKey(name))||"null");if(cached&&now-cached.at<ttl&&isUsablePayload(name,cached.payload)){DATA_MEMORY.set(name,cached);return cloneValue(cached.payload)}}catch(e){}}
 }
 const branch=CHANNELS[name];let payload=null,source="";
 // Read the durable snapshot before accepting a remote replacement.  A payload
 // can be syntactically valid yet catastrophically incomplete (the class of
 // regression that previously hid most calendar events).
 const lastGoodForGuard=(branch||name==="market-snapshot.json")?await readLastGood(name):null;
 const acceptRemote=(candidate,candidateSource)=>{
  if(!isUsablePayload(name,candidate))return false;
  if(isCatastrophicPayloadRegression(name,candidate,lastGoodForGuard)){console.warn(`Rejected catastrophic ${name} shrink from ${payloadCardinality(name,lastGoodForGuard)} to ${payloadCardinality(name,candidate)} (${candidateSource})`);return false}
  payload=candidate;source=candidateSource;return true;
 };
 const endpoint=name==="market-snapshot.json"?await ensureRuntimeEndpoint():"";
 if(name==="market-snapshot.json"&&endpoint){try{acceptRemote(await getJson(`${endpoint}/market-snapshot.json?_=${Date.now()}`,6000),"worker")}catch(e){}}
 if(branch&&!payload){try{const live=await loadLiveBranchFast(name,branch);acceptRemote(live.payload,live.source)}catch(e){}}
 if(!payload&&lastGoodForGuard){payload=lastGoodForGuard;source="browser-last-good"}
 if(!payload&&!lastGoodForGuard){const cached=await readLastGood(name);if(cached){payload=cached;source="browser-last-good"}}
 if(!payload){try{const candidate=await getJson(`data/${name}?t=${Date.now()}`,5000);if(isUsablePayload(name,candidate)){payload=candidate;source="same-origin-main"}}catch(e){}}
 if(!payload)payload=cloneValue(fallback);
 if(name==="market-snapshot.json")payload=mergeSnapshotCache(payload||cloneValue(fallback));
 if(payload?.metadata)payload=annotateFrontendFreshness(name,payload,source);
 if(isUsablePayload(name,payload))void rememberLastGood(name,payload);
 const entry={at:Date.now(),payload};DATA_MEMORY.set(name,entry);if(WEB_STORAGE_CACHE_FILES.has(name)){try{sessionStorage.setItem(dataCacheKey(name),JSON.stringify(entry))}catch(e){}}
 return cloneValue(payload);
}
async function loadData(name,fallback={},options={}){
 if(options.force)return await _loadData(name,fallback,options);
 const active=DATA_INFLIGHT.get(name);if(active)return cloneValue(await active);
 const promise=_loadData(name,fallback,options).finally(()=>DATA_INFLIGHT.delete(name));
 DATA_INFLIGHT.set(name,promise);
 return cloneValue(await promise);
}
const STOCK_BASIC_ENDPOINTS=[
 {url:"https://openapi.twse.com.tw/v1/opendata/t187ap03_L",exchange:"TWSE",source:"TWSE 上市公司基本資料"},
 {url:"https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",exchange:"TPEx",source:"TPEx 上櫃公司基本資料"}
];
const basicField=(row,...labels)=>{for(const label of labels){if(row?.[label]!=null&&String(row[label]).trim())return row[label]}for(const [key,value] of Object.entries(row||{})){if(labels.some(label=>String(key).includes(label))&&value!=null&&String(value).trim())return value}return null};
const basicDate=value=>{const text=String(value||"").trim();if(!text)return"";const token=text.replace(/[年.]/g,"/").replace(/月/g,"/").replace(/日/g,"");let y,m,d,hit=token.match(/(?:^|\D)(\d{4})[\/-](\d{1,2})[\/-](\d{1,2})(?!\d)/);if(hit){y=Number(hit[1]);m=Number(hit[2]);d=Number(hit[3])}else{hit=token.match(/(?:^|\D)(\d{2,3})[\/-](\d{1,2})[\/-](\d{1,2})(?!\d)/);if(hit){y=Number(hit[1])+1911;m=Number(hit[2]);d=Number(hit[3])}else{const compact=text.replace(/\s+/g,"").match(/(?:^|\D)(\d{8}|\d{6,7})(?!\d)/);if(!compact)return"";const raw=compact[1];if(raw.length===8){y=Number(raw.slice(0,4));m=Number(raw.slice(4,6));d=Number(raw.slice(6,8))}else{const n=raw.length-4;y=Number(raw.slice(0,n))+1911;m=Number(raw.slice(n,n+2));d=Number(raw.slice(-2))}}}if(!Number.isInteger(y)||y<1800||y>new Date().getFullYear()+1)return"";const probe=new Date(Date.UTC(y,m-1,d));if(probe.getUTCFullYear()!==y||probe.getUTCMonth()!==m-1||probe.getUTCDate()!==d)return"";return`${String(y).padStart(4,"0")}-${String(m).padStart(2,"0")}-${String(d).padStart(2,"0")}`};
const saneBasicDates=(established,listed)=>{const listedDate=basicDate(listed),establishedDate=basicDate(established),today=new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());return{listed_date:listedDate&&listedDate<=today?listedDate:"",established_date:establishedDate&&establishedDate<=today&&(!listedDate||establishedDate<=listedDate)?establishedDate:""}};
const basicNumber=value=>{const m=String(value||"").replace(/,/g,"").match(/[-+]?\d+(?:\.\d+)?/);return m?Number(m[0]):null};
function officialBasicRecord(row,endpoint){
 const symbol=String(basicField(row,"公司代號","公司代碼","SecuritiesCompanyCode")||"").trim().toUpperCase();
 if(!/^\d{4,6}[A-Z]?$/.test(symbol))return null;
 const yahooSymbol=endpoint.exchange==="TPEx"?`${symbol}.TWO`:symbol;
 const dates=saneBasicDates(basicField(row,"成立日期","DateOfIncorporation"),basicField(row,"上市日期","上櫃日期","DateOfListing"));
 const record={symbol,company_name:String(basicField(row,"公司名稱","CompanyName")||"").trim(),short_name:String(basicField(row,"公司簡稱","CompanyAbbreviation")||"").trim(),asset_class:"stock",market:"TW",exchange:endpoint.exchange,market_label:endpoint.exchange==="TWSE"?"上市":"上櫃",currency:"TWD",industry:String(basicField(row,"產業別","產業類別","Industry")||"").trim(),address:String(basicField(row,"住址","地址","Address")||"").trim(),tax_id:String(basicField(row,"營利事業統一編號","統一編號","UnifiedBusinessNo")||"").trim(),chairperson:String(basicField(row,"董事長","Chairman")||"").trim(),general_manager:String(basicField(row,"總經理","GeneralManager")||"").trim(),spokesperson:String(basicField(row,"發言人","Spokesman")||"").trim(),phone:String(basicField(row,"總機電話","Telephone")||"").trim(),established_date:dates.established_date,listed_date:dates.listed_date,paid_in_capital:basicNumber(basicField(row,"實收資本額","PaidinCapital")),issued_shares:basicNumber(basicField(row,"已發行普通股數","已發行普通股數或TDR原股發行股數","IssuedShares")),website:String(basicField(row,"網址","URL","公司網站")||"").trim(),email:String(basicField(row,"電子郵件信箱","Email")||"").trim(),accounting_firm:String(basicField(row,"簽證會計師事務所")||"").trim(),source:endpoint.source,source_level:"official",source_url:endpoint.url,official_url:`https://mops.twse.com.tw/mops/web/t05st03?step=1&off=1&firstin=1&co_id=${symbol}`,profile_url:`https://tw.stock.yahoo.com/quote/${yahooSymbol}/profile`,quote_url:`https://tw.stock.yahoo.com/quote/${yahooSymbol}`,financial_url:`https://tw.stock.yahoo.com/quote/${yahooSymbol}/income-statement`};
 const fields=[record.symbol,record.company_name||record.short_name,record.asset_class,record.market,record.exchange,record.industry,record.currency,record.listed_date,record.paid_in_capital,record.issued_shares,record.official_url,record.profile_url];
 record.basic_coverage_percent=Math.round(fields.filter(value=>value!==null&&value!==undefined&&String(value).trim()!=="").length/fields.length*1000)/10;const metrics=record.metrics||{};const mf=["pe","pb","dividend_yield","eps","roe","debt_ratio","net_margin","current_ratio"].filter(key=>finite(metrics[key])!=null).length;record.financial_coverage_percent=Math.round((mf/8*.6+Math.min((record.financials||[]).length,12)/12*.4)*1000)/10;
 record.updated_at=new Date().toISOString();return record;
}
async function loadStockBasics(){
 const fallback=window.__STOCK_BASICS_SEED__||{metadata:{status:"waiting",item_count:0},items:{}};
 const payload=await loadData("stock-basics.json",fallback),items={...(payload.items||{})};
 if(Object.keys(items).length>=500)return payload;
 const settled=await Promise.allSettled(STOCK_BASIC_ENDPOINTS.map(async endpoint=>({endpoint,rows:await getJson(endpoint.url,15000)})));
 let added=0;
 for(const result of settled){if(result.status!=="fulfilled"||!Array.isArray(result.value.rows))continue;for(const row of result.value.rows){const record=officialBasicRecord(row,result.value.endpoint);if(!record)continue;items[record.symbol]={...(items[record.symbol]||{}),...record};added++}}
 const values=Object.values(items),average=values.length?values.reduce((sum,row)=>sum+Number(row.basic_coverage_percent||0),0)/values.length:0;
 return {...payload,metadata:{...(payload.metadata||{}),version:APP_VERSION,item_count:values.length,average_basic_coverage_percent:Math.round(average*10)/10,scope:"all-currently-listed-twse-and-tpex-stocks",browser_official_fallback_added:added},items};
}
function normalizeNewsChannel(cfg,payload){
 const floor=Date.now()-NEWS_RETENTION_MS,tomorrow=Date.now()+86400000;
 const rows=(payload?.items||[]).filter(item=>{const at=Date.parse(item.published_at||item.date||0);return Number.isFinite(at)&&at>=floor&&at<=tomorrow}).sort((a,b)=>Date.parse(b.published_at||b.date||0)-Date.parse(a.published_at||a.date||0)).slice(0,NEWS_CHANNEL_MEMORY_LIMIT).map(item=>({...item,source_id:item.source_id||cfg.id,source:item.source||cfg.label,channel_kind:cfg.kind}));
 return {...payload,channel:cfg,items:rows,metadata:{...(payload?.metadata||{}),frontend_retention_days:20,frontend_item_limit:NEWS_CHANNEL_MEMORY_LIMIT}};
}
function mergeNewsChannels(channels){
 const seen=new Set(),items=[];
 for(const channel of channels||[]){for(const item of channel?.items||[]){const key=String(item.canonical_url||item.url||item.id||item.title||"").toLowerCase();if(!key||seen.has(key))continue;seen.add(key);items.push(item)}}
 items.sort((a,b)=>Date.parse(b.published_at||b.date||0)-Date.parse(a.published_at||a.date||0));
 const kept=items.slice(0,NEWS_MERGED_MEMORY_LIMIT),updated=(channels||[]).map(c=>c?.metadata?.updated_at).filter(Boolean).sort().pop()||null;
 const bad=new Set(["warning","partial","fallback","degraded","loading","waiting","pending","seeded","stale","failed","error","unavailable","circuit-open"]);
 const resolved=(channels||[]).filter(c=>{const status=String(c?.metadata?.frontend_status||c?.metadata?.status||"").toLowerCase();return !bad.has(status)&&(c?.metadata?.updated_at||Number(c?.items?.length||0)>0)}).length;
 const summaries=(channels||[]).map(c=>({channel:c.channel,metadata:c.metadata||{},health:c.health||{}}));
 return {metadata:{version:APP_VERSION,updated_at:updated,item_count:kept.length,total_candidate_count:items.length,channel_count:(channels||[]).length,resolved_channel_count:resolved,retention_days:20,memory_limit:NEWS_MERGED_MEMORY_LIMIT},channels:summaries,items:kept};
}
function startNewsChannels(options={}){
 const channels=NEWS_FILES.map(cfg=>normalizeNewsChannel(cfg,window[cfg.seed]||{metadata:{source_id:cfg.id,source_name:cfg.label,status:"waiting",item_count:0},items:[]}));
 const emit=()=>{const merged=mergeNewsChannels(channels);try{options.onUpdate?.(cloneValue(merged))}catch(e){console.warn("news progressive callback failed",e)}return merged};
 const promises=NEWS_FILES.map((cfg,index)=>loadData(cfg.file,window[cfg.seed]||{metadata:{source_id:cfg.id,source_name:cfg.label,status:"waiting",item_count:0},items:[]},options.force?{force:true}:{}).then(payload=>{channels[index]=normalizeNewsChannel(cfg,payload);emit();return channels[index]}).catch(()=>channels[index]));
 const initial=mergeNewsChannels(channels),done=Promise.allSettled(promises).then(()=>emit());
 return {initial,done};
}
async function loadNewsChannels(){return await startNewsChannels().done}
async function loadStockNews(){
 const fallback=window.__STOCK_NEWS_SEED__||{metadata:{version:APP_VERSION,status:"waiting",item_count:0},items:[]};
 return await loadData("stock-news.json",fallback);
}


const KLINE_INTERVALS={
 "5m":{range:"5d",interval:"5m"},"15m":{range:"1mo",interval:"15m"},"30m":{range:"1mo",interval:"30m"},
 "60m":{range:"3mo",interval:"60m"},"4h":{range:"3mo",interval:"60m",aggregate:4},
 "1d":{range:"1y",interval:"1d"},"1wk":{range:"5y",interval:"1wk"},"1mo":{range:"10y",interval:"1mo"}
};
function chartCandles(payload){
 const chart=payload?.chart?.result?.[0]||payload?.result?.[0]||payload;
 const stamps=chart?.timestamp||[],quote=chart?.indicators?.quote?.[0]||chart?.quote||{};
 const opens=quote.open||[],highs=quote.high||[],lows=quote.low||[],closes=quote.close||[],volumes=quote.volume||[];
 const rows=[];for(let i=0;i<Math.min(stamps.length,opens.length,highs.length,lows.length,closes.length);i++){
  const open=finite(opens[i]),high=finite(highs[i]),low=finite(lows[i]),close=finite(closes[i]);
  if([open,high,low,close].some(value=>value==null))continue;
  rows.push({time:Number(stamps[i]),open,high,low,close,volume:finite(volumes[i])});
 }
 return rows;
}
function aggregateCandles(rows,size){
 const output=[];for(let i=0;i<rows.length;i+=size){const group=rows.slice(i,i+size);if(!group.length)continue;output.push({time:group[0].time,open:group[0].open,high:Math.max(...group.map(x=>x.high)),low:Math.min(...group.map(x=>x.low)),close:group.at(-1).close,volume:group.reduce((sum,x)=>sum+(x.volume||0),0)});}return output;
}
let marketKlinePayloadPromise=null,marketKlinePayloadAt=0;
async function staticMarketKline(symbol,interval){
 if(!marketKlinePayloadPromise||Date.now()-marketKlinePayloadAt>30000){marketKlinePayloadAt=Date.now();marketKlinePayloadPromise=loadData("market-kline.json",window.__MARKET_KLINE_SEED__||{items:{}}).catch(error=>{marketKlinePayloadPromise=null;throw error})}
 const payload=await marketKlinePayloadPromise,row=payload?.items?.[symbol],entry=row?.intervals?.[interval];
 if(!entry?.candles?.length)return null;
 return {symbol,interval,candles:entry.candles,source:entry.source||payload.metadata?.note||"GitHub K 線通道",updated_at:entry.updated_at||payload.metadata?.updated_at,status:entry.status||"ok"};
}
async function loadMarketKline(symbol,interval="1d"){
 const spec=KLINE_INTERVALS[interval]||KLINE_INTERVALS["1d"],encoded=encodeURIComponent(symbol);let payload=null;
 const endpoint=await ensureRuntimeEndpoint();
 if(endpoint){try{payload=await getJson(`${endpoint}/kline?symbol=${encoded}&interval=${encodeURIComponent(interval)}&_=${Date.now()}`,9000)}catch(e){}}
 if(!payload){const staticPayload=await staticMarketKline(symbol,interval);if(staticPayload)payload=staticPayload}
 // Do not fall back to browser-to-Yahoo requests.  Besides being CORS-unstable,
 // client-side 4h aggregation can cross exchange sessions.  Verified edge or
 // published static candles are the only K-line authorities.
 if(!payload)throw Error("此週期尚未同步；請等待下一次行情更新");
 let rows=Array.isArray(payload.candles)?payload.candles:chartCandles(payload);
 rows=rows.map(row=>{const raw=row.time??row.timestamp??row.date;const time=typeof raw==="string"&&!/^\d+$/.test(raw)?raw:Number(raw);return {time,open:finite(row.open),high:finite(row.high),low:finite(row.low),close:finite(row.close),volume:finite(row.volume)}}).filter(row=>row.time&&[row.open,row.high,row.low,row.close].every(value=>value!=null));
 if(spec.aggregate&&!payload.candles)rows=aggregateCandles(rows,spec.aggregate);
 if(rows.length<2)throw Error("此週期資料不足");
 return {symbol,interval,candles:rows,source:payload.source||payload.metadata?.source||(endpoint?"edge live market":"published K-line"),updated_at:payload.updated_at||payload.metadata?.updated_at,status:payload.status||"ok"};
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

const WATCHLIST_KEY="marketRadarWatchlistV1";
function loadWatchlist(){try{const value=JSON.parse(localStorage.getItem(WATCHLIST_KEY)||"[]");return Array.isArray(value)?value.filter(row=>row&&row.symbol).slice(0,100):[]}catch(e){return[]}}
function saveWatchlist(rows){const clean=[],seen=new Set();for(const raw of rows||[]){const symbol=String(raw?.symbol||"").trim().toUpperCase();if(!symbol||seen.has(symbol))continue;seen.add(symbol);clean.push({symbol,name:String(raw?.name||symbol).trim(),asset_class:String(raw?.asset_class||"").trim(),exchange:String(raw?.exchange||"").trim(),added_at:raw?.added_at||new Date().toISOString()})}localStorage.setItem(WATCHLIST_KEY,JSON.stringify(clean.slice(0,100)));window.dispatchEvent(new CustomEvent("watchlistchange"));return clean}
function toggleWatchlist(item={}){const symbol=String(item.symbol||"").trim().toUpperCase();if(!symbol)return{added:false,items:loadWatchlist()};const rows=loadWatchlist(),index=rows.findIndex(row=>String(row.symbol).toUpperCase()===symbol);let added=false;if(index>=0)rows.splice(index,1);else{rows.unshift({symbol,name:String(item.name||symbol).trim(),asset_class:String(item.asset_class||"").trim(),exchange:String(item.exchange||"").trim(),added_at:new Date().toISOString()});added=true}return{added,items:saveWatchlist(rows)}}
function installGlobalMobileQuickNav(){
 // v11.4.58: never add a second persistent navigation row on phones.
 // The home page already owns its single left-side quick rail and every app page
 // already has the canonical bottom navigation. Keeping one navigation owner
 // prevents the old duplicated 01-04 bar from covering portfolio/calendar/K-line content.
 if(document.querySelector(".floating-quick-nav")||document.querySelector(".mobile-nav"))return;
}
function syncMobileNavCurrent(){const page=(location.pathname.split("/").pop()||"index.html").toLowerCase();document.querySelectorAll(".mobile-nav a").forEach(link=>{const href=(link.getAttribute("href")||"").split("#")[0].split("?")[0].toLowerCase();link.classList.toggle("active",href===page||(page===""&&href==="index.html"))})}
function initSharedMobileUi(){installGlobalMobileQuickNav();syncMobileNavCurrent()}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",initSharedMobileUi,{once:true});else initSharedMobileUi();

function scheduleAssetPrefetch(){
 // Do not preload seven data channels on every page.  The old idle prefetch
 // could download several megabytes even when the user never opened a stock.
 // Only warm the actual asset page after the user shows intent.
 const warm=event=>{const link=event.target?.closest?.('a[href*="asset.html?symbol="]');if(!link||link.dataset.prefetched)return;link.dataset.prefetched="1";const tag=document.createElement("link");tag.rel="prefetch";tag.href=link.href;document.head.appendChild(tag)};
 document.addEventListener("pointerover",warm,{passive:true});document.addEventListener("touchstart",warm,{passive:true});
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",scheduleAssetPrefetch,{once:true});else scheduleAssetPrefetch();
window.MR={$,$$,escapeHtml,finite,fmt,pct,cls,formatTime,formatEventTime,stripHtml,normalizeText,safeHttpUrl,safeExternalHref,newsImageCandidates,newsHasImage,advanceNewsImage,pickNewsFallbackSlug,renderNewsThumb,relatedNews,loadData,loadMarketKline,loadStockBasics,loadNewsChannels,startNewsChannels,mergeNewsChannels,loadStockNews,getJson,loadPortfolio,savePortfolio,loadWatchlist,saveWatchlist,toggleWatchlist,mergeAssets,NEWS_FILES,OWNER,REPO,getLiveMarketEndpoint,ensureRuntimeEndpoint,KLINE_INTERVALS};
})();
