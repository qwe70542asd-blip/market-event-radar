const BUILD="v11.5.1";
const CACHE_PREFIX="market-event-radar-";
const CACHE_NAME="market-event-radar-v11-5-1";
const CORE_STATIC=[
  "./",
  "index.html",
  "404.html",
  "manifest.webmanifest",
  "assets/styles.css?v=11.5.1",
  "assets/v11.5.1-overrides.css?v=11.5.1",
  "assets/date-alerts.css?v=11.5.1",
  "assets/shared.js?v=11.5.1",
  "assets/home.js?v=11.5.1",
  "assets/stale-market-guard.js?v=11.5.1",
  "assets/date-alerts.js?v=11.5.1",
  "assets/pwa-install.js?v=11.5.1",
  "assets/sw-register.js?v=11.5.1",
  "data/home-bootstrap-seed.js?v=11.5.1",
  "assets/favicon.svg"
];
const OPTIONAL_STATIC=[
  "portfolio.html","tw-market.html","asset.html","news.html","institutional.html","data-status.html","event.html",
  "assets/portfolio.js?v=11.5.1","assets/tw-market.js?v=11.5.1","assets/asset.js?v=11.5.1","assets/news.js?v=11.5.1","assets/institutional.js?v=11.5.1","assets/data-status.js?v=11.5.1","assets/event.js?v=11.5.1"
];
const NETWORK_INFLIGHT=new Map();

function canonicalRequest(request){
  const url=new URL(request.url);
  if(url.origin===self.location.origin){url.searchParams.delete("t");url.searchParams.delete("_")}
  return new Request(url.toString(),{method:"GET",credentials:"same-origin"});
}

async function fetchOnce(request,timeoutMs=8000){
  const key=canonicalRequest(request),token=key.url;
  let active=NETWORK_INFLIGHT.get(token);
  if(!active){
    active=(async()=>{
      const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),timeoutMs);
      try{return await fetch(new Request(request,{cache:"no-store",signal:ctl.signal}))}
      finally{clearTimeout(timer)}
    })().finally(()=>NETWORK_INFLIGHT.delete(token));
    NETWORK_INFLIGHT.set(token,active);
  }
  return (await active).clone();
}

async function networkFirst(request,fallback,timeoutMs){
  const key=canonicalRequest(request),cache=await caches.open(CACHE_NAME);
  try{
    const response=await fetchOnce(request,timeoutMs);
    if(response.ok){await cache.put(key,response.clone());return response}
    return await cache.match(key)||await caches.match(fallback||key,{ignoreSearch:false})||response;
  }catch(error){
    return await cache.match(key)||await caches.match(fallback||key,{ignoreSearch:false})||Response.error();
  }
}

async function cacheFirst(request){
  const key=canonicalRequest(request),cache=await caches.open(CACHE_NAME),hit=await cache.match(key);
  if(hit)return hit;
  const response=await fetchOnce(request,8000);
  if(response.ok)await cache.put(key,response.clone());
  return response;
}

self.addEventListener("install",event=>event.waitUntil((async()=>{
  const cache=await caches.open(CACHE_NAME);
  await Promise.allSettled(CORE_STATIC.map(url=>cache.add(new Request(url,{cache:"reload"}))));
  await self.skipWaiting();
})()));

self.addEventListener("activate",event=>event.waitUntil((async()=>{
  const keys=await caches.keys();
  await Promise.all(keys.filter(key=>key.startsWith(CACHE_PREFIX)&&key!==CACHE_NAME).map(key=>caches.delete(key)));
  await self.clients.claim();
})()));

self.addEventListener("fetch",event=>{
  const request=event.request;if(request.method!=="GET")return;
  const url=new URL(request.url);
  if(url.origin!==self.location.origin)return;
  if(request.mode==="navigate"){event.respondWith(networkFirst(request,"index.html",3500));return}
  if(url.pathname.includes("/data/")&&/\.json$/i.test(url.pathname)){event.respondWith(networkFirst(request,null,2500));return}
  if(/\.(?:js|css|svg|png|webp|ico|webmanifest)$/i.test(url.pathname)){event.respondWith(cacheFirst(request));return}
});

self.addEventListener("message",event=>{if(event.data?.type==="SKIP_WAITING")self.skipWaiting()});
