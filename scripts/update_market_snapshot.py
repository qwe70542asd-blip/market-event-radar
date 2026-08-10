#!/usr/bin/env python3
"""Refresh global-market quotes and continuous daily candlesticks.

v11.4.38 data-quality policy
- A card may only combine price, change and OHLC from the same exchange session.
- When Yahoo's live quote is newer than the last completed daily candle, the
  live-session OHLC comes from Yahoo meta fields; yesterday's daily candle is
  used only as previous close.
- TAIEX history is sourced from TWSE. Yahoo is used for the live session and as
  a history fallback.
- Suspicious or mixed-session data fails closed and the last verified row is
  retained with a stale/cached status.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from typing import Any
from io import StringIO
from zoneinfo import ZoneInfo

import csv
import requests

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.38"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.4.38)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6",
}
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
TWSE_TAIEX = "https://www.twse.com.tw/indicesReport/MI_5MINS_HIST"
NIKKEI_DAILY_CSV = "https://indexes.nikkei.co.jp/nkave/historical/nikkei_stock_average_daily_en.csv"
CANDLE_LIMIT = 70
KLINE_SYMBOLS = {"^TWII", "^DJI", "^IXIC", "^SOX", "^GSPC", "^N225"}
SYMBOLS = [
    # Six index cards, in the same order used by the homepage.
    ("^TWII", "台灣加權", "TW", "index"),
    ("^DJI", "道瓊工業平均指數", "US", "index"),
    ("^IXIC", "NASDAQ", "US", "index"),
    ("^SOX", "費城半導體", "US", "index"),
    ("^GSPC", "S&P 500", "US", "index"),
    ("^N225", "日經 225", "JP", "index"),
    # Supporting macro indicators.
    ("^VIX", "VIX 恐慌指數", "US", "risk"),
    ("^TNX", "美國 10 年債殖利率", "US", "yield"),
    ("DX-Y.NYB", "美元指數 DXY", "US", "currency-index"),
    ("TWD=X", "美元兌新台幣", "FX", "fx"),
    ("KRW=X", "美元兌韓元", "FX", "fx"),
]


MARKET_SCHEDULES = {
    "TW": {"tz": "Asia/Taipei", "sessions": ((time(9, 0), time(13, 30)),)},
    "JP": {"tz": "Asia/Tokyo", "sessions": ((time(9, 0), time(11, 30)), (time(12, 30), time(15, 30)))},
    "KR": {"tz": "Asia/Seoul", "sessions": ((time(9, 0), time(15, 30)),)},
    "US": {"tz": "America/New_York", "sessions": ((time(9, 30), time(16, 0)),)},
}


def number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def convert_yield(value: float | None, quote_kind: str) -> float | None:
    return value / 10 if quote_kind == "yield" and value is not None else value


def market_timezone(market: str) -> ZoneInfo:
    return ZoneInfo(MARKET_SCHEDULES.get(market, {}).get("tz", "Asia/Taipei"))


def market_datetime_from_timestamp(value: Any, market: str) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), market_timezone(market))
    except (TypeError, ValueError, OSError):
        return None


def taipei_iso_from_timestamp(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(int(value), ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds")
    except (TypeError, ValueError, OSError):
        return None


def market_session_state(market: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or NOW
    local = now.astimezone(market_timezone(market))
    weekday = local.weekday()
    sessions = MARKET_SCHEDULES.get(market, {}).get("sessions", ())
    is_weekday = weekday < 5
    is_open = is_weekday and any(start <= local.time() <= end for start, end in sessions)
    local_minutes = local.hour * 60 + local.minute
    first_start = sessions[0][0].hour * 60 + sessions[0][0].minute if sessions else 0
    preopen = bool(is_weekday and sessions and first_start - 5 <= local_minutes < first_start)
    closed_today = bool(is_weekday and sessions and local.time() > sessions[-1][1])
    return {
        "market_now": local,
        "market_date": local.date().isoformat(),
        "is_open": bool(is_open),
        "preopen": bool(preopen),
        "closed_today": bool(closed_today),
    }


def parse_yahoo_candles(chart: dict[str, Any], market: str, quote_kind: str | None = None) -> list[dict[str, Any]]:
    # Backward-compatible two-argument form: parse_yahoo_candles(chart, quote_kind).
    if quote_kind is None:
        quote_kind = market
        market = "US"
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
        stamp = market_datetime_from_timestamp(timestamps[index], market)
        values = [
            convert_yield(number(opens[index]), quote_kind),
            convert_yield(number(highs[index]), quote_kind),
            convert_yield(number(lows[index]), quote_kind),
            convert_yield(number(closes[index]), quote_kind),
        ]
        if stamp is None or any(value is None for value in values):
            continue
        open_value, high_value, low_value, close_value = values
        if high_value < low_value:
            high_value, low_value = low_value, high_value
        rows.append({
            "date": stamp.date().isoformat(),
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



def daily_reference(candles: list[dict[str, Any]], live_price: float | None, market_date: str | None = None) -> dict[str, Any]:
    """Compatibility helper for tests and downstream tools.

    The v11.4.38 publisher uses same-session-price-vs-adjacent-close. This
    helper preserves the old adjacent-daily-candles API without ever using
    Yahoo chartPreviousClose, which can refer to the beginning of a range.
    """
    valid = sorted(
        {str(row.get("date")): row for row in candles if row.get("date") and number(row.get("close")) is not None}.values(),
        key=lambda row: str(row.get("date")),
    )
    if not valid:
        return {"price": live_price, "previous_close": None, "change": None, "change_percent": None, "reference_date": market_date, "previous_reference_date": None}
    latest = valid[-1]
    price = live_price if live_price is not None else number(latest.get("close"))
    if market_date and str(latest.get("date")) < market_date:
        previous = number(latest.get("close")); previous_date = str(latest.get("date")); reference_date = market_date
    elif len(valid) >= 2:
        previous = number(valid[-2].get("close")); previous_date = str(valid[-2].get("date")); reference_date = str(latest.get("date"))
    else:
        previous = None; previous_date = None; reference_date = str(latest.get("date"))
    change = price - previous if price is not None and previous is not None else None
    percent = change / previous * 100 if change is not None and previous not in (None, 0) else None
    return {"price": price, "previous_close": previous, "change": change, "change_percent": percent, "reference_date": reference_date, "previous_reference_date": previous_date}

def valid_ohlc(open_value: float | None, high_value: float | None, low_value: float | None, close_value: float | None) -> bool:
    if any(value is None for value in (open_value, high_value, low_value, close_value)):
        return False
    return high_value >= max(open_value, close_value) and low_value <= min(open_value, close_value) and high_value >= low_value


def meta_session_candle(meta: dict[str, Any], market: str, quote_kind: str) -> dict[str, Any] | None:
    quote_dt = market_datetime_from_timestamp(meta.get("regularMarketTime"), market)
    if quote_dt is None:
        return None
    price = convert_yield(number(meta.get("regularMarketPrice")), quote_kind)
    open_value = convert_yield(number(meta.get("regularMarketOpen")), quote_kind)
    high_value = convert_yield(number(meta.get("regularMarketDayHigh")), quote_kind)
    low_value = convert_yield(number(meta.get("regularMarketDayLow")), quote_kind)
    if not valid_ohlc(open_value, high_value, low_value, price):
        return None
    return {
        "date": quote_dt.date().isoformat(),
        "timestamp": int(meta.get("regularMarketTime")),
        "open": open_value,
        "high": high_value,
        "low": low_value,
        "close": price,
        "volume": number(meta.get("regularMarketVolume")),
        "source": "Yahoo live session",
    }


def merge_candles(primary: list[dict[str, Any]], fallback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {row.get("date"): row for row in fallback if row.get("date")}
    for row in primary:
        if row.get("date"):
            merged[row["date"]] = row
    return [merged[key] for key in sorted(merged)][-CANDLE_LIMIT:]


def build_session_row(chart: dict[str, Any], symbol: str, name: str, market: str, quote_kind: str) -> dict[str, Any]:
    meta = chart.get("meta") or {}
    candles = parse_yahoo_candles(chart, market, quote_kind)
    live_candle = meta_session_candle(meta, market, quote_kind)
    if live_candle:
        candles = merge_candles([live_candle], candles)

    valid = [row for row in candles if valid_ohlc(number(row.get("open")), number(row.get("high")), number(row.get("low")), number(row.get("close")))]
    valid.sort(key=lambda row: str(row.get("date")))
    if not valid:
        raise RuntimeError("Yahoo returned no valid daily candle or live-session OHLC")

    latest = valid[-1]
    session_date = str(latest["date"])
    previous = number(valid[-2]["close"]) if len(valid) >= 2 else convert_yield(number(meta.get("regularMarketPreviousClose") or meta.get("previousClose")), quote_kind)
    price = number(latest["close"])
    change = price - previous if price is not None and previous is not None else None
    change_percent = change / previous * 100 if change is not None and previous not in (None, 0) else None
    quote_dt = market_datetime_from_timestamp(meta.get("regularMarketTime"), market)
    quote_age = (NOW.astimezone(market_timezone(market)) - quote_dt).total_seconds() if quote_dt else None
    schedule = market_session_state(market)
    window_open = bool(schedule["is_open"])
    session_confirmed = session_date == schedule["market_date"]
    verified_open = window_open and session_confirmed
    stale_reasons: list[str] = []
    unconfirmed_reason = None
    if window_open and not session_confirmed:
        unconfirmed_reason = f"尚未確認 {schedule['market_date']} 交易資料；可能休市或行情尚未開出"
    elif verified_open and (quote_age is None or quote_age > 180):
        stale_reasons.append("盤中超過 3 分鐘未更新")
    freshness_status = "stale" if stale_reasons else "live" if verified_open else "unconfirmed" if unconfirmed_reason else "closed"

    row = {
        "symbol": symbol,
        "name": name,
        "market": market,
        "quote_kind": quote_kind,
        "price": price,
        "previous_close": previous,
        "change": change,
        "change_percent": change_percent,
        "reference_date": session_date,
        "previous_reference_date": str(valid[-2]["date"]) if len(valid) >= 2 else "source-meta",
        "change_basis": "same-session-price-vs-adjacent-close",
        "session_date": session_date,
        "price_date": session_date,
        "ohlc_date": session_date,
        "open": latest["open"],
        "high": latest["high"],
        "low": latest["low"],
        "close": latest["close"],
        "volume": latest.get("volume"),
        "currency": meta.get("currency"),
        "market_at": taipei_iso_from_timestamp(meta.get("regularMarketTime")),
        "market_at_local": quote_dt.isoformat(timespec="seconds") if quote_dt else None,
        "quote_age_seconds": quote_age,
        "display_suffix": "%" if quote_kind == "yield" else "",
        "candles": valid[-CANDLE_LIMIT:] if symbol in KLINE_SYMBOLS else [],
        "candle_count": min(len(valid), CANDLE_LIMIT) if symbol in KLINE_SYMBOLS else 0,
        "candle_interval": "1d" if symbol in KLINE_SYMBOLS else None,
        "candle_range": "3mo" if symbol in KLINE_SYMBOLS else None,
        "source": "Yahoo public chart API",
        "candle_source": "Yahoo daily chart + same-session live OHLC",
        "data_status": "stale" if stale_reasons else "cached" if unconfirmed_reason else "live",
        "freshness_status": freshness_status,
        "stale_reason": "；".join(stale_reasons) or unconfirmed_reason,
        "validation_status": "verified",
        "market_open": verified_open,
    }
    validate_market_row(row)
    return row


def validate_market_row(row: dict[str, Any]) -> None:
    price, previous = number(row.get("price")), number(row.get("previous_close"))
    open_value, high_value, low_value, close_value = (number(row.get(key)) for key in ("open", "high", "low", "close"))
    if not valid_ohlc(open_value, high_value, low_value, close_value):
        raise ValueError(f"{row.get('symbol')} display OHLC is incomplete or invalid")
    if price is None or not (low_value <= price <= high_value):
        raise ValueError(f"{row.get('symbol')} live price is outside same-session high/low")
    session_dates = {str(row.get(key) or "") for key in ("session_date", "price_date", "ohlc_date")}
    if len(session_dates) != 1 or "" in session_dates:
        raise ValueError(f"{row.get('symbol')} mixed-session price/OHLC")
    change, percent = number(row.get("change")), number(row.get("change_percent"))
    if previous is not None:
        expected = price - previous
        expected_percent = expected / previous * 100 if previous else None
        if change is None or abs(change - expected) > max(1e-6, abs(expected) * 1e-8):
            raise ValueError(f"{row.get('symbol')} change arithmetic mismatch")
        if expected_percent is not None and (percent is None or abs(percent - expected_percent) > 1e-7):
            raise ValueError(f"{row.get('symbol')} percentage arithmetic mismatch")
    for candle in row.get("candles") or []:
        if not valid_ohlc(*(number(candle.get(key)) for key in ("open", "high", "low", "close"))):
            raise ValueError(f"{row.get('symbol')} contains invalid candle")


def fetch_yahoo(session: requests.Session, symbol: str, name: str, market: str, quote_kind: str) -> dict[str, Any]:
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
    return build_session_row(result[0], symbol, name, market, quote_kind)


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
            values = [
                number(row.get("OpeningIndex") or row.get("開盤指數") or row.get("open")),
                number(row.get("HighestIndex") or row.get("最高指數") or row.get("high")),
                number(row.get("LowestIndex") or row.get("最低指數") or row.get("low")),
                number(row.get("ClosingIndex") or row.get("收盤指數") or row.get("close")),
            ]
        elif isinstance(row, (list, tuple)) and len(row) >= 5:
            date = parse_roc_date(row[0]); values = list(map(number, row[1:5]))
        else:
            continue
        if not date or not valid_ohlc(*values):
            continue
        parsed.append({"date": date, "open": values[0], "high": values[1], "low": values[2], "close": values[3], "volume": None, "source": "TWSE official TAIEX history"})
    return parsed


def fetch_nikkei_official(session: requests.Session) -> list[dict[str, Any]]:
    response=session.get(NIKKEI_DAILY_CSV,headers=HEADERS,timeout=18)
    response.raise_for_status()
    text=response.content.decode("utf-8-sig",errors="replace")
    rows=[]
    for raw in csv.DictReader(StringIO(text)):
        date_raw=str(raw.get("Date") or raw.get("date") or "").strip()
        parsed=None
        for pattern in ("%Y/%m/%d","%Y-%m-%d","%b/%d/%Y"):
            try: parsed=datetime.strptime(date_raw,pattern).date().isoformat();break
            except ValueError: pass
        if not parsed:continue
        values=[number(raw.get("Open") or raw.get("open")),number(raw.get("High") or raw.get("high")),number(raw.get("Low") or raw.get("low")),number(raw.get("Close") or raw.get("close"))]
        if not valid_ohlc(*values):continue
        rows.append({"date":parsed,"open":values[0],"high":values[1],"low":values[2],"close":values[3],"volume":None,"source":"Nikkei official daily data"})
    return rows[-CANDLE_LIMIT:]


def enrich_nikkei_with_official(session: requests.Session, yahoo_row: dict[str, Any]) -> dict[str, Any]:
    official=fetch_nikkei_official(session)
    if not official:return yahoo_row
    yahoo_candles=yahoo_row.get("candles") or []
    schedule=market_session_state("JP")
    session_date=str(yahoo_row.get("session_date") or "")
    official_by_date={str(row.get("date")):row for row in official}
    if not schedule["is_open"] and session_date in official_by_date:
        display=official_by_date[session_date]
        idx=next((i for i,row in enumerate(official) if row["date"]==session_date),len(official)-1)
        previous=number(official[idx-1]["close"]) if idx>0 else number(yahoo_row.get("previous_close"))
        price=number(display["close"]);change=price-previous if price is not None and previous is not None else None
        percent=change/previous*100 if change is not None and previous not in (None,0) else None
        row={**yahoo_row,"price":price,"previous_close":previous,"change":change,"change_percent":percent,"open":display["open"],"high":display["high"],"low":display["low"],"close":display["close"],"candles":merge_candles(official,yahoo_candles),"candle_source":"Nikkei official daily history + Yahoo live fallback","source":"Nikkei official completed-session validation","validation_source":"Nikkei official daily CSV"}
    else:
        prior=[row for row in official if row["date"]<session_date]
        previous=number(prior[-1]["close"]) if prior else number(yahoo_row.get("previous_close"))
        price=number(yahoo_row.get("price"));change=price-previous if price is not None and previous is not None else None
        percent=change/previous*100 if change is not None and previous not in (None,0) else None
        row={**yahoo_row,"previous_close":previous,"change":change,"change_percent":percent,"candles":merge_candles(official,yahoo_candles),"candle_source":"Nikkei official daily history + Yahoo same-session live candle","source":"Yahoo live quote validated against Nikkei official completed history","validation_source":"Nikkei official daily CSV"}
    row["candle_count"]=len(row.get("candles") or [])
    validate_market_row(row)
    return row


def fetch_twse_taiex(session: requests.Session, months: int = 4) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}; errors: list[str] = []
    for offset in range(months):
        year, month = month_start(NOW.year, NOW.month, offset)
        try:
            response = session.get(TWSE_TAIEX, params={"response": "json", "date": f"{year:04d}{month:02d}01"}, headers=HEADERS, timeout=18)
            response.raise_for_status()
            for candle in parse_twse_payload(response.json()): rows[candle["date"]] = candle
        except Exception as exc:
            errors.append(f"{year:04d}-{month:02d}: {exc}")
    if not rows:
        raise RuntimeError("TWSE TAIEX history unavailable: " + "; ".join(errors[:3]))
    return [rows[key] for key in sorted(rows)][-CANDLE_LIMIT:]


def enrich_taiex_with_twse(session: requests.Session, yahoo_row: dict[str, Any]) -> dict[str, Any]:
    official = fetch_twse_taiex(session)
    # Preserve Yahoo's current-session candle when TWSE's completed history has
    # not published that session yet.
    yahoo_candles = yahoo_row.get("candles") or []
    candles = merge_candles(official, yahoo_candles)
    session_date = str(yahoo_row.get("session_date") or "")
    display = next((row for row in reversed(candles) if str(row.get("date")) == session_date), None)
    if display is None:
        raise ValueError("TWSE/Yahoo session date mismatch")
    row = {
        **yahoo_row,
        "candles": candles,
        "candle_count": len(candles),
        "candle_source": "TWSE official history + Yahoo same-session live candle",
        "source": "TWSE official history + Yahoo live quote",
    }
    validate_market_row(row)
    return row


def cached_row(previous: dict[str, Any] | None, name: str, market: str, quote_kind: str, error: str) -> dict[str, Any]:
    if not previous:
        return empty_row("", name, market, quote_kind, error)
    return {
        **previous,
        "name": name,
        "market": market,
        "quote_kind": quote_kind,
        "data_status": "cached",
        "freshness_status": "stale",
        "stale_reason": f"最新資料驗證失敗，保留上次正確資料：{error[:260]}",
        "last_error": error[:500],
        "validation_status": "cached-last-verified",
    }


def empty_row(symbol: str, name: str, market: str, quote_kind: str, error: str) -> dict[str, Any]:
    return {
        "symbol": symbol, "name": name, "market": market, "quote_kind": quote_kind,
        "price": None, "previous_close": None, "change": None, "change_percent": None,
        "open": None, "high": None, "low": None, "close": None, "volume": None,
        "market_at": None, "display_suffix": "%" if quote_kind == "yield" else "",
        "candles": [], "candle_count": 0,
        "candle_interval": "1d" if symbol in KLINE_SYMBOLS else None,
        "candle_range": "3mo" if symbol in KLINE_SYMBOLS else None,
        "data_status": "waiting", "freshness_status": "unavailable",
        "validation_status": "unavailable", "last_error": error[:500],
    }


def main() -> None:
    old = read_json(DATA / "market-snapshot.json", {"items": []})
    old_by_symbol = {str(row.get("symbol")): row for row in old.get("items") or []}
    session = requests.Session(); rows: list[dict[str, Any]] = []; warnings: list[str] = []
    for symbol, name, market, quote_kind in SYMBOLS:
        previous = old_by_symbol.get(symbol)
        try:
            row = fetch_yahoo(session, symbol, name, market, quote_kind)
            if symbol == "^TWII":
                try:
                    row = enrich_taiex_with_twse(session, row)
                except Exception as exc:
                    warnings.append(f"TWSE ^TWII: {exc}")
                    row["candle_source"] = "Yahoo same-session chart fallback"
                    row["source"] = "Yahoo public chart API (TWSE history unavailable)"
            elif symbol == "^N225":
                try:
                    row = enrich_nikkei_with_official(session,row)
                except Exception as exc:
                    warnings.append(f"Nikkei ^N225 official validation: {exc}")
                    row["validation_source"]="Yahoo only; Nikkei official validation unavailable"
            if symbol in KLINE_SYMBOLS and len(row.get("candles") or []) < 10 and previous:
                row["candles"] = merge_candles(row.get("candles") or [], previous.get("candles") or [])
                row["candle_count"] = len(row["candles"])
            validate_market_row(row)
            rows.append(row)
        except Exception as exc:
            warning = f"{symbol}: {exc}"; warnings.append(warning)
            cached = cached_row(previous, name, market, quote_kind, warning) if previous else empty_row(symbol, name, market, quote_kind, warning)
            cached["symbol"] = symbol
            rows.append(cached)

    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "source": "TWSE official TAIEX history + Yahoo same-session quote/OHLC",
            "warnings": warnings,
            "kline_symbols": sorted(KLINE_SYMBOLS),
            "kline_interval": "1d",
            "kline_range": "3mo",
            "supported_intervals": ["5m", "15m", "30m", "60m", "4h", "1d", "1wk", "1mo"],
            "note": "Price, change and OHLC must share one exchange session. Mixed-session or stale intraday payloads fail closed.",
            "quality_policy": "fail-closed-on-mixed-session-stale-or-invalid-ohlc",
            "polling_policy": "one-minute while any tracked market is open; fifteen-minute off-session health checks; GitHub Actions is fallback only",
        },
        "items": rows,
    }
    write_payload("market-snapshot.json", "__MARKET_SNAPSHOT_SEED__", payload)


if __name__ == "__main__":
    main()
