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



    def test_nested_weekend_chip_sources_are_removed(self):
        items={"00403A":{"symbol":"00403A","date":"2026-08-07","sources":[{"name":"bad","date":"2026-08-08"},{"name":"good","date":"2026-08-07"}],"history":[{"date":"2026-08-08"},{"date":"2026-08-07"}]}}
        cleaned,removed=update_tw_chips.sanitize_item_dates(items)
        self.assertGreaterEqual(removed,2)
        self.assertEqual([row["date"] for row in cleaned["00403A"]["sources"]],["2026-08-07"])
        self.assertEqual([row["date"] for row in cleaned["00403A"]["history"]],["2026-08-07"])

    def test_quote_total_beats_partial_single_market_component(self):
        rows=update_tw_market.merge_history(
            [],
            [{'date':'2026-08-07','twse_trade_value':1000,'sources':['TWSE OpenAPI']}],
            1250,
            '2026-08-07',
        )
        self.assertEqual(rows[0]['trade_value'],1250)
        self.assertTrue(rows[0]['complete_total'])
        self.assertEqual(rows[0]['total_coverage'],'twse+tpex-quote-sum')

    def test_partial_single_market_is_not_complete(self):
        rows=update_tw_market.merge_history(
            [],
            [{'date':'2026-08-07','twse_trade_value':1000,'sources':['TWSE OpenAPI']}],
            None,
            None,
        )
        self.assertEqual(rows[0]['trade_value'],1000)
        self.assertFalse(rows[0]['complete_total'])
        self.assertEqual(rows[0]['total_coverage'],'partial-single-market')

    def test_recent_history_completeness_rejects_large_gap(self):
        from datetime import date
        end=date(2026,8,7)
        good=[]
        cursor=end
        while len(good)<21:
            if cursor.weekday()<5:
                good.append({'date':cursor.isoformat(),'complete_total':True,'trade_value':1})
            cursor-=timedelta(days=1)
        self.assertTrue(update_tw_market.recent_history_complete(good,'2026-08-07',21,45))
        gapped=good[:5]+[{'date':(date(2026,6,30)-timedelta(days=i)).isoformat(),'complete_total':True,'trade_value':1} for i in range(30) if (date(2026,6,30)-timedelta(days=i)).weekday()<5]
        self.assertFalse(update_tw_market.recent_history_complete(gapped,'2026-08-07',21,45))

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


    def test_legacy_source_label_does_not_make_partial_total_complete(self):
        old = [{
            "date": "2026-08-06",
            "trade_value": 974054973424,
            "twse_trade_value": 974054973424,
            "tpex_trade_value": None,
            "source": "TWSE/TPEx official close quote sum + TWSE OpenAPI FMTQIK",
        }]
        rows = update_tw_market.merge_history(old, [], None, "2026-08-07")
        row = next(item for item in rows if item["date"] == "2026-08-06")
        self.assertFalse(row["complete_total"])
        self.assertEqual(row["total_coverage"], "legacy-total-unverified")


if __name__=='__main__': unittest.main()
