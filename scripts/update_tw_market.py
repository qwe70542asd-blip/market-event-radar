#!/usr/bin/env python3
"""Refresh Taiwan closing quotes and classify products conservatively.

ETF classification is based on official fund lists.  Warrants, ETNs and other
six-digit derivatives are marked as ``other`` and never enter stock/ETF ranks.
"""
from __future__ import annotations

import re
from typing import Any

import requests

from common import DATA, NOW, read_json, write_payload

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.3)"}
TWSE_QUOTES = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_QUOTES = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
TWSE_FUNDS = "https://openapi.twse.com.tw/v1/opendata/t187ap47_L"
TPEX_FUNDS = "https://www.tpex.org.tw/openapi/v1/tpex_opfund_latest"


def number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").strip()
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
        except Exception as exc:
            warnings.append(f"{label} ETF list: {exc}")

    # Conservative last-known-good fallback: only prior rows already classified as
    # ETF and 00-prefixed fund codes.  This never promotes 7xxxxx warrants.
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


def main() -> None:
    old = read_json(DATA / "tw-market.json", {"items": []})
    old_rows = old.get("items") or []
    session = requests.Session()
    etf_codes, warnings = official_etf_codes(session, old_rows)
    rows: list[dict] = []
    for url, exchange in ((TWSE_QUOTES, "TWSE"), (TPEX_QUOTES, "TPEx")):
        try:
            rows.extend(fetch_quotes(session, url, exchange, etf_codes))
        except Exception as exc:
            warnings.append(f"{exchange} quotes: {exc}")

    if len(rows) < 100:
        # Preserve the old payload, but reclassify every row with the corrected rules.
        rows = [{**row, "asset_class": asset_class(str(row.get("symbol") or ""), etf_codes)} for row in old_rows]

    ranked_rows = [row for row in rows if row.get("asset_class") in {"stock", "etf"}]
    up = sum((number(row.get("change_percent")) or 0) > 0 for row in ranked_rows)
    down = sum((number(row.get("change_percent")) or 0) < 0 for row in ranked_rows)
    payload = {
        "metadata": {
            "version": "v11.4.2",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "trading_date": NOW.date().isoformat(),
            "market_status": "official-close",
            "source": "TWSE／TPEx official open data",
            "warnings": warnings,
            "etf_count": sum(row.get("asset_class") == "etf" for row in rows),
            "excluded_product_count": sum(row.get("asset_class") == "other" for row in rows),
            "etf_classifier": "official-fund-whitelist-with-conservative-last-known-good-fallback",
        },
        "breadth": {"up": up, "down": down, "flat": len(ranked_rows) - up - down},
        "items": rows,
    }
    write_payload("tw-market.json", "__TW_MARKET_SEED__", payload)


if __name__ == "__main__":
    main()
