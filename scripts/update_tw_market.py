#!/usr/bin/env python3
"""Refresh Taiwan stock and ETF quotes with official MIS and daily OpenAPI data."""
from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "tw-market.json"
SEED = DATA / "tw-market-seed.js"
NOW = datetime.now(ZoneInfo("Asia/Taipei"))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.1)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
    "Referer": "https://mis.twse.com.tw/stock/fibest.jsp?stock=2330",
}
TWSE_DAILY = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_DAILY = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes"
MIS_HOME = "https://mis.twse.com.tw/stock/fibest.jsp?stock=2330"
MIS_API = "https://mis.twse.com.tw/stock/api/getStockInfo.jsp"


def number(value):
    try:
        text = str(value).strip().replace(",", "").replace("%", "")
        if text in {"", "-", "--", "---", "null", "N/A"}:
            return None
        value = float(text)
        return value if math.isfinite(value) else None
    except Exception:
        return None


def first(row: dict, *keys):
    compact = {re.sub(r"\s+", "", str(k)).lower(): v for k, v in row.items()}
    for key in keys:
        value = compact.get(re.sub(r"\s+", "", key).lower())
        if value not in (None, ""):
            return value
    return None


def valid_code(value) -> str:
    code = str(value or "").strip().upper()
    return code if re.fullmatch(r"(?:[1-9]\d{3}|00\d{2,4}[A-Z]?)", code) else ""


def load_assets() -> dict[tuple[str, str], dict]:
    try:
        payload = json.loads((DATA / "assets.json").read_text(encoding="utf-8"))
    except Exception:
        payload = {"assets": []}
    out = {}
    for row in payload.get("assets", []):
        if row.get("market") != "TW" or row.get("asset_class") not in {"stock", "etf"}:
            continue
        code = valid_code(row.get("symbol"))
        exchange = "TPEx" if "TPEX" in str(row.get("exchange","")).upper() else "TWSE"
        if code:
            out[(exchange, code)] = {
                "symbol": code, "name": row.get("name") or code, "exchange": exchange,
                "asset_class": row.get("asset_class") or ("etf" if code.startswith("00") else "stock"),
            }
    return out


def daily_row(row: dict, exchange: str) -> dict | None:
    code = valid_code(first(row, "Code", "SecuritiesCompanyCode", "證券代號", "股票代號", "代號"))
    if not code:
        return None
    name = str(first(row, "Name", "CompanyName", "證券名稱", "股票名稱", "名稱") or code).strip()
    close = number(first(row, "ClosingPrice", "Close", "收盤價", "收盤"))
    change = number(first(row, "Change", "ChangeAmount", "漲跌", "漲跌價差"))
    previous = close - change if close is not None and change is not None else None
    volume = number(first(row, "TradeVolume", "TradingShares", "成交股數", "成交量"))
    return {
        "symbol": code, "name": name, "exchange": exchange,
        "asset_class": "etf" if code.startswith("00") else "stock",
        "price": close, "previous_close": previous, "change": change,
        "change_percent": change / previous * 100 if change is not None and previous not in (None,0) else None,
        "open": number(first(row, "OpeningPrice", "Open", "開盤價")),
        "high": number(first(row, "HighestPrice", "High", "最高價")),
        "low": number(first(row, "LowestPrice", "Low", "最低價")),
        "volume": round(volume / 1000) if volume is not None and exchange == "TWSE" else volume,
        "trade_value": number(first(row, "TradeValue", "成交金額")),
        "quote_date": "", "quote_time": "13:30:00", "status": "daily-fallback",
    }


def fetch_daily(session: requests.Session) -> dict[tuple[str,str],dict]:
    out = {}
    for exchange, url in (("TWSE", TWSE_DAILY), ("TPEx", TPEX_DAILY)):
        try:
            response = session.get(url, headers=HEADERS, timeout=35)
            response.raise_for_status()
            payload = response.json()
            rows = payload if isinstance(payload, list) else payload.get("data", [])
            for raw in rows:
                item = daily_row(raw, exchange)
                if item:
                    out[(exchange, item["symbol"])] = item
        except Exception as exc:
            print("warning daily", exchange, exc)
    return out


def mis_price(row: dict):
    for key in ("z", "b", "a", "y"):
        text = str(row.get(key) or "").split("_", 1)[0]
        value = number(text)
        if value is not None:
            return value
    return None


def fetch_mis(session: requests.Session, universe: dict[tuple[str,str],dict]) -> dict[tuple[str,str],dict]:
    securities = sorted(universe.values(), key=lambda row:(row["exchange"],row["symbol"]))
    if not securities:
        return {}
    try:
        session.get(MIS_HOME, headers=HEADERS, timeout=18)
    except Exception:
        pass
    out = {}
    for offset in range(0, len(securities), 60):
        batch = securities[offset:offset+60]
        channels = "|".join(f"{'otc' if row['exchange']=='TPEx' else 'tse'}_{row['symbol']}.tw" for row in batch)
        try:
            response = session.get(MIS_API, params={"ex_ch":channels,"json":"1","delay":"0","_":int(time.time()*1000)}, headers=HEADERS, timeout=35)
            response.raise_for_status()
            payload = response.json()
            for row in payload.get("msgArray", []):
                code = valid_code(row.get("c"))
                exchange = "TPEx" if str(row.get("ex")).lower() == "otc" else "TWSE"
                base = universe.get((exchange,code), {})
                previous = number(row.get("y"))
                price = mis_price(row)
                change = price - previous if price is not None and previous is not None else None
                out[(exchange,code)] = {
                    **base, "symbol":code, "exchange":exchange,
                    "name":str(row.get("n") or base.get("name") or code).strip(),
                    "price":price, "previous_close":previous, "change":change,
                    "change_percent":change/previous*100 if change is not None and previous not in (None,0) else None,
                    "open":number(row.get("o")), "high":number(row.get("h")), "low":number(row.get("l")),
                    "volume":number(row.get("v")), "trade_value":None,
                    "quote_date":str(row.get("d") or ""), "quote_time":str(row.get("t") or row.get("ot") or ""),
                    "market_at":number(row.get("tlong")), "status":"mis",
                }
        except Exception as exc:
            print("warning MIS", offset, exc)
        time.sleep(.12)
    return out


def market_status() -> str:
    minute = NOW.hour*60+NOW.minute
    if NOW.weekday() >= 5:
        return "closed"
    if 9*60 <= minute <= 13*60+35:
        return "trading"
    if 8*60+30 <= minute < 9*60:
        return "preopen"
    return "closed"


def main() -> None:
    session = requests.Session()
    known = load_assets()
    daily = fetch_daily(session)
    universe = {**known}
    for key, row in daily.items():
        universe[key] = {**universe.get(key,{}), **{k:row.get(k) for k in ("symbol","name","exchange","asset_class")}}
    live = fetch_mis(session, universe)
    merged = {**daily}
    for key, row in live.items():
        fallback = daily.get(key,{})
        merged[key] = {**fallback, **{k:v for k,v in row.items() if v is not None and v != ""}}
    for key, base in universe.items():
        merged.setdefault(key, {**base, "price":None,"previous_close":None,"change":None,"change_percent":None,
            "open":None,"high":None,"low":None,"volume":None,"trade_value":None,"quote_date":"","quote_time":"","status":"pending"})
    items = sorted(merged.values(), key=lambda row:(row.get("exchange",""),row.get("symbol","")))
    usable = [row for row in items if number(row.get("price")) is not None and number(row.get("previous_close")) is not None]
    if len(usable) < 25:
        raise SystemExit(f"Only {len(usable)} usable quotes; previous file was not replaced.")
    dates = [row.get("quote_date") for row in items if row.get("quote_date")]
    trading_date = max(dates) if dates else None
    up = sum(1 for row in usable if (number(row.get("change_percent")) or 0)>0)
    down = sum(1 for row in usable if (number(row.get("change_percent")) or 0)<0)
    payload = {
        "metadata":{"version":"v11.1.3","updated_at":NOW.isoformat(timespec="seconds"),
            "trading_date":trading_date,"market_status":market_status(),"quote_count":len(usable),
            "source":"TWSE MIS、TWSE／TPEx OpenAPI","note":"盤中行情可能延遲；休市時保留最後交易日。"},
        "breadth":{"up":up,"down":down,"flat":len(usable)-up-down},"items":items,
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEED.write_text("window.__TW_MARKET_SEED__ = "+json.dumps(payload,ensure_ascii=False)+";\n",encoding="utf-8")
    print("tw quotes",len(usable))


if __name__ == "__main__":
    main()
