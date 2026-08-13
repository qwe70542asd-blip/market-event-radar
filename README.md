# 市場事件雷達 v11.4.43

以事件月曆為核心，整合台股行情、全球市場、財經新聞、法人籌碼、股票／ETF 資料與個人投資組合的靜態 PWA。

## v11.4.43：正確性強化與來源健康

這版針對 v11.4.40 上線後的 live audit，優先修「錯資料被當成正常」與「來源降級卻看起來健康」兩類問題。

- **TPEx 公司日期**：Gregorian／ROC 日期正規化；成立日晚於掛牌日或未來日期會被拒絕，且 stock-basics 發布前有 fail-closed 驗證。
- **TPEx 股利計畫**：依 live diagnostic 實際欄位，支援歷史 header `股東會日期配盈餘/待彌補虧損(元)` 中的 ROC 日期，不再把整欄直接當成金額排除。
- **當沖／法人市場摘要**：TWSE 由官方 TWTB4U 精確加總當沖股數與買賣金額；TPEx 法人金額 parser 擴充中英文 schema。缺資料仍保持 `—`，不做張數×股價推估。
- **Data Verification**：不同或未知財報期間的 ROE／EPS／財務比率不再誤標 conflict；PE／PB／殖利率等 point-in-time 指標仍做跨來源比對。
- **個股頁可信度**：每個指標改讀自己的 verification status，不再受整組 metrics 的 conflict 污染。
- **歷史股利韌性**：MOPS 大規模失敗時短暫開 circuit breaker；錯誤只保留摘要樣本，官方當期資料與 Yahoo reference history 繼續可用。
- **新聞來源健康**：direct source 403 + history fallback 會標記 degraded/partial，不再顯示 health=ok。
- **PWA**：network-first 遇 HTTP 4xx/5xx 也會使用已存在的 cache fallback。
- **GitHub Actions**：diagnostic artifact 改用 Node-24-compatible `actions/upload-artifact@v7`。

## 覆蓋舊 repository

解壓 ZIP 後，把 ZIP 裡的所有根目錄內容直接覆蓋本機 `market-event-radar`，不要再多包一層資料夾。覆蓋完成後執行：

```text
CLEAN-REPO.cmd
```

它會移除 v11.4.36～v11.4.40 已淘汰的 verifier/test helper、舊 deletion manifest、舊 apply helper 與意外巢狀 repository，不會刪除 production scripts。之後使用 GitHub Desktop Commit / Push。

建議 commit：`market-event-radar-v11.4.43-correctness-hardening`

完整修正與驗收條件見 `docs/V11.4.43.md`、`docs/V11.4.43-release-audit.md`、`VALIDATION.txt`。

資料僅供市場觀察，不構成投資建議。無法驗證的值維持缺值／warning，不得偽造成正式或即時資料。
