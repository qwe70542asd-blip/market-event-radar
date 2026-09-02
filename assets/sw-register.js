(()=>{"use strict";
if(!("serviceWorker" in navigator))return;
const BUILD="v11.5.1",RELOAD_KEY=`mr-sw-controller-${BUILD}`;

navigator.serviceWorker.addEventListener("controllerchange",()=>{
  try{sessionStorage.setItem(RELOAD_KEY,"1")}catch(e){}
  window.dispatchEvent(new CustomEvent("mr:service-worker-updated",{detail:{build:BUILD}}));
});

async function register(){
  try{
    const reg=await navigator.serviceWorker.register(`service-worker.js?v=${encodeURIComponent(BUILD)}`,{updateViaCache:"none"});
    setTimeout(()=>reg.update().catch(()=>{}),5000);
    if(reg.waiting)reg.waiting.postMessage({type:"SKIP_WAITING"});
    reg.addEventListener("updatefound",()=>{
      const worker=reg.installing;
      worker?.addEventListener("statechange",()=>{
        if(worker.state==="installed"&&navigator.serviceWorker.controller){
          worker.postMessage({type:"SKIP_WAITING"});
        }
      });
    });
  }catch(e){console.warn("service worker",e)}
}

const schedule=()=>{
  if("requestIdleCallback" in window)requestIdleCallback(()=>register(),{timeout:3000});
  else setTimeout(register,1200);
};
if(document.readyState==="complete")schedule();
else window.addEventListener("load",schedule,{once:true});
})();