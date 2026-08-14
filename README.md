# 市場事件雷達 v11.4.46

以事件月曆為核心，整合台股行情、全球市場、財經新聞、法人籌碼、股票／ETF 資料與個人投資組合的靜態 PWA。

## v11.4.46：防回歸、安全授權與 Production Readiness

這版把「程式碼存在」與「正式環境真的啟用」分開驗收，避免即時行情、Cloudflare 部署或外部 API parser 再次出現修過後復發。

- **即時行情不再假裝成功**：Worker 未實際部署時 UI 明確顯示 `GitHub 備援・非即時`；只有真正從 Worker 取得資料才可顯示盤中每分鐘刷新。
- **部署後 404 假失敗已修正**：Production Readiness 對新部署 Worker 採 0/3/5/10/15/30 秒重試，不再於 Wrangler 成功後不到 1 秒就因 workers.dev 路由尚未傳播而誤判失敗。
- **CSP 測試不再自撞安全政策**：Chromium smoke 改用 Playwright Locator/Expect，不再使用字串版 `wait_for_function` 觸發 `unsafe-eval`。正式頁面仍保持 `script-src 'self'`。
- **Worker 身分鎖定**：只接受 `market-event-radar-live.qwe70542asd.workers.dev`，且瀏覽器在信任 endpoint 前必須驗證 `/health` 的 service/version/KV/rate-limit contract。
- **Cloudflare 原生 Rate Limiting**：對 snapshot/K-line 加入 Workers Rate Limiting binding，超量回 429；無 binding 時 Worker 健康狀態直接 degraded。
- **Cloudflare Token 洩漏掃描**：CI 額外攔截 2026 新格式 `cfut_`、`cfat_`、`cfk_`。
- **Cloudflare 授權 fail-closed**：Token／Account／KV 少任何一項就讓部署紅燈；Endpoint 直接取自 Wrangler 成功部署輸出並經 live gate 驗證，不再靠人工維護，也不再允許 `skipped` 卻顯示 success。
- **權限分離**：Cloudflare deploy job 只有 repository read；發布 `live-runtime` 的 write job 不持有 Cloudflare Token。
- **Actions 供應鏈鎖定**：所有外部 Action 使用完整 commit SHA；checkout 一律 `persist-credentials:false`；目前鎖定 checkout v7.0.1、setup-python v7.0.0、upload-artifact v7.0.1、wrangler-action v4.0.0；Wrangler 固定 4.123.0；Python 依賴固定版本。
- **永久 Security Gate**：CSP、外部 URL scheme、remote runtime JS、憑證檔、Actions SHA、部署授權、Portfolio 匯入限制都進 CI 自動阻擋。
- **Dependabot + PR Gate**：每週檢查 pip / GitHub Actions 更新，PR 也必須跑完整 Release Verification，避免「更新套件＝直接進正式環境」。
- **TWSE parser 防漂移**：正式 updater 與 live verifier 共用同一個語意 selector/parser，不再各自硬寫不同 endpoint。
- **Service Worker 防舊版卡住**：runtime config 不預快取；JS/CSS/data 改 network-first。
- **單一 live branch writer**：持續保留 v11.4.44 建立的單一發布者規則，新增 `live-runtime` 後共 25 個 live branches 全部一個 writer。

## 覆蓋既有 repository

這是 **full overwrite release**，不是 patch。請依照以下順序：

1. 先在 GitHub Desktop Fetch/Pull 最新 `main`。
2. 把 v11.4.46 ZIP 內容直接解壓到 repository root，不要多包一層資料夾。
3. 執行 `CLEAN-REPO.cmd`。
4. 回 GitHub Desktop 確認除了修改／新增檔案，也有顯示舊檔刪除。
5. Commit / Push。
6. GitHub Actions 的 `Verify v11.4.46 stable app release` 必須通過；紅燈不要忽略。

建議 commit：`market-event-radar-v11.4.46`

完整根因、刪除清單與驗收結果見：

- `docs/V11.4.46-release-audit.md`
- `DELETION-MANIFEST-v11.4.46.txt`
- `VALIDATION.txt`
- `GITHUB-DESKTOP-UPDATE.txt`

資料僅供市場觀察，不構成投資建議。無法驗證的值維持缺值／warning，不得偽造成正式或即時資料。
