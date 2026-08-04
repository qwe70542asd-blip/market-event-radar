from pathlib import Path
import json,unittest
ROOT=Path(__file__).resolve().parents[1]

class StaticTests(unittest.TestCase):
 def test_required_tree(self):
  for path in [".github/workflows","assets","data","docs","scripts","tests","index.html","portfolio.html","tw-market.html","news.html","institutional.html","asset.html","coverage.html","service-worker.js"]:
   self.assertTrue((ROOT/path).exists(),path)
 def test_version(self):
  self.assertEqual(json.loads((ROOT/"VERSION.json").read_text(encoding="utf-8"))["baseline_version"],"11.4.0")
 def test_ascii_filenames(self):
  for path in ROOT.rglob("*"):
   self.assertTrue(all(ord(char)<128 for char in path.name),f"non ASCII filename: {path}")
 def test_home_replaces_crypto(self):
  html=(ROOT/"index.html").read_text(encoding="utf-8")
  self.assertIn("今日市場重點",html);self.assertNotIn("虛擬貨幣即時排行",html);self.assertNotIn("工作",html)
 def test_calendar_is_grouped(self):
  js=(ROOT/"assets/home.js").read_text(encoding="utf-8")
  for text in ("重大事件","公司資訊","除權息","day-summary","dividendTable","localKey"):
   self.assertIn(text,js)
 def test_news_is_clean_and_classified(self):
  script=(ROOT/"scripts/update_news.py").read_text(encoding="utf-8")
  for text in ("article_url","clean_text","ai_category","market_direction","affected_markets","extract_key_facts","original_text"):
   self.assertIn(text,script)
 def test_stage2_news_layout(self):
  html=(ROOT/"news.html").read_text(encoding="utf-8")
  js=(ROOT/"assets/news.js").read_text(encoding="utf-8")
  for text in ("重大市場資訊","個股重要公告","一般財經新聞","companyNotices"):
   self.assertIn(text,html)
  for text in ("company-notice-card","notice-facts","notice-full","item.is_major===true&&!item.company"):
   self.assertIn(text,js)
 def test_market_rankings(self):
  html=(ROOT/"tw-market.html").read_text(encoding="utf-8")
  for text in ("今日個股漲幅前 15 名","今日個股跌幅前 15 名","今日 ETF 漲幅前 15 名","今日 ETF 跌幅前 15 名","成交金額"):
   self.assertIn(text,html)
 def test_institutional_search_and_hot_lists(self):
  html=(ROOT/"institutional.html").read_text(encoding="utf-8")
  js=(ROOT/"assets/institutional.js").read_text(encoding="utf-8")
  for text in ("搜尋單一標的籌碼","熱門個股前 10 名","熱門 ETF 前 10 名","當沖","融資","融券"):
   self.assertIn(text,html)
  for text in ("chipSuggestions","selectItem","最近五日趨勢"):
   self.assertIn(text,js)
 def test_stage1_global_market(self):
  script=(ROOT/"scripts/update_market_snapshot.py").read_text(encoding="utf-8")
  for symbol in ("^KS11","^KQ11","^VIX","^TNX","DX-Y.NYB","TWD=X","KRW=X"):
   self.assertIn(symbol,script)
  self.assertNotIn('(\"NVDA\", \"NVIDIA\"',script)
  seed=json.loads((ROOT/"data/market-snapshot.json").read_text(encoding="utf-8"))
  symbols={row.get("symbol") for row in seed.get("items",[])}
  self.assertNotIn("NVDA",symbols);self.assertIn("^KS11",symbols);self.assertIn("^VIX",symbols)
 def test_stage1_etf_whitelist(self):
  script=(ROOT/"scripts/update_tw_market.py").read_text(encoding="utf-8")
  self.assertIn("TWSE_FUNDS",script);self.assertIn("TPEX_FUNDS",script);self.assertIn('return "other"',script)
  self.assertNotIn("len(s)>4",script)
  market_js=(ROOT/"assets/tw-market.js").read_text(encoding="utf-8")
  institutional_js=(ROOT/"assets/institutional.js").read_text(encoding="utf-8")
  self.assertIn('item.asset_class===assetClass',market_js)
  self.assertIn('item.asset_class==="etf"',institutional_js)
 def test_stage1_missing_values(self):
  shared=(ROOT/"assets/shared.js").read_text(encoding="utf-8")
  self.assertIn("v===null||v===undefined",shared)
  self.assertIn('typeof v==="string"&&!v.trim()',shared)
 def test_stage1_news_scope_and_titles(self):
  script=(ROOT/"scripts/update_news.py").read_text(encoding="utf-8")
  for text in ("GENERIC_TITLE_RE","rewrite_company_title","resolve_url","company_announcement","scope == \"market\" and impact == \"high\""):
   self.assertIn(text,script)
  news_js=(ROOT/"assets/news.js").read_text(encoding="utf-8")
  self.assertIn('item.is_major===true&&!item.company',news_js)
 def test_stage1_calendar_local_date(self):
  updater=(ROOT/"scripts/update_events.py").read_text(encoding="utf-8")
  home=(ROOT/"assets/home.js").read_text(encoding="utf-8")
  self.assertIn('"local_date": start.astimezone(TAIPEI).date().isoformat()',updater)
  self.assertIn("eventDateKey",home);self.assertIn("eventIdentity",home)

 def test_stage3_event_news_linking(self):
  shared=(ROOT/"assets/shared.js").read_text(encoding="utf-8")
  home=(ROOT/"assets/home.js").read_text(encoding="utf-8")
  event=(ROOT/"assets/event.js").read_text(encoding="utf-8")
  event_html=(ROOT/"event.html").read_text(encoding="utf-8")
  for text in ("relatedNews","EVENT_ALIASES","windowDays"):
   self.assertIn(text,shared)
  self.assertIn("event-related-news",home)
  self.assertIn("related-news-grid",event)
  self.assertIn("data/news-seed.js?v=11.4.0",event_html)

 def test_stage3_official_financial_pipeline(self):
  updater=(ROOT/"scripts/update_assets.py").read_text(encoding="utf-8")
  for text in ("BWIBBU_ALL","tpex_mainboard_peratio_analysis","t187ap14_L","mopsfin_t187ap14_O","financial_endpoint","merge_financial","ThreadPoolExecutor","[:12]"):
   self.assertIn(text,updater)
  asset_html=(ROOT/"asset.html").read_text(encoding="utf-8")
  asset_js=(ROOT/"assets/asset.js").read_text(encoding="utf-8")
  for text in ("最近 12 期財務資料","financialRows","metricUpdated"):
   self.assertIn(text,asset_html)
  for text in ("尚未公告","不適用","資料暫時無法取得","net_margin","current_ratio"):
   self.assertIn(text,asset_js)

 def test_stage3_news_analysis(self):
  updater=(ROOT/"scripts/update_news.py").read_text(encoding="utf-8")
  news_js=(ROOT/"assets/news.js").read_text(encoding="utf-8")
  for text in ("importance_score","why_it_matters","event_terms","infer_symbols","build_asset_alias_map"):
   self.assertIn(text,updater)
  for text in ("why-it-matters","重要度","市場判讀"):
   self.assertIn(text,news_js)

 def test_stage3_hot_score_and_final_cache(self):
  inst=(ROOT/"assets/institutional.js").read_text(encoding="utf-8")
  html=(ROOT/"institutional.html").read_text(encoding="utf-8")
  sw=(ROOT/"service-worker.js").read_text(encoding="utf-8")
  self.assertIn("hot-score",inst)
  self.assertIn("熱門分數",html)
  self.assertIn("market-event-radar-v11-4-0",sw)

if __name__=="__main__":unittest.main()
