#!/usr/bin/env python3
"""Update Taiwan day-trading and margin-financing/short-selling data.

The updater uses official TWSE and TPEx endpoints, keeps the previous successful
market when one exchange is temporarily unavailable, and never turns a missing
value into zero.  Individual rows are stored for the asset page; the home page
uses the market summaries in the same payload.
"""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import requests


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "tw-chips.json"
SEED = DATA / "tw-chips-seed.js"
TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime.now(TAIPEI)

TWSE_DAY = "https://www.twse.com.tw/rwd/zh/afterTrading/TWTB4U"
TWSE_MARGIN = "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
TPEX_DAY_CANDIDATES = (
    "https://www.tpex.org.tw/openapi/v1/tpex_day_trading",
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_day_trading",
    "https://www.tpex.org.tw/www/zh-tw/intraday/stat?response=json",
)
TPEX_MARGIN_CANDIDATES = (
    "https://www.tpex.org.tw/openapi/v1/tpex_margin_trading",
    "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_trading",
    "https://www.tpex.org.tw/www/zh-tw/margin/marginBalance?response=json",
    "https://www.tpex.org.tw/www/zh-tw/margin/margin?response=json",
)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.0; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6",
}


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def clean(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).replace("（", "(").replace("）", ")")


def number(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if text in {"", "-", "--", "---", "N/A", "null"}:
        return None
    try:
        result = float(text)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def first(row: dict[str, Any], includes: Iterable[str], excludes: Iterable[str] = ()) -> float | None:
    include_tokens = tuple(clean(token) for token in includes)
    exclude_tokens = tuple(clean(token) for token in excludes)
    for key, value in row.items():
        label = clean(key)
        if all(token in label for token in include_tokens) and not any(token in label for token in exclude_tokens):
            parsed = number(value)
            if parsed is not None:
                return parsed
    return None


def value_at(row: dict[str, Any], alternatives: Iterable[Iterable[str]], excludes: Iterable[str] = ()) -> float | None:
    for tokens in alternatives:
        value = first(row, tokens, excludes)
        if value is not None:
            return value
    return None


def rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    rows: list[dict[str, Any]] = []
    if isinstance(payload.get("data"), list) and payload.get("fields"):
        fields = [str(field) for field in payload["fields"]]
        rows.extend(dict(zip(fields, raw)) for raw in payload["data"] if isinstance(raw, list))
    for table in payload.get("tables") or []:
        if not isinstance(table, dict):
            continue
        fields = [str(field) for field in table.get("fields") or []]
        data = table.get("data") or []
        if fields:
            rows.extend(dict(zip(fields, raw)) for raw in data if isinstance(raw, list))
    for key in ("items", "rows"):
        rows.extend(row for row in payload.get(key) or [] if isinstance(row, dict))
    return rows


def symbol_of(row: dict[str, Any]) -> str:
    for key, value in row.items():
        label = clean(key).lower()
        if any(token in label for token in ("證券代號", "股票代號", "code", "symbol")):
            symbol = str(value or "").strip().upper()
            if re.fullmatch(r"(?:[1-9]\d{3}|00\d{2,4}[A-Z]?)", symbol):
                return symbol
    return ""


def date_of(row: dict[str, Any]) -> str | None:
    for key, value in row.items():
        if any(token in clean(key).lower() for token in ("日期", "date")):
            text = str(value or "").strip()
            match = re.search(r"(\d{4})[/\-]?(\d{2})[/\-]?(\d{2})", text)
            if match:
                return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
            roc = re.search(r"(\d{3})[/\-](\d{1,2})[/\-](\d{1,2})", text)
            if roc:
                return f"{int(roc.group(1))+1911:04d}-{int(roc.group(2)):02d}-{int(roc.group(3)):02d}"
    return None


def blank_item() -> dict[str, Any]:
    return {
        "day_trading": {"volume": None, "trade_value": None, "ratio_percent": None},
        "margin": {"balance_shares": None, "balance_amount": None, "change_shares": None},
        "short": {"balance_shares": None, "change_shares": None},
    }


def parse_day_rows(rows: list[dict[str, Any]], exchange: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any], str | None]:
    items: dict[str, dict[str, Any]] = {}
    market = {"ratio_percent": None, "trade_value": None, "volume": None}
    reported_dates: list[str] = []
    for row in rows:
        reported = date_of(row)
        if reported:
            reported_dates.append(reported)
        symbol = symbol_of(row)
        volume = value_at(row, (("當沖", "成交股數"), ("當日沖銷", "股數"), ("DayTrade", "Volume")))
        trade_value = value_at(row, (("當沖", "成交金額"), ("當日沖銷", "金額"), ("DayTrade", "Value")))
        ratio = value_at(row, (("當沖", "比率"), ("當日沖銷", "比重"), ("DayTrade", "Ratio")))
        if symbol:
            item = items.setdefault(f"{exchange}:{symbol}", blank_item())
            item["day_trading"] = {"volume": volume, "trade_value": trade_value, "ratio_percent": ratio}
            item["date"] = reported
            continue
        if volume is not None:
            market["volume"] = volume
        if trade_value is not None:
            market["trade_value"] = trade_value
        if ratio is not None:
            market["ratio_percent"] = ratio
    if market["volume"] is None:
        values = [item["day_trading"]["volume"] for item in items.values() if item["day_trading"]["volume"] is not None]
        market["volume"] = sum(values) if values else None
    if market["trade_value"] is None:
        values = [item["day_trading"]["trade_value"] for item in items.values() if item["day_trading"]["trade_value"] is not None]
        market["trade_value"] = sum(values) if values else None
    return items, market, max(reported_dates) if reported_dates else None


def parse_margin_rows(rows: list[dict[str, Any]], exchange: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Any], str | None]:
    items: dict[str, dict[str, Any]] = {}
    margin_market = {"balance_shares": None, "balance_amount": None, "change_shares": None}
    short_market = {"balance_shares": None, "change_shares": None}
    reported_dates: list[str] = []
    for row in rows:
        reported = date_of(row)
        if reported:
            reported_dates.append(reported)
        symbol = symbol_of(row)
        margin_balance = value_at(row, (("融資", "今日餘額"), ("融資", "餘額"), ("Margin", "Balance")), excludes=("金額",))
        margin_amount = value_at(row, (("融資", "金額"), ("Margin", "Amount")))
        margin_change = value_at(row, (("融資", "增減"), ("Margin", "Change")))
        short_balance = value_at(row, (("融券", "今日餘額"), ("融券", "餘額"), ("Short", "Balance")))
        short_change = value_at(row, (("融券", "增減"), ("Short", "Change")))
        if symbol:
            item = items.setdefault(f"{exchange}:{symbol}", blank_item())
            item["margin"] = {"balance_shares": margin_balance, "balance_amount": margin_amount, "change_shares": margin_change}
            item["short"] = {"balance_shares": short_balance, "change_shares": short_change}
            item["date"] = reported
            continue
        label = " ".join(str(value) for value in row.values())
        if "融資" in label:
            if margin_balance is None:
                margin_balance = value_at(row, (("今日餘額",), ("餘額",)), excludes=("融券",))
            margin_market = {"balance_shares": margin_balance, "balance_amount": margin_amount, "change_shares": margin_change}
        if "融券" in label:
            if short_balance is None:
                short_balance = value_at(row, (("今日餘額",), ("餘額",)), excludes=("融資",))
            short_market = {"balance_shares": short_balance, "change_shares": short_change}
    for market, section, key in ((margin_market, "margin", "balance_shares"), (short_market, "short", "balance_shares")):
        if market[key] is None:
            values = [item[section][key] for item in items.values() if item[section][key] is not None]
            market[key] = sum(values) if values else None
        if market["change_shares"] is None:
            values = [item[section]["change_shares"] for item in items.values() if item[section]["change_shares"] is not None]
            market["change_shares"] = sum(values) if values else None
    return items, margin_market, short_market, max(reported_dates) if reported_dates else None


def merge_items(*groups: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for group in groups:
        for key, value in group.items():
            current = merged.setdefault(key, blank_item())
            current.update({name: section for name, section in value.items() if name not in {"day_trading", "margin", "short"}})
            for section in ("day_trading", "margin", "short"):
                if section in value:
                    current[section].update(value[section])
    return merged


def get_json(session: requests.Session, url: str, params: dict[str, Any] | None = None) -> Any:
    response = session.get(url, params=params, headers=HEADERS, timeout=35)
    response.raise_for_status()
    return response.json()


def first_available(session: requests.Session, urls: Iterable[str]) -> Any:
    error: Exception | None = None
    for url in urls:
        try:
            return get_json(session, url)
        except Exception as exc:  # API names occasionally change; preserve old data.
            error = exc
    if error:
        raise error
    raise RuntimeError("No endpoint configured")


def fetch_exchange(session: requests.Session, exchange: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    if exchange == "TWSE":
        day_payload = get_json(session, TWSE_DAY, {"response": "json", "selectType": "All"})
        margin_payload = get_json(session, TWSE_MARGIN, {"response": "json", "selectType": "ALL"})
    else:
        day_payload = first_available(session, TPEX_DAY_CANDIDATES)
        margin_payload = first_available(session, TPEX_MARGIN_CANDIDATES)
    day_items, day_market, day_date = parse_day_rows(rows_from_payload(day_payload), exchange)
    margin_items, margin_market, short_market, margin_date = parse_margin_rows(rows_from_payload(margin_payload), exchange)
    items = merge_items(day_items, margin_items)
    if not items and not any(value is not None for value in (*day_market.values(), *margin_market.values(), *short_market.values())):
        raise RuntimeError(f"{exchange} official payload had no recognised chip fields")
    reported = max(value for value in (day_date, margin_date) if value) if day_date or margin_date else None
    return {
        "date": reported,
        "day_trading": day_market,
        "margin": margin_market,
        "short": short_market,
    }, items


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    previous = read_json(OUT, {"markets": {}, "items": {}})
    markets = dict(previous.get("markets") or {})
    item_groups = [dict(previous.get("items") or {})]
    statuses: dict[str, str] = {}
    session = requests.Session()
    for exchange, key in (("TWSE", "twse"), ("TPEx", "tpex")):
        try:
            market, items = fetch_exchange(session, exchange)
            markets[key] = market
            item_groups.append(items)
            statuses[key] = "ok"
        except Exception as exc:
            statuses[key] = f"stale: {str(exc)[:120]}" if markets.get(key) else f"unavailable: {str(exc)[:120]}"
    if not any(status == "ok" for status in statuses.values()):
        raise SystemExit("No official Taiwan chip source succeeded; previous file was kept.")
    items = merge_items(*item_groups)
    dates = [market.get("date") for market in markets.values() if isinstance(market, dict) and market.get("date")]
    payload = {
        "metadata": {
            "version": "v11.0.0",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "trading_date": max(dates) if dates else None,
            "mode": "live",
            "source": "TWSE／TPEx 官方盤後資料",
            "status": statuses,
            "note": "當沖資料於盤後彙整；融資券為官方餘額。分點成交不等於券商自有持股。",
        },
        "markets": markets,
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED.write_text("window.__TW_CHIPS_SEED__ = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"Taiwan chips: {len(items)} symbols; status {statuses}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
