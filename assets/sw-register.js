(() => {
  "use strict";
  const VERSION="11.1.4";
  const KEY="market-radar-version";
  if(!("serviceWorker" in navigator))return;
  window.addEventListener("load",async()=>{
    try{
      const previous=localStorage.getItem(KEY);
      const registration=await navigator.serviceWorker.register(`./service-worker.js?v=${VERSION}`,{updateViaCache:"none"});
      await registration.update();
      localStorage.setItem(KEY,VERSION);
      let reloaded=false;
      navigator.serviceWorker.addEventListener("controllerchange",()=>{if(reloaded)return;reloaded=true;location.reload()});
      if(registration.waiting)registration.waiting.postMessage({type:"SKIP_WAITING"});
      registration.addEventListener("updatefound",()=>{
        const worker=registration.installing;
        worker?.addEventListener("statechange",()=>{if(worker.state==="installed"&&navigator.serviceWorker.controller)worker.postMessage({type:"SKIP_WAITING"})});
      });
      if(previous!==VERSION&&"caches" in window){
        const keep="market-event-radar-v11-1-4";
        const keys=await caches.keys();
        await Promise.all(keys.filter(key=>key.startsWith("market-event-radar-")&&key!==keep).map(key=>caches.delete(key)));
      }
    }catch(error){console.warn("Service worker registration failed:",error)}
  });
})();
