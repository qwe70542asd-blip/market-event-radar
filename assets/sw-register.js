(()=>{"use strict";
if(!("serviceWorker" in navigator))return;
const BUILD="v11.5.0",RELOAD_KEY=`mr-sw-controller-${BUILD}`;
let reloading=false;
navigator.serviceWorker.addEventListener("controllerchange",()=>{
  if(reloading)return;
  try{if(sessionStorage.getItem(RELOAD_KEY)==="1")return;sessionStorage.setItem(RELOAD_KEY,"1")}catch(e){}
  reloading=true;location.reload();
});
async function register(){
  try{
    const reg=await navigator.serviceWorker.register(`service-worker.js?v=${encodeURIComponent(BUILD)}`,{updateViaCache:"none"});
    await reg.update();
    if(reg.waiting)reg.waiting.postMessage({type:"SKIP_WAITING"});
    reg.addEventListener("updatefound",()=>{const worker=reg.installing;worker?.addEventListener("statechange",()=>{if(worker.state==="installed"&&navigator.serviceWorker.controller)worker.postMessage({type:"SKIP_WAITING"})})});
  }catch(e){console.warn("service worker",e)}
}
// The script sits at the end of body; registering now avoids waiting for every image/network task.
register();
})();
