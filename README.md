# 市場事件雷達｜v10.8.0 排版整合測試版

這個資料夾是目前唯一應繼續修改的網站原始碼基準。

- 目前版本：`v10.8.0-layout-integrated`
- 專案網址：`https://qwe70542asd-blip.github.io/market-event-radar/`
- 顯示時區：`Asia/Taipei`（台灣時間）
- 目前狀態：完成首頁電腦版／手機版排版整合；資料更新問題仍依測試清單逐項處理
- 舊版 `v10.6.1`、`v10.6.2`、`v10.7.0` 壓縮包不再使用

## 先看哪裡

1. `docs/01-LATEST-REQUIREMENTS.md`：最新且唯一有效的完整需求。
2. `docs/02-KNOWN-ISSUES.md`：目前已確認的問題與證據。
3. `docs/03-TEST-ORDER.md`：一次只測一項的檢查順序。
4. `docs/04-FILE-MAP-AND-DEPLOY.md`：檔案用途與之後的 GitHub 上傳方式。
5. `docs/05-STATIC-VALIDATION.md`：本次整理包已完成與尚未完成的檢查。

## 目前最重要的原則

- 先修自動更新，再處理新聞、行情、法人等前端顯示。
- 資料失敗時不得顯示假 `0.00%`、假 `+0.0 億` 或假的即時時間。
- 所有時間都要明確使用台灣時間。
- 未完成四市場證券主檔前，不得宣稱「所有股票完整收錄」。
- 每次只修一個問題，通過對應測試後才進下一項。

## 資料夾結構

```text
.
├── .github/workflows/       GitHub Actions 自動更新
├── assets/                  前端 JavaScript、CSS 與圖示
├── data/                    安裝包資料與離線備援
├── docs/                    最新規格、問題與測試文件
├── scripts/                 市場資料更新程式
├── index.html               首頁
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
