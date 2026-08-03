(() => {
  "use strict";

  const VERSION = "11.2.5";
  const OWNER = "qwe70542asd-blip";
  const REPO = "market-event-radar";
  const LEGACY_LIVE_BASE = `https://raw.githubusercontent.com/${OWNER}/${REPO}/live-data/`;
  const MAIN_BASE = `https://raw.githubusercontent.com/${OWNER}/${REPO}/main/`;
  const DATA_CHANNELS = Object.freeze({
    assets: {
      branch:"live-assets", label:"股票主檔／財務／ETF",
      files:["assets.json","asset-coverage.json"]
    },
    events: {
      branch:"live-events", label:"市場事件月曆",
      files:["events.json"]
    },
    twMarket: {
      branch:"live-tw-market", label:"台股與 ETF 行情",
      files:["tw-market.json"]
    },
    twChips: {
      branch:"live-tw-chips", label:"法人／當沖／融資券",
      files:["tw-chips.json"]
    },
    globalMarket: {
      branch:"live-global-market", label:"全球市場行情",
      files:["market-snapshot.json"]
    },
    news: {
      branch:"live-news", label:"多來源財經新聞",
      files:["news.json","news-link-cache.json"]
    }
  });
  const DATA_BRANCH_BY_FILE = Object.fromEntries(
    Object.values(DATA_CHANNELS).flatMap(channel => channel.files.map(file => [file, channel.branch]))
  );
  const PORTFOLIO_KEY = "market-radar-portfolio-v11-1";
  const LEGACY_PORTFOLIO_KEYS = ["market-radar-portfolio-v11", "market-radar-portfolio-v11-0", "market-radar-portfolio-v10-3", "market-radar-portfolio-v10", "market-event-radar-portfolio", "market-radar-portfolio"];
  const QUOTE_CACHE_KEY = "market-radar-quote-cache-v11-1";

  const OFFICIAL_OVERRIDES = {
    "TW:00403A": {
      id:"TW:00403A", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"00403A", name:"主動統一升級50", sector:"fund",
      sub_industry:"台灣主動式 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["統一台股升級50主動式ETF","統一升級50","主動統一升級50"],
      etf:{
        issuer:"統一證券投資信託股份有限公司",
        category:"主動式 ETF",
        benchmark:"臺灣證券交易所發行量加權股價報酬指數",
        strategy:"至少六成配置台股市值前 200 大企業，以前 50 大為核心，搭配 51–200 大增強選股池。",
        distribution:"尚無配息資料",
        official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/00403A"
      }
    },
    "TW:00981A": {
      id:"TW:00981A", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"00981A", name:"主動統一台股增長", sector:"fund",
      sub_industry:"台灣主動式 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["統一台股增長主動式ETF","統一台股增長","主動統一台股增長"],
      etf:{
        issuer:"統一證券投資信託股份有限公司",
        category:"主動式 ETF",
        benchmark:"臺灣證券交易所發行量加權股價報酬指數",
        strategy:"以大型、創新、成長為核心選股邏輯，至少六成配置大型股。",
        distribution:"季配；歷史配息依官方公告",
        official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/00981A"
      }
    },
    "TW:009816": {
      id:"TW:009816", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"009816", name:"凱基台灣TOP50", sector:"fund",
      sub_industry:"台灣市值型 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["凱基台灣 TOP 50","凱基TOP50"],
      etf:{
        issuer:"凱基證券投資信託股份有限公司",
        category:"台股 ETF",
        benchmark:"臺灣指數公司特選臺灣 TOP 50 指數",
        strategy:"追蹤特選臺灣 TOP 50 指數，聚焦大型權值企業。",
        distribution:"尚無配息資料",
        official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/009816"
      }
    },
    "TW:00663L": {
      id:"TW:00663L", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"00663L", name:"國泰臺灣加權正2", sector:"fund",
      sub_industry:"台灣槓桿型 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["國泰臺指正2","國泰臺灣加權指數單日正向2倍基金"],
      etf:{
        issuer:"國泰證券投資信託股份有限公司",
        manager:"蘇鼎宇",
        category:"股票槓反ETF",
        benchmark:"臺灣日報酬兩倍指數",
        leverage:"單日正向 2 倍",
        strategy:"追求臺灣加權指數單日報酬的兩倍。",
        distribution:"尚無配息資料",
        official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/00663L"
      }
    },
    "TW:00631L": {
      id:"TW:00631L", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"00631L", name:"元大台灣50正2", sector:"fund",
      sub_industry:"台灣槓桿型 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["台灣50正2","元大台灣50單日正向2倍"],
      etf:{
        issuer:"元大證券投資信託股份有限公司",
        category:"股票槓反 ETF",
        benchmark:"臺灣 50 指數",
        leverage:"單日正向 2 倍",
        strategy:"追求臺灣 50 指數單日報酬的兩倍；不適合以兩倍長期報酬直線推估。",
        distribution:"尚無配息資料",
        official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/00631L"
      }
    },
    "TW:0050": {
      id:"TW:0050", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"0050", name:"元大台灣50", sector:"fund",
      sub_industry:"台灣市值型 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["元大台灣卓越50","台灣50"],
      etf:{issuer:"元大證券投資信託股份有限公司",category:"台股 ETF",benchmark:"臺灣 50 指數",distribution:"依官方公告",official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/0050"}
    },
    "TW:006208": {
      id:"TW:006208", asset_class:"etf", market:"TW", exchange:"TWSE",
      symbol:"006208", name:"富邦台50", sector:"fund",
      sub_industry:"台灣市值型 ETF", official_industry:"ETF", currency:"TWD",
      aliases:["富邦台灣50","富邦台灣釆吉50"],
      etf:{issuer:"富邦證券投資信託股份有限公司",category:"台股 ETF",benchmark:"臺灣 50 指數",distribution:"依官方公告",official_url:"https://www.twse.com.tw/zh/ETFortune/etfInfo/006208"}
    }
  };

  const $ = (selector, root=document) => root.querySelector(selector);
  const $$ = (selector, root=document) => [...root.querySelectorAll(selector)];
  const normalize = value => String(value || "").normalize("NFKC").toLowerCase().replace(/[\s._\-\/]+/g, "");
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[ch]));
  const finite = value => value === null || value === undefined || value === "" ? null :
    Number.isFinite(Number(value)) ? Number(value) : null;

  function taipeiClockParts(date=new Date()) {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone:"Asia/Taipei",
      weekday:"short",
      hour:"2-digit",
      minute:"2-digit",
      second:"2-digit",
      hourCycle:"h23"
    }).formatToParts(date);
    return Object.fromEntries(parts.map(part => [part.type, part.value]));
  }

  function isTaiwanQuoteWindow(date=new Date()) {
    const parts=taipeiClockParts(date);
    if (["Sat","Sun"].includes(parts.weekday)) return false;
    const minutes=Number(parts.hour)*60+Number(parts.minute);
    return minutes>=8*60+30 && minutes<=13*60+35;
  }

  function taiwanQuoteRefreshDelay(date=new Date()) {
    return isTaiwanQuoteWindow(date) ? 5_000 : 60_000;
  }

  function scheduleAdaptiveRefresh(task, delayProvider, initialDelay=0) {
    let stopped=false;
    let timer=null;
    const run=async()=>{
      if(stopped)return;
      try{await task()}catch(error){console.warn("Adaptive refresh failed:",error)}
      if(stopped)return;
      const delay=Math.max(1_000,Number(typeof delayProvider==="function"?delayProvider():delayProvider)||60_000);
      timer=setTimeout(run,delay);
    };
    timer=setTimeout(run,Math.max(0,initialDelay));
    return ()=>{stopped=true;if(timer)clearTimeout(timer)};
  }

  function startCryptoTickerStream({
    symbols=["BTC","ETH","BNB","XRP","SOL","ADA"],
    onUpdate=()=>{},
    onStatus=()=>{}
  }={}) {
    const names={BTC:"Bitcoin",ETH:"Ethereum",BNB:"BNB",XRP:"XRP",SOL:"Solana",ADA:"Cardano"};
    const normalized=[...new Set(symbols.map(symbol=>String(symbol||"").toUpperCase()
      .replace(/[-_]?USDT$/,"").replace(/[-_]?USD$/,"")).filter(Boolean))];
    const streams=normalized.map(symbol=>`${symbol.toLowerCase()}usdt@miniTicker`).join("/");
    let socket=null;
    let stopped=false;
    let reconnectAttempt=0;
    let reconnectTimer=null;
    let fallbackTimer=null;
    let connectTimer=null;
    const rows=new Map();

    const emit=()=>onUpdate([...rows.values()].sort((a,b)=>normalized.indexOf(a.symbol)-normalized.indexOf(b.symbol)));

    const applyTicker=data=>{
      const pair=String(data?.s||"").toUpperCase();
      if(!pair.endsWith("USDT"))return;
      const symbol=pair.slice(0,-4);
      if(!normalized.includes(symbol))return;
      const price=finite(data.c);
      const open=finite(data.o);
      const high=finite(data.h);
      const low=finite(data.l);
      const baseVolume=finite(data.v);
      const quoteVolume=finite(data.q);
      const pct=price!==null&&open?((price-open)/open*100):null;
      const previous=rows.get(symbol)||{};
      rows.set(symbol,{
        ...previous,
        symbol,
        name:names[symbol]||symbol,
        current_price:price,
        price_change_percentage_24h:pct,
        high_24h:high,
        low_24h:low,
        total_volume:quoteVolume,
        base_volume:baseVolume,
        updated_at:Number(data.E||Date.now()),
        source:"Binance WebSocket"
      });
      emit();
    };

    const fallbackFetch=async()=>{
      if(stopped)return;
      try{
        const ids={BTC:"bitcoin",ETH:"ethereum",BNB:"binancecoin",XRP:"ripple",SOL:"solana",ADA:"cardano"};
        const query=normalized.map(symbol=>ids[symbol]).filter(Boolean).join(",");
        const response=await fetch(`https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&ids=${encodeURIComponent(query)}&sparkline=false&price_change_percentage=24h`,{cache:"no-store"});
        if(!response.ok)throw new Error(`CoinGecko ${response.status}`);
        for(const row of await response.json()){
          const symbol=String(row.symbol||"").toUpperCase();
          if(!normalized.includes(symbol))continue;
          rows.set(symbol,{
            symbol,
            name:row.name||names[symbol]||symbol,
            current_price:finite(row.current_price),
            price_change_percentage_24h:finite(row.price_change_percentage_24h),
            high_24h:finite(row.high_24h),
            low_24h:finite(row.low_24h),
            total_volume:finite(row.total_volume),
            market_cap:finite(row.market_cap),
            updated_at:Date.now(),
            source:"CoinGecko fallback"
          });
        }
        emit();
        onStatus("fallback");
      }catch(error){
        console.warn("Crypto fallback failed:",error);
        onStatus("offline");
      }
    };

    const scheduleFallback=()=>{
      clearInterval(fallbackTimer);
      fallbackTimer=setInterval(()=>{
        if(!socket||socket.readyState!==WebSocket.OPEN)fallbackFetch();
      },30_000);
    };

    const connect=()=>{
      if(stopped||!streams)return;
      clearTimeout(reconnectTimer);
      try{
        socket=new WebSocket(`wss://data-stream.binance.vision/stream?streams=${streams}`);
      }catch(error){
        socket=null;
        fallbackFetch();
        reconnectTimer=setTimeout(connect,Math.min(30_000,2_000*2**reconnectAttempt++));
        return;
      }
      onStatus("connecting");
      clearTimeout(connectTimer);
      connectTimer=setTimeout(()=>{
        if(socket && socket.readyState!==WebSocket.OPEN){
          onStatus("fallback");
          fallbackFetch();
          try{socket.close()}catch{}
        }
      },7000);
      socket.addEventListener("open",()=>{
        clearTimeout(connectTimer);
        reconnectAttempt=0;
        onStatus("live");
      });
      socket.addEventListener("message",event=>{
        try{
          const message=JSON.parse(event.data);
          applyTicker(message?.data||message);
        }catch(error){
          console.warn("Crypto stream payload error:",error);
        }
      });
      socket.addEventListener("close",()=>{
        clearTimeout(connectTimer);
        if(stopped)return;
        onStatus("reconnecting");
        fallbackFetch();
        reconnectTimer=setTimeout(connect,Math.min(30_000,2_000*2**reconnectAttempt++));
      });
      socket.addEventListener("error",()=>{
        try{socket.close()}catch{}
      });
    };

    fallbackFetch();
    connect();
    scheduleFallback();

    return ()=>{
      stopped=true;
      clearTimeout(reconnectTimer);
      clearTimeout(connectTimer);
      clearInterval(fallbackTimer);
      try{socket?.close()}catch{}
    };
  }

  function cacheBust(url) {
    return `${url}${url.includes("?") ? "&" : "?"}t=${Date.now()}`;
  }

  async function fetchJson(url, timeout=10000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    try {
      const response = await fetch(cacheBust(url), {cache:"no-store", signal:controller.signal, headers:{Accept:"application/json"}});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } finally {
      clearTimeout(timer);
    }
  }

  function quoteNumber(value) {
    const first = String(value ?? "").split("_", 1)[0].replace(/,/g, "").trim();
    if (!first || ["-","--","---"].includes(first)) return null;
    const number = Number(first);
    return Number.isFinite(number) ? number : null;
  }

  function quoteLevelList(value) {
    return String(value ?? "").split("_")
      .map(item => quoteNumber(item))
      .filter(item => item !== null);
  }

  function quotePrice(row) {
    for (const key of ["z","b","a","y"]) {
      const value = quoteNumber(row?.[key]);
      if (value !== null) return value;
    }
    return null;
  }

  async function fetchTaiwanLiveQuotes(entries, timeout=9000) {
    const securities = (entries || []).map(entry => {
      const symbol = String(entry?.symbol || "").trim().toUpperCase();
      if (!/^(?:[1-9]\d{3}|00\d{2,4}[A-Z]?)$/.test(symbol)) return null;
      const exchangeText = String(entry?.exchange || "").toUpperCase();
      const isTpex = exchangeText.includes("TPEX") || exchangeText.includes("OTC") || entry?.market_board === "tpex";
      return {symbol, exchange:isTpex ? "TPEx" : "TWSE", channel:`${isTpex ? "otc" : "tse"}_${symbol}.tw`};
    }).filter(Boolean);
    if (!securities.length) return [];

    const byChannel = new Map(securities.map(row => [row.channel, row]));
    const output = [];
    for (let offset=0; offset<securities.length; offset+=50) {
      const batch = securities.slice(offset, offset+50);
      const channels = batch.map(row => row.channel).join("|");
      const url = `https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=${encodeURIComponent(channels)}&json=1&delay=0&_=${Date.now()}`;
      try {
        const payload = await fetchJson(url, timeout);
        for (const row of payload?.msgArray || []) {
          const symbol = String(row.c || "").trim().toUpperCase();
          if (!symbol) continue;
          const exchange = String(row.ex || "").toLowerCase() === "otc" ? "TPEx" : "TWSE";
          const previous = quoteNumber(row.y);
          const price = quotePrice(row);
          const change = price !== null && previous !== null ? price - previous : null;
          const askPrices=quoteLevelList(row.a);
          const bidPrices=quoteLevelList(row.b);
          const askVolumes=quoteLevelList(row.f);
          const bidVolumes=quoteLevelList(row.g);
          output.push({
            symbol, exchange, name:String(row.n || symbol).trim(),
            full_name:String(row.nf || row.n || symbol).trim(),
            price, previous_close:previous, change,
            change_percent:change !== null && previous ? change / previous * 100 : null,
            open:quoteNumber(row.o), high:quoteNumber(row.h), low:quoteNumber(row.l),
            upper_limit:quoteNumber(row.u), lower_limit:quoteNumber(row.w),
            volume:quoteNumber(row.v), last_trade_volume:quoteNumber(row.tv ?? row.s),
            bid_prices:bidPrices, bid_volumes:bidVolumes,
            ask_prices:askPrices, ask_volumes:askVolumes,
            quote_date:String(row.d || ""), quote_time:String(row.t || row.ot || ""),
            status:"mis-browser", market_at:quoteNumber(row.tlong), source:"TWSE MIS"
          });
        }
      } catch (error) {
        console.warn("TWSE MIS browser refresh failed:", error);
      }
    }
    return output;
  }

  async function fetchTaiwanIndicesLive(timeout=9000) {
    const channels = "tse_t00.tw|otc_o00.tw";
    const url = `https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch=${encodeURIComponent(channels)}&json=1&delay=0&_=${Date.now()}`;
    try {
      const payload = await fetchJson(url, timeout);
      return (payload?.msgArray || []).map(row => {
        const isOtc = String(row.ex || "").toLowerCase() === "otc" || String(row.c || "").toLowerCase() === "o00";
        const symbol = isOtc ? "^TWOII" : "^TWII";
        const previous = quoteNumber(row.y);
        const price = quotePrice(row);
        const change = price !== null && previous !== null ? price - previous : null;
        return {
          symbol, name:isOtc ? "台灣櫃買指數" : "台灣加權指數",
          market:"TW", currency:"", price, previous_close:previous, change,
          change_percent:change !== null && previous ? change / previous * 100 : null,
          open:quoteNumber(row.o), high:quoteNumber(row.h), low:quoteNumber(row.l),
          volume:quoteNumber(row.v), market_at:quoteNumber(row.tlong),
          quote_date:String(row.d || ""), quote_time:String(row.t || row.ot || ""),
          market_state:"REGULAR", source:"TWSE MIS"
        };
      }).filter(row => row.price !== null);
    } catch (error) {
      console.warn("TWSE MIS index refresh failed:", error);
      return [];
    }
  }

  async function fetchYahooChart(symbol, timeout=9000) {
    const encoded = encodeURIComponent(String(symbol || ""));
    const endpoints = [
      `https://query1.finance.yahoo.com/v8/finance/chart/${encoded}?range=1d&interval=1m&includePrePost=false`,
      `https://query2.finance.yahoo.com/v8/finance/chart/${encoded}?range=1d&interval=1m&includePrePost=false`
    ];
    for (const url of endpoints) {
      try {
        const payload = await fetchJson(url, timeout);
        const result = payload?.chart?.result?.[0];
        if (!result) continue;
        const meta = result.meta || {};
        const closes = result?.indicators?.quote?.[0]?.close || [];
        const points = closes.filter(value => Number.isFinite(Number(value))).map(Number);
        const price = finite(meta.regularMarketPrice) ?? (points.length ? points[points.length-1] : null);
        const previous = finite(meta.chartPreviousClose ?? meta.previousClose);
        const change = price !== null && previous !== null ? price - previous : null;
        return {
          symbol:String(symbol), name:meta.shortName || meta.longName || String(symbol),
          market:meta.exchangeName || "", currency:meta.currency || "",
          price, previous_close:previous, change,
          change_percent:change !== null && previous ? change / previous * 100 : null,
          open:finite(meta.regularMarketOpen), high:finite(meta.regularMarketDayHigh),
          low:finite(meta.regularMarketDayLow), volume:finite(meta.regularMarketVolume),
          market_at:finite(meta.regularMarketTime), market_state:meta.marketState || "",
          source:"Yahoo chart 1m"
        };
      } catch (error) {
        console.warn("Yahoo chart browser refresh failed:", symbol, error);
      }
    }
    return null;
  }

  function yahooTaiwanSymbol(asset) {
    const symbol=String(asset?.symbol||asset||"").toUpperCase();
    const exchange=String(asset?.exchange||"").toUpperCase();
    if(!symbol)return"";
    return `${symbol}.${exchange.includes("TPEX")||exchange.includes("OTC")?"TWO":"TW"}`;
  }

  async function fetchTaiwanSeries(asset,{range="1d",interval="1m",timeout=9000}={}) {
    const yahooSymbol=yahooTaiwanSymbol(asset);
    if(!yahooSymbol)return null;
    const encoded=encodeURIComponent(yahooSymbol);
    const endpoints=[
      `https://query1.finance.yahoo.com/v8/finance/chart/${encoded}?range=${encodeURIComponent(range)}&interval=${encodeURIComponent(interval)}&includePrePost=false&events=div%2Csplits`,
      `https://query2.finance.yahoo.com/v8/finance/chart/${encoded}?range=${encodeURIComponent(range)}&interval=${encodeURIComponent(interval)}&includePrePost=false&events=div%2Csplits`
    ];
    for(const url of endpoints){
      try{
        const payload=await fetchJson(url,timeout);
        const result=payload?.chart?.result?.[0];
        if(!result)continue;
        const quote=result?.indicators?.quote?.[0]||{};
        const timestamps=result.timestamp||[];
        const rows=timestamps.map((timestamp,index)=>({
          timestamp:Number(timestamp)*1000,
          open:finite(quote.open?.[index]),
          high:finite(quote.high?.[index]),
          low:finite(quote.low?.[index]),
          close:finite(quote.close?.[index]),
          volume:finite(quote.volume?.[index])
        })).filter(row=>row.close!==null);
        return {
          symbol:yahooSymbol,
          meta:result.meta||{},
          rows,
          source:"Yahoo chart",
          fetched_at:new Date().toISOString()
        };
      }catch(error){
        console.warn("Taiwan series fetch failed:",yahooSymbol,error);
      }
    }
    return null;
  }

  function seriesReturn(rows,days){
    const usable=(rows||[]).filter(row=>finite(row.close)!==null);
    if(usable.length<2)return null;
    const latest=usable[usable.length-1];
    const target=latest.timestamp-days*86400000;
    let previous=usable[0];
    for(const row of usable){
      if(row.timestamp<=target)previous=row;
      else break;
    }
    return previous.close ? (latest.close-previous.close)/previous.close*100 : null;
  }

  function buildPriceDistribution(rows,{buckets=12}={}) {
    const usable=(rows||[]).filter(row=>finite(row.close)!==null&&finite(row.volume)!==null&&row.volume>0);
    if(!usable.length)return[];
    const prices=usable.map(row=>row.close);
    const min=Math.min(...prices),max=Math.max(...prices);
    const step=max>min?(max-min)/Math.max(1,buckets-1):Math.max(min*.001,0.01);
    const map=new Map();
    for(const row of usable){
      const index=max>min?Math.min(buckets-1,Math.max(0,Math.round((row.close-min)/step))):0;
      const key=min+index*step;
      const current=map.get(index)||{price:key,volume:0,count:0};
      current.volume+=row.volume||0;
      current.count+=1;
      map.set(index,current);
    }
    return [...map.values()].sort((a,b)=>b.price-a.price);
  }

  function mergeQuoteItems(baseItems=[], updates=[]) {
    const map = new Map((baseItems || []).map(item => [
      `${String(item.exchange || item.market || "").toUpperCase()}:${String(item.symbol || "").toUpperCase()}`, {...item}
    ]));
    for (const update of updates || []) {
      const symbol = String(update?.symbol || "").toUpperCase();
      if (!symbol) continue;
      const exchange = String(update.exchange || update.market || "").toUpperCase();
      let key = `${exchange}:${symbol}`;
      if (!map.has(key)) {
        const existingKey = [...map.keys()].find(candidate => candidate.endsWith(`:${symbol}`));
        if (existingKey) key = existingKey;
      }
      map.set(key, {...(map.get(key) || {}), ...update});
    }
    return [...map.values()];
  }

  function scorePayload(payload) {
    const listScore = ["assets","items","events","announcements","daily","financials"].reduce((sum,key) =>
      sum + (Array.isArray(payload?.[key]) ? payload[key].length : 0), 0);
    const summaryScore = Number(payload?.summary?.total_stocks || 0);
    return listScore + summaryScore;
  }

  function payloadTime(payload) {
    return Date.parse(payload?.metadata?.updated_at || payload?.updated_at || payload?.published_at || 0) || 0;
  }

  function isUsablePayload(payload) {
    return Boolean(payload && typeof payload === "object" && (
      scorePayload(payload) > 0 ||
      payload?.metadata?.updated_at ||
      payload?.summary?.total_stocks > 0
    ));
  }

  function dataBranchFor(path) {
    const clean = String(path || "").replace(/^\.?\//,"").replace(/^data\//,"");
    return DATA_BRANCH_BY_FILE[clean] || null;
  }

  function dataChannelUrl(path) {
    const clean = String(path || "").replace(/^\.?\//,"").replace(/^data\//,"");
    const branch = dataBranchFor(clean);
    return branch ? `https://raw.githubusercontent.com/${OWNER}/${REPO}/${branch}/${clean}` : null;
  }

  async function loadData(path, fallback={}) {
    const clean = String(path || "").replace(/^\.?\//,"").replace(/^data\//,"");
    const local = String(path || "").startsWith("data/") ? String(path) : `data/${clean}`;
    const dedicatedUrl = dataChannelUrl(clean);
    const annotate = (payload, source, branch) => ({...payload,__source:source,__branch:branch});

    // The dedicated branch is the source of truth, but a blocked raw GitHub
    // request must not leave the whole page blank.  Give it a short head start,
    // then fall back to the bundled seed immediately.
    if (dedicatedUrl) {
      try {
        const payload = await fetchJson(dedicatedUrl, 6000);
        if (isUsablePayload(payload)) return annotate(payload,"channel",dataBranchFor(clean));
      } catch (error) {
        console.warn(`Dedicated data channel unavailable: ${clean}`, error);
      }
    }

    try {
      const payload = await fetchJson(local, 2500);
      if (isUsablePayload(payload)) return annotate(payload,"local","main-pages");
    } catch (error) {
      console.warn(`Bundled data unavailable: ${clean}`, error);
    }

    // Migration fallbacks are attempted concurrently and capped at six seconds.
    const fallbacks = [
      ["legacy", `${LEGACY_LIVE_BASE}${clean}`, "live-data"],
      ["main", `${MAIN_BASE}data/${clean}`, "main"]
    ];
    const results = await Promise.allSettled(fallbacks.map(([,url]) => fetchJson(url,6000)));
    const available = results.flatMap((result,index) => {
      if (result.status !== "fulfilled" || !isUsablePayload(result.value)) return [];
      const [source,,branch] = fallbacks[index];
      return [annotate(result.value,source,branch)];
    });
    if (available.length) return available.sort((a,b) => payloadTime(b)-payloadTime(a)||scorePayload(b)-scorePayload(a))[0];
    return {...fallback, __source:"fallback", __branch:null};
  }

  async function loadChannelManifest(channel) {
    const definition = typeof channel === "string" ? DATA_CHANNELS[channel] : channel;
    if (!definition?.branch) return null;
    const url = `https://raw.githubusercontent.com/${OWNER}/${REPO}/${definition.branch}/channel.json`;
    try {
      return await fetchJson(url, 10000);
    } catch {
      return null;
    }
  }

  function canonicalAsset(raw={}) {
    const symbol = String(raw.symbol || "").trim().toUpperCase();
    const market = String(raw.market || (symbol.match(/^\d/) ? "TW" : "US")).toUpperCase();
    const id = String(raw.id || `${market}:${symbol}`).toUpperCase();
    const override = OFFICIAL_OVERRIDES[id] || {};
    const merged = {
      aliases:[], themes:[], metrics:{}, financials:[], listing_status:"active",
      ...raw, ...override, id:override.id || id, symbol:override.symbol || symbol, market:override.market || market
    };
    merged.aliases = [...new Set([...(raw.aliases || []), ...(override.aliases || [])].filter(Boolean))];
    if (raw.etf || override.etf) {
      merged.etf = {...(override.etf || {}), ...(raw.etf || {})};
    }
    merged.search_blob = normalize([
      merged.symbol, merged.name, merged.market, merged.exchange, merged.sector,
      merged.sub_industry, merged.official_industry, ...merged.aliases
    ].join(" "));
    return merged;
  }

  function mergeAssets(primary=[], seed=[]) {
    const map = new Map();
    [...seed, ...primary].forEach(raw => {
      const asset = canonicalAsset(raw);
      if (!asset.id || !asset.symbol) return;
      map.set(asset.id, canonicalAsset({...map.get(asset.id), ...asset}));
    });
    Object.values(OFFICIAL_OVERRIDES).forEach(raw => map.set(raw.id, canonicalAsset({...map.get(raw.id), ...raw})));
    return [...map.values()];
  }

  function exactCodeLike(query) {
    return /^[0-9]{4,6}[A-Z]?$/i.test(String(query || "").trim());
  }

  function searchAssets(assets, query, options={}) {
    const raw = String(query || "").trim();
    const q = normalize(raw);
    if (!q) return [];
    const market = options.market || "all";
    const assetClass = options.asset_class || "all";
    const pool = assets.filter(asset => market === "all" || asset.market === market)
      .filter(asset => assetClass === "all" || asset.asset_class === assetClass ||
        (assetClass === "stock" && asset.asset_class === "etf"));

    if (exactCodeLike(raw)) {
      return pool.filter(asset => normalize(asset.symbol) === q);
    }

    return pool.map(asset => {
      const symbol = normalize(asset.symbol);
      const name = normalize(asset.name);
      let score = 0;
      if (symbol === q) score += 1000;
      else if (symbol.startsWith(q)) score += 500;
      if (name === q) score += 900;
      else if (name.startsWith(q)) score += 450;
      else if (name.includes(q)) score += 220;
      if (asset.search_blob.includes(q)) score += 120;
      return {asset, score};
    }).filter(row => row.score > 0)
      .sort((a,b) => b.score-a.score || a.asset.symbol.localeCompare(b.asset.symbol))
      .slice(0,12).map(row => row.asset);
  }

  function resolveAsset(assets, value, options={}) {
    const raw = String(value || "").trim();
    const q = normalize(raw);
    const results = searchAssets(assets, raw, options);
    const exact = results.find(asset => normalize(asset.symbol) === q || normalize(asset.name) === q ||
      (asset.aliases || []).some(alias => normalize(alias) === q));
    return exact || (exactCodeLike(raw) ? null : results[0]) || null;
  }

  function loadPortfolio() {
    let raw = localStorage.getItem(PORTFOLIO_KEY);
    if (!raw) {
      for (const key of LEGACY_PORTFOLIO_KEYS) {
        raw = localStorage.getItem(key);
        if (raw) break;
      }
    }
    // Older experimental builds used several unversioned portfolio keys. Scan
    // only keys that clearly belong to this project so an upgrade does not make
    // a user's holdings appear to vanish.
    if (!raw) {
      for (let index=0; index<localStorage.length; index++) {
        const key=localStorage.key(index) || "";
        if (!/market.*portfolio|portfolio.*market/i.test(key)) continue;
        const candidate=localStorage.getItem(key);
        try {
          const parsed=JSON.parse(candidate || "[]");
          if (Array.isArray(parsed) && parsed.length) {
            raw=candidate;
            break;
          }
        } catch {}
      }
    }
    let rows = [];
    try { rows = JSON.parse(raw || "[]"); } catch {}
    return Array.isArray(rows) ? rows : [];
  }

  function migratePortfolio(entries, assets) {
    const migrated = entries.map(entry => {
      const symbol = String(entry.symbol || String(entry.asset_id || "").split(":").pop() || "").toUpperCase();
      const market = entry.market || (String(entry.asset_id || "").startsWith("TW:") || /^\d/.test(symbol) ? "TW" : "US");
      const resolved = resolveAsset(assets, symbol, {market, asset_class:"all"}) ||
        canonicalAsset({...entry, symbol, market});
      return {
        ...entry, ...resolved,
        id: entry.id || (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`),
        asset_id: resolved.id || `${market}:${symbol}`,
        symbol: resolved.symbol || symbol,
        name: resolved.name || entry.name || symbol,
        market: resolved.market || market,
        asset_class: resolved.asset_class || entry.asset_class || "stock"
      };
    });
    savePortfolio(migrated);
    return migrated;
  }

  function savePortfolio(entries) {
    localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(entries));
    window.dispatchEvent(new CustomEvent("market-portfolio-changed", {detail:entries}));
  }

  function quoteMap(payload) {
    return new Map((payload?.items || []).map(item => [
      `${String(item.exchange || "TWSE").toUpperCase()}:${String(item.symbol || "").toUpperCase()}`, item
    ]));
  }

  function findTwQuote(entry, payload) {
    const symbol = String(entry.symbol || "").toUpperCase();
    const items = payload?.items || [];
    return items.find(item => String(item.symbol).toUpperCase() === symbol) || null;
  }

  function loadQuoteCache() {
    try { return JSON.parse(localStorage.getItem(QUOTE_CACHE_KEY) || "{}"); }
    catch { return {}; }
  }

  function saveQuoteCache(cache) {
    try { localStorage.setItem(QUOTE_CACHE_KEY, JSON.stringify(cache)); } catch {}
  }

  function formatPrice(value, currency="TWD") {
    const number = finite(value);
    if (number === null) return "—";
    const digits = number >= 1000 ? 0 : number >= 100 ? 1 : number >= 10 ? 2 : number >= 1 ? 3 : 5;
    const prefix = currency === "USD" ? "$" : currency === "TWD" ? "NT$" : "";
    return `${prefix}${number.toLocaleString("zh-TW",{maximumFractionDigits:digits})}`;
  }

  function formatPercent(value) {
    const number = finite(value);
    return number === null ? "—" : `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
  }

  function formatMoney(value, signed=false) {
    const number = finite(value);
    if (number === null) return "—";
    return `${signed && number > 0 ? "+" : ""}NT$${Math.round(number).toLocaleString("zh-TW")}`;
  }

  function formatVolume(value) {
    const number = finite(value);
    if (number === null) return "—";
    if (number >= 100000000) return `${(number/100000000).toFixed(1)}億`;
    if (number >= 10000) return `${(number/10000).toFixed(1)}萬`;
    return Math.round(number).toLocaleString("zh-TW");
  }

  function direction(value) {
    const number = finite(value);
    return number === null || number === 0 ? "flat" : number > 0 ? "up" : "down";
  }

  function formatTime(value) {
    if (!value) return "尚無時間";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "尚無時間";
    return date.toLocaleString("zh-TW",{timeZone:"Asia/Taipei",month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false});
  }

  function safeNewsLink(item) {
    const value = item?.pdf_link || item?.article_link || item?.direct_link || item?.link || item?.url || "";
    try {
      const url = new URL(value, location.href);
      if (!["http:","https:"].includes(url.protocol)) return "#";
      // TWSE /rwd/ newsDetail is a JSON API. Convert legacy live-data
      // links to the readable article route before opening a new tab.
      if (/(^|\.)twse\.com\.tw$/i.test(url.hostname) && /\/rwd\/(?:zh|en)\/news\/newsDetail\//i.test(url.pathname)) {
        url.pathname = url.pathname.replace(/\/rwd\/(zh|en)\/news\/newsDetail\//i, "/$1/news/newsDetail/");
      }
      return url.href;
    } catch { return "#"; }
  }

  function newsIdentity(item) {
    if (item?.cluster_id) return String(item.cluster_id);
    const raw = String(item?.title || "").normalize("NFKC");
    const date = String(item?.published_at || "").slice(0,10);
    if (/(?:排行|排名).*?(?:前|Top)\s*\d+\s*名/i.test(raw)) {
      const market = raw.includes("上市") ? "上市" : raw.includes("上櫃") ? "上櫃" : "市場";
      const family = /外資|投信|自營商|融資|融券|借券/.test(raw) ? "法人籌碼" : "市場排行";
      return `template:${date}:${market}:${family}`;
    }
    const title = raw.toLowerCase()
      .replace(/\bhttps?:\/\/\S+/g, "")
      .replace(/[\s\p{P}\p{S}]+/gu, "");
    return title || String(item?.id || item?.link || "");
  }

  function diversifyNews(items, limit=Infinity) {
    const identityGroups = new Map();
    (items || []).forEach(item => {
      const key = newsIdentity(item);
      if (!key) return;
      if (!identityGroups.has(key)) identityGroups.set(key, []);
      identityGroups.get(key).push(item);
    });
    const unique = [...identityGroups.values()].map(rows => {
      rows.sort((a,b) => Date.parse(b.published_at || 0)-Date.parse(a.published_at || 0));
      const primary = {...rows[0]};
      const existing = Number(primary.duplicate_count || primary.related_count || 0);
      primary.duplicate_count = existing + Math.max(0, rows.length - 1);
      primary.related_sources = [...new Set([
        ...(primary.related_sources || []),
        ...rows.map(row => row.source).filter(Boolean)
      ])];
      return primary;
    });
    const groups = new Map();
    unique
      .sort((a,b) => Date.parse(b.published_at || 0)-Date.parse(a.published_at || 0))
      .forEach(item => {
        const source = String(item.source || "其他來源");
        if (!groups.has(source)) groups.set(source, []);
        groups.get(source).push(item);
      });

    const output = [];
    let lastSource = "";
    while (output.length < limit) {
      const available = [...groups.entries()].filter(([,queue]) => queue.length);
      if (!available.length) break;
      let choices = available.filter(([source]) => source !== lastSource);
      if (!choices.length) choices = available;
      choices.sort((a,b) => Date.parse(b[1][0]?.published_at || 0)-Date.parse(a[1][0]?.published_at || 0));
      const [source, queue] = choices[0];
      output.push(queue.shift());
      lastSource = source;
    }
    return output;
  }

  const SECTOR_TERMS = {
    technology:["科技","AI","人工智慧","半導體","晶片","伺服器","軟體","雲端","電子","CoWoS","先進製程"],
    finance:["金融","金控","銀行","保險","證券","利率","房貸"],
    shipping:["航運","海運","貨櫃","散裝","運價","SCFI","航空","物流"],
    industrial:["機械","工具機","重電","自動化","製造"],
    materials:["鋼鐵","水泥","塑化","化工","原物料","紡織"],
    consumer:["消費","零售","百貨","電商","餐飲","食品"],
    healthcare:["生技","製藥","醫療","新藥","醫材"],
    energy:["能源","原油","天然氣","綠能","太陽能","風電","儲能"],
    fund:["ETF","基金","淨值","折溢價","配息","成分股","資產配置","台股","加權指數"]
  };

  function newsKeywords(asset) {
    const values = new Set([asset.symbol, asset.name, ...(asset.aliases || []), asset.sub_industry, asset.official_industry]);
    (SECTOR_TERMS[asset.sector] || []).forEach(v => values.add(v));
    if (asset.asset_class === "etf") {
      (SECTOR_TERMS.fund || []).forEach(v => values.add(v));
      [asset.etf?.benchmark, asset.etf?.category].filter(Boolean).forEach(v => values.add(v));
      (asset.etf?.holdings || []).slice(0,10).forEach(row => values.add(row.name || row.symbol));
    }
    return [...values].filter(Boolean).map(normalize).filter(v => v.length >= 2);
  }

  function newsScore(item, asset) {
    const text = normalize(`${item.title || ""} ${item.summary || ""} ${item.source || ""} ${(item.tags || []).join(" ")}`);
    let score = 0;
    const symbol = normalize(asset.symbol);
    newsKeywords(asset).forEach(keyword => {
      if (!text.includes(keyword)) return;
      score += keyword === symbol ? 120 : keyword === normalize(asset.name) ? 95 : 15;
    });
    if (asset.asset_class === "etf" && /ETF|基金|指數|成分股/i.test(`${item.title} ${item.summary}`)) score += 12;
    return score;
  }

  window.MR = {
    VERSION, OWNER, REPO, LEGACY_LIVE_BASE, MAIN_BASE, PORTFOLIO_KEY, OFFICIAL_OVERRIDES,
    $, $$, normalize, escapeHtml, finite, taipeiClockParts, isTaiwanQuoteWindow,
    taiwanQuoteRefreshDelay, scheduleAdaptiveRefresh, startCryptoTickerStream,
    fetchJson, fetchTaiwanLiveQuotes, fetchTaiwanIndicesLive, fetchYahooChart,
    fetchTaiwanSeries, yahooTaiwanSymbol, seriesReturn, buildPriceDistribution,
    mergeQuoteItems, loadData, loadChannelManifest, dataBranchFor, dataChannelUrl, DATA_CHANNELS,
    canonicalAsset, mergeAssets,
    searchAssets, resolveAsset, loadPortfolio, migratePortfolio, savePortfolio,
    findTwQuote, loadQuoteCache, saveQuoteCache, formatPrice, formatPercent, formatMoney,
    formatVolume, direction, formatTime, safeNewsLink, diversifyNews, newsKeywords, newsScore
  };
})();
