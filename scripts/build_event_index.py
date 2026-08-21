#!/usr/bin/env python3
"""Build the compact homepage event index from the verified full event archive."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from common import DATA, NOW, VERSION, read_json, write_payload

FULL = DATA / "events.json"


def month_shift(day: date, delta: int) -> date:
    raw = day.year * 12 + day.month - 1 + delta
    return date(raw // 12, raw % 12 + 1, 1)


def event_day(row: dict[str, Any]) -> str:
    value = str(row.get("local_date") or row.get("target_date") or row.get("ex_date") or row.get("start") or "")
    return value[:10] if len(value) >= 10 else ""


def event_group(row: dict[str, Any]) -> str:
    group = str(row.get("event_group") or "").lower()
    category = str(row.get("category") or row.get("event_type") or "").lower()
    if group == "dividend" or any(token in category for token in ("dividend", "ex-right", "ex-div", "distribution")):
        return "dividend"
    if group == "corporate" or any(token in category for token in ("earnings", "corporate", "conference", "shareholder", "financial-report", "material")):
        return "company"
    return "major"


KEEP_KEYS = {
    "id","tracking_key","title","start","local_date","target_date","ex_date",
    "category","event_type","event_group","region","impact","description","summary",
    "market_effect","source_name","source_url","origin","all_day","assets","symbols",
    "tags","verification_status","time_status","date_basis","symbol","asset_id",
    "asset_name","name","cash_dividend","stock_dividend","stock_dividend_ratio",
    "payment_date","pay_date","announcement_kind","announced_at","previous_start",
    "reported_by","other_reports",
}


def clipped(value: Any, limit: int) -> Any:
    if not isinstance(value, str):
        return value
    value = " ".join(value.split())
    return value if len(value) <= limit else value[:limit].rstrip() + "…"


def compact(row: dict[str, Any]) -> dict[str, Any]:
    out = {key: row[key] for key in KEEP_KEYS if key in row and row[key] not in (None, "", [], {})}
    if "description" in out: out["description"] = clipped(out["description"], 420)
    if "summary" in out: out["summary"] = clipped(out["summary"], 320)
    if "market_effect" in out: out["market_effect"] = clipped(out["market_effect"], 260)
    return out


def main() -> None:
    payload = read_json(FULL, {"metadata": {}, "sources": [], "events": []})
    rows = [row for row in payload.get("events") or [] if isinstance(row, dict)]
    today = NOW.date()
    calendar_start = month_shift(today.replace(day=1), -1)
    calendar_end = month_shift(today.replace(day=1), 2) - timedelta(days=1)
    major_start = today - timedelta(days=45)
    major_end = today + timedelta(days=370)
    announcement_cutoff = NOW - timedelta(days=3)
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        day_text = event_day(row)
        try:
            day = date.fromisoformat(day_text)
        except ValueError:
            continue
        kind = event_group(row)
        recent_announcement = False
        if row.get("announced_at"):
            try:
                stamp = datetime.fromisoformat(str(row["announced_at"]).replace("Z", "+00:00"))
                recent_announcement = stamp.timestamp() >= announcement_cutoff.timestamp()
            except Exception:
                recent_announcement = False
        keep = (
            (kind in {"company", "dividend"} and calendar_start <= day <= calendar_end)
            or (kind == "major" and major_start <= day <= major_end)
            or recent_announcement
        )
        if not keep:
            continue
        key = str(row.get("id") or row.get("tracking_key") or f"{day_text}|{row.get('title')}")
        if key in seen:
            continue
        seen.add(key)
        selected.append(compact(row))
    selected.sort(key=lambda row: (event_day(row), str(row.get("title") or "")))
    metadata = dict(payload.get("metadata") or {})
    metadata.update({
        "version": VERSION,
        "is_index": True,
        "full_event_count": len(rows),
        "event_count": len(selected),
        "calendar_window_start": calendar_start.isoformat(),
        "calendar_window_end": calendar_end.isoformat(),
        "major_window_start": major_start.isoformat(),
        "major_window_end": major_end.isoformat(),
        "index_policy": "homepage compact index; full events.json remains authoritative",
    })
    write_payload("events-index.json", "__EVENT_INDEX_SEED__", {"metadata": metadata, "sources": payload.get("sources") or [], "events": selected})
    print({"event_index": len(selected), "full": len(rows), "calendar_window": [calendar_start.isoformat(), calendar_end.isoformat()]})


if __name__ == "__main__":
    main()
