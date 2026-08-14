/* v11.4.46 runtime endpoint bootstrap.
 * The public Worker URL is published only after a successful production
 * deployment to the history-free live-runtime branch. Deployment credentials
 * are never exposed to the browser. The endpoint is accepted only when both
 * its exact workers.dev hostname and its /health identity contract match.
 */
(()=>{
  "use strict";
  const OWNER="qwe70542asd-blip",REPO="market-event-radar",VERSION="v11.4.46";
  const EXPECTED_HOST="market-event-radar-live.qwe70542asd.workers.dev";
  const safeEndpoint=value=>{
    const text=String(value||"").trim().replace(/\/$/,"");
    if(!/^https:\/\//i.test(text))return "";
    try{
      const url=new URL(text);
      if(url.username||url.password||url.hostname!==EXPECTED_HOST||!['','/'].includes(url.pathname)||url.search||url.hash)return "";
      return url.origin;
    }catch(e){return ""}
  };
  const verifyHealth=async endpoint=>{
    const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),6500);
    try{
      const response=await fetch(`${endpoint}/health`,{cache:"no-store",headers:{Accept:"application/json"},signal:ctl.signal});
      if(!response.ok)return false;
      const body=await response.json();
      return body?.service==="Market Event Radar live market"&&body?.version===VERSION&&body?.status==="ok"&&body?.cache_binding===true&&body?.rate_limit_binding===true;
    }catch(e){return false}finally{clearTimeout(timer)}
  };
  window.MR_RUNTIME={version:VERSION,liveMarketEndpoint:"",source:"unconfigured"};
  window.MR_RUNTIME_READY=(async()=>{
    const url=`https://raw.githubusercontent.com/${OWNER}/${REPO}/live-runtime/runtime-config.json?_=${Date.now()}`;
    try{
      const response=await fetch(url,{cache:"no-store",headers:{Accept:"application/json"}});
      if(!response.ok)throw Error(`runtime ${response.status}`);
      const payload=await response.json();
      const endpoint=safeEndpoint(payload?.liveMarketEndpoint);
      if(payload?.version!==VERSION||!endpoint)throw Error("runtime config rejected");
      if(!await verifyHealth(endpoint))throw Error("runtime health identity rejected");
      window.MR_RUNTIME={version:VERSION,liveMarketEndpoint:endpoint,source:"live-runtime-verified"};
    }catch(error){
      window.MR_RUNTIME={version:VERSION,liveMarketEndpoint:"",source:"github-fallback-only"};
    }
    window.dispatchEvent(new CustomEvent("market-radar:runtime-ready",{detail:window.MR_RUNTIME}));
    return window.MR_RUNTIME;
  })();
})();
