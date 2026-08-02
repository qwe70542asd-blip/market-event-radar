# 本次整理包檢查結果

檢查日期：2026-08-02

## 已通過

- 17 個前端 JavaScript 檔案語法檢查。
- 6 個 Python 更新程式語法檢查。
- `data/` 內 9 個 JSON、`manifest.webmanifest` 與 `VERSION.json` 解析檢查。
- 7 個 HTML 頁面的本機檔案引用檢查。
- GitHub Actions Workflow YAML 解析檢查。
- 4 項最後交易日單元測試：跨時區日線、禁止舊日覆蓋、同日修正、ETF 成交值排行。
- `live-data` 共用路徑測試：行情、新聞、法人與標的明細皆會移除前面的 `data/`，對應分支根目錄。
- 首頁 ID 唯一性與區塊順序檢查：ETF 行情之後為虛擬貨幣，近期高影響事件位於下層。
- 第一次上傳的 Workflow 模式已確認為 `all`。
- 新整理包未包含 `scripts/__pycache__/`。
- 網站安裝名稱已移除舊的 `10.5` 顯示。

## 尚未宣告通過

- GitHub Actions 線上執行。
- `live-data` 分支建立與寫入。
- 線上新聞、行情、法人與公告的有效資料。
- Service Worker 在實際 GitHub Pages 上的快取接管。
- 桌機與手機的真實瀏覽器顯示與互動。
- 虛擬貨幣長時間運作的跳動與穩定性。
- 全產業指標、四市場證券主檔、ETF／基金完整資料。

以上未完成項目必須依 `03-TEST-ORDER.md` 逐項驗證，不能用本次靜態檢查代替。
