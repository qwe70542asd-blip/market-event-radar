#!/usr/bin/env python3
"""Refresh related market coverage for upcoming events.

The script reads data/events.json, searches Google News RSS for the most
important upcoming events, and writes data/news.json plus data/news-seed.js.
When the network source fails it preserves the last successful articles.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EVENTS_PATH = DATA / "events.json"
NEWS_PATH = DATA / "news.json"
SEED_PATH = DATA / "news-seed.js"
TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime.now(TAIPEI)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/1.0; +https://github.com/)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
}


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def iso(value: datetime) -> str:
    return value.astimezone(TAIPEI).isoformat(timespec="seconds")


def clean(value: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def parse_pubdate(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TAIPEI)
        return iso(parsed)
    except (TypeError, ValueError):
        return None


def query_for_event(event: dict) -> str:
    title = clean(event.get("title"))
    title = re.sub(r"\b20\d{2}\b", "", title)
    assets = [clean(asset) for asset in event.get("assets", [])[:2] if clean(asset)]
    suffix = " 投資 市場" if event.get("category") in {"macro", "central-bank"} else " 財報 市場"
    return clean(" ".join([title, *assets]) + suffix)


def fetch_feed(session: requests.Session, query: str) -> list[dict]:
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )
    response = session.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    rows = []
    for item in root.findall("./channel/item")[:8]:
        title = clean(item.findtext("title"))
        link = clean(item.findtext("link"))
        source_node = item.find("source")
        source = clean(source_node.text if source_node is not None else "Google News")
        published_at = parse_pubdate(item.findtext("pubDate"))
        if not title or not link:
            continue
        rows.append({"title": title, "link": link, "source": source or "Google News", "published_at": published_at})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Keep existing coverage without network requests.")
    args = parser.parse_args()

    events_payload = read_json(EVENTS_PATH, {"events": []})
    previous = read_json(NEWS_PATH, {"items": []})
    if args.offline:
        print(f"Offline mode: kept {len(previous.get('items', []))} articles")
        return 0

    max_events = int(os.getenv("NEWS_MAX_EVENTS", "12"))
    cutoff = NOW + timedelta(days=35)
    candidates = []
    for event in events_payload.get("events", []):
        try:
            start = datetime.fromisoformat(event["start"]).astimezone(TAIPEI)
        except (KeyError, TypeError, ValueError):
            continue
        if NOW - timedelta(hours=18) <= start <= cutoff and event.get("impact") in {"high", "medium"}:
            candidates.append(event)
    candidates.sort(key=lambda event: (0 if event.get("impact") == "high" else 1, event.get("start", "")))
    candidates = candidates[:max_events]

    session = requests.Session()
    generated: list[dict] = []
    failures = 0
    for event in candidates:
        query = query_for_event(event)
        try:
            articles = fetch_feed(session, query)
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"[warning] news for {event.get('title')}: {exc}", file=sys.stderr)
            articles = []
        for article in articles[:3]:
            generated.append({
                "id": stable_id(event.get("id", ""), article["link"]),
                "event_id": event.get("id"),
                "event_title": event.get("title"),
                "title": article["title"],
                "link": article["link"],
                "source": article["source"],
                "published_at": article["published_at"],
                "query": query,
            })
        time.sleep(0.35)

    by_link = {}
    for item in generated:
        by_link.setdefault(item["link"], item)
    items = list(by_link.values())
    items.sort(key=lambda item: item.get("published_at") or "", reverse=True)

    if not items:
        items = previous.get("items", [])
        status = "warning"
        message = "news source unavailable; kept last successful data"
    else:
        status = "warning" if failures else "ok"
        message = f"{failures} event queries failed" if failures else ""

    payload = {
        "metadata": {
            "updated_at": iso(NOW),
            "timezone": "Asia/Taipei",
            "item_count": len(items),
            "note": "Related coverage from public Google News RSS search results.",
        },
        "source": {"name": "Google News RSS", "status": status, "message": message},
        "items": items[:36],
    }
    NEWS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED_PATH.write_text("window.__MARKET_NEWS_SEED__ = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"Wrote {len(payload['items'])} related articles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
