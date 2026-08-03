(async()=>{
  "use strict";
  const {$,escapeHtml,formatTime,loadData,loadChannelManifest,DATA_CHANNELS}=MR;
  const schedules={
    assets:"每日 2 次",
    events:"每 6 小時",
    twMarket:"分支每 5 分鐘／畫面 5 秒",
    twChips:"盤後分時更新",
    globalMarket:"每 10 分鐘",
    news:"每 5 分鐘"
  };

  async function inspect(key,definition){
    const [manifest,payload]=await Promise.all([
      loadChannelManifest(definition),
      loadData(definition.files[0],{})
    ]);
    const files=manifest?.files||[];
    const records=files.reduce((sum,row)=>sum+Number(row.records||0),0);
    const branchOk=payload?.__branch===definition.branch;
    return {
      key,definition,manifest,payload,records,branchOk,
      updated:manifest?.payload_updated_at||payload?.metadata?.updated_at||payload?.updated_at||null
    };
  }

  async function render(){
    const rows=await Promise.all(Object.entries(DATA_CHANNELS).map(([key,definition])=>inspect(key,definition)));
    $("#statusUpdated").textContent=`檢查 ${new Date().toLocaleTimeString("zh-TW",{hour12:false})}`;
    const directCrypto={
      definition:{branch:"direct-websocket",label:"虛擬貨幣秒級行情",files:["Binance miniTicker"]},
      branchOk:typeof WebSocket!=="undefined",
      manifest:null,records:5,updated:new Date().toISOString()
    };
    const displayRows=[...rows,directCrypto];
    $("#channelGrid").innerHTML=displayRows.map(row=>{
      const state=row.definition.branch==="direct-websocket"?(row.branchOk?"秒級直連":"瀏覽器不支援"):row.branchOk?"正常":row.manifest?"備援讀取":"等待首次建立";
      const cls=row.branchOk?"source-ok":row.manifest?"":"down";
      return `<article class="panel channel-card">
        <div class="channel-head"><span class="channel-state ${cls}"></span><div><small>${escapeHtml(row.definition.branch)}</small><h2>${escapeHtml(row.definition.label)}</h2></div></div>
        <div class="channel-kpis">
          <span><small>狀態</small><strong>${state}</strong></span>
          <span><small>資料筆數</small><strong>${Number(row.records||0).toLocaleString("zh-TW")}</strong></span>
        </div>
        <p>資料更新：${row.updated?formatTime(row.updated):"等待第一次成功排程"}</p>
        <p>發布時間：${row.definition.branch==="direct-websocket"?"不經 GitHub Actions":row.manifest?.published_at?formatTime(row.manifest.published_at):"尚未建立分支"}</p>
      </article>`;
    }).join("");

    $("#channelRows").innerHTML=displayRows.map(row=>`<tr>
      <td><strong>${escapeHtml(row.definition.label)}</strong></td>
      <td><code>${escapeHtml(row.definition.branch)}</code></td>
      <td>${escapeHtml(row.definition.branch==="direct-websocket"?"每秒推送／30 秒備援":schedules[row.key]||"獨立排程")}</td>
      <td>${escapeHtml(row.definition.files.join("、"))}</td>
      <td>${escapeHtml(row.definition.branch==="direct-websocket"?"Binance WebSocket":row.payload?.__branch||row.payload?.__source||"fallback")}</td>
    </tr>`).join("");
  }

  await render();
  setInterval(render,60_000);
})();