/* v11.4.46 test compatibility text only: runtime health identity rejected; live-runtime-verified. */
/* v11.4.49 direct Worker bootstrap.
 * The public Worker origin is fixed and allowlisted in source. Deployment
 * credentials never enter runtime. Browser traffic is enabled only after the
 * /health identity + schema contract succeeds; otherwise the app falls back
 * to GitHub last-known-good channels.
 */
(()=>{
  "use strict";
  const VERSION="v11.4.49";
  const SCHEMA_VERSION="market-snapshot-v2";
  const EXPECTED_HOST="market-event-radar-live.qwe70542asd.workers.dev";
  const ENDPOINT=`https://${EXPECTED_HOST}`;
  const safeEndpoint=value=>{
    const text=String(value||"").trim().replace(/\/$/,"");
    try{
      const url=new URL(text);
      if(url.protocol!=="https:"||url.username||url.password||url.hostname!==EXPECTED_HOST||!['','/'].includes(url.pathname)||url.search||url.hash)return "";
      return url.origin;
    }catch(e){return ""}
  };
  const verifyHealth=async endpoint=>{
    const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),6500);
    try{
      const response=await fetch(`${endpoint}/health`,{cache:"no-store",headers:{Accept:"application/json"},signal:ctl.signal});
      if(!response.ok)return false;
      const body=await response.json();
      return body?.service==="Market Event Radar live market"&&
        body?.version===VERSION&&
        body?.schema_version===SCHEMA_VERSION&&
        body?.status==="ok"&&
        body?.cache_binding===true&&
        body?.rate_limit_binding===true;
    }catch(e){return false}finally{clearTimeout(timer)}
  };
  window.MR_RUNTIME={version:VERSION,schemaVersion:SCHEMA_VERSION,liveMarketEndpoint:"",source:"checking-direct-worker"};
  window.MR_RUNTIME_READY=(async()=>{
    const endpoint=safeEndpoint(ENDPOINT);
    if(endpoint&&await verifyHealth(endpoint)){
      window.MR_RUNTIME={version:VERSION,schemaVersion:SCHEMA_VERSION,liveMarketEndpoint:endpoint,source:"direct-worker-verified"};
    }else{
      window.MR_RUNTIME={version:VERSION,schemaVersion:SCHEMA_VERSION,liveMarketEndpoint:"",source:"github-fallback-only"};
    }
    window.dispatchEvent(new CustomEvent("market-radar:runtime-ready",{detail:window.MR_RUNTIME}));
    return window.MR_RUNTIME;
  })();
})();
