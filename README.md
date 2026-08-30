# 市場事件雷達 v11.4.58

## 完整整合版：資料健康、版本同步、記憶體／舊資料限流

這是 **Full Replacement** 完整覆蓋版。v11.4.58 保留既有首頁、台股排行、法人籌碼、K 線、新聞、個股／ETF、投資組合與 Cloudflare Worker，並把資料更新與顯示問題統一收斂到同一套健康檢查與 fail-closed 規則。


### v11.4.58 手機密度與月曆可讀性

- 手機首頁未設定投資組合時隱藏 6 個空白資產格，只保留簡化空狀態與「管理組合」。
- 手機首頁縮減台股狀態、今日重點、熱度與產業動能的垂直留白，重要數值維持可讀。
- 手機取消左側浮動快速列，使用既有底部導覽，釋放內容寬度。
- 月曆的地區／事件／影響三個常駐下拉改成單一「篩選」按鈕；點擊後開啟 bottom sheet，提供清除／套用。
- 月曆本月統計改成小型輔助文字，月曆更早進入第一屏。
- 重大事件／經濟央行／公司資訊 legend 與日期格 badge 放大；黃色提高對比。
- 既有 v11.4.57 的 bounded cache、分片載入、last-known-good TTL 與資料健康 fail-closed 規則全部保留。

### v11.4.58 主要修正

- Worker、`VERSION.json` 與 production readiness 改成同一版本來源，避免部署成功但 `/health` 還回舊版。
- 新增輕量 `channel-health.json`；資料狀態頁只讀健康摘要，不再一次下載所有大型歷史資料。
- 健康狀態明確區分 fresh / partial / degraded / stale / pending / failed / unavailable；waiting、pending、seeded 不再顯示為正常綠燈。
- ETF／Yahoo 詳細資料加入 per-item 過期偵測；檔案剛更新也不能掩蓋個別舊資料。
- 股利 MOPS circuit-open、籌碼不同日期、新聞 fallback 等會直接降級，不再「假正常」。
- 中央 verification 擴到行情、籌碼、事件、公司資料、ETF、股利、新聞與公告；完整交叉驗證每小時一次，輕量健康索引每 15 分鐘一次。
- 個股頁改成 **0–9 前綴 detail shards**：只下載目前代碼所在的一個小分片，不再同時載入完整 assets／籌碼／營收／股利／Yahoo／ETF／公司基本資料／verification 巨檔。
- 個股頁 HTML 移除舊版多餘 seed 檔，只保留行情、事件與聚合個股新聞的必要 fallback。
- 新聞採 20 天滾動保留，單來源與合併後瀏覽器記憶體都有上限；首頁／新聞頁不會因舊新聞長期累積而持續膨脹。
- 大型新聞與 verification 不再寫進瀏覽器 IndexedDB last-good，舊版本殘留也會清除。
- shard 在重新產生前會先還原上一份成功版本，並套用 catastrophic-shrink guard，避免破損批次把完整資料覆蓋成少量資料。
- Service Worker cache identity 更新到 v11.4.58，啟用新版時會清掉舊 cache。

### 安裝／覆蓋

1. GitHub Desktop 選擇 `market-event-radar`。
2. 按 **Show in Explorer**。
3. 解壓 `market-event-radar-v11.4.58-full-replace.zip`。
4. 將 ZIP 第一層所有檔案與資料夾直接覆蓋 repository root，不要多包一層資料夾。
5. 依 `DELETION-MANIFEST-v11.4.58.txt` 移除舊版 release-only 檔案。
6. Commit 建議：`market-event-radar-v11.4.58-full-replace`。
7. Push 後等待 **Verify stable app release** 與 Worker deploy 完成。

### 驗證

本地完整驗證為 **307 tests passed**。詳細結果見 `VALIDATION-v11.4.58.txt`。
