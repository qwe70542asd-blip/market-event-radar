(() => {
  "use strict";

  const root = document.querySelector("#marketTicker");
  if (!root) return;

  const seed = window.__MARKET_SNAPSHOT_SEED__ || {metadata:{},items:[]};

  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
  }[char]));

  function number(value, item) {
    if (value === null || value === undefined || !Number.isFinite(Number(value))) return "—";
    const num = Number(value);
    if (item.kind === "crypto" && num >= 1000) return num.toLocaleString("en-US",{maximumFractionDigits:0});
    if (item.kind === "yield") return num.toFixed(2);
    if (item.kind === "fx") return num.toFixed(num >= 100 ? 2 : 4);
    if (num >= 10000) return num.toLocaleString("en-US",{maximumFractionDigits:0});
    return num.toLocaleString("en-US",{minimumFractionDigits:num < 100 ? 2 : 0,maximumFractionDigits:2});
  }

  function dateText(value) {
    if (!value) return "";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value).slice(0,10);
    return parsed.toLocaleString("zh-TW",{
      month:"numeric",day:"numeric",hour:"2-digit",minute:"2-digit",hour12:false
    });
  }

  function card(item) {
    const pct = Number(item.change_percent);
    const hasPct = Number.isFinite(pct);
    const direction = hasPct ? (pct > 0 ? "up" : pct < 0 ? "down" : "flat") : "flat";
    const sign = pct > 0 ? "+" : "";
    const href = item.link || item.source_url || "#";
    const stale = ["stale","fallback"].includes(item.status);
    return `
      <a class="market-ticker-item ${direction} ${stale ? "stale" : ""}" href="${escapeHtml(href)}" target="_blank" rel="noreferrer noopener"
         title="${escapeHtml(`${item.name}｜${item.source || "等待來源"}｜${item.delay || ""}｜${dateText(item.as_of)}`)}">
        <span class="market-ticker-region">${escapeHtml(item.region || "市場")}</span>
        <div>
          <strong>${escapeHtml(item.name)}</strong>
          <small>${escapeHtml(item.delay || "延遲資料")}</small>
        </div>
        <b>${number(item.value,item)}${item.kind === "yield" ? "%" : ""}</b>
        <em>${hasPct ? `${sign}${pct.toFixed(2)}%` : "待更新"}</em>
      </a>`;
  }

  function render(payload) {
    const metadata = payload?.metadata || {};
    const valid = (payload?.items || []).filter(item =>
      item && item.value !== null && item.value !== undefined && item.status !== "pending"
    );

    const status = document.querySelector("#marketTickerStatus");
    if (status) {
      const updated = dateText(metadata.updated_at);
      status.textContent = valid.length
        ? `${valid.length} 項｜${updated || "最近更新"}｜延遲／收盤資料`
        : "市場資料等待第一次排程";
      status.classList.toggle("warning", valid.length < 6);
    }

    if (!valid.length) {
      root.innerHTML = `
        <div class="market-ticker-empty">
          <strong>市場指數同步中</strong>
          <span>執行 GitHub Actions 的 Update v10.4.5 multi-source market ticker 後顯示。</span>
        </div>`;
      return;
    }

    const markup = valid.map(card).join("");
    root.innerHTML = `
      <div class="market-ticker-track">
        <div class="market-ticker-set">${markup}</div>
        <div class="market-ticker-set" aria-hidden="true">${markup}</div>
      </div>`;
  }

  async function load() {
    let payload = seed;
    try {
      const response = await fetch(`data/market-snapshot.json?t=${Date.now()}`,{cache:"no-store"});
      if (response.ok) {
        const live = await response.json();
        if ((live.items || []).some(item => item?.value !== null && item?.value !== undefined)) payload = live;
      }
    } catch {}
    render(payload);
  }

  load();
})();