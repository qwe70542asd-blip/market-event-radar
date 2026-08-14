# 市場事件雷達 v11.4.44

以事件月曆為核心，整合台股行情、全球市場、財經新聞、法人籌碼、股票／ETF 資料與個人投資組合的靜態 PWA。

## v11.4.44：單一發布者與台股交易日完整性

這版不是再疊一層小修，而是針對 v11.4.43 線上失敗紀錄與 repository 結構做整體清查，把會互相覆蓋、會留下舊檔、會把不同交易日資料混在一起的路徑一次收斂。

- **Repository 覆蓋殘留**：`CLEAN-REPO.cmd` 改由 `scripts/cleanup_repo.py` 讀取 `VERSION.json`，自動清除舊版 regression tests、verifier、deletion manifest、`apply_v*.py`、巢狀 repository 與已淘汰的重複 workflow。
- **單一 live branch 發布者**：移除 15 個與 aggregate scheduler 重複的 workflow。`scripts/audit_workflow_publishers.py` 會在 Release Verification 阻擋任何 `live-*` branch 多重 writer。
- **台股交易日分離**：quote snapshot 的 `trading_date` 與成交金額歷史的 `history_end` 分開管理，不再因其中一個來源較慢就把另一份已驗證資料回退或刪掉。
- **TWSE／TPEx 完整性**：新 snapshot 必須兩個市場各自都有足夠有效列、交易日一致且不得倒退，否則保留 last-known-good，避免 TWSE-only 或混合交易日資料被當成完整台股。
- **排程穩定性**：5 分鐘一次的 `update-market-core.yml` 不再取消仍在正常執行的上一輪更新。
- **Release Verification**：先檢查 stale/conflicting files 與 workflow writer 衝突，再跑 syntax、資料驗證、259 個 regression tests、HTTP app-shell、Chromium runtime 與 reachability-aware live contract。

## 覆蓋既有 repository

這是 **full overwrite release**，不是 patch。請依照以下順序：

1. 先在 GitHub Desktop Fetch/Pull 最新 `main`。
2. 把 v11.4.44 ZIP 內容直接解壓到 repository root，不要多包一層資料夾。
3. 執行 `CLEAN-REPO.cmd`。
4. 回 GitHub Desktop 確認除了修改／新增檔案，也有顯示舊檔刪除。
5. Commit / Push。
6. GitHub Actions 的 `Verify v11.4.44 stable app release` 必須通過；紅燈不要忽略。

建議 commit：`market-event-radar-v11.4.44`

完整根因、刪除清單與驗收結果見：

- `docs/V11.4.44-release-audit.md`
- `DELETION-MANIFEST-v11.4.44.txt`
- `VALIDATION.txt`
- `GITHUB-DESKTOP-UPDATE.txt`

資料僅供市場觀察，不構成投資建議。無法驗證的值維持缺值／warning，不得偽造成正式或即時資料。
