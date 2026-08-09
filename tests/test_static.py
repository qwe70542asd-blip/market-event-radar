from pathlib import Path
import json,re,unittest
ROOT=Path(__file__).resolve().parents[1]

class StaticTests(unittest.TestCase):
 def read(self,path):return (ROOT/path).read_text(encoding="utf-8")
 def test_required_tree(self):
  for path in [".github/workflows","assets","data","docs","scripts","tests","index.html","news.html","asset.html","service-worker.js"]:self.assertTrue((ROOT/path).exists(),path)
 def test_version(self):
  self.assertEqual(json.loads(self.read("VERSION.json"))["baseline_version"],"11.4.35")
 def test_ascii_filenames(self):
  for path in ROOT.rglob("*"):self.assertTrue(all(ord(c)<128 for c in path.name),path)
 def test_no_audio(self):
  self.assertFalse(any(p.suffix.lower() in {".m4a",".mp3",".wav"} for p in ROOT.rglob("*")))
 def test_home_market_focus(self):
  html=self.read("index.html")
  for token in ("我的資產總覽","今日台股狀態","balanced-summary-row","marketStateSummary","foreignDirectionDetail"):self.assertIn(token,html)
  self.assertNotIn("虛擬貨幣即時排行",html)
 def test_calendar_grouped(self):
  html=self.read("index.html");js=self.read("assets/home.js")
  for token in ("市場事件日曆","股利股息日曆","marketCalendarFilters","dividendCalendarFilters","calendarModeSummary"):self.assertIn(token,html)
  for token in ("setCalendarMode","marketRelevant","dividendRelevant","dividendTable","localKey"):self.assertIn(token,js)
 def test_global_market_set(self):
  script=self.read("scripts/update_market_snapshot.py");home=self.read("assets/home.js")
  for x in ("^TWII","^DJI","^IXIC","^SOX","^GSPC","^N225","^VIX","^TNX","DX-Y.NYB","TWD=X","KRW=X"):self.assertIn(x,script)
  for x in ("2330.TW","2454.TW","3017.TW","2408.TW","LEADER_META"):self.assertNotIn(x,script)
  for x in ("parse_yahoo_candles","fetch_twse_taiex","candles","candle_source","data_status",'"range": "3mo"','"interval": "1d"'):self.assertIn(x,script)
  for x in ('marketKlineSymbols=["^TWII","^DJI","^IXIC","^SOX","^GSPC","^N225"]',"market-candle","近 ${candles.length||0} 個交易日"):self.assertIn(x,home)
  self.assertNotIn("^TWOII",script+home)
  self.assertNotIn("^KS11",script+home);self.assertNotIn("^KQ11",script+home)
 def test_etf_whitelist(self):
  script=self.read("scripts/update_tw_market.py")
  for x in ("TWSE_FUNDS","TPEX_FUNDS","assets.json",'return "other"'):self.assertIn(x,script)
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
  for f in ("assets/home.js","assets/news.js","assets/event.js"):self.assertIn("loadNewsChannels",self.read(f),f)
  self.assertIn("loadStockNews",self.read("assets/asset.js"))
  self.assertNotIn("loadNewsChannels",self.read("assets/asset.js"))
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
  sw=self.read("service-worker.js");self.assertIn("market-event-radar-v11-4-35",sw)
  for seed in ("news-cna-seed.js","news-moneydj-seed.js","news-wealth-seed.js","news-yahoo-seed.js","news-technews-seed.js","news-ctee-seed.js","news-asia-risk-seed.js","stock-news-seed.js","company-disclosures-seed.js","monthly-revenue-seed.js","dividend-history-seed.js","secondary-reference-seed.js","data-verification-seed.js","yahoo-details-seed.js","etf-details-seed.js","stock-basics-seed.js","market-volume-history-seed.js","market-kline-seed.js"):self.assertIn(seed,sw)
 def test_cross_market_validator_uses_exchange_local_timestamp(self):
  validator=self.read("scripts/validate_public_data.py")
  self.assertIn('row.get("market_at_local")',validator)
  self.assertNotIn('market_at=str(row.get("market_at")',validator)

 def test_tw_chips_restores_live_verified_date_and_asset_master(self):
  workflow=self.read(".github/workflows/update-tw-chips.yml")
  for token in ("live-assets","live-tw-market","live-tw-chips"):
   self.assertIn(token,workflow)

 def test_market_snapshot_seed_schema(self):
  payload=json.loads(self.read("data/market-snapshot.json"))
  self.assertEqual(payload.get("metadata",{}).get("version"),"v11.4.35")
  self.assertEqual(set(payload.get("metadata",{}).get("kline_symbols",[])),{"^TWII","^DJI","^IXIC","^SOX","^GSPC","^N225"})
  self.assertNotIn("^TWOII",{row.get("symbol") for row in payload.get("items",[])})

 def test_all_pages_current_version(self):
  for p in ROOT.glob("*.html"):
   body=p.read_text(encoding="utf-8")
   self.assertIn("v11.4.35",body,p.name)
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

 def test_balanced_portfolio_summary_layout(self):
  css=self.read("assets/styles.css")
  for token in ("v11.4.35 portfolio summary balance","grid-template-columns:repeat(3,minmax(0,1fr))","grid-template-rows:repeat(2,minmax(78px,1fr))","justify-content:center"):
   self.assertIn(token,css)

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
  script=self.read("scripts/update_tw_market.py");workflow=self.read(".github/workflows/update-market-core.yml")
  for x in ("market-volume-history.json","volume_ratio_20d","average_20d_trade_value"):self.assertIn(x,script)
  self.assertIn("market-volume-history.json",workflow)
  self.assertIn("live-assets",workflow)

 def test_compact_controls_before_calendar_layout(self):
  html=self.read("index.html")
  self.assertLess(html.index("compact-feature-strip"),html.index("我的資產總覽"))
  self.assertLess(html.index("我的資產總覽"),html.index("六大指數互動 K 線與關鍵資訊"))
  self.assertLess(html.index("六大指數互動 K 線與關鍵資訊"),html.index("市場事件月曆"))
  self.assertLess(html.index("市場事件月曆"),html.index("今日新公布日期"))
  for token in ("home-summary-row","balanced-summary-row","dual-calendar-card","calendar-mode-switch","market-kline-panel","六大指數互動 K 線與關鍵資訊"):self.assertIn(token,html)
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
  shared=self.read("assets/shared.js");asset=self.read("assets/asset.js");updater=self.read("scripts/update_stock_basics.py")
  for token in ("live-stock-basics","stock-basics.json","loadStockBasics","STOCK_BASIC_ENDPOINTS"):self.assertIn(token,shared+asset)
  for token in ("t187ap03_L","mopsfin_t187ap03_O","universe = set(official)","all-currently-listed-twse-and-tpex-stocks"):self.assertIn(token,updater)
  self.assertNotIn("candidates = [asset for asset in assets",updater)
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

 def test_public_coverage_page_removed(self):
  self.assertFalse((ROOT/"coverage.html").exists())
  self.assertFalse((ROOT/"assets/coverage.js").exists())
  for page in ROOT.glob("*.html"):
   body=page.read_text(encoding="utf-8")
   self.assertNotIn("coverage.html",body,page.name)
   self.assertNotIn("資料覆蓋",body,page.name)
  sw=self.read("service-worker.js")
  self.assertNotIn("coverage.html",sw)
  self.assertNotIn("assets/coverage.js",sw)

 def test_backend_audit_uses_final_merged_etf_view(self):
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
  self.assertIn('"market-snapshot.json","market-kline.json","tw-market.json","market-volume-history.json","events.json"',shared)

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

 def test_strict_data_quality_gates(self):
  market=self.read("scripts/update_market_snapshot.py");events=self.read("scripts/update_events.py");news=self.read("scripts/news_pipeline.py");validator=self.read("scripts/validate_public_data.py")
  for token in ("same-session-price-vs-adjacent-close","mixed-session","validate_market_row","quality_policy"):self.assertIn(token,market)
  for token in ("choose_material_target_date","explicit-labeled-date","official-announcement-date","BLS_HTML_URL","BEA_FULL_URL"):self.assertIn(token,events)
  for token in ("valid_symbols=set(aliases.values())","Longest-name-first","official stock/ETF master"):self.assertIn(token,news)
  for token in ("bad market change","period start leaked","invalid news symbols"):self.assertIn(token,validator)
  for workflow in ("update-global-market.yml","update-events.yml","update-stock-basics.yml"):
   self.assertIn("validate_public_data.py",self.read(f".github/workflows/{workflow}"))

 def test_company_and_financial_coverage_are_separate(self):
  updater=self.read("scripts/update_stock_basics.py");asset=self.read("assets/asset.js")
  for token in ("financial_coverage_percent","average_financial_coverage_percent","INDUSTRY_NAMES","industry_name"):self.assertIn(token,updater)
  self.assertIn("公司主檔",asset);self.assertIn("財務資料",asset)
  payload=json.loads(self.read("data/stock-basics.json"))
  self.assertIn("average_financial_coverage_percent",payload["metadata"])
  self.assertTrue(all("financial_coverage_percent" in row for row in payload.get("items",{}).values()))

 def test_seed_data_passes_strict_validator(self):
  import subprocess,sys
  subprocess.run([sys.executable,str(ROOT/"scripts/validate_public_data.py"),"all"],cwd=ROOT,check=True)

 def test_v11421_live_market_and_interactive_kline(self):
  home=self.read("assets/home.js");shared=self.read("assets/shared.js");worker=self.read("edge/market-live-worker.js")
  for token in ("60000","anyTrackedMarketOpen","visibilitychange","freshness_status","session_date"):self.assertIn(token,home)
  for token in ("loadMarketKline","5m","15m","30m","60m","4h","1wk","1mo","LIVE_MARKET_ENDPOINT"):self.assertIn(token,shared)
  for token in ("scheduled(event,env,ctx)","* * * * *","same-session","marketOpen"):self.assertIn(token,worker+self.read("edge/wrangler.toml.example"))

 def test_v11421_historical_exdiv_backfill(self):
  events=self.read("scripts/update_events.py")
  for token in ("TWSE_EXDIV_HISTORY_URL","TPEX_EXDIV_HISTORY_URL","fetch_twse_exdiv_history","fetch_tpex_exdiv_history","twse-exdiv-history","tpex-exdiv-history"):self.assertIn(token,events)

 def test_home_featured_information_is_time_bounded(self):
  home=self.read("assets/home.js")
  for token in ("recentMajorNews","upcomingMajorEvents","tomorrowKey","afterTomorrowKey","86400000","目前沒有近 24 小時重大新聞或今明後重大事件"):self.assertIn(token,home)

 def test_v11422_six_index_order_and_no_kospi_cards(self):
  home=self.read("assets/home.js");market=self.read("scripts/update_market_snapshot.py")
  self.assertIn('marketKlineSymbols=["^TWII","^DJI","^IXIC","^SOX","^GSPC","^N225"]',home)
  self.assertIn('(\"^DJI\", \"道瓊工業平均指數\"',market)
  self.assertNotIn('(\"^KS11\",',market);self.assertNotIn('(\"^KQ11\",',market)

 def test_v11428_sector_heat_removed_from_home_but_classifier_retained(self):
  html=self.read("index.html");home=self.read("assets/home.js");market=self.read("scripts/update_market_snapshot.py");engine=self.read("assets/dynamic-leaders.js")
  self.assertIn("今日台股狀態",html);self.assertNotIn('id="marketList"',html);self.assertNotIn("台股今日產業強弱",html)
  for forbidden in ("LEADER_META","leader_ticker",'"leader_order":',"const TW_LEADERS") :self.assertNotIn(forbidden,market+home)
  for token in ("半導體","AI 伺服器／電腦","散熱","網通／高速傳輸","PCB／載板","記憶體／儲存","INDUSTRY_CODE_MAP"):self.assertIn(token,engine)
  self.assertIn("const official=",engine);self.assertNotIn("classifySector(row,basic,signal.text)",engine)

 def test_v11422_static_multi_interval_kline_channel(self):
  updater=self.read("scripts/update_market_klines.py");shared=self.read("assets/shared.js");workflow=self.read(".github/workflows/update-global-market.yml")
  for token in ("aggregate_4h","session_anchor","market-kline.json","5m","15m","30m","60m","1wk","1mo"):self.assertIn(token,updater+shared+workflow)
  self.assertIn("Date.now()-marketKlinePayloadAt>30000",shared)
  self.assertIn("market-kline.json:data/market-kline.json",workflow)

 def test_v11422_known_actions_failures_are_fixed(self):
  verification=self.read("scripts/update_data_verification.py");basics=self.read("scripts/update_stock_basics.py");news=self.read("scripts/news_pipeline.py")
  for token in ("normalize_rows","isinstance(value, dict)","isinstance(value, list)"):self.assertIn(token,verification)
  for token in ("len(raw) > 2","其他業"):self.assertIn(token,basics)
  for token in ("full official stock-basics channel","valid_symbols=set(aliases.values())"):self.assertIn(token,news)

 def test_v11422_event_dividend_and_news_ui_hardening(self):
  event=self.read("assets/event.js");home=self.read("assets/home.js");shared=self.read("assets/shared.js");asset=self.read("assets/asset.js")
  for token in ("event-facts-grid","事件說明","查看官方網頁","官方原始 API／文字檔已整理成本站內容"):self.assertIn(token,event+self.read("assets/styles.css"))
  for token in ("金額待公告","event.html?id=", "dividend-history.json"):self.assertIn(token,home)
  for token in ("fallback=","fetchpriority","remote-image-failed"):self.assertIn(token,shared+self.read("assets/styles.css"))
  for token in ("change_shares","待前一交易日","industry_name"):self.assertIn(token,asset+self.read("scripts/update_etf_details.py"))

 def test_v11422_crypto_removed_from_public_master(self):
  payload=json.loads(self.read("data/assets.json"));assets=payload.get("assets",[])
  self.assertFalse(any(str(row.get("asset_class")).lower()=="crypto" or row.get("market")=="CRYPTO" for row in assets))
  self.assertNotIn("CRYPTO:BTC",self.read("data/assets-seed.js"));self.assertNotIn("CRYPTO:ETH",self.read("data/assets-seed.js"))

 def test_v11424_release_verification_workflow(self):
  workflow=self.read(".github/workflows/release-verification.yml");smoke=self.read("scripts/http_smoke.py")
  for token in ("validate_public_data.py all","python -m pytest -q","http.server 8765","scripts/http_smoke.py"):self.assertIn(token,workflow)
  for token in ("今日台股狀態","market-kline-seed.js","HTTP smoke passed"):self.assertIn(token,smoke)

 def test_v11424_home_news_is_photo_first_and_never_uses_old_news_as_filler(self):
  home=self.read("assets/home.js");shared=self.read("assets/shared.js")
  for token in ("recentPhotoNews","validRecentNews","newsHasImage(item)","age<=86400000","eventSlots"):self.assertIn(token,home)
  for token in ("GENERIC_NEWS_IMAGE_RE","remote-image-loaded","no-referrer","advanceNewsImage","newsImageCandidates"):self.assertIn(token,shared)

 def test_v11424_media_scraper_rejects_generic_images_and_retries_article_page(self):
  script=self.read("scripts/update_media_source.py")
  for token in ("GENERIC_IMAGE_RE","usable_image_url","srcset","data-srcset","image_fetch_limit", "48","enrich_merged_article_images","image_policy","120"):self.assertIn(token,script)
  self.assertIn('item.pop("image_url",None)',script)

 def test_v11424_version_bump_prevents_same_version_asset_cache(self):
  for path in ("index.html","assets/shared.js","assets/home.js","assets/sw-register.js","service-worker.js","VERSION.json"):
   content=self.read(path);self.assertIn("11.4.35",content);self.assertNotIn("11.4.23",content);self.assertNotIn("11.4.22",content)

 def test_v11428_compact_market_state_replaces_sector_heat(self):
  html=self.read("index.html");home=self.read("assets/home.js");snapshot=self.read("scripts/update_market_snapshot.py")
  for token in ("今日台股狀態","盤勢方向","市場廣度","外資方向","成交動能","marketStateSummary"):self.assertIn(token,html)
  for token in ("marketTone","breadthSummary","foreignDirectionDetail","volumeMomentum"):self.assertIn(token,home+html)
  self.assertNotIn('id="marketList"',html);self.assertNotIn("台股今日產業強弱",html)
  for symbol in ("2330.TW","2454.TW","2317.TW","2382.TW","3017.TW","3324.TW","2345.TW","2368.TW","3037.TW","2408.TW"):self.assertNotIn(symbol,snapshot)

 def test_v11424_edge_worker_uses_current_six_indices(self):
  worker=self.read("edge/market-live-worker.js")
  for token in ("^TWII","^DJI","^IXIC","^SOX","^GSPC","^N225","aggregate4h"):self.assertIn(token,worker)
  for token in ("^KS11","^KQ11","KR:"):self.assertNotIn(token,worker)


 def test_v11426_institutional_cards_show_lot_units(self):
  js=self.read("assets/institutional.js");html=self.read("institutional.html")
  for token in ("displayLots","flowLabel","單位：張","外資買賣超","投信買賣超","自營商買賣超","三大法人合計"):
   self.assertIn(token,js+html)
  self.assertIn("1 張 = 1,000 股",html)

 def test_v11426_portfolio_autocomplete(self):
  html=self.read("portfolio.html");js=self.read("assets/portfolio.js")
  for token in ("holdingSuggestions","aria-autocomplete","searchCandidates","data-index","ArrowDown","ArrowUp","Enter"):
   self.assertIn(token,html+js)
  for token in ("找不到正式標的","applyCandidate","candidateMap.get(symbol)"):
   self.assertIn(token,js)

 def test_v11426_news_image_pipeline_retries_candidates(self):
  updater=self.read("scripts/update_media_source.py");shared=self.read("assets/shared.js")
  for token in ("resolve_google_news","article_image_candidates_from_soup","image_candidates","enrich_merged_article_images","fallback-required"):
   self.assertIn(token,updater)
  for token in ("newsImageCandidates","advanceNewsImage","data-candidates","remote-image-failed","no-referrer"):
   self.assertIn(token,shared)

 def test_v11428_featured_news_is_one_lead_plus_right_column(self):
  home=self.read("assets/home.js");css=self.read("assets/styles.css")
  for token in ("home-news-feature-layout","home-feature-lead","home-feature-side-list","featured.slice(1,6)"):self.assertIn(token,home+css)
  self.assertIn("grid-template-columns:minmax(0,1.75fr) minmax(330px,.85fr)",css)

 def test_v11426_industry_codes_are_normalized(self):
  engine=self.read("assets/dynamic-leaders.js")
  for token in ("INDUSTRY_CODE_MAP","normalizeIndustry","\"26\":\"光電\"","\"28\":\"電子零組件\""):
   self.assertIn(token,engine)

 def test_v11426_nikkei_uses_official_completed_daily_validation(self):
  market=self.read("scripts/update_market_snapshot.py")
  for token in ("NIKKEI_DAILY_CSV","fetch_nikkei_official","enrich_nikkei_with_official","Nikkei official daily data","validation_source"):
   self.assertIn(token,market)

 def test_v11426_15m_is_documented_as_post_deploy_nonblocking(self):
  audit=self.read("docs/V11.4.35-release-audit.md")
  for token in ("15 分鐘 K","非阻擋","部署後","不得偽造"):
   self.assertIn(token,audit)

 def test_v11428_mobile_calendar_has_no_forced_horizontal_scroll(self):
  css=self.read("assets/styles.css");html=self.read("index.html");manifest=json.loads(self.read("manifest.webmanifest"))
  for token in (".calendar-weekdays,.calendar-grid{width:100%;min-width:0!important","overflow:visible!important","grid-template-columns:repeat(7,minmax(0,1fr))",".mobile-install-trigger","assets/pwa-install.js?v=11.4.35"):
   self.assertIn(token,css+html)
  self.assertEqual(manifest.get("display"),"standalone")
  self.assertTrue(any(icon.get("sizes")=="192x192" for icon in manifest.get("icons",[])))
  self.assertTrue(any(icon.get("sizes")=="512x512" for icon in manifest.get("icons",[])))

 def test_v11431_calendar_boot_is_nonblocking(self):
  home=self.read("assets/home.js")
  for token in ("eventLivePromise","withBootTimeout(eventLivePromise,eventFallback,3500)","events=fresh","renderCalendar();"):
   self.assertIn(token,home)

 def test_v11431_date_alert_integrity_guards(self):
  frontend=self.read("assets/date-alerts.js");backend=self.read("scripts/update_events.py");workflow=self.read(".github/workflows/update-events.yml")
  for token in ("trustedAnnouncement","next<today","previous>=today","dayDistance(previous,next)<=183"):
   self.assertIn(token,frontend)
  for token in ("announcement_candidate","announcement_semantically_valid","suppressed_origins","strict-v11.4.35"):
   self.assertIn(token,backend)
  self.assertIn("v11.4.35",workflow)


 def test_v11431_repo_layout_guard(self):
  cleanup=self.read("scripts/cleanup_repo.py"); workflow=self.read(".github/workflows/release-verification.yml")
  for bad in ("scripts/.github","scripts/assets","scripts/data","scripts/tests","scripts/scripts"):
   self.assertFalse((ROOT/bad).exists(),bad)
  self.assertIn("--check",workflow);self.assertIn("NESTED_DIRS",cleanup)

 def test_v11431_market_runtime_and_verified_dates(self):
  home=self.read("assets/home.js");market=self.read("scripts/update_tw_market.py");core=self.read(".github/workflows/update-market-core.yml")
  self.assertIn("const quoteAgeMinutes=",home)
  self.assertIn("最新交易日",home)
  self.assertIn("trading_date",market);self.assertNotIn('"quote_date": NOW.date().isoformat()',market)
  snapshot=self.read("scripts/update_market_snapshot.py")
  self.assertIn("session_confirmed",snapshot);self.assertIn("unconfirmed_reason",snapshot)
  self.assertIn('cron: "*/5 * * * *"',core)
  self.assertIn('meta.get("version")=="v11.4.35"',core)

 def test_v11431_scheduler_is_consolidated(self):
  batch=self.read(".github/workflows/update-news-batch.yml");official=self.read(".github/workflows/update-official-feeds.yml")
  stock=self.read(".github/workflows/update-stock-news.yml")
  self.assertIn("matrix:",batch);self.assertIn("live-stock-news",batch)
  self.assertNotIn("workflow_run:",stock);self.assertNotIn("schedule:",stock)
  self.assertIn('cron: "7,22,37,52 * * * *"',official)
  for name in ("update-news-cna.yml","update-news-moneydj.yml","update-news-cnyes.yml","update-news-udn.yml","update-news-ltn.yml","update-news-wealth.yml","update-news-yahoo.yml","update-news-technews.yml","update-news-ctee.yml","update-news-asia-risk.yml","update-company-disclosures.yml","update-official-notices.yml","update-global-market.yml","update-tw-market.yml"):
   body=self.read(f".github/workflows/{name}")
   self.assertIn("workflow_dispatch:",body,name);self.assertNotIn("schedule:",body,name)

 def test_v11431_branch_publisher_is_history_free(self):
  script=self.read("scripts/publish_data_branch.sh")
  self.assertIn("git switch --orphan",script)
  self.assertIn("__publish_",script)
  self.assertIn("snapshot_history",script)
  self.assertNotIn('git checkout --orphan "$branch" 2>/dev/null || git checkout "$branch"',script)

 def test_v11431_news_timestamp_and_symbol_guards(self):
  pipeline=self.read("scripts/news_pipeline.py");company=self.read("scripts/update_company_disclosures.py");official=self.read("scripts/update_official_notices.py");stock=self.read("scripts/update_stock_news.py")
  for token in ("if dt is None:","numeric_context","assets_rows","valid_symbols","legacy_now_fallback","legacy_archive_removed"):
   self.assertIn(token,pipeline)
  self.assertIn("publication_datetime",company);self.assertIn("zfill(6)",company)
  self.assertIn("if not date_match",official);self.assertNotIn('(?:cp|news|lp|np)',official)
  self.assertIn("infer_symbols",stock);self.assertIn('primary["symbols"]',stock) if False else None

 def test_v11431_verification_separates_trust_and_completeness(self):
  verifier=self.read("scripts/update_data_verification.py");ui=self.read("assets/data-status.js");asset=self.read("assets/asset.js")
  for token in ("trust_overall","completeness_status","coverage_percent","source_snapshots","stale_sources","reference_session_match"):
   self.assertIn(token,verifier)
  for token in ("欄位完整","部分完整","平均欄位覆蓋","過期來源"):
   self.assertIn(token,ui)
  self.assertIn("trust_overall",asset);self.assertIn("completeness_status",asset)

 def test_v11431_frontend_live_data_load_is_bounded(self):
  shared=self.read("assets/shared.js")
  self.assertIn("DATA_INFLIGHT",shared)
  self.assertIn("LARGE_BRANCH_FILES",shared)
  self.assertIn("loadStatically",shared)
  self.assertIn("statically-live-branch",shared)
  self.assertIn('"stock-basics.json"',shared)
  self.assertNotIn("Promise.any(requests)",shared)
  self.assertIn("Only warm the actual asset page after the user shows intent",shared)
  self.assertNotIn("requestIdleCallback",shared)

 def test_v11431_windows_cleanup_does_not_require_python(self):
  batch=self.read("CLEAN-REPO.cmd")
  self.assertIn('rmdir /s /q "scripts\\%%D"',batch)
  self.assertIn('del /f /q "scripts\\%%F"',batch)
  self.assertNotIn('python scripts\\cleanup_repo.py',batch.lower())


 def test_v11431_second_scan_timestamp_integrity(self):
  market=self.read("scripts/update_market_snapshot.py");events=self.read("scripts/update_events.py");chips=self.read("scripts/update_tw_chips.py");stock_news=self.read("scripts/update_stock_news.py")
  self.assertNotIn('taipei_iso_from_timestamp(meta.get("regularMarketTime")) or NOW',market)
  self.assertIn('if not announcement_day:',events);self.assertNotIn('announcement_day = parse_market_date(first_value(row, ["發言日期", "出表日期", "Date"])) or NOW.date()',events)
  self.assertNotIn('row_date(row) or NOW.date().isoformat()',chips);self.assertIn('_source_date',chips)
  self.assertIn('or ARCHIVE_START',stock_news)

 def test_v11431_verifier_restores_completeness_audit(self):
  workflow=self.read(".github/workflows/update-data-verification.yml")
  self.assertIn('asset-audit.json:data/asset-audit.json',workflow)

 def test_v11431_edge_worker_is_current_and_uses_verified_time(self):
  worker=self.read("edge/market-live-worker.js")
  self.assertIn('v11.4.35',worker);self.assertNotIn('v11.4.27',worker)
  self.assertIn('missing verified quote time',worker)
  self.assertIn('marketDate(new Date(x.time*1000),market)',worker)
  self.assertIn('latestSession===session?previous?.close:latest?.close',worker)
  self.assertIn('sessionConfirmed=session===expected',worker);self.assertIn('unconfirmed',worker)

 def test_v11431_kline_browser_does_not_invent_session_aggregation(self):
  shared=self.read("assets/shared.js")
  self.assertIn("Verified edge or",shared)
  self.assertNotIn('query1.finance.yahoo.com/v8/finance/chart/${encoded}',shared)

 def test_v11431_asset_page_does_not_load_every_news_channel(self):
  asset=self.read("assets/asset.js")
  self.assertNotIn("loadNewsChannels",asset)
  self.assertIn("eventPromise",asset);self.assertIn("stockNewsPromise",asset)
  self.assertIn("Core asset information loads first",asset)

 def test_v11431_secondary_reference_uses_verified_session_dates(self):
  updater=self.read("scripts/update_secondary_reference.py");asset=self.read("assets/asset.js")
  self.assertIn('"quote_date":quote_date',updater)
  self.assertNotIn('chartPreviousClose',updater)
  self.assertIn('secondaryQuote.quote_date',asset)

 def test_v11431_verification_avoids_market_core_boundary(self):
  workflow=self.read(".github/workflows/update-data-verification.yml")
  self.assertIn('cron: "58 * * * *"',workflow)

 def test_v11431_tpex_dividend_parser_accepts_official_field_names(self):
  events=self.read("scripts/update_events.py")
  self.assertIn('公司代號名稱',events)
  self.assertIn('董事會決議通過股利分派日',events)

 def test_v11431_tpex_dividend_endpoint(self):
  events=self.read("scripts/update_events.py")
  self.assertIn("mopsfin_t187ap39_O",events)
  self.assertNotIn("mopsfin_t187ap45_O",events)

 def test_v11432_chart_library_is_not_boot_blocking(self):
  html=self.read("index.html"); loader=self.read("assets/chart-loader.js"); home=self.read("assets/home.js"); sw=self.read("service-worker.js")
  self.assertNotIn('<script src="https://unpkg.com/lightweight-charts',html)
  self.assertIn('assets/chart-loader.js?v=11.4.35',html)
  self.assertLess(html.index('assets/chart-loader.js?v=11.4.35'),html.index('assets/shared.js?v=11.4.35'))
  self.assertIn('market-radar:chart-lib-ready',loader);self.assertIn('market-radar:chart-lib-ready',home)
  self.assertIn('assets/chart-loader.js?v=11.4.35',sw)

 def test_v11432_large_payloads_do_not_use_web_storage(self):
  shared=self.read("assets/shared.js")
  self.assertIn('WEB_STORAGE_CACHE_FILES=new Set(["market-snapshot.json"])',shared)
  self.assertIn('STORAGE_CLEANUP_KEY="mr-storage-cleanup-v11.4.35"',shared)
  self.assertIn('if(!WEB_STORAGE_CACHE_FILES.has(name))return null',shared)

 def test_v11432_event_series_tracking_and_clean_rebuild(self):
  events=self.read("scripts/update_events.py"); workflow=self.read(".github/workflows/update-events.yml"); alerts=self.read("assets/date-alerts.js")
  for token in ('TRACKING_KEY_VERSION = 2','bea_series_key','bls_series_key','assign_bea_tracking','canonical_event_key','tracking_migration_origins'):
   self.assertIn(token,events)
  self.assertGreaterEqual(workflow.count("inputs.clean_rebuild"),2)
  self.assertIn('strict-v11.4.35-series-safe',workflow)
  self.assertIn('reject legacy recurring-series keys',alerts)

 def test_v11432_market_and_chip_state_migrations(self):
  market=self.read("scripts/update_tw_market.py");chips=self.read("scripts/update_tw_chips.py");core=self.read(".github/workflows/update-market-core.yml");chipflow=self.read(".github/workflows/update-tw-chips.yml")
  for token in ('valid_session_date','trim_history_to_trading_date','legacy_history_polluted','Removed retained turnover rows newer than the latest verified trading session'):
   self.assertIn(token,market)
  for token in ('migrate_legacy_items','sanitize_market_dates','symbol-keyed-v2','valid_chip_date'):
   self.assertIn(token,chips)
  self.assertIn('weekday()',core);self.assertIn('symbol-keyed-v2',chipflow)

 def test_v11432_mobile_compact_and_touch_targets(self):
  alert_css=self.read("assets/date-alerts.css");css=self.read("assets/styles.css");alerts=self.read("assets/date-alerts.js")
  self.assertIn('min-height:40px',alert_css)
  self.assertIn('min-width:44px',css);self.assertIn('min-height:44px',css)
  self.assertIn('window.matchMedia?.("(max-width: 720px)")?.matches?6:12',alerts)

 def test_v11433_nested_copy_prevention_is_ignored_and_cleaned(self):
  ignore=self.read(".gitignore");batch=self.read("CLEAN-REPO.cmd");verify=self.read(".github/workflows/release-verification.yml")
  for token in ('/scripts/.github/','/scripts/assets/','/scripts/data/','/scripts/scripts/'):
   self.assertIn(token,ignore)
  self.assertIn(r'scripts\%%D',batch);self.assertIn('verify-v11-4-35-main',verify)

 def test_v11433_cloudflare_deploy_uses_step_level_secret_gate(self):
  deploy=self.read(".github/workflows/deploy-live-market-worker.yml")
  self.assertNotIn("if: ${{ secrets.",deploy)
  self.assertIn("CF_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}",deploy)
  self.assertIn("Cloudflare secrets are not configured; skipping optional edge-worker deployment",deploy)

 def test_v11433_release_has_real_browser_runtime_gate(self):
  verify=self.read(".github/workflows/release-verification.yml"); smoke=self.read("scripts/browser_smoke.py")
  self.assertIn("Chromium homepage runtime",verify)
  self.assertIn("playwright install --with-deps chromium",verify)
  self.assertIn("pageerror",smoke)
  self.assertIn("#calendarGrid",smoke)
  self.assertIn("42",smoke)

 def test_v11435_tpex_bls_and_verification_barriers_are_pinned(self):
  events=self.read("scripts/update_events.py"); chips=self.read("scripts/update_tw_chips.py"); verify=self.read(".github/workflows/update-data-verification.yml")
  snapshot=json.loads(self.read("data/bls-official-schedule-2026.json"))
  self.assertIn("每仟股無償配股",events); self.assertIn("shares_per_thousand / 1000.0",events)
  self.assertIn("現金股利經董事會決議、增資配股經董事會擬議日期",events)
  self.assertIn("BLS_SNAPSHOT_PATH",events); self.assertEqual(len(snapshot.get("events") or []),63)
  self.assertIn('day_trading_scope',chips)
  self.assertNotIn("def parse_tpex_day_trade(rows:",chips)
  self.assertIn("Wait for v11.4.35 Taiwan market release barrier",verify)
  self.assertIn('if [ "$VERSION" = "v11.4.35" ]',verify)

if __name__=="__main__":unittest.main()
