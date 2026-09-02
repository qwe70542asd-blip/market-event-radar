from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("update_channel_health", ROOT / "scripts/update_channel_health.py")
health = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(health)
TZ = ZoneInfo("Asia/Taipei")


def set_now(text: str) -> None:
    health.NOW = datetime.fromisoformat(text).replace(tzinfo=TZ)


def test_computed_stale_beats_missing_status():
    set_now("2026-09-02T14:00:00")
    row = health.classify("events.json", {"metadata": {"updated_at": "2026-09-01T12:00:00+08:00"}, "events": [{"id": 1}]}, 3600)
    assert row["status"] == "stale"
    assert row["stale"] is True


def test_fresh_nonempty_payload_without_status_is_inferred_fresh():
    set_now("2026-09-02T14:00:00")
    row = health.classify("assets.json", {"metadata": {"updated_at": "2026-09-02T13:55:00+08:00"}, "assets": [{"symbol": "2330"}]}, 3600)
    assert row["status"] == "fresh"
    assert any("fresh inferred" in reason for reason in row["reasons"])


def test_closed_market_uses_relaxed_sla_but_open_market_does_not():
    set_now("2026-09-02T14:00:00")
    base = {"metadata": {"updated_at": "2026-09-02T12:40:00+08:00"}, "items": [{"symbol": "^TWII", "market_open": False}]}
    closed = health.classify("market-snapshot.json", base, 1200)
    assert closed["status"] == "fresh"
    assert closed["effective_max_age_seconds"] >= 12 * 3600
    opened = health.classify("market-snapshot.json", {**base, "items": [{"symbol": "^TWII", "market_open": True}]}, 1200)
    assert opened["status"] == "stale"
    assert opened["effective_max_age_seconds"] == 1200


def test_mixed_chip_component_dates_downgrade_channel():
    set_now("2026-09-02T14:00:00")
    payload = {
        "metadata": {"updated_at": "2026-09-02T13:55:00+08:00", "trading_date": "2026-09-02", "status": "ok"},
        "markets": {"twse": {"institutional_date": "2026-09-02"}, "tpex": {"day_trading_date": "2026-09-01"}},
        "items": {"2330": {"symbol": "2330"}},
    }
    row = health.classify("tw-chips.json", payload, 72 * 3600)
    assert row["status"] == "partial"
    assert row["date_mismatch_samples"] == ["tpex.day_trading_date=2026-09-01"]


def test_yahoo_large_stale_ratio_is_degraded():
    set_now("2026-09-02T14:00:00")
    items = {str(i): {"updated_at": "2026-08-20T10:00:00+08:00"} for i in range(10)}
    payload = {"metadata": {"updated_at": "2026-09-02T13:55:00+08:00", "status": "ok"}, "items": items}
    row = health.classify("yahoo-details.json", payload, 96 * 3600)
    assert row["status"] == "degraded"
    assert row["stale_item_count"] == 10
