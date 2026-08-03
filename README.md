# 市場事件雷達｜v11.2.3 啟動修正版

本版修正 上一版所有頁面顯示空白的共同原因，並加入發布前瀏覽器測試與 15 分鐘硬性上限。

## 根本原因

`assets/shared.js` 最後建立 `window.MR` 時輸出不存在的 `LIVE_BASE`，實際常數名稱已改成 `LEGACY_LIVE_BASE`。這個 ReferenceError 會讓 `MR` 完全無法建立，因此首頁、台股排行、法人籌碼、事件月曆、全球行情與投資組合的後續 JavaScript 全部停止。

## 修正

- 改為正確輸出 `LEGACY_LIVE_BASE`。
- 新增 shared.js 啟動測試，未來若輸出未宣告變數會直接測試失敗。
- 專用資料分支最長等待 6 秒，失敗後立即改讀網站內建資料，再嘗試舊分支備援。
- 動態 raw GitHub、TWSE、Yahoo、CoinGecko 請求不再被 Service Worker 快取。
- 擴充舊投資組合 localStorage 金鑰遷移。
- 六個 Workflow 的 `timeout-minutes` 全部設定為 14，超過即判定失敗。
- 籌碼官方請求縮短為每次 10 秒、最多回查 7 個交易日。
- 財報來源單次逾時縮短，避免單一 MOPS 端點拖垮整個排程。
- Git 分支讀寫加入 45–90 秒逾時。

## 發布前測試

- 26 項 Python 單元測試。
- shared.js Node 執行期啟動測試。
- Chromium 瀏覽器端到端測試：首頁、台股排行、法人籌碼、新聞、資料狀態。
- 台股、事件、籌碼、新聞、全球市場的模擬分支資料皆能渲染。
- 籌碼與事件更新程式使用官方欄位形狀模擬執行。
- JSON、Python、JavaScript、Shell、YAML、HTML 引用檢查。

## 上傳

1. 解壓縮 ZIP。
2. 將資料夾內全部檔案覆蓋到 GitHub Desktop 倉庫根目錄。
3. Commit：`修正全站資料啟動 v11.2.3`
4. Push origin。
5. 等 Pages 部署完成。
6. 網站按 `Ctrl + F5`。
7. Actions 中所有工作若超過 14 分鐘會自動失敗，不會無限卡住。

六個 `live-*` 資料分支不需要刪除。
