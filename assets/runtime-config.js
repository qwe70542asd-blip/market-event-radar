/* Schema-gated direct Worker bootstrap.
 * Frontend patch versions and Worker patch versions are intentionally decoupled.
 */
(()=>{
  "use strict";
  const APP_VERSION="v11.5.0";
  const SCHEMA_VERSION="market-snapshot-v2";
  const EXPECTED_HOST="market-event-radar-live.qwe70542asd.workers.dev";
  const ENDPOINT=`https://${EXPECTED_HOST}`;
  const safeEndpoint=value=>{
    const text=String(value||"").trim().replace(/\/$/,"");
    try{
      const url=new URL(text);
      if(url.protocol!=="https:"||url.username||url.password||url.hostname!==EXPECTED_HOST||!["","/"].includes(url.pathname)||url.search||url.hash)return "";
      return url.origin;
    }catch(e){return ""}
  };
  const verifyHealth=async endpoint=>{
    const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),6500);
    try{
      const response=await fetch(`${endpoint}/health`,{cache:"no-store",headers:{Accept:"application/json"},signal:ctl.signal});
      if(!response.ok)return null;
      const body=await response.json();
      const ok=body?.service==="Market Event Radar live market"&&body?.schema_version===SCHEMA_VERSION&&body?.status==="ok"&&body?.cache_binding===true&&body?.rate_limit_binding===true;
      return ok?body:null;
    }catch(e){return null}finally{clearTimeout(timer)}
  };
  window.MR_RUNTIME={appVersion:APP_VERSION,schemaVersion:SCHEMA_VERSION,workerVersion:"",liveMarketEndpoint:"",source:"checking-direct-worker"};
  window.MR_RUNTIME_READY=(async()=>{
    const endpoint=safeEndpoint(ENDPOINT),health=endpoint?await verifyHealth(endpoint):null;
    if(endpoint&&health){
      window.MR_RUNTIME={appVersion:APP_VERSION,schemaVersion:SCHEMA_VERSION,workerVersion:String(health.version||""),liveMarketEndpoint:endpoint,source:"direct-worker-verified"};
    }else{
      window.MR_RUNTIME={appVersion:APP_VERSION,schemaVersion:SCHEMA_VERSION,workerVersion:"",liveMarketEndpoint:"",source:"github-fallback-only"};
    }
    window.dispatchEvent(new CustomEvent("market-radar:runtime-ready",{detail:window.MR_RUNTIME}));
    return window.MR_RUNTIME;
  })();
})();
