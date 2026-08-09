# 市場事件雷達 v11.4.34

以雙模式事件月曆為核心，整合台股行情、六大指數 K 線、多來源財經新聞、法人籌碼、完整台股／ETF 主檔與個人投資組合的靜態 PWA。

## v11.4.34 重點

這版是 **成交歷史完整性 + TPEx 股利解析 + Stock Basics + 發版 CI 修正版**，專門處理 v11.4.32 部署後仍可確認的資料缺口。

- **成交歷史逐月回補**：不再用全體 row count 決定是否跳過後續月份，避免五月／七月這類整月缺口被誤判成 history complete。
- **成交額完整性 fail-closed**：TWSE 單市場 component 不再冒充完整台股總成交額；verified TWSE+TPEx quote sum 可優先採用，5／20／60 日均量只使用 complete total。
- **近期完整性判斷**：`volume_history_complete` 會檢查近期 session 的數量與跨度，不再因舊月份資料很多就顯示綠燈。
- **TPEx ETF fallback 分離**：TWSE ETF 名單成功不會阻止 TPEx 使用 last-known-good whitelist。
- **Stock Basics 產業欄位修正**：`industry`／`industry_name` 不再洩漏 `9103` 這類純數字舊值；strict validator 同步防堵。
- **TPEx 股利 parser 更新**：支援 `董事會擬議日期`、`董事會決議日期`、全形標點與更多官方欄位別名，解決來源有大量 rows 卻解析 0 件的問題。
- **歷史事件來源健康度**：合法空結果不再誤報 parser warning；非空來源解析 0 才 warning。BLS 多一層官方年度頁 fallback，若仍 403 就保留 warning／last-known-good。
- **更嚴格市場驗證**：檢查 `market_at`、session、最新 candle、台股 quote date、成交歷史週末／未來／重複 session 與 completeness claim。
- **Cloudflare deploy workflow 修正**：移除 job-level `secrets` 判斷；未設定 secrets 時安全跳過 optional edge deployment。
- **真正瀏覽器 CI**：Release verification 新增 Playwright Chromium runtime gate，實際要求首頁無 `pageerror`、月曆 42 格、標題初始化與雙模式可切換。
- **repository 清理**：`CLEAN-REPO.cmd` + `DELETION-MANIFEST-v11.4.34.txt` 用來把 GitHub 上仍追蹤的舊 `scripts/` 巢狀專案真正提交為 deletions。

## 覆蓋舊 repository 時一定要做

單純把 ZIP 解壓覆蓋 **不會刪除 Git 已追蹤的舊 `scripts/...` 巢狀副本**。覆蓋完成後請先執行根目錄：

```text
CLEAN-REPO.cmd
```

再到 GitHub Desktop 確認有大量舊 `scripts/assets`、`scripts/data`、`scripts/scripts` 等刪除項目，和本版修改一起 Commit / Push。

完整修正與部署檢查見 `docs/V11.4.34.md`、`docs/V11.4.34-release-audit.md` 與 `VALIDATION.txt`。

資料僅供市場觀察，不構成投資建議。所有市場與事件資料都應保留來源、時間與狀態；無法驗證的資料不得偽造成即時或正式值。
