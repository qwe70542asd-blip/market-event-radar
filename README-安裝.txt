v11.4.53 一鍵覆蓋版

使用方式：
1. 把整個「market-event-radar-v11.4.53-one-click」資料夾解壓到你的 market-event-radar 專案根目錄裡。
2. 雙擊 ONE-CLICK-REPLACE-v11.4.53.cmd。
3. 安裝器會覆蓋新版檔案、更新首頁/Service Worker，並刪除所有舊版本殘留。
4. 完成後打開 GitHub Desktop，確認 Changes，Commit + Push。

會刪除：
- 舊版 DELETION-MANIFEST-v*.txt
- 舊版 VALIDATION-v*.txt
- 舊版 assets/v*-overrides.css
- 舊版 apply_v*.py / test_v*_*.py / verify_v*_live_sources.py
- 已列為 obsolete 的舊 workflow

不會刪除：
- .git
- 目前有效的 data/
- 目前有效的 workflows
- 你的 GitHub 設定與 Secrets
