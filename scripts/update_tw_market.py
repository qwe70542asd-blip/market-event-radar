#!/usr/bin/env python3
"""Build a compact Taiwan cash-market quote feed for the ranking page.

Primary intraday source:
  TWSE Market Information System (MIS) getStockInfo endpoint.

Official daily OpenAPI rows are also read on every run.  They expand the symbol
universe and provide a last-trading-day fallback when MIS is between sessions.
The updater never publishes an empty file: an unsuccessful run raises and leaves
the previous live-data branch untouched.
"""
from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo

try:
    import requests
except ModuleNotFoundError:  # Allows parser tests in restricted local runtimes.
    requests = None


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = DATA / "tw-market.json"
SEED = DATA / "tw-market-seed.js"
TAIPEI = ZoneInfo("Asia/Taipei")

TWSE_DAILY = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_DAILY = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
MIS_HOME = "https://mis.twse.com.tw/stock/fibest.jsp?stock=2330"
MIS_QUOTE = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/10.9; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6",
    "Referer": "https://mis.twse.com.tw/stock/fibest.jsp?stock=2330",
}


def number(value):
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text or text in {"-", "--", "---", "N/A", "null"}:
        return None
    try:
        result = float(text)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def integer(value):
    parsed = number(value)
    return int(parsed) if parsed is not None else None


def first(row: dict, *keys):
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    compact = {str(key).replace(" ", "").lower(): value for key, value in row.items()}
    for key in keys:
        normalized = str(key).replace(" ", "").lower()
        if normalized in compact and compact[normalized] not in (None, ""):
            return compact[normalized]
    return None


def security_code(value: object) -> str:
    code = str(value or "").strip().upper()
    # Ordinary shares are four digits and ETFs begin with 00.  This deliberately
    # excludes warrants, rights and most structured products from the ranking.
    if re.fullmatch(r"[1-9]\d{3}", code) or re.fullmatch(r"00\d{2,4}[A-Z]?", code):
        return code
    return ""


def asset_class(code: str, known: str | None = None) -> str:
    if known in {"stock", "etf"}:
        return known
    return "etf" if code.startswith("00") else "stock"


def load_known_assets() -> dict[tuple[str, str], dict]:
    try:
        payload = json.loads((DATA / "assets.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {"assets": []}
    known = {}
    for item in payload.get("assets", []):
        if item.get("market") != "TW" or item.get("asset_class") not in {"stock", "etf"}:
            continue
        code = security_code(item.get("symbol"))
        exchange = "TPEx" if "TPEX" in str(item.get("exchange", "")).upper() else "TWSE"
        if code:
            known[(exchange, code)] = {
                "symbol": code,
                "name": str(item.get("name") or code).strip(),
                "exchange": exchange,
                "asset_class": asset_class(code, item.get("asset_class")),
            }
    return known


def parse_daily_row(row: dict, exchange: str) -> dict | None:
    code = security_code(first(
        row,
        "Code", "SecuritiesCompanyCode", "SecuritiesCode", "證券代號", "股票代號", "代號",
    ))
    if not code:
        return None
    name = str(first(row, "Name", "CompanyName", "SecuritiesName", "證券名稱", "股票名稱", "名稱") or code).strip()
    close = number(first(row, "ClosingPrice", "Close", "收盤價", "收盤"))
    change = number(first(row, "Change", "ChangeAmount", "漲跌", "漲跌價差"))
    previous = close - change if close is not None and change is not None else None
    percent = change / previous * 100 if change is not None and previous not in (None, 0) else None
    volume_shares = integer(first(row, "TradeVolume", "TradingShares", "成交股數", "成交量"))
    return {
        "symbol": code,
        "name": name,
        "exchange": exchange,
        "asset_class": asset_class(code),
        "price": close,
        "previous_close": previous,
        "change": change,
        "change_percent": percent,
        "open": number(first(row, "OpeningPrice", "Open", "開盤價", "開盤")),
        "high": number(first(row, "HighestPrice", "High", "最高價", "最高")),
        "low": number(first(row, "LowestPrice", "Low", "最低價", "最低")),
        "volume": round(volume_shares / 1000) if volume_shares is not None else None,
        "trade_value": integer(first(row, "TradeValue", "TransactionAmount", "成交金額")),
        "quote_date": "",
        "quote_time": "13:30:00",
        "status": "daily-fallback",
    }


def fetch_daily(session: requests.Session) -> dict[tuple[str, str], dict]:
    rows: dict[tuple[str, str], dict] = {}
    for exchange, url in (("TWSE", TWSE_DAILY), ("TPEx", TPEX_DAILY)):
        try:
            response = session.get(url, headers=HEADERS, timeout=35)
            response.raise_for_status()
            payload = response.json()
            raw_rows = payload if isinstance(payload, list) else payload.get("data", [])
            for raw in raw_rows:
                parsed = parse_daily_row(raw, exchange)
                if parsed:
                    rows[(exchange, parsed["symbol"])] = parsed
        except Exception as exc:  # One market may still be available.
            print(f"warning daily {exchange}: {exc}")
    return rows


def chunks(values: list[dict], size: int) -> Iterable[list[dict]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]


def live_price(row: dict):
    direct = number(row.get("z"))
    if direct is not None:
        return direct
    for field in ("b", "a"):
        first_level = str(row.get(field) or "").split("_", 1)[0]
        parsed = number(first_level)
        if parsed is not None:
            return parsed
    return number(row.get("y"))


def parse_mis_row(row: dict, fallback: dict | None = None) -> dict | None:
    code = security_code(row.get("c"))
    if not code:
        return None
    exchange = "TPEx" if str(row.get("ex") or "").lower() == "otc" else "TWSE"
    previous = number(row.get("y"))
    price = live_price(row)
    change = price - previous if price is not None and previous is not None else None
    percent = change / previous * 100 if change is not None and previous not in (None, 0) else None
    base = fallback or {}
    quote_date = str(row.get("d") or "").strip()
    quote_time = str(row.get("t") or row.get("ot") or "").strip()
    return {
        "symbol": code,
        "name": str(row.get("n") or base.get("name") or code).strip(),
        "exchange": exchange,
        "asset_class": asset_class(code, base.get("asset_class")),
        "price": price if price is not None else base.get("price"),
        "previous_close": previous if previous is not None else base.get("previous_close"),
        "change": change if change is not None else base.get("change"),
        "change_percent": percent if percent is not None else base.get("change_percent"),
        "open": number(row.get("o")) if number(row.get("o")) is not None else base.get("open"),
        "high": number(row.get("h")) if number(row.get("h")) is not None else base.get("high"),
        "low": number(row.get("l")) if number(row.get("l")) is not None else base.get("low"),
        "volume": integer(row.get("v")) if integer(row.get("v")) is not None else base.get("volume"),
        "trade_value": base.get("trade_value"),
        "quote_date": quote_date,
        "quote_time": quote_time,
        "market_at": integer(row.get("tlong")),
        "status": "mis",
    }


def fetch_mis(session: requests.Session, universe: dict[tuple[str, str], dict]) -> dict[tuple[str, str], dict]:
    securities = sorted(universe.values(), key=lambda item: (item["exchange"], item["symbol"]))
    if not securities:
        return {}
    try:
        session.get(MIS_HOME, headers=HEADERS, timeout=20)
    except Exception as exc:
        print(f"warning MIS warmup: {exc}")

    results: dict[tuple[str, str], dict] = {}
    for batch in chunks(securities, 60):
        channels = "|".join(
            f"{'otc' if item['exchange'] == 'TPEx' else 'tse'}_{item['symbol']}.tw"
            for item in batch
        )
        try:
            response = session.get(
                MIS_QUOTE,
                params={"ex_ch": channels, "json": "1", "delay": "0", "_": str(int(time.time() * 1000))},
                headers=HEADERS,
                timeout=35,
            )
            response.raise_for_status()
            payload = response.json()
            if str(payload.get("rtcode", "0000")) != "0000":
                raise RuntimeError(payload.get("rtmessage") or "MIS response error")
            for raw in payload.get("msgArray", []):
                code = security_code(raw.get("c"))
                exchange = "TPEx" if str(raw.get("ex") or "").lower() == "otc" else "TWSE"
                parsed = parse_mis_row(raw, universe.get((exchange, code)))
                if parsed:
                    results[(exchange, code)] = parsed
        except Exception as exc:
            print(f"warning MIS batch {batch[0]['symbol']}..{batch[-1]['symbol']}: {exc}")
        time.sleep(0.15)
    return results


def market_status(now: datetime) -> str:
    minute = now.hour * 60 + now.minute
    if now.weekday() >= 5:
        return "closed"
    if 8 * 60 + 30 <= minute < 9 * 60:
        return "preopen"
    if 9 * 60 <= minute <= 13 * 60 + 35:
        return "trading"
    return "closed"


def iso_quote_date(value: str) -> str:
    text = str(value or "").strip()
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def clean_item(item: dict) -> dict:
    output = dict(item)
    output["quote_date"] = iso_quote_date(output.get("quote_date", ""))
    for key in ("price", "previous_close", "change", "change_percent", "open", "high", "low"):
        value = output.get(key)
        output[key] = round(float(value), 4) if isinstance(value, (int, float)) and math.isfinite(value) else None
    for key in ("volume", "trade_value", "market_at"):
        value = output.get(key)
        output[key] = int(value) if isinstance(value, (int, float)) and math.isfinite(value) else None
    return output


def main():
    if requests is None:
        raise SystemExit("requests is required; run pip install -r requirements.txt")
    now = datetime.now(TAIPEI)
    session = requests.Session()
    known = load_known_assets()
    daily = fetch_daily(session)

    universe = {**known}
    for key, item in daily.items():
        universe[key] = {**universe.get(key, {}), **{k: item[k] for k in ("symbol", "name", "exchange", "asset_class")}}

    live = fetch_mis(session, universe)
    merged = {**daily, **live}
    # Keep known securities even if both quote sources temporarily omit them.
    for key, item in universe.items():
        merged.setdefault(key, {
            **item,
            "price": None, "previous_close": None, "change": None, "change_percent": None,
            "open": None, "high": None, "low": None, "volume": None, "trade_value": None,
            "quote_date": "", "quote_time": "", "status": "pending",
        })

    items = [clean_item(item) for item in merged.values()]
    usable = [item for item in items if item.get("price") is not None and item.get("previous_close") is not None]
    if len(usable) < 25:
        raise SystemExit(f"Only {len(usable)} usable Taiwan quotes; previous live file was not replaced.")

    dates = [item["quote_date"] for item in items if item.get("quote_date")]
    trading_date = max(dates) if dates else ""
    status = market_status(now)
    advancing = sum(1 for item in usable if (item.get("change_percent") or 0) > 0)
    declining = sum(1 for item in usable if (item.get("change_percent") or 0) < 0)
    unchanged = len(usable) - advancing - declining
    payload = {
        "metadata": {
            "version": "v11.0.0",
            "updated_at": now.isoformat(timespec="seconds"),
            "trading_date": trading_date,
            "market_status": status,
            "quote_count": len(usable),
            "source": "臺灣證券交易所基本市況報導、TWSE／TPEx OpenAPI",
            "refresh_seconds": 300,
            "note": "盤中行情可能延遲；休市時保留最後交易日。排行不含權證與多數結構型商品。",
        },
        "breadth": {"up": advancing, "down": declining, "flat": unchanged},
        "items": sorted(items, key=lambda item: (item["exchange"], item["symbol"])),
    }
    DATA.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED.write_text("window.__TW_MARKET_SEED__ = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    print(f"Taiwan quotes: {len(usable)}/{len(items)}; trading date: {trading_date}; MIS: {len(live)}")


if __name__ == "__main__":
    main()
