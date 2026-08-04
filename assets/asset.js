(async()=>{
  "use strict";
  const {$,escapeHtml,fmt,pct,cls,formatTime,loadData,finite,stripHtml}=MR;
  const symbol=new URLSearchParams(location.search).get("symbol")?.toUpperCase()||"2330";
  const [assets,tw,chips,news]=await Promise.all([
    loadData("assets.json",window.__ASSET_SEED__||{assets:[]}),
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]}),
    loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{items:{}}),
    loadData("news.json",window.__NEWS_SEED__||{items:[]})
  ]);
  const asset=(assets.assets||[]).find(row=>String(row.symbol).toUpperCase()===symbol)||{symbol,name:symbol};
  const quote=(tw.items||[]).find(row=>String(row.symbol).toUpperCase()===symbol)||{};
  const chip=chips.items?.[symbol]||{};
  document.title=`${asset.name||symbol}｜市場事件雷達`;
  $("#assetTitle").textContent=`${asset.symbol||symbol} ${asset.name||""}`;
  $("#assetSub").textContent=[asset.exchange,asset.official_industry||asset.sub_industry,asset.asset_class].filter(Boolean).join(" · ");
  $("#assetPrice").textContent=fmt(quote.price);
  $("#assetChange").textContent=pct(quote.change_percent);
  $("#assetChange").className=cls(quote.change_percent);

  const metrics=asset.metrics||{},statuses=asset.metric_status||{},sources=asset.metric_sources||{};
  const metricDisplay=(key,value,unit="")=>{
    const status=statuses[key];
    if(status==="not_applicable")return "不適用";
    if(status==="source_error")return "資料暫時無法取得";
    if(finite(value)==null)return "尚未公告";
    return `${fmt(value,key==="eps"?2:2)}${unit}`;
  };
  const metricCards=[
    ["本益比","pe",metrics.pe,""],
    ["股價淨值比","pb",metrics.pb,""],
    ["殖利率","dividend_yield",metrics.dividend_yield,"%"],
    ["EPS","eps",metrics.eps," 元"],
    ["ROE","roe",metrics.roe,"%"],
    ["負債比","debt_ratio",metrics.debt_ratio,"%"],
    ["淨利率","net_margin",metrics.net_margin,"%"],
    ["流動比率","current_ratio",metrics.current_ratio,"%"],
    ["融資餘額","margin",chip.margin?.balance,""],
    ["融券餘額","short",chip.short?.balance,""]
  ];
  $("#assetMetrics").innerHTML=metricCards.map(([label,key,value,unit])=>{
    const source=key==="margin"||key==="short"?"TWSE／TPEx 信用交易":sources[key];
    const display=key==="margin"||key==="short"?(finite(value)==null?"尚未公告":fmt(value,0)):metricDisplay(key,value,unit);
    return `<article class="stat metric-card"><small>${escapeHtml(label)}</small><strong>${escapeHtml(display)}</strong><span>${escapeHtml(source||"官方資料等待更新")}</span></article>`;
  }).join("");
  $("#metricUpdated").textContent=asset.metrics_updated_at?`財務指標更新 ${formatTime(asset.metrics_updated_at)}`:"等待第一次官方財務更新";

  const etf=asset.etf||{};
  const typeText=asset.asset_class==="etf"?(etf.category||asset.sub_industry||"ETF"):asset.official_industry||asset.sub_industry||"尚未取得";
  $("#assetInfo").innerHTML=`<div class="asset-info-grid">
    <div><small>公司／發行人</small><p>${escapeHtml(asset.company_name||etf.issuer||"尚未取得")}</p></div>
    <div><small>類型／產業</small><p>${escapeHtml(typeText)}</p></div>
    <div><small>上市／上櫃日期</small><p>${escapeHtml(asset.listed_date||etf.listing_date||"尚未取得")}</p></div>
    <div><small>發行股數／實收資本額</small><p>${finite(asset.issued_shares)!=null?`${fmt(asset.issued_shares,0)} 股`:finite(asset.paid_in_capital)!=null?`${fmt(asset.paid_in_capital,0)} 元`:"尚未取得"}</p></div>
    <div><small>追蹤指數</small><p>${escapeHtml(etf.benchmark||"不適用")}</p></div>
    <div><small>資料狀態</small><p>${asset.financials?.length?`已保存 ${asset.financials.length} 期財報`:asset.asset_class==="etf"?"ETF 不適用公司財報":"等待官方財報"}</p></div>
  </div>`;

  $("#holdingRows").innerHTML=(etf.holdings||[]).map(row=>`<tr><td>${escapeHtml(row.symbol||"")}</td><td>${escapeHtml(row.name||"")}</td><td>${finite(row.weight)==null?"—":`${fmt(row.weight)}%`}</td></tr>`).join("")||'<tr><td colspan="3" class="empty">官方尚未提供、尚未接入，或主動 ETF 揭露有時間差。頁面不會用推測成分股補值。</td></tr>';

  const financials=(asset.financials||[]).slice(0,12);
  const finRatio=(n,d)=>finite(n)!=null&&finite(d)!=null&&Number(d)!==0?Number(n)/Number(d)*100:null;
  const financialRows=financials.map(row=>{
    const roe=finRatio(row.net_income,row.total_equity),debt=finRatio(row.total_liabilities,row.total_assets),margin=finRatio(row.net_income,row.revenue),current=finRatio(row.current_assets,row.current_liabilities);
    return `<tr><td><b>${escapeHtml(row.period||"—")}</b><br><small>${escapeHtml(row.source||"官方財報")}</small></td><td>${fmt(row.revenue,0)}</td><td>${fmt(row.net_income,0)}</td><td>${finite(row.eps)==null?"—":fmt(row.eps,2)}</td><td>${finite(roe)==null?"—":`${fmt(roe,2)}%`}</td><td>${finite(debt)==null?"—":`${fmt(debt,2)}%`}</td><td>${finite(margin)==null?"—":`${fmt(margin,2)}%`}</td><td>${finite(current)==null?"—":`${fmt(current,2)}%`}</td></tr>`;
  }).join("");
  $("#financialRows").innerHTML=financialRows||`<tr><td colspan="8" class="empty">${asset.asset_class==="etf"?"ETF 不適用公司財務報表。":"尚未取得可解析的季度財報；GitHub Actions 會持續保留最後成功資料。"}</td></tr>`;

  $("#brokerRows").innerHTML=(chip.brokers||[]).map(row=>`<tr><td>${escapeHtml(row.name||"—")}</td><td class="${cls(row.net)}">${fmt(row.net,0)}</td><td>${fmt(row.buy,0)}</td><td>${fmt(row.sell,0)}</td></tr>`).join("")||'<tr><td colspan="4" class="empty">尚無可用分點資料。券商分點成交不等於券商或外資的真實持倉。</td></tr>';

  const related=(news.items||[]).filter(item=>{
    const itemSymbols=(item.symbols||[]).map(value=>String(value).toUpperCase());
    const text=`${item.title||""} ${item.ai_summary||item.summary||""}`;
    return item.url_valid!==false&&(itemSymbols.includes(symbol)||(asset.name&&text.includes(asset.name))||(asset.company_name&&text.includes(asset.company_name)));
  }).slice(0,9);
  $("#assetNews").innerHTML=related.map(item=>`<a class="news-card compact" href="${escapeHtml(item.url||"#")}" target="_blank" rel="noreferrer noopener"><div class="news-meta"><span>${escapeHtml(item.source||"")}</span><time>${escapeHtml(formatTime(item.published_at))}</time></div><div class="ai-badges"><span class="tag">${escapeHtml(item.ai_category||item.topic||"市場")}</span><span class="impact-badge ${escapeHtml(item.impact||"medium")}">${item.impact==="high"?"高影響":item.impact==="low"?"低影響":"中影響"}</span></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(stripHtml(item.ai_summary||item.summary||"").slice(0,150))}</p></a>`).join("")||'<div class="empty">尚無相關新聞</div>';
})();
