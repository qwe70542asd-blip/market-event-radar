#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from common import DATA, NOW, VERSION, read_json, write_payload

MAX_HOME_EVENT_DAYS_PAST = 45
MAX_HOME_EVENT_DAYS_FUTURE = 120


def mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def rows(value: Any) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: clean(v) for k, v in value.items() if v not in (None, "", [], {})}
    if isinstance(value, list):
        return [clean(v) for v in value]
    return value


def date_key(value: Any) -> str:
    text = str(value or "").strip()
    if len(text) >= 10 and text[4:5] == "-" and text[7:8] == "-":
        return text[:10]
    return ""


def event_day(event: dict[str, Any]) -> str:
    for key in ("local_date", "target_date", "ex_date", "start"):
        day = date_key(event.get(key))
        if day:
            return day
    return ""


def dividend_rows(payload: dict[str, Any], symbol: str) -> list[dict[str, Any]]:
    value = mapping(payload.get("items")).get(symbol)
    if isinstance(value, list):
        return rows(value)
    return rows(mapping(value).get("rows"))


def enrich_dividend(event: dict[str, Any], dividend_payload: dict[str, Any]) -> dict[str, Any]:
    symbol = str(event.get("symbol") or event.get("asset_id") or "").upper()
    if not symbol:
        return event
    day = event_day(event)
    candidates = dividend_rows(dividend_payload, symbol)
    match = next((row for row in candidates if day and day in {date_key(row.get(k)) for k in ("ex_date", "payment_date", "record_date", "board_date")}), None)
    match = match or (candidates[0] if candidates else {})
    out = dict(event)
    aliases = {
        "cash_dividend": ("cash_dividend", "cash", "amount"),
        "stock_dividend": ("stock_dividend", "stock"),
        "payment_date": ("payment_date", "pay_date"),
    }
    for target, keys in aliases.items():
        if out.get(target) not in (None, ""):
            continue
        for key in keys:
            value = match.get(key)
            if value not in (None, ""):
                out[target] = value
                break
    return out


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    keep = (
        "id", "tracking_key", "title", "start", "local_date", "target_date", "ex_date",
        "category", "event_type", "event_group", "region", "impact", "description", "summary",
        "market_effect", "source_name", "source_url", "origin", "all_day", "time_status",
        "symbol", "asset_id", "asset_name", "name", "announced_at", "announcement_kind", "previous_start", "period", "fiscal_period", "cash_dividend", "stock_dividend",
        "stock_dividend_ratio", "amount", "payment_date", "pay_date", "verification_status",
    )
    return clean({key: event.get(key) for key in keep})


def compact_asset(asset: dict[str, Any]) -> dict[str, Any]:
    keep = ("id", "asset_class", "market", "exchange", "symbol", "name", "company_name", "official_industry", "sub_industry", "currency")
    return clean({key: asset.get(key) for key in keep})


def compact_market(payload: dict[str, Any]) -> dict[str, Any]:
    items = [row for row in rows(payload.get("items")) if str(row.get("asset_class") or "").lower() in {"stock", "etf"}]
    return {
        "metadata": {**mapping(payload.get("metadata")), "version": VERSION, "frontend_profile": "stock-etf-only"},
        "breadth": mapping(payload.get("breadth")),
        "items": items,
    }


def compact_chip_row(row: dict[str, Any]) -> dict[str, Any]:
    keep = ("symbol", "name", "exchange", "asset_class", "date", "unit", "institutional", "margin", "short", "day_trade", "sources", "broker_note")
    out = {key: row.get(key) for key in keep}
    history = rows(row.get("history") or row.get("recent"))[:5]
    if history:
        out["history"] = history
    return clean(out)


def main() -> None:
    assets = mapping(read_json(DATA / "assets.json", {}))
    events = mapping(read_json(DATA / "events.json", {}))
    dividends = mapping(read_json(DATA / "dividend-history.json", {}))
    market = mapping(read_json(DATA / "tw-market.json", {}))
    chips = mapping(read_json(DATA / "tw-chips.json", {}))

    home_assets = [compact_asset(row) for row in rows(assets.get("assets"))]
    write_payload("home-assets.json", None, {
        "metadata": {"version": VERSION, "updated_at": NOW.isoformat(timespec="seconds"), "status": "ok" if home_assets else "waiting", "item_count": len(home_assets), "payload_mode": "frontend-compact-index", "source_updated_at": mapping(assets.get("metadata")).get("updated_at")},
        "assets": home_assets,
    })

    today = NOW.date()
    start = today - timedelta(days=MAX_HOME_EVENT_DAYS_PAST)
    end = today + timedelta(days=MAX_HOME_EVENT_DAYS_FUTURE)
    event_rows: list[dict[str, Any]] = []
    for event in rows(events.get("events")):
        day = event_day(event)
        try:
            parsed = datetime.strptime(day, "%Y-%m-%d").date()
        except Exception:
            continue
        if start <= parsed <= end:
            event_rows.append(compact_event(enrich_dividend(event, dividends)))
    write_payload("home-events.json", None, {
        "metadata": {"version": VERSION, "updated_at": NOW.isoformat(timespec="seconds"), "status": "ok" if event_rows else "waiting", "event_count": len(event_rows), "window_start": start.isoformat(), "window_end": end.isoformat(), "payload_mode": "frontend-compact-calendar", "source_updated_at": mapping(events.get("metadata")).get("updated_at")},
        "events": event_rows,
    })

    market_compact = compact_market(market)
    write_payload("tw-market-compact.json", None, market_compact)

    chip_items = mapping(chips.get("items"))
    compact_items = {symbol: compact_chip_row(mapping(row)) for symbol, row in chip_items.items() if isinstance(row, dict)}
    write_payload("tw-chips-compact.json", None, {
        "metadata": {**mapping(chips.get("metadata")), "version": VERSION, "updated_at": mapping(chips.get("metadata")).get("updated_at") or NOW.isoformat(timespec="seconds"), "status": mapping(chips.get("metadata")).get("status") or "ok", "item_count": len(compact_items), "payload_mode": "current-plus-five-session-frontend"},
        "markets": mapping(chips.get("markets")),
        "items": compact_items,
    })

    print({"home_assets": len(home_assets), "home_events": len(event_rows), "market_items": len(market_compact["items"]), "chip_items": len(compact_items)})


if __name__ == "__main__":
    main()
