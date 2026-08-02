(async () => {
  "use strict";
  const { $, escapeHtml, finite, loadData, mergeAssets, searchAssets, resolveAsset,
    loadPortfolio, migratePortfolio, savePortfolio, findTwQuote, formatPrice, formatPercent,
    formatMoney, direction, safeNewsLink, newsScore, formatTime } = MR;

  const [assetPayload,twPayload,marketPayload,newsPayload] = await Promise.all([
    loadData("assets.json", window.__ASSET_SEED__ || {assets:[]}),
    loadData("tw-market.json", window.__TW_MARKET_SEED__ || {items:[]}),
    loadData("market-snapshot.json", window.__MARKET_SNAPSHOT_SEED__ || {items:[]}),
    loadData("news.json", window.__NEWS_SEED__ || {items:[]})
  ]);
  const assets = mergeAssets(assetPayload.assets || [], (window.__ASSET_SEED__ || {}).assets || []);
  let entries = migratePortfolio(loadPortfolio(), assets);
  let selectedId = "";

  function quoteFor(entry) {
    if (entry.market === "TW") return findTwQuote(entry,twPayload);
    return (marketPayload.items || []).find(item => String(item.symbol || "").toUpperCase() === String(entry.symbol || "").toUpperCase()) || null;
  }
  function stats() {
    const counts = {
      all:entries.length,
      stocks:entries.filter(e=>e.asset_class==="stock").length,
      etfs:entries.filter(e=>e.asset_class==="etf").length,
      crypto:entries.filter(e=>e.asset_class==="crypto").length
    };
    $("#portfolioStats").innerHTML = `<article class="stat"><span>全部</span><strong>${counts.all}</strong></article><article class="stat"><span>股票</span><strong>${counts.stocks}</strong></article><article class="stat"><span>ETF／基金</span><strong>${counts.etfs}</strong></article><article class="stat"><span>虛擬貨幣</span><strong>${counts.crypto}</strong></article>`;
  }
  function renderHoldings() {
    stats();
    let live=0;
    const rows = entries.map(entry => {
      const quote = quoteFor(entry);
      if (finite(quote?.price)!==null) live++;
      const price=finite(quote?.price), shares=finite(entry.shares), avg=finite(entry.avg_cost);
      const value=price!==null&&shares!==null?price*shares:null;
      const cost=avg!==null&&shares!==null?avg*shares:null;
      const pnl=value!==null&&cost!==null?value-cost:null;
      return `<tr>
        <td><a href="asset.html?id=${encodeURIComponent(entry.asset_id || `${entry.market}:${entry.symbol}`)}"><strong>${escapeHtml(entry.symbol)} ${escapeHtml(entry.name)}</strong><small>${escapeHtml(entry.exchange || entry.market)} · ${entry.asset_class==="etf"?"ETF":entry.asset_class==="crypto"?"虛擬貨幣":"股票"}</small></a></td>
        <td><strong>${formatPrice(price,entry.currency)}</strong><small class="${direction(quote?.change_percent)}">${formatPercent(quote?.change_percent)}</small></td>
        <td><strong>${shares===null?"觀察":`${shares.toLocaleString("zh-TW")} 股`}</strong><small>${avg===null?"未填成本":`均價 ${formatPrice(avg,entry.currency)}`}</small></td>
        <td><strong>${entry.currency==="USD"?(value===null?"—":`$${value.toLocaleString("zh-TW",{maximumFractionDigits:2})}`):formatMoney(value)}</strong></td>
        <td><strong class="${direction(pnl)}">${entry.currency==="USD"?(pnl===null?"—":`${pnl>0?"+":""}$${pnl.toLocaleString("zh-TW",{maximumFractionDigits:2})}`):formatMoney(pnl,true)}</strong><small>${pnl!==null&&cost?formatPercent(pnl/cost*100):"—"}</small></td>
        <td><div class="row-actions"><button data-edit="${entry.id}">編輯</button><button data-remove="${entry.id}">移除</button></div></td>
      </tr>`;
    });
    $("#holdingRows").innerHTML = rows.length?rows.join(""):'<tr><td colspan="6"><div class="empty">尚未加入標的。</div></td></tr>';
    $("#holdingStatus").textContent = live?`${live} 項有行情`:"等待行情";
    document.querySelectorAll("[data-remove]").forEach(btn=>btn.addEventListener("click",()=>{
      entries=entries.filter(e=>e.id!==btn.dataset.remove);savePortfolio(entries);renderAll();
    }));
    document.querySelectorAll("[data-edit]").forEach(btn=>btn.addEventListener("click",()=>{
      const entry=entries.find(e=>e.id===btn.dataset.edit);if(!entry)return;
      const form=$("#addForm");form.query.value=`${entry.symbol} ${entry.name}`;form.shares.value=entry.shares??"";form.avg_cost.value=entry.avg_cost??"";selectedId=entry.asset_id;form.dataset.editId=entry.id;$("#formStatus").textContent=`正在編輯 ${entry.name}`;
      window.scrollTo({top:0,behavior:"smooth"});
    }));
  }
  function renderNews() {
    const scored=(newsPayload.items||[]).map(item=>{
      let best=0,reason=null;entries.forEach(entry=>{const score=newsScore(item,entry);if(score>best){best=score;reason=entry}});return{item,best,reason};
    }).filter(row=>row.best>0).sort((a,b)=>b.best-a.best||new Date(b.item.published_at)-new Date(a.item.published_at)).slice(0,6);
    $("#portfolioNews").innerHTML=scored.length?scored.map(({item,reason})=>`<a class="news-card" href="${escapeHtml(safeNewsLink(item))}" target="_blank" rel="noreferrer noopener"><div class="news-source"><span>${escapeHtml(item.source||"財經新聞")}</span><time>${formatTime(item.published_at)}</time></div><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.summary||"點擊前往原始來源。")}</p><div class="tag-row"><span class="tag">${escapeHtml(reason.name)}</span><span class="tag">${escapeHtml(item.topic||"market")}</span></div></a>`).join(""):'<div class="empty" style="grid-column:1/-1">新聞排程完成後，這裡會依正式名稱、代碼、產業與 ETF 成分關聯顯示。</div>';
  }
  function renderAll(){renderHoldings();renderNews()}

  function showSuggestions() {
    const form=$("#addForm"),query=form.query.value,market=form.market.value,cls=form.asset_class.value;
    const items=searchAssets(assets,query,{market,asset_class:cls==="fund"?"all":cls});
    const box=$("#assetSuggestions");
    box.innerHTML=items.map(asset=>`<button type="button" data-id="${escapeHtml(asset.id)}"><strong>${escapeHtml(asset.symbol)}</strong><span><b>${escapeHtml(asset.name)}</b><small>${escapeHtml(asset.sub_industry||asset.official_industry||asset.sector)}</small></span><em>${escapeHtml(asset.exchange||asset.market)}</em></button>`).join("");
    box.hidden=!items.length;
    box.querySelectorAll("[data-id]").forEach(btn=>btn.addEventListener("click",()=>{
      const asset=assets.find(a=>a.id===btn.dataset.id);selectedId=asset.id;form.query.value=`${asset.symbol} ${asset.name}`;box.hidden=true;$("#formStatus").textContent=`已選擇：${asset.name}（${asset.symbol}）`;
    }));
  }
  $("#addForm").query.addEventListener("input",()=>{selectedId="";showSuggestions()});
  $("#addForm").market.addEventListener("change",()=>{selectedId="";showSuggestions()});
  $("#addForm").asset_class.addEventListener("change",()=>{selectedId="";showSuggestions()});
  $("#addForm").addEventListener("submit",event=>{
    event.preventDefault();
    const form=event.currentTarget;
    let asset=selectedId&&assets.find(a=>a.id===selectedId);
    if(!asset)asset=resolveAsset(assets,form.query.value.split(/\s+/)[0],{market:form.market.value,asset_class:form.asset_class.value==="fund"?"all":form.asset_class.value});
    if(!asset){$("#formStatus").textContent="查無正式代碼；請從搜尋結果選擇。009816 是有效的凱基台灣TOP50。";return}
    const shares=finite(form.shares.value),avg=finite(form.avg_cost.value);
    const editId=form.dataset.editId;
    const existingIndex=editId?entries.findIndex(e=>e.id===editId):entries.findIndex(e=>e.asset_id===asset.id);
    const next={...asset,id:editId||(crypto.randomUUID?crypto.randomUUID():`${Date.now()}-${Math.random()}`),asset_id:asset.id,shares,avg_cost:avg};
    if(existingIndex>=0)entries[existingIndex]=next;else entries.push(next);
    savePortfolio(entries);form.reset();form.dataset.editId="";selectedId="";$("#formStatus").textContent=existingIndex>=0?"組合資料已更新。":"已加入投資組合。";renderAll();
  });

  renderAll();
})();
