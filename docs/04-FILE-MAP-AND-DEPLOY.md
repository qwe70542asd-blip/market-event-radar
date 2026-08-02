# 檔案整理與之後上傳規則

## 唯一修改來源

只使用完整包：`market-event-radar-v11.0.0-complete.zip`

以下舊檔不再使用：

- `market-event-radar-v10.6.1-integrated.zip`
- `market-event-radar-v10.6.2-cache-fix.zip`
- `market-event-radar-v10.7.0-checked.zip`
- `乾淨重裝說明-v10-6-0.txt`
- `交付前自我檢查-v10-6-0.txt`
- `scripts/__pycache__/`

## 主要檔案責任

| 路徑 | 用途 | 目前注意事項 |
|---|---|---|
| `.github/workflows/update-live-data.yml` | 市場、公告、事件與主檔更新 | 與新聞排程分開驗證 |
| `.github/workflows/update-news.yml` | 獨立新聞抓取、分類、AI 可選增強與發布 | 失敗不阻擋市場／公告 |
| `.github/workflows/update-tw-market.yml` | 台股行情、當沖與融資券更新 | 交易時段每 5 分鐘檢查 |
| `assets/data-source.js` | `live-data`、main 與 seed 的讀取優先順序 | `live-data` 使用根目錄；本機與 main 保留 `data/` 目錄 |
| `assets/market-ticker.js` | 指數與 ETF 行情 | 需驗證 30 秒檢查與缺值顯示 |
| `assets/news-core.js` | 共用新聞載入 | 需驗證空 JSON 與備援合併 |
| `assets/news-ui.js` | 首頁新聞顯示 | 需驗證輪播與台灣時間 |
| `assets/news-page.js` | 完整新聞頁 | 需驗證筆數、時間與連結 |
| `assets/institutional.js` | 法人頁 | 需驗證最近交易日與排行 |
| `assets/crypto-live.js` | 幣圈排行與串流 | 需驗證局部更新、不跳動 |
| `assets/app.js` | 首頁事件、篩選、時間與偏好 | 舊偏好鍵僅用於一次性讀取遷移 |
| `assets/asset-detail.js` | 個股／ETF 分流、籌碼、成分、配息與新聞 | 缺授權資料時顯示限制，不填假值 |
| `service-worker.js` | 快取策略 | 版本更動時必須同步更新 |
| `assets/sw-register.js` | 新 Service Worker 接管 | 與快取版本必須一致 |
| `data/*.json` | 安裝包資料／最近資料 | 不能代替線上更新成功證據 |
| `data/*-seed.js` | JSON 失敗時的離線備援 | 必须标示 seed，不冒充即時資料 |
| `scripts/update_tw_chips.py` | 當沖、融資與融券官方資料 | 單一交易所失敗時保留前次成功值 |
| `scripts/*.py` | 各類資料抓取與產生 | metadata 版本統一為 v11.0.0 |

## 上傳 GitHub 前

1. 不要把外層資料夾一起上傳；GitHub 根目錄要直接看到 `index.html`、`assets`、`data`、`scripts` 與 `.github`。
2. 不要混入任何舊壓縮包或舊版說明。
3. 提交後先執行 T01，不要直接用頁面是否有卡片判斷資料正常。
4. T01 失敗時，只處理 Actions 錯誤；不要同時改新聞、行情和字體。

## GitHub 提交說明

整理基準第一次提交可使用：

```text
v11.0.0：整合 live-data 路徑、完整首次更新與首頁區塊排序
```

後續每次只提交一個問題，例如：

```text
fix T01：建立 live-data 並修正自動更新
fix T03：修正新聞空資料載入
fix T04：修正行情缺值與更新狀態
```

這樣若某次修改出錯，可以明確知道是哪一項，不會再出現版本混用。
