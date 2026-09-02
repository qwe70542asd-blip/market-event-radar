(()=>{"use strict";
const BUILD="v11.5.1";
const START=Date.now();
const DATA_HOSTS=new Set(["raw.githubusercontent.com","cdn.jsdelivr.net","cdn.statically.io","api.github.com"]);
const KEEP_KEY=/(portfolio|watchlist|holding|transaction|cost|theme|install|mr-user)/i;

function purgeLegacyVersionCache(storage){
  if(!storage)return;
  try{
    const remove=[];
    for(let i=0;i<storage.length;i++){
      const key=storage.key(i)||"";
      if(KEEP_KEY.test(key))continue;
      if(/^mr-data-cache-v11\.4\./.test(key) ||
         /^mr-data-cache-v11\.5\.0:/.test(key) ||
         /^mr-last-good-v11\.4\./.test(key) ||
         /^mr-last-good-v11\.5\.0:/.test(key) ||
         /^mr-sw-controller-v11\.5\.0$/.test(key)){
        remove.push(key);
      }
    }
    remove.forEach(key=>storage.removeItem(key));
  }catch(e){}
}
purgeLegacyVersionCache(window.sessionStorage);
purgeLegacyVersionCache(window.localStorage);

if(typeof window.fetch==="function" && !window.__MR_FETCH_DEDUPE_V1151__){
  window.__MR_FETCH_DEDUPE_V1151__=true;
  const nativeFetch=window.fetch.bind(window);
  const inflight=new Map();

  const canonicalKey=(input,init)=>{
    const method=String(init?.method || (input instanceof Request?input.method:"GET") || "GET").toUpperCase();
    if(method!=="GET" && method!=="HEAD")return "";
    let raw="";
    try{raw=input instanceof Request?input.url:String(input)}catch(e){return ""}
    try{
      const url=new URL(raw,location.href);
      if(!DATA_HOSTS.has(url.hostname) && url.origin!==location.origin)return "";
      url.searchParams.delete("t");
      url.searchParams.delete("_");
      return `${method}:${url.toString()}`;
    }catch(e){return ""}
  };

  const withBootTimeout=(input,init={})=>{
    let raw="";
    try{raw=input instanceof Request?input.url:String(input)}catch(e){return init}
    let url;
    try{url=new URL(raw,location.href)}catch(e){return init}
    if(Date.now()-START>15000 || !DATA_HOSTS.has(url.hostname))return init;
    const controller=new AbortController();
    const timeout=url.hostname==="raw.githubusercontent.com"?2800:2200;
    const timer=setTimeout(()=>controller.abort("fast-boot-timeout"),timeout);
    const original=init.signal || (input instanceof Request?input.signal:null);
    if(original){
      if(original.aborted)controller.abort(original.reason);
      else original.addEventListener("abort",()=>controller.abort(original.reason),{once:true});
    }
    return {...init,signal:controller.signal,__mrTimer:timer};
  };

  window.fetch=async function(input,init={}){
    const key=canonicalKey(input,init);
    if(!key)return nativeFetch(input,init);
    let promise=inflight.get(key);
    if(!promise){
      const tuned=withBootTimeout(input,init);
      const timer=tuned.__mrTimer;
      if("__mrTimer" in tuned)delete tuned.__mrTimer;
      promise=nativeFetch(input,tuned).finally(()=>{
        if(timer)clearTimeout(timer);
        inflight.delete(key);
      });
      inflight.set(key,promise);
    }
    const response=await promise;
    return response.clone();
  };
}

window.__MR_FAST_BOOT__={build:BUILD,startedAt:START};
})();