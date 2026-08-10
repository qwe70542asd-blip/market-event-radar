# 市場事件雷達 v11.4.40

以事件月曆為核心，整合台股行情、全球市場、財經新聞、法人籌碼、股票／ETF 資料與個人投資組合的靜態 PWA。

## v11.4.40：資料正確性、法人金額與同步整合

這版承接 v11.4.39 stable core，集中處理自我檢查發現的資料誤判、來源同步與完整性問題，不移除既有功能。

- **新聞實體辨識**：所有兩字中文公司簡稱都視為高碰撞名稱，必須有鄰近市場／企業語境；修正「至上」誤中「截至上午」等問題，保留舊新聞 archive 的重新分類機制。
- **新聞分類**：毛利率、營益率、淨利率不再因包含「利率」而誤判成央行新聞；Fed、央行、升降息與政策利率仍正常歸類。
- **Data Verification release barrier**：push 後等待 assets、tw-market、monthly-revenue、dividend-history、secondary-reference、Yahoo details、ETF details 全部升到 v11.4.40 才發布驗證快照。
- **法人籌碼**：TWSE／TPEx 同時顯示買賣超張數與官方買賣超金額；金額缺值不以股價×張數估算，張數與金額日期不同時也不混用。
- **TWSE 籌碼韌性**：日期指定報表優先、verified-session fallback、JSON/BOM 容錯與 retry；上游失敗時保留 last-known-good。
- **TPEx 發行股數**：若主檔沒有直接發行股數，只有在官方實收資本額與普通股面額足以安全計算時才補值，並標記 `calculated_official_fields` 與來源。
- **股利歷史**：Yahoo dividend event 只作 reference backfill；官方 TWSE／TPEx／MOPS 優先。跨來源優先以除息日辨識同一筆，避免把同年多次配息錯合併。
- **ETF 驗證**：正規化臺/台、HTML entity、法律全名與 MSCI 標記差異；主動 ETF 官方「不適用」追蹤指數不再和績效比較基準形成假 conflict。
- **PWA**：同源靜態 JS/CSS/SVG/圖片/JSON 可由 precache cache-first；頁面 navigation 與 live data 維持 network-first。
- **GitHub Actions**：checkout/setup-python 使用 Node 24 相容 major；Cloudflare secrets 未設定時明確 warning + skip，不再製造永久紅燈，也不會假稱 worker 已部署。

## 覆蓋舊 repository

解壓 ZIP 後，把 ZIP 裡的所有根目錄內容直接覆蓋本機 `market-event-radar`，不要再多包一層資料夾。覆蓋完成後執行：

```text
CLEAN-REPO.cmd
```

它會移除 v11.4.36～v11.4.39 已淘汰的 verifier/test helper、舊 deletion manifest 與意外巢狀 repository，不會刪除 production scripts。之後使用 GitHub Desktop Commit / Push。

建議 commit：`market-event-radar-v11.4.40-data-integrity`

完整修正與驗收條件見 `docs/V11.4.40.md`、`docs/V11.4.40-release-audit.md`、`VALIDATION.txt`。

資料僅供市場觀察，不構成投資建議。無法驗證的值維持缺值／warning，不得偽造成正式或即時資料。
