# 市場事件雷達 v11.5.1

## Full Replacement / Runtime Stability Release

v11.5.1 延續 v11.5.0 的 Compact Live Data Architecture，這版集中修正首頁啟動、重複請求、Service Worker、舊 cache、版本混用與 GitHub Actions 發布一致性。此 ZIP 是**完整 repository replacement**，不是 patch、overlay、updater 或產生器。

### v11.5.1 主要修正

- 首頁 19 個獨立 seed script 合併為單一 `data/home-bootstrap-seed.js` fallback bundle；首頁外部 script 全部使用 `defer`，避免 parser-blocking request storm。
- `shared.js` 新增同 URL inflight GET 去重；第一屏只啟動 Raw + jsDelivr 兩條鏡像，後續刷新才開完整 fallback ladder。
- 首頁新聞改成單 worker、延遲啟動、來源間 stagger；台股即時刷新加入 focus / visibility 節流，避免切回頁面立刻重抓同一批資料。
- stale market guard 首次只共用一般 `loadData` inflight，15 秒後才允許 forced refresh，不再於 boot 後 2 秒重複強制抓行情／籌碼／snapshot。
- 舊 localStorage / sessionStorage / IndexedDB 清理改為 load 後 idle 執行，不再首頁同步掃完整 channel 清單造成 UI 卡住。
- Service Worker 使用 v11.5.1 原子 cache namespace；版本化 JS/CSS/圖示採 cache-first，資料 JSON 與 navigation 採有 timeout 的 network-first；cache key 僅移除 `t`/`_` busting query，保留 `v` 版本，不再 `ignoreSearch:true` 混用舊資產。
- SW 註冊延後至 window load / idle；升版只清除舊 `market-event-radar-*` cache，不再 `controllerchange -> location.reload()`，避免 reload loop。
- `runtime-config` health probe 的首頁等待上限縮短，避免 Worker health 異常拖住第一屏。
- active data JSON / seed release metadata 統一為 `v11.5.1`。
- GitHub Actions 需要比對 release version 的地方改由 `VERSION.json` 解析，避免下一版 workflow 還寫死舊 patch 版號；release verification concurrency 名稱也不再綁 patch number。
- 保留 v11.5.0 既有 compact frontend、兩位數 asset shard、事件日曆、資料品質 fail-closed、24 live branches 單 writer 等正式規格。

### Full Replace 使用方式

1. GitHub Desktop 選擇 `market-event-radar`，用 **Show in Explorer** 開啟 repository。
2. 保留 repository 根目錄的 `.git`。
3. 解壓 `market-event-radar-v11.5.1-full-replace.zip`。
4. ZIP 第一層就是正式專案 root；將第一層內容直接放到 repository root，不要再多包一層資料夾。
5. 若 repository 中仍有舊版 release-only 檔案，依 `DELETION-MANIFEST-v11.5.1.txt` 移除；本包本身不需要執行任何 patch、updater 或 generator。
6. Commit 建議：`market-event-radar-v11.5.1-full-replace`，再 Push。
7. Push 後確認 `Verify stable app release` 與各 live-data workflows 正常完成。

### 驗證

本版發布前已完成完整 pytest、repository cleanup、24 branch single-writer audit、Python / JavaScript / shell syntax、16 個 workflow YAML、安全稽核、production readiness、strict public-data validation、compact payload budget 與 HTTP smoke。瀏覽器 smoke 在目前執行環境仍因 localhost 被 Chromium 系統政策阻擋，GitHub Hosted Runner 的 browser gate 保留為 push 後權威驗證。

詳見 `VALIDATION-v11.5.1.txt` 與 `docs/V11.5.1-ARCHITECTURE.md`。
