# 市場事件雷達 v11.5.0

## 大版本：Compact Live Data Architecture

v11.5.0 是封版型架構更新，不新增花俏功能，優先處理「頁面打不開、舊資料來源互相覆蓋、舊系統殘留、同一頁下載完整巨型資料檔」等問題。

### 主要改動

- 首頁不再直接下載 `assets.json`、`events.json`、`tw-chips.json`、`dividend-history.json` 等完整歷史資料。
- 新增四個前端輕量資料契約：
  - `home-assets.json`
  - `home-events.json`
  - `tw-market-compact.json`
  - `tw-chips-compact.json`
- 首頁、台股排行、法人籌碼、投資組合、stale guard、日期提醒、個股頁行情全部改用 compact 通道。
- 完整 `events.json` 只在事件詳情找不到該事件時才按需下載，不再作為首頁開機依賴。
- 個股 detail shard 從舊的一碼 0–9 分片改為二碼 00–99 分片；舊的一碼 shard 已從 release 移除，避免新舊格式同時存在。
- 未知數字產業代碼（例如 `91`）不得直接成為首頁產業名稱；個股頁顯示「其他／未分類」。
- 移除舊版 `mobile-global-quick-nav` 動態注入系統；首頁只保留一組左側固定 01–04 浮動導覽，其他頁只使用既有底部導覽。
- Service Worker 保留 network-first 與一次性升版重載，但不再安裝時預抓大型 optional data。
- 新增前端 payload budget gate；compact payload 超過限制時 CI 直接失敗。
- `channel-health.json` 同時監控 compact 前端索引，前端資料缺失會被列為 critical health 問題。

### 發布規則

1. GitHub Desktop 選擇 `market-event-radar`。
2. **Show in Explorer**。
3. 保留 repository 內的 `.git`。
4. 解壓 `market-event-radar-v11.5.0-full-replace.zip`。
5. ZIP 第一層全部內容直接覆蓋 repository root，不要多包一層。
6. 依 `DELETION-MANIFEST-v11.5.0.txt` 確認舊 release-only 檔案已移除。
7. Commit 建議：`market-event-radar-v11.5.0-full-replace`。
8. Push 後等待 `Verify stable app release` 與資料更新 workflows 完成。

### 驗證

詳見 `VALIDATION-v11.5.0.txt` 與 `docs/V11.5.0-ARCHITECTURE.md`。
