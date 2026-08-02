from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("update_news", ROOT / "scripts" / "update_news.py")
news = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(news)


def test_google_queries_request_twenty_day_backfill():
    url = news.google_url({
        "query": "site:example.com 財經",
        "hl": "zh-TW",
        "gl": "TW",
        "ceid": "TW:zh-Hant",
    })
    assert "when%3A20d" in url


def test_rolling_retention_removes_only_items_older_than_twenty_days():
    now = datetime(2026, 8, 2, 12, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    news.NOW = now
    kept = {"published_at": (now - timedelta(days=19, hours=23)).isoformat()}
    expired = {"published_at": (now - timedelta(days=20, seconds=1)).isoformat()}
    assert news.still_recent(kept, news.NEWS_RETENTION_DAYS)
    assert not news.still_recent(expired, news.NEWS_RETENTION_DAYS)


def test_same_headline_merges_sources_and_keeps_best_link():
    published = "2026-08-02T09:00:00+08:00"
    low = {
        "title": "台股盤中大漲，電子權值領軍",
        "source": "轉載媒體",
        "source_group": "tw-media",
        "origin": "publisher-search",
        "quality_score": 70,
        "published_at": published,
    }
    high = {
        **low,
        "source": "中央社",
        "origin": "direct-rss",
        "quality_score": 96,
    }
    rows, removed = news.deduplicate_headlines([low, high])
    assert removed == 1
    assert len(rows) == 1
    assert rows[0]["source"] == "中央社"
    assert rows[0]["duplicate_count"] == 1
    assert set(rows[0]["duplicate_sources"]) == {"中央社", "轉載媒體"}


def test_ai_event_merge_uses_event_key_only_inside_time_window():
    first = {"id":"a","title":"台積電法說公布展望","source":"中央社","event_key":"tsmc-guidance","published_at":"2026-08-01T10:00:00+08:00"}
    duplicate = {"id":"b","title":"TSMC gives updated guidance","source":"Reuters","event_key":"tsmc-guidance","published_at":"2026-08-01T12:00:00+08:00"}
    later = {"id":"c","title":"台積電下一季再更新展望","source":"中央社","event_key":"tsmc-guidance","published_at":"2026-08-10T10:00:00+08:00"}
    rows, removed = news.merge_ai_events([first, duplicate, later])
    assert removed == 1
    assert len(rows) == 2
