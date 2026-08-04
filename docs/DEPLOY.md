# 部署

1. 將 `market-event-radar` 內全部檔案覆蓋原 GitHub 專案根目錄。
2. 使用 GitHub Desktop 提交並推送到 `main`。
3. GitHub Pages 設為 `Deploy from a branch`、`main`、`/(root)`。
4. 到 Actions 手動執行六個更新工作一次。
5. 事件工作第一次建立比對基準，第二次後才標記真正的新公布日期。
6. 若舊畫面仍存在，重新整理兩次或清除該網站快取。


## v11.4.2 首次上傳後

1. 手動執行 `Update v11.4.2 finance news`，確認 `live-news` 不再是 0 則。
2. 手動執行 `Update v11.4.2 assets and audit`，第一次會回補最近 60 個月月營收。
3. 股利歷史採每次 120 家分批回補；`data/asset-history-state.json` 會記錄進度。
4. 不要刪除 `live-news` 與 `live-assets` 分支，下一次排程會從最後成功資料繼續合併。
