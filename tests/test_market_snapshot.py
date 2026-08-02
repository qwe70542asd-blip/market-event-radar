import unittest
import sys
import types
from datetime import datetime
from zoneinfo import ZoneInfo

# The production workflow installs these dependencies. The local unit tests do
# not call their network/HTML features, so lightweight stubs keep this test
# runnable in a minimal Python environment too.
if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = object
    requests_stub.Response = object
    sys.modules["requests"] = requests_stub
if "bs4" not in sys.modules:
    bs4_stub = types.ModuleType("bs4")
    bs4_stub.BeautifulSoup = object
    sys.modules["bs4"] = bs4_stub

from scripts import update_market_snapshot as market


class StubResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class StubSession:
    def __init__(self, payload):
        self.payload = payload

    def get(self, *args, **kwargs):
        return StubResponse(self.payload)


class MarketSnapshotTests(unittest.TestCase):
    def test_yahoo_uses_timestamp_aligned_daily_closes(self):
        ny = ZoneInfo("America/New_York")
        timestamps = [
            int(datetime(2026, 7, 30, 9, 30, tzinfo=ny).timestamp()),
            int(datetime(2026, 7, 31, 9, 30, tzinfo=ny).timestamp()),
        ]
        payload = {
            "chart": {"result": [{
                "meta": {"exchangeTimezoneName": "America/New_York", "regularMarketPrice": 9999},
                "timestamp": timestamps,
                "indicators": {"quote": [{"close": [100, 104]}]},
            }]}
        }
        item = market.fetch_yahoo(
            StubSession(payload), "SP500", "^GSPC", market.INDEX_META["SP500"]
        )
        self.assertEqual(item["value"], 104)
        self.assertEqual(item["previous"], 100)
        self.assertEqual(item["trading_date"], "2026-07-31")

    def test_older_source_date_cannot_replace_newer_saved_date(self):
        old = {"SP500": {"id": "SP500", "value": 110, "trading_date": "2026-08-01", "as_of": "2026-08-01"}}
        candidate = market.make_item(
            "SP500", market.INDEX_META["SP500"], value=90, previous=89,
            as_of="2026-07-31", source="test", source_url="", delay="test",
        )
        kept = market.use_latest(old, candidate)
        self.assertEqual(kept["value"], 110)
        self.assertEqual(kept["trading_date"], "2026-08-01")

    def test_same_day_correction_replaces_saved_value(self):
        old = {"SP500": {"id": "SP500", "value": 100, "trading_date": "2026-07-31", "as_of": "2026-07-31"}}
        candidate = market.make_item(
            "SP500", market.INDEX_META["SP500"], value=101, previous=99,
            as_of="2026-07-31", source="test", source_url="", delay="test",
        )
        accepted = market.use_latest(old, candidate)
        self.assertEqual(accepted["value"], 101)

    def test_tw_etf_ranking_uses_official_trading_value(self):
        quotes = {}
        for index in range(1, 18):
            code = f"00{index:03d}"
            quotes[code] = {
                "Code": code,
                "Name": f"ETF {index}",
                "ClosingPrice": str(20 + index),
                "TradeValue": str(index * 1_000_000),
            }
        ranking, trade_day = market.rank_tw_etfs_from_quotes(quotes, "2026-07-31")
        self.assertEqual(len(ranking), 15)
        self.assertEqual(ranking[0][0], "00017")
        self.assertEqual(trade_day, "2026-07-31")


if __name__ == "__main__":
    unittest.main()
