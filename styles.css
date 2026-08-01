# 全球市場即時雷達（Global Market Radar）

公開網址預計為：

```text
https://qwe70542asd-blip.github.io/market-event-radar/
```

這是一個可部署到 GitHub Pages 的全球市場資訊首頁，使用 **Asia/Taipei 台灣時間** 顯示。

## 網站內容

- 台灣、美國、日本、韓國、歐洲主要市場報價
- 台灣加權、S&P 500、那斯達克、道瓊、費半、日經 225、TOPIX、KOSPI、KOSDAQ、DAX、FTSE 100、CAC 40
- 各市場代表性大型股報價與走勢
- 聯準會、歐洲央行、日本銀行、韓國銀行等央行事件
- CPI、非農、PPI、GDP、PCE、JOLTS 等經濟數據
- 重要科技公司財報、科技發表會與台股公告
- 高／中／低市場影響標示、倒數、搜尋、地區／類型篩選
- 清單與月曆兩種事件檢視

市場行情由 TradingView 公開嵌入元件呈現。不同交易所的資料授權不同，部分行情可能延遲；實際成交價請以交易所與券商為準。

## 每日自動更新事件

`.github/workflows/update-events.yml` 每天台灣時間約 **08:15** 執行：

1. 下載官方 BLS 行事曆。
2. 讀取 BEA 發布時程。
3. 嘗試讀取 Nasdaq 財報行事曆。
4. 合併 `data/manual_events.json`。
5. 更新 `data/events.json` 與 `data/seed.js`。
6. 自動提交更新，GitHub Pages 隨即發布。

若某個來源暫時失效，更新器會保留上一次成功資料。

## 啟用 GitHub Pages

1. 進入儲存庫的 **Settings → Pages**。
2. `Build and deployment` 的 Source 選 **Deploy from a branch**。
3. Branch 選 `main`，資料夾選 `/ (root)`。
4. 按 **Save**。
5. 等候數分鐘後開啟公開網址。

Actions 第一次執行前，請確認 **Settings → Actions → General → Workflow permissions** 已選 `Read and write permissions`。

## 本機預覽

```bash
python -m http.server 8000
```

開啟：

```text
http://localhost:8000
```

## 新增事件

編輯 `data/manual_events.json`。支援：

- `category`: `central-bank`, `macro`, `earnings`, `tech`, `taiwan`, `policy`
- `region`: `TW`, `US`, `JP`, `KR`, `EU`, `GLOBAL`
- `impact`: `high`, `medium`, `low`

## 免責聲明

本網站僅整理公開市場資訊，不構成投資建議。行情可能為延遲資料，事件日期也可能臨時調整；交易前請再次確認官方公告、交易所與券商報價。
