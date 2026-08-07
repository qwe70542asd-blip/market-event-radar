#!/usr/bin/env python3
"""Publish multi-interval K-lines for the six homepage indices.

The static JSON channel is the reliable fallback for GitHub Pages/App WebView.
An optional edge worker may refresh more frequently, but the UI no longer
requires browser-to-Yahoo CORS access.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import requests

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.24"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.4.24)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6",
}
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
SYMBOLS = ["^TWII", "^DJI", "^IXIC", "^SOX", "^GSPC", "^N225"]
MARKETS = {"^TWII": "TW", "^N225": "JP", "^DJI": "US", "^IXIC": "US", "^SOX": "US", "^GSPC": "US"}
TIMEZONES = {"TW": "Asia/Taipei", "JP": "Asia/Tokyo", "US": "America/New_York"}
SPECS = {
    "5m": ("5d", "5m"),
    "15m": ("1mo", "15m"),
    "30m": ("1mo", "30m"),
    "60m": ("3mo", "60m"),
    "1d": ("1y", "1d"),
    "1wk": ("5y", "1wk"),
    "1mo": ("10y", "1mo"),
}


def num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def valid_ohlc(row: dict[str, Any]) -> bool:
    o, h, l, c = (num(row.get(k)) for k in ("open", "high", "low", "close"))
    return None not in (o, h, l, c) and h >= max(o, c) and l <= min(o, c)


def array_value(values: Any, index: int) -> Any:
    return values[index] if isinstance(values, list) and index < len(values) else None


def parse_chart(payload: dict[str, Any], market: str) -> list[dict[str, Any]]:
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError("empty Yahoo chart result")
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    rows: list[dict[str, Any]] = []
    zone = ZoneInfo(TIMEZONES[market])
    for index, stamp in enumerate(timestamps):
        row = {
            "time": int(stamp),
            "local_date": datetime.fromtimestamp(int(stamp), zone).date().isoformat(),
            "open": num(array_value(quote.get("open"), index)),
            "high": num(array_value(quote.get("high"), index)),
            "low": num(array_value(quote.get("low"), index)),
            "close": num(array_value(quote.get("close"), index)),
            "volume": num(array_value(quote.get("volume"), index)),
        }
        if valid_ohlc(row):
            rows.append(row)
    return rows


def session_anchor(dt: datetime, market: str) -> tuple[str, int] | None:
    """Return (session-date, four-hour bucket) without crossing lunch/overnight."""
    minutes = dt.hour * 60 + dt.minute
    if market == "TW":
        if not 540 <= minutes <= 810:
            return None
        return dt.date().isoformat(), (minutes - 540) // 240
    if market == "JP":
        if 540 <= minutes <= 690:
            return dt.date().isoformat(), 0
        if 750 <= minutes <= 930:
            return dt.date().isoformat(), 1
        return None
    if market == "US":
        if not 570 <= minutes <= 960:
            return None
        return dt.date().isoformat(), (minutes - 570) // 240
    return None


def aggregate_4h(rows: list[dict[str, Any]], market: str) -> list[dict[str, Any]]:
    zone = ZoneInfo(TIMEZONES[market])
    groups: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        dt = datetime.fromtimestamp(int(row["time"]), zone)
        key = session_anchor(dt, market)
        if key is not None:
            groups[key].append(row)
    output = []
    for key in sorted(groups):
        group = sorted(groups[key], key=lambda row: row["time"])
        output.append({
            "time": group[0]["time"],
            "local_date": key[0],
            "open": group[0]["open"],
            "high": max(row["high"] for row in group),
            "low": min(row["low"] for row in group),
            "close": group[-1]["close"],
            "volume": sum((row.get("volume") or 0) for row in group),
        })
    return output


def fetch_interval(session: requests.Session, symbol: str, interval: str) -> list[dict[str, Any]]:
    market = MARKETS[symbol]
    range_value, yahoo_interval = SPECS[interval]
    response = session.get(
        YAHOO_CHART.format(symbol=requests.utils.quote(symbol, safe="")),
        params={"range": range_value, "interval": yahoo_interval, "events": "div,splits"},
        headers=HEADERS,
        timeout=22,
    )
    response.raise_for_status()
    return parse_chart(response.json(), market)


def main() -> None:
    previous = read_json(DATA / "market-kline.json", {"items": {}})
    old_items = previous.get("items") or {}
    session = requests.Session()
    items: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for symbol in SYMBOLS:
        market = MARKETS[symbol]
        intervals: dict[str, Any] = {}
        for interval in SPECS:
            try:
                rows = fetch_interval(session, symbol, interval)
                if len(rows) < 2:
                    raise RuntimeError(f"only {len(rows)} candles")
                intervals[interval] = {"candles": rows, "source": "Yahoo chart via GitHub Actions", "updated_at": NOW.isoformat(timespec="seconds")}
            except Exception as exc:
                warnings.append(f"{symbol} {interval}: {exc}")
                retained = ((old_items.get(symbol) or {}).get("intervals") or {}).get(interval)
                if retained:
                    intervals[interval] = {**retained, "status": "cached", "last_error": str(exc)[:300]}
        hourly = (intervals.get("60m") or {}).get("candles") or []
        if hourly:
            four_hour = aggregate_4h(hourly, market)
            if four_hour:
                intervals["4h"] = {"candles": four_hour, "source": "1-hour candles aggregated by exchange session", "updated_at": NOW.isoformat(timespec="seconds")}
        elif ((old_items.get(symbol) or {}).get("intervals") or {}).get("4h"):
            intervals["4h"] = ((old_items.get(symbol) or {}).get("intervals") or {}).get("4h")
        items[symbol] = {"symbol": symbol, "market": market, "intervals": intervals}
    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": "ok" if not warnings else "partial",
            "symbols": SYMBOLS,
            "supported_intervals": ["5m", "15m", "30m", "60m", "4h", "1d", "1wk", "1mo"],
            "warnings": warnings[:100],
            "note": "Static multi-interval fallback. 4-hour candles never cross exchange sessions.",
        },
        "items": items,
    }
    write_payload("market-kline.json", "__MARKET_KLINE_SEED__", payload)
    print(payload["metadata"])


if __name__ == "__main__":
    main()
