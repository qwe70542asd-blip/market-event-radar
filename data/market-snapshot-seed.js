window.__MARKET_SNAPSHOT_SEED__ = {
  "metadata": {
    "updated_at": "2026-07-31T14:00:00+08:00",
    "timezone": "Asia/Taipei",
    "version": "v10.4.5",
    "item_count": 16,
    "healthy_count": 1,
    "status": "seed",
    "display_policy": "delayed-or-last-close",
    "note": "Initial package seed. Run the market ticker workflow to fill all sources."
  },
  "sources": [],
  "items": [
    {
      "id": "TAIEX",
      "name": "台股加權",
      "kind": "index",
      "currency": "點",
      "region": "TW",
      "link": "https://www.twse.com.tw/zh/trading/historical/fmtqik.html",
      "value": 43119.75,
      "previous": 39933.3,
      "change": 3186.45,
      "change_percent": 7.9794,
      "as_of": "2026-07-31",
      "source": "TWSE 官方 OpenAPI",
      "source_url": "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK",
      "delay": "盤後",
      "status": "ok",
      "note": "安裝包初始值；執行 Action 後更新",
      "updated_at": "2026-07-31T14:00:00+08:00"
    }
  ]
};
