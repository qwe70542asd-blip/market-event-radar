import importlib.util
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_tw_market.py"
SPEC = importlib.util.spec_from_file_location("update_tw_market", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TaiwanMarketTests(unittest.TestCase):
    def test_security_universe_excludes_warrants(self):
        self.assertEqual(MODULE.security_code("2330"), "2330")
        self.assertEqual(MODULE.security_code("0050"), "0050")
        self.assertEqual(MODULE.security_code("00631L"), "00631L")
        self.assertEqual(MODULE.security_code("03001P"), "")

    def test_mis_quote_fields_and_percent(self):
        row = {
            "c": "1101", "n": "台泥", "ex": "tse", "z": "24.3000", "y": "24.0500",
            "o": "24.3500", "h": "24.8000", "l": "24.2500", "v": "24497",
            "d": "20260731", "t": "13:30:00", "tlong": "1785479400000",
        }
        parsed = MODULE.parse_mis_row(row)
        self.assertEqual(parsed["symbol"], "1101")
        self.assertEqual(parsed["exchange"], "TWSE")
        self.assertAlmostEqual(parsed["change"], 0.25)
        self.assertAlmostEqual(parsed["change_percent"], 0.25 / 24.05 * 100)
        self.assertEqual(parsed["volume"], 24497)

    def test_mis_uses_best_bid_when_last_trade_is_blank(self):
        row = {"c": "2330", "n": "台積電", "ex": "tse", "z": "-", "b": "1190_1185_", "a": "1195_1200_", "y": "1180"}
        parsed = MODULE.parse_mis_row(row)
        self.assertEqual(parsed["price"], 1190)
        self.assertAlmostEqual(parsed["change_percent"], 10 / 1180 * 100)

    def test_daily_fallback_converts_shares_to_lots(self):
        row = {
            "Code": "2330", "Name": "台積電", "ClosingPrice": "1180", "Change": "10",
            "OpeningPrice": "1170", "HighestPrice": "1190", "LowestPrice": "1165",
            "TradeVolume": "24567000", "TradeValue": "28900000000",
        }
        parsed = MODULE.parse_daily_row(row, "TWSE")
        self.assertEqual(parsed["volume"], 24567)
        self.assertEqual(parsed["previous_close"], 1170)
        self.assertAlmostEqual(parsed["change_percent"], 10 / 1170 * 100)

    def test_market_session_uses_taipei_time(self):
        tz = ZoneInfo("Asia/Taipei")
        self.assertEqual(MODULE.market_status(datetime(2026, 8, 3, 8, 45, tzinfo=tz)), "preopen")
        self.assertEqual(MODULE.market_status(datetime(2026, 8, 3, 9, 0, tzinfo=tz)), "trading")
        self.assertEqual(MODULE.market_status(datetime(2026, 8, 3, 13, 30, tzinfo=tz)), "trading")
        self.assertEqual(MODULE.market_status(datetime(2026, 8, 2, 10, 0, tzinfo=tz)), "closed")


if __name__ == "__main__":
    unittest.main()
