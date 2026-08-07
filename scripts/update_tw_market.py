#!/usr/bin/env python3
"""Refresh Taiwan closing quotes and online historical market turnover.

v11.4.25 always asks the official TWSE/TPEx network sources for historical
turnover from 2026-01-01. Local JSON is only a last-known-good cache; the
20-session average no longer waits for the site to accumulate one day at a time.
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

import requests

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.25"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.4.25)"}
TWSE_QUOTES = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_QUOTES = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
TWSE_FUNDS = "https://openapi.twse.com.tw/v1/opendata/t187ap47_L"
TPEX_FUNDS = "https://www.tpex.org.tw/openapi/v1/tpex_opfund_latest"
TWSE_HISTORY_OPENAPI = "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK"
TWSE_HISTORY_MONTH = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
TPEX_HISTORY_OPENAPI = "https://www.tpex.org.tw/openapi/v1/tpex_daily_trading_index"
TPEX_HISTORY_MONTH = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingIndex"
HISTORY_START = date(2026, 1, 1)


def number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").replace("元", "").strip()
    if not text or text in {"-", "--", "N/A", "null", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def first(row: dict, names: tuple[str, ...]) -> str:
    for name in names:
        value = str(row.get(name) or "").strip()
        if value:
            return value
    return ""


def parse_market_date(value: Any) -> str | None:
    text = str(value or "").strip().replace("年", "/").replace("月", "/").replace("日", "")
    digits = re.sub(r"\D", "", text)
    try:
        if len(digits) == 7:
            year, month, day = int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:7])
        elif len(digits) >= 8:
            year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
        else:
            parts = [int(x) for x in re.findall(r"\d+", text)[:3]]
            if len(parts) != 3:
                return None
            year, month, day = parts
            if year < 1911:
                year += 1911
        parsed = date(year, month, day)
        return parsed.isoformat()
    except (ValueError, TypeError):
        return None


def official_etf_codes(session: requests.Session, old_rows: list[dict]) -> tuple[set[str], list[str]]:
    codes: set[str] = set()
    warnings: list[str] = []
    sources = [
        (TWSE_FUNDS, ("基金代號", "證券代號", "Code", "SecuritiesCode", "基金證券代號"), "TWSE"),
        (TPEX_FUNDS, ("SecuritiesCompanyCode", "SecuritiesCode", "Code", "證券代號", "基金代號"), "TPEx"),
    ]
    for url, keys, label in sources:
        try:
            response = session.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list):
                raise RuntimeError("unexpected response")
            before = len(codes)
            for row in rows:
                code = first(row, keys)
                if code:
                    codes.add(code.upper())
            if len(codes) == before:
                warnings.append(f"{label} ETF list returned no recognized code")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{label} ETF list: {exc}")
    if not codes:
        codes.update(
            str(row.get("symbol") or "").upper()
            for row in old_rows
            if row.get("asset_class") == "etf" and str(row.get("symbol") or "").upper().startswith("00")
        )
    return {code for code in codes if code}, warnings


def asset_class(symbol: str, etf_codes: set[str]) -> str:
    code = symbol.upper()
    if code in etf_codes:
        return "etf"
    if re.fullmatch(r"\d{4}", code):
        return "stock"
    return "other"


def fetch_quotes(session: requests.Session, url: str, exchange: str, etf_codes: set[str]) -> list[dict]:
    response = session.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("unexpected quote response")
    output = []
    for row in payload:
        symbol = first(row, ("Code", "SecuritiesCompanyCode", "SecuritiesCode", "股票代號"))
        name = first(row, ("Name", "CompanyName", "SecuritiesCompanyName", "股票名稱"))
        price = number(first(row, ("ClosingPrice", "Close", "ClosePrice", "收盤價")))
        change = number(first(row, ("Change", "ChangeAmount", "漲跌價差")))
        if not symbol or price is None:
            continue
        previous = price - change if change is not None else None
        output.append({
            "symbol": symbol,
            "name": name,
            "exchange": exchange,
            "asset_class": asset_class(symbol, etf_codes),
            "price": price,
            "previous_close": previous,
            "change": change,
            "change_percent": change / previous * 100 if change is not None and previous not in (None, 0) else None,
            "open": number(first(row, ("OpeningPrice", "Open", "開盤價"))),
            "high": number(first(row, ("HighestPrice", "High", "最高價"))),
            "low": number(first(row, ("LowestPrice", "Low", "最低價"))),
            "volume": number(first(row, ("TradeVolume", "TradingShares", "TradingVolume", "成交股數"))),
            "trade_value": number(first(row, ("TradeValue", "TransactionAmount", "成交金額"))),
            "quote_date": NOW.date().isoformat(),
            "quote_time": NOW.strftime("%H:%M"),
            "status": "official-close",
        })
    return output


def rows_and_fields(payload: Any) -> tuple[list[Any], list[str]]:
    if isinstance(payload, list):
        return payload, []
    if not isinstance(payload, dict):
        return [], []
    rows = payload.get("data") or payload.get("items") or payload.get("tables") or []
    fields = payload.get("fields") or payload.get("columns") or []
    if isinstance(rows, list) and rows and isinstance(rows[0], dict) and "data" in rows[0]:
        table = rows[0]
        return table.get("data") or [], table.get("fields") or []
    return rows if isinstance(rows, list) else [], fields if isinstance(fields, list) else []


def history_records(payload: Any, component: str, source: str) -> list[dict[str, Any]]:
    raw_rows, fields = rows_and_fields(payload)
    output: list[dict[str, Any]] = []
    for raw in raw_rows:
        if isinstance(raw, (list, tuple)):
            row = {str(fields[index]): value for index, value in enumerate(raw) if index < len(fields)} if fields else {}
            if not row and len(raw) >= 3:
                row = {"Date": raw[0], "TradeValue": raw[2]}
        elif isinstance(raw, dict):
            row = raw
        else:
            continue
        day = parse_market_date(first(row, (
            "Date", "日期", "資料日期", "TradeDate", "TradingDate", "成交日期",
        )))
        value = number(first(row, (
            "TradeValue", "成交金額", "成交金額(元)", "Amount", "TradingValue",
            "成交值", "TotalAmount", "TransactionAmount",
        )))
        if not day or value is None or value <= 0:
            continue
        parsed_day = date.fromisoformat(day)
        if not HISTORY_START <= parsed_day <= NOW.date():
            continue
        output.append({"date": day, component: value, "sources": [source]})
    return output


def fetch_json(session: requests.Session, url: str, *, params: dict[str, Any] | None = None) -> Any:
    response = session.get(url, params=params, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.json()


def online_history(session: requests.Session) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    for url, component, label in (
        (TWSE_HISTORY_OPENAPI, "twse_trade_value", "TWSE OpenAPI FMTQIK"),
        (TPEX_HISTORY_OPENAPI, "tpex_trade_value", "TPEx OpenAPI daily trading index"),
    ):
        try:
            parsed = history_records(fetch_json(session, url), component, label)
            rows.extend(parsed)
            if not parsed:
                warnings.append(f"{label}: no recognized historical rows")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{label}: {exc}")

    # The monthly official endpoints are a second online path. They are queried
    # when OpenAPI does not yield enough sessions, and they also fill missing months.
    twse_count = sum("twse_trade_value" in row for row in rows)
    tpex_count = sum("tpex_trade_value" in row for row in rows)
    year, month = HISTORY_START.year, HISTORY_START.month
    while (year, month) <= (NOW.year, NOW.month):
        if twse_count < 40:
            try:
                payload = fetch_json(session, TWSE_HISTORY_MONTH, params={"response": "json", "date": f"{year:04d}{month:02d}01"})
                parsed = history_records(payload, "twse_trade_value", "TWSE official monthly FMTQIK")
                rows.extend(parsed)
                twse_count += len(parsed)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"TWSE monthly {year:04d}-{month:02d}: {exc}")
        if tpex_count < 40:
            try:
                payload = fetch_json(session, TPEX_HISTORY_MONTH, params={"date": f"{year:04d}/{month:02d}/01", "id": "", "response": "json"})
                parsed = history_records(payload, "tpex_trade_value", "TPEx official monthly daily-indices")
                rows.extend(parsed)
                tpex_count += len(parsed)
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"TPEx monthly {year:04d}-{month:02d}: {exc}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return rows, warnings


def merge_history(old_rows: list[dict], online_rows: list[dict], current_total: float | None) -> list[dict]:
    by_date: dict[str, dict[str, Any]] = {}
    for raw in [*old_rows, *online_rows]:
        day = parse_market_date(raw.get("date"))
        if not day:
            continue
        parsed_day = date.fromisoformat(day)
        if not HISTORY_START <= parsed_day <= NOW.date():
            continue
        row = by_date.setdefault(day, {"date": day, "sources": []})
        for key in ("twse_trade_value", "tpex_trade_value"):
            value = number(raw.get(key))
            if value is not None and value > 0:
                row[key] = value
        # Old v11.4.25 files only had the total. Keep it as a fallback, but an
        # online component sum wins whenever available.
        old_total = number(raw.get("trade_value"))
        if old_total is not None and old_total > 0:
            row["legacy_trade_value"] = old_total
        for source in raw.get("sources") or ([raw.get("source")] if raw.get("source") else []):
            if source and source not in row["sources"]:
                row["sources"].append(source)
    today = NOW.date().isoformat()
    if current_total is not None and current_total > 0:
        row = by_date.setdefault(today, {"date": today, "sources": []})
        row["live_quote_sum"] = current_total
        if "TWSE/TPEx official close quote sum" not in row["sources"]:
            row["sources"].append("TWSE/TPEx official close quote sum")
    output = []
    for day, row in by_date.items():
        components = [number(row.get("twse_trade_value")), number(row.get("tpex_trade_value"))]
        components = [value for value in components if value is not None and value > 0]
        total = sum(components) if components else number(row.get("live_quote_sum")) or number(row.get("legacy_trade_value"))
        if total is None or total <= 0:
            continue
        output.append({
            "date": day,
            "trade_value": total,
            "twse_trade_value": number(row.get("twse_trade_value")),
            "tpex_trade_value": number(row.get("tpex_trade_value")),
            "source": " + ".join(row.get("sources") or ["official online history"]),
            "sources": row.get("sources") or [],
            "updated_at": NOW.isoformat(timespec="seconds"),
        })
    return sorted(output, key=lambda item: item["date"], reverse=True)


def average(values: list[float], sessions: int) -> float | None:
    selected = values[:sessions]
    return sum(selected) / len(selected) if selected else None


def main() -> None:
    old = read_json(DATA / "tw-market.json", {"items": []})
    old_rows = old.get("items") or []
    session = requests.Session()
    etf_codes, warnings = official_etf_codes(session, old_rows)
    rows: list[dict] = []
    for url, exchange in ((TWSE_QUOTES, "TWSE"), (TPEX_QUOTES, "TPEx")):
        try:
            rows.extend(fetch_quotes(session, url, exchange, etf_codes))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{exchange} quotes: {exc}")

    if len(rows) < 100:
        rows = [{**row, "asset_class": asset_class(str(row.get("symbol") or ""), etf_codes)} for row in old_rows]

    ranked_rows = [row for row in rows if row.get("asset_class") in {"stock", "etf"}]
    up = sum((number(row.get("change_percent")) or 0) > 0 for row in ranked_rows)
    down = sum((number(row.get("change_percent")) or 0) < 0 for row in ranked_rows)
    current_quote_total = sum(number(row.get("trade_value")) or 0 for row in ranked_rows) or None

    history_path = DATA / "market-volume-history.json"
    history = read_json(history_path, {"metadata": {}, "items": []})
    fetched_history, history_warnings = online_history(session)
    warnings.extend(history_warnings)
    history_rows = merge_history(history.get("items") or [], fetched_history, current_quote_total)
    previous_values = [number(item.get("trade_value")) for item in history_rows if item.get("date") != NOW.date().isoformat()]
    previous_values = [value for value in previous_values if value is not None and value > 0]
    latest_row = next((item for item in history_rows if item.get("date") == NOW.date().isoformat()), None)
    total_trade_value = number(latest_row.get("trade_value")) if latest_row else current_quote_total
    average_5d = average(previous_values, 5)
    average_20d = average(previous_values, 20)
    average_60d = average(previous_values, 60)
    volume_ratio_20d = total_trade_value / average_20d if total_trade_value not in (None, 0) and average_20d not in (None, 0) else None

    volume_payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "history_start": HISTORY_START.isoformat(),
            "history_end": NOW.date().isoformat(),
            "retention_policy": "2026-01-01 through today",
            "source_policy": "direct official network backfill every run; local JSON is fallback only",
            "session_count": len(history_rows),
            "warnings": history_warnings,
        },
        "items": history_rows,
    }
    history_path.write_text(json.dumps(volume_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (DATA / "market-volume-history-seed.js").write_text(
        "window.__MARKET_VOLUME_HISTORY_SEED__=" + json.dumps(volume_payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8",
    )

    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "trading_date": NOW.date().isoformat(),
            "market_status": "official-close",
            "source": "TWSE/TPEx official online open data",
            "warnings": warnings,
            "etf_count": sum(row.get("asset_class") == "etf" for row in rows),
            "excluded_product_count": sum(row.get("asset_class") == "other" for row in rows),
            "etf_classifier": "official-fund-whitelist-with-conservative-last-known-good-fallback",
            "total_trade_value": total_trade_value,
            "average_5d_trade_value": average_5d,
            "average_20d_trade_value": average_20d,
            "average_60d_trade_value": average_60d,
            "volume_ratio_20d": volume_ratio_20d,
            "volume_history_sessions": len(previous_values),
            "volume_history_start": HISTORY_START.isoformat(),
            "volume_history_source": "direct-online-official",
            "volume_history_complete": len(previous_values) >= 20,
        },
        "breadth": {"up": up, "down": down, "flat": len(ranked_rows) - up - down},
        "items": rows,
    }
    write_payload("tw-market.json", "__TW_MARKET_SEED__", payload)


if __name__ == "__main__":
    main()
