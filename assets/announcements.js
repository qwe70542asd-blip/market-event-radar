(() => {
  "use strict";
  const $=selector=>document.querySelector(selector);
  const escapeHtml=value=>String(value??"").replace(/[&<>\"]/g,char=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[char]));
  const state={items:[],index:0,timer:null,paused:false};

  function fmt(value) {
    if (!value) return "等待更新";
    const date=new Date(value);
    return Number.isNaN(date.getTime())?String(value):date.toLocaleString("zh-TW",{month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false});
  }

  function formatTradingDate(value) {
    if (!value) return "等待最近交易日";
    const date=new Date(`${value}T12:00:00+08:00`);
    if (Number.isNaN(date.getTime())) return value;
    return `${date.getMonth()+1}/${date.getDate()}（週${["日","一","二","三","四","五","六"][date.getDay()]}）`;
  }

  function isSafeUrl(value) {
    try {
      const url=new URL(String(value||""),location.href);
      if (!["http:","https:"].includes(url.protocol)) return false;
      if (/google\./i.test(url.hostname) || url.hostname==="news.google.com") return false;
      return true;
    } catch { return false; }
  }

  function articleLink(item) {
    const values=[item?.direct_link,item?.safe_link,item?.link,item?.source_url,item?.source_home];
    return values.find(isSafeUrl) || "";
  }

  function amount(value) {
    const number=Number(value);
    return Number.isFinite(number)?`${number>=0?"+":""}${number.toFixed(1)} 億`:"—";
  }

  function institutionalCard(label,value,dateText,href,note,external=false) {
    return `<a class="institutional-card" href="${escapeHtml(href||"#")}"${external?' target="_blank" rel="noreferrer noopener"':""}>
      <span>${escapeHtml(label)}</span><strong>${amount(value)}</strong><small>${escapeHtml(dateText)}${note?` · ${escapeHtml(note)}`:""}</small>
    </a>`;
  }

  function showTicker(index) {
    const link=$("#announcementTickerLink");
    if (!link) return;
    if (!state.items.length) {
      $("#announcementTickerRegion").textContent="—";
      $("#announcementTickerTitle").textContent="等待官方公告排程";
      $("#announcementTickerSource").textContent="尚無可直接開啟的公告";
      $("#announcementCounter").textContent="0/0";
      link.removeAttribute("href");
      return;
    }
    state.index=(index+state.items.length)%state.items.length;
    const item=state.items[state.index];
    $("#announcementTickerRegion").textContent=item.region||"GLOBAL";
    $("#announcementTickerTitle").textContent=item.title_zh||item.title_original||"官方公告";
    $("#announcementTickerSource").textContent=`${item.source||"官方來源"} · ${fmt(item.published_at)}`;
    $("#announcementCounter").textContent=`${state.index+1}/${state.items.length}`;
    link.href=articleLink(item);
    link.classList.remove("announcement-swap");
    void link.offsetWidth;
    link.classList.add("announcement-swap");
  }

  function restartTimer() {
    clearInterval(state.timer);
    if (state.paused) return;
    state.timer=setInterval(()=>showTicker(state.index+1),8000);
  }

  function render(payload) {
    const institutional=payload.institutional||{};
    const cards=$("#institutionalCards");
    if (cards) {
      const twse=institutional.twse||{},tpex=institutional.tpex||{};
      const twseDate=formatTradingDate(institutional.twse_date||institutional.date);
      const tpexDate=formatTradingDate(institutional.tpex_date||institutional.date);
      const lag=institutional.is_previous_trading_day?"最近交易日":"當日盤後";
      cards.innerHTML=[
        institutionalCard("上市外資",twse.foreign,twseDate,"institutional.html?market=twse&type=foreign",`${lag} · 查看圖表`),
        institutionalCard("上市投信",twse.investment_trust,twseDate,"institutional.html?market=twse&type=investment_trust","官方彙總 · 查看圖表"),
        institutionalCard("上市自營商",twse.dealer,twseDate,"institutional.html?market=twse&type=dealer","自行＋避險 · 查看圖表"),
        institutionalCard("上櫃三大法人",tpex.total,tpexDate,"institutional.html?market=tpex&type=total",`${lag} · 查看圖表`),
      ].join("");
    }
    state.items=(payload.items||[]).filter(item=>articleLink(item)).sort((a,b)=>new Date(b.published_at||0)-new Date(a.published_at||0)).slice(0,30);
    showTicker(0);
    restartTimer();
    const updated=$("#announcementUpdatedAt");
    if (updated) updated.textContent=payload.metadata?.updated_at?fmt(payload.metadata.updated_at):"等待第一次排程";
    const note=$(".announcement-note");
    if (note) note.textContent="法人卡片可進入日、週、月圖表；官方公告只保留可直接開啟的來源。";
  }

  async function load() {
    const seed=window.__MARKET_ANNOUNCEMENT_SEED__||{institutional:{},items:[]};
    let payload=seed;
    try {
      payload=window.MarketDataSource?.loadJson
        ? await window.MarketDataSource.loadJson("data/announcements.json",seed)
        : seed;
    } catch {}
    render(payload);
  }

  $("#announcementPrev")?.addEventListener("click",()=>{showTicker(state.index-1);restartTimer();});
  $("#announcementNext")?.addEventListener("click",()=>{showTicker(state.index+1);restartTimer();});
  const ticker=$(".announcement-ticker");
  ticker?.addEventListener("mouseenter",()=>{state.paused=true;restartTimer();});
  ticker?.addEventListener("mouseleave",()=>{state.paused=false;restartTimer();});
  load();
  setInterval(load,5*60_000);
})();
