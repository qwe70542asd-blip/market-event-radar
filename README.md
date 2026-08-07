# 市場事件雷達 v11.4.26

v11.4.26 是 App 上線前的大整理版，重點是資料顯示清楚、搜尋操作、新聞圖片、首頁排版、產業分類、法人單位與指數資料驗證。

## 本版重點

- 法人市場彙總與個股法人資料統一顯示「張」，正負值同時標示買超／賣超；1 張 = 1,000 股。
- 投資組合新增股票／ETF autocomplete：可輸入代碼前綴或名稱，支援鍵盤與觸控，選取後自動帶入名稱；不存在的標的不允許加入。
- 「台股產業熱度榜」改名為「台股今日產業強弱」，TWSE／TPEx 數字產業代碼會先轉成中文，避免 26、28 直接露出。
- 首頁精選重大資訊改為自動填滿 Grid，避免右下角大片空白。
- 首頁精選新聞限定最近 24 小時，重大事件限定今日／明日／後日；舊新聞保留在歷史新聞區。
- 新聞圖片流程重做：即時與歷史新聞先合併，Google News 先解析回原文，再搜尋 OG、Twitter、JSON-LD、srcset 與文章主圖；保存多個候選圖片，前端失敗時逐一重試，最後才使用本地主題備援圖。
- 日經 225 已加入 Nikkei 官方 Daily Data CSV 驗證已完成交易日；盤中仍以 Yahoo 同交易日資料為即時來源，禁止不同交易日混用。
- 六大指數維持：台灣加權、道瓊、NASDAQ、費半、S&P 500、日經 225。
- 行情資料驗證失敗時採 fail-closed，保留最後一次已驗證資料，不以可疑資料覆蓋。
- 15 分鐘 K 線列為部署後驗證項目，不在本機測試中虛報通過；詳見 `docs/V11.4.26-release-audit.md`。

## 覆蓋部署

1. 解壓 ZIP。
2. 將包內所有檔案直接覆蓋 repository 根目錄。
3. 保留原本 `.git` 資料夾。
4. GitHub Desktop Commit：`market-event-radar-v11.4.26`。
5. Push origin。
6. 確認 `Verify v11.4.26 app release` 與資料更新 Actions。
7. 若要 30～60 秒真正即時行情，部署 `edge/market-live-worker.js` 並將 Worker HTTPS URL 填入 `assets/runtime-config.js`。

## 已知部署後檢查

- 15 分鐘 K：Yahoo／Edge Worker 外部資料依賴，部署後逐一檢查六個指數；失敗時顯示暫時無法取得，不偽造 K 棒。
- `assets/runtime-config.js` 若 `liveMarketEndpoint` 為空，GitHub Actions 僅是排程備援，不能視為每分鐘即時。
- 新聞原圖需等新聞 Actions 在線上重新掃描來源，原站拒絕圖片請求時會依候選圖順序重試後再回退主題圖。

資料僅供市場觀察，不構成投資建議。
