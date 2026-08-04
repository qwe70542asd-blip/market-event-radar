#!/usr/bin/env python3
"""Refresh the compact global-market board.

The board contains broad indices, Korea, risk gauges, rates and FX.  Individual
stocks are intentionally excluded so the panel stays market-level.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from common import DATA, NOW, read_json, write_payload

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.3)"}
SYMBOLS = [
    ("^TWII", "台灣加權", "TW", "index"),
    ("^TWOII", "台灣櫃買指數", "TW", "index"),
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


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def fetch_one(session: requests.Session, symbol: str, name: str, market: str, quote_kind: str) -> dict:
    response = session.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(symbol, safe='')}",
        params={"range": "2d", "interval": "5m"},
        headers=HEADERS,
        timeout=14,
    )
    response.raise_for_status()
    result = response.json().get("chart", {}).get("result") or []
    if not result:
        raise RuntimeError("empty chart result")
    chart = result[0]
    meta = chart.get("meta") or {}
    quote = (chart.get("indicators", {}).get("quote") or [{}])[0]
    closes = [_number(value) for value in quote.get("close") or []]
    closes = [value for value in closes if value is not None]
    price = _number(meta.get("regularMarketPrice"))
    if price is None and closes:
        price = closes[-1]
    previous = _number(meta.get("chartPreviousClose"))
    if previous is None:
        previous = _number(meta.get("previousClose"))
    change = price - previous if price is not None and previous is not None else None
    change_percent = change / previous * 100 if change is not None and previous not in (None, 0) else None

    # Yahoo's ^TNX is quoted as yield multiplied by ten.  Store a human-readable
    # percent value while preserving the correct day-over-day percent move.
    display_price = price / 10 if quote_kind == "yield" and price is not None else price
    display_previous = previous / 10 if quote_kind == "yield" and previous is not None else previous
    display_change = display_price - display_previous if display_price is not None and display_previous is not None else None

    market_timestamp = meta.get("regularMarketTime")
    market_at = NOW.isoformat(timespec="seconds")
    if market_timestamp:
        try:
            market_at = datetime.fromtimestamp(int(market_timestamp), ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")
        except (TypeError, ValueError, OSError):
            pass

    return {
        "symbol": symbol,
        "name": name,
        "market": market,
        "quote_kind": quote_kind,
        "price": display_price,
        "previous_close": display_previous,
        "change": display_change,
        "change_percent": change_percent,
        "open": _number(meta.get("regularMarketOpen")),
        "high": _number(meta.get("regularMarketDayHigh")),
        "low": _number(meta.get("regularMarketDayLow")),
        "volume": _number(meta.get("regularMarketVolume")),
        "currency": meta.get("currency"),
        "market_at": market_at,
        "display_suffix": "%" if quote_kind == "yield" else "",
    }


def main() -> None:
    old = read_json(DATA / "market-snapshot.json", {"items": []})
    old_by_symbol = {str(row.get("symbol")): row for row in old.get("items") or []}
    session = requests.Session()
    rows, warnings = [], []
    for args in SYMBOLS:
        try:
            rows.append(fetch_one(session, *args))
        except Exception as exc:  # source failure must not erase a working row
            symbol, name, market, quote_kind = args
            warnings.append(f"{symbol}: {exc}")
            previous = old_by_symbol.get(symbol)
            if previous:
                rows.append({**previous, "name": name, "market": market, "quote_kind": quote_kind})
            else:
                rows.append({
                    "symbol": symbol,
                    "name": name,
                    "market": market,
                    "quote_kind": quote_kind,
                    "price": None,
                    "previous_close": None,
                    "change": None,
                    "change_percent": None,
                    "market_at": None,
                    "display_suffix": "%" if quote_kind == "yield" else "",
                })

    payload = {
        "metadata": {
            "version": "v11.4.4",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "source": "Yahoo public chart API",
            "warnings": warnings,
            "note": "Market-level indices, Korea, VIX, U.S. 10Y yield, DXY and FX; no individual stock.",
        },
        "items": rows,
    }
    write_payload("market-snapshot.json", "__MARKET_SNAPSHOT_SEED__", payload)


if __name__ == "__main__":
    main()
