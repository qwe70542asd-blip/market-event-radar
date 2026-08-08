from datetime import timedelta
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
if str(SCRIPTS) not in sys.path: sys.path.insert(0,str(SCRIPTS))

import update_market_klines
import update_tw_market
import update_tw_chips


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

    def test_legacy_weekend_turnover_row_is_removed(self):
        rows=update_tw_market.merge_history(
            [
                {'date':'2026-08-08','trade_value':9999,'source':'legacy-bad'},
                {'date':'2026-08-07','trade_value':1000,'source':'legacy-good'},
            ], [], None, None
        )
        self.assertEqual([row['date'] for row in rows], ['2026-08-07'])
        self.assertIsNone(update_tw_market.valid_session_date('2026-08-08'))

    def test_retained_turnover_newer_than_verified_session_is_removed(self):
        rows=update_tw_market.trim_history_to_trading_date(
            [
                {'date':'2026-08-10','trade_value':9999},
                {'date':'2026-08-07','trade_value':1000},
            ],
            '2026-08-07',
        )
        self.assertEqual([row['date'] for row in rows], ['2026-08-07'])

    def test_tw_chips_prefixed_key_and_old_schema_migrate(self):
        items,migrated=update_tw_chips.migrate_legacy_items({
            'twse:2330': {
                'symbol':'2330','foreign_net':1200,'trust_net':-20,'dealer_net':10,'total_net':1190,
                'day_trading':{'volume':500,'volume_ratio_percent':12.5},
                'date':'2026-08-08',
                'history':[{'date':'2026-08-07','institutional':{'foreign_net':1000}},{'date':'2026-08-08','institutional':{'foreign_net':2000}}],
            }
        })
        self.assertEqual(migrated,1)
        self.assertEqual(set(items),{'2330'})
        self.assertEqual(items['2330']['institutional']['foreign_net'],1200)
        self.assertEqual(items['2330']['day_trade']['ratio'],12.5)
        self.assertNotIn('date',items['2330'])
        self.assertEqual([row['date'] for row in items['2330']['history']],['2026-08-07'])

    def test_tw_chips_market_weekend_date_is_removed(self):
        markets,removed=update_tw_chips.sanitize_market_dates({'twse':{'institutional_date':'2026-08-08','stock_count':1000}})
        self.assertEqual(removed,1)
        self.assertNotIn('institutional_date',markets['twse'])


if __name__=='__main__': unittest.main()
