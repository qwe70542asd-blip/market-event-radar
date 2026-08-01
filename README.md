# 全球市場即時雷達 v6

公開網址：

```text
https://qwe70542asd-blip.github.io/market-event-radar/
```

這是一個以 **Asia/Taipei 台灣時間** 顯示的投資事件工作台，整合市場代理行情、財報、央行、經濟數據、科技活動與相關報導。

## v6 重點

- 移除容易出現紅色驚嘆號的 TradingView 大型跨國行情表。
- 只保留一條較輕量的市場代理跑馬燈：EWT、TSM ADR、SPY、QQQ、SOXX、EWJ、EWY、FEZ、USDJPY、US10Y、VIX。
- 預設顯示未來 7 天事件板，同一天多事件會並排顯示。
- 滑鼠停留或鍵盤聚焦事件，可快速查看影響與相關報導；點擊可開啟完整詳情。
- 新增台股／AI、利率／通膨、科技財報、日本／亞洲焦點模式。
- 新增 `Ctrl + K` 快速搜尋與動作選單，並支援 `/` 聚焦事件搜尋。
- 篩選、焦點與顯示模式會保存在瀏覽器中。
- 新增公開新聞 RSS 整合，GitHub Actions 每 4 小時更新相關報導。
- 事件來源失效時保留上一次成功資料，避免整頁空白。

## 為什麼原本有紅色驚嘆號

原本的大型 TradingView Market Quotes 元件包含 `INDEX:TAIEX`、`NASDAQ:SOX`、`TVC:NI225`、`KRX:KOSPI`、`FTSE:UKX`、`EURONEXT:PX1` 等商品。部分交易所或商品只允許在 TradingView 本站查看，不允許第三方網頁嵌入；錯誤發生在跨網域 iframe 內，外層網站無法可靠偵測或修復。

v6 不再使用這個大型元件，改用可公開顯示的 ETF、ADR、匯率與風險指標作為市場代理，因此不再留下大片空白或紅色驚嘆號。

## 自動更新

### 市場事件

`.github/workflows/update-events.yml` 每天約台灣時間 08:15 執行：

1. 下載 BLS 行事曆。
2. 讀取 BEA 發布時程。
3. 嘗試讀取 Nasdaq 財報行事曆。
4. 合併 `data/manual_events.json`。
5. 更新 `data/events.json` 與 `data/seed.js`。

### 相關報導

`.github/workflows/update-news.yml` 每 4 小時執行：

1. 讀取未來 35 天高／中影響事件。
2. 透過 Google News RSS 搜尋相關公開報導。
3. 每個事件保留最多 3 則，並去除重複網址。
4. 更新 `data/news.json` 與 `data/news-seed.js`。
5. 抓取失敗時保留上一次成功資料。

## 啟用 GitHub Pages

1. **Settings → Pages**。
2. Source 選 **Deploy from a branch**。
3. Branch 選 `main`，資料夾選 `/ (root)`。
4. 按 **Save**。

請確認 **Settings → Actions → General → Workflow permissions** 已選 `Read and write permissions`。

## 本機預覽

```bash
python -m http.server 8000
```

開啟：

```text
http://localhost:8000
```

## 免責聲明

本網站僅整理公開市場資訊，不構成投資建議。行情為市場代理或延遲資料，事件與報導也可能臨時調整；交易前請再次確認官方公告、交易所與券商報價。
