from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_etf_details as etf
import update_yahoo_details as yahoo
import update_tw_chips as chips
import update_market_snapshot as market_snapshot
import update_tw_market as tw_market
import update_events as event_updater
import news_pipeline as news


class ParserTests(unittest.TestCase):
    def test_twse_etf_parser(self):
        html = """
        <html><body><h2>元大臺灣50ETF證券投資信託基金</h2>
        <div>證券簡稱 元大台灣50 證券類別 台股ETF 發行公司 元大投信 基金經理人 王小明 標的指數 臺灣50指數 主題/因子 大型權值</div>
        <div>資產規模(億元) 100.5 億元 受益人次(萬人) 12.3 萬人</div>
        <table><tr><th>發放日</th><th>配息</th></tr><tr><td>2026/07/01</td><td>0.5</td></tr></table>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        with patch.object(etf, "fetch", return_value=("https://www.twse.com.tw/zh/ETFortune/etfInfo/0050", soup)):
            row = etf.parse_twse("0050")
        self.assertEqual(row["issuer"], "元大投信")
        self.assertEqual(row["manager"], "王小明")
        self.assertEqual(row["benchmark"], "臺灣50指數")
        self.assertEqual(row["beneficiary_count"], 123000)
        self.assertEqual(row["distributions"][0]["amount"], 0.5)

    def test_moneydj_holdings_parser(self):
        html = """
        <html><body><div>持股明細 資料日期：2026/07/23</div>
        <table><tr><th>個股名稱</th><th>投資比例(%)</th><th>持有股數</th></tr>
        <tr><td>台積電(2330.TW)</td><td>10.17</td><td>11,840,000</td></tr></table>
        <table><tr><th>產業</th><th>比例(%)</th></tr><tr><td>半導體業</td><td>70.5</td></tr></table>
        </body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        with patch.object(etf, "fetch", return_value=("https://moneydj.test", soup)):
            row = etf.parse_moneydj_holdings("0050")
        self.assertEqual(row["holdings"][0]["symbol"], "2330")
        self.assertEqual(row["holdings"][0]["shares"], 11840000)
        self.assertEqual(row["allocations"][0]["weight"], 70.5)
        self.assertEqual(row["holdings_date"], "2026-07-23")

    def test_financial_calculation_and_estimate_label(self):
        series = {
            "quarterlyTotalRevenue": [{"asOfDate": "2026-03-31", "reportedValue": {"raw": 1000}}],
            "quarterlyGrossProfit": [{"asOfDate": "2026-03-31", "reportedValue": {"raw": 400}}],
            "quarterlyNetIncomeCommonStockholders": [{"asOfDate": "2026-03-31", "reportedValue": {"raw": 100}}],
            "quarterlyTotalAssets": [{"asOfDate": "2026-03-31", "reportedValue": {"raw": 2000}}],
            "quarterlyTotalLiabilitiesNetMinorityInterest": [{"asOfDate": "2026-03-31", "reportedValue": {"raw": 800}}],
            "quarterlyStockholdersEquity": [{"asOfDate": "2026-03-31", "reportedValue": {"raw": 1200}}],
            "quarterlyCurrentAssets": [{"asOfDate": "2026-03-31", "reportedValue": {"raw": 600}}],
            "quarterlyCurrentLiabilities": [{"asOfDate": "2026-03-31", "reportedValue": {"raw": 300}}],
        }
        rows = yahoo.financial_rows(series, fallback_shares=50)
        self.assertEqual(rows[0]["eps"], 2)
        self.assertEqual(rows[0]["eps_status"], "estimated")
        self.assertAlmostEqual(rows[0]["gross_margin"], 40)
        self.assertAlmostEqual(rows[0]["debt_ratio"], 40)
        self.assertAlmostEqual(rows[0]["current_ratio"], 200)

    def test_twse_chip_parsers(self):
        assets = {"00981A": {"name": "主動統一台股增長", "asset_class": "etf"}}
        institutional_rows = [{
            "證券代號": "00981A", "證券名稱": "主動統一台股增長",
            "外陸資買賣超股數(不含外資自營商)": "56,033,000",
            "投信買賣超股數": "0", "自營商買賣超股數": "-37,983,000",
            "三大法人買賣超股數": "18,050,000", "日期": "2026/07/21"
        }]
        parsed, market, traded = chips.parse_institutional(institutional_rows, assets, "https://twse.test/T86")
        self.assertEqual(parsed["00981A"]["institutional"]["foreign_net"], 56033)
        self.assertEqual(parsed["00981A"]["institutional"]["dealer_net"], -37983)
        self.assertEqual(market["total_net"], 18050)
        self.assertEqual(traded, "2026-07-21")
        margin_rows = [{
            "股票代號": "00981A", "股票名稱": "主動統一台股增長",
            "融資前日餘額": "172,882,000", "融資今日餘額": "175,408,000",
            "融券前日餘額": "4,924,000", "融券今日餘額": "3,950,000", "日期": "2026/07/27"
        }]
        parsed_margin, _ = chips.parse_margin(margin_rows, assets, "https://twse.test/margin")
        self.assertEqual(parsed_margin["00981A"]["margin"]["change"], 2526)
        self.assertEqual(parsed_margin["00981A"]["short"]["change"], -974)

    def test_yahoo_chip_history_parsers(self):
        asset = {"symbol": "00981A", "name": "主動統一台股增長", "asset_class": "etf", "exchange": "TWSE"}
        institutional_html = "<html><body><h2>法人逐日買賣超</h2><div>2026/07/21</div><div>56,033</div><div>0</div><div>-37,983</div><div>18,050</div><div>2.62%</div><div>7.03%</div><div>198,242</div><div>2026/07/20</div><div>3,874</div><div>0</div><div>-31,712</div><div>-27,838</div></body></html>"
        margin_html = "<html><body><h2>資券餘額逐日增減</h2><div>2026/07/27</div><div>2,526</div><div>175,408</div><div>7.18%</div><div>-974</div><div>3,950</div><div>0.16%</div><div>2.25%</div><div>108</div></body></html>"
        soups = [BeautifulSoup(institutional_html, "lxml"), BeautifulSoup(margin_html, "lxml")]
        with patch.object(chips, "fetch_soup", side_effect=soups):
            institutional = chips.parse_yahoo_institutional(asset)
            margin = chips.parse_yahoo_margin(asset)
        self.assertEqual(institutional["institutional"]["foreign_net"], 56033)
        self.assertEqual(len(institutional["history"]), 2)
        self.assertEqual(margin["margin"]["balance"], 175408)
        self.assertEqual(margin["short"]["change"], -974)

    def test_yahoo_daily_candle_parser(self):
        chart = {
            "timestamp": [1785801600, 1785888000],
            "indicators": {"quote": [{
                "open": [100, 102], "high": [105, 108], "low": [98, 101],
                "close": [103, 107], "volume": [1000, 1200]
            }]}
        }
        rows = market_snapshot.parse_yahoo_candles(chart, "index")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["open"], 102)
        self.assertEqual(rows[-1]["close"], 107)
        self.assertEqual(rows[-1]["source"], "Yahoo chart")

    def test_twse_taiex_payload_parser(self):
        payload = {"data": [["115/08/03", "28,100.00", "28,300.00", "27,950.00", "28,250.00"]]}
        rows = market_snapshot.parse_twse_payload(payload)
        self.assertEqual(rows[0]["date"], "2026-08-03")
        self.assertEqual(rows[0]["high"], 28300)
        self.assertEqual(rows[0]["source"], "TWSE official TAIEX history")

    def test_merge_candles_prefers_official(self):
        yahoo = [{"date": "2026-08-03", "close": 100, "source": "Yahoo chart"}]
        official = [{"date": "2026-08-03", "close": 101, "source": "TWSE official TAIEX history"}]
        rows = market_snapshot.merge_candles(official, yahoo)
        self.assertEqual(rows[0]["close"], 101)
        self.assertIn("TWSE", rows[0]["source"])

    def test_asia_risk_major_classification(self):
        row = news.classify("日圓跌至40年低點 日本企業倒閉增加", "日銀政策與企業成本壓力恐影響亞洲資金流向及台灣出口供應鏈", {}, "media")
        self.assertEqual(row["ai_topic"], "asia-risk")
        self.assertEqual(row["impact"], "high")
        self.assertTrue(row["is_major"])
        self.assertEqual(row["regional_risk"], "asia")


    def test_market_turnover_history_parser(self):
        payload={"fields":["日期","成交股數","成交金額"],"data":[["115/08/03","1,000","123,456,789"]]}
        rows=tw_market.history_records(payload,"twse_trade_value","TWSE test")
        self.assertEqual(rows[0]["date"],"2026-08-03")
        self.assertEqual(rows[0]["twse_trade_value"],123456789)

    def test_market_turnover_merge_sums_online_components(self):
        rows=tw_market.merge_history([], [
            {"date":"2026-08-03","twse_trade_value":100,"sources":["TWSE"]},
            {"date":"2026-08-03","tpex_trade_value":25,"sources":["TPEx"]},
        ], None)
        self.assertEqual(rows[0]["trade_value"],125)

    def test_news_archive_drops_pre_2026_and_keeps_old_major(self):
        base={"title":"聯準會重大利率決策影響全球市場","summary":"聯準會政策聲明可能影響美債、美元與全球股票市場。","url":"https://example.com/a","impact":"high","is_major":True,"importance_score":80}
        old={**base,"published_at":"2025-12-31T12:00:00+08:00"}
        kept={**base,"id":"b","url":"https://example.com/b","published_at":"2026-01-15T12:00:00+08:00"}
        rows=news.dedupe([old,kept])
        self.assertEqual([row["url"] for row in rows],["https://example.com/b"])

    def test_fomc_2026_calendar_parser(self):
        class Response:
            text='<html><body><h4>2026 FOMC Meetings</h4><div>January</div><div>27-28</div><div>March</div><div>17-18*</div><h4>2025 FOMC Meetings</h4></body></html>'
        with patch.object(event_updater,"http_get",return_value=Response()):
            result=event_updater.fetch_fomc(object())
        self.assertEqual(len(result.events),2)
        self.assertTrue(all(row["title"]=="美國聯準會 FOMC 利率決策" for row in result.events))

    def test_daily_change_uses_adjacent_candles(self):
        candles=[
            {"date":"2026-08-03","close":100},
            {"date":"2026-08-04","close":102},
            {"date":"2026-08-05","close":105},
        ]
        row=market_snapshot.daily_reference(candles,105,"2026-08-05")
        self.assertEqual(row["previous_close"],102)
        self.assertEqual(row["change"],3)
        self.assertAlmostEqual(row["change_percent"],3/102*100)

    def test_material_financial_report_uses_board_date_not_period_start(self):
        subject="提報董事會或經董事會決議日期:115/08/04 財務報告期間:115/01/01~115/06/30"
        day,basis=event_updater.choose_material_target_date(subject,"financial-report",event_updater.date(2026,8,5))
        self.assertEqual(day.isoformat(),"2026-08-04")
        self.assertEqual(basis,"explicit-labeled-date")

    def test_material_financial_report_falls_back_to_announcement_date(self):
        subject="本公司公布115年上半年財務報告，期間115/01/01至115/06/30"
        day,basis=event_updater.choose_material_target_date(subject,"financial-report",event_updater.date(2026,8,5))
        self.assertEqual(day.isoformat(),"2026-08-05")
        self.assertEqual(basis,"official-announcement-date")

    def test_news_symbols_require_official_master_and_longest_name(self):
        aliases={"南亞科":"2408","南亞":"1303","鴻海":"2317"}
        text="南亞科今年資本支出697億元；鴻海營收9465億元"
        self.assertEqual(news.infer_symbols(text,aliases),["2408","2317"])

    def test_bls_html_fallback_parser(self):
        class Response:
            text='<html><table><tr><td>Wednesday, August 12, 2026</td><td>08:30 AM</td><td>Consumer Price Index for July 2026</td></tr></table></html>'
        with patch.object(event_updater,"http_get",return_value=Response()):
            rows=event_updater.fetch_bls_html(object())
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["title"],"美國 CPI 通膨")
        self.assertEqual(rows[0]["date_basis"],"BLS official release schedule")

    def test_bea_table_parser(self):
        class Response:
            text='<html><table><tr><td>August 26</td><td>8:30 AM</td><td>News</td><td>GDP (Second Estimate) and Corporate Profits, 2nd Quarter 2026</td></tr></table></html>'
        with patch.object(event_updater,"http_get",return_value=Response()):
            result=event_updater.fetch_bea(object())
        self.assertEqual(len(result.events),1)
        self.assertEqual(result.events[0]["title"],"美國 GDP")

    def test_financial_coverage_is_separate_from_basic_coverage(self):
        import update_stock_basics
        row={"metrics":{"pe":10,"pb":1,"dividend_yield":3},"financials":[]}
        self.assertLess(update_stock_basics.financial_coverage(row),50)

    def test_same_session_live_ohlc_replaces_previous_daily_display(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        old=int(datetime(2026,8,4,16,0,tzinfo=ZoneInfo("America/New_York")).timestamp())
        current=int(datetime(2026,8,5,12,0,tzinfo=ZoneInfo("America/New_York")).timestamp())
        chart={
            "meta":{"regularMarketTime":current,"regularMarketPrice":107,"regularMarketOpen":103,"regularMarketDayHigh":108,"regularMarketDayLow":102,"regularMarketVolume":9000,"currency":"USD"},
            "timestamp":[old],
            "indicators":{"quote":[{"open":[100],"high":[105],"low":[98],"close":[102],"volume":[1000]}]}
        }
        row=market_snapshot.build_session_row(chart,"^GSPC","S&P 500","US","index")
        self.assertEqual(row["session_date"],"2026-08-05")
        self.assertEqual(row["open"],103)
        self.assertEqual(row["high"],108)
        self.assertEqual(row["previous_close"],102)
        self.assertEqual(row["change"],5)

    def test_same_session_validator_rejects_price_outside_high_low(self):
        row={"symbol":"X","price":110,"previous_close":100,"change":10,"change_percent":10,"session_date":"2026-08-05","price_date":"2026-08-05","ohlc_date":"2026-08-05","open":101,"high":108,"low":99,"close":107,"candles":[]}
        with self.assertRaises(ValueError):market_snapshot.validate_market_row(row)

    def test_tpex_dividend_plan_combined_company_schema(self):
        payload=[{
            "公司代號名稱":"6488 環球晶",
            "股利年度":"115",
            "期別":"年度",
            "董事會決議通過股利分派日":"115/08/07",
            "股東配發內容-盈餘分配之現金股利(元/股)":"10.5",
        }]
        rows=event_updater.parse_dividend_plans(payload,"TPEX",event_updater.TPEX_DIVIDEND_PLAN_URL,"tpex-dividend-plan")
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["symbol"],"6488")
        self.assertEqual(rows[0]["asset_name"],"環球晶")
        self.assertEqual(rows[0]["local_date"],"2026-08-07")
        self.assertEqual(rows[0]["cash_dividend"],10.5)
        self.assertIn("115 年度",rows[0]["fiscal_period"])

    def test_twse_historical_exdiv_parser(self):
        payload={"fields":["日期","股票代號","股票名稱","除權息","息值"],"data":[["115/06/02","2330","台積電","除息","5.0"]]}
        rows=event_updater.parse_twse_exdiv_history_payload(payload)
        self.assertEqual(rows[0]["local_date"] if "local_date" in rows[0] else rows[0]["ex_date"],"2026-06-02")
        self.assertEqual(rows[0]["symbol"],"2330")

    def test_tpex_historical_exdiv_parser(self):
        payload=[{"ExRrightsExDividendDate":"115/06/03","SecuritiesCompanyCode":"6488","CompanyName":"環球晶","ExRrightsExDividend":"除息","CashDividend":"10"}]
        rows=event_updater.parse_tpex_exdiv_history_payload(payload)
        self.assertEqual(rows[0]["ex_date"],"2026-06-03")
        self.assertEqual(rows[0]["cash_dividend"],10)

if __name__ == "__main__":
    unittest.main()


def test_nikkei_official_csv_parser():
    import sys
    sys.path.insert(0,str(ROOT/"scripts"))
    import update_market_snapshot as market
    class Response:
        content=b"Date,Open,High,Low,Close\n2026/08/06,65565.27,66302.52,64555.52,65685.22\n2026/08/07,65250.00,65500.00,64800.00,65210.13\n"
        def raise_for_status(self): return None
    class Session:
        def get(self,*args,**kwargs): return Response()
    rows=market.fetch_nikkei_official(Session())
    assert rows[-1]["date"]=="2026-08-07"
    assert rows[-1]["close"]==65210.13
    assert rows[-1]["source"]=="Nikkei official daily data"
