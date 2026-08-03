const CACHE_NAME="market-event-radar-v11-1-2";
const STATIC=[
  "./","index.html","404.html","portfolio.html","tw-market.html","asset.html","news.html","institutional.html","event.html",
  "manifest.webmanifest","assets/styles.css?v=11.1.2","assets/shared.js?v=11.1.2","assets/home.js?v=11.1.2",
  "assets/portfolio.js?v=11.1.2","assets/tw-market.js?v=11.1.2","assets/asset.js?v=11.1.2",
  "assets/news.js?v=11.1.2","assets/institutional.js?v=11.1.2","assets/event.js?v=11.1.2",
  "assets/sw-register.js?v=11.1.2","assets/favicon.svg",
  "data/assets-seed.js?v=11.1.2","data/events-seed.js?v=11.1.2","data/news-seed.js?v=11.1.2",
  "data/tw-market-seed.js?v=11.1.2","data/tw-chips-seed.js?v=11.1.2","data/market-snapshot-seed.js?v=11.1.2"
];
self.addEventListener("install",event=>event.waitUntil(caches.open(CACHE_NAME).then(cache=>cache.addAll(STATIC)).then(()=>self.skipWaiting())));
self.addEventListener("activate",event=>event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(key=>key!==CACHE_NAME).map(key=>caches.delete(key)))).then(()=>self.clients.claim())));
async function networkFirst(request,fallback){
  try{
    const response=await fetch(new Request(request,{cache:"no-store"}));
    if(response&&response.ok){
      const cache=await caches.open(CACHE_NAME);
      const url=new URL(request.url);
      cache.put(new Request(url.origin+url.pathname),response.clone()).catch(()=>{});
    }
    return response;
  }catch(error){
    const url=new URL(request.url);
    return await caches.match(new Request(url.origin+url.pathname))||await caches.match(fallback||request)||Response.error();
  }
}
async function staleWhileRevalidate(request){
  const cache=await caches.open(CACHE_NAME);
  const cached=await cache.match(request);
  const fresh=fetch(new Request(request,{cache:"no-cache"})).then(response=>{if(response&&response.ok)cache.put(request,response.clone());return response}).catch(()=>null);
  return cached||await fresh||Response.error();
}
self.addEventListener("fetch",event=>{
  if(event.request.method!=="GET")return;
  const url=new URL(event.request.url);
  if(url.pathname.includes("/data/")&&url.pathname.endsWith(".json")){event.respondWith(networkFirst(event.request));return}
  if(event.request.mode==="navigate"){event.respondWith(networkFirst(event.request,"index.html"));return}
  if(url.origin===self.location.origin&&/\.(?:js|css|html)$/.test(url.pathname)){event.respondWith(networkFirst(event.request));return}
  if(url.origin===self.location.origin)event.respondWith(staleWhileRevalidate(event.request));
});
self.addEventListener("message",event=>{if(event.data?.type==="SKIP_WAITING")self.skipWaiting()});
