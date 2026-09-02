(function(root,factory){
  const api=factory();
  if(typeof module==="object"&&module.exports)module.exports=api;
  else root.MR_DYNAMIC_LEADERS=api;
})(typeof globalThis!=="undefined"?globalThis:this,function(){
  "use strict";
  const finite=value=>{if(value===null||value===undefined||value==="")return null;const n=Number(String(value).replace(/,/g,""));return Number.isFinite(n)?n:null};
  const clean=value=>String(value||"").replace(/<[^>]*>/g," ").replace(/\s+/g," ").trim();
  const toMap=(items,key="symbol")=>{
    if(Array.isArray(items))return new Map(items.map(row=>[String(row?.[key]||"").toUpperCase(),row]));
    return new Map(Object.entries(items||{}).map(([id,row])=>[String(row?.[key]||id||"").toUpperCase(),row]));
  };
  const logNorm=(value,max)=>value>0&&max>0?Math.log1p(value)/Math.log1p(max):0;
  const symbolsForNews=item=>{
    const symbols=new Set((item?.symbols||[]).map(String));
    for(const row of item?.companies||[])if(row?.symbol)symbols.add(String(row.symbol));
    return [...symbols].map(value=>value.toUpperCase().replace(/\.(?:TW|TWO)$/i,""));
  };
  const INDUSTRY_CODE_MAP={"01":"水泥","02":"食品","03":"塑膠","04":"紡織纖維","05":"電機機械","06":"電器電纜","08":"玻璃陶瓷","09":"造紙","10":"鋼鐵","11":"橡膠","12":"汽車","14":"建材營造","15":"航運","16":"觀光餐旅","17":"金融保險","18":"貿易百貨","20":"其他","21":"化學","22":"生技醫療","23":"油電燃氣","24":"半導體","25":"電腦及週邊設備","26":"光電","27":"通信網路","28":"電子零組件","29":"電子通路","30":"資訊服務","31":"其他電子","32":"數位雲端","33":"綠能環保","34":"電子商務","35":"居家生活","36":"運動休閒"};
  function normalizeIndustry(value){const raw=clean(value);if(!raw)return"";const match=raw.match(/^0?(\d{1,3})$/);if(match)return INDUSTRY_CODE_MAP[String(match[1]).padStart(2,"0")]||"其他";if(/^\d+(?:[.\-]\d+)?$/.test(raw))return"其他";return raw;}
  function classifySector(row={},basic={}){
    const symbol=String(row.symbol||basic.symbol||"");
    const name=clean(row.name||basic.short_name||basic.company_name||"");
    const official=normalizeIndustry(basic.industry_name||basic.industry||basic.industry_code||row.industry||row.industry_code||"");
    const scope=clean(basic.business_scope||"");
    const canonical=`${name} ${official} ${scope}`;
    const exact=[
      [/台積電|聯電|世界先進|力積電|晶圓代工/,"晶圓代工"],
      [/聯發科|瑞昱|創意|世芯|智原|IC設計|IC 設計/,"IC 設計"],
      [/日月光|矽品|京元電子|力成|封裝|測試/,"封裝測試"],
      [/奇鋐|雙鴻|健策|建準|散熱|風扇|水冷|冷卻/,"散熱"],
      [/金像電|欣興|南電|臻鼎|健鼎|華通|PCB|印刷電路|載板|ABF/,"PCB／載板"],
      [/智邦|啟碁|中磊|正文|交換器|網通|高速傳輸|光通訊/,"網通／高速傳輸"],
      [/南亞科|華邦電|旺宏|群聯|威剛|DRAM|NAND|記憶體|儲存/,"記憶體／儲存"],
      [/鴻海|廣達|緯創|英業達|緯穎|仁寶|伺服器|電腦系統|ODM|EMS/,"AI 伺服器／電腦"],
      [/台達電|光寶科|康舒|群電|電源供應|電源管理|能源管理/,"電源／能源管理"],
      [/華城|士電|中興電|亞力|重電|電機機械/,"重電／電機"],
      [/中華電|台灣大|遠傳|電信|通信服務/,"電信"],
    ];
    for(const [pattern,label] of exact)if(pattern.test(canonical))return label;
    const officialRules=[
      [/半導體/,"半導體"],[/電子零組件/,"電子零組件"],[/其他電子/,"電子製造"],
      [/金融|銀行|金控|證券|保險|壽險/,"金融"],[/航運|海運|航空/,"航運"],
      [/鋼鐵|水泥|塑膠|化工|玻璃|造紙/,"原物料"],[/生技|醫療|製藥|醫材/,"生技醫療"],
      [/汽車/,"汽車／車電"],[/電器電纜/,"電器電纜"],[/觀光|餐旅/,"觀光餐旅"],
      [/建材營造/,"營建"],[/食品/,"食品"],[/貿易百貨/,"貿易百貨"],
    ];
    for(const [pattern,label] of officialRules)if(pattern.test(official))return label;
    const raw=official.replace(/業$/," ").trim();
    return raw||`其他產業${symbol?` ${symbol}`:""}`;
  }
  function buildNewsSignals(newsItems=[],now=Date.now()){
    const map=new Map();
    for(const item of newsItems||[]){
      const published=Date.parse(item?.published_at||item?.date||0),ageDays=(now-published)/86400000;
      if(!Number.isFinite(ageDays)||ageDays<0||ageDays>7)continue;
      const base=Math.max(0,finite(item.importance_score)||0)+(item.impact==="high"?35:item.impact==="medium"?16:6)+(item.is_major?18:0);
      const score=base*Math.max(.15,1-ageDays/8);
      const text=clean(`${item.title||""} ${item.ai_summary||item.summary||""}`);
      for(const symbol of symbolsForNews(item)){
        const old=map.get(symbol)||{score:0,text:"",count:0};
        map.set(symbol,{score:old.score+score,text:`${old.text} ${text}`.trim(),count:old.count+1});
      }
    }
    return map;
  }
  function selectDynamicLeaders({marketItems=[],basicsItems={},chipItems={},newsItems=[],now=Date.now(),limit=10,minSectors=6,maxPerSector=2}={}){
    const basics=toMap(basicsItems),chips=toMap(chipItems),newsSignals=buildNewsSignals(newsItems,now);
    let candidates=(marketItems||[]).filter(row=>row?.asset_class==="stock"&&/^\d{4}$/.test(String(row.symbol||""))&&finite(row.price)>0&&finite(row.trade_value)>0);
    if(!candidates.length)return[];
    candidates=candidates.map(row=>{
      const symbol=String(row.symbol),basic=basics.get(symbol)||{},chip=chips.get(symbol)||{},signal=newsSignals.get(symbol)||{score:0,text:"",count:0};
      const price=finite(row.price)||0,shares=finite(basic.issued_shares)||(finite(basic.paid_in_capital)||0)/10;
      const marketCap=shares>0?shares*price:0,tradeValue=Math.max(0,finite(row.trade_value)||0),volume=Math.max(0,finite(row.volume)||0);
      const change=finite(row.change_percent)||0,foreignNet=finite(chip?.institutional?.foreign_net)||0;
      return {...row,basic,chip,signal,marketCap,tradeValue,volume,change,foreignNet,sector:classifySector(row,basic)};
    });
    const maxima={
      marketCap:Math.max(1,...candidates.map(x=>x.marketCap)),tradeValue:Math.max(1,...candidates.map(x=>x.tradeValue)),
      volume:Math.max(1,...candidates.map(x=>x.volume)),foreign:Math.max(1,...candidates.map(x=>Math.abs(x.foreignNet))),news:Math.max(1,...candidates.map(x=>x.signal.score))
    };
    const sectorCapRanks=new Map();
    for(const row of candidates){const rows=sectorCapRanks.get(row.sector)||[];rows.push(row);sectorCapRanks.set(row.sector,rows)}
    for(const rows of sectorCapRanks.values())rows.sort((a,b)=>b.marketCap-a.marketCap||b.tradeValue-a.tradeValue||String(a.symbol).localeCompare(String(b.symbol)));
    candidates=candidates.map(row=>{
      const sectorRank=(sectorCapRanks.get(row.sector)||[]).findIndex(x=>x.symbol===row.symbol);
      const parts={
        marketCap:36*logNorm(row.marketCap,maxima.marketCap),
        tradeValue:29*logNorm(row.tradeValue,maxima.tradeValue),
        volume:6*logNorm(row.volume,maxima.volume),
        momentum:7*Math.min(Math.abs(row.change)/10,1),
        institutional:9*logNorm(Math.abs(row.foreignNet),maxima.foreign),
        news:11*logNorm(row.signal.score,maxima.news),
        sectorLeadership:sectorRank===0?8:sectorRank===1?4:0,
      };
      const score=Object.values(parts).reduce((sum,value)=>sum+value,0);
      const reasonKey=Object.entries(parts).sort((a,b)=>b[1]-a[1])[0]?.[0];
      const reasons={marketCap:"市值代表",tradeValue:"成交額焦點",volume:"量能焦點",momentum:row.change>=0?"強勢動能":"波動焦點",institutional:row.foreignNet>=0?"法人買超":"法人資金焦點",news:"新聞／財報焦點",sectorLeadership:"產業代表"};
      return {...row,score,score_parts:parts,selection_reason:reasons[reasonKey]||"市場焦點"};
    }).sort((a,b)=>b.score-a.score||b.tradeValue-a.tradeValue||String(a.symbol).localeCompare(String(b.symbol)));
    const grouped=new Map();for(const row of candidates){const rows=grouped.get(row.sector)||[];rows.push(row);grouped.set(row.sector,rows)}
    const sectorGroups=[...grouped.entries()].sort((a,b)=>b[1][0].score-a[1][0].score||a[0].localeCompare(b[0],"zh-Hant"));
    const selected=[],counts=new Map(),seen=new Set();
    const add=row=>{if(!row||seen.has(row.symbol)||(counts.get(row.sector)||0)>=maxPerSector)return false;selected.push(row);seen.add(row.symbol);counts.set(row.sector,(counts.get(row.sector)||0)+1);return true};
    for(const [,rows] of sectorGroups.slice(0,Math.min(minSectors,sectorGroups.length)))add(rows[0]);
    for(const row of candidates){if(selected.length>=limit)break;add(row)}
    return selected.slice(0,limit).map((row,index)=>({...row,dynamic_order:index+1}));
  }
  function buildSectorHeatGroups({leaders=[],marketItems=[],basicsItems={},limit=5,stocksPerSector=2}={}){
    const basics=toMap(basicsItems),marketBySector=new Map();
    const leaderBySector=new Map();
    for(const row of leaders||[]){
      const sector=row.sector||"其他產業";
      const list=leaderBySector.get(sector)||[];if(!list.some(item=>item.symbol===row.symbol))list.push(row);leaderBySector.set(sector,list);
    }
    for(const row of marketItems||[]){
      if(row?.asset_class!=="stock"||!/^\d{4}$/.test(String(row.symbol||"")))continue;
      const symbol=String(row.symbol||"");
      const sector=classifySector(row,basics.get(symbol)||{});
      if(!leaderBySector.has(sector))continue;
      const list=marketBySector.get(sector)||[];list.push(row);marketBySector.set(sector,list);
    }
    const groups=[];
    for(const [sector,rows] of leaderBySector){
      const members=marketBySector.get(sector)||rows;
      const valid=members.filter(row=>finite(row.change_percent)!=null&&finite(row.trade_value)>0);
      const totalValue=valid.reduce((sum,row)=>sum+(finite(row.trade_value)||0),0);
      const weighted=totalValue?valid.reduce((sum,row)=>sum+(finite(row.change_percent)||0)*(finite(row.trade_value)||0),0)/totalValue:0;
      const up=valid.filter(row=>(finite(row.change_percent)||0)>0).length,down=valid.filter(row=>(finite(row.change_percent)||0)<0).length;
      const top=[...rows].sort((a,b)=>b.score-a.score||b.tradeValue-a.tradeValue).slice(0,stocksPerSector);
      groups.push({sector,change_percent:weighted,trade_value:totalValue,up,down,stocks:top,heat_score:Math.abs(weighted)*15+Math.log1p(totalValue)});
    }
    return groups.sort((a,b)=>b.heat_score-a.heat_score||b.trade_value-a.trade_value).slice(0,limit);
  }
  return {classifySector,normalizeIndustry,INDUSTRY_CODE_MAP,buildNewsSignals,selectDynamicLeaders,buildSectorHeatGroups};
});
