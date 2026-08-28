/**
 * Market Event Radar v11.4.55 edge live-market service.
 * KV is last-known-good storage only. Hot snapshot/kline responses use Cache API
 * so the Free-plan KV write budget is not consumed every minute.
 */
const VERSION="v11.4.55";
const SCHEMA_VERSION="market-snapshot-v2";
const SNAPSHOT_KEY=`snapshot:${SCHEMA_VERSION}`;
const HOT_SNAPSHOT_URL="https://market-event-radar-cache.invalid/market-snapshot.json";
const SYMBOLS=[
  ["^TWII","台灣加權","TW"],["^DJI","道瓊工業平均指數","US"],["^IXIC","NASDAQ","US"],
  ["^SOX","費城半導體","US"],["^GSPC","S&P 500","US"],["^N225","日經 225","JP"]
];
const ALLOWED_SYMBOLS=new Map(SYMBOLS.map(row=>[row[0],row]));
const SPECS={"5m":["5d","5m"],"15m":["1mo","15m"],"30m":["1mo","30m"],"60m":["3mo","60m"],"4h":["3mo","60m"],"1d":["1y","1d"],"1wk":["5y","1wk"],"1mo":["10y","1mo"]};
const TZ={TW:"Asia/Taipei",JP:"Asia/Tokyo",US:"America/New_York"};
const SESSIONS={TW:[[540,810]],JP:[[540,690],[750,930]],US:[[570,960]]};
const baseHeaders={
  "access-control-allow-origin":"*",
  "access-control-allow-methods":"GET,OPTIONS",
  "access-control-allow-headers":"content-type",
  "cache-control":"no-store",
  "x-content-type-options":"nosniff",
  "referrer-policy":"no-referrer"
};
const json=(body,status=200,extra={})=>new Response(JSON.stringify(body),{status,headers:{...baseHeaders,...extra,"content-type":"application/json;charset=utf-8"}});
const num=value=>value===null||value===undefined||value===""?null:Number.isFinite(Number(value))?Number(value):null;
const cacheReady=env=>!!env?.MARKET_CACHE&&typeof env.MARKET_CACHE.get==="function"&&typeof env.MARKET_CACHE.put==="function";
const rateLimitReady=env=>!!env?.API_RATE_LIMITER&&typeof env.API_RATE_LIMITER.limit==="function";
const rateKey=url=>url.pathname==="/kline"?`kline:${String(url.searchParams.get("symbol")||"").toUpperCase()}:${url.searchParams.get("interval")||"1d"}`:url.pathname;
async function requesterKey(request){
  const raw=String(request.headers.get("cf-connecting-ip")||request.headers.get("x-forwarded-for")||"anonymous").split(",")[0].trim();
  try{
    const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(raw));
    return [...new Uint8Array(digest)].slice(0,8).map(value=>value.toString(16).padStart(2,"0")).join("");
  }catch(error){return "anonymous"}
}
async function enforceRateLimit(request,url,env){
  if(!rateLimitReady(env))return json({error:"rate limiter unavailable",version:VERSION,schema_version:SCHEMA_VERSION},503);
  const client=await requesterKey(request);
  const result=await env.API_RATE_LIMITER.limit({key:`${client}:${rateKey(url)}`});
  if(!result?.success)return json({error:"rate limit exceeded",version:VERSION,schema_version:SCHEMA_VERSION},429,{"retry-after":"60"});
  return null;
}
function localParts(date,market){const parts=new Intl.DateTimeFormat("en-CA",{timeZone:TZ[market],weekday:"short",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).formatToParts(date);return Object.fromEntries(parts.map(item=>[item.type,item.value]));}
function marketOpen(market,date=new Date()){const p=localParts(date,market);if(["Sat","Sun"].includes(p.weekday))return false;const minutes=Number(p.hour)*60+Number(p.minute);return SESSIONS[market].some(([start,end])=>minutes>=start-5&&minutes<=end+5)}
function anyMarketOpen(date=new Date()){return SYMBOLS.some(row=>marketOpen(row[2],date))}
function marketDate(date,market){const p=localParts(date,market);return `${p.year}-${p.month}-${p.day}`}
function chartRows(chart){const quote=chart?.indicators?.quote?.[0]||{},times=chart?.timestamp||[],rows=[];for(let index=0;index<Math.min(times.length,(quote.open||[]).length,(quote.high||[]).length,(quote.low||[]).length,(quote.close||[]).length);index++){const open=num(quote.open[index]),high=num(quote.high[index]),low=num(quote.low[index]),close=num(quote.close[index]);if([open,high,low,close].some(value=>value===null))continue;rows.push({time:Number(times[index]),open,high,low,close,volume:num((quote.volume||[])[index])});}return rows;}
function aggregate4h(rows,market){const groups=new Map();for(const row of rows){const p=localParts(new Date(row.time*1000),market),minutes=Number(p.hour)*60+Number(p.minute),sessions=SESSIONS[market]||[];let session=-1,start=0;for(let i=0;i<sessions.length;i++){if(minutes>=sessions[i][0]&&minutes<=sessions[i][1]){session=i;start=sessions[i][0];break}}if(session<0)continue;const bucket=Math.floor((minutes-start)/240),key=`${p.year}-${p.month}-${p.day}:${session}:${bucket}`,group=groups.get(key)||[];group.push(row);groups.set(key,group)}const out=[];for(const group of groups.values()){group.sort((a,b)=>a.time-b.time);out.push({time:group[0].time,open:group[0].open,high:Math.max(...group.map(row=>row.high)),low:Math.min(...group.map(row=>row.low)),close:group.at(-1).close,volume:group.reduce((sum,row)=>sum+(row.volume||0),0)})}return out.sort((a,b)=>a.time-b.time);}
async function yahoo(symbol,range="3mo",interval="1d"){if(!ALLOWED_SYMBOLS.has(symbol))throw new Error("symbol not allowed");const url=`https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=${encodeURIComponent(range)}&interval=${encodeURIComponent(interval)}&events=div%2Csplits`;const response=await fetch(url,{headers:{"user-agent":"Mozilla/5.0 MarketEventRadar/11.4.55","accept-language":"zh-TW,en;q=.7"}});if(!response.ok)throw new Error(`${symbol} Yahoo ${response.status}`);const body=await response.json(),chart=body?.chart?.result?.[0];if(!chart)throw new Error(`${symbol} empty chart`);return chart;}
async function buildRow([symbol,name,market]){const chart=await yahoo(symbol),meta=chart.meta||{},rows=chartRows(chart),latest=rows.at(-1),previous=rows.at(-2),stamp=Number(meta.regularMarketTime||latest?.time||0);if(!Number.isFinite(stamp)||stamp<=0)throw new Error(`${symbol} missing verified quote time`);const quoteAt=new Date(stamp*1000),session=marketDate(quoteAt,market);const live={open:num(meta.regularMarketOpen),high:num(meta.regularMarketDayHigh),low:num(meta.regularMarketDayLow),close:num(meta.regularMarketPrice),volume:num(meta.regularMarketVolume)};const useLive=[live.open,live.high,live.low,live.close].every(value=>value!==null)&&live.high>=Math.max(live.open,live.close)&&live.low<=Math.min(live.open,live.close);const display=useLive?live:latest;if(!display)throw new Error(`${symbol} missing OHLC`);const latestSession=latest?marketDate(new Date(latest.time*1000),market):null,prev=latestSession===session?previous?.close:latest?.close,change=prev===null||prev===undefined?null:display.close-prev,percent=prev?change/prev*100:null;if(display.close<display.low||display.close>display.high)throw new Error(`${symbol} mixed session`);const windowOpen=marketOpen(market),expected=marketDate(new Date(),market),sessionConfirmed=session===expected,isOpen=windowOpen&&sessionConfirmed,ageSeconds=Math.max(0,(Date.now()-quoteAt.getTime())/1000),stale=isOpen&&ageSeconds>180,unconfirmed=windowOpen&&!sessionConfirmed,staleReason=stale?"盤中超過 3 分鐘未更新":unconfirmed?`尚未確認 ${expected} 交易資料；可能休市或行情尚未開出`:null;return {symbol,name,market,price:display.close,previous_close:prev,change,change_percent:percent,session_date:session,price_date:session,ohlc_date:session,open:display.open,high:display.high,low:display.low,close:display.close,volume:display.volume,market_at:quoteAt.toISOString(),quote_age_seconds:ageSeconds,candles:rows.slice(-70).map(x=>({...x,date:marketDate(new Date(x.time*1000),market)})),candle_count:Math.min(rows.length,70),candle_interval:"1d",data_status:stale?"stale":unconfirmed?"cached":"live",freshness_status:stale?"stale":isOpen?"live":unconfirmed?"unconfirmed":"closed",stale_reason:staleReason,market_open:isOpen,validation_status:"verified",source:"Yahoo edge same-session quote"};}
async function hotGet(url){try{const response=await caches.default.match(new Request(url));return response?await response.json():null}catch(error){return null}}
async function hotPut(url,payload,ttl){try{const response=new Response(JSON.stringify(payload),{headers:{"content-type":"application/json;charset=utf-8","cache-control":`public,max-age=${ttl}`}});await caches.default.put(new Request(url),response)}catch(error){}}
async function refresh(env,onlyOpen=false,persistLkg=false){
  const old=cacheReady(env)?await env.MARKET_CACHE.get(SNAPSHOT_KEY,"json")||{items:[]}:{items:[]};
  const oldMap=new Map((old.items||[]).map(row=>[row.symbol,row])),now=new Date(),targets=onlyOpen?SYMBOLS.filter(row=>marketOpen(row[2],now)):SYMBOLS,targetSet=new Set(targets.map(row=>row[0])),items=[];
  for(const config of SYMBOLS){
    if(!targetSet.has(config[0])){items.push(oldMap.get(config[0])||{symbol:config[0],name:config[1],market:config[2],data_status:"waiting"});continue}
    try{items.push(await buildRow(config))}catch(error){items.push({...oldMap.get(config[0]),symbol:config[0],name:config[1],market:config[2],data_status:"cached",freshness_status:"stale",stale_reason:String(error.message||error),validation_status:"cached-last-verified"})}
  }
  const payload={metadata:{version:VERSION,schema_version:SCHEMA_VERSION,updated_at:new Date().toISOString(),source:"Cloudflare Worker + Yahoo same-session chart",polling_policy:"Cache API hot data; KV checkpoint max four writes/hour"},items};
  if(persistLkg&&cacheReady(env))await env.MARKET_CACHE.put(SNAPSHOT_KEY,JSON.stringify(payload),{expirationTtl:86400});
  return payload;
}
async function snapshot(env){
  const open=anyMarketOpen(),hot=await hotGet(HOT_SNAPSHOT_URL),hotAge=Date.now()-Date.parse(hot?.metadata?.updated_at||0),hotTtl=open?90000:900000;
  if(hot&&Number.isFinite(hotAge)&&hotAge<hotTtl)return json(hot);
  const lkg=cacheReady(env)?await env.MARKET_CACHE.get(SNAPSHOT_KEY,"json"):null;
  try{const payload=await refresh(env,open,!lkg);await hotPut(HOT_SNAPSHOT_URL,payload,open?60:600);return json(payload)}catch(error){if(lkg?.metadata?.schema_version===SCHEMA_VERSION)return json({...lkg,metadata:{...(lkg.metadata||{}),stale:true,stale_reason:String(error.message||error)}});return json({error:"live refresh unavailable",detail:String(error.message||error),version:VERSION,schema_version:SCHEMA_VERSION},503)}
}
async function kline(url,env){
  const symbol=String(url.searchParams.get("symbol")||"").toUpperCase(),interval=url.searchParams.get("interval")||"1d";
  if(!ALLOWED_SYMBOLS.has(symbol)||!SPECS[interval])return json({error:"unsupported symbol or interval",version:VERSION,schema_version:SCHEMA_VERSION},400);
  const hotUrl=`https://market-event-radar-cache.invalid/kline/${encodeURIComponent(symbol)}/${encodeURIComponent(interval)}`;
  const cached=await hotGet(hotUrl),market=ALLOWED_SYMBOLS.get(symbol)[2],ttl=marketOpen(market)?60000:900000,cachedAge=Date.now()-Date.parse(cached?.metadata?.updated_at||0);
  if(cached?.metadata?.schema_version===SCHEMA_VERSION&&Number.isFinite(cachedAge)&&cachedAge<ttl)return json(cached);
  try{const [range,yahooInterval]=SPECS[interval],chart=await yahoo(symbol,range,yahooInterval);let candles=chartRows(chart);if(interval==="4h")candles=aggregate4h(candles,market);if(candles.length<2)throw new Error("insufficient candles");const payload={metadata:{version:VERSION,schema_version:SCHEMA_VERSION,updated_at:new Date().toISOString()},symbol,interval,source:"Yahoo chart via edge worker",candles};await hotPut(hotUrl,payload,marketOpen(market)?60:600);return json(payload)}catch(error){if(cached?.metadata?.schema_version===SCHEMA_VERSION)return json({...cached,metadata:{...(cached.metadata||{}),stale:true,stale_reason:String(error.message||error)}});return json({error:"kline unavailable",version:VERSION,schema_version:SCHEMA_VERSION},503)}
}
export default{
 async fetch(request,env){
  if(request.method==="OPTIONS")return new Response(null,{headers:baseHeaders});
  if(request.method!=="GET")return json({error:"method not allowed",version:VERSION,schema_version:SCHEMA_VERSION},405,{allow:"GET, OPTIONS"});
  const url=new URL(request.url),runtimeReady=rateLimitReady(env);
  if(url.pathname==="/health")return json({service:"Market Event Radar live market",version:VERSION,schema_version:SCHEMA_VERSION,status:runtimeReady?"ok":"degraded",cache_binding:cacheReady(env),rate_limit_binding:rateLimitReady(env),hot_cache:"cache-api",kv_write_policy:"snapshot checkpoint max four writes/hour; kline no KV writes",time:new Date().toISOString()});
  if(url.pathname==="/market-snapshot.json"||url.pathname==="/kline"){const limited=await enforceRateLimit(request,url,env);if(limited)return limited;}
  if(url.pathname==="/market-snapshot.json")return await snapshot(env);
  if(url.pathname==="/kline")return await kline(url,env);
  return json({service:"Market Event Radar live market",version:VERSION,schema_version:SCHEMA_VERSION,routes:["/health","/market-snapshot.json","/kline"]},404);
 },
 async scheduled(event,env,ctx){const minute=new Date(event.scheduledTime).getUTCMinutes(),persistLkg=minute%15===0;ctx.waitUntil((async()=>{try{const payload=await refresh(env,minute%15!==0,persistLkg);await hotPut(HOT_SNAPSHOT_URL,payload,anyMarketOpen()?60:600)}catch(error){console.warn("scheduled refresh failed",String(error.message||error))}})())}
};
