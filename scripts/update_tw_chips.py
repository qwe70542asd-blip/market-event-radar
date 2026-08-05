#!/usr/bin/env python3
"""Update Taiwan institutional, margin, short and day-trading data.

Official TWSE structured data is primary. Yahoo Taiwan pages are used only as a
reference fallback and to backfill recent history. A failed run always preserves
the last valid payload and never publishes an empty file.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.15"
TIMEOUT = 24
YAHOO_BATCH = 24
PRIORITY_SYMBOLS = [
    "00981A", "00403A", "00631L", "006208", "0050", "0056", "00878", "00919",
    "2330", "2317", "2454", "3231", "2344", "2408", "2059",
]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
    "Accept": "application/json,text/html,application/xhtml+xml,*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
DATE_RE = re.compile(r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}")
NUMBER_RE = re.compile(r"^[+\-−]?[\d,.]+(?:\.\d+)?%?$")


def number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("−", "-").replace("＋", "+")
    text = re.sub(r"\([^)]*\)", "", text).replace("%", "").strip()
    if text in {"", "-", "—", "--", "N/A", "null"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        match = re.search(r"[+\-]?\d+(?:\.\d+)?", text)
        return float(match.group()) if match else None


def integer_or_float(value: float | None) -> int | float | None:
    if value is None:
        return None
    rounded = round(value)
    return int(rounded) if abs(value - rounded) < 1e-9 else round(value, 4)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalized_key(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", clean(value)).lower()


def field_pair(row: dict[str, Any], *needles: str) -> tuple[str | None, Any]:
    normalized = [(key, normalized_key(key)) for key in row]
    for needle in needles:
        target = normalized_key(needle)
        for key, key_norm in normalized:
            if key_norm == target:
                return key, row.get(key)
    for needle in needles:
        target = normalized_key(needle)
        for key, key_norm in normalized:
            if target and target in key_norm:
                return key, row.get(key)
    return None, None


def field(row: dict[str, Any], *needles: str) -> Any:
    return field_pair(row, *needles)[1]


def symbol_from_row(row: dict[str, Any]) -> str:
    value = field(row, "證券代號", "股票代號", "證券代碼", "股票代碼", "代號")
    return re.sub(r"[^0-9A-Za-z]", "", str(value or "")).upper()


def date_value(value: Any) -> str | None:
    text = clean(value)
    match = DATE_RE.search(text)
    if not match:
        compact = re.search(r"(20\d{2})(\d{2})(\d{2})", text)
        if compact:
            return f"{compact.group(1)}-{compact.group(2)}-{compact.group(3)}"
        return None
    parts = re.split(r"[/-]", match.group())
    return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"


def row_date(row: dict[str, Any]) -> str | None:
    for key, value in row.items():
        if "日期" in str(key) or normalized_key(key) in {"date", "tradedate"}:
            parsed = date_value(value)
            if parsed:
                return parsed
    return None


def as_lots(value: Any, key: str | None = None) -> int | float | None:
    parsed = number(value)
    if parsed is None:
        return None
    label = str(key or "")
    if "張" in label:
        return integer_or_float(parsed)
    if "股" in label or abs(parsed) >= 1_000_000:
        return integer_or_float(parsed / 1000)
    return integer_or_float(parsed)


def get_rows(url: str) -> list[dict[str, Any]]:
    response = SESSION.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    if isinstance(payload.get("data"), list) and payload.get("fields"):
        fields = payload.get("fields") or []
        return [dict(zip(fields, row)) for row in payload.get("data") or [] if isinstance(row, list)]
    for key in ("data", "items", "results"):
        rows = payload.get(key)
        if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
            return rows
    return []


def try_rows(urls: Iterable[str], errors: list[dict[str, str]], label: str) -> tuple[list[dict[str, Any]], str | None]:
    for url in urls:
        try:
            rows = get_rows(url)
            if rows:
                return rows, url
        except Exception as exc:
            errors.append({"source": label, "url": url, "error": str(exc)[:220]})
    return [], None


def parse_institutional(rows: list[dict[str, Any]], assets: dict[str, dict[str, Any]], source_url: str | None) -> tuple[dict[str, dict[str, Any]], dict[str, Any], str | None]:
    output: dict[str, dict[str, Any]] = {}
    latest_date = None
    totals = {"foreign_net": 0.0, "trust_net": 0.0, "dealer_net": 0.0, "total_net": 0.0}
    total_seen = {key: False for key in totals}
    for row in rows:
        symbol = symbol_from_row(row)
        if not symbol:
            continue
        foreign_key, foreign_raw = field_pair(row, "外陸資買賣超股數不含外資自營商", "外資買賣超股數", "外陸資買賣超")
        trust_key, trust_raw = field_pair(row, "投信買賣超股數", "投信買賣超")
        dealer_key, dealer_raw = field_pair(row, "自營商買賣超股數", "自營商買賣超")
        proprietary_key, proprietary_raw = field_pair(row, "自營商自行買賣買賣超股數", "自營商自行買賣")
        hedge_key, hedge_raw = field_pair(row, "自營商避險買賣超股數", "自營商避險")
        total_key, total_raw = field_pair(row, "三大法人買賣超股數", "三大法人買賣超")
        foreign = as_lots(foreign_raw, foreign_key)
        trust = as_lots(trust_raw, trust_key)
        dealer = as_lots(dealer_raw, dealer_key)
        if dealer is None:
            proprietary = as_lots(proprietary_raw, proprietary_key)
            hedge = as_lots(hedge_raw, hedge_key)
            values = [value for value in (proprietary, hedge) if value is not None]
            dealer = integer_or_float(sum(values)) if values else None
        total = as_lots(total_raw, total_key)
        if total is None:
            values = [value for value in (foreign, trust, dealer) if value is not None]
            total = integer_or_float(sum(values)) if values else None
        traded = row_date(row) or NOW.date().isoformat()
        latest_date = max(latest_date or traded, traded)
        institutional = {key: value for key, value in {
            "foreign_net": foreign, "trust_net": trust, "dealer_net": dealer, "total_net": total,
        }.items() if value is not None}
        if not institutional:
            continue
        output[symbol] = {
            "symbol": symbol,
            "name": clean(field(row, "證券名稱", "股票名稱")) or (assets.get(symbol) or {}).get("name"),
            "asset_class": (assets.get(symbol) or {}).get("asset_class", "stock"),
            "exchange": "TWSE",
            "date": traded,
            "unit": "張",
            "institutional": institutional,
            "sources": [{"name": "TWSE 三大法人", "url": source_url, "level": "official", "date": traded}],
        }
        for key, value in institutional.items():
            totals[key] += float(value)
            total_seen[key] = True
    market = {key: integer_or_float(value) for key, value in totals.items() if total_seen[key]}
    return output, market, latest_date


def parse_margin(rows: list[dict[str, Any]], assets: dict[str, dict[str, Any]], source_url: str | None) -> tuple[dict[str, dict[str, Any]], str | None]:
    output: dict[str, dict[str, Any]] = {}
    latest_date = None
    for row in rows:
        symbol = symbol_from_row(row)
        if not symbol:
            continue
        current_margin_key, current_margin_raw = field_pair(row, "融資今日餘額", "融資餘額")
        previous_margin_key, previous_margin_raw = field_pair(row, "融資前日餘額")
        change_margin_key, change_margin_raw = field_pair(row, "融資增減", "融資餘額增減")
        current_short_key, current_short_raw = field_pair(row, "融券今日餘額", "融券餘額")
        previous_short_key, previous_short_raw = field_pair(row, "融券前日餘額")
        change_short_key, change_short_raw = field_pair(row, "融券增減", "融券餘額增減")
        margin_balance = as_lots(current_margin_raw, current_margin_key)
        previous_margin = as_lots(previous_margin_raw, previous_margin_key)
        margin_change = as_lots(change_margin_raw, change_margin_key)
        if margin_change is None and margin_balance is not None and previous_margin is not None:
            margin_change = integer_or_float(float(margin_balance) - float(previous_margin))
        short_balance = as_lots(current_short_raw, current_short_key)
        previous_short = as_lots(previous_short_raw, previous_short_key)
        short_change = as_lots(change_short_raw, change_short_key)
        if short_change is None and short_balance is not None and previous_short is not None:
            short_change = integer_or_float(float(short_balance) - float(previous_short))
        if all(value is None for value in (margin_balance, margin_change, short_balance, short_change)):
            continue
        traded = row_date(row) or NOW.date().isoformat()
        latest_date = max(latest_date or traded, traded)
        offset = as_lots(field(row, "資券互抵"), "張")
        output[symbol] = {
            "symbol": symbol,
            "name": clean(field(row, "股票名稱", "證券名稱")) or (assets.get(symbol) or {}).get("name"),
            "asset_class": (assets.get(symbol) or {}).get("asset_class", "stock"),
            "exchange": "TWSE",
            "date": traded,
            "unit": "張",
            "margin": {key: value for key, value in {"balance": margin_balance, "change": margin_change}.items() if value is not None},
            "short": {key: value for key, value in {"balance": short_balance, "change": short_change}.items() if value is not None},
            "offset_volume": offset,
            "sources": [{"name": "TWSE 融資融券", "url": source_url, "level": "official", "date": traded}],
        }
        if margin_balance not in (None, 0) and short_balance is not None:
            output[symbol]["short"]["ratio"] = round(float(short_balance) / float(margin_balance) * 100, 4)
    return output, latest_date


def parse_day_trade(rows: list[dict[str, Any]], assets: dict[str, dict[str, Any]], source_url: str | None) -> tuple[dict[str, dict[str, Any]], str | None]:
    output: dict[str, dict[str, Any]] = {}
    latest_date = None
    for row in rows:
        symbol = symbol_from_row(row)
        if not symbol:
            continue
        volume_key, volume_raw = field_pair(row, "當日沖銷成交股數", "當沖成交股數", "當日沖銷交易成交股數")
        ratio_raw = field(row, "當日沖銷成交股數占市場比重", "當沖比率", "當沖比例")
        volume = as_lots(volume_raw, volume_key)
        ratio_value = number(ratio_raw)
        if volume is None and ratio_value is None:
            continue
        traded = row_date(row) or NOW.date().isoformat()
        latest_date = max(latest_date or traded, traded)
        output[symbol] = {
            "symbol": symbol,
            "name": clean(field(row, "證券名稱", "股票名稱")) or (assets.get(symbol) or {}).get("name"),
            "asset_class": (assets.get(symbol) or {}).get("asset_class", "stock"),
            "exchange": "TWSE",
            "date": traded,
            "unit": "張",
            "day_trade": {key: value for key, value in {"volume": volume, "ratio": ratio_value}.items() if value is not None},
            "sources": [{"name": "TWSE 當沖統計", "url": source_url, "level": "official", "date": traded}],
        }
    return output, latest_date


def fetch_soup(url: str) -> BeautifulSoup:
    response = SESSION.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding or "utf-8"
    return BeautifulSoup(response.text, "lxml")


def strings_after(soup: BeautifulSoup, marker: str) -> list[str]:
    strings = [clean(value) for value in soup.stripped_strings if clean(value)]
    try:
        start = next(index for index, value in enumerate(strings) if marker in value)
    except StopIteration:
        return []
    return strings[start + 1:]


def numeric_token(value: str) -> bool:
    return bool(NUMBER_RE.fullmatch(clean(value)))


def parse_yahoo_institutional(asset: dict[str, Any]) -> dict[str, Any]:
    symbol = str(asset.get("symbol") or "").upper()
    suffix = "TWO" if str(asset.get("exchange") or "").upper() == "TPEX" else "TW"
    url = f"https://tw.stock.yahoo.com/quote/{symbol}.{suffix}/institutional-trading"
    soup = fetch_soup(url)
    stream = strings_after(soup, "法人逐日買賣超")
    history = []
    index = 0
    while index < len(stream):
        traded = date_value(stream[index])
        if not traded:
            index += 1
            continue
        numbers = []
        cursor = index + 1
        while cursor < len(stream) and not date_value(stream[cursor]) and len(numbers) < 8:
            if numeric_token(stream[cursor]):
                numbers.append(number(stream[cursor]))
            cursor += 1
        if len(numbers) >= 4:
            history.append({
                "date": traded,
                "institutional": {
                    "foreign_net": integer_or_float(numbers[0]),
                    "trust_net": integer_or_float(numbers[1]),
                    "dealer_net": integer_or_float(numbers[2]),
                    "total_net": integer_or_float(numbers[3]),
                },
                "source": "Yahoo 股市法人買賣",
                "source_url": url,
                "source_level": "reference",
            })
        index = max(cursor, index + 1)
        if len(history) >= 20:
            break
    if not history:
        raise ValueError("Yahoo 法人逐日表無可解析資料")
    latest = history[0]
    return {
        "symbol": symbol,
        "name": asset.get("name"),
        "asset_class": asset.get("asset_class"),
        "exchange": asset.get("exchange"),
        "date": latest["date"],
        "unit": "張",
        "institutional": latest["institutional"],
        "history": history,
        "sources": [{"name": "Yahoo 股市法人買賣", "url": url, "level": "reference", "date": latest["date"]}],
    }


def parse_yahoo_margin(asset: dict[str, Any]) -> dict[str, Any]:
    symbol = str(asset.get("symbol") or "").upper()
    suffix = "TWO" if str(asset.get("exchange") or "").upper() == "TPEX" else "TW"
    url = f"https://tw.stock.yahoo.com/quote/{symbol}.{suffix}/margin"
    soup = fetch_soup(url)
    stream = strings_after(soup, "資券餘額逐日增減")
    history = []
    index = 0
    while index < len(stream):
        traded = date_value(stream[index])
        if not traded:
            index += 1
            continue
        tokens: list[tuple[float, bool]] = []
        cursor = index + 1
        while cursor < len(stream) and not date_value(stream[cursor]) and len(tokens) < 14:
            token = clean(stream[cursor])
            if numeric_token(token):
                parsed = number(token)
                if parsed is not None:
                    tokens.append((parsed, token.endswith("%")))
            cursor += 1
        plain = [value for value, is_percent in tokens if not is_percent]
        percentages = [value for value, is_percent in tokens if is_percent]
        if len(plain) >= 4:
            margin_change, margin_balance, short_change, short_balance = plain[:4]
            history.append({
                "date": traded,
                "margin": {"change": integer_or_float(margin_change), "balance": integer_or_float(margin_balance), **({"usage_rate": percentages[0]} if percentages else {})},
                "short": {"change": integer_or_float(short_change), "balance": integer_or_float(short_balance), **({"usage_rate": percentages[1]} if len(percentages) > 1 else {}), **({"ratio": percentages[2]} if len(percentages) > 2 else {})},
                "offset_volume": integer_or_float(plain[4]) if len(plain) > 4 else None,
                "source": "Yahoo 股市資券變化",
                "source_url": url,
                "source_level": "reference",
            })
        index = max(cursor, index + 1)
        if len(history) >= 20:
            break
    if not history:
        raise ValueError("Yahoo 資券逐日表無可解析資料")
    latest = history[0]
    return {
        "symbol": symbol,
        "name": asset.get("name"),
        "asset_class": asset.get("asset_class"),
        "exchange": asset.get("exchange"),
        "date": latest["date"],
        "unit": "張",
        "margin": latest["margin"],
        "short": latest["short"],
        "offset_volume": latest.get("offset_volume"),
        "history": history,
        "sources": [{"name": "Yahoo 股市資券變化", "url": url, "level": "reference", "date": latest["date"]}],
    }


def deep_nonempty_merge(base: dict[str, Any], extra: dict[str, Any], prefer_base: bool = True) -> dict[str, Any]:
    result = dict(base or {})
    for key, value in (extra or {}).items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_nonempty_merge(result[key], value, prefer_base=prefer_base)
        elif key == "sources":
            combined = []
            for source in list(result.get(key) or []) + list(value or []):
                if source and source not in combined:
                    combined.append(source)
            result[key] = combined
        elif not prefer_base or result.get(key) in (None, "", [], {}):
            result[key] = value
    return result


def merge_history(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for row in group or []:
            traded = date_value(row.get("date"))
            if not traded:
                continue
            current = merged.get(traded, {"date": traded})
            merged[traded] = deep_nonempty_merge(current, row, prefer_base=True)
    return sorted(merged.values(), key=lambda row: row.get("date") or "", reverse=True)[:40]


def merge_item(old: dict[str, Any], new: dict[str, Any], official_first: bool = True) -> dict[str, Any]:
    result = deep_nonempty_merge(old or {}, new or {}, prefer_base=official_first)
    old_history = list((old or {}).get("history") or (old or {}).get("recent") or [])
    new_history = list((new or {}).get("history") or [])
    latest_snapshot = {
        "date": (new or {}).get("date"),
        "institutional": (new or {}).get("institutional"),
        "margin": (new or {}).get("margin"),
        "short": (new or {}).get("short"),
        "day_trade": (new or {}).get("day_trade"),
    }
    if latest_snapshot["date"]:
        new_history.append({key: value for key, value in latest_snapshot.items() if value not in (None, {}, [])})
    result["history"] = merge_history(new_history, old_history)
    result["recent"] = result["history"][:5]
    return result


def yahoo_one(asset: dict[str, Any]) -> tuple[str, dict[str, Any] | None, str | None]:
    symbol = str(asset.get("symbol") or "").upper()
    try:
        institutional = None
        margin = None
        errors = []
        try:
            institutional = parse_yahoo_institutional(asset)
        except Exception as exc:
            errors.append(f"法人: {exc}")
        time.sleep(.12)
        try:
            margin = parse_yahoo_margin(asset)
        except Exception as exc:
            errors.append(f"資券: {exc}")
        row = {}
        if institutional:
            row = merge_item(row, institutional, official_first=True)
        if margin:
            row = merge_item(row, margin, official_first=True)
        if not row:
            return symbol, None, "; ".join(errors) or "Yahoo 籌碼無資料"
        row["source_status"] = "partial" if errors else "ok"
        row["source_errors"] = errors
        return symbol, row, None
    except Exception as exc:
        return symbol, None, str(exc)


def candidate_batch(assets: list[dict[str, Any]], state: dict[str, Any], old_items: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
    candidates = [asset for asset in assets if asset.get("market") == "TW" and asset.get("asset_class") in {"stock", "etf"} and asset.get("symbol")]
    priority_index = {symbol: index for index, symbol in enumerate(PRIORITY_SYMBOLS)}
    candidates.sort(key=lambda asset: (priority_index.get(str(asset.get("symbol")).upper(), 9999), asset.get("asset_class") != "etf", str(asset.get("symbol"))))
    missing_priority = [asset for asset in candidates if str(asset.get("symbol")).upper() in priority_index and not (old_items.get(str(asset.get("symbol")).upper()) or {}).get("institutional")]
    cursor = int(state.get("yahoo_cursor") or 0)
    cursor = cursor if cursor < len(candidates) else 0
    rolling = candidates[cursor:cursor + YAHOO_BATCH]
    if len(rolling) < YAHOO_BATCH:
        rolling += candidates[:YAHOO_BATCH - len(rolling)]
    selected = []
    seen = set()
    for asset in missing_priority + rolling:
        symbol = str(asset.get("symbol")).upper()
        if symbol in seen:
            continue
        selected.append(asset)
        seen.add(symbol)
        if len(selected) >= YAHOO_BATCH:
            break
    return selected, (cursor + len(rolling)) % len(candidates) if candidates else 0


def main() -> None:
    default = {"metadata": {}, "markets": {}, "items": {}, "history": {}, "available_dates": [], "state": {}}
    old = read_json(DATA / "tw-chips.json", default)
    if not isinstance(old, dict):
        old = default
    items = dict(old.get("items") or {})
    state = dict(old.get("state") or {})
    assets_list = read_json(DATA / "assets.json", {"assets": []}).get("assets", [])
    asset_map = {str(asset.get("symbol") or "").upper(): asset for asset in assets_list if asset.get("symbol")}
    errors: list[dict[str, str]] = []

    institutional_rows, institutional_url = try_rows([
        "https://openapi.twse.com.tw/v1/fund/T86",
        "https://www.twse.com.tw/rwd/zh/fund/T86?response=json&selectType=ALLBUT0999",
    ], errors, "TWSE 三大法人")
    margin_rows, margin_url = try_rows([
        "https://openapi.twse.com.tw/v1/exchangeReport/MI_MARGN",
        "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?response=json&selectType=ALL",
    ], errors, "TWSE 融資融券")
    day_rows, day_url = try_rows([
        "https://openapi.twse.com.tw/v1/exchangeReport/TWTB4U",
        "https://www.twse.com.tw/rwd/zh/afterTrading/TWTB4U?response=json&selectType=All",
    ], errors, "TWSE 當沖")

    official_inst, market_inst, institutional_date = parse_institutional(institutional_rows, asset_map, institutional_url)
    official_margin, margin_date = parse_margin(margin_rows, asset_map, margin_url)
    official_day, day_date = parse_day_trade(day_rows, asset_map, day_url)
    official_symbols = set(official_inst) | set(official_margin) | set(official_day)
    for symbol in official_symbols:
        combined = {}
        for source in (official_inst.get(symbol), official_margin.get(symbol), official_day.get(symbol)):
            if source:
                combined = merge_item(combined, source, official_first=True)
        items[symbol] = merge_item(combined, items.get(symbol) or {}, official_first=True)

    batch, next_cursor = candidate_batch(assets_list, state, items)
    yahoo_success = 0
    yahoo_errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(yahoo_one, asset) for asset in batch]
        for future in as_completed(futures):
            symbol, row, error = future.result()
            if row:
                # Existing official values stay primary; Yahoo fills gaps and history.
                items[symbol] = merge_item(items.get(symbol) or {}, row, official_first=True)
                yahoo_success += 1
            elif error:
                yahoo_errors.append({"symbol": symbol, "error": error[:320]})

    dates = set(old.get("available_dates") or [])
    for value in (institutional_date, margin_date, day_date):
        if value:
            dates.add(value)
    for row in items.values():
        if row.get("date"):
            dates.add(str(row["date"]))
        for history_row in row.get("history") or []:
            if history_row.get("date"):
                dates.add(str(history_row["date"]))
    trading_date = max(dates) if dates else (old.get("metadata") or {}).get("trading_date")
    old_markets = dict(old.get("markets") or {})
    twse_market = dict(old_markets.get("twse") or {})
    if market_inst:
        twse_market["institutional"] = market_inst
        twse_market["institutional_date"] = institutional_date
    twse_market["stock_count"] = sum(1 for row in items.values() if str(row.get("exchange") or "").upper() == "TWSE")
    markets = {**old_markets, "twse": twse_market}

    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "trading_date": trading_date,
            "status": "ok" if official_symbols and yahoo_success == len(batch) else "partial" if items else "warning",
            "source": "TWSE official structured data; Yahoo Taiwan reference fallback",
            "item_count": len(items),
            "official_item_count": len(official_symbols),
            "yahoo_batch_size": len(batch),
            "yahoo_batch_success": yahoo_success,
            "note": "官方資料優先；第三方只補缺漏。失敗時保留最後成功資料，缺值不以 0 代替。",
        },
        "markets": markets,
        "items": items,
        "history": old.get("history") or {},
        "available_dates": sorted(dates, reverse=True)[:120],
        "state": {**state, "yahoo_cursor": next_cursor, "last_batch_at": NOW.isoformat(timespec="seconds")},
        "errors": (errors + yahoo_errors)[:160],
    }
    # Always serialize a valid non-empty JSON document, even when all upstreams fail.
    write_payload("tw-chips.json", "__TW_CHIPS_SEED__", payload)
    print(payload["metadata"])


if __name__ == "__main__":
    main()
