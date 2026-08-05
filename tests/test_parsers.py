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


if __name__ == "__main__":
    unittest.main()
