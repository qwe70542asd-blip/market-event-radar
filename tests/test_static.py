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

if __name__=="__main__":
    unittest.main()
