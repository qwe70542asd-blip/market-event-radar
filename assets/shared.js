(()=>{"use strict";
const OWNER="qwe70542asd-blip",REPO="market-event-radar";
const CHANNELS={"assets.json":"live-assets","asset-audit.json":"live-assets","asset-coverage.json":"live-assets","events.json":"live-events","event-source-state.json":"live-events","tw-market.json":"live-tw-market","tw-chips.json":"live-tw-chips","market-snapshot.json":"live-global-market","news-cna.json":"live-news-cna","news-moneydj.json":"live-news-moneydj","news-cnyes.json":"live-news-cnyes","news-udn.json":"live-news-udn","news-ltn.json":"live-news-ltn","news-wealth.json":"live-news-wealth","news-yahoo.json":"live-news-yahoo","news-technews.json":"live-news-technews","news-ctee.json":"live-news-ctee","news-asia-risk.json":"live-news-asia-risk","stock-news.json":"live-stock-news","official-market-notices.json":"live-official-notices","company-disclosures.json":"live-company-disclosures","monthly-revenue.json":"live-monthly-revenue","dividend-history.json":"live-dividend-history","market-volume-history.json":"live-tw-market","secondary-reference.json":"live-secondary-reference","data-verification.json":"live-data-verification","yahoo-details.json":"live-yahoo-details","etf-details.json":"live-etf-details","stock-basics.json":"live-stock-basics"};
const NEWS_FILES=[{"file":"news-cna.json","id":"cna","label":"中央社","seed":"__NEWS_CNA_SEED__","kind":"media"},{"file":"news-moneydj.json","id":"moneydj","label":"MoneyDJ","seed":"__NEWS_MONEYDJ_SEED__","kind":"media"},{"file":"news-cnyes.json","id":"cnyes","label":"鉅亨網","seed":"__NEWS_CNYES_SEED__","kind":"media"},{"file":"news-udn.json","id":"udn","label":"經濟日報","seed":"__NEWS_UDN_SEED__","kind":"media"},{"file":"news-ltn.json","id":"ltn","label":"自由財經","seed":"__NEWS_LTN_SEED__","kind":"media"},{"file":"news-wealth.json","id":"wealth","label":"財富自由","seed":"__NEWS_WEALTH_SEED__","kind":"media"},{"file":"news-yahoo.json","id":"yahoo","label":"Yahoo股市","seed":"__NEWS_YAHOO_SEED__","kind":"media"},{"file":"news-technews.json","id":"technews","label":"科技新報／財經新報","seed":"__NEWS_TECHNEWS_SEED__","kind":"media"},{"file":"news-ctee.json","id":"ctee","label":"工商時報","seed":"__NEWS_CTEE_SEED__","kind":"media"},{"file":"news-asia-risk.json","id":"asia-risk","label":"亞洲總體風險","seed":"__NEWS_ASIA_RISK_SEED__","kind":"media"},{"file":"official-market-notices.json","id":"official-notices","label":"官方市場公告","seed":"__OFFICIAL_NOTICE_SEED__","kind":"official"},{"file":"company-disclosures.json","id":"company-disclosures","label":"個股重大訊息","seed":"__COMPANY_DISCLOSURE_SEED__","kind":"company"}];
const $=(q,r=document)=>r.querySelector(q),$$=(q,r=document)=>[...r.querySelectorAll(q)];
const escapeHtml=v=>String(v??"").replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));
const finite=v=>{if(v===null||v===undefined)return null;if(typeof v==="string"&&!v.trim())return null;const n=Number(String(v).replace(/,/g,""));return Number.isFinite(n)?n:null};
const fmt=(v,d=2)=>finite(v)==null?"—":Number(finite(v)).toLocaleString("zh-TW",{maximumFractionDigits:d,minimumFractionDigits:0});
const pct=v=>finite(v)==null?"—":`${Number(v)>0?"+":""}${Number(v).toFixed(2)}%`;
const cls=v=>finite(v)==null||Number(v)===0?"flat":Number(v)>0?"up":"down";
const formatTime=(v,opts={})=>{if(!v)return"—";const d=new Date(v);if(Number.isNaN(+d))return String(v);return new Intl.DateTimeFormat("zh-TW",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:opts.dateOnly?undefined:"2-digit",minute:opts.dateOnly?undefined:"2-digit",hour12:false}).format(d)};
const stripHtml=value=>String(value??"").replace(/<[^>]*>/g," ").replace(/&nbsp;/gi," ").replace(/\s+/g," ").trim();
const normalizeText=value=>stripHtml(value).toLowerCase().normalize("NFKC").replace(/[^0-9a-z\u3400-\u9fff]+/g," ").trim();
const newsHasImage=item=>/^https?:\/\//i.test(String(item?.image_url||""));
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
 const fallback=`assets/news-fallback/${slug}.svg`;
 if(newsHasImage(item))return `<div class="news-thumb ${kind}" data-fallback="${slug}"><img src="${escapeHtml(item.image_url)}" data-fallback-src="${fallback}" alt="${alt}" loading="lazy" referrerpolicy="no-referrer" onerror="if(this.dataset.fallbackDone)return;this.dataset.fallbackDone='1';this.src=this.dataset.fallbackSrc;this.parentElement?.classList.add('fallback','remote-image-failed')"><span class="fallback-label">${label}</span></div>`;
 return `<div class="news-thumb ${kind} fallback" data-fallback="${slug}"><img src="${fallback}" alt="${alt}" loading="lazy"><span class="fallback-label">${label}</span></div>`;
}
async function getJson(url,timeout=9000){const ctl=new AbortController(),id=setTimeout(()=>ctl.abort(),timeout);try{const r=await fetch(url,{cache:"no-store",headers:{Accept:"application/json"},signal:ctl.signal});if(!r.ok)throw Error(r.status);return await r.json()}finally{clearTimeout(id)}}
const FRESH_BRANCH_FILES=new Set(["market-snapshot.json","tw-market.json","market-volume-history.json","events.json"]);
const cloneValue=value=>typeof structuredClone==="function"?structuredClone(value):JSON.parse(JSON.stringify(value));
function decodeGitHubContent(value){const binary=atob(String(value||"").replace(/\s+/g,"")),bytes=Uint8Array.from(binary,char=>char.charCodeAt(0));return JSON.parse(new TextDecoder("utf-8").decode(bytes))}
async function loadBranchApi(name,branch){
 const url=`https://api.github.com/repos/${OWNER}/${REPO}/contents/${encodeURIComponent(name)}?ref=${encodeURIComponent(branch)}&_=${Date.now()}`;
 const meta=await getJson(url,11000);
 if(meta?.encoding==="base64"&&meta?.content)return decodeGitHubContent(meta.content);
 if(meta?.download_url)return await getJson(`${meta.download_url}${meta.download_url.includes("?")?"&":"?"}sha=${encodeURIComponent(meta.sha||Date.now())}`,11000);
 throw Error("GitHub contents API returned no JSON content");
}
const snapshotCacheKey="mr-market-snapshot-last-good-v11.4.17";
const snapshotCandleCount=row=>(Array.isArray(row?.candles)?row.candles:[]).filter(candle=>candle?.date&&[candle.open,candle.high,candle.low,candle.close].every(value=>finite(value)!=null)).length;
function mergeSnapshotCache(payload){
 let cached=null;try{cached=JSON.parse(localStorage.getItem(snapshotCacheKey)||"null")}catch(e){}
 if(!cached?.items?.length)return payload;
 const oldMap=new Map(cached.items.map(row=>[String(row.symbol||"").toUpperCase(),row]));
 const items=(payload?.items||[]).map(row=>{const old=oldMap.get(String(row.symbol||"").toUpperCase());if(snapshotCandleCount(row)>=10||!old)return row;return {...old,...row,candles:old.candles||[],candle_count:snapshotCandleCount(old),candle_source:`${row.candle_source||row.source||"線上行情"}／瀏覽器上次成功 K 線`,data_status:row.data_status==="live"?"cached-kline":row.data_status};});
 return {...payload,items};
}
function rememberSnapshot(payload){const wanted=new Set(["^TWII","^KS11","^N225","^IXIC","^SOX","^GSPC"]),good=(payload?.items||[]).filter(row=>wanted.has(String(row.symbol||"").toUpperCase())&&snapshotCandleCount(row)>=10).length;if(good>=4){try{localStorage.setItem(snapshotCacheKey,JSON.stringify(payload))}catch(e){}}}
async function loadData(name,fallback={}){
 const branch=CHANNELS[name];let payload=null;
 if(branch&&FRESH_BRANCH_FILES.has(name)){try{payload=await loadBranchApi(name,branch)}catch(e){}}
 if(!payload&&branch){try{payload=await getJson(`https://raw.githubusercontent.com/${OWNER}/${REPO}/${branch}/${name}?t=${Date.now()}`,11000)}catch(e){}}
 if(!payload){try{payload=await getJson(`data/${name}?t=${Date.now()}`,9000)}catch(e){payload=cloneValue(fallback)}}
 if(name==="market-snapshot.json"){payload=mergeSnapshotCache(payload||cloneValue(fallback));rememberSnapshot(payload)}
 return payload||cloneValue(fallback);
}
const STOCK_BASIC_ENDPOINTS=[
 {url:"https://openapi.twse.com.tw/v1/opendata/t187ap03_L",exchange:"TWSE",source:"TWSE 上市公司基本資料"},
 {url:"https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",exchange:"TPEx",source:"TPEx 上櫃公司基本資料"}
];
const basicField=(row,...labels)=>{for(const label of labels){if(row?.[label]!=null&&String(row[label]).trim())return row[label]}for(const [key,value] of Object.entries(row||{})){if(labels.some(label=>String(key).includes(label))&&value!=null&&String(value).trim())return value}return null};
const basicDate=value=>{const text=String(value||"").trim();let m=text.match(/(20\d{2})[\/-]?(\d{2})[\/-]?(\d{2})/);if(m)return`${m[1]}-${m[2]}-${m[3]}`;m=text.match(/(\d{2,3})[\/-](\d{1,2})[\/-](\d{1,2})/);return m?`${Number(m[1])+1911}-${String(m[2]).padStart(2,"0")}-${String(m[3]).padStart(2,"0")}`:""};
const basicNumber=value=>{const m=String(value||"").replace(/,/g,"").match(/[-+]?\d+(?:\.\d+)?/);return m?Number(m[0]):null};
function officialBasicRecord(row,endpoint){
 const symbol=String(basicField(row,"公司代號","公司代碼","SecuritiesCompanyCode")||"").trim().toUpperCase();
 if(!/^\d{4,6}[A-Z]?$/.test(symbol))return null;
 const yahooSymbol=endpoint.exchange==="TPEx"?`${symbol}.TWO`:symbol;
 const record={symbol,company_name:String(basicField(row,"公司名稱","CompanyName")||"").trim(),short_name:String(basicField(row,"公司簡稱","CompanyAbbreviation")||"").trim(),asset_class:"stock",market:"TW",exchange:endpoint.exchange,market_label:endpoint.exchange==="TWSE"?"上市":"上櫃",currency:"TWD",industry:String(basicField(row,"產業別","產業類別","Industry")||"").trim(),address:String(basicField(row,"住址","地址","Address")||"").trim(),tax_id:String(basicField(row,"營利事業統一編號","統一編號","UnifiedBusinessNo")||"").trim(),chairperson:String(basicField(row,"董事長","Chairman")||"").trim(),general_manager:String(basicField(row,"總經理","GeneralManager")||"").trim(),spokesperson:String(basicField(row,"發言人","Spokesman")||"").trim(),phone:String(basicField(row,"總機電話","Telephone")||"").trim(),established_date:basicDate(basicField(row,"成立日期","DateOfIncorporation")),listed_date:basicDate(basicField(row,"上市日期","上櫃日期","DateOfListing")),paid_in_capital:basicNumber(basicField(row,"實收資本額","PaidinCapital")),issued_shares:basicNumber(basicField(row,"已發行普通股數","已發行普通股數或TDR原股發行股數","IssuedShares")),website:String(basicField(row,"網址","URL","公司網站")||"").trim(),email:String(basicField(row,"電子郵件信箱","Email")||"").trim(),accounting_firm:String(basicField(row,"簽證會計師事務所")||"").trim(),source:endpoint.source,source_level:"official",source_url:endpoint.url,official_url:`https://mops.twse.com.tw/mops/web/t05st03?step=1&off=1&firstin=1&co_id=${symbol}`,profile_url:`https://tw.stock.yahoo.com/quote/${yahooSymbol}/profile`,quote_url:`https://tw.stock.yahoo.com/quote/${yahooSymbol}`,financial_url:`https://tw.stock.yahoo.com/quote/${yahooSymbol}/income-statement`};
 const fields=[record.symbol,record.company_name||record.short_name,record.asset_class,record.market,record.exchange,record.industry,record.currency,record.listed_date,record.paid_in_capital,record.issued_shares,record.official_url,record.profile_url];
 record.basic_coverage_percent=Math.round(fields.filter(value=>value!==null&&value!==undefined&&String(value).trim()!=="").length/fields.length*1000)/10;
 record.updated_at=new Date().toISOString();return record;
}
async function loadStockBasics(){
 const fallback=window.__STOCK_BASICS_SEED__||{metadata:{version:"v11.4.17",status:"waiting",item_count:0},items:{}};
 const payload=await loadData("stock-basics.json",fallback),items={...(payload.items||{})};
 if(Object.keys(items).length>=500)return payload;
 const settled=await Promise.allSettled(STOCK_BASIC_ENDPOINTS.map(async endpoint=>({endpoint,rows:await getJson(endpoint.url,15000)})));
 let added=0;
 for(const result of settled){if(result.status!=="fulfilled"||!Array.isArray(result.value.rows))continue;for(const row of result.value.rows){const record=officialBasicRecord(row,result.value.endpoint);if(!record)continue;items[record.symbol]={...(items[record.symbol]||{}),...record};added++}}
 const values=Object.values(items),average=values.length?values.reduce((sum,row)=>sum+Number(row.basic_coverage_percent||0),0)/values.length:0;
 return {...payload,metadata:{...(payload.metadata||{}),version:"v11.4.17",item_count:values.length,average_basic_coverage_percent:Math.round(average*10)/10,scope:"all-currently-listed-twse-and-tpex-stocks",browser_official_fallback_added:added},items};
}
async function loadNewsChannels(){
 const channels=await Promise.all(NEWS_FILES.map(async cfg=>{
  const fallback=window[cfg.seed]||{metadata:{source_id:cfg.id,source_name:cfg.label,status:"waiting",item_count:0},items:[]};
  const payload=await loadData(cfg.file,fallback);
  const archiveStart=Date.parse("2026-01-01T00:00:00+08:00"),tomorrow=Date.now()+86400000;
  return {...payload,channel:cfg,items:(payload.items||[]).filter(item=>{const at=Date.parse(item.published_at||item.date||0);return Number.isFinite(at)&&at>=archiveStart&&at<=tomorrow}).map(item=>({...item,source_id:item.source_id||cfg.id,source:item.source||cfg.label,channel_kind:cfg.kind}))};
 }));
 const seen=new Set(),items=[];
 for(const channel of channels){for(const item of channel.items||[]){const key=String(item.id||`${item.title||""}|${item.url||""}`);if(!key||seen.has(key))continue;seen.add(key);items.push(item)}}
 items.sort((a,b)=>Date.parse(b.published_at||b.date||0)-Date.parse(a.published_at||a.date||0));
 const updated=channels.map(c=>c.metadata?.updated_at).filter(Boolean).sort().pop()||null;
 return {metadata:{version:"v11.4.17",updated_at:updated,item_count:items.length,channel_count:channels.length},channels,items};
}
async function loadStockNews(){
 const fallback=window.__STOCK_NEWS_SEED__||{metadata:{version:"v11.4.17",status:"waiting",item_count:0},items:[]};
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
window.MR={$,$$,escapeHtml,finite,fmt,pct,cls,formatTime,stripHtml,normalizeText,newsHasImage,pickNewsFallbackSlug,renderNewsThumb,relatedNews,loadData,loadStockBasics,loadNewsChannels,loadStockNews,getJson,loadPortfolio,savePortfolio,mergeAssets,NEWS_FILES,OWNER,REPO};
})();
