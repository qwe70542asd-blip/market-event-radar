(() => {
  "use strict";
  const $ = selector => document.querySelector(selector);
  const $$ = selector => [...document.querySelectorAll(selector)];
  const FLOW_LABELS = {
    foreign:"上市外資", investment_trust:"上市投信", dealer:"上市自營商", total:"三大法人合計"
  };
  const FLOW_SHORT = {foreign:"外資",investment_trust:"投信",dealer:"自營商",total:"三大法人"};
  const state = { payload:null, flow:"foreign", range:"20" };

  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const finite = value => Number.isFinite(Number(value));
  const num = value => finite(value) ? Number(value) : 0;
  const money = value => finite(value) ? `${Number(value) >= 0 ? "+" : ""}${Number(value).toFixed(1)} 億` : "—";
  const gross = value => finite(value) ? `${Number(value).toFixed(1)} 億` : "—";
  const shares = value => finite(value) ? `${(Math.abs(Number(value))/1000).toLocaleString("zh-TW",{maximumFractionDigits:0})} 張` : "—";
  const fmtDate = value => {
    if (!value) return "—";
    const d = new Date(`${String(value).slice(0,10)}T12:00:00+08:00`);
    return Number.isNaN(d.getTime()) ? value : `${d.getMonth()+1}/${d.getDate()}`;
  };
  const fmtFullDate = value => {
    if (!value) return "—";
    const d = new Date(`${String(value).slice(0,10)}T12:00:00+08:00`);
    if (Number.isNaN(d.getTime())) return value;
    const day = ["日","一","二","三","四","五","六"][d.getDay()];
    return `${d.getFullYear()}/${d.getMonth()+1}/${d.getDate()}（週${day}）`;
  };

  async function load() {
    const seed = window.__INSTITUTIONAL_HISTORY_SEED__ || {metadata:{},daily:[],rankings:{}};
    let payload = seed;
    try {
      const live = window.MarketDataSource?.loadJson
        ? await window.MarketDataSource.loadJson("data/institutional-history.json", seed)
        : seed;
      if ((live.daily || []).length) payload = live;
    } catch {}
    state.payload = payload;
    const params = new URLSearchParams(location.search);
    const flow = params.get("type");
    if (FLOW_LABELS[flow]) state.flow = flow;
    bind();
    render();
  }

  function bind() {
    $$('[data-flow]').forEach(button => button.addEventListener('click', () => {
      state.flow = button.dataset.flow;
      const url = new URL(location.href);
      url.searchParams.set('type', state.flow);
      history.replaceState({}, '', url);
      render();
    }));
    $$('[data-range]').forEach(button => button.addEventListener('click', () => {
      state.range = button.dataset.range;
      render();
    }));
  }

  function flowData(row) {
    return row?.[state.flow] || {buy:null,sell:null,net:null};
  }

  function visibleRows() {
    const rows = [...(state.payload?.daily || [])].sort((a,b) => a.date.localeCompare(b.date));
    if (state.range === 'all') return rows;
    return rows.slice(-Number(state.range));
  }

  function streak(rows) {
    if (!rows.length) return {count:0,direction:"無資料"};
    const latestSign = Math.sign(num(flowData(rows.at(-1)).net));
    if (!latestSign) return {count:1,direction:"持平"};
    let count = 0;
    for (let i=rows.length-1;i>=0;i--) {
      if (Math.sign(num(flowData(rows[i]).net)) !== latestSign) break;
      count++;
    }
    return {count,direction:latestSign > 0 ? "連續買超" : "連續賣超"};
  }

  function summary(rows) {
    const all = [...(state.payload?.daily || [])].sort((a,b) => a.date.localeCompare(b.date));
    const latest = all.at(-1);
    const current = flowData(latest);
    const sumLast = count => all.slice(-count).reduce((sum,row) => sum + num(flowData(row).net), 0);
    const periodSum = rows.reduce((sum,row) => sum + num(flowData(row).net), 0);
    const s = streak(all);
    const ratio = num(current.sell) ? num(current.buy) / num(current.sell) : null;
    return {latest,current,sum5:sumLast(5),sum20:sumLast(20),periodSum,streak:s,ratio};
  }

  function render() {
    const rows = visibleRows();
    const info = summary(rows);
    const metadata = state.payload?.metadata || {};
    $('#institutionalTitle').textContent = `${FLOW_LABELS[state.flow]}資金流向`;
    $('#institutionalSubtitle').textContent = state.flow === 'dealer'
      ? '自營商為「自行買賣＋避險」合計；頁面也保留拆分資訊。'
      : '證交所官方 BFI82U 市場總額，搭配 T86 個股買賣超排行。';
    $('#institutionalUpdatedAt').textContent = metadata.updated_at ? `更新 ${new Date(metadata.updated_at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false})}` : '安裝包初始資料';
    $('#institutionalSourceLabel').textContent = metadata.mode === 'live' ? 'TWSE 官方盤後資料' : '試作版種子資料；執行 Action 補齊';
    $('#institutionalStatusDot').className = metadata.mode === 'live' ? 'ok' : 'warning';
    $$('[data-flow]').forEach(button => button.classList.toggle('active', button.dataset.flow === state.flow));
    $$('[data-range]').forEach(button => button.classList.toggle('active', button.dataset.range === state.range));

    $('#institutionalSummary').innerHTML = [
      ['最近交易日', money(info.current.net), info.latest ? fmtFullDate(info.latest.date) : '—'],
      ['近 5 日累計', money(info.sum5), info.sum5 >= 0 ? '資金淨流入' : '資金淨流出'],
      ['近 20 日累計', money(info.sum20), `${Math.min(20,(state.payload?.daily || []).length)} 個交易日`],
      ['連買／連賣', `${info.streak.count} 日`, info.streak.direction],
      ['當日買進', gross(info.current.buy), '市場總買進金額'],
      ['當日賣出', gross(info.current.sell), info.ratio ? `買賣比 ${info.ratio.toFixed(2)}` : '—']
    ].map(([label,value,note]) => `<article><span>${escapeHtml(label)}</span><strong class="${String(value).startsWith('+') ? 'positive' : String(value).startsWith('-') ? 'negative' : ''}">${escapeHtml(value)}</strong><small>${escapeHtml(note)}</small></article>`).join('');

    renderDailyChart(rows);
    renderCumulativeChart(rows);
    renderWeeklyChart(state.payload?.daily || []);
    renderBuySellChart(rows);
    renderRankings();
    renderTable(rows);
  }

  function chartBase(container, values, {height=260, labels=[]}={}) {
    const width = 900, pad = {l:54,r:18,t:18,b:34};
    const plotW = width-pad.l-pad.r, plotH = height-pad.t-pad.b;
    const min = Math.min(0,...values), max = Math.max(0,...values);
    const span = Math.max(1,max-min);
    const y = value => pad.t + (max-value)/span*plotH;
    const zeroY = y(0);
    return {width,height,pad,plotW,plotH,min,max,y,zeroY,labels,container};
  }

  function axisSvg(base) {
    const {width,height,pad,plotW,plotH,min,max,y,zeroY} = base;
    const lines = [];
    for (let i=0;i<=4;i++) {
      const value = max-(max-min)*i/4;
      const py = pad.t+plotH*i/4;
      lines.push(`<line x1="${pad.l}" y1="${py}" x2="${pad.l+plotW}" y2="${py}" class="chart-grid-line"/><text x="${pad.l-8}" y="${py+4}" text-anchor="end" class="chart-axis-text">${value.toFixed(0)}</text>`);
    }
    lines.push(`<line x1="${pad.l}" y1="${zeroY}" x2="${pad.l+plotW}" y2="${zeroY}" class="chart-zero-line"/>`);
    return lines.join('');
  }

  function renderDailyChart(rows) {
    const values = rows.map(row => num(flowData(row).net));
    const root = $('#dailyFlowChart');
    if (!values.length) return emptyChart(root);
    const base = chartBase(root, values, {labels:rows.map(row => fmtDate(row.date))});
    const step = base.plotW/values.length;
    const barW = Math.max(4,Math.min(28,step*0.64));
    const bars = values.map((value,index) => {
      const x = base.pad.l+step*index+(step-barW)/2;
      const top = value >= 0 ? base.y(value) : base.zeroY;
      const h = Math.max(1,Math.abs(base.y(value)-base.zeroY));
      const label = rows.length <= 20 || index % Math.ceil(rows.length/10) === 0 ? `<text x="${x+barW/2}" y="${base.height-10}" text-anchor="middle" class="chart-axis-text">${base.labels[index]}</text>` : '';
      return `<g class="chart-bar-group"><rect x="${x}" y="${top}" width="${barW}" height="${h}" rx="3" class="${value>=0?'chart-positive':'chart-negative'}"><title>${rows[index].date} ${money(value)}</title></rect>${label}</g>`;
    }).join('');
    root.innerHTML = `<svg viewBox="0 0 ${base.width} ${base.height}" role="img">${axisSvg(base)}${bars}</svg>`;
  }

  function renderCumulativeChart(rows) {
    let running = 0;
    const values = rows.map(row => running += num(flowData(row).net));
    const root = $('#cumulativeFlowChart');
    if (!values.length) return emptyChart(root);
    const base = chartBase(root, values, {labels:rows.map(row => fmtDate(row.date))});
    const step = values.length > 1 ? base.plotW/(values.length-1) : base.plotW;
    const points = values.map((value,index) => `${base.pad.l+step*index},${base.y(value)}`).join(' ');
    const area = `${base.pad.l},${base.zeroY} ${points} ${base.pad.l+step*(values.length-1)},${base.zeroY}`;
    const dots = values.map((value,index) => `<circle cx="${base.pad.l+step*index}" cy="${base.y(value)}" r="${values.length<=20?3:2}" class="${value>=0?'chart-positive-fill':'chart-negative-fill'}"><title>${rows[index].date} 累積 ${money(value)}</title></circle>`).join('');
    root.innerHTML = `<svg viewBox="0 0 ${base.width} ${base.height}" role="img">${axisSvg(base)}<polygon points="${area}" class="chart-area"/><polyline points="${points}" class="chart-line"/>${dots}</svg>`;
  }

  function weekKey(date) {
    const d = new Date(`${date}T12:00:00+08:00`);
    const day = (d.getDay()+6)%7;
    d.setDate(d.getDate()-day);
    return d.toISOString().slice(0,10);
  }

  function renderWeeklyChart(rows) {
    const groups = new Map();
    rows.forEach(row => {
      const key = weekKey(row.date);
      groups.set(key,(groups.get(key)||0)+num(flowData(row).net));
    });
    const weekly = [...groups.entries()].sort().slice(-10).map(([date,value]) => ({date,value}));
    const root = $('#weeklyFlowChart');
    if (!weekly.length) return emptyChart(root);
    const values = weekly.map(row => row.value);
    const base = chartBase(root, values, {height:220,labels:weekly.map(row => fmtDate(row.date))});
    const step = base.plotW/values.length, barW = Math.min(42,step*0.58);
    const bars = values.map((value,index) => {
      const x = base.pad.l+step*index+(step-barW)/2;
      const top = value>=0?base.y(value):base.zeroY;
      const h = Math.max(1,Math.abs(base.y(value)-base.zeroY));
      return `<rect x="${x}" y="${top}" width="${barW}" height="${h}" rx="4" class="${value>=0?'chart-positive':'chart-negative'}"><title>週 ${weekly[index].date} ${money(value)}</title></rect><text x="${x+barW/2}" y="${base.height-10}" text-anchor="middle" class="chart-axis-text">${base.labels[index]}</text>`;
    }).join('');
    root.innerHTML = `<svg viewBox="0 0 ${base.width} ${base.height}">${axisSvg(base)}${bars}</svg>`;
  }

  function renderBuySellChart(rows) {
    const last = rows.slice(-10);
    const values = last.flatMap(row => [num(flowData(row).buy),num(flowData(row).sell)]);
    const root = $('#buySellChart');
    if (!values.length) return emptyChart(root);
    const base = chartBase(root, values, {height:220,labels:last.map(row => fmtDate(row.date))});
    const max = Math.max(1,...values), y = value => base.pad.t+(max-value)/max*base.plotH;
    const step = base.plotW/last.length, barW=Math.min(24,step*0.25);
    const bars = last.map((row,index) => {
      const flow=flowData(row), x=base.pad.l+step*index+step/2;
      const buy=num(flow.buy), sell=num(flow.sell);
      return `<rect x="${x-barW-2}" y="${y(buy)}" width="${barW}" height="${base.pad.t+base.plotH-y(buy)}" rx="3" class="chart-buy"><title>${row.date} 買進 ${gross(buy)}</title></rect><rect x="${x+2}" y="${y(sell)}" width="${barW}" height="${base.pad.t+base.plotH-y(sell)}" rx="3" class="chart-sell"><title>${row.date} 賣出 ${gross(sell)}</title></rect><text x="${x}" y="${base.height-10}" text-anchor="middle" class="chart-axis-text">${fmtDate(row.date)}</text>`;
    }).join('');
    root.innerHTML = `<div class="chart-inline-legend"><span><i class="buy"></i>買進</span><span><i class="sell"></i>賣出</span></div><svg viewBox="0 0 ${base.width} ${base.height}">${bars}</svg>`;
  }

  function emptyChart(root) {
    root.innerHTML = '<div class="chart-empty">執行法人資料 Action 後會補齊完整歷史圖表。</div>';
  }

  function rankingRows() {
    return state.payload?.rankings?.[state.flow] || {buys:[],sells:[]};
  }

  function renderRankings() {
    const ranking = rankingRows();
    const date = state.payload?.ranking_date || state.payload?.metadata?.latest_date;
    $('#topBuyTitle').textContent = `${FLOW_SHORT[state.flow]}買超個股前 10`;
    $('#topSellTitle').textContent = `${FLOW_SHORT[state.flow]}賣超個股前 10`;
    $('#rankingDateBuy').textContent = date ? fmtFullDate(date) : '等待更新';
    $('#rankingDateSell').textContent = date ? fmtFullDate(date) : '等待更新';
    $('#topBuyList').innerHTML = rankMarkup(ranking.buys,'buy');
    $('#topSellList').innerHTML = rankMarkup(ranking.sells,'sell');
  }

  function rankMarkup(items,kind) {
    if (!items?.length) return '<div class="ranking-empty">第一次執行「Update v10.7.1 integrated live data」後，會由 TWSE T86 補上官方個股排行。</div>';
    const max = Math.max(...items.map(item => Math.abs(num(item.net))),1);
    return items.slice(0,10).map((item,index) => `<a href="asset.html?id=TW:${encodeURIComponent(item.symbol)}" class="flow-rank-row"><b>${index+1}</b><div><strong>${escapeHtml(item.symbol)} ${escapeHtml(item.name)}</strong><small>買 ${shares(item.buy)}｜賣 ${shares(item.sell)}</small></div><span class="rank-bar"><i style="width:${Math.abs(num(item.net))/max*100}%"></i></span><em class="${kind==='buy'?'positive':'negative'}">${item.net>=0?'+':''}${shares(item.net)}</em></a>`).join('');
  }

  function renderTable(rows) {
    let running=0;
    const withRunning=rows.map(row => ({row,running:running+=num(flowData(row).net)}));
    $('#historyCount').textContent = `${rows.length} 個交易日`;
    $('#institutionalHistoryBody').innerHTML = withRunning.slice().reverse().map(({row,running}) => {
      const flow=flowData(row), net=num(flow.net);
      return `<tr><td>${escapeHtml(fmtFullDate(row.date))}</td><td>${gross(flow.buy)}</td><td>${gross(flow.sell)}</td><td class="${net>=0?'positive':'negative'}">${money(net)}</td><td class="${running>=0?'positive':'negative'}">${money(running)}</td><td><span class="flow-direction ${net>=0?'buy':'sell'}">${net>=0?'買超':'賣超'}</span></td></tr>`;
    }).join('');
  }

  load();
})();
