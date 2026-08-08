# 市場事件雷達 v11.4.32

以雙模式事件月曆為核心，整合台股行情、六大指數 K 線、多來源財經新聞、法人籌碼、完整台股／ETF 主檔與個人投資組合的靜態 PWA。

## v11.4.32 重點

這版是 **live state migration + 日期追蹤完整性 + 手機執行期強化版**。除了修畫面，也處理 v11.4.31 實際部署後才暴露的舊資料污染與 workflow 問題。

- **BEA 日期追蹤重做**：PCE、GDP、貿易收支等週期事件改用「系列＋參考期間」tracking key，避免不同月份互相覆蓋造成假改期；同時修正 BEA 表格 title 被 `July 2026` 截斷，以及 GDP Third Estimate 被季度文字中的 `2nd` 誤判成 Second Estimate。
- **BLS 官方 fallback 修正**：ICS 失敗時先讀各發布項目的官方 schedule table，再退回年度頁；修正 `Reference Month | Release Date | Release Time` 表格因欄位分隔而完全解析不到的問題。
- **TWSE 歷史除權息修正**：改用官方 `strDate` / `endDate` 區間查詢；支援 2026 年後的 `權/息`、`權值+息值` 等新欄位，避免純除息被誤標成除權息。
- **事件 archive 不再被每日 snapshot 洗掉**：TPEx 歷史除權息與 TWSE/TPEx 每日重大訊息改成增量保留；舊已驗證事件會保留，未來同 tracking key 真正改期時才由新資料取代。
- **canonical event 去重更精確**：同日 manual/official PCE、GDP 等合併，官方來源優先；股利「方案決議／發放／除權／除息」各自保留，不再因同股票同日期誤合併。
- **台股 live migration**：舊的週末／未來成交歷史先清掉，再以官方交易日決定 `trading_date`；選定交易日後再次裁掉所有較新的殘留 session，解決舊 `2026-08-08` 假交易日阻斷發布。
- **tw-chips schema migration**：舊 `twse:2330` / `tpex:xxxx` key 轉成純代碼；移除週末／未來日期與舊 `day_trading` 結構，統一成 `symbol-keyed-v2`。
- **TPEx 股利 parser 與來源健康度**：補齊官方欄位別名；來源明明有 rows 但解析為 0 時改報 warning，不再假綠燈。
- **首頁第三方 K 線不再阻塞啟動**：Lightweight Charts 改成非阻擋載入；CDN 慢或失敗時首頁仍先啟動並使用 SVG fallback，成功後再升級互動圖。
- **手機版 compact**：日期公告、月曆日彈窗與操作按鈕縮成手機專用密度；移除市場事件彈窗重複統計，並放大實際 touch target。
- **大型 JSON 不再塞 persistent web storage**：只保留小型市場 snapshot 的 last-good 持久化，大型事件／K 線等資料只做記憶體快取，並清掉舊版大型 cache key。
- **repository / CI migration**：新增 `CLEAN-REPO.cmd` 與 layout guard，清除曾誤追蹤在 `scripts/` 下的完整專案副本；release verification 與資料 workflow 更新為 v11.4.32。

## 覆蓋舊 repository 時一定要做

單純把 ZIP 解壓覆蓋 **不會刪除 Git 已追蹤的舊 `scripts/...` 巢狀副本**。覆蓋完成後請先執行根目錄：

```text
CLEAN-REPO.cmd
```

再到 GitHub Desktop 確認有大量舊 `scripts/assets`、`scripts/data`、`scripts/scripts` 等刪除項目，和本版修改一起 Commit / Push。

完整修正與部署檢查見 `docs/V11.4.32.md`、`docs/V11.4.32-release-audit.md` 與 `VALIDATION.txt`。

資料僅供市場觀察，不構成投資建議。所有市場與事件資料都應保留來源、時間與狀態；無法驗證的資料不得偽造成即時或正式值。
