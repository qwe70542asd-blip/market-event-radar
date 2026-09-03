(()=>{"use strict";
if(!("serviceWorker" in navigator))return;
const BUILD="v11.5.1",CACHE_PREFIX="market-event-radar-",CACHE_NAME="market-event-radar-v11-5-1";

async function purgeLegacyCaches(){
  if(!("caches" in window))return;
  try{const keys=await caches.keys();await Promise.all(keys.filter(key=>key.startsWith(CACHE_PREFIX)&&key!==CACHE_NAME).map(key=>caches.delete(key)))}catch(e){}
}

navigator.serviceWorker.addEventListener("controllerchange",()=>{
  window.dispatchEvent(new CustomEvent("mr:service-worker-updated",{detail:{build:BUILD}}));
});

async function register(){
  try{
    await purgeLegacyCaches();
    const reg=await navigator.serviceWorker.register(`service-worker.js?v=${encodeURIComponent(BUILD)}`,{updateViaCache:"none"});
    if(reg.waiting)reg.waiting.postMessage({type:"SKIP_WAITING"});
    reg.addEventListener("updatefound",()=>{
      const worker=reg.installing;
      worker?.addEventListener("statechange",()=>{if(worker.state==="installed"&&navigator.serviceWorker.controller)worker.postMessage({type:"SKIP_WAITING"})});
    });
    setTimeout(()=>reg.update().catch(()=>{}),10000);
  }catch(e){console.warn("service worker",e)}
}

const schedule=()=>{if("requestIdleCallback" in window)requestIdleCallback(()=>register(),{timeout:3000});else setTimeout(register,1200)};
if(document.readyState==="complete")schedule();else window.addEventListener("load",schedule,{once:true});
})();
