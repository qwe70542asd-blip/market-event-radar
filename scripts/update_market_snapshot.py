#!/usr/bin/env python3
"""Refresh global-market quotes and continuous daily candlesticks.

v11.4.19 source policy:
- TAIEX daily OHLC: TWSE official historical index endpoint, with Yahoo as
  the quote/candle fallback.
- Overseas indices, rates, risk gauges and FX: Yahoo public chart endpoint.
- Each row preserves its last successful payload when one source fails, so a
  temporary outage does not blank every K-line card.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.19"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.4.19)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6",
}
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
TWSE_TAIEX = "https://www.twse.com.tw/indicesReport/MI_5MINS_HIST"
CANDLE_LIMIT = 70
KLINE_SYMBOLS = {"^TWII", "^KS11", "^N225", "^IXIC", "^SOX", "^GSPC"}
SYMBOLS = [
    ("^TWII", "台灣加權", "TW", "index"),
    ("^GSPC", "S&P 500", "US", "index"),
    ("^DJI", "道瓊工業", "US", "index"),
    ("^IXIC", "NASDAQ", "US", "index"),
    ("^SOX", "費城半導體", "US", "index"),
    ("^N225", "日經 225", "JP", "index"),
    ("^KS11", "韓國 KOSPI", "KR", "index"),
    ("^KQ11", "韓國 KOSDAQ", "KR", "index"),
    ("^VIX", "VIX 恐慌指數", "US", "risk"),
    ("^TNX", "美國 10 年債殖利率", "US", "yield"),
    ("DX-Y.NYB", "美元指數 DXY", "US", "currency-index"),
    ("TWD=X", "美元兌新台幣", "FX", "fx"),
    ("KRW=X", "美元兌韓元", "FX", "fx"),
]


def number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def iso_from_timestamp(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return None


def candle_date(value: Any) -> str | None:
    stamp = iso_from_timestamp(value)
    return stamp[:10] if stamp else None


def convert_yield(value: float | None, quote_kind: str) -> float | None:
    return value / 10 if quote_kind == "yield" and value is not None else value


def parse_yahoo_candles(chart: dict[str, Any], quote_kind: str) -> list[dict[str, Any]]:
    timestamps = chart.get("timestamp") or []
    quote = (chart.get("indicators", {}).get("quote") or [{}])[0]
    opens = quote.get("open") or []
    highs = quote.get("high") or []
    lows = quote.get("low") or []
    closes = quote.get("close") or []
    volumes = quote.get("volume") or []
    size = min(len(timestamps), len(opens), len(highs), len(lows), len(closes))
    rows: list[dict[str, Any]] = []
    for index in range(size):
        open_value = convert_yield(number(opens[index]), quote_kind)
        high_value = convert_yield(number(highs[index]), quote_kind)
        low_value = convert_yield(number(lows[index]), quote_kind)
        close_value = convert_yield(number(closes[index]), quote_kind)
        date = candle_date(timestamps[index])
        if not date or any(value is None for value in (open_value, high_value, low_value, close_value)):
            continue
        if high_value < low_value:
            high_value, low_value = low_value, high_value
        rows.append({
            "date": date,
            "timestamp": int(timestamps[index]),
            "open": open_value,
            "high": high_value,
            "low": low_value,
            "close": close_value,
            "volume": number(volumes[index]) if index < len(volumes) else None,
            "source": "Yahoo chart",
        })
    deduped = {row["date"]: row for row in rows}
    return [deduped[key] for key in sorted(deduped)][-CANDLE_LIMIT:]


def fetch_yahoo(
    session: requests.Session,
    symbol: str,
    name: str,
    market: str,
    quote_kind: str,
) -> dict[str, Any]:
    response = session.get(
        YAHOO_CHART.format(symbol=requests.utils.quote(symbol, safe="")),
        params={"range": "3mo", "interval": "1d", "events": "div,splits"},
        headers=HEADERS,
        timeout=18,
    )
    response.raise_for_status()
    result = response.json().get("chart", {}).get("result") or []
    if not result:
        raise RuntimeError("empty Yahoo chart result")
    chart = result[0]
    meta = chart.get("meta") or {}
    candles = parse_yahoo_candles(chart, quote_kind)

    price = convert_yield(number(meta.get("regularMarketPrice")), quote_kind)
    if price is None and candles:
        price = candles[-1]["close"]
    previous = convert_yield(number(meta.get("chartPreviousClose")), quote_kind)
    if previous is None:
        previous = convert_yield(number(meta.get("previousClose")), quote_kind)
    if previous is None and len(candles) >= 2:
        previous = candles[-2]["close"]
    change = price - previous if price is not None and previous is not None else None
    change_percent = change / previous * 100 if change is not None and previous not in (None, 0) else None

    latest = candles[-1] if candles else {}
    market_at = iso_from_timestamp(meta.get("regularMarketTime")) or NOW.isoformat(timespec="seconds")
    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "quote_kind": quote_kind,
        "price": price,
        "previous_close": previous,
        "change": change,
        "change_percent": change_percent,
        "open": latest.get("open") if latest else convert_yield(number(meta.get("regularMarketOpen")), quote_kind),
        "high": latest.get("high") if latest else convert_yield(number(meta.get("regularMarketDayHigh")), quote_kind),
        "low": latest.get("low") if latest else convert_yield(number(meta.get("regularMarketDayLow")), quote_kind),
        "close": latest.get("close") if latest else price,
        "volume": latest.get("volume") if latest else number(meta.get("regularMarketVolume")),
        "currency": meta.get("currency"),
        "market_at": market_at,
        "display_suffix": "%" if quote_kind == "yield" else "",
        "candles": candles if symbol in KLINE_SYMBOLS else [],
        "candle_count": len(candles) if symbol in KLINE_SYMBOLS else 0,
        "candle_interval": "1d" if symbol in KLINE_SYMBOLS else None,
        "candle_range": "3mo" if symbol in KLINE_SYMBOLS else None,
        "source": "Yahoo public chart API",
        "candle_source": "Yahoo chart",
        "data_status": "live",
    }


def month_start(year: int, month: int, offset: int) -> tuple[int, int]:
    value = year * 12 + (month - 1) - offset
    return value // 12, value % 12 + 1


def parse_roc_date(value: Any) -> str | None:
    text = str(value or "").strip()
    parts = text.replace("-", "/").split("/")
    if len(parts) != 3:
        return None
    try:
        year, month, day = (int(part) for part in parts)
        if year < 1911:
            year += 1911
        datetime(year, month, day)
        return f"{year:04d}-{month:02d}-{day:02d}"
    except (TypeError, ValueError):
        return None


def parse_twse_payload(payload: Any) -> list[dict[str, Any]]:
    raw_rows: list[Any] = []
    if isinstance(payload, dict):
        raw_rows = payload.get("data") or payload.get("items") or []
    elif isinstance(payload, list):
        raw_rows = payload
    parsed: list[dict[str, Any]] = []
    for row in raw_rows:
        if isinstance(row, dict):
            date = parse_roc_date(row.get("Date") or row.get("日期") or row.get("date"))
            open_value = number(row.get("OpeningIndex") or row.get("開盤指數") or row.get("open"))
            high_value = number(row.get("HighestIndex") or row.get("最高指數") or row.get("high"))
            low_value = number(row.get("LowestIndex") or row.get("最低指數") or row.get("low"))
            close_value = number(row.get("ClosingIndex") or row.get("收盤指數") or row.get("close"))
        elif isinstance(row, (list, tuple)) and len(row) >= 5:
            date = parse_roc_date(row[0])
            open_value, high_value, low_value, close_value = map(number, row[1:5])
        else:
            continue
        if not date or any(value is None for value in (open_value, high_value, low_value, close_value)):
            continue
        parsed.append({
            "date": date,
            "open": open_value,
            "high": high_value,
            "low": low_value,
            "close": close_value,
            "volume": None,
            "source": "TWSE official TAIEX history",
        })
    return parsed


def fetch_twse_taiex(session: requests.Session, months: int = 4) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for offset in range(months):
        year, month = month_start(NOW.year, NOW.month, offset)
        date = f"{year:04d}{month:02d}01"
        try:
            response = session.get(
                TWSE_TAIEX,
                params={"response": "json", "date": date},
                headers=HEADERS,
                timeout=18,
            )
            response.raise_for_status()
            payload = response.json()
            for candle in parse_twse_payload(payload):
                rows[candle["date"]] = candle
        except Exception as exc:
            errors.append(f"{year:04d}-{month:02d}: {exc}")
    if not rows:
        raise RuntimeError("TWSE TAIEX history unavailable: " + "; ".join(errors[:3]))
    return [rows[key] for key in sorted(rows)][-CANDLE_LIMIT:]


def merge_candles(primary: list[dict[str, Any]], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {row.get("date"): row for row in fallback if row.get("date")}
    for row in primary:
        if row.get("date"):
            merged[row["date"]] = row
    return [merged[key] for key in sorted(merged)][-CANDLE_LIMIT:]


def enrich_taiex_with_twse(session: requests.Session, yahoo_row: dict[str, Any]) -> dict[str, Any]:
    official = fetch_twse_taiex(session)
    candles = merge_candles(official, yahoo_row.get("candles") or [])
    latest = candles[-1] if candles else {}
    previous = candles[-2].get("close") if len(candles) >= 2 else yahoo_row.get("previous_close")
    price = yahoo_row.get("price")
    if price is None:
        price = latest.get("close")
    change = price - previous if price is not None and previous is not None else None
    change_percent = change / previous * 100 if change is not None and previous not in (None, 0) else None
    return {
        **yahoo_row,
        "price": price,
        "previous_close": previous,
        "change": change,
        "change_percent": change_percent,
        "open": latest.get("open") or yahoo_row.get("open"),
        "high": latest.get("high") or yahoo_row.get("high"),
        "low": latest.get("low") or yahoo_row.get("low"),
        "close": latest.get("close") or yahoo_row.get("close") or price,
        "candles": candles,
        "candle_count": len(candles),
        "source": "TWSE official history + Yahoo quote",
        "candle_source": "TWSE official TAIEX history",
        "data_status": "live",
    }


def cached_row(previous: dict[str, Any], name: str, market: str, quote_kind: str, error: str) -> dict[str, Any]:
    return {
        **previous,
        "name": name,
        "market": market,
        "quote_kind": quote_kind,
        "data_status": "cached",
        "last_error": error[:500],
    }


def empty_row(symbol: str, name: str, market: str, quote_kind: str, error: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "quote_kind": quote_kind,
        "price": None,
        "previous_close": None,
        "change": None,
        "change_percent": None,
        "open": None,
        "high": None,
        "low": None,
        "close": None,
        "volume": None,
        "market_at": None,
        "display_suffix": "%" if quote_kind == "yield" else "",
        "candles": [],
        "candle_count": 0,
        "candle_interval": "1d" if symbol in KLINE_SYMBOLS else None,
        "candle_range": "3mo" if symbol in KLINE_SYMBOLS else None,
        "data_status": "waiting",
        "last_error": error[:500],
    }


def main() -> None:
    old = read_json(DATA / "market-snapshot.json", {"items": []})
    old_by_symbol = {str(row.get("symbol")): row for row in old.get("items") or []}
    session = requests.Session()
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    for symbol, name, market, quote_kind in SYMBOLS:
        previous = old_by_symbol.get(symbol)
        try:
            row = fetch_yahoo(session, symbol, name, market, quote_kind)
            if symbol == "^TWII":
                try:
                    row = enrich_taiex_with_twse(session, row)
                except Exception as exc:
                    warnings.append(f"TWSE ^TWII: {exc}")
                    row["candle_source"] = "Yahoo chart fallback"
                    row["source"] = "Yahoo public chart API (TWSE unavailable)"
            if symbol in KLINE_SYMBOLS and len(row.get("candles") or []) < 10 and previous:
                old_candles = previous.get("candles") or []
                row["candles"] = merge_candles(row.get("candles") or [], old_candles)
                row["candle_count"] = len(row["candles"])
            rows.append(row)
        except Exception as exc:
            warning = f"{symbol}: {exc}"
            warnings.append(warning)
            rows.append(cached_row(previous, name, market, quote_kind, warning) if previous else empty_row(symbol, name, market, quote_kind, warning))

    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "source": "TWSE official TAIEX history + Yahoo public chart API",
            "warnings": warnings,
            "kline_symbols": sorted(KLINE_SYMBOLS),
            "kline_interval": "1d",
            "kline_range": "3mo",
            "note": "TAIEX uses TWSE official daily OHLC with Yahoo fallback. Korea, Japan and U.S. indices use Yahoo daily OHLC. Each symbol preserves the last successful candles independently.",
        },
        "items": rows,
    }
    write_payload("market-snapshot.json", "__MARKET_SNAPSHOT_SEED__", payload)


if __name__ == "__main__":
    main()
