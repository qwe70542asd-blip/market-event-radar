window.__MARKET_NEWS_SEED__ = {
  metadata: {
    updated_at: "2026-08-02T12:00:00+08:00",
    timezone: "Asia/Taipei",
    item_count: 5,
    note: "內建可讀備援；自動排程成功後會與最新新聞合併。"
  },
  source: { name: "財經快訊備援", status: "cached", message: "顯示最近可直接開啟的原始文章" },
  sources: [
    { name: "經濟日報", status: "ok" },
    { name: "永豐金證券", status: "ok" },
    { name: "Reuters", status: "ok" },
    { name: "Federal Reserve", status: "ok" }
  ],
  items: [
    {
      id: "seed-20260802-udn", title: "8月2日五件財經大事搶先看", source: "經濟日報",
      source_group: "publisher", region: "TW", topic: "market", language: "zh-Hant",
      published_at: "2026-08-02T03:00:11+08:00", quality_score: 92, is_breaking: true,
      direct_link: "https://money.udn.com/money/story/5607/9665366?from=edn_previous_story"
    },
    {
      id: "seed-20260731-sinotrade", title: "八月關鍵時程：美股財報、台股法說與重要總經數據", source: "永豐金證券",
      source_group: "broker", region: "TW", topic: "market", language: "zh-Hant",
      published_at: "2026-07-31T16:00:00+08:00", quality_score: 90, is_breaking: false,
      direct_link: "https://www.sinotrade.com.tw/richclub/hotstock/%E5%85%AB%E6%9C%88%E6%8A%95%E8%B3%87%E4%BA%BA%E4%B8%8D%E5%8F%AF%E4%B8%8D%E7%9F%A5%E7%9A%84%E9%97%9C%E9%8D%B5%E6%99%82%E7%A8%8B-%E7%BE%8E%E8%82%A1SpaceX-NVDA%E8%B2%A1%E5%A0%B1%E6%8E%A5%E5%8A%9B-%E5%8F%B0%E8%82%A1%E6%B3%95%E8%AA%AA-%E7%AC%AC%E4%BA%8C%E5%AD%A3%E7%87%9F%E6%94%B6%E9%99%B8%E7%BA%8C%E7%99%BB%E5%A0%B4-%E8%82%A1%E5%B8%82%E8%A9%B1%E9%A1%8C-6a6c1fd668efc90ac5a239f3"
    },
    {
      id: "seed-20260731-reuters", title: "華爾街收高：亞馬遜財報緩解市場對 AI 支出的疑慮", source: "Reuters",
      source_group: "publisher", region: "US", topic: "market", language: "zh-Hant",
      published_at: "2026-08-01T05:30:00+08:00", quality_score: 94, is_breaking: true,
      direct_link: "https://www.reuters.com/business/nasdaq-100-leads-us-futures-higher-amazon-surge-offsets-apple-decline-2026-07-31/"
    },
    {
      id: "seed-20260729-fed", title: "聯準會維持政策利率在 3.50% 至 3.75%", source: "Federal Reserve",
      source_group: "official-central-bank", region: "US", topic: "policy", language: "zh-Hant",
      published_at: "2026-07-30T02:00:00+08:00", quality_score: 96, is_breaking: false,
      direct_link: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260729a.htm"
    },
    {
      id: "seed-20260802-ibd", title: "本週焦點：AMD、儲存與大型企業財報接力", source: "Investor's Business Daily",
      source_group: "publisher", region: "US", topic: "earnings", language: "zh-Hant",
      published_at: "2026-08-02T09:00:00+08:00", quality_score: 84, is_breaking: false,
      direct_link: "https://www.investors.com/market-trend/stock-market-today/dow-jones-futures-spacex-amd-sandisk-eli-lilly-earnings-loom/"
    }
  ]
};
