# v11.4.2 第三階段與最終整合

## 事件相關新聞

前端不修改官方事件內容，而是載入 `news.json` 後進行關聯：

- 股票代碼精準配對優先。
- 公司名稱與別名次之。
- CPI、PCE、JOLTS、FOMC、BOJ、非農、GDP、PMI 等事件別名補強。
- 文章發布時間限制在事件前後三天。
- 日曆卡片最多三則，事件詳情最多五則。

## 個股財務資料

`scripts/update_assets.py` 會使用官方來源更新公司主檔、估值、EPS、損益表及資產負債表。財報依期間合併並保留最近十二期。單一來源失敗不會清空既有資料。

## 熱門排行

熱門分數由成交金額、成交量、漲跌幅、外資買賣與當沖比例組成，當日第一名正規化為 100 分。排行只用於市場熱度觀察，不代表投資建議。

## 新聞影響分析

規則式分析輸出：

- `ai_category`
- `impact`
- `market_direction`
- `affected_markets`
- `confidence`
- `importance_score`
- `why_it_matters`
- `event_terms`
- `symbols`
