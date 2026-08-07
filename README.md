# 市場事件雷達 v11.4.21

本版優先修正「新價格與舊 OHLC 混在同一張卡片」以及 GitHub 排程無法保證每分鐘執行的問題。資料若無法確認屬於同一交易日，會保留上次驗證成功內容並標示延遲，不再冒充今日行情。

## v11.4.21 重點

- 指數價格、開盤、最高、最低、收盤、成交量及漲跌，必須屬於同一個交易日。
- 盤中價格必須位於當日最高與最低之間；不符合即拒絕發布。
- 台灣、日本、韓國與美國市場依各自交易時段分開檢查。
- 網頁開啟期間：任一市場開盤時每 60 秒重新讀取；休市期間每 15 分鐘；切回 App／頁面立即更新。
- GitHub Actions 保留每 5 分鐘備援，但不再宣稱它能保證每分鐘即時。
- 內附 Cloudflare Worker，可在市場開盤期間每分鐘更新，並每 15 分鐘執行完整健康檢查。
- 六大指數新增 5 分、15 分、30 分、1 小時、4 小時、日、週、月 K。
- K 線支援滑鼠／手指游標 OHLC、縮放、拖曳與雙指縮放。
- 首頁精選只顯示今日、明日、後天重大事件，以及最近 24 小時突發新聞；不再用數月前舊聞補位。
- 新增 TWSE、TPEx 歷史除權息結果回補，自 2026-01-01 起與未來預告表合併。
- 不包含虛擬貨幣、永續合約或加密貨幣交易功能。

## 一般部署

1. 解壓縮 ZIP。
2. 將全部檔案複製到 repository 根目錄並覆蓋。
3. 保留 `.git` 資料夾。
4. Commit：`Update to v11.4.21`。
5. Push 後等待 GitHub Actions 第一輪更新。

未部署即時 Worker 時，網站仍會使用 GitHub 資料分支與本機快取，但更新頻率仍受 GitHub Actions 排程限制。

## 啟用盤中每分鐘更新

1. 建立 Cloudflare Worker 與 KV namespace。
2. 在 GitHub repository secrets 加入：
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_ACCOUNT_ID`
   - `CLOUDFLARE_KV_NAMESPACE_ID`
3. 手動執行 `Deploy v11.4.21 live market worker` workflow。
4. 將部署後的 Worker 網址填入 `assets/runtime-config.js`：

```js
window.MR_RUNTIME={
  liveMarketEndpoint:"https://你的-worker.workers.dev"
};
```

詳細步驟見 `docs/V11.4.21-live-market.md`。

資料僅供市場觀察，不構成投資建議。
