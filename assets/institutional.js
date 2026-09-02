(async()=>{
  "use strict";
  const {$,escapeHtml,fmt,pct,cls,formatTime,loadData,finite}=MR;
  let payload=window.__TW_CHIPS_SEED__||{markets:{},items:{}},market=window.__TW_MARKET_SEED__||{items:[]},yahooPayload=window.__YAHOO_DETAILS_SEED__||{items:{}};
  const display=(value,digits=0)=>finite(value)==null?"—":fmt(value,digits);
  const displayLots=value=>{const n=finite(value);if(n==null)return "—";const digits=Math.abs(n-Math.round(n))<1e-9?0:Math.min(3,Math.max(1,String(n).split(".")[1]?.length||1));return `${n>0?"+":""}${fmt(n,digits)} 張`};
  const displayAmount=value=>{const n=finite(value);return n==null?"—":`${n>0?"+":""}${fmt(n/1e8,2)} 億元`};
  const flowLabel=value=>{const n=finite(value);return n==null?"資料待補":n>0?"買超":n<0?"賣超":"持平"};
  const nonempty=value=>value!==null&&value!==undefined&&value!==""&&(!(Array.isArray(value))||value.length);
  const mergeObject=(primary={},fallback={})=>{
    const out={...fallback,...primary};
    for(const key of new Set([...Object.keys(fallback||{}),...Object.keys(primary||{})])){
      const a=primary?.[key],b=fallback?.[key];
      if(a&&typeof a==="object"&&!Array.isArray(a)&&b&&typeof b==="object"&&!Array.isArray(b))out[key]=mergeObject(a,b);
      else if(!nonempty(a)&&nonempty(b))out[key]=b;
    }
    return out;
  };
  const mergeHistory=(...groups)=>{
    const map=new Map();
    for(const group of groups)for(const row of group||[]){
      const key=String(row?.date||"");if(!key)continue;
      map.set(key,mergeObject(map.get(key)||{},row));
    }
    return [...map.values()].sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(0,40);
  };
  let chipItems={},yahooItems={},marketItems=[],marketMap=new Map(),searchable=[];
  function rebuildDerived(){chipItems=payload.items||{};yahooItems=yahooPayload.items||{};marketItems=market.items||[];marketMap=new Map(marketItems.map(item=>[String(item.symbol),item]));const allSymbols=new Map();for(const item of marketItems)if(["stock","etf"].includes(item.asset_class))allSymbols.set(String(item.symbol),item);for(const item of Object.values(chipItems))allSymbols.set(String(item.symbol),{...allSymbols.get(String(item.symbol)),...item});searchable=[...allSymbols.values()].sort((a,b)=>String(a.symbol).localeCompare(String(b.symbol),"zh-Hant"));}
  rebuildDerived();
  const freshYahooRow=row=>{const stamp=Date.parse(row?.updated_at||row?.source_updated_at||"");return Number.isFinite(stamp)&&Date.now()-stamp>=-5*60*1000&&Date.now()-stamp<=96*3600*1000};
  const verifiedMarketDate=()=>String(market.metadata?.trading_date||"");
  const sameCurrentSession=row=>{const expected=verifiedMarketDate(),day=String(row?.date||"");return !expected||!day||day===expected};

  function chipFor(symbol){
    const rawOfficial=chipItems[symbol]||{},rawYahoo=yahooItems[symbol]||{},yahoo=freshYahooRow(rawYahoo)?(rawYahoo.chips||{}):{};
    const official=sameCurrentSession(rawOfficial)?rawOfficial:{symbol:rawOfficial.symbol,name:rawOfficial.name,exchange:rawOfficial.exchange,asset_class:rawOfficial.asset_class,date:rawOfficial.date,sources:rawOfficial.sources||[]};
    const currentYahoo=sameCurrentSession(yahoo)?yahoo:{history:yahoo.history||yahoo.recent||[]};
    const merged=mergeObject(official,currentYahoo);
    merged.history=mergeHistory(rawOfficial.history||rawOfficial.recent,yahoo.history||yahoo.recent);
    if(!sameCurrentSession(rawOfficial)&&rawOfficial.date)merged.current_session_note=`法人／資券資料停在 ${rawOfficial.date}，等待 ${verifiedMarketDate()||"最新交易日"}`;
    return merged;
  }
  function marketCard(key,label){
    const marketData=payload.markets?.[key]||{};
    const expected=verifiedMarketDate(),lotsDate=String(marketData.institutional_date||marketData.trading_date||""),amountDate=String(marketData.institutional_amount_date||"");
    const lotsCurrent=!expected||!lotsDate||lotsDate===expected,amountSessionMatches=lotsCurrent&&(!amountDate||!expected||amountDate===expected)&&(!lotsDate||!amountDate||lotsDate===amountDate);
    const institutional=lotsCurrent?(marketData.institutional||{}):{},amounts=amountSessionMatches?(marketData.institutional_amounts||{}):{};
    if(expected&&!lotsCurrent)return `<article class="stat market-flow-stat"><small>${label} 法人</small><strong class="flat">待更新</strong><span class="stat-detail">目前 ${escapeHtml(lotsDate||"無日期")} · 等待 ${escapeHtml(expected)}</span></article>`;
    const values=[institutional.foreign_net,institutional.trust_net,institutional.dealer_net,institutional.total_net];
    const amountValues=[amounts.foreign?.net,amounts.trust?.net,amounts.dealer?.net,amounts.total?.net];
    if(![...values,...amountValues].some(value=>finite(value)!=null))return "";
    const card=(name,value,amount)=>`<article class="stat market-flow-stat"><small>${label} ${name}</small><strong class="${cls(value)}">${displayLots(value)}</strong><b class="market-flow-amount ${cls(amount)}">${displayAmount(amount)}</b><span class="stat-detail">${flowLabel(finite(value)!=null?value:amount)} · 張數 / 金額</span></article>`;
    return card("外資",institutional.foreign_net,amounts.foreign?.net)+card("投信",institutional.trust_net,amounts.trust?.net)+card("自營商",institutional.dealer_net,amounts.dealer?.net)+card("合計",institutional.total_net,amounts.total?.net);
  }
  function renderMarketCards(){const marketCards=marketCard("twse","上市")+marketCard("tpex","上櫃");$("#chipsDate").textContent=payload.metadata?.updated_at?formatTime(payload.metadata.updated_at):"盤後資料同步中";$("#marketFlowCards").innerHTML=marketCards||'<div class="empty compact-empty">市場法人彙總同步中；單一標的仍可使用下方搜尋。</div>'}

  const hasAny=(object,keys)=>keys.some(key=>finite(object?.[key])!=null);
  const trendRows=item=>{
    const history=item.history||item.recent||[];
    const rows=Array.isArray(history)?history.filter(row=>row?.date&&(hasAny(row.institutional,["foreign_net","trust_net","dealer_net"])||hasAny(row.margin,["balance","change"])||hasAny(row.short,["balance","change"]))):[];
    if(!rows.length)return "";
    return `<div class="chip-trend"><h3>最近五日趨勢</h3><div class="table-wrap"><table><thead><tr><th>日期</th><th>外資（張）</th><th>投信（張）</th><th>自營商（張）</th><th>融資增減（張）</th><th>融券增減（張）</th></tr></thead><tbody>${rows.slice(0,5).map(row=>`<tr><td>${escapeHtml(row.date||"—")}</td><td class="${cls(row.institutional?.foreign_net)}">${displayLots(row.institutional?.foreign_net)}</td><td class="${cls(row.institutional?.trust_net)}">${displayLots(row.institutional?.trust_net)}</td><td class="${cls(row.institutional?.dealer_net)}">${displayLots(row.institutional?.dealer_net)}</td><td class="${cls(row.margin?.change)}">${display(row.margin?.change)}</td><td class="${cls(row.short?.change)}">${display(row.short?.change)}</td></tr>`).join("")}</tbody></table></div></div>`;
  };
  const sourceLine=item=>{
    const sources=(item.sources||[]).map(source=>source?.name).filter(Boolean);
    return sources.length?`<p class="chip-source-note">資料來源：${escapeHtml([...new Set(sources)].join("、"))}${item.date?` · ${escapeHtml(item.date)}`:""} · 單位：${escapeHtml(item.unit||"張")}</p>`:"";
  };
  const detail=item=>{
    const quote=marketMap.get(String(item.symbol))||{};
    const institutional=item.institutional||{},margin=item.margin||{},short=item.short||{},dayTrade=item.day_trade||{};
    const institutionalAvailable=hasAny(institutional,["foreign_net","trust_net","dealer_net","total_net"]);
    const creditAvailable=hasAny(margin,["balance","change"])||hasAny(short,["balance","change","ratio"])||hasAny(dayTrade,["volume","ratio"]);
    const sections=[];
    if(institutionalAvailable)sections.push(`<section><h3>三大法人</h3><div class="chip-metric-grid"><div><small>外資買賣超</small><strong class="${cls(institutional.foreign_net)}">${displayLots(institutional.foreign_net)}</strong></div><div><small>投信買賣超</small><strong class="${cls(institutional.trust_net)}">${displayLots(institutional.trust_net)}</strong></div><div><small>自營商買賣超</small><strong class="${cls(institutional.dealer_net)}">${displayLots(institutional.dealer_net)}</strong></div><div><small>三大法人合計</small><strong class="${cls(institutional.total_net)}">${displayLots(institutional.total_net)}</strong></div></div></section>`);
    if(creditAvailable)sections.push(`<section><h3>信用交易與當沖</h3><div class="chip-metric-grid"><div><small>當沖量</small><strong>${display(dayTrade.volume)}</strong></div><div><small>當沖比</small><strong>${finite(dayTrade.ratio)==null?"—":pct(dayTrade.ratio)}</strong></div><div><small>融資餘額（張）</small><strong>${display(margin.balance)}</strong></div><div><small>融資增減（張）</small><strong class="${cls(margin.change)}">${display(margin.change)}</strong></div><div><small>融券餘額（張）</small><strong>${display(short.balance)}</strong></div><div><small>融券增減（張）</small><strong class="${cls(short.change)}">${display(short.change)}</strong></div></div></section>`);
    const noData=!institutionalAvailable&&!creditAvailable;
    return `<article class="chip-detail-card"><div class="chip-detail-head"><div><span class="tag">${escapeHtml(quote.asset_class==="etf"?"ETF":"個股")}</span><strong>${escapeHtml(item.symbol)}</strong><span>${escapeHtml(item.name||quote.name||"")}</span></div><a class="btn" href="asset.html?symbol=${encodeURIComponent(item.symbol)}">查看標的 →</a></div>${item.current_session_note?`<p class="status-warning">${escapeHtml(item.current_session_note)}</p>`:""}<div class="chip-summary-line"><span>成交價 <b>${display(quote.price,2)}</b></span><span>漲跌幅 <b class="${cls(quote.change_percent)}">${pct(quote.change_percent)}</b></span><span>成交量 <b>${display(quote.volume)}</b></span><span>成交金額 <b>${display(quote.trade_value)}</b></span></div>${noData?'<div class="empty compact-empty chip-no-data">尚未取得此標的的法人、資券或當沖資料；行情資料仍可正常查看。資料通道會保留最後成功版本並分批補齊。</div>':`<div class="chip-section-grid">${sections.join("")}</div>`}${trendRows(item)}${sourceLine(item)}<p class="broker-note">${escapeHtml(item.broker_note||"公開分點與籌碼資料僅供觀察，不代表券商、外資或最終客戶的真實持倉。")}</p></article>`;
  };

  let selectedSymbol="";
  function renderItem(symbol,{writeInput=false}={}){
    const selected=searchable.find(item=>String(item.symbol)===String(symbol));
    if(!selected)return;
    selectedSymbol=String(selected.symbol);
    if(writeInput)$("#chipSymbol").value=selectedSymbol;
    $("#chipSuggestions").innerHTML="";
    const chip=chipFor(selectedSymbol);
    $("#chipResult").innerHTML=detail({...selected,...chip,name:chip.name||selected.name});
  }
  function search(){
    const input=$("#chipSymbol"),raw=input.value,query=raw.trim().toUpperCase();
    if(!query){selectedSymbol="";$("#chipSuggestions").innerHTML="";$("#chipResult").innerHTML='<div class="empty">請輸入股票或 ETF 代碼／名稱，再選擇要查看的標的。</div>';return}
    const exact=searchable.find(item=>String(item.symbol).toUpperCase()===query);
    if(exact){renderItem(exact.symbol,{writeInput:false});return}
    selectedSymbol="";
    const matches=searchable.filter(item=>`${item.symbol} ${item.name||""}`.toUpperCase().includes(query)).slice(0,8);
    $("#chipSuggestions").innerHTML=matches.map(item=>`<button type="button" data-chip-symbol="${escapeHtml(item.symbol)}"><b>${escapeHtml(item.symbol)}</b><span>${escapeHtml(item.name||"")}</span><small>${item.asset_class==="etf"?"ETF":"個股"}</small></button>`).join("")||'<div class="empty compact-empty">找不到符合的標的</div>';
    document.querySelectorAll("[data-chip-symbol]").forEach(button=>button.onclick=()=>renderItem(button.dataset.chipSymbol,{writeInput:true}));
    $("#chipResult").innerHTML='<div class="empty">請從上方搜尋建議選擇一個標的。</div>';
  }
  const input=$("#chipSymbol");
  input.addEventListener("input",search);
  input.addEventListener("keydown",event=>{
    if(event.key==="Escape"){$("#chipSuggestions").innerHTML="";return}
    if(event.key!=="Enter")return;
    const exact=searchable.find(item=>String(item.symbol).toUpperCase()===input.value.trim().toUpperCase());
    const first=document.querySelector("[data-chip-symbol]");
    if(exact){event.preventDefault();renderItem(exact.symbol,{writeInput:false})}
    else if(first){event.preventDefault();renderItem(first.dataset.chipSymbol,{writeInput:true})}
  });
  $("#clearChipSearch").onclick=()=>{input.value="";search();input.focus()};

  const isEtf=item=>item.asset_class==="etf";
  const hot=etf=>{
    const rows=marketItems.filter(item=>["stock","etf"].includes(item.asset_class)&&isEtf(item)===etf);
    const maxValue=Math.max(1,...rows.map(item=>finite(item.trade_value)||0)),maxVolume=Math.max(1,...rows.map(item=>finite(item.volume)||0));
    return rows.map(item=>{
      const chip=chipFor(item.symbol),foreign=Math.abs(finite(chip.institutional?.foreign_net)||0),dayRatio=Math.abs(finite(chip.day_trade?.ratio)||0);
      const rawScore=((finite(item.trade_value)||0)/maxValue)*55+((finite(item.volume)||0)/maxVolume)*25+Math.min(Math.abs(finite(item.change_percent)||0),10)*1.2+Math.min(foreign/1000000,5)+Math.min(dayRatio,100)*.03;
      return {...item,chip,rawScore};
    }).sort((a,b)=>b.rawScore-a.rawScore).slice(0,10).map((item,index,selected)=>{
      const top=selected[0]?.rawScore||1;
      return {...item,score:Math.max(1,Math.round(item.rawScore/top*100))};
    });
  };
  const hotHtml=rows=>rows.map((item,index)=>`<tr><td>${index+1}</td><td><a href="asset.html?symbol=${encodeURIComponent(item.symbol)}"><b>${escapeHtml(item.symbol)}</b><br><small>${escapeHtml(item.name||"")}</small></a></td><td><span class="hot-score">${item.score}</span></td><td class="${cls(item.change_percent)}">${pct(item.change_percent)}</td><td>${display(item.trade_value)}</td><td class="${cls(item.chip.institutional?.foreign_net)}">${displayLots(item.chip.institutional?.foreign_net)}</td><td>${finite(item.chip.day_trade?.ratio)==null?"—":pct(item.chip.day_trade.ratio)}</td></tr>`).join("")||'<tr><td colspan="7" class="empty">等待市場資料</td></tr>';
  function renderHot(){$("#hotStocks").innerHTML=hotHtml(hot(false));$("#hotEtfs").innerHTML=hotHtml(hot(true));}
  function refreshMounted(){rebuildDerived();renderMarketCards();renderHot();if(selectedSymbol&&searchable.some(item=>String(item.symbol)===selectedSymbol))renderItem(selectedSymbol);else if($("#chipSymbol").value.trim())search()}
  refreshMounted();
  loadData("tw-chips-compact.json",payload).then(fresh=>{if(fresh?.markets){payload=fresh;refreshMounted()}}).catch(()=>{});
  loadData("tw-market-compact.json",market).then(fresh=>{if(Array.isArray(fresh?.items)&&fresh.items.length){market=fresh;refreshMounted()}}).catch(()=>{});
})();
