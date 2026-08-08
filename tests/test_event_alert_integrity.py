from __future__ import annotations

import importlib.util
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
