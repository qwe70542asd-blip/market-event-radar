// v11.4.57: fail closed for stale breadth/chips, but keep a verified same-session TAIEX quote visible.
(()=>{
  "use strict";
  const fmtDay=value=>String(value||"").slice(0,10);
  const dayText=value=>fmtDay(value).replaceAll("-","/");
  const finite=value=>{if(value===null||value===undefined||value==="")return null;const n=Number(value);return Number.isFinite(n)?n:null};
  const parseDay=value=>{const text=fmtDay(value);return /^\d{4}-\d{2}-\d{2}$/.test(text)?Date.parse(`${text}T12:00:00+08:00`):NaN};
  const fallbackTooOld=day=>{const at=parseDay(day);return !Number.isFinite(at)||Date.now()-at>5*86400000};
  const assessDates=(marketDate,chipDate,referenceDate)=>{
    marketDate=fmtDay(marketDate);chipDate=fmtDay(chipDate);referenceDate=fmtDay(referenceDate);
    const referenceAhead=!!(referenceDate&&marketDate&&referenceDate>marketDate);
    const marketStale=!marketDate||referenceAhead||(!referenceDate&&fallbackTooOld(marketDate));
    const chipsStale=!marketStale&&(!chipDate||chipDate<marketDate);
    return {marketStale,chipsStale,marketDate,chipDate,referenceDate,referenceAhead};
  };
  if(typeof globalThis!=="undefined")globalThis.__MR_ASSESS_TW_DATES__=assessDates;
  let state=null,applying=false;
  const setText=(id,text,cls)=>{const node=document.getElementById(id);if(!node)return;node.textContent=text;if(cls!==undefined)node.className=cls};
  const partialTone=change=>change>=.35?"偏多":change<=-.35?"偏空":"震盪";
  const partialChange=value=>`${value>0?"+":""}${value.toFixed(2)}%`;
  function applyPartialMarket(){
    if(applying||!state?.partialLive)return;applying=true;
    const {marketDate,chipDate,referenceDate,referenceChange}=state,tone=partialTone(referenceChange);
    setText("marketFreshness","部分即時","status-pill warning");setText("marketUpdated",`指數 ${dayText(referenceDate)}／廣度 ${dayText(marketDate)||"待更新"}`);
    setText("marketTone",`${tone} ${partialChange(referenceChange)}`,referenceChange>0?"up":referenceChange<0?"down":"flat");
    setText("breadthSummary",`待更新（${dayText(marketDate)||"未確認"}）`);
    setText("foreignDirection","待更新","flat");setText("foreignDirectionDetail",`法人 ${dayText(chipDate)||"未確認"}／最新指數 ${dayText(referenceDate)}`);
    setText("volumeMomentum","待更新");setText("volumeMomentumNote","等待全市場成交資料完成同步");
    setText("focusUpdated",`即時指數 ${dayText(referenceDate)} · 全市場 ${dayText(marketDate)||"待更新"} · 法人 ${dayText(chipDate)||"待更新"}`);
    setText("briefMarketTone",`${tone} ${partialChange(referenceChange)}`);setText("briefForeign","待更新");
    setText("todayBriefSentence",`台股加權指數 ${tone} ${partialChange(referenceChange)}；全市場廣度、成交動能與法人資料仍等待 ${dayText(referenceDate)} 完整更新。`);
    setText("marketHeatScore","—");setText("marketHeatLabel","等待全市場");setText("marketHeatUp","—");setText("marketHeatDown","—");setText("marketHeatFlat","—");setText("marketHeatDate",`指數 ${dayText(referenceDate)} · 廣度待更新`);
    const sector=document.getElementById("sectorMomentumUpdated");if(sector)sector.textContent=`等待 ${dayText(referenceDate)} 全市場行情`;
    const root=document.getElementById("marketStateSummary");root?.classList.add("market-data-partial");root?.classList.remove("market-data-stale","chip-data-stale");queueMicrotask(()=>{applying=false});
  }
  function applyMarketStale(){
    if(applying||!state?.marketStale||state?.partialLive)return;applying=true;
    const {marketDate,chipDate,referenceDate}=state;
    setText("marketFreshness","資料延遲","status-pill warning");setText("marketUpdated",`資料日期 ${dayText(marketDate)||"未確認"}`);
    setText("marketTone","暫不判定","flat");setText("breadthSummary","資料延遲");setText("foreignDirection","待更新","flat");
    setText("foreignDirectionDetail",`法人 ${dayText(chipDate)||"未確認"}／行情 ${dayText(marketDate)||"未確認"}`);
    setText("volumeMomentum","暫不判定");setText("volumeMomentumNote",`等待最新有效交易日${referenceDate?`（參考 ${dayText(referenceDate)}）`:""}`);
    setText("focusUpdated",`行情 ${dayText(marketDate)||"未確認"} · 最新參考 ${dayText(referenceDate)||"待確認"}`);
    setText("briefMarketTone","資料延遲");setText("briefForeign","資料延遲");
    setText("todayBriefSentence",`台股資料延遲：最後行情 ${dayText(marketDate)||"未確認"}，暫停今日盤勢、外資與量能判讀。`);
    const root=document.getElementById("marketStateSummary");root?.classList.add("market-data-stale");root?.classList.remove("market-data-partial","chip-data-stale");queueMicrotask(()=>{applying=false});
  }
  // Keep valid price/breadth/volume conclusions when only institutional data is behind.
  function applyChipStale(){
    if(applying||!state?.chipsStale||state?.marketStale)return;applying=true;
    const {marketDate,chipDate}=state;
    setText("foreignDirection","待更新","flat");setText("foreignDirectionDetail",`法人 ${dayText(chipDate)||"未確認"}／行情 ${dayText(marketDate)||"未確認"}`);setText("briefForeign","待更新");
    const root=document.getElementById("marketStateSummary");root?.classList.remove("market-data-stale","market-data-partial");root?.classList.add("chip-data-stale");queueMicrotask(()=>{applying=false});
  }
  function clearGuard(){const root=document.getElementById("marketStateSummary");root?.classList.remove("market-data-stale","market-data-partial","chip-data-stale")}
  function applyState(){if(state?.partialLive)applyPartialMarket();else if(state?.marketStale)applyMarketStale();else if(state?.chipsStale)applyChipStale();else clearGuard()}
  async function assess(){
    if(!window.MR?.loadData)return;
    const twFallback=window.__TW_MARKET_SEED__||{items:[],metadata:{}},chipsFallback=window.__TW_CHIPS_SEED__||{markets:{},metadata:{}},snapFallback=window.__MARKET_SNAPSHOT_SEED__||{items:[],metadata:{}};
    try{
      const [tw,chips,snapshot]=await Promise.all([
        MR.loadData("tw-market.json",twFallback,{force:true}).catch(()=>twFallback),MR.loadData("tw-chips.json",chipsFallback,{force:true}).catch(()=>chipsFallback),MR.loadData("market-snapshot.json",snapFallback,{force:true}).catch(()=>snapFallback)
      ]);
      const marketDate=fmtDay(tw?.metadata?.trading_date),chipDate=fmtDay(chips?.metadata?.trading_date),twii=(snapshot?.items||[]).find(row=>String(row?.symbol||"").toUpperCase()==="^TWII"),referenceDate=fmtDay(twii?.session_date||twii?.price_date||twii?.ohlc_date);
      let referenceChange=finite(twii?.change_percent);const price=finite(twii?.price),prev=finite(twii?.previous_close);if(referenceChange==null&&price!=null&&prev!=null&&prev!==0)referenceChange=(price-prev)/prev*100;
      state={...assessDates(marketDate,chipDate,referenceDate),referenceChange};state.partialLive=!!(state.marketStale&&state.referenceAhead&&referenceChange!=null);
      applyState();
    }catch(error){console.warn("stale market guard assessment failed",error)}
  }
  const boot=()=>{assess();setTimeout(assess,2000);setInterval(assess,60000);const root=document.getElementById("marketStateSummary");if(root)new MutationObserver(()=>{if(!applying)applyState()}).observe(root,{subtree:true,childList:true,characterData:true,attributes:true})};
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot();
})();
