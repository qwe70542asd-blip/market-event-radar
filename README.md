# 市場事件雷達｜v11.0.0 完整整合版

這個資料夾是目前唯一應繼續修改的網站原始碼基準。

- 目前版本：`v11.0.0-complete-integration`

## v11.0.0 整合內容

- `tw-market.html`：上市／上櫃漲幅榜、跌幅榜與市場家數。
- 使用者可建立只存在瀏覽器的台股組合，股數與成本為選填。
- `.github/workflows/update-news.yml`：新聞改為完全獨立發布；公告失敗不再阻擋新聞。
- 新聞先由排程抓取、規則分類與去重；設定 `OPENAI_API_KEY` 後才啟用 AI 摘要、分類與同事件合併，AI 失敗仍照常發布。
- 虛擬貨幣分組只由暫停按鈕控制，不會因手機觸控或滑入狀態卡在 `1/5`。
- 首頁「最新官方公告」卡已移除，改為上市／上櫃當沖、融資與融券摘要。
- `asset.html` 會辨識一般個股或 ETF：個股顯示財報與籌碼；ETF 才顯示成分股、淨值與折溢價。
- 個股籌碼包含三大法人、當沖與融資券；券商分點沒有授權資料時只提供官方查詢入口，不填假排行。
- `.github/workflows/update-tw-market.yml`：台股行情與盤後籌碼資料獨立更新。
- `data/tw-market.json`：全市場股票與 ETF 行情；休市時保留最後交易日。
- 專案網址：`https://qwe70542asd-blip.github.io/market-event-radar/`
- 顯示時區：`Asia/Taipei`（台灣時間）
- 目前狀態：本機語法、資料結構與解析測試完成；首次上傳後仍需由 GitHub Actions 取得真實新聞、籌碼與全市場行情。
- 舊版 `v10.6.1`、`v10.6.2`、`v10.7.0` 壓縮包不再使用

## 先看哪裡

1. `docs/01-LATEST-REQUIREMENTS.md`：最新且唯一有效的完整需求。
2. `docs/02-KNOWN-ISSUES.md`：目前已確認的問題與證據。
3. `docs/03-TEST-ORDER.md`：一次只測一項的檢查順序。
4. `docs/04-FILE-MAP-AND-DEPLOY.md`：檔案用途與之後的 GitHub 上傳方式。
5. `docs/05-STATIC-VALIDATION.md`：本次整理包已完成與尚未完成的檢查。

## 目前最重要的原則

- 新聞與官方公告各自獨立；任何一邊失敗都不得發布空白檔案，也不得阻擋另一邊成功資料。
- 新聞相同標題只保留一列，其他來源合併為「另有 N 個來源」。
- 首次完整更新回補最近 20 天；其後超過 20 天才移除。
- 資料失敗時不得顯示假 `0.00%`、假 `+0.0 億` 或假的即時時間。
- 所有時間都要明確使用台灣時間。
- 未完成四市場證券主檔前，不得宣稱「所有股票完整收錄」。
- 上傳後先檢查完整資料流程，再依畫面逐項確認。

## 資料夾結構

```text
.
├── .github/workflows/       GitHub Actions 自動更新
├── assets/                  前端 JavaScript、CSS 與圖示
├── data/                    安裝包資料與離線備援
├── docs/                    最新規格、問題與測試文件
├── scripts/                 市場資料更新程式
├── index.html               首頁
├── tw-market.html           台股漲跌榜與本機自訂組合頁
├── news.html                財經新聞頁
├── institutional.html       法人籌碼頁
├── portfolio.html           投資組合頁
├── asset.html               個股／ETF／基金分析頁
├── event.html               事件詳情頁
├── service-worker.js        離線快取與更新控制
└── manifest.webmanifest     網站安裝資訊
```

## 注意

這個基準包的用途是避免版本再次混亂。它保留目前程式狀態與已知問題，不能因為語法檢查通過就當成線上資料已正常。正式上傳前，必須依 `docs/03-TEST-ORDER.md` 完成線上 Actions 與頁面實測。
