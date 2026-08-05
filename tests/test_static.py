from pathlib import Path
import json,re,unittest
ROOT=Path(__file__).resolve().parents[1]

class StaticTests(unittest.TestCase):
 def read(self,path):return (ROOT/path).read_text(encoding="utf-8")
 def test_required_tree(self):
  for path in [".github/workflows","assets","data","docs","scripts","tests","index.html","news.html","asset.html","service-worker.js"]:self.assertTrue((ROOT/path).exists(),path)
 def test_version(self):
  self.assertEqual(json.loads(self.read("VERSION.json"))["baseline_version"],"11.4.17")
 def test_ascii_filenames(self):
  for path in ROOT.rglob("*"):self.assertTrue(all(ord(c)<128 for c in path.name),path)
 def test_no_audio(self):
  self.assertFalse(any(p.suffix.lower() in {".m4a",".mp3",".wav"} for p in ROOT.rglob("*")))
 def test_home_market_focus(self):
  html=self.read("index.html")
  for token in ("我的資產總覽","即時大盤資訊","balanced-summary-row","marketList"):self.assertIn(token,html)
  self.assertNotIn("虛擬貨幣即時排行",html)
 def test_calendar_grouped(self):
  html=self.read("index.html");js=self.read("assets/home.js")
  for token in ("市場事件日曆","股利股息日曆","marketCalendarFilters","dividendCalendarFilters","calendarModeSummary"):self.assertIn(token,html)
  for token in ("setCalendarMode","marketRelevant","dividendRelevant","dividendTable","localKey"):self.assertIn(token,js)
 def test_global_market_set(self):
  script=self.read("scripts/update_market_snapshot.py");home=self.read("assets/home.js")
  for x in ("^TWII","^KS11","^N225","^IXIC","^SOX","^GSPC","^KQ11","^VIX","^TNX","DX-Y.NYB","TWD=X","KRW=X"):self.assertIn(x,script)
  for x in ("parse_yahoo_candles","fetch_twse_taiex","candles","candle_source","data_status",'"range": "3mo"','"interval": "1d"'):self.assertIn(x,script)
  for x in ('marketKlineSymbols=["^TWII","^KS11","^N225","^IXIC","^SOX","^GSPC"]',"market-candle","近 ${candles.length||0} 個交易日"):self.assertIn(x,home)
  self.assertNotIn("^TWOII",script+home)
  self.assertNotIn('("NVDA", "NVIDIA"',script)
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
 def test_news_config_has_nine_publishers(self):
  cfg=json.loads(self.read("data/news-channels.json"));ids={x["id"] for x in cfg["media"]}
  self.assertEqual(ids,{"cna","moneydj","cnyes","udn","ltn","wealth","yahoo","technews","ctee","asia-risk"})
 def test_cna_uses_direct_rss(self):
  cfg=json.loads(self.read("data/news-channels.json"));cna=next(x for x in cfg["media"] if x["id"]=="cna")
  self.assertTrue(all("feedburner.com/rsscna" in x for x in cna["urls"]))
  self.assertFalse(any("news.google.com" in x for x in cna["urls"]))
 def test_media_sources_are_direct(self):
  cfg=json.loads(self.read("data/news-channels.json"))
  urls=[u for c in cfg["media"] for u in c["urls"]]
  self.assertTrue(any("news.google.com/rss/search" in u for u in urls))
  self.assertTrue(all("news.google.com" not in u for c in cfg["media"] if c["id"]!="asia-risk" for u in c["urls"]))
 def test_separate_data_files(self):
  for name in ["news-cna","news-moneydj","news-cnyes","news-udn","news-ltn","news-wealth","news-yahoo","news-technews","news-ctee","news-asia-risk","stock-news","official-market-notices","company-disclosures","monthly-revenue","dividend-history"]:
   self.assertTrue((ROOT/f"data/{name}.json").exists());self.assertTrue((ROOT/f"data/{name}-seed.js").exists())
 def test_separate_live_branches(self):
  shared=self.read("assets/shared.js")
  for branch in ("live-news-cna","live-news-moneydj","live-news-cnyes","live-news-udn","live-news-ltn","live-news-wealth","live-news-yahoo","live-news-technews","live-news-ctee","live-news-asia-risk","live-stock-news","live-official-notices","live-company-disclosures","live-monthly-revenue","live-dividend-history"):self.assertIn(branch,shared)
 def test_load_news_channels(self):
  shared=self.read("assets/shared.js")
  for x in ("NEWS_FILES","loadNewsChannels","Promise.all","channel_kind"):self.assertIn(x,shared)
 def test_consumers_use_multi_source(self):
  for f in ("assets/home.js","assets/news.js","assets/asset.js","assets/event.js"):self.assertIn("loadNewsChannels",self.read(f),f)
  self.assertIn('loadData("events.json"',self.read("assets/date-alerts.js"))
 def test_news_page_blocks(self):
  html=self.read("news.html")
  for x in ("精選重大資訊","最新財經新聞","官方市場公告","個股重大訊息","latestNewsRows","news-hero-layout","portal-news-grid"):self.assertIn(x,html)
  for x in ("獨立資料來源","publisherBlocks"):self.assertNotIn(x,html)
 def test_news_source_status(self):
  js=self.read("assets/news.js")
  for x in ("newsHealthNote","majorScore","portal-news-card","hero-lead"):self.assertIn(x,js)
  for x in ("sourceStatus","publisherBlocks","sourceFilters"):self.assertNotIn(x,js)
 def test_official_structured_sources(self):
  official=self.read("scripts/update_official_notices.py");company=self.read("scripts/update_company_disclosures.py")
  self.assertIn("/v1/news/newsList",official);self.assertIn("t187ap04_L",company);self.assertIn("t187ap04_O",company)
 def test_independent_workflows(self):
  expected=["update-news-cna.yml","update-news-moneydj.yml","update-news-cnyes.yml","update-news-udn.yml","update-news-ltn.yml","update-news-wealth.yml","update-news-yahoo.yml","update-news-technews.yml","update-news-ctee.yml","update-news-asia-risk.yml","update-stock-news.yml","update-official-notices.yml","update-company-disclosures.yml","update-monthly-revenue.yml","update-dividend-history.yml"]
  for name in expected:self.assertTrue((ROOT/".github/workflows"/name).exists(),name)
  self.assertFalse((ROOT/".github/workflows/update-news.yml").exists())
 def test_workflows_publish_unique_branches(self):
  texts="\n".join(self.read(p.relative_to(ROOT)) for p in (ROOT/".github/workflows").glob("update-news-*.yml"))
  for branch in ("live-news-cna","live-news-moneydj","live-news-cnyes","live-news-udn","live-news-ltn","live-news-wealth","live-news-yahoo","live-news-technews","live-news-ctee","live-news-asia-risk"):self.assertIn(branch,texts)
 def test_service_worker_cache(self):
  sw=self.read("service-worker.js");self.assertIn("market-event-radar-v11-4-17",sw)
  for seed in ("news-cna-seed.js","news-moneydj-seed.js","news-wealth-seed.js","news-yahoo-seed.js","news-technews-seed.js","news-ctee-seed.js","news-asia-risk-seed.js","stock-news-seed.js","company-disclosures-seed.js","monthly-revenue-seed.js","dividend-history-seed.js","secondary-reference-seed.js","data-verification-seed.js","yahoo-details-seed.js","etf-details-seed.js","stock-basics-seed.js","market-volume-history-seed.js"):self.assertIn(seed,sw)
 def test_market_snapshot_seed_schema(self):
  payload=json.loads(self.read("data/market-snapshot.json"))
  self.assertEqual(payload.get("metadata",{}).get("version"),"v11.4.17")
  self.assertEqual(set(payload.get("metadata",{}).get("kline_symbols",[])),{"^TWII","^KS11","^N225","^IXIC","^SOX","^GSPC"})
  self.assertNotIn("^TWOII",{row.get("symbol") for row in payload.get("items",[])})

 def test_all_pages_current_version(self):
  for p in ROOT.glob("*.html"):
   body=p.read_text(encoding="utf-8")
   self.assertIn("v11.4.17",body,p.name)
   self.assertNotIn("v11.4.15",body,p.name)


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
  for x in ("BATCH_MONTHS = 12","ThreadPoolExecutor(max_workers=2)","month_cursor"):self.assertIn(x,script)

 def test_chinese_only_news_gate(self):
  pipeline=self.read("scripts/news_pipeline.py")
  for x in ("readable_chinese","decode_response","MOJIBAKE_RE","language\":\"zh-Hant"):
   self.assertIn(x,pipeline)

 def test_compact_disclosures(self):
  updater=self.read("scripts/update_company_disclosures.py");front=self.read("assets/news.js")
  for x in ("concise_disclosure_summary","short_summary","full_text"):self.assertIn(x,updater)
  for x in ("notice-details","查看公告內容","slice(0,4)"):self.assertIn(x,front)

 def test_dividend_year_filter(self):
  asset=self.read("assets/asset.js")
  self.assertIn("(20\\d{2})",asset)
  self.assertNotIn("(?:20)?(\\d{2,4})",asset)

 def test_stock_news_is_separate_from_disclosures(self):
  pipeline=self.read("scripts/news_pipeline.py");front=self.read("assets/news.js");asset=self.read("assets/asset.js")
  for x in ('forced_scope=="media"','is_stock_news','"stock" if stock_article'):self.assertIn(x,pipeline)
  self.assertIn('item.source_id==="company-disclosures"',front)
  self.assertNotIn('item.source_id==="company-disclosures"||item.scope==="company"',front)
  for x in ("loadStockNews","stockNewsPayload","asset-media-card"):self.assertIn(x,asset+self.read("assets/shared.js"))

 def test_stock_news_aggregator(self):
  script=self.read("scripts/update_stock_news.py")
  for x in ("other_reports","asset_profiles","SequenceMatcher","stock-news.json"):self.assertIn(x,script)
  self.assertTrue((ROOT/".github/workflows/update-stock-news.yml").exists())

 def test_stock_news_sources_include_requested_media(self):
  cfg=json.loads(self.read("data/news-channels.json"));ids={x["id"] for x in cfg["media"]}
  for x in ("wealth","yahoo","technews","ctee"):self.assertIn(x,ids)
  wealth=next(x for x in cfg["media"] if x["id"]=="wealth")
  self.assertTrue(any("stock.ltn.com.tw" in u for u in wealth["urls"]))
  yahoo=next(x for x in cfg["media"] if x["id"]=="yahoo")
  self.assertTrue(all("rss?category=" in u for u in yahoo["urls"]))

 def test_stock_news_cards_support_images(self):
  self.assertIn("image_url",self.read("scripts/update_media_source.py"))
  for path in ("assets/shared.js","assets/asset.js","assets/news.js","assets/home.js"):
   self.assertIn("renderNewsThumb",self.read(path),path)
  self.assertIn("data-fallback-src",self.read("assets/shared.js"))
  self.assertIn("stock-news-grid",self.read("assets/styles.css"))

 def test_home_summary_and_volume_momentum(self):
  html=self.read("index.html");js=self.read("assets/home.js")
  for x in ("我的資產總覽","portfolioTotalValue","成交動能","volumeMomentum"):self.assertIn(x,html)
  for x in ("renderPortfolioSummary","volume_ratio_20d","portfolioDayPL"):self.assertIn(x,js)
  self.assertNotIn("台灣櫃買指數",html)

 def test_tpex_web_news_disabled(self):
  updater=self.read("scripts/update_official_notices.py")
  self.assertNotIn("tpex_press",updater)
  self.assertIn("TPEx 網頁新聞與公告",updater)
  data=json.loads(self.read("data/official-market-notices.json"))
  self.assertFalse(any("櫃買" in str(x.get("source","")) for x in data.get("items",[])))

 def test_verification_channels(self):
  shared=self.read("assets/shared.js");asset=self.read("assets/asset.js")
  for x in ("live-secondary-reference","live-data-verification"):self.assertIn(x,shared)
  for x in ("secondary-reference.json","data-verification.json","assetTrust","多來源一致","資料衝突"):self.assertIn(x,asset)
  for name in ("update-secondary-reference.yml","update-data-verification.yml"):
   self.assertTrue((ROOT/".github/workflows"/name).exists(),name)

 def test_market_volume_history(self):
  script=self.read("scripts/update_tw_market.py");workflow=self.read(".github/workflows/update-tw-market.yml")
  for x in ("market-volume-history.json","volume_ratio_20d","average_20d_trade_value"):self.assertIn(x,script)
  self.assertIn("market-volume-history.json",workflow)

 def test_compact_controls_before_calendar_layout(self):
  html=self.read("index.html")
  self.assertLess(html.index("compact-feature-strip"),html.index("我的資產總覽"))
  self.assertLess(html.index("我的資產總覽"),html.index("六大指數日 K 與關鍵資訊"))
  self.assertLess(html.index("六大指數日 K 與關鍵資訊"),html.index("市場事件月曆"))
  self.assertLess(html.index("市場事件月曆"),html.index("今日新公布日期"))
  for token in ("home-summary-row","balanced-summary-row","dual-calendar-card","calendar-mode-switch","market-kline-panel","六大指數日 K 與關鍵資訊"):self.assertIn(token,html)
  for token in ("home-primary-grid","home-market-rail"):self.assertNotIn(token,html)

 def test_today_new_dates_jump_to_matching_calendar_mode(self):
  html=self.read("index.html");js=self.read("assets/date-alerts.js")+self.read("assets/home.js")
  self.assertIn("今日新公布日期",html)
  for token in ("data-calendar-jump","market-radar:calendar-jump","data-calendar-mode","data-calendar-date"):self.assertIn(token,js)

 def test_non_ai_news_image_pipeline(self):
  updater=self.read("scripts/update_media_source.py");news=self.read("assets/news.js");home=self.read("assets/home.js");shared=self.read("assets/shared.js")
  for x in ("og:image","twitter:image","article_image_from_soup","enrich_article_images","fallback_image_slug"):self.assertIn(x,updater)
  for x in ("renderNewsThumb","newsHasImage","majorCandidates.find(newsHasImage)"):self.assertIn(x,news+shared)
  self.assertIn("renderNewsThumb",home)
  self.assertIn("data-fallback",shared)
  self.assertNotIn("fallbackImage",news)

 def test_no_ai_image_generation_dependency(self):
  text="\n".join(self.read(p.relative_to(ROOT)) for p in [ROOT/"scripts/update_media_source.py",ROOT/"assets/news.js",ROOT/"assets/home.js"])
  for forbidden in ("image_gen","openai.images","dall-e","stable diffusion","midjourney"):
   self.assertNotIn(forbidden.lower(),text.lower())

 def test_compact_clickable_news_portal(self):
  html=self.read("news.html");js=self.read("assets/news.js");css=self.read("assets/styles.css")
  self.assertNotIn("sourceFilters",html+js)
  for x in ("hero-lead","hero-side-item","portal-news-card","portal-news-grid"):self.assertIn(x,js+css)
  self.assertNotIn("閱讀原文 →",js)

 def test_yahoo_detail_channel(self):
  for p in ("scripts/update_yahoo_details.py",".github/workflows/update-yahoo-details.yml","data/yahoo-details.json","data/yahoo-details-seed.js"):self.assertTrue((ROOT/p).exists(),p)
  shared=self.read("assets/shared.js");asset=self.read("assets/asset.js");workflow=self.read(".github/workflows/update-yahoo-details.yml")
  for x in ("live-yahoo-details","yahoo-details.json"):self.assertIn(x,shared+asset+workflow)
  for x in ("querySummary" if False else "quoteSummary","fundamentals-timeseries","quarterlyTotalRevenue","topHoldings"):self.assertIn(x,self.read("scripts/update_yahoo_details.py"))
  self.assertIn("Yahoo 參考資料",asset)

 def test_etf_detail_channel(self):
  for p in ("scripts/update_etf_details.py",".github/workflows/update-etf-details.yml","data/etf-details.json","data/etf-details-seed.js"):self.assertTrue((ROOT/p).exists(),p)
  shared=self.read("assets/shared.js");asset=self.read("assets/asset.js");workflow=self.read(".github/workflows/update-etf-details.yml")
  for x in ("live-etf-details","etf-details.json"):self.assertIn(x,shared+asset+workflow)
  updater=self.read("scripts/update_etf_details.py")
  for x in ("ETFortune/etfInfo","Basic0004","Basic0007","active-etf.aspx","field_sources","verification"):self.assertIn(x,updater)

 def test_financial_calculation_metadata(self):
  updater=self.read("scripts/update_yahoo_details.py");asset=self.read("assets/asset.js")
  for x in ("quarterlyBasicAverageShares","quarterlyDilutedAverageShares","metrics_meta","eps_status","估算EPS","單季ROE年化"):self.assertIn(x,updater)
  for x in ("計算值","估算值","yahooMetricMeta"):self.assertIn(x,asset)

 def test_news_without_giant_placeholders(self):
  shared=self.read("assets/shared.js");news=self.read("assets/news.js");css=self.read("assets/styles.css")
  self.assertIn("hero-lead.no-image",css)
  self.assertIn("assets/news-fallback/",shared)
  self.assertIn("majorCandidates.find(newsHasImage)",news)


 def test_stock_basic_channel(self):
  for path in ("scripts/update_stock_basics.py",".github/workflows/update-stock-basics.yml","data/stock-basics.json","data/stock-basics-seed.js"):
   self.assertTrue((ROOT/path).exists(),path)
  shared=self.read("assets/shared.js");asset=self.read("assets/asset.js");coverage=self.read("assets/coverage.js");updater=self.read("scripts/update_stock_basics.py")
  for token in ("live-stock-basics","stock-basics.json","loadStockBasics","STOCK_BASIC_ENDPOINTS"):self.assertIn(token,shared+asset+coverage)
  for token in ("t187ap03_L","mopsfin_t187ap03_O","universe = set(official)","all-currently-listed-twse-and-tpex-stocks"):self.assertIn(token,updater)
  self.assertNotIn("candidates = [asset for asset in assets",updater)
  self.assertIn("Object.entries(stockBasics)",coverage)
  payload=json.loads(self.read("data/stock-basics.json"))
  self.assertGreaterEqual(len(payload.get("items",{})),10)
  self.assertTrue(all(float(row.get("basic_coverage_percent",0))>=90 for row in payload.get("items",{}).values()))

 def test_chip_search_allows_manual_deletion(self):
  js=self.read("assets/institutional.js")
  self.assertIn('if(writeInput)$("#chipSymbol").value=selectedSymbol',js)
  self.assertIn('renderItem(exact.symbol,{writeInput:false})',js)
  self.assertNotIn('value=`${selected.symbol} ${selected.name',js)
  self.assertIn('event.key!=="Enter"',js)

 def test_tw_chips_updater_is_real_and_preserves_last_good(self):
  script=self.read("scripts/update_tw_chips.py")
  for token in ("/v1/fund/T86","MI_MARGN","TWTB4U","institutional-trading","/margin","write_payload","YAHOO_BATCH","merge_history"):
   self.assertIn(token,script)
  self.assertNotIn("add official parsers here",script)
  workflow=self.read(".github/workflows/update-tw-chips.yml")
  for token in ("Validate chips payload","json.loads","path.stat().st_size"):
   self.assertIn(token,workflow)

 def test_coverage_uses_final_merged_etf_view(self):
  js=self.read("assets/coverage.js")
  for token in ("assets.json","dividend-history.json","data-verification.json","deriveAllocations","officialEtf","distributionRows","allocationsComplete"):
   self.assertIn(token,js)
  audit=self.read("scripts/audit_all_assets.py")
  for token in ("yahoo-details.json","etf-details.json","dividend-history.json","產業配置","multi_source"):
   self.assertIn(token,audit)
  daily=self.read(".github/workflows/update-daily.yml")
  for token in ("Restore enrichment channels for final audit","live-yahoo-details","live-etf-details","live-dividend-history"):
   self.assertIn(token,daily)

 def test_priority_symbols_are_backfilled_first(self):
  for path in ("scripts/update_etf_details.py","scripts/update_yahoo_details.py","scripts/update_tw_chips.py"):
   text=self.read(path)
   self.assertIn("00981A",text,path)
   self.assertIn("PRIORITY_SYMBOLS",text,path)

 def test_asia_macro_risk_channel(self):
  cfg=json.loads(self.read("data/news-channels.json"));channel=next(x for x in cfg["media"] if x["id"]=="asia-risk")
  self.assertEqual(channel["kind"],"rss")
  self.assertTrue(any("news.google.com/rss/search" in u for u in channel["urls"]))
  for token in ("日圓","韓國央行","地方債","亞洲資金外流"):
   self.assertIn(token,self.read("scripts/news_pipeline.py"))
  self.assertIn('data-topic="asia-risk"',self.read("news.html"))
  self.assertIn("live-news-asia-risk",self.read("assets/shared.js"))
  self.assertTrue((ROOT/".github/workflows/update-news-asia-risk.yml").exists())
  self.assertIn("live-news-asia-risk",self.read(".github/workflows/update-stock-news.yml"))

 def test_asia_channel_excludes_video_programs(self):
  cfg=json.loads(self.read("data/news-channels.json"));channel=next(x for x in cfg["media"] if x["id"]=="asia-risk")
  self.assertIn("youtube.com",channel["exclude_domains"])
  self.assertIn("訪談",channel["exclude_title_patterns"])
  updater=self.read("scripts/update_media_source.py")
  for token in ("excluded_item","resolve_google_news","discovery_source"):
   self.assertIn(token,updater)

 def test_v11417_fresh_data_loader(self):
  shared=self.read("assets/shared.js")
  for token in ("loadBranchApi","api.github.com/repos","snapshotCacheKey","mergeSnapshotCache","FRESH_BRANCH_FILES"):self.assertIn(token,shared)
  self.assertIn('"market-snapshot.json","tw-market.json","market-volume-history.json","events.json"',shared)

 def test_online_turnover_backfill(self):
  script=self.read("scripts/update_tw_market.py");workflow=self.read(".github/workflows/update-tw-market.yml")
  for token in ("TWSE_HISTORY_OPENAPI","TWSE_HISTORY_MONTH","TPEX_HISTORY_OPENAPI","TPEX_HISTORY_MONTH","HISTORY_START = date(2026, 1, 1)","direct-online-official"):self.assertIn(token,script)
  for token in ("tw-market.json:data/tw-market.json","Validate online turnover archive"):self.assertIn(token,workflow)

 def test_calendar_archive_from_20260101(self):
  script=self.read("scripts/update_events.py");workflow=self.read(".github/workflows/update-events.yml")
  for token in ("ARCHIVE_START = date(2026, 1, 1)","fetch_fomc","FOMC_URL","archive_policy"):self.assertIn(token,script)
  self.assertIn('metadata.get("archive_start")=="2026-01-01"',workflow)

 def test_news_archive_policy_and_backfill(self):
  pipeline=self.read("scripts/news_pipeline.py");updater=self.read("scripts/update_media_source.py")
  for token in ("ARCHIVE_START=datetime(2026,1,1","keep_in_archive","RECENT_FULL_DAYS=30","published_at_desc"):self.assertIn(token,pipeline)
  for token in ("HISTORY_QUERIES","google-news-history","NEWS_HISTORY_BACKFILL","after:{start.isoformat()}"):self.assertIn(token,updater)

 def test_global_workflow_restores_last_kline(self):
  workflow=self.read(".github/workflows/update-global-market.yml")
  for token in ("Restore last successful global snapshot","market-snapshot.json:data/market-snapshot.json","Validate six index K-lines"):self.assertIn(token,workflow)

if __name__=="__main__":unittest.main()
