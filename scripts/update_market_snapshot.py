#!/usr/bin/env python3
"""Build the compact multi-source market ticker for Market Event Radar v10.4.5.

Source order:
- Taiwan weighted index: TWSE official OpenAPI.
- TPEx index: TPEx official OpenAPI, then Yahoo chart fallback.
- Global equity indices / FX: Yahoo chart API, then Stooq daily fallback.
- U.S. 10Y / VIX fallback: FRED daily CSV.
- Crypto: CoinGecko public API.
- Previous successful JSON is retained when a source temporarily fails.

This is a delayed/last-close dashboard, not a licensed real-time exchange feed.
"""
from __future__ import annotations

import csv
import io
import json
import math
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = DATA / "market-snapshot.json"
SEED = DATA / "market-snapshot-seed.js"
TAIPEI = ZoneInfo("Asia/Taipei")
UTC = ZoneInfo("UTC")
NOW = datetime.now(TAIPEI)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/10.4.5; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "application/json,text/plain,*/*",
}

ITEM_ORDER = [
    "TAIEX", "TPEX", "SP500", "NASDAQ", "DJIA", "SOX",
    "NIKKEI", "KOSPI", "VIX", "US10Y", "USDJPY", "USDTWD",
    "WTI", "GOLD", "BTC", "ETH",
]

ITEM_META = {
    "TAIEX":  {"name":"台股加權", "kind":"index", "currency":"點", "region":"TW", "link":"https://www.twse.com.tw/zh/trading/historical/fmtqik.html"},
    "TPEX":   {"name":"櫃買指數", "kind":"index", "currency":"點", "region":"TW", "link":"https://www.tpex.org.tw/zh-tw/mainboard/trading/info/daily-indices.html"},
    "SP500":  {"name":"S&P 500", "kind":"index", "currency":"點", "region":"US", "link":"https://finance.yahoo.com/quote/%5EGSPC/"},
    "NASDAQ": {"name":"NASDAQ", "kind":"index", "currency":"點", "region":"US", "link":"https://finance.yahoo.com/quote/%5EIXIC/"},
    "DJIA":   {"name":"道瓊工業", "kind":"index", "currency":"點", "region":"US", "link":"https://finance.yahoo.com/quote/%5EDJI/"},
    "SOX":    {"name":"費城半導體", "kind":"index", "currency":"點", "region":"US", "link":"https://finance.yahoo.com/quote/%5ESOX/"},
    "NIKKEI": {"name":"日經 225", "kind":"index", "currency":"點", "region":"JP", "link":"https://finance.yahoo.com/quote/%5EN225/"},
    "KOSPI":  {"name":"韓國 KOSPI", "kind":"index", "currency":"點", "region":"KR", "link":"https://finance.yahoo.com/quote/%5EKS11/"},
    "VIX":    {"name":"VIX 恐慌指數", "kind":"index", "currency":"點", "region":"US", "link":"https://fred.stlouisfed.org/series/VIXCLS"},
    "US10Y":  {"name":"美國 10 年債", "kind":"yield", "currency":"%", "region":"US", "link":"https://fred.stlouisfed.org/series/DGS10"},
    "USDJPY": {"name":"美元／日圓", "kind":"fx", "currency":"JPY", "region":"GLOBAL", "link":"https://finance.yahoo.com/quote/JPY=X/"},
    "USDTWD": {"name":"美元／台幣", "kind":"fx", "currency":"TWD", "region":"TW", "link":"https://finance.yahoo.com/quote/TWD=X/"},
    "WTI":    {"name":"WTI 原油", "kind":"commodity", "currency":"USD", "region":"GLOBAL", "link":"https://finance.yahoo.com/quote/CL=F/"},
    "GOLD":   {"name":"黃金", "kind":"commodity", "currency":"USD", "region":"GLOBAL", "link":"https://finance.yahoo.com/quote/GC=F/"},
    "BTC":    {"name":"Bitcoin", "kind":"crypto", "currency":"USD", "region":"CRYPTO", "link":"https://www.coingecko.com/en/coins/bitcoin"},
    "ETH":    {"name":"Ethereum", "kind":"crypto", "currency":"USD", "region":"CRYPTO", "link":"https://www.coingecko.com/en/coins/ethereum"},
}

YAHOO = {
    "TPEX": "^TWOII",
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DJIA": "^DJI",
    "SOX": "^SOX",
    "NIKKEI": "^N225",
    "KOSPI": "^KS11",
    "VIX": "^VIX",
    "USDJPY": "JPY=X",
    "USDTWD": "TWD=X",
    "WTI": "CL=F",
    "GOLD": "GC=F",
}

STOOQ = {
    "SP500": "^SPX",
    "NASDAQ": "^NDQ",
    "DJIA": "^DJI",
    "SOX": "^SOX",
    "NIKKEI": "^NKX",
    "VIX": "^VIX",
    "WTI": "CL.F",
    "GOLD": "GC.F",
}

FRED = {
    "VIX": "VIXCLS",
    "US10Y": "DGS10",
}


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def clean_number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(str(value).replace(",", "").strip())
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=TAIPEI)
    return value.astimezone(TAIPEI).isoformat(timespec="seconds")


def roc_to_iso(value: str) -> str:
    text = str(value or "").replace("/", "").replace("-", "").strip()
    if len(text) == 7 and text.isdigit():
        return f"{int(text[:3]) + 1911:04d}-{text[3:5]}-{text[5:7]}"
    if len(text) == 8 and text.isdigit():
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return text


def request(session: requests.Session, url: str, *, timeout: int = 16, attempts: int = 3, **kwargs: Any) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = session.get(url, headers={**HEADERS, **kwargs.pop("headers", {})}, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.1 * (attempt + 1))
    assert last_error is not None
    raise last_error


def item(item_id: str, *, value: float, previous: float | None, as_of: str, source: str, source_url: str,
         delay: str, status: str = "ok", note: str = "") -> dict[str, Any]:
    meta = ITEM_META[item_id]
    change = value - previous if previous is not None else None
    change_percent = (change / previous * 100) if previous not in (None, 0) else None
    return {
        "id": item_id,
        **meta,
        "value": value,
        "previous": previous,
        "change": change,
        "change_percent": change_percent,
        "as_of": as_of,
        "source": source,
        "source_url": source_url,
        "delay": delay,
        "status": status,
        "note": note,
        "updated_at": iso(NOW),
    }


def fetch_twse(session: requests.Session) -> dict[str, Any]:
    url = "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK"
    rows = request(session, url).json()
    if not isinstance(rows, list) or not rows:
        raise ValueError("TWSE returned no index rows")
    rows = [row for row in rows if clean_number(row.get("TAIEX")) is not None]
    latest = rows[-1]
    value = clean_number(latest.get("TAIEX"))
    change = clean_number(latest.get("Change"))
    previous = value - change if value is not None and change is not None else (
        clean_number(rows[-2].get("TAIEX")) if len(rows) > 1 else None
    )
    assert value is not None
    return item(
        "TAIEX", value=value, previous=previous,
        as_of=roc_to_iso(latest.get("Date", "")),
        source="TWSE 官方 OpenAPI", source_url=url,
        delay="盤後", note="官方每日市場成交資訊",
    )


def flexible_value(row: dict[str, Any], candidates: list[str]) -> float | None:
    lower = {str(key).lower(): value for key, value in row.items()}
    for key in candidates:
        if key.lower() in lower:
            number = clean_number(lower[key.lower()])
            if number is not None:
                return number
    for key, value in row.items():
        label = str(key).lower()
        if any(candidate.lower() in label for candidate in candidates):
            number = clean_number(value)
            if number is not None:
                return number
    return None


def flexible_text(row: dict[str, Any], candidates: list[str]) -> str:
    lower = {str(key).lower(): value for key, value in row.items()}
    for key in candidates:
        if key.lower() in lower and str(lower[key.lower()]).strip():
            return str(lower[key.lower()]).strip()
    return ""


def fetch_tpex(session: requests.Session) -> dict[str, Any]:
    url = "https://www.tpex.org.tw/openapi/v1/tpex_index"
    rows = request(session, url, headers={"Referer":"https://www.tpex.org.tw/"}).json()
    if not isinstance(rows, list) or not rows:
        raise ValueError("TPEx returned no index rows")
    parsed = []
    for row in rows:
        value = flexible_value(row, ["Close", "ClosingIndex", "Index", "收盤指數", "櫃買指數"])
        if value is not None:
            parsed.append((row, value))
    if not parsed:
        raise ValueError("TPEx response fields were not recognized")
    latest, value = parsed[-1]
    previous_value = parsed[-2][1] if len(parsed) > 1 else None
    change = flexible_value(latest, ["Change", "漲跌", "漲跌點數"])
    previous = value - change if change is not None else previous_value
    date_text = flexible_text(latest, ["Date", "日期", "TradeDate"])
    return item(
        "TPEX", value=value, previous=previous,
        as_of=roc_to_iso(date_text),
        source="TPEx 官方 OpenAPI", source_url=url,
        delay="盤後", note="官方櫃買指數歷史資料",
    )


def fetch_yahoo(session: requests.Session, item_id: str, symbol: str) -> dict[str, Any]:
    encoded = quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range=5d&interval=1d&includePrePost=false"
    payload = request(session, url, headers={"Referer":"https://finance.yahoo.com/"}).json()
    result = (((payload or {}).get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise ValueError(f"Yahoo returned no result for {symbol}")
    meta = result.get("meta") or {}
    closes = [clean_number(value) for value in (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])]
    closes = [value for value in closes if value is not None]
    value = clean_number(meta.get("regularMarketPrice")) or (closes[-1] if closes else None)
    previous = clean_number(meta.get("chartPreviousClose")) or clean_number(meta.get("previousClose"))
    if previous is None and len(closes) >= 2:
        previous = closes[-2]
    if value is None:
        raise ValueError(f"Yahoo price missing for {symbol}")
    market_time = meta.get("regularMarketTime")
    as_of = iso(datetime.fromtimestamp(market_time, tz=UTC)) if market_time else iso(NOW)
    return item(
        item_id, value=value, previous=previous, as_of=as_of,
        source="Yahoo Finance chart", source_url=ITEM_META[item_id]["link"],
        delay="延遲／最近成交", note=f"符號 {symbol}",
    )


def fetch_stooq(session: requests.Session, item_id: str, symbol: str) -> dict[str, Any]:
    url = f"https://stooq.com/q/d/l/?s={quote(symbol.lower())}&i=d"
    text = request(session, url, headers={"Accept":"text/csv"}).text
    rows = list(csv.DictReader(io.StringIO(text)))
    rows = [row for row in rows if clean_number(row.get("Close")) is not None]
    if not rows:
        raise ValueError(f"Stooq returned no rows for {symbol}")
    latest = rows[-1]
    previous = clean_number(rows[-2].get("Close")) if len(rows) > 1 else None
    return item(
        item_id, value=clean_number(latest["Close"]), previous=previous,
        as_of=str(latest.get("Date") or ""),
        source="Stooq 日資料", source_url=f"https://stooq.com/q/?s={quote(symbol.lower())}",
        delay="日資料", status="fallback", note=f"Yahoo 暫時不可用；使用 {symbol}",
    )


def fetch_fred(session: requests.Session, item_id: str, series: str) -> dict[str, Any]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    rows = list(csv.DictReader(io.StringIO(request(session, url, headers={"Accept":"text/csv"}).text)))
    values = []
    for row in rows:
        value = clean_number(row.get(series))
        if value is not None:
            values.append((row.get("DATE") or row.get("observation_date") or "", value))
    if not values:
        raise ValueError(f"FRED returned no values for {series}")
    latest_date, value = values[-1]
    previous = values[-2][1] if len(values) > 1 else None
    return item(
        item_id, value=value, previous=previous, as_of=latest_date,
        source="FRED", source_url=ITEM_META[item_id]["link"],
        delay="官方日資料", note=f"FRED series {series}",
    )


def fetch_crypto(session: requests.Session) -> list[dict[str, Any]]:
    url = "https://api.coingecko.com/api/v3/simple/price"
    payload = request(
        session, url,
        params={
            "ids":"bitcoin,ethereum",
            "vs_currencies":"usd",
            "include_24hr_change":"true",
            "include_last_updated_at":"true",
        },
    ).json()
    results = []
    for item_id, coin_id in (("BTC","bitcoin"),("ETH","ethereum")):
        row = payload.get(coin_id) or {}
        value = clean_number(row.get("usd"))
        pct = clean_number(row.get("usd_24h_change"))
        if value is None:
            raise ValueError(f"CoinGecko {coin_id} price missing")
        previous = value / (1 + pct / 100) if pct is not None and pct > -100 else None
        updated = row.get("last_updated_at")
        as_of = iso(datetime.fromtimestamp(updated, tz=UTC)) if updated else iso(NOW)
        results.append(item(
            item_id, value=value, previous=previous, as_of=as_of,
            source="CoinGecko", source_url=ITEM_META[item_id]["link"],
            delay="近即時聚合", note="24 小時漲跌",
        ))
    return results


def previous_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {row.get("id"): row for row in payload.get("items", []) if row.get("id")}


def retained(item_id: str, previous: dict[str, dict[str, Any]], message: str) -> dict[str, Any]:
    old = previous.get(item_id)
    if old and clean_number(old.get("value")) is not None:
        row = dict(old)
        row["status"] = "stale"
        row["delay"] = "前次成功資料"
        row["note"] = message
        row["updated_at"] = iso(NOW)
        return row
    meta = ITEM_META[item_id]
    return {
        "id": item_id, **meta, "value": None, "previous": None,
        "change": None, "change_percent": None, "as_of": "",
        "source": "", "source_url": meta["link"], "delay": "等待更新",
        "status": "pending", "note": message, "updated_at": iso(NOW),
    }


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    previous_payload = read_json(OUTPUT, {"items":[]})
    old = previous_map(previous_payload)
    session = requests.Session()
    items: dict[str, dict[str, Any]] = {}
    statuses: list[dict[str, Any]] = []

    def run(item_id: str, label: str, function) -> None:
        try:
            row = function()
            items[item_id] = row
            statuses.append({"id":item_id,"source":label,"status":"ok","message":row.get("source","")})
        except Exception as exc:
            items[item_id] = retained(item_id, old, f"{label} 暫時失敗：{type(exc).__name__}")
            statuses.append({"id":item_id,"source":label,"status":"warning","message":str(exc)[:160]})

    run("TAIEX", "TWSE", lambda: fetch_twse(session))

    try:
        tpex = fetch_tpex(session)
        items["TPEX"] = tpex
        statuses.append({"id":"TPEX","source":"TPEx","status":"ok","message":tpex["source"]})
    except Exception as official_exc:
        try:
            tpex = fetch_yahoo(session, "TPEX", YAHOO["TPEX"])
            tpex["status"] = "fallback"
            tpex["note"] = "TPEx 官方 OpenAPI 暫時不可用，使用 Yahoo 延遲行情"
            items["TPEX"] = tpex
            statuses.append({"id":"TPEX","source":"TPEx→Yahoo","status":"warning","message":str(official_exc)[:120]})
        except Exception as yahoo_exc:
            items["TPEX"] = retained("TPEX", old, "TPEx 與 Yahoo 皆暫時不可用")
            statuses.append({"id":"TPEX","source":"TPEx→Yahoo","status":"warning","message":f"{official_exc}; {yahoo_exc}"[:160]})

    for item_id, symbol in YAHOO.items():
        if item_id == "TPEX":
            continue
        try:
            row = fetch_yahoo(session, item_id, symbol)
            items[item_id] = row
            statuses.append({"id":item_id,"source":"Yahoo","status":"ok","message":symbol})
        except Exception as yahoo_exc:
            fallback_symbol = STOOQ.get(item_id)
            if fallback_symbol:
                try:
                    row = fetch_stooq(session, item_id, fallback_symbol)
                    items[item_id] = row
                    statuses.append({"id":item_id,"source":"Yahoo→Stooq","status":"warning","message":str(yahoo_exc)[:120]})
                    continue
                except Exception as stooq_exc:
                    message = f"Yahoo/Stooq failed: {yahoo_exc}; {stooq_exc}"
            else:
                message = f"Yahoo failed: {yahoo_exc}"
            items[item_id] = retained(item_id, old, message[:150])
            statuses.append({"id":item_id,"source":"Yahoo","status":"warning","message":message[:160]})

    # FRED is the primary source for the treasury yield. It also replaces VIX
    # only when Yahoo/Stooq did not return usable data.
    run("US10Y", "FRED DGS10", lambda: fetch_fred(session, "US10Y", FRED["US10Y"]))
    if items.get("VIX", {}).get("status") in {"pending", "stale"}:
        run("VIX", "FRED VIXCLS", lambda: fetch_fred(session, "VIX", FRED["VIX"]))

    try:
        for row in fetch_crypto(session):
            items[row["id"]] = row
            statuses.append({"id":row["id"],"source":"CoinGecko","status":"ok","message":row["source"]})
    except Exception as exc:
        for item_id in ("BTC","ETH"):
            items[item_id] = retained(item_id, old, f"CoinGecko 暫時失敗：{type(exc).__name__}")
            statuses.append({"id":item_id,"source":"CoinGecko","status":"warning","message":str(exc)[:160]})

    ordered = [items[item_id] for item_id in ITEM_ORDER if item_id in items]
    healthy = sum(1 for row in ordered if row.get("status") in {"ok","fallback"})
    payload = {
        "metadata": {
            "updated_at": iso(NOW),
            "timezone": "Asia/Taipei",
            "version": "v10.4.5",
            "item_count": len(ordered),
            "healthy_count": healthy,
            "status": "ok" if healthy >= 10 else "partial",
            "display_policy": "delayed-or-last-close",
            "note": "Unavailable symbols are hidden. Previous successful data is retained when a source fails.",
        },
        "sources": statuses,
        "items": ordered,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED.write_text("window.__MARKET_SNAPSHOT_SEED__ = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"Wrote {len(ordered)} ticker items; healthy={healthy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
