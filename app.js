#!/usr/bin/env python3
"""Build data/events.json for the Market Event Radar static site.

The script is designed for GitHub Actions. It prioritizes official calendars,
keeps the last successful data when a source fails, and merges curated events
from data/manual_events.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser
try:
    from icalendar import Calendar
except ImportError:  # Optional during offline/local preview
    Calendar = None

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EVENTS_PATH = DATA_DIR / "events.json"
MANUAL_PATH = DATA_DIR / "manual_events.json"
SEED_PATH = DATA_DIR / "seed.js"

TAIPEI = ZoneInfo("Asia/Taipei")
NEW_YORK = ZoneInfo("America/New_York")
NOW = datetime.now(TAIPEI)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/1.0; +https://github.com/)",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
}

WATCHLIST = {
    "NVDA", "AMD", "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA",
    "AVGO", "QCOM", "MU", "INTC", "ARM", "ASML", "TSM", "SMCI", "ORCL",
    "PLTR", "NFLX", "CRM", "ADBE", "DELL", "HPE", "LRCX", "AMAT", "KLAC",
}

BLS_TRANSLATIONS = {
    "Employment Situation": ("美國非農就業報告", "high", ["NASDAQ", "美債", "美元", "黃金", "台股"]),
    "Consumer Price Index": ("美國 CPI 通膨", "high", ["NASDAQ", "美債", "美元", "黃金", "台股"]),
    "Producer Price Index": ("美國 PPI 生產者物價", "medium", ["美債", "美元", "NASDAQ"]),
    "Job Openings and Labor Turnover Survey": ("美國 JOLTS 職缺數", "medium", ["美債", "美元", "NASDAQ"]),
    "Productivity and Costs": ("美國生產力與單位勞動成本", "medium", ["美債", "NASDAQ", "美元"]),
    "U.S. Import and Export Price Indexes": ("美國進出口物價", "low", ["美元", "美債", "原物料"]),
    "Employment Cost Index": ("美國就業成本指數", "high", ["美債", "美元", "NASDAQ"]),
    "Real Earnings": ("美國實質薪資", "low", ["消費股", "美元", "美債"]),
}

BEA_TRANSLATIONS = {
    "Gross Domestic Product": ("美國 GDP", "high", ["S&P 500", "美債", "美元", "台股"]),
    "Personal Income and Outlays": ("美國個人所得與支出／PCE", "high", ["NASDAQ", "美債", "美元", "黃金"]),
    "U.S. International Trade in Goods and Services": ("美國貿易收支", "medium", ["美元", "美債", "航運"]),
    "Corporate Profits": ("美國企業獲利", "medium", ["S&P 500", "NASDAQ"]),
}


@dataclass
class SourceResult:
    key: str
    name: str
    url: str
    events: list[dict[str, Any]]
    status: str = "ok"
    message: str = ""


def get_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha1(raw).hexdigest()[:13]}"


def iso_taipei(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=TAIPEI)
    return value.astimezone(TAIPEI).isoformat(timespec="seconds")


def request(session: requests.Session, url: str, **kwargs: Any) -> requests.Response:
    response = session.get(url, headers={**HEADERS, **kwargs.pop("headers", {})}, timeout=25, **kwargs)
    response.raise_for_status()
    return response


def clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_money(value: str | None) -> float:
    if not value:
        return 0.0
    text = value.replace("$", "").replace(",", "").strip().upper()
    match = re.match(r"([-+]?\d+(?:\.\d+)?)\s*([KMBT]?)", text)
    if not match:
        return 0.0
    number = float(match.group(1))
    return number * {"": 1, "K": 1e3, "M": 1e6, "B": 1e9, "T": 1e12}[match.group(2)]


def translate_release(summary: str, mapping: dict[str, tuple[str, str, list[str]]]) -> tuple[str, str, list[str]] | None:
    for needle, translated in mapping.items():
        if needle.lower() in summary.lower():
            return translated
    return None


def fetch_bls(session: requests.Session) -> SourceResult:
    url = "https://www.bls.gov/schedule/news_release/bls.ics"
    response = request(session, url)
    if Calendar is None:
        raise RuntimeError("icalendar package is required for the BLS feed")
    calendar = Calendar.from_ical(response.content)
    events: list[dict[str, Any]] = []
    window_start = NOW - timedelta(days=7)
    window_end = NOW + timedelta(days=370)

    for component in calendar.walk("VEVENT"):
        summary = clean_text(component.get("summary"))
        translated = translate_release(summary, BLS_TRANSLATIONS)
        if not translated:
            continue
        dt = component.decoded("dtstart")
        if isinstance(dt, date) and not isinstance(dt, datetime):
            dt = datetime.combine(dt, time(8, 30), tzinfo=NEW_YORK)
        elif dt.tzinfo is None:
            dt = dt.replace(tzinfo=NEW_YORK)
        dt_taipei = dt.astimezone(TAIPEI)
        if not (window_start <= dt_taipei <= window_end):
            continue
        title, impact, assets = translated
        description = clean_text(component.get("description")) or f"BLS 發布 {summary}。"
        events.append({
            "id": stable_id("bls", summary, dt_taipei.isoformat()),
            "title": title,
            "start": iso_taipei(dt_taipei),
            "category": "macro",
            "region": "US",
            "impact": impact,
            "description": description,
            "market_effect": "實際市場反應通常取決於公布值與市場預期的落差，以及對聯準會政策路徑的影響。",
            "assets": assets,
            "tags": ["BLS", summary],
            "source_name": "U.S. BLS",
            "source_url": url,
            "origin": "bls",
            "all_day": False,
            "is_estimated": False,
        })
    return SourceResult("bls", "U.S. BLS release calendar", url, events)


def fetch_bea(session: requests.Session) -> SourceResult:
    url = "https://www.bea.gov/news/schedule"
    html = request(session, url).text
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    current_year = NOW.year
    pattern = re.compile(
        r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(?P<day>\d{1,2})\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s+(?P<ampm>AM|PM)\s+(?:News|Data)\s+(?P<title>[^\n]+)",
        re.IGNORECASE,
    )
    events: list[dict[str, Any]] = []
    for match in pattern.finditer(text):
        raw_title = clean_text(match.group("title"))
        translated = translate_release(raw_title, BEA_TRANSLATIONS)
        if not translated:
            continue
        month = datetime.strptime(match.group("month"), "%B").month
        hour = int(match.group("hour")) % 12 + (12 if match.group("ampm").upper() == "PM" else 0)
        dt = datetime(current_year, month, int(match.group("day")), hour, int(match.group("minute")), tzinfo=NEW_YORK).astimezone(TAIPEI)
        if dt < NOW - timedelta(days=7) or dt > NOW + timedelta(days=370):
            continue
        title, impact, assets = translated
        if "GDP" in raw_title and "Personal Income" in raw_title:
            title = "美國 GDP＋PCE／個人所得與支出"
        events.append({
            "id": stable_id("bea", raw_title, dt.isoformat()),
            "title": title,
            "start": iso_taipei(dt),
            "category": "macro",
            "region": "US",
            "impact": impact,
            "description": f"BEA 發布 {raw_title}。",
            "market_effect": "成長與通膨數據可能改變美債殖利率、美元與風險資產的利率定價。",
            "assets": assets,
            "tags": ["BEA", raw_title],
            "source_name": "U.S. BEA",
            "source_url": url,
            "origin": "bea",
            "all_day": False,
            "is_estimated": False,
        })
    if not events:
        raise RuntimeError("BEA schedule parser returned no recognized events")
    return SourceResult("bea", "U.S. BEA release schedule", url, events)


def report_datetime(us_date: date, timing: str) -> tuple[datetime, bool, str]:
    timing_text = timing.lower()
    if "after" in timing_text or "post" in timing_text:
        local = datetime.combine(us_date, time(17, 0), tzinfo=NEW_YORK)
        return local.astimezone(TAIPEI), False, "美股盤後"
    if "before" in timing_text or "pre" in timing_text:
        local = datetime.combine(us_date, time(7, 0), tzinfo=NEW_YORK)
        return local.astimezone(TAIPEI), False, "美股盤前"
    local = datetime.combine(us_date, time(9, 0), tzinfo=TAIPEI)
    return local, True, "時間待確認"


def fetch_nasdaq(session: requests.Session) -> SourceResult:
    url = "https://api.nasdaq.com/api/calendar/earnings"
    page_url = "https://www.nasdaq.com/market-activity/earnings"
    if os.getenv("NASDAQ_ENABLED", "1").lower() in {"0", "false", "no"}:
        return SourceResult("nasdaq", "Nasdaq earnings calendar", page_url, [], "warning", "disabled")

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    }
    events: list[dict[str, Any]] = []
    errors = 0
    for offset in range(0, 46):
        us_day = (NOW.astimezone(NEW_YORK) + timedelta(days=offset)).date()
        if us_day.weekday() >= 5:
            continue
        try:
            payload = request(session, url, headers=headers, params={"date": us_day.isoformat()}).json()
            rows = (((payload or {}).get("data") or {}).get("rows") or [])
        except Exception:
            errors += 1
            continue

        for row in rows:
            symbol = clean_text(row.get("symbol")).upper()
            name = clean_text(row.get("name"))
            market_cap = parse_money(clean_text(row.get("marketCap")))
            if symbol not in WATCHLIST and market_cap < 10_000_000_000:
                continue
            timing = clean_text(row.get("time") or row.get("timeOfDay") or "")
            dt, estimated, timing_label = report_datetime(us_day, timing)
            impact = "high" if symbol in WATCHLIST or market_cap >= 100_000_000_000 else "medium"
            events.append({
                "id": stable_id("earnings", symbol, us_day.isoformat()),
                "title": f"{symbol} {name} 財報".strip(),
                "start": iso_taipei(dt),
                "category": "earnings",
                "region": "US",
                "impact": impact,
                "description": f"{name or symbol} 預計於美股 {us_day.isoformat()} {timing_label}公布財報。財報日期可能由公司調整。",
                "market_effect": "財測、營收與毛利率相對預期的落差，可能影響公司股價及同產業供應鏈。",
                "assets": [symbol, "NASDAQ", "產業供應鏈"],
                "tags": [symbol, "財報", timing_label],
                "source_name": "Nasdaq Earnings Calendar",
                "source_url": page_url,
                "origin": "nasdaq",
                "all_day": estimated,
                "is_estimated": estimated,
            })
    if not events and errors:
        raise RuntimeError(f"Nasdaq endpoint failed on {errors} dates")
    status = "warning" if errors else "ok"
    return SourceResult("nasdaq", "Nasdaq earnings calendar", page_url, events, status, f"{errors} request errors" if errors else "")


def deduplicate(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for event in events:
        event = dict(event)
        event.setdefault("impact", "low")
        event.setdefault("category", "macro")
        event.setdefault("region", "GLOBAL")
        event.setdefault("assets", [])
        event.setdefault("tags", [])
        event.setdefault("all_day", False)
        event.setdefault("is_estimated", False)
        event.setdefault("origin", "manual")
        event_id = event.get("id") or stable_id("event", clean_text(event.get("title")), clean_text(event.get("start")))
        event["id"] = event_id
        # Manual events win over automatically collected versions with the same ID.
        if event_id not in by_id or event.get("origin") == "manual":
            by_id[event_id] = event
    return sorted(by_id.values(), key=lambda e: date_parser.isoparse(e["start"]))


def retain_previous(previous: dict[str, Any], origin: str) -> list[dict[str, Any]]:
    return [e for e in previous.get("events", []) if e.get("origin") == origin]


def run_source(
    key: str,
    name: str,
    url: str,
    fetcher: Callable[[requests.Session], SourceResult],
    session: requests.Session,
    previous: dict[str, Any],
    offline: bool,
) -> SourceResult:
    if offline:
        return SourceResult(key, name, url, retain_previous(previous, key), "warning", "offline mode")
    try:
        return fetcher(session)
    except Exception as exc:  # noqa: BLE001 - preserve last known-good data
        print(f"[warning] {key}: {exc}", file=sys.stderr)
        return SourceResult(key, name, url, retain_previous(previous, key), "warning", str(exc))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="Do not access the network; merge manual and existing data only.")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manual = get_json(MANUAL_PATH, [])
    previous = get_json(EVENTS_PATH, {"events": [], "sources": []})
    previous_sources = {s.get("name"): s for s in previous.get("sources", [])}

    session = requests.Session()
    definitions = [
        ("bls", "U.S. BLS release calendar", "https://www.bls.gov/schedule/news_release/bls.ics", fetch_bls),
        ("bea", "U.S. BEA release schedule", "https://www.bea.gov/news/schedule", fetch_bea),
        ("nasdaq", "Nasdaq earnings calendar", "https://www.nasdaq.com/market-activity/earnings", fetch_nasdaq),
    ]
    results = [run_source(*definition, session, previous, args.offline) for definition in definitions]

    generated: list[dict[str, Any]] = []
    for event in manual:
        event = dict(event)
        event["origin"] = "manual"
        generated.append(event)
    for result in results:
        generated.extend(result.events)

    cutoff_past = NOW - timedelta(days=8)
    cutoff_future = NOW + timedelta(days=550)
    events = [
        event for event in deduplicate(generated)
        if cutoff_past <= date_parser.isoparse(event["start"]).astimezone(TAIPEI) <= cutoff_future
    ]

    source_rows: list[dict[str, Any]] = []
    for result in results:
        previous_row = previous_sources.get(result.name, {})
        last_success = iso_taipei(NOW) if result.status == "ok" else previous_row.get("last_success")
        source_rows.append({
            "name": result.name,
            "status": result.status,
            "last_success": last_success,
            "url": result.url,
            "message": result.message,
        })

    # Stable/manual source rows shown in the UI.
    source_rows.extend([
        {"name": "Federal Reserve calendar", "status": "ok", "last_success": iso_taipei(NOW), "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"},
        {"name": "Bank of Japan calendar", "status": "ok", "last_success": iso_taipei(NOW), "url": "https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm"},
        {"name": "European Central Bank calendar", "status": "ok", "last_success": iso_taipei(NOW), "url": "https://www.ecb.europa.eu/press/calendars/mgcgc/html/index.en.html"},
        {"name": "TSMC financial calendar", "status": "ok", "last_success": iso_taipei(NOW), "url": "https://investor.tsmc.com/chinese/financial-calendar"},
        {"name": "Curated technology events", "status": "ok", "last_success": iso_taipei(NOW), "url": ""},
    ])

    payload = {
        "metadata": {
            "updated_at": iso_taipei(NOW),
            "timezone": "Asia/Taipei",
            "generation_mode": "offline" if args.offline else "daily",
            "event_count": len(events),
            "note": "Official-source-first pipeline with last-known-good fallback.",
        },
        "sources": source_rows,
        "events": events,
    }
    EVENTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED_PATH.write_text("window.__MARKET_EVENT_SEED__ = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"Wrote {len(events)} events to {EVENTS_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
