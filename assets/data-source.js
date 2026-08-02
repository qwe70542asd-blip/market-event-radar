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

  async function fetchJsonUrl(url,timeout=9000) {
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),timeout);
    try {
      const response=await fetch(`${url}${url.includes("?")?"&":"?"}t=${Date.now()}`,{cache:"no-store",headers:{Accept:"application/json"},signal:controller.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally { clearTimeout(timer); }
  }

  async function loadJson(path,fallback={}) {
    try {
      const payload=await fetchJsonUrl(remotePath(path));
      return {...payload,__data_source:"live-data"};
    } catch {}
    try {
      const payload=await fetchJsonUrl(MAIN_BASE + String(path || "").replace(/^\.\//,""));
      return {...payload,__data_source:"main"};
    } catch {}
    try {
      const payload=await fetchJsonUrl(path);
      return {...payload,__data_source:"local"};
    } catch {}
    return fallback;
  }

  window.MarketDataSource={REMOTE_BASE,MAIN_BASE,remotePath,fetchJsonUrl,loadJson};
})();
