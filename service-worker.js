const CACHE_NAME="market-event-radar-v11-5-0";
const CORE_STATIC=["./","index.html","404.html","manifest.webmanifest","assets/styles.css?v=11.5.0","assets/v11.5.0-overrides.css?v=11.5.0","assets/date-alerts.css?v=11.5.0","assets/shared.js?v=11.5.0","assets/home.js?v=11.5.0","assets/stale-market-guard.js?v=11.5.0","assets/date-alerts.js?v=11.5.0","assets/sw-register.js?v=11.5.0","assets/favicon.svg","data/tw-market-seed.js?v=11.5.0","data/tw-chips-seed.js?v=11.5.0","data/market-snapshot-seed.js?v=11.5.0"];
const OPTIONAL_STATIC=["portfolio.html","tw-market.html","asset.html","news.html","institutional.html","data-status.html","event.html","assets/portfolio.js?v=11.5.0","assets/tw-market.js?v=11.5.0","assets/asset.js?v=11.5.0","assets/news.js?v=11.5.0","assets/institutional.js?v=11.5.0","assets/data-status.js?v=11.5.0","assets/event.js?v=11.5.0","assets/pwa-install.js?v=11.5.0"];

self.addEventListener("install",event=>event.waitUntil((async()=>{
  const cache=await caches.open(CACHE_NAME);
  await cache.addAll(CORE_STATIC);
  // Optional pages are cached on demand. Avoid a 40+ request install storm on phones.
  await self.skipWaiting();
})()));
self.addEventListener("activate",event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE_NAME).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
function normalizedCacheRequest(req){const u=new URL(req.url);if(u.origin===self.location.origin){u.searchParams.delete("t");u.searchParams.delete("_");return new Request(u.toString(),{method:"GET",credentials:"same-origin"})}return req}
async function networkFirst(request,fallback){const key=normalizedCacheRequest(request),cache=await caches.open(CACHE_NAME);try{const response=await fetch(new Request(request,{cache:"no-store"}));if(response.ok)await cache.put(key,response.clone());return response.ok?response:(await cache.match(key,{ignoreSearch:true})||await caches.match(fallback||key,{ignoreSearch:true})||response)}catch(error){return await cache.match(key,{ignoreSearch:true})||await caches.match(fallback||key,{ignoreSearch:true})||Response.error()}}
async function cacheFirst(request){const cache=await caches.open(CACHE_NAME),hit=await cache.match(request)||await cache.match(request,{ignoreSearch:true});if(hit)return hit;const response=await fetch(request);if(response.ok)await cache.put(request,response.clone());return response}
self.addEventListener("fetch",event=>{if(event.request.method!=="GET")return;const url=new URL(event.request.url);if(url.hostname==="raw.githubusercontent.com"||url.hostname==="api.github.com"||url.hostname.includes("yahoo.com"))return;const same=url.origin===self.location.origin;if(event.request.mode==="navigate"){event.respondWith(networkFirst(event.request,"index.html"));return}if(same&&(url.pathname.endsWith("/assets/runtime-config.js")||url.pathname.includes("/data/")||/\.(?:js|css|json)$/i.test(url.pathname))){event.respondWith(networkFirst(event.request));return}if(same&&/\.(?:svg|png|webp|ico)$/i.test(url.pathname))event.respondWith(cacheFirst(event.request))});
self.addEventListener("message",event=>{if(event.data?.type==="SKIP_WAITING")self.skipWaiting()});
