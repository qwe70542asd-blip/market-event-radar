(()=>{
  "use strict";
  const notify=()=>window.dispatchEvent(new CustomEvent("market-radar:chart-lib-ready"));
  if(window.LightweightCharts){notify();return}
  const script=document.createElement("script");
  script.src="https://unpkg.com/lightweight-charts@4.2.3/dist/lightweight-charts.standalone.production.js";
  script.async=true;
  script.crossOrigin="anonymous";
  script.onload=notify;
  script.onerror=()=>window.dispatchEvent(new CustomEvent("market-radar:chart-lib-failed"));
  document.head.appendChild(script);
})();
