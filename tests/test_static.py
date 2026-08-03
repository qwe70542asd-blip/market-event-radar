
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class StaticTests(unittest.TestCase):
    def test_json(self):
        for path in (ROOT/"data").glob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))

    def test_etf_identities_and_manager(self):
        assets=json.loads((ROOT/"data/assets.json").read_text(encoding="utf-8"))["assets"]
        by_symbol={row["symbol"]:row for row in assets}
        self.assertEqual(by_symbol["00403A"]["name"],"主動統一升級50")
        self.assertEqual(by_symbol["009816"]["name"],"凱基台灣TOP50")
        self.assertEqual(by_symbol["00981A"]["name"],"主動統一台股增長")
        self.assertEqual(by_symbol["00663L"]["etf"]["manager"],"蘇鼎宇")

    def test_no_fake_quotes(self):
        rows=json.loads((ROOT/"data/tw-market.json").read_text(encoding="utf-8"))["items"]
        self.assertTrue(all(row["price"] is None for row in rows))

    def test_homepage_order_and_indices(self):
        html=(ROOT/"index.html").read_text(encoding="utf-8")
        self.assertLess(html.index("feature-strip"),html.index("taiwan-index-strip"))
        self.assertLess(html.index("taiwan-index-strip"),html.index("portfolioLive"))
        self.assertLess(html.index("portfolioLive"),html.index("home-grid"))
        snapshot=json.loads((ROOT/"data/market-snapshot.json").read_text(encoding="utf-8"))
        symbols={row["symbol"] for row in snapshot["items"]}
        self.assertIn("^TWII",symbols)
        self.assertIn("^TWOII",symbols)

    def test_portfolio_limit_sort_and_more_card(self):
        home=(ROOT/"assets/home.js").read_text(encoding="utf-8")
        self.assertIn("ranked.slice(0, 7)",home)
        self.assertIn("portfolio-more-card",home)
        self.assertIn("b.marketValue - a.marketValue",home)

    def test_compact_clean_layout(self):
        css=(ROOT/"assets/styles.css").read_text(encoding="utf-8")
        self.assertIn(".noise { display:none !important; }",css)
        self.assertIn(".taiwan-index-strip",css)
        self.assertIn("grid-template-rows:auto auto",css)
        self.assertIn("minmax(70px,1fr)",css)

    def test_news_clustering_and_interleaving(self):
        updater=(ROOT/"scripts/update_news.py").read_text(encoding="utf-8")
        shared=(ROOT/"assets/shared.js").read_text(encoding="utf-8")
        self.assertIn("def cluster_news",updater)
        self.assertIn("def interleave_sources",updater)
        self.assertIn("fetch_company_announcements",updater)
        self.assertIn("function diversifyNews",shared)
        self.assertIn("template:",shared)

    def test_twse_readable_news_route(self):
        shared=(ROOT/"assets/shared.js").read_text(encoding="utf-8")
        self.assertIn("newsDetail",shared)
        self.assertIn('"/$1/news/newsDetail/"',shared)

    def test_financial_analysis_parser(self):
        spec=importlib.util.spec_from_file_location("update_assets",ROOT/"scripts/update_assets.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        income=[{"公司代號":"3231","年度":"115","季別":"2","營業收入":"1000000","營業毛利（毛損）淨額":"120000","營業利益（損失）":"80000","本期淨利（淨損）":"60000","基本每股盈餘（元）":"3.2"}]
        balance=[{"公司代號":"3231","年度":"115","季別":"2","流動資產":"700000","資產總額":"1500000","流動負債":"350000","負債總額":"800000","權益總額":"700000"}]
        valuation=[{"Code":"3231","PEratio":"20","PBratio":"2.1","DividendYield":"2.5"}]
        metrics,_,status=module.analysis_for("3231",module.parse_income(income),module.parse_balance(balance),module.parse_valuation(valuation))
        self.assertEqual(status,"complete")
        self.assertEqual(metrics["eps"],3.2)
        self.assertAlmostEqual(metrics["current_ratio"],2.0)




    def test_clean_rebuild_and_nonblocking_single_stock(self):
        updater=(ROOT/"scripts/update_assets.py").read_text(encoding="utf-8")
        workflow=(ROOT/".github/workflows/update-daily.yml").read_text(encoding="utf-8")
        self.assertIn("TPEx stock 1595 has no parsed EPS",updater)
        self.assertNotIn("Coverage regression: TPEx stock 1595",updater)
        self.assertIn("clean_rebuild",workflow)
        self.assertNotIn('assert target and target.get("metrics",{}).get("eps") is not None',workflow)

    def test_mops_parser_dependencies(self):
        requirements=(ROOT/"requirements.txt").read_text(encoding="utf-8")
        updater=(ROOT/"scripts/update_assets.py").read_text(encoding="utf-8")
        workflow=(ROOT/".github/workflows/update-daily.yml").read_text(encoding="utf-8")
        self.assertIn("html5lib>=1.1,<2", requirements)
        self.assertIn("def read_html_tables", updater)
        self.assertIn('for flavor in ("lxml", "html5lib")', updater)
        self.assertIn("Verify financial parser dependencies", workflow)

    def test_high_frequency_live_refresh(self):
        shared=(ROOT/"assets/shared.js").read_text(encoding="utf-8")
        home=(ROOT/"assets/home.js").read_text(encoding="utf-8")
        asset=(ROOT/"assets/asset.js").read_text(encoding="utf-8")
        portfolio=(ROOT/"assets/portfolio.js").read_text(encoding="utf-8")
        market=(ROOT/"assets/tw-market.js").read_text(encoding="utf-8")
        news_workflow=(ROOT/".github/workflows/update-news.yml").read_text(encoding="utf-8")
        self.assertIn("fetchTaiwanLiveQuotes",shared)
        self.assertIn("fetchTaiwanIndicesLive",home)
        self.assertIn('fetchYahooChart("^TWII")',home)
        self.assertIn('fetchYahooChart("^TWOII")',home)
        self.assertIn("return isTaiwanQuoteWindow(date) ? 5_000 : 60_000",shared)
        self.assertIn("scheduleAdaptiveRefresh(refreshLiveMarket,taiwanQuoteRefreshDelay,2500)",home)
        self.assertIn("scheduleAdaptiveRefresh(refreshCurrentQuote,taiwanQuoteRefreshDelay,2500)",asset)
        self.assertIn("scheduleAdaptiveRefresh(refreshPortfolioQuotes,taiwanQuoteRefreshDelay,2500)",portfolio)
        self.assertIn("scheduleAdaptiveRefresh(refreshVisibleQuotes,taiwanQuoteRefreshDelay,2500)",market)
        self.assertIn("startCryptoTickerStream",shared)
        self.assertIn("wss://data-stream.binance.vision",shared)
        self.assertIn("setInterval(refreshNewsData,5*60_000)",home)
        self.assertIn('3,8,13,18,23,28,33,38,43,48,53,58',news_workflow)

    def test_market_wide_coverage_audit(self):
        updater=(ROOT/"scripts/update_assets.py").read_text(encoding="utf-8")
        workflow=(ROOT/".github/workflows/update-daily.yml").read_text(encoding="utf-8")
        self.assertIn("TWSE_EPS_URL",updater)
        self.assertIn("TPEX_EPS_URL",updater)
        self.assertIn("asset-coverage.json",updater)
        self.assertIn("coverage",workflow)
        self.assertTrue((ROOT/"coverage.html").exists())
        self.assertTrue((ROOT/"assets/coverage.js").exists())

    def test_tpex_1595_eps_fallback_parser(self):
        spec=importlib.util.spec_from_file_location("update_assets_1595",ROOT/"scripts/update_assets.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        rows=[{"公司代號":"1595","年度":"115","季別":"2","基本每股盈餘（元）":"1.23"}]
        parsed=module.parse_income(rows)
        self.assertEqual(parsed["1595"][0]["eps"],1.23)


    def test_six_independent_data_channels(self):
        workflows={p.name:p.read_text(encoding="utf-8") for p in (ROOT/".github/workflows").glob("*.yml")}
        self.assertEqual(set(workflows),{
            "update-daily.yml","update-events.yml","update-global-market.yml",
            "update-news.yml","update-tw-chips.yml","update-tw-market.yml"
        })
        branches={
            "update-daily.yml":"live-assets",
            "update-events.yml":"live-events",
            "update-global-market.yml":"live-global-market",
            "update-news.yml":"live-news",
            "update-tw-chips.yml":"live-tw-chips",
            "update-tw-market.yml":"live-tw-market",
        }
        groups=set()
        for name,branch in branches.items():
            body=workflows[name]
            self.assertIn(branch,body)
            self.assertNotIn("LIVE_BRANCH: live-data",body)
            group=next(line.strip().split(":",1)[1].strip() for line in body.splitlines() if line.strip().startswith("group:"))
            self.assertNotIn(group,groups)
            groups.add(group)
        self.assertEqual(len(groups),6)

    def test_branch_aware_frontend_loader(self):
        shared=(ROOT/"assets/shared.js").read_text(encoding="utf-8")
        for branch in ("live-assets","live-events","live-tw-market","live-tw-chips","live-global-market","live-news"):
            self.assertIn(branch,shared)
        self.assertIn("const dedicated = available.find",shared)
        self.assertIn("loadChannelManifest",shared)
        self.assertTrue((ROOT/"data-status.html").exists())
        self.assertTrue((ROOT/"assets/data-status.js").exists())

    def test_isolated_publish_helpers(self):
        publish=(ROOT/"scripts/publish_data_branch.sh").read_text(encoding="utf-8")
        restore=(ROOT/"scripts/restore_data_branch.sh").read_text(encoding="utf-8")
        self.assertIn("channel.json",publish)
        self.assertIn("GH_TOKEN",publish)
        self.assertIn("git ls-remote",restore)

    def test_actions_use_node24_compatible_versions(self):
        for path in (ROOT/".github/workflows").glob("*.yml"):
            body=path.read_text(encoding="utf-8")
            self.assertIn("actions/checkout@v6",body)
            self.assertIn("actions/setup-python@v6",body)

    def test_crypto_second_level_and_fallback(self):
        shared=(ROOT/"assets/shared.js").read_text(encoding="utf-8")
        home=(ROOT/"assets/home.js").read_text(encoding="utf-8")
        self.assertIn("@miniTicker",shared)
        self.assertIn("30_000",shared)
        self.assertIn('symbols:["BTC","ETH","BNB","SOL","XRP"]',home)
        self.assertIn('live:"每秒即時"',home)

    def test_full_market_is_not_polled_every_five_seconds(self):
        market=(ROOT/"assets/tw-market.js").read_text(encoding="utf-8")
        self.assertIn("liveTargets()",market)
        self.assertIn("slice(0,20)",market)
        self.assertIn("setInterval(refreshFullSnapshot,60_000)",market)
        self.assertNotIn("fetchTaiwanLiveQuotes(items)",market)

    def test_event_channel_legacy_bootstrap(self):
        workflow=(ROOT/".github/workflows/update-events.yml").read_text(encoding="utf-8")
        self.assertIn('"live-data"',workflow)
        self.assertIn("empty event calendar after legacy bootstrap",workflow)
        self.assertIn("events.json:data/events.json",workflow)

    def test_chip_channel_uses_latest_available_trade_date(self):
        updater=(ROOT/"scripts/update_tw_chips.py").read_text(encoding="utf-8")
        self.assertIn("def candidate_trade_dates",updater)
        self.assertIn("for date in candidate_trade_dates()",updater)
        self.assertIn('"status":"warning"',updater)
        self.assertNotIn('raise SystemExit("No verified official chip values',updater)

    def test_portfolio_unknown_legacy_key_recovery(self):
        shared=(ROOT/"assets/shared.js").read_text(encoding="utf-8")
        self.assertIn("localStorage.length",shared)
        self.assertIn("market.*portfolio|portfolio.*market",shared)

    def test_etf_official_parser(self):
        spec=importlib.util.spec_from_file_location("update_assets_etf",ROOT/"scripts/update_assets.py")
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        row={"基金代號":"00663L","基金簡稱":"國泰臺灣加權正2","基金類型":"股票槓反ETF",
             "基金中文名稱":"國泰臺指ETF傘型證券投資信託基金","標的指數/追蹤指數名稱":"臺灣日報酬兩倍指數",
             "基金經理人":"蘇鼎宇","成立日期":"2016/07/01","上市日期":"2016/07/14","保管機構":"第一商業銀行"}
        asset=module.normalize_master(row,"TWSE","etf")
        self.assertEqual(asset["etf"]["manager"],"蘇鼎宇")
        self.assertEqual(asset["etf"]["benchmark"],"臺灣日報酬兩倍指數")

if __name__=="__main__":
    unittest.main()
