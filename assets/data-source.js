(() => {
  "use strict";
  const OWNER="qwe70542asd-blip";
  const REPO="market-event-radar";
  const LIVE_BRANCH="live-data";
  const MAIN_BRANCH="main";
  const REMOTE_BASE=`https://raw.githubusercontent.com/${OWNER}/${REPO}/${LIVE_BRANCH}/`;
  const MAIN_BASE=`https://raw.githubusercontent.com/${OWNER}/${REPO}/${MAIN_BRANCH}/`;

  function remotePath(path) {
    return REMOTE_BASE + String(path || "").replace(/^\.\//,"");
  }

  async function fetchJsonUrl(url,timeout=6000) {
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),timeout);
    try {
      const response=await fetch(`${url}${url.includes("?")?"&":"?"}t=${Date.now()}`,{cache:"no-store",headers:{Accept:"application/json"},signal:controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally { clearTimeout(timer); }
  }

  function dataScore(payload) {
    const arrays=[payload?.items,payload?.events,payload?.announcements,payload?.taiwan_etfs,payload?.us_etfs];
    return arrays.reduce((total,rows)=>total+(Array.isArray(rows)?rows.length:0),0);
  }

  function valueScore(payload) {
    const arrays=[payload?.items,payload?.taiwan_etfs,payload?.us_etfs];
    return arrays.reduce((total,rows)=>total+(Array.isArray(rows)
      ? rows.filter(row=>row?.value!==null&&row?.value!==undefined&&row?.value!=="").length
      : 0),0);
  }

  function updatedTime(payload) {
    const parsed=Date.parse(payload?.metadata?.updated_at||payload?.updated_at||"");
    return Number.isFinite(parsed)?parsed:0;
  }

  async function loadJson(path,fallback={}) {
    const cleanPath=String(path||"").replace(/^\.\//,"");
    const requests=[
      ["live-data",remotePath(cleanPath)],
      ["local",cleanPath],
      ["main",MAIN_BASE+cleanPath],
    ];
    const settled=await Promise.allSettled(requests.map(([,url])=>fetchJsonUrl(url)));
    const candidates=settled.flatMap((result,index)=>result.status==="fulfilled"
      ? [{...result.value,__data_source:requests[index][0],__priority:3-index}]
      : []);
    if (!candidates.length) return fallback;
    const isMarketPayload=candidates.some(candidate=>Array.isArray(candidate?.taiwan_etfs)||Array.isArray(candidate?.us_etfs));
    candidates.sort((a,b)=>isMarketPayload
      ? valueScore(b)-valueScore(a)||updatedTime(b)-updatedTime(a)||dataScore(b)-dataScore(a)||(b.__priority||0)-(a.__priority||0)
      : dataScore(b)-dataScore(a)||updatedTime(b)-updatedTime(a)||(b.__priority||0)-(a.__priority||0));
    const selected={...candidates[0]};
    delete selected.__priority;
    return selected;
  }

  window.MarketDataSource={REMOTE_BASE,MAIN_BASE,remotePath,fetchJsonUrl,loadJson};
})();
