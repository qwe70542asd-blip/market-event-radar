from __future__ import annotations

import importlib.util
import sys
import unittest
import json
import tempfile
from unittest import mock
from datetime import datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("update_events", ROOT / "scripts" / "update_events.py")
update_events = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = update_events
SPEC.loader.exec_module(update_events)


class EventAlertIntegrityTests(unittest.TestCase):
    def iso(self, day, hour=9):
        return datetime.combine(day, time(hour, 0), tzinfo=update_events.TAIPEI).isoformat(timespec="seconds")

    def row(self, day, **extra):
        value = {
            "start": self.iso(day),
            "origin": "bea",
            "event_type": "economic-release",
            "date_basis": "BEA official release schedule",
        }
        value.update(extra)
        return value

    def test_historical_backfill_is_not_new_announcement(self):
        today = update_events.NOW.date()
        self.assertIsNone(update_events.announcement_candidate(self.row(today - timedelta(days=30)), None, today))

    def test_new_future_schedule_is_new_date(self):
        today = update_events.NOW.date()
        candidate = update_events.announcement_candidate(self.row(today + timedelta(days=14)), None, today)
        self.assertEqual(candidate, ("new-date", None))

    def test_reused_periodic_key_after_old_occurrence_is_not_date_changed(self):
        today = update_events.NOW.date()
        current = self.row(today + timedelta(days=20))
        old_state = {"start": self.iso(today - timedelta(days=20))}
        candidate = update_events.announcement_candidate(current, old_state, today)
        self.assertEqual(candidate, ("new-date", None))

    def test_future_reschedule_is_date_changed(self):
        today = update_events.NOW.date()
        current = self.row(today + timedelta(days=22))
        old_state = {"start": self.iso(today + timedelta(days=15))}
        candidate = update_events.announcement_candidate(current, old_state, today)
        self.assertEqual(candidate[0], "date-changed")
        self.assertEqual(candidate[1][:10], (today + timedelta(days=15)).isoformat())

    def test_old_source_publication_does_not_become_new_date_after_parser_backfill(self):
        today = update_events.NOW.date()
        current = self.row(
            today + timedelta(days=20),
            source_published_at=self.iso(today - timedelta(days=10)),
            origin="twse-material",
            event_type="investor-conference",
            date_basis="explicit-labeled-date",
        )
        self.assertIsNone(update_events.announcement_candidate(current, None, today))

    def test_ordinary_financial_report_announcement_is_not_date_alert(self):
        today = update_events.NOW.date()
        current = self.row(
            today,
            origin="twse-material",
            event_type="financial-report",
            date_basis="official-announcement-date",
        )
        self.assertIsNone(update_events.announcement_candidate(current, None, today))

    def test_semantic_guard_rejects_past_previous_date(self):
        today = update_events.NOW.date()
        current = self.row(
            today + timedelta(days=10),
            announced_at=self.iso(today),
            announcement_kind="date-changed",
            previous_start=self.iso(today - timedelta(days=1)),
        )
        self.assertFalse(update_events.announcement_semantically_valid(current, today))

    def test_bea_recurring_occurrences_receive_distinct_tracking_keys(self):
        today = update_events.NOW.date()
        rows = []
        for offset in (20, 50):
            start = datetime.combine(today + timedelta(days=offset), time(20, 30), tzinfo=update_events.TAIPEI)
            rows.append(update_events.make_event(
                event_id="temp", tracking_key="bea|pce|pending", title="美國個人所得與支出／PCE", start=start,
                category="macro", event_type="economic-release", event_group="macro", region="US", impact="high",
                description="", market_effect="", source_name="U.S. BEA", source_url=update_events.BEA_URL, origin="bea",
                tags=["BEA", "Personal Income and Outlays"], _tracking_series="pce", _tracking_period="",
            ))
        assigned = update_events.assign_bea_tracking(rows)
        keys = [row["tracking_key"] for row in assigned]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertTrue(all(key.startswith("bea|pce|") for key in keys))

    def test_bls_release_page_fallback_parses_reference_month_and_release_date(self):
        class Response:
            def __init__(self,text): self.text=text
        def fake_get(session,url,**kwargs):
            if url.endswith('/cpi.htm'):
                return Response('<table><tr><th>Reference Month</th><th>Release Date</th><th>Release Time</th></tr><tr><td>July 2026</td><td>Aug. 12, 2026</td><td>08:30 AM</td></tr></table>')
            return Response('<html><body>No scheduled rows</body></html>')
        with mock.patch.object(update_events,'http_get',fake_get):
            rows=update_events.fetch_bls_release_pages(object())
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['tracking_key'],'bls|cpi|2026-jul')
        self.assertEqual(rows[0]['local_date'],'2026-08-12')

    def test_bls_tracking_uses_reference_period(self):
        start = datetime(2026, 8, 12, 20, 30, tzinfo=update_events.TAIPEI)
        row = update_events._bls_event("Consumer Price Index for July 2026", start, "")
        self.assertIsNotNone(row)
        self.assertIn("bls|cpi|2026-jul", row["tracking_key"])

    def test_bea_official_schedule_rows_parse_with_stable_period_keys(self):
        html='''<table>
        <tr><td>August 26 8:30 AM</td><td>N ews</td><td>Personal Income and Outlays, July 2026</td></tr>
        <tr><td>September 30 8:30 AM</td><td>N ews</td><td>GDP (Third Estimate), Industries, Corporate Profits, State GDP, and State Personal Income, 2nd Quarter 2026; State PCE, 2025</td></tr>
        </table>'''
        class Response:
            text=html
        with mock.patch.object(update_events,'http_get',lambda session,url,**kwargs: Response()):
            result=update_events.fetch_bea(object())
        keys={row['tracking_key'] for row in result.events}
        self.assertIn('bea|pce|2026|2026-jul',keys)
        self.assertIn('bea|gdp-third|2026|2026-q2',keys)

    def test_bea_flat_text_fallback_keeps_reference_month_in_title(self):
        html='<div>August 26 8:30 AM N ews Personal Income and Outlays, July 2026 September 3 8:30 AM N ews U.S. International Trade in Goods and Services, July 2026</div>'
        class Response:
            text=html
        with mock.patch.object(update_events,'http_get',lambda session,url,**kwargs: Response()):
            result=update_events.fetch_bea(object())
        keys={row['tracking_key'] for row in result.events}
        self.assertIn('bea|pce|2026|2026-jul',keys)
        self.assertIn('bea|trade|2026|2026-jul',keys)

    def test_bea_gdp_title_with_state_pce_stays_gdp_series(self):
        raw="GDP (Third Estimate), Industries, Corporate Profits, State GDP, and State Personal Income, 2nd Quarter 2026; State PCE, 2025"
        self.assertEqual(update_events.bea_series_key(raw),"gdp-third")
        self.assertEqual(update_events.release_period_token(raw),"2026-q2")

    def test_manual_and_official_pce_share_canonical_key(self):
        start = datetime(2026, 8, 26, 20, 30, tzinfo=update_events.TAIPEI).isoformat(timespec="seconds")
        manual = {"start": start, "local_date": "2026-08-26", "title": "美國 7 月 PCE 物價與個人所得支出", "region": "US", "event_group": "macro", "tags": ["PCE"], "origin": "manual"}
        official = {"start": start, "local_date": "2026-08-26", "title": "美國個人所得與支出／PCE", "region": "US", "event_group": "macro", "tags": ["BEA", "Personal Income and Outlays"], "origin": "bea"}
        self.assertEqual(update_events.canonical_event_key(manual), update_events.canonical_event_key(official))

    def test_v11431_false_bea_state_is_baselined_during_v11432_migration(self):
        today = update_events.NOW.date()
        start = datetime.combine(today + timedelta(days=18), time(20, 30), tzinfo=update_events.TAIPEI)
        official = update_events.make_event(
            event_id="bea-new", tracking_key="bea|pce|2026|2026-jul", title="美國個人所得與支出／PCE", start=start,
            category="macro", event_type="economic-release", event_group="macro", region="US", impact="high",
            description="official", market_effect="", source_name="U.S. BEA", source_url=update_events.BEA_URL, origin="bea",
            tags=["BEA", "Personal Income and Outlays, July 2026"], date_basis="BEA official release schedule",
        )
        false_old = {**official,
            "id":"bea-old", "tracking_key":"bea|n ews | personal income and outlays,",
            "announced_at":update_events.NOW.isoformat(timespec="seconds"),
            "announcement_kind":"date-changed", "announcement_status":"date_changed_today",
            "previous_start":"2026-12-23T21:30:00+08:00",
        }
        empty = lambda key, origin: update_events.SourceResult(key, key, "", (origin,), [])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); data=root/"data"; data.mkdir()
            events_path=data/"events.json"; seed_path=data/"events-seed.js"; manual_path=data/"manual-events.json"; state_path=data/"event-source-state.json"
            events_path.write_text(json.dumps({"events":[false_old],"sources":[]},ensure_ascii=False),encoding="utf-8")
            manual_path.write_text("[]",encoding="utf-8")
            state_path.write_text(json.dumps({
                "initialized":True,"tracking_key_version":1,"initialized_origins":["bea","bls"],
                "events":{"bea|n ews | personal income and outlays,":{"start":"2026-12-23T21:30:00+08:00","origin":"bea"}},
            }),encoding="utf-8")
            patches={
                "fetch_bls":lambda session: empty("bls","bls"),
                "fetch_bea":lambda session: update_events.SourceResult("bea","bea",update_events.BEA_URL,("bea",),[official]),
                "fetch_fomc":lambda session: empty("fomc","fomc"),
                "fetch_twse_exdiv":lambda session: empty("twse-exdiv","twse-exdiv"),
                "fetch_tpex_exdiv":lambda session: empty("tpex-exdiv","tpex-exdiv"),
                "fetch_twse_exdiv_history":lambda session: empty("twse-exdiv-history","twse-exdiv-history"),
                "fetch_tpex_exdiv_history":lambda session: empty("tpex-exdiv-history","tpex-exdiv-history"),
                "fetch_twse_dividend_plans":lambda session: empty("twse-dividend-plan","twse-dividend-plan"),
                "fetch_tpex_dividend_plans":lambda session: empty("tpex-dividend-plan","tpex-dividend-plan"),
                "fetch_twse_material":lambda session: empty("twse-material","twse-material"),
                "fetch_tpex_material":lambda session: empty("tpex-material","tpex-material"),
            }
            with mock.patch.multiple(update_events, DATA=data, EVENTS_PATH=events_path, SEED_PATH=seed_path, MANUAL_PATH=manual_path, STATE_PATH=state_path, **patches):
                update_events.main()
            payload=json.loads(events_path.read_text(encoding="utf-8")); state=json.loads(state_path.read_text(encoding="utf-8"))
            pce=[row for row in payload["events"] if row.get("origin")=="bea" and "PCE" in row.get("title","")]
            self.assertEqual(len(pce),1)
            self.assertEqual(pce[0]["tracking_key"],"bea|pce|2026|2026-jul")
            self.assertNotIn("announcement_kind",pce[0])
            self.assertEqual(payload["metadata"]["announced_today_count"],0)
            self.assertEqual(state["tracking_key_version"],2)
            self.assertNotIn("bea|n ews | personal income and outlays,",state["events"])

    def test_incremental_daily_source_retains_old_verified_archive_rows(self):
        today=update_events.NOW.date()
        old={"id":"old-material","tracking_key":"twse-material|2330|investor-conference|old","origin":"twse-material","start":self.iso(today-timedelta(days=20)),"title":"old"}
        new={"id":"new-material","tracking_key":"twse-material|2454|investor-conference|new","origin":"twse-material","start":self.iso(today),"title":"new"}
        merged=update_events.merge_incremental_archive([old],[new],["twse-material"])
        self.assertEqual({row['id'] for row in merged},{'old-material','new-material'})

    def test_incremental_source_replaces_same_tracking_future_reschedule(self):
        today=update_events.NOW.date()
        old={"id":"old-future","tracking_key":"tpex-exdiv-history|1234|除息","origin":"tpex-exdiv-history","start":self.iso(today+timedelta(days=10)),"title":"old"}
        new={"id":"new-future","tracking_key":"tpex-exdiv-history|1234|除息","origin":"tpex-exdiv-history","start":self.iso(today+timedelta(days=12)),"title":"new"}
        merged=update_events.merge_incremental_archive([old],[new],["tpex-exdiv-history"])
        self.assertEqual([row['id'] for row in merged],['new-future'])

    def test_dividend_decision_and_payment_same_day_do_not_collapse(self):
        base={"start":"2026-08-20T09:00:00+08:00","local_date":"2026-08-20","symbol":"2330","event_group":"dividend","region":"TW"}
        decision={**base,"title":"2330 台積電 股利方案決議","category":"dividend-decision","event_type":"dividend-decision"}
        payment={**base,"title":"2330 台積電 8/20 股利發放","category":"dividend-payment","event_type":"dividend-payment"}
        self.assertNotEqual(update_events.canonical_event_key(decision),update_events.canonical_event_key(payment))

    def test_twse_post_20260427_exdiv_history_schema_uses_right_slash_dividend_field(self):
        payload={
            "fields":["資料日期","股票代號","股票名稱","除權息前收盤價","除權息參考價","權值+息值","權/息"],
            "data":[
                ["115年05月14日","01002T","土銀國泰R1","14.68","14.22","0.457505","息"],
                ["115年05月14日","8033","雷虎","140.00","137.66","2.332507","權"],
            ],
        }
        rows=update_events.parse_twse_exdiv_history_payload(payload)
        self.assertEqual(len(rows),2)
        by_symbol={row['symbol']:row for row in rows}
        self.assertEqual(by_symbol['01002T']['cash_dividend'],0.457505)
        self.assertNotIn('stock_dividend_ratio',by_symbol['8033'])
        self.assertIn('除權',by_symbol['8033']['title'])

    def test_twse_exdiv_history_fetch_uses_supported_date_range_params(self):
        calls=[]
        class Response:
            url=update_events.TWSE_EXDIV_HISTORY_URL
            def json(self):
                return {"fields":["資料日期","股票代號","股票名稱","權值+息值","權/息"],"data":[["115年01月05日","2330","台積電","1.0","息"]]}
        def fake_get(session,url,**kwargs):
            calls.append(kwargs.get('params') or {})
            return Response()
        with mock.patch.object(update_events,'http_get',fake_get):
            result=update_events.fetch_twse_exdiv_history(object())
        self.assertTrue(result.events)
        self.assertEqual(len(calls),1)
        self.assertTrue(all('strDate' in params and 'endDate' in params for params in calls))
        self.assertTrue(all('date' not in params for params in calls))

    def test_tpex_dividend_aliases_are_recognized(self):
        row = {
            "公司代號": "1234", "公司名稱": "測試公司", "年度": "115",
            "董事會日期": "115/08/07",
            "股東配發-盈餘分配之現金股利(元/股)": "2.5",
        }
        events = update_events.parse_dividend_plans([row], "TPEX", update_events.TPEX_DIVIDEND_PLAN_URL, "tpex-dividend-plan")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["symbol"], "1234")
        self.assertEqual(events[0]["cash_dividend"], 2.5)


if __name__ == "__main__":
    unittest.main()

class EventArchiveRegressionBarrierTests(unittest.TestCase):
    def test_catastrophic_nonempty_archive_shrink_is_blocked(self):
        previous=[{"id":str(i)} for i in range(100)]
        current=[{"id":str(i)} for i in range(60)]
        with self.assertRaises(SystemExit):
            update_events.assert_event_archive_not_catastrophically_shrunk(previous,current)

    def test_normal_archive_dedup_churn_is_allowed(self):
        previous=[{"id":str(i)} for i in range(100)]
        current=[{"id":str(i)} for i in range(90)]
        update_events.assert_event_archive_not_catastrophically_shrunk(previous,current)
