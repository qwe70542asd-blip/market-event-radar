(() => {
  "use strict";
  const $ = s => document.querySelector(s);
  const escapeHtml = v => String(v || "").replace(/[&<>\"]/g, c => ({ "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;" }[c]));
  const params=new URLSearchParams(location.search);
  const assetId=params.get("id");
  let payload={};

  function formatNumber(value, digits=2){
    const n=Number(value); if(!Number.isFinite(n)) return "—";
    return new Intl.NumberFormat("zh-TW",{maximumFractionDigits:digits}).format(n);
  }
  function percent(value){ const n=Number(value); return Number.isFinite(n)?`${n.toFixed(1)}%`:"—"; }

  function scoreAsset(asset){
    const m=asset.metrics||{};
    const parts={
      profitability: Number.isFinite(+m.roe) ? Math.max(0,Math.min(100,50+(+m.roe-10)*2.5)) : 50,
      leverage: Number.isFinite(+m.debt_ratio) ? Math.max(0,Math.min(100,100-(+m.debt_ratio))) : 50,
      liquidity: Number.isFinite(+m.current_ratio) ? Math.max(0,Math.min(100,(+m.current_ratio)*35)) : 50,
      valuation: Number.isFinite(+m.pe) ? Math.max(0,Math.min(100,100-(+m.pe)*2)) : 50,
      income: Number.isFinite(+m.dividend_yield) ? Math.max(0,Math.min(100,(+m.dividend_yield)*14)) : 50
    };
    const available=Object.values(m).filter(x=>x!==null&&x!==undefined&&x!=="").length;
    const base=Object.values(parts).reduce((a,b)=>a+b,0)/5;
    return {parts,total:available>=3?Math.round(base*Math.min(1,0.45+available/12)):null,coverage:Math.min(100,Math.round(available/10*100))};
  }
  function radarSvg(parts){
    const keys=["profitability","leverage","liquidity","valuation","income"];
    const labels=["獲利","負債","流動","估值","收益"];
    const cx=120,cy=105,r=72;
    const point=(i,v)=>{const a=-Math.PI/2+i*2*Math.PI/5;const rr=r*v/100;return [cx+Math.cos(a)*rr,cy+Math.sin(a)*rr];};
    const grid=[25,50,75,100].map(level=>`<polygon points="${keys.map((_,i)=>point(i,level).join(",")).join(" ")}"/>`).join("");
    const axes=keys.map((_,i)=>{const [x,y]=point(i,100);return `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}"/><text x="${x}" y="${y}" dx="${x<cx?-10:x>cx?10:0}" dy="${y<cy?-8:14}">${labels[i]}</text>`}).join("");
    const data=keys.map((k,i)=>point(i,parts[k]).join(",")).join(" ");
    return `<svg class="model-radar" viewBox="0 0 240 220" role="img" aria-label="穩健度模型雷達圖"><g class="radar-grid">${grid}${axes}</g><polygon class="radar-data" points="${data}"/></svg>`;
  }
  function metricBars(asset){
    const rows=[
      ["本益比",asset.metrics?.pe,asset.industry_median?.pe],
      ["股價淨值比",asset.metrics?.pb,asset.industry_median?.pb],
      ["股息殖利率",asset.metrics?.dividend_yield,asset.industry_median?.dividend_yield],
      ["ROE",asset.metrics?.roe,asset.industry_median?.roe],
      ["負債比",asset.metrics?.debt_ratio,asset.industry_median?.debt_ratio]
    ];
    return rows.map(([label,value,median])=>{
      const v=Number(value),m=Number(median),max=Math.max(Math.abs(v||0),Math.abs(m||0),1);
      return `<article class="comparison-row"><b>${label}</b><div><span style="width:${Number.isFinite(v)?Math.min(100,Math.abs(v)/max*100):0}%"></span></div><strong>${formatNumber(value)}</strong><small>產業中位 ${formatNumber(median)}</small></article>`;
    }).join("");
  }
  function render(asset){
    document.title=`${asset.name} ${asset.symbol}｜市場雷達`;
    $("#assetName").textContent=asset.name;
    $("#assetSymbol").textContent=asset.symbol;
    $("#assetMeta").textContent=`${asset.exchange||asset.market} · ${asset.official_industry||asset.sub_industry||asset.sector} · ${asset.currency||""}`;
    $("#assetTypeBadge").textContent=asset.asset_class==="crypto"?"虛擬貨幣":asset.asset_class==="fund"||asset.asset_class==="etf"?"基金／ETF":"股票";
    const m=asset.metrics||{}, model=scoreAsset(asset);
    $("#assetMetricGrid").innerHTML=[
      ["最新價格",m.price],["市值",m.market_cap],["本益比",m.pe],["股價淨值比",m.pb],
      ["股息殖利率",m.dividend_yield?percent(m.dividend_yield):"—"],["EPS",m.eps],
      ["ROE",m.roe?percent(m.roe):"—"],["負債比",m.debt_ratio?percent(m.debt_ratio):"—"]
    ].map(([l,v])=>`<article><span>${l}</span><strong>${typeof v==="number"?formatNumber(v):escapeHtml(v||"—")}</strong></article>`).join("");
    $("#stabilityScore").textContent=model.total===null?"資料不足":model.total;
    $("#dataCoverage").textContent=`資料覆蓋 ${model.coverage}%`;
    $("#stabilityRadar").innerHTML=radarSvg(model.parts);
    $("#comparisonBars").innerHTML=metricBars(asset);
    $("#rankingGrid").innerHTML=`
      <article><span>產業 EPS 排名</span><strong>${escapeHtml(asset.rankings?.eps||"資料不足")}</strong></article>
      <article><span>產業 ROE 排名</span><strong>${escapeHtml(asset.rankings?.roe||"資料不足")}</strong></article>
      <article><span>產業估值分位</span><strong>${escapeHtml(asset.rankings?.valuation||"資料不足")}</strong></article>
      <article><span>產業穩健度排名</span><strong>${escapeHtml(asset.rankings?.stability||"資料不足")}</strong></article>`;
    $("#financialTable").innerHTML=(asset.financials||[]).length ? (asset.financials||[]).map(row=>`
      <tr><td>${escapeHtml(row.period)}</td><td>${formatNumber(row.revenue)}</td><td>${formatNumber(row.operating_income)}</td><td>${formatNumber(row.net_income)}</td><td>${formatNumber(row.eps)}</td></tr>`).join("") :
      '<tr><td colspan="5">官方財報資料尚未同步；可先使用下方官方來源連結。</td></tr>';
    $("#officialLinks").innerHTML=[
      asset.detail?.website&&["公司官網",asset.detail.website],
      asset.market==="TW"&&["公開資訊觀測站","https://mops.twse.com.tw/"],
      asset.market==="US"&&["SEC EDGAR",`https://www.sec.gov/edgar/search/#/q=${encodeURIComponent(asset.symbol)}`]
    ].filter(Boolean).map(([l,u])=>`<a href="${u}" target="_blank" rel="noreferrer noopener">${l} →</a>`).join("");
    $("#modelNotice").textContent="穩健度是資料型比較模型，會受到資料缺漏與產業差異影響，不是信用評等、目標價或買賣建議。";
  }
  async function load(){
    let seed=window.__MARKET_ASSET_SEED__||{assets:[]};
    try{const r=await fetch(`data/assets.json?t=${Date.now()}`,{cache:"no-store"});if(r.ok)seed=await r.json();}catch{}
    let asset=(seed.assets||[]).find(x=>x.id===assetId);
    if(!asset&&window.MarketAssets) asset=window.MarketAssets.byId(assetId);
    if(!asset){$("#assetName").textContent="找不到標的";return;}
    try{
      const safeId=String(asset.id).replace(/:/g,"__");
      const r=await fetch(`data/asset-details/${encodeURIComponent(safeId)}.json?t=${Date.now()}`,{cache:"no-store"});
      if(r.ok) asset={...asset,...await r.json()};
    }catch{}
    render(asset);
  }
  window.addEventListener("market-assets-loaded",load,{once:true});
  if(window.MarketAssets?.state.loaded) load();
})();