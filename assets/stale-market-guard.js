// v11.4.53: fail closed when Taiwan market/chip data is older than the latest verified ^TWII session.
(()=>{
  "use strict";
  const fmtDay=value=>String(value||"").slice(0,10);
  const dayText=value=>fmtDay(value).replaceAll("-","/");
  const parseDay=value=>{
    const text=fmtDay(value);
    return /^\d{4}-\d{2}-\d{2}$/.test(text)?Date.parse(`${text}T12:00:00+08:00`):NaN;
  };
  const fallbackTooOld=day=>{
    const at=parseDay(day);
    if(!Number.isFinite(at))return true;
    return Date.now()-at>5*86400000;
  };
  let state=null,applying=false;

  function setText(id,text,cls){
    const node=document.getElementById(id);
    if(!node)return;
    node.textContent=text;
    if(cls!==undefined)node.className=cls;
  }
  function apply(){
    if(applying||!state?.stale)return;
    applying=true;
    const {marketDate,chipDate,referenceDate}=state;
    setText("marketFreshness","資料延遲","status-pill warning");
    setText("marketUpdated",`資料日期 ${dayText(marketDate)||"未確認"}`);
    setText("marketTone","暫不判定","flat");
    setText("breadthSummary","資料延遲");
    setText("foreignDirection","待更新","flat");
    setText("foreignDirectionDetail",`法人 ${dayText(chipDate)||"未確認"}／行情 ${dayText(marketDate)||"未確認"}`);
    setText("volumeMomentum","暫不判定");
    setText("volumeMomentumNote",`等待最新有效交易日${referenceDate?`（參考 ${dayText(referenceDate)}）`:""}`);
    setText("focusUpdated",`行情 ${dayText(marketDate)||"未確認"} · 最新參考 ${dayText(referenceDate)||"待確認"}`);
    setText("briefMarketTone","資料延遲");
    setText("briefForeign","資料延遲");
    setText("todayBriefSentence",`台股資料延遲：最後行情 ${dayText(marketDate)||"未確認"}，暫停今日盤勢、外資與量能判讀。`);
    document.getElementById("marketStateSummary")?.classList.add("market-data-stale");
    queueMicrotask(()=>{applying=false});
  }

  async function assess(){
    if(!window.MR?.loadData)return;
    const twFallback=window.__TW_MARKET_SEED__||{items:[],metadata:{}};
    const chipsFallback=window.__TW_CHIPS_SEED__||{markets:{},metadata:{}};
    const snapFallback=window.__MARKET_SNAPSHOT_SEED__||{items:[],metadata:{}};
    try{
      const [tw,chips,snapshot]=await Promise.all([
        MR.loadData("tw-market.json",twFallback,{force:true}).catch(()=>twFallback),
        MR.loadData("tw-chips.json",chipsFallback,{force:true}).catch(()=>chipsFallback),
        MR.loadData("market-snapshot.json",snapFallback,{force:true}).catch(()=>snapFallback),
      ]);
      const marketDate=fmtDay(tw?.metadata?.trading_date);
      const chipDate=fmtDay(chips?.metadata?.trading_date);
      const twii=(snapshot?.items||[]).find(row=>String(row?.symbol||"").toUpperCase()==="^TWII");
      const referenceDate=fmtDay(twii?.session_date||twii?.price_date||twii?.ohlc_date);
      const referenceAhead=referenceDate&&marketDate&&referenceDate>marketDate;
      const chipsBehind=chipDate&&marketDate&&chipDate<marketDate;
      const stale=!marketDate||referenceAhead||fallbackTooOld(marketDate);
      state={stale,marketDate,chipDate,referenceDate,chipsBehind};
      if(stale)apply();
      else document.getElementById("marketStateSummary")?.classList.remove("market-data-stale");
    }catch(error){
      console.warn("stale market guard assessment failed",error);
    }
  }

  const boot=()=>{
    assess();
    setTimeout(assess,2000);
    setInterval(assess,60000);
    const root=document.getElementById("marketStateSummary");
    if(root){
      new MutationObserver(()=>{if(!applying&&state?.stale)apply()})
        .observe(root,{subtree:true,childList:true,characterData:true,attributes:true});
    }
  };
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});
  else boot();
})();
