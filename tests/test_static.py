
import importlib.util
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

class StaticTests(unittest.TestCase):
    def test_json(self):
        for path in (ROOT/"data").glob("*.json"):
            json.loads(path.read_text(encoding="utf-8"))

    def test_etf_identities(self):
        assets=json.loads((ROOT/"data/assets.json").read_text(encoding="utf-8"))["assets"]
        by_symbol={row["symbol"]:row for row in assets}
        self.assertEqual(by_symbol["00403A"]["name"],"主動統一升級50")
        self.assertEqual(by_symbol["009816"]["name"],"凱基台灣TOP50")
        self.assertEqual(by_symbol["00981A"]["name"],"主動統一台股增長")

    def test_no_fake_quotes(self):
        rows=json.loads((ROOT/"data/tw-market.json").read_text(encoding="utf-8"))["items"]
        self.assertTrue(all(row["price"] is None for row in rows))

    def test_compact_clean_layout(self):
        css=(ROOT/"assets/styles.css").read_text(encoding="utf-8")
        self.assertIn(".noise { display:none !important; }",css)
        self.assertIn("grid-template-columns:repeat(auto-fit,minmax(180px,1fr))",css)

    def test_twse_readable_news_route(self):
        shared=(ROOT/"assets/shared.js").read_text(encoding="utf-8")
        self.assertIn('newsDetail',shared)
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

if __name__=="__main__":
    unittest.main()
