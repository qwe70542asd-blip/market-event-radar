# 市場事件雷達 v11.4.55

以事件月曆為核心，整合台股行情、六大指數、重大財經資訊、法人籌碼、股票／ETF 資料與個人投資組合的靜態 PWA。

## v11.4.55：手機首頁改版／事件月曆清晰化／防回歸

這版是 **full replacement**，以 v11.4.54 為母版，保留既有資料更新、行情防呆、法人日期驗證、六大指數 K 線、新聞、ETF／個股、投資組合與 Cloudflare Worker；本次只增加首頁決策資訊並修正手機重複導覽。

- 手機不再動態注入第二組 01–04 快速導覽；首頁原有快速導覽改成頁面內元件，不會固定遮住資產、月曆或 K 線。
- App 安裝按鈕只有在 Android／桌面瀏覽器真的觸發可安裝事件時顯示；iOS 顯示「加入主畫面」。
- 新增「市場上漲熱度」0–100，直接以全市場上漲家數占比呈現，並列出上漲／下跌／平盤家數。
- 新增「今日風險」低／中／高，依市場廣度、法人方向、量能與高影響事件判斷；事件或行情未完整時維持「資料同步中」。
- 新增「今日產業動能」強勢／弱勢 TOP 3，以產業成分股漲跌幅中位數排序，明確標示不等同資金淨流入。
- 事件月曆不再使用手機上難辨識的彩色橫線，改為「顏色圓點 + 件數」：重大事件、經濟／央行、公司資訊、股利／除權息。
- 手機版保留月曆操作說明；點日期後以底部抽屜顯示明細，先列出高影響、經濟／央行與公司資訊件數。
- 新增固定 regression tests，檢查重複 ID、重複 script/style、第二組 quick nav、月曆橫線回歸、手機 bottom sheet 與新儀表板 live rerender。

## 乾淨替換既有 repository

1. GitHub Desktop 先 **Fetch/Pull** 最新 `main`。
2. 打開本機 `market-event-radar` repository 資料夾。
3. **保留隱藏的 `.git` 資料夾**；刪除其餘舊專案檔案與資料夾。
4. 解壓 `market-event-radar-v11.4.55-full-replace.zip`，把 ZIP **裡面的所有內容**直接放到 repository root。不要多包一層資料夾。
5. 確認 `index.html`、`.github`、`assets`、`data`、`scripts` 都直接位於 repository root。
6. 執行一次 `CLEAN-REPO.cmd`。正常應顯示 `repository layout clean for v11.4.55` 或完成清理。
7. GitHub Desktop Commit：`market-event-radar-v11.4.55-full-replace`，再 Push。
8. GitHub Actions 至少確認：
   - `Verify v11.4.55 stable app release` 綠燈
   - `Update v11.4.55 event calendar and announced dates` 綠燈
   - `Deploy v11.4.55 live market worker` 綠燈

## Cloudflare

不需要重建既有設定。仍使用：

- Secret `CLOUDFLARE_API_TOKEN`
- Secret `CLOUDFLARE_ACCOUNT_ID`
- Variable `CLOUDFLARE_KV_NAMESPACE_ID`

不要建立 `LIVE_MARKET_ENDPOINT`。瀏覽器只接受固定 allowlist 的 `market-event-radar-live.qwe70542asd.workers.dev`，並在使用前驗證 `/health` 的 service、release version、schema、KV 與 rate-limit binding。

資料僅供市場觀察，不構成投資建議。無法驗證的值維持缺值／warning，不偽造成正式或即時資料。
