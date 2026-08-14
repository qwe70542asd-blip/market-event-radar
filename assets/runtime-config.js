/* v11.4.45 runtime endpoint bootstrap.
 * The public Worker URL is published only after a successful production
 * deployment to the history-free live-runtime branch.  Deployment credentials
 * are never exposed to the browser.
 */
(()=>{
  "use strict";
  const OWNER="qwe70542asd-blip",REPO="market-event-radar",VERSION="v11.4.45";
  const safeEndpoint=value=>{
    const text=String(value||"").trim().replace(/\/$/,"");
    if(!/^https:\/\//i.test(text))return "";
    try{const url=new URL(text);if(url.username||url.password)return "";return url.origin+url.pathname.replace(/\/$/,"")}catch(e){return ""}
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
      window.MR_RUNTIME={version:VERSION,liveMarketEndpoint:endpoint,source:"live-runtime"};
    }catch(error){
      window.MR_RUNTIME={version:VERSION,liveMarketEndpoint:"",source:"github-fallback-only"};
    }
    window.dispatchEvent(new CustomEvent("market-radar:runtime-ready",{detail:window.MR_RUNTIME}));
    return window.MR_RUNTIME;
  })();
})();
