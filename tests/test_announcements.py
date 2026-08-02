from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("update_announcements", ROOT / "scripts" / "update_announcements.py")
announcements = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(announcements)


def test_official_date_parser_accepts_iso_and_roc_dates():
    assert announcements.parse_date("2026-07-31").startswith("2026-07-31T")
    assert announcements.parse_date("115/07/31").startswith("2026-07-31T")


def test_direct_official_article_outranks_homepage_fallback():
    fallback = {"link_status": "official-homepage", "published_at": "2026-08-02T08:00:00+08:00"}
    direct = {"link_status": "direct", "published_at": "2026-08-02T07:00:00+08:00"}
    assert announcements.announcement_rank(direct) > announcements.announcement_rank(fallback)
