from pathlib import Path
import json,re,unittest
ROOT=Path(__file__).resolve().parents[1]

class StaticTests(unittest.TestCase):
 def read(self,path):return (ROOT/path).read_text(encoding="utf-8")
 def test_required_tree(self):
  for path in [".github/workflows","assets","data","docs","scripts","tests","index.html","news.html","asset.html","service-worker.js"]:self.assertTrue((ROOT/path).exists(),path)
 def test_version(self):
  self.assertEqual(json.loads(self.read("VERSION.json"))["baseline_version"],"11.4.3")
 def test_ascii_filenames(self):
  for path in ROOT.rglob("*"):self.assertTrue(all(ord(c)<128 for c in path.name),path)
 def test_no_audio(self):
  self.assertFalse(any(p.suffix.lower() in {".m4a",".mp3",".wav"} for p in ROOT.rglob("*")))
 def test_home_market_focus(self):
  html=self.read("index.html");self.assertIn("今日市場重點",html);self.assertNotIn("虛擬貨幣即時排行",html)
 def test_calendar_grouped(self):
  js=self.read("assets/home.js")
  for x in ("重大事件","公司資訊","除權息","dividendTable","localKey"):self.assertIn(x,js)
 def test_global_market_set(self):
  script=self.read("scripts/update_market_snapshot.py")
  for x in ("^KS11","^KQ11","^VIX","^TNX","DX-Y.NYB","TWD=X","KRW=X"):self.assertIn(x,script)
  self.assertNotIn('(\"NVDA\", \"NVIDIA\"',script)
 def test_etf_whitelist(self):
  script=self.read("scripts/update_tw_market.py")
  for x in ("TWSE_FUNDS","TPEX_FUNDS",'return "other"'):self.assertIn(x,script)
 def test_stock_etf_split(self):
  html=self.read("asset.html");js=self.read("assets/asset.js")
  self.assertNotIn("券商分點",html)
  for x in ("fundSection","holdingsSection","chartSection","const isEtf","fetchTwseHistory","fetchTpexHistory"):self.assertIn(x,html+js)
 def test_history_pipeline_preserved(self):
  script=self.read("scripts/update_assets.py")
  for x in ("HISTORY_MONTHS = 60","MOPS_REVENUE_ARCHIVES","fetch_mops_dividend_history","asset-history-state.json"):self.assertIn(x,script)
 def test_news_config_has_five_publishers(self):
  cfg=json.loads(self.read("data/news-channels.json"));ids={x["id"] for x in cfg["media"]}
  self.assertEqual(ids,{"cna","moneydj","cnyes","udn","ltn"})
 def test_cna_uses_direct_rss(self):
  cfg=json.loads(self.read("data/news-channels.json"));cna=next(x for x in cfg["media"] if x["id"]=="cna")
  self.assertTrue(all("feedburner.com/rsscna" in x for x in cna["urls"]))
  self.assertFalse(any("news.google.com" in x for x in cna["urls"]))
 def test_media_sources_are_direct(self):
  cfg=json.loads(self.read("data/news-channels.json"))
  urls=[u for c in cfg["media"] for u in c["urls"]]
  self.assertFalse(any("news.google.com" in u for u in urls))
 def test_separate_data_files(self):
  for name in ["news-cna","news-moneydj","news-cnyes","news-udn","news-ltn","official-market-notices","company-disclosures","monthly-revenue","dividend-history"]:
   self.assertTrue((ROOT/f"data/{name}.json").exists());self.assertTrue((ROOT/f"data/{name}-seed.js").exists())
 def test_separate_live_branches(self):
  shared=self.read("assets/shared.js")
  for branch in ("live-news-cna","live-news-moneydj","live-news-cnyes","live-news-udn","live-news-ltn","live-official-notices","live-company-disclosures","live-monthly-revenue","live-dividend-history"):self.assertIn(branch,shared)
 def test_load_news_channels(self):
  shared=self.read("assets/shared.js")
  for x in ("NEWS_FILES","loadNewsChannels","Promise.all","channel_kind"):self.assertIn(x,shared)
 def test_consumers_use_multi_source(self):
  for f in ("assets/home.js","assets/news.js","assets/asset.js","assets/event.js","assets/date-alerts.js"):self.assertIn("loadNewsChannels",self.read(f),f)
 def test_news_page_blocks(self):
  html=self.read("news.html")
  for x in ("獨立資料來源","重大市場資訊","官方市場公告","個股重大訊息","publisherBlocks","全部媒體新聞查詢"):self.assertIn(x,html)
 def test_news_source_status(self):
  js=self.read("assets/news.js")
  for x in ("sourceStatus","publisherBlocks","sourceFilters","獨立來源"):self.assertIn(x,js)
 def test_official_structured_sources(self):
  official=self.read("scripts/update_official_notices.py");company=self.read("scripts/update_company_disclosures.py")
  self.assertIn("/v1/news/newsList",official);self.assertIn("t187ap04_L",company);self.assertIn("t187ap04_O",company)
 def test_independent_workflows(self):
  expected=["update-news-cna.yml","update-news-moneydj.yml","update-news-cnyes.yml","update-news-udn.yml","update-news-ltn.yml","update-official-notices.yml","update-company-disclosures.yml","update-monthly-revenue.yml","update-dividend-history.yml"]
  for name in expected:self.assertTrue((ROOT/".github/workflows"/name).exists(),name)
  self.assertFalse((ROOT/".github/workflows/update-news.yml").exists())
 def test_workflows_publish_unique_branches(self):
  texts="\n".join(self.read(p.relative_to(ROOT)) for p in (ROOT/".github/workflows").glob("update-news-*.yml"))
  for branch in ("live-news-cna","live-news-moneydj","live-news-cnyes","live-news-udn","live-news-ltn"):self.assertIn(branch,texts)
 def test_service_worker_cache(self):
  sw=self.read("service-worker.js");self.assertIn("market-event-radar-v11-4-3",sw)
  for seed in ("news-cna-seed.js","news-moneydj-seed.js","company-disclosures-seed.js","monthly-revenue-seed.js","dividend-history-seed.js"):self.assertIn(seed,sw)
 def test_all_pages_current_version(self):
  for p in ROOT.glob("*.html"):self.assertNotIn("v11.4.2",p.read_text(encoding="utf-8"),p.name)

 def test_history_channels_are_isolated(self):
  shared=self.read("assets/shared.js"); asset=self.read("assets/asset.js"); updater=self.read("scripts/update_assets.py")
  for x in ("live-monthly-revenue","live-dividend-history"):self.assertIn(x,shared)
  for x in ("monthly-revenue.json","dividend-history.json"):self.assertIn(x,asset)
  self.assertIn("EMBEDDED_HISTORY_BACKFILL = False",updater)
  for name in ("update-monthly-revenue.yml","update-dividend-history.yml"):self.assertTrue((ROOT/".github/workflows"/name).exists())

 def test_dividend_cursor_does_not_block(self):
  script=self.read("scripts/update_dividend_history.py")
  for x in ("retry_symbols","cursor + len(new_targets)","ThreadPoolExecutor(max_workers=2)"):self.assertIn(x,script)

 def test_revenue_small_batches(self):
  script=self.read("scripts/update_monthly_revenue.py")
  for x in ("BATCH_MONTHS = 4","ThreadPoolExecutor(max_workers=2)","month_cursor"):self.assertIn(x,script)

if __name__=="__main__":unittest.main()
