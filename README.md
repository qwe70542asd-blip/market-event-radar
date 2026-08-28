# 市場事件雷達 v11.4.52

以事件月曆為核心，整合台股行情、六大指數、重大財經資訊、法人籌碼、股票／ETF 資料與個人投資組合的靜態 PWA。

## v11.4.52：完整替換／資料完整性防回歸

這版是 **full replacement**，不是 overlay。目標是把先前覆蓋更新留下的舊檔問題一次清掉，並保留 v11.4.48 已完成的首頁 UX。

- 首頁左側 1×4 浮動導覽、日曆優先、固定高度重大資訊卡、浮動事件視窗關閉鍵全部保留。
- 新增 BOJ、ECB、BOE、台灣央行（CBC）與韓國央行（BOK）2026 官方貨幣政策日期，合計 36 筆；官方只給日期時保持「日期限定」，不猜測時刻。
- 首頁「焦點產業」先看最近 24 小時；沒有明確焦點才放寬至 72 小時，不再讓舊新聞長期霸榜。
- 普通重大新聞保留 24 小時、真正突發事件最高 48 小時、制度／央行／系統性／地緣政治重大資訊最高 72 小時。
- 「市場制度」判斷收緊：單純出現證交所／櫃買中心／金管會名稱不再自動升級，必須同時出現新制、修正、上路、規則調整等制度變更訊號；零股、撮合、交易時間等明確制度詞仍可直接判定。
- `publish_data_branch.sh` 改從 `VERSION.json` 讀取版本，不再把 live branch 的 channel marker 寫死成 v11.4.46。
- 舊 `DELETION-MANIFEST-v*.txt` 與舊 `assets/v*-overrides.css` 不包含在本套件；`cleanup_repo.py --check` 會阻止它們再次混入。

## 乾淨替換既有 repository

1. GitHub Desktop 先 **Fetch/Pull** 最新 `main`。
2. 打開本機 `market-event-radar` repository 資料夾。
3. **保留隱藏的 `.git` 資料夾**；刪除其餘舊專案檔案與資料夾。
4. 解壓 `market-event-radar-v11.4.52-full-replace.zip`，把 ZIP **裡面的所有內容**直接放到 repository root。不要多包一層資料夾。
5. 確認 `index.html`、`.github`、`assets`、`data`、`scripts` 都直接位於 repository root。
6. 執行一次 `CLEAN-REPO.cmd`。正常應顯示 `repository layout clean for v11.4.52` 或完成清理。
7. GitHub Desktop Commit：`market-event-radar-v11.4.52-full-replace`，再 Push。
8. GitHub Actions 至少確認：
   - `Verify v11.4.52 stable app release` 綠燈
   - `Update v11.4.52 event calendar and announced dates` 綠燈
   - `Deploy v11.4.52 live market worker` 綠燈

## Cloudflare

不需要重建既有設定。仍使用：

- Secret `CLOUDFLARE_API_TOKEN`
- Secret `CLOUDFLARE_ACCOUNT_ID`
- Variable `CLOUDFLARE_KV_NAMESPACE_ID`

不要建立 `LIVE_MARKET_ENDPOINT`。瀏覽器只接受固定 allowlist 的 `market-event-radar-live.qwe70542asd.workers.dev`，並在使用前驗證 `/health` 的 service、release version、schema、KV 與 rate-limit binding。

資料僅供市場觀察，不構成投資建議。無法驗證的值維持缺值／warning，不偽造成正式或即時資料。
