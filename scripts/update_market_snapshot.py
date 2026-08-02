#!/usr/bin/env python3
"""Build grouped index and ETF market snapshots for Market Event Radar v10.6.0.

Visible groups:
- Taiwan indices: TAIEX and TPEx.
- U.S. four major indices: S&P 500, NASDAQ Composite, Dow Jones, Philadelphia Semiconductor.
- Japan/Korea: Nikkei 225 and KOSPI.
- Taiwan ETF top 15: ranked by TWSE ETF e添富 daily trading value when available.
- U.S. ETF watch group: fixed liquid benchmark/sector ETF set.

Quotes are delayed or end-of-day public data. This script does not claim licensed real-time exchange data.
"""
from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUTPUT = DATA / "market-snapshot.json"
SEED = DATA / "market-snapshot-seed.js"
TAIPEI = ZoneInfo("Asia/Taipei")
UTC = ZoneInfo("UTC")
NOW = datetime.now(TAIPEI)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/10.6.0; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "application/json,text/html,text/plain,*/*",
}

INDEX_ORDER = ["TAIEX","TPEX","SP500","NASDAQ","DJIA","SOX","NIKKEI","KOSPI"]
INDEX_META = {
    "TAIEX":{"name":"台股加權","kind":"index","currency":"點","region":"TW","link":"https://www.twse.com.tw/zh/trading/historical/fmtqik.html"},
    "TPEX":{"name":"櫃買指數","kind":"index","currency":"點","region":"TW","link":"https://www.tpex.org.tw/zh-tw/mainboard/trading/info/daily-indices.html"},
    "SP500":{"name":"S&P 500","kind":"index","currency":"點","region":"US","link":"https://finance.yahoo.com/quote/%5EGSPC/"},
    "NASDAQ":{"name":"NASDAQ","kind":"index","currency":"點","region":"US","link":"https://finance.yahoo.com/quote/%5EIXIC/"},
    "DJIA":{"name":"道瓊工業","kind":"index","currency":"點","region":"US","link":"https://finance.yahoo.com/quote/%5EDJI/"},
    "SOX":{"name":"費城半導體","kind":"index","currency":"點","region":"US","link":"https://finance.yahoo.com/quote/%5ESOX/"},
    "NIKKEI":{"name":"日經 225","kind":"index","currency":"點","region":"JP","link":"https://finance.yahoo.com/quote/%5EN225/"},
    "KOSPI":{"name":"韓國 KOSPI","kind":"index","currency":"點","region":"KR","link":"https://finance.yahoo.com/quote/%5EKS11/"},
}
YAHOO_INDEX = {
    "TPEX":"^TWOII","SP500":"^GSPC","NASDAQ":"^IXIC","DJIA":"^DJI",
    "SOX":"^SOX","NIKKEI":"^N225","KOSPI":"^KS11",
}

# Used only if the official TWSE ranking page cannot be parsed on a run.
TW_ETF_FALLBACK = [
    ("0050","元大台灣50"),("00631L","元大台灣50正2"),("00981A","主動統一台股增長"),
    ("0056","元大高股息"),("00685L","群益臺灣加權正2"),("00403A","主動統一升級50"),
    ("00632R","元大台灣50反1"),("00991A","主動復華未來50"),("009816","凱基台灣TOP50"),
    ("00406A","主動中信台灣收益"),("00919","群益台灣精選高息"),("00878","國泰永續高股息"),
    ("006208","富邦台50"),("0052","富邦科技"),("00929","復華台灣科技優息"),
]

US_ETFS = [
    ("SPY","SPDR S&P 500 ETF"),("QQQ","Invesco QQQ"),("DIA","SPDR Dow Jones ETF"),
    ("IWM","iShares Russell 2000 ETF"),("VOO","Vanguard S&P 500 ETF"),("VTI","Vanguard Total Stock Market ETF"),
    ("SMH","VanEck Semiconductor ETF"),("SOXX","iShares Semiconductor ETF"),("XLK","Technology Select Sector SPDR"),
    ("TLT","iShares 20+ Year Treasury Bond ETF"),
]


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def clean_number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).replace(",", "").replace("+", "").strip()
    if not text or text in {"--", "---", "-"}:
        return None
    try:
        number = float(text)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=TAIPEI)
    return value.astimezone(TAIPEI).isoformat(timespec="seconds")


def roc_to_iso(value: str) -> str:
    text = re.sub(r"\D", "", str(value or ""))
    if len(text) == 7:
        return f"{int(text[:3]) + 1911:04d}-{text[3:5]}-{text[5:7]}"
    if len(text) == 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return str(value or "")


def request(session: requests.Session, url: str, *, timeout: int = 18, attempts: int = 3, **kwargs: Any) -> requests.Response:
    last_error: Exception | None = None
    extra_headers = kwargs.pop("headers", {})
    for attempt in range(attempts):
        try:
            response = session.get(url, headers={**HEADERS, **extra_headers}, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.2 * (attempt + 1))
    assert last_error is not None
    raise last_error


def make_item(item_id: str, meta: dict[str, Any], *, value: float, previous: float | None, as_of: str,
              source: str, source_url: str, delay: str, status: str = "ok", note: str = "",
              symbol: str = "", rank: int | None = None) -> dict[str, Any]:
    change = value - previous if previous is not None else None
    change_percent = (change / previous * 100) if previous not in (None, 0) else None
    return {
        "id": item_id, **meta, "symbol": symbol or item_id, "rank": rank,
        "value": value, "previous": previous, "change": change, "change_percent": change_percent,
        "as_of": as_of, "source": source, "source_url": source_url, "delay": delay,
        "status": status, "note": note, "updated_at": iso(NOW),
    }


def fetch_twse_index(session: requests.Session) -> dict[str, Any]:
    url = "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK"
    rows = request(session, url).json()
    rows = [row for row in rows if clean_number(row.get("TAIEX")) is not None]
    if not rows:
        raise ValueError("TWSE returned no index rows")
    latest = rows[-1]
    value = clean_number(latest.get("TAIEX"))
    change = clean_number(latest.get("Change"))
    previous = value - change if value is not None and change is not None else None
    assert value is not None
    return make_item("TAIEX", INDEX_META["TAIEX"], value=value, previous=previous,
                     as_of=roc_to_iso(latest.get("Date", "")), source="TWSE 官方 OpenAPI",
                     source_url=url, delay="盤後")


def fetch_tpex_index(session: requests.Session) -> dict[str, Any]:
    url = "https://www.tpex.org.tw/openapi/v1/tpex_index"
    rows = request(session, url, headers={"Referer":"https://www.tpex.org.tw/"}).json()
    if not isinstance(rows, list) or not rows:
        raise ValueError("TPEx returned no rows")
    parsed: list[tuple[dict[str, Any], float]] = []
    for row in rows:
        for key in ("Close","ClosingIndex","Index","收盤指數","櫃買指數"):
            if key in row and clean_number(row.get(key)) is not None:
                parsed.append((row, clean_number(row.get(key))))
                break
    if not parsed:
        raise ValueError("TPEx fields not recognized")
    latest, value = parsed[-1]
    previous = parsed[-2][1] if len(parsed) > 1 else None
    change = next((clean_number(latest.get(key)) for key in ("Change","漲跌","漲跌點數") if clean_number(latest.get(key)) is not None), None)
    if change is not None:
        previous = value - change
    date_text = next((str(latest.get(key)) for key in ("Date","日期","TradeDate") if latest.get(key)), "")
    return make_item("TPEX", INDEX_META["TPEX"], value=value, previous=previous,
                     as_of=roc_to_iso(date_text), source="TPEx 官方 OpenAPI", source_url=url, delay="盤後")


def fetch_yahoo(session: requests.Session, item_id: str, symbol: str, meta: dict[str, Any], *, rank: int | None = None) -> dict[str, Any]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol, safe='')}?range=5d&interval=1d&includePrePost=false"
    payload = request(session, url, headers={"Referer":"https://finance.yahoo.com/"}).json()
    result = (((payload or {}).get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise ValueError(f"Yahoo returned no result for {symbol}")
    info = result.get("meta") or {}
    closes = [clean_number(x) for x in (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])]
    closes = [x for x in closes if x is not None]
    value = clean_number(info.get("regularMarketPrice")) or (closes[-1] if closes else None)
    previous = clean_number(info.get("chartPreviousClose")) or clean_number(info.get("previousClose"))
    if previous is None and len(closes) >= 2:
        previous = closes[-2]
    if value is None:
        raise ValueError(f"Yahoo price missing for {symbol}")
    market_time = info.get("regularMarketTime")
    as_of = iso(datetime.fromtimestamp(market_time, tz=UTC)) if market_time else iso(NOW)
    return make_item(item_id, meta, value=value, previous=previous, as_of=as_of,
                     source="Yahoo Finance chart", source_url=meta.get("link", "https://finance.yahoo.com/"),
                     delay="延遲／最近成交", symbol=item_id, rank=rank)


def fetch_twse_daily_quote_map(session: requests.Session) -> dict[str, dict[str, Any]]:
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    rows = request(session, url).json()
    result = {}
    for row in rows if isinstance(rows, list) else []:
        code = str(row.get("Code") or row.get("證券代號") or "").strip()
        if code:
            result[code] = row
    return result


def parse_tw_etf_ranking(session: requests.Session) -> tuple[list[tuple[str,str]], str]:
    urls = [
        "https://www.twse.com.tw/rwd/zh/ETFortune-institute/index",
        "https://www.twse.com.tw/zh/ETFortune-institute/index",
    ]
    last_error: Exception | None = None
    for url in urls:
        try:
            text = request(session, url, headers={"Accept":"text/html"}).text
            soup = BeautifulSoup(text, "html.parser")
            date_match = re.search(r"資料更新時間[:：]?\s*(\d{4}[./-]\d{1,2}[./-]\d{1,2})", soup.get_text(" ", strip=True))
            rank_date = date_match.group(1).replace(".", "-").replace("/", "-") if date_match else ""
            for table in soup.find_all("table"):
                headers = [cell.get_text(" ", strip=True) for cell in table.find_all("th")]
                joined = " ".join(headers)
                if "股票代號" not in joined or not ("今日成交值" in joined or "成交金額" in joined):
                    continue
                ranked = []
                for row in table.find_all("tr"):
                    cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td","th"])]
                    if len(cells) < 3:
                        continue
                    code = next((c for c in cells if re.fullmatch(r"\d{4,6}[A-Z]?", c)), "")
                    if not code:
                        continue
                    idx = cells.index(code)
                    name = cells[idx + 1] if idx + 1 < len(cells) else code
                    if code not in {x[0] for x in ranked}:
                        ranked.append((code, name))
                    if len(ranked) >= 15:
                        return ranked, rank_date
            raise ValueError("TWSE ETF ranking table not found")
        except Exception as exc:
            last_error = exc
    raise last_error or ValueError("TWSE ETF ranking unavailable")


def tw_etf_item_from_official(code: str, name: str, rank: int, row: dict[str, Any]) -> dict[str, Any] | None:
    close = clean_number(row.get("ClosingPrice") or row.get("收盤價"))
    change = clean_number(row.get("Change") or row.get("漲跌價差"))
    if close is None:
        return None
    previous = close - change if change is not None else None
    meta = {
        "name": name or str(row.get("Name") or row.get("證券名稱") or code),
        "kind":"etf","currency":"TWD","region":"TW","market":"TW","exchange":"TWSE",
        "link":f"https://www.twse.com.tw/zh/ETFortune/products?query={code}",
    }
    return make_item(f"TWETF:{code}", meta, value=close, previous=previous, as_of=iso(NOW),
                     source="TWSE 官方當日成交資訊", source_url="https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
                     delay="盤後", symbol=code, rank=rank)


def retain(old: dict[str, dict[str, Any]], item_id: str, meta: dict[str, Any], *, symbol: str = "", rank: int | None = None, note: str = "") -> dict[str, Any]:
    previous = old.get(item_id)
    if previous and clean_number(previous.get("value")) is not None:
        row = dict(previous)
        row.update({"status":"stale","delay":"前次成功資料","note":note,"updated_at":iso(NOW)})
        if rank is not None:
            row["rank"] = rank
        return row
    return {"id":item_id, **meta, "symbol":symbol or item_id, "rank":rank, "value":None, "previous":None,
            "change":None, "change_percent":None, "as_of":"", "source":"", "source_url":meta.get("link",""),
            "delay":"等待更新", "status":"pending", "note":note, "updated_at":iso(NOW)}


def old_items(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = list(payload.get("items", [])) + list(payload.get("taiwan_etfs", [])) + list(payload.get("us_etfs", []))
    return {row.get("id"):row for row in rows if row.get("id")}


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    previous_payload = read_json(OUTPUT, {})
    old = old_items(previous_payload)
    session = requests.Session()
    items: dict[str, dict[str, Any]] = {}
    statuses: list[dict[str, Any]] = []

    def run_index(item_id: str, label: str, fn) -> None:
        try:
            row = fn()
            items[item_id] = row
            statuses.append({"id":item_id,"source":label,"status":"ok","message":row.get("source","")})
        except Exception as exc:
            items[item_id] = retain(old, item_id, INDEX_META[item_id], note=f"{label} 暫時失敗：{type(exc).__name__}")
            statuses.append({"id":item_id,"source":label,"status":"warning","message":str(exc)[:180]})

    run_index("TAIEX","TWSE",lambda:fetch_twse_index(session))
    try:
        row = fetch_tpex_index(session)
        items["TPEX"] = row
        statuses.append({"id":"TPEX","source":"TPEx","status":"ok","message":row["source"]})
    except Exception as official_exc:
        try:
            row = fetch_yahoo(session,"TPEX",YAHOO_INDEX["TPEX"],INDEX_META["TPEX"])
            row["status"] = "fallback"
            row["note"] = "TPEx 官方資料暫時不可用，改用延遲行情"
            items["TPEX"] = row
            statuses.append({"id":"TPEX","source":"TPEx→Yahoo","status":"warning","message":str(official_exc)[:150]})
        except Exception as exc:
            items["TPEX"] = retain(old,"TPEX",INDEX_META["TPEX"],note="TPEx 與 Yahoo 皆暫時不可用")
            statuses.append({"id":"TPEX","source":"TPEx→Yahoo","status":"warning","message":str(exc)[:180]})

    for item_id in ("SP500","NASDAQ","DJIA","SOX","NIKKEI","KOSPI"):
        run_index(item_id,"Yahoo",lambda item_id=item_id: fetch_yahoo(session,item_id,YAHOO_INDEX[item_id],INDEX_META[item_id]))

    # Taiwan ETF ranking + official EOD quote map.
    try:
        ranking, ranking_date = parse_tw_etf_ranking(session)
        ranking_source = "TWSE ETF e添富成交值排行"
    except Exception as exc:
        ranking, ranking_date = TW_ETF_FALLBACK, ""
        ranking_source = "固定備援清單"
        statuses.append({"id":"TW_ETF_RANK","source":"TWSE ETF e添富","status":"warning","message":str(exc)[:180]})

    try:
        official_quotes = fetch_twse_daily_quote_map(session)
    except Exception as exc:
        official_quotes = {}
        statuses.append({"id":"TW_ETF_QUOTES","source":"TWSE STOCK_DAY_ALL","status":"warning","message":str(exc)[:180]})

    taiwan_etfs = []
    for rank, (code, name) in enumerate(ranking[:15], start=1):
        item_id = f"TWETF:{code}"
        row = tw_etf_item_from_official(code,name,rank,official_quotes.get(code,{}) ) if code in official_quotes else None
        if row is None:
            meta = {"name":name,"kind":"etf","currency":"TWD","region":"TW","market":"TW","exchange":"TWSE","link":f"https://tw.stock.yahoo.com/quote/{code}.TW"}
            try:
                row = fetch_yahoo(session,item_id,f"{code}.TW",meta,rank=rank)
                row["symbol"] = code
            except Exception as exc:
                row = retain(old,item_id,meta,symbol=code,rank=rank,note=f"ETF 行情暫時失敗：{type(exc).__name__}")
        row["ranking_source"] = ranking_source
        row["ranking_date"] = ranking_date
        taiwan_etfs.append(row)

    us_etfs = []
    for rank, (symbol, name) in enumerate(US_ETFS, start=1):
        item_id = f"USETF:{symbol}"
        meta = {"name":name,"kind":"etf","currency":"USD","region":"US","market":"US","exchange":"NYSE/NASDAQ","link":f"https://finance.yahoo.com/quote/{symbol}/"}
        try:
            row = fetch_yahoo(session,item_id,symbol,meta,rank=rank)
            row["symbol"] = symbol
        except Exception as exc:
            row = retain(old,item_id,meta,symbol=symbol,rank=rank,note=f"ETF 行情暫時失敗：{type(exc).__name__}")
        us_etfs.append(row)

    ordered = [items[item_id] for item_id in INDEX_ORDER]
    all_rows = ordered + taiwan_etfs + us_etfs
    healthy = sum(1 for row in all_rows if row.get("status") in {"ok","fallback"} and row.get("value") is not None)
    payload = {
        "metadata": {
            "updated_at":iso(NOW), "timezone":"Asia/Taipei", "version":"v10.6.0",
            "item_count":len(all_rows), "healthy_count":healthy,
            "status":"ok" if healthy >= 20 else "partial",
            "display_policy":"delayed-or-last-close",
            "tw_etf_ranking":"daily-trading-value",
            "note":"Grouped indices and vertical ETF rails. Previous successful values are retained on source failure.",
        },
        "sources":statuses,
        "items":ordered,
        "taiwan_etfs":taiwan_etfs,
        "us_etfs":us_etfs,
    }
    OUTPUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEED.write_text("window.__MARKET_SNAPSHOT_SEED__ = "+json.dumps(payload,ensure_ascii=False,indent=2)+";\n",encoding="utf-8")
    print(f"indices={len(ordered)} tw_etfs={len(taiwan_etfs)} us_etfs={len(us_etfs)} healthy={healthy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
