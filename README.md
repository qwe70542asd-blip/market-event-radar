# 市場事件雷達 v11.4.39

以雙模式事件月曆為核心，整合台股行情、六大指數 K 線、多來源財經新聞、法人籌碼、完整台股／ETF 主檔與個人投資組合的靜態 PWA。

## v11.4.39 重點：穩定資料核心重做

本版不移除既有網站功能，集中重做最容易造成整條 pipeline 紅燈或資料誤判的 **TPEx 當沖、TPEx 股利判定、Data Verification、Release live gate**。

- **Data Verification stock / ETF 完全隔離**：可選來源不再共用 branch-local 變數，避免 ETF 先跑時 `channel_revenue` 未初始化，或股票誤用 ETF reference row。
- **上游版本透明**：`version_mismatch_sources` 會明確列出尚未升到本版的 live channel；資料會標 partial，而不是假裝同步完成。
- **TPEx 當沖直接支援真實 OpenAPI schema**：`DayTradingVolume`、`DayTradingValueOfBuys`、`DayTradingValueOfSells` 與三個市場比重欄位。volume / buy / sell 三個核心欄位必須一起存在才發布。
- **TPEx 股利 healthy-zero 語意**：歷史表可達但監控期間沒有 eligible row 時，視為健康零資料；`股東會日期配盈餘/待彌補虧損(元)` 明確排除，不再誤當日期。
- **Release Verification 改成 deterministic-first**：syntax、strict validation、pytest、HTTP、Chromium 先完整執行，最後才檢查 TPEx live contract。
- **外部故障隔離**：TPEx 5xx／網路／非 JSON 回應只記 external warning；HTTP 200 且有 eligible/current rows 但 production parser 不認得，才是 blocking contract failure。
- **診斷保留**：`Diagnose TPEx live schemas` 繼續蒐集實際 schema，維護時不靠猜欄位。

## 覆蓋舊 repository

解壓 ZIP 後，將 ZIP 內所有根目錄內容直接覆蓋本機 `market-event-radar`。因為覆蓋不會自動刪除舊 Git 追蹤檔，覆蓋後先執行：

```text
CLEAN-REPO.cmd
```

它會清除舊版 verifier/test helper、意外巢狀 repository 與 obsolete release files，不會刪正常 production scripts。之後再由 GitHub Desktop Commit / Push。

建議 commit：`market-event-radar-v11.4.39-stable-core`

完整修正與部署檢查見 `docs/V11.4.39.md`、`docs/V11.4.39-release-audit.md` 與 `VALIDATION.txt`。

資料僅供市場觀察，不構成投資建議。所有市場與事件資料都應保留來源、時間與狀態；無法驗證的資料不得偽造成即時或正式值。
