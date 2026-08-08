from datetime import timedelta
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
if str(SCRIPTS) not in sys.path: sys.path.insert(0,str(SCRIPTS))

import update_market_klines
import update_tw_market


class MarketIntegrityTests(unittest.TestCase):
    def test_quote_total_is_attached_only_to_verified_date(self):
        rows=update_tw_market.merge_history(
            [{'date':'2026-08-07','trade_value':1000,'source':'old'}],
            [],1200,'2026-08-07'
        )
        dates={row['date'] for row in rows}
        self.assertIn('2026-08-07',dates)
        self.assertNotIn('2026-08-08',dates)

    def test_no_unverified_current_date_is_inserted(self):
        rows=update_tw_market.merge_history([],[],1200,None)
        self.assertEqual(rows,[])

    def test_recent_interval_is_reused(self):
        entry={'candles':[{'close':1},{'close':2}], 'updated_at':update_market_klines.NOW.isoformat(timespec='seconds')}
        self.assertTrue(update_market_klines.retained_is_fresh(entry,'15m'))

    def test_stale_interval_is_refetched(self):
        old=update_market_klines.NOW-timedelta(hours=2)
        entry={'candles':[{'close':1},{'close':2}], 'updated_at':old.isoformat(timespec='seconds')}
        self.assertFalse(update_market_klines.retained_is_fresh(entry,'15m'))


if __name__=='__main__': unittest.main()
