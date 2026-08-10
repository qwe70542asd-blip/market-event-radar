# 市場事件雷達 v11.4.37

以雙模式事件月曆為核心，整合台股行情、六大指數 K 線、多來源財經新聞、法人籌碼、完整台股／ETF 主檔與個人投資組合的靜態 PWA。

## v11.4.37 重點

這版集中處理 v11.4.34 部署後仍存在的 **TPEx 事件解析、TPEx 當沖口徑、Data Verification 搶跑與 BLS 403**。已正常的全球行情、台股成交額歷史、Stock Basics、TPEx 法人／融資與 Release Chromium CI 不重新改寫。

- **TPEx 歷史除權息**：支援官方文件實際使用的 `代號`、`名稱`、`權或息`、`現金股利`、`每仟股無償配股`。
- **TPEx 股利方案**：支援多種 payload shape、全形標點與 current long-form 董事會日期欄位；legacy 股利表無法解析 current-window event 時，只能由另一個 TPEx 官方重大訊息來源備援。
- **TPEx 當沖**：正確解析民國日期並從多日資料挑最新 verified session；OpenAPI 以市場彙總口徑發布，明確標示 `market-aggregate`，不偽造個股當沖。
- **Data Verification release barrier**：release push 時先等待 `live-tw-market` 達到 v11.4.37，再恢復來源並產生 verification，避免舊版 snapshot 搶跑。
- **BLS 403 官方備援**：加入 `data/bls-official-schedule-2026.json`，內容逐筆依 BLS 官方 2026 release schedule 建立；只有 live 官方路徑全部失敗才使用，且不推算任何未列日期。
- **BLS tracking 修正**：Productivity and Costs 的 preliminary / revised 同季事件分開追蹤，不會互相覆蓋。

## 覆蓋舊 repository 時一定要做

單純把 ZIP 解壓覆蓋 **不會刪除 Git 已追蹤的舊 `scripts/...` 巢狀副本**。覆蓋完成後請先執行根目錄：

```text
CLEAN-REPO.cmd
```

再到 GitHub Desktop 確認有大量舊 `scripts/assets`、`scripts/data`、`scripts/scripts` 等刪除項目，和本版修改一起 Commit / Push。

完整修正與部署檢查見 `docs/V11.4.37.md`、`docs/V11.4.37-release-audit.md` 與 `VALIDATION.txt`。

資料僅供市場觀察，不構成投資建議。所有市場與事件資料都應保留來源、時間與狀態；無法驗證的資料不得偽造成即時或正式值。
