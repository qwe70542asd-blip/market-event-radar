(() => {
  "use strict";

  const root = document.querySelector("#marketTicker");
  if (!root) return;

  const seed = window.__MARKET_SNAPSHOT_SEED__ || { metadata:{}, items:[], taiwan_etfs:[], us_etfs:[] };
  const REFRESH_MS = 30_000;
  let refreshTimer = null;
  let lastFingerprint = "";
  let mobilePanelIndex = 0;
  const INDEX_GROUPS = [
    { id:"tw", label:"台股指數", note:"集中市場／櫃買", ids:["TAIEX","TPEX"] },
    { id:"us", label:"美股四大指數", note:"S&P／NASDAQ／道瓊／費半", ids:["SP500","NASDAQ","DJIA","SOX"] },
    { id:"asia", label:"日韓指數", note:"日本／韓國", ids:["NIKKEI","KOSPI"] }
  ];

  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[char]));

  function formatNumber(value, item = {}) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
    const num = Number(value);
    if (item.currency === "TWD" && item.kind === "etf") return num.toFixed(num < 100 ? 2 : 1);
    if (num >= 10000) return num.toLocaleString("en-US", { maximumFractionDigits:0 });
    return num.toLocaleString("en-US", { minimumFractionDigits:num < 100 ? 2 : 0, maximumFractionDigits:2 });
  }

  function formatTime(value) {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value).slice(0,10);
    return parsed.toLocaleString("zh-TW", { timeZone:"Asia/Taipei", month:"numeric", day:"numeric", hour:"2-digit", minute:"2-digit", hour12:false });
  }

  function direction(item) {
    if (item?.change_percent === null || item?.change_percent === undefined || item?.change_percent === "") return "pending";
    const pct = Number(item?.change_percent);
    if (!Number.isFinite(pct) || pct === 0) return "flat";
    return pct > 0 ? "up" : "down";
  }

  function pctText(item) {
    if (item?.change_percent === null || item?.change_percent === undefined || item?.change_percent === "") return "待更新";
    const pct = Number(item?.change_percent);
    if (!Number.isFinite(pct)) return "待更新";
    return `${pct > 0 ? "+" : ""}${pct.toFixed(2)}%`;
  }

  function indexRow(item) {
    if (!item) return `<div class="market-index-row pending"><span>—</span><strong>等待更新</strong><b>—</b><em>—</em></div>`;
    const stale = ["stale","fallback"].includes(item.status) ? " stale" : "";
    return `<a class="market-index-row ${direction(item)}${stale}" href="${escapeHtml(item.link || item.source_url || '#')}" target="_blank" rel="noreferrer noopener"
      title="${escapeHtml(`${item.source || "等待來源"}｜${item.delay || ""}｜${formatTime(item.as_of)}`)}">
      <span>${escapeHtml(item.region || "市場")}</span>
      <strong>${escapeHtml(item.name || item.id)}</strong>
      <b>${formatNumber(item.value,item)}</b>
      <em>${pctText(item)}</em>
    </a>`;
  }

  function indexGroup(group, map) {
    return `<article class="market-index-group market-index-${group.id}">
      <header><div><strong>${group.label}</strong><small>${group.note}</small></div><span>${group.ids.length} 項</span></header>
      <div>${group.ids.map(id => indexRow(map.get(id))).join("")}</div>
    </article>`;
  }

  function etfRow(item, index) {
    const rank = Number(item.rank) || index + 1;
    const href = item.link || item.source_url || "#";
    return `<a class="market-etf-row ${direction(item)}" href="${escapeHtml(href)}" target="_blank" rel="noreferrer noopener"
      title="${escapeHtml(`${item.source || "行情來源"}｜${item.delay || ""}｜${formatTime(item.as_of)}`)}">
      <span class="market-etf-rank">${rank}</span>
      <strong class="market-etf-symbol">${escapeHtml(item.symbol || item.id)}</strong>
      <small class="market-etf-name">${escapeHtml(item.name || "ETF")}</small>
      <b>${formatNumber(item.value,item)}</b>
      <em>${pctText(item)}</em>
    </a>`;
  }

  function etfPanel(id, label, note, rows, countLabel) {
    const safeRows = Array.isArray(rows) ? rows.filter(row => row && row.symbol) : [];
    return `<article class="market-etf-panel">
      <header>
        <div><strong>${label}</strong><small>${note}</small></div>
        <span>${countLabel}</span>
      </header>
      <div class="market-etf-viewport" id="${id}" data-visible="4">
        <div class="market-etf-track">
          ${safeRows.length ? safeRows.map(etfRow).join("") : '<div class="market-etf-empty">ETF 行情等待第一次排程</div>'}
        </div>
      </div>
    </article>`;
  }

  function startVerticalRail(viewport) {
    const track = viewport?.querySelector(".market-etf-track");
    if (!track) return;
    const original = [...track.querySelectorAll(".market-etf-row")];
    const visible = Math.min(Number(viewport.dataset.visible || 5), original.length);
    if (original.length <= visible || !visible) return;

    original.slice(0, visible).forEach(row => track.appendChild(row.cloneNode(true)));
    let index = 0;
    let paused = false;
    let timer;

    const step = () => {
      if (paused) return;
      const first = track.querySelector(".market-etf-row");
      if (!first) return;
      const rowHeight = first.getBoundingClientRect().height;
      index += 1;
      track.style.transition = "transform .46s cubic-bezier(.22,.7,.2,1)";
      track.style.transform = `translateY(${-index * rowHeight}px)`;
      if (index >= original.length) {
        window.setTimeout(() => {
          track.style.transition = "none";
          index = 0;
          track.style.transform = "translateY(0)";
          void track.offsetHeight;
        }, 500);
      }
    };

    const play = () => { clearInterval(timer); timer = setInterval(step, 8000); };
    viewport.addEventListener("mouseenter", () => { paused = true; });
    viewport.addEventListener("mouseleave", () => { paused = false; });
    viewport.addEventListener("focusin", () => { paused = true; });
    viewport.addEventListener("focusout", () => { paused = false; });
    document.addEventListener("visibilitychange", () => document.hidden ? clearInterval(timer) : play());
    play();
  }

  function marketPanels() {
    return [...root.querySelectorAll(".market-index-group,.market-etf-panel")];
  }

  function updateMobileCounter() {
    const panels = marketPanels();
    const counter = document.querySelector("#marketPanelCounter");
    if (!panels.length) {
      if (counter) counter.textContent = "0/0";
      return;
    }
    mobilePanelIndex = Math.max(0, Math.min(mobilePanelIndex, panels.length - 1));
    if (counter) counter.textContent = `${mobilePanelIndex + 1}/${panels.length}`;
  }

  function scrollToMarketPanel(index) {
    const panels = marketPanels();
    if (!panels.length) return;
    mobilePanelIndex = (index + panels.length) % panels.length;
    const panel = panels[mobilePanelIndex];
    const target = panel.getBoundingClientRect().left - root.getBoundingClientRect().left + root.scrollLeft;
    root.scrollTo({ left:target, behavior:"smooth" });
    updateMobileCounter();
  }

  function bindMobileMarketControls() {
    const prev = document.querySelector("#marketPrev");
    const next = document.querySelector("#marketNext");
    if (prev && !prev.dataset.bound) {
      prev.dataset.bound = "true";
      prev.addEventListener("click", () => scrollToMarketPanel(mobilePanelIndex - 1));
    }
    if (next && !next.dataset.bound) {
      next.dataset.bound = "true";
      next.addEventListener("click", () => scrollToMarketPanel(mobilePanelIndex + 1));
    }
    if (!root.dataset.mobileScrollBound) {
      root.dataset.mobileScrollBound = "true";
      let scrollTimer;
      root.addEventListener("scroll", () => {
        clearTimeout(scrollTimer);
        scrollTimer = window.setTimeout(() => {
          const panels = marketPanels();
          if (!panels.length) return;
          const rootLeft = root.getBoundingClientRect().left;
          mobilePanelIndex = panels.reduce((best, panel, index) => {
            const distance = Math.abs(panel.getBoundingClientRect().left - rootLeft);
            return distance < best.distance ? { index, distance } : best;
          }, { index:0, distance:Number.POSITIVE_INFINITY }).index;
          updateMobileCounter();
        }, 90);
      }, { passive:true });
    }
    updateMobileCounter();
  }

  function updateStatus(payload) {
    const metadata = payload?.metadata || {};
    const items = Array.isArray(payload?.items) ? payload.items : [];
    const twEtfs = payload?.taiwan_etfs || [];
    const usEtfs = payload?.us_etfs || [];
    const status = document.querySelector("#marketTickerStatus");
    const healthy = [...items, ...twEtfs, ...usEtfs].filter(item => item?.value !== null && item?.value !== undefined).length;
    if (status) {
      status.textContent = healthy
        ? `${healthy} 項｜資料 ${formatTime(metadata.updated_at) || "等待更新"}（台灣）｜每 30 秒檢查`
        : "行情等待第一次排程";
      status.classList.toggle("warning", healthy < 8);
    }
  }

  function render(payload) {
    const items = Array.isArray(payload?.items) ? payload.items : [];
    const map = new Map(items.map(item => [item.id, item]));
    const twEtfs = payload?.taiwan_etfs || [];
    const usEtfs = payload?.us_etfs || [];
    updateStatus(payload);

    root.innerHTML = `
      <div class="market-index-groups">${INDEX_GROUPS.map(group => indexGroup(group,map)).join("")}</div>
      <div class="market-etf-groups">
        ${etfPanel("twEtfRail","台股主流 ETF","成交值排行前 15；一次顯示 4 檔向上輪播",twEtfs,"前 15")}
        ${etfPanel("usEtfRail","美股 ETF","大盤、科技、半導體與債券；一次顯示 4 檔",usEtfs,`${usEtfs.length || 10} 檔`)}
      </div>`;

    startVerticalRail(document.querySelector("#twEtfRail"));
    startVerticalRail(document.querySelector("#usEtfRail"));
    bindMobileMarketControls();
  }

  function mergeRows(seedRows = [], liveRows = []) {
    const merged = new Map((Array.isArray(seedRows) ? seedRows : []).map(item => [item.id || item.symbol, {...item}]));
    for (const live of (Array.isArray(liveRows) ? liveRows : [])) {
      const key = live?.id || live?.symbol;
      if (!key) continue;
      const base = merged.get(key) || {};
      const next = {...base, ...live};
      ["value","previous","change","change_percent"].forEach(field => {
        if (live[field] === null || live[field] === undefined || live[field] === "") next[field] = base[field] ?? null;
      });
      merged.set(key, next);
    }
    return [...merged.values()];
  }

  function mergePayload(base, live) {
    return {
      ...base,
      ...live,
      metadata: {...(base?.metadata || {}), ...(live?.metadata || {})},
      items: mergeRows(base?.items, live?.items),
      taiwan_etfs: mergeRows(base?.taiwan_etfs, live?.taiwan_etfs),
      us_etfs: mergeRows(base?.us_etfs, live?.us_etfs),
    };
  }

  async function load() {
    let payload = seed;
    try {
      const live = window.MarketDataSource?.loadJson
        ? await window.MarketDataSource.loadJson("data/market-snapshot.json", seed)
        : seed;
      payload = mergePayload(seed, live);
    } catch {}
    const fingerprint=JSON.stringify({
      updated:payload?.metadata?.updated_at||"",
      values:[...(payload?.items||[]),...(payload?.taiwan_etfs||[]),...(payload?.us_etfs||[])].map(row=>[row?.id||row?.symbol,row?.value,row?.change_percent])
    });
    if (fingerprint!==lastFingerprint) {
      lastFingerprint=fingerprint;
      render(payload);
    } else updateStatus(payload);
  }

  load();
  refreshTimer=setInterval(load,REFRESH_MS);
  window.addEventListener("online",load);
  document.addEventListener("visibilitychange",()=>{
    if (document.hidden) clearInterval(refreshTimer);
    else { load(); refreshTimer=setInterval(load,REFRESH_MS); }
  });
})();
