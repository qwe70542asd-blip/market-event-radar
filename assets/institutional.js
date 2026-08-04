(async()=>{
  "use strict";
  const {$,escapeHtml,fmt,pct,cls,formatTime,loadData,finite}=MR;
  const [payload,market]=await Promise.all([
    loadData("tw-chips.json",window.__TW_CHIPS_SEED__||{markets:{},items:{}}),
    loadData("tw-market.json",window.__TW_MARKET_SEED__||{items:[]})
  ]);
  $("#chipsDate").textContent=payload.metadata?.updated_at?formatTime(payload.metadata.updated_at):"等待盤後資料";
  const display=(value,digits=0)=>finite(value)==null?"—":fmt(value,digits);
  const chipItems=Object.values(payload.items||{});
  const marketItems=market.items||[];
  const marketMap=new Map(marketItems.map(item=>[String(item.symbol),item]));
  const allSymbols=new Map();
  for(const item of marketItems)if(["stock","etf"].includes(item.asset_class))allSymbols.set(String(item.symbol),item);
  for(const item of chipItems)allSymbols.set(String(item.symbol),{...allSymbols.get(String(item.symbol)),...item});
  const searchable=[...allSymbols.values()].sort((a,b)=>String(a.symbol).localeCompare(String(b.symbol),"zh-Hant"));

  function marketCard(key,label){
    const marketData=payload.markets?.[key]||{},institutional=marketData.institutional||{};
    return `<article class="stat"><small>${label} 外資</small><strong class="${cls(institutional.foreign_net)}">${display(institutional.foreign_net)}</strong></article><article class="stat"><small>${label} 投信</small><strong class="${cls(institutional.trust_net)}">${display(institutional.trust_net)}</strong></article><article class="stat"><small>${label} 自營商</small><strong class="${cls(institutional.dealer_net)}">${display(institutional.dealer_net)}</strong></article><article class="stat"><small>${label} 合計</small><strong class="${cls(institutional.total_net)}">${display(institutional.total_net)}</strong></article>`;
  }
  $("#marketFlowCards").innerHTML=marketCard("twse","上市");

  const trendRows=item=>{
    const history=item.history||item.recent||[];
    if(!Array.isArray(history)||!history.length)return '<div class="empty compact-empty">目前沒有最近五日歷史資料</div>';
    return `<div class="chip-trend"><h3>最近五日趨勢</h3><div class="table-wrap"><table><thead><tr><th>日期</th><th>外資</th><th>投信</th><th>自營商</th><th>融資增減</th><th>融券增減</th></tr></thead><tbody>${history.slice(-5).reverse().map(row=>`<tr><td>${escapeHtml(row.date||"—")}</td><td class="${cls(row.institutional?.foreign_net)}">${display(row.institutional?.foreign_net)}</td><td class="${cls(row.institutional?.trust_net)}">${display(row.institutional?.trust_net)}</td><td class="${cls(row.institutional?.dealer_net)}">${display(row.institutional?.dealer_net)}</td><td class="${cls(row.margin?.change)}">${display(row.margin?.change)}</td><td class="${cls(row.short?.change)}">${display(row.short?.change)}</td></tr>`).join("")}</tbody></table></div></div>`;
  };
  const detail=item=>{
    const quote=marketMap.get(String(item.symbol))||{};
    return `<article class="chip-detail-card"><div class="chip-detail-head"><div><span class="tag">${escapeHtml(quote.asset_class==="etf"?"ETF":"個股")}</span><strong>${escapeHtml(item.symbol)}</strong><span>${escapeHtml(item.name||quote.name||"")}</span></div><a class="btn" href="asset.html?symbol=${encodeURIComponent(item.symbol)}">查看標的 →</a></div><div class="chip-summary-line"><span>成交價 <b>${display(quote.price,2)}</b></span><span>漲跌幅 <b class="${cls(quote.change_percent)}">${pct(quote.change_percent)}</b></span><span>成交量 <b>${display(quote.volume)}</b></span><span>成交金額 <b>${display(quote.trade_value)}</b></span></div><div class="chip-section-grid"><section><h3>三大法人</h3><div class="chip-metric-grid"><div><small>外資</small><strong class="${cls(item.institutional?.foreign_net)}">${display(item.institutional?.foreign_net)}</strong></div><div><small>投信</small><strong class="${cls(item.institutional?.trust_net)}">${display(item.institutional?.trust_net)}</strong></div><div><small>自營商</small><strong class="${cls(item.institutional?.dealer_net)}">${display(item.institutional?.dealer_net)}</strong></div><div><small>三大法人</small><strong class="${cls(item.institutional?.total_net)}">${display(item.institutional?.total_net)}</strong></div></div></section><section><h3>信用交易與當沖</h3><div class="chip-metric-grid"><div><small>當沖量</small><strong>${display(item.day_trade?.volume)}</strong></div><div><small>當沖比</small><strong>${finite(item.day_trade?.ratio)==null?"—":pct(item.day_trade.ratio)}</strong></div><div><small>融資餘額</small><strong>${display(item.margin?.balance)}</strong></div><div><small>融資增減</small><strong class="${cls(item.margin?.change)}">${display(item.margin?.change)}</strong></div><div><small>融券餘額</small><strong>${display(item.short?.balance)}</strong></div><div><small>融券增減</small><strong class="${cls(item.short?.change)}">${display(item.short?.change)}</strong></div></div></section></div>${trendRows(item)}<p class="broker-note">${escapeHtml(item.broker_note||"公開分點資料僅供觀察，不代表券商、外資或最終客戶的真實持倉。")}</p></article>`;
  };

  let selected=null;
  function selectItem(symbol){
    selected=searchable.find(item=>String(item.symbol)===String(symbol));
    if(!selected)return;
    $("#chipSymbol").value=`${selected.symbol} ${selected.name||""}`.trim();
    $("#chipSuggestions").innerHTML="";
    const chip=(payload.items||{})[selected.symbol]||selected;
    $("#chipResult").innerHTML=detail({...selected,...chip,name:chip.name||selected.name});
  }
  function search(){
    const query=$("#chipSymbol").value.trim().toUpperCase();
    if(!query){selected=null;$("#chipSuggestions").innerHTML="";$("#chipResult").innerHTML='<div class="empty">請輸入股票或 ETF 代碼／名稱，再選擇要查看的標的。</div>';return}
    const normalized=query.split(/\s+/)[0];
    const exact=searchable.find(item=>String(item.symbol).toUpperCase()===normalized);
    if(exact&&query===normalized){selectItem(exact.symbol);return}
    const matches=searchable.filter(item=>`${item.symbol} ${item.name||""}`.toUpperCase().includes(query)).slice(0,8);
    $("#chipSuggestions").innerHTML=matches.map(item=>`<button type="button" data-chip-symbol="${escapeHtml(item.symbol)}"><b>${escapeHtml(item.symbol)}</b><span>${escapeHtml(item.name||"")}</span><small>${item.asset_class==="etf"?"ETF":"個股"}</small></button>`).join("")||'<div class="empty compact-empty">找不到符合的標的</div>';
    document.querySelectorAll("[data-chip-symbol]").forEach(button=>button.onclick=()=>selectItem(button.dataset.chipSymbol));
    if(!selected)$("#chipResult").innerHTML='<div class="empty">請從上方搜尋建議選擇一個標的。</div>';
  }
  $("#chipSymbol").oninput=search;
  $("#clearChipSearch").onclick=()=>{$("#chipSymbol").value="";search();$("#chipSymbol").focus()};

  const isEtf=item=>item.asset_class==="etf";
  const hot=etf=>{
    const rows=marketItems.filter(item=>["stock","etf"].includes(item.asset_class)&&isEtf(item)===etf);
    const maxValue=Math.max(1,...rows.map(item=>finite(item.trade_value)||0)),maxVolume=Math.max(1,...rows.map(item=>finite(item.volume)||0));
    return rows.map(item=>{
      const chip=(payload.items||{})[item.symbol]||{},foreign=Math.abs(finite(chip.institutional?.foreign_net)||0),dayRatio=Math.abs(finite(chip.day_trade?.ratio)||0);
      const rawScore=((finite(item.trade_value)||0)/maxValue)*55+((finite(item.volume)||0)/maxVolume)*25+Math.min(Math.abs(finite(item.change_percent)||0),10)*1.2+Math.min(foreign/1000000,5)+Math.min(dayRatio,100)*.03;
      return {...item,chip,rawScore};
    }).sort((a,b)=>b.rawScore-a.rawScore).slice(0,10).map((item,index,selected)=>{
      const top=selected[0]?.rawScore||1;
      return {...item,score:Math.max(1,Math.round(item.rawScore/top*100))};
    });
  };
  const hotHtml=rows=>rows.map((item,index)=>`<tr><td>${index+1}</td><td><a href="asset.html?symbol=${encodeURIComponent(item.symbol)}"><b>${escapeHtml(item.symbol)}</b><br><small>${escapeHtml(item.name||"")}</small></a></td><td><span class="hot-score">${item.score}</span></td><td class="${cls(item.change_percent)}">${pct(item.change_percent)}</td><td>${display(item.trade_value)}</td><td class="${cls(item.chip.institutional?.foreign_net)}">${display(item.chip.institutional?.foreign_net)}</td><td>${finite(item.chip.day_trade?.ratio)==null?"—":pct(item.chip.day_trade.ratio)}</td></tr>`).join("")||'<tr><td colspan="7" class="empty">等待市場資料</td></tr>';
  $("#hotStocks").innerHTML=hotHtml(hot(false));
  $("#hotEtfs").innerHTML=hotHtml(hot(true));
})();
