#!/usr/bin/env python3
"""Build a rich market calendar for Market Event Radar v10.4.

Coverage:
- Official macro schedules: BLS, BEA and curated central-bank events.
- U.S. earnings, dividends, payment dates and stock splits from Nasdaq calendar APIs.
- Taiwan listed/OTC ex-right and ex-dividend schedules, including ETFs and active ETFs.
- Taiwan dividend decisions, shareholder meetings and daily material information.
- MOPS investor conferences and financial-report presentations.
- Rule-based Taiwan monthly-revenue / quarterly-report deadlines.

The output intentionally keeps low-impact company events. The UI decides what to
show first and lets users filter the full day, instead of deleting events at
collection time.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time as time_module
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

try:
    from icalendar import Calendar
except ImportError:
    Calendar = None

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EVENTS_PATH = DATA_DIR / "events.json"
MANUAL_PATH = DATA_DIR / "manual_events.json"
BOOTSTRAP_PATH = DATA_DIR / "bootstrap_corporate_events.json"
ASSETS_PATH = DATA_DIR / "assets.json"
SEED_PATH = DATA_DIR / "seed.js"

TAIPEI = ZoneInfo("Asia/Taipei")
NEW_YORK = ZoneInfo("America/New_York")
NOW = datetime.now(TAIPEI)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/10.4; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}
NASDAQ_HEADERS = {
    **HEADERS,
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.nasdaq.com",
    "Referer": "https://www.nasdaq.com/",
}

TWSE_EXDIV_URL = "https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL"
TPEX_EXDIV_URL = "https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost"
TWSE_DIVIDEND_PLAN_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap45_L"
TPEX_DIVIDEND_PLAN_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap45_O"
TWSE_MATERIAL_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
TPEX_MATERIAL_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"
TWSE_REVENUE_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap05_L"
TPEX_REVENUE_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"
MOPS_REDIRECT_URL = "https://mops.twse.com.tw/mops/api/redirectToOld"
MOPS_CONFERENCE_PAGE = "https://mops.twse.com.tw/mops/#/web/t100sb02_1"

WATCHLIST = {
    "NVDA","AMD","AAPL","MSFT","GOOGL","GOOG","AMZN","META","AVGO","QCOM","MU","INTC","ORCL","CRM","ADBE",
    "JPM","BAC","WFC","C","GS","MS","BLK","AXP","V","MA","SCHW","PNC",
    "CAT","DE","HON","GE","RTX","LMT","NOC","BA","UPS","FDX","UNP","CSX",
    "XOM","CVX","COP","SLB","OXY","LIN","FCX","NEM","DOW","NUE",
    "WMT","COST","HD","LOW","MCD","SBUX","NKE","DIS","KO","PEP","PG","PM",
    "JNJ","PFE","MRK","LLY","UNH","ABBV","AMGN","GILD","TMO","ABT",
    "NEE","DUK","SO","VZ","T","TMUS","AMT","PLD","O","TSLA","GM","F","TM","MATX","ZIM",
}

BLS_TRANSLATIONS = {
    "Employment Situation": ("美國非農就業報告", "high", ["NASDAQ", "美債", "美元", "黃金", "台股"]),
    "Consumer Price Index": ("美國 CPI 通膨", "high", ["NASDAQ", "美債", "美元", "黃金", "台股"]),
    "Producer Price Index": ("美國 PPI 生產者物價", "medium", ["美債", "美元", "NASDAQ"]),
    "Job Openings and Labor Turnover Survey": ("美國 JOLTS 職缺數", "medium", ["美債", "美元", "NASDAQ"]),
    "Productivity and Costs": ("美國生產力與單位勞動成本", "medium", ["美債", "NASDAQ", "美元"]),
    "U.S. Import and Export Price Indexes": ("美國進出口物價", "low", ["美元", "美債", "原物料"]),
    "Employment Cost Index": ("美國就業成本指數", "high", ["美債", "美元", "NASDAQ"]),
    "Real Earnings": ("美國實質薪資", "low", ["消費股", "美元", "美債"]),
}
BEA_TRANSLATIONS = {
    "Gross Domestic Product": ("美國 GDP", "high", ["S&P 500", "美債", "美元", "台股"]),
    "Personal Income and Outlays": ("美國個人所得與支出／PCE", "high", ["NASDAQ", "美債", "美元", "黃金"]),
    "U.S. International Trade in Goods and Services": ("美國貿易收支", "medium", ["美元", "美債", "航運"]),
    "Corporate Profits": ("美國企業獲利", "medium", ["S&P 500", "NASDAQ"]),
}

GROUP_BY_CATEGORY = {
    "central-bank":"macro", "macro":"macro", "policy":"macro",
    "earnings":"earnings", "monthly-revenue":"earnings", "report-deadline":"earnings",
    "ex-dividend":"dividend", "dividend-decision":"dividend", "dividend-payment":"dividend", "etf-distribution":"dividend",
    "investor-conference":"corporate", "shareholder-meeting":"corporate", "corporate-action":"corporate",
    "taiwan":"corporate", "tech":"corporate",
}


@dataclass
class SourceResult:
    key: str
    name: str
    url: str
    events: list[dict[str, Any]]
    status: str = "ok"
    message: str = ""


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(clean(part) for part in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha1(raw).hexdigest()[:15]}"


def iso_taipei(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=TAIPEI)
    return value.astimezone(TAIPEI).isoformat(timespec="seconds")


def parse_number(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("$", "")
    if not text or text in {"-", "--", "N/A", "尚未公告"}:
        return None
    try:
        return float(text.rstrip("%"))
    except ValueError:
        match = re.match(r"([-+]?\d+(?:\.\d+)?)\s*([KMBT])", text, re.I)
        if not match:
            return None
        return float(match.group(1)) * {"K":1e3,"M":1e6,"B":1e9,"T":1e12}[match.group(2).upper()]


def fmt_number(value: float | None, digits: int = 4) -> str:
    if value is None:
        return ""
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return text


def parse_roc_date(value: Any) -> date | None:
    text = clean(value).replace("/", "").replace("-", "")
    if not text:
        return None
    try:
        if len(text) == 7 and text.isdigit():
            return date(int(text[:3]) + 1911, int(text[3:5]), int(text[5:7]))
        if len(text) == 8 and text.isdigit():
            return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None
    try:
        return date_parser.parse(clean(value), dayfirst=False).date()
    except Exception:
        return None


def at_taipei(day: date, hhmm: str | None = None, default_hour: int = 9) -> datetime:
    hour, minute = default_hour, 0
    if hhmm:
        match = re.search(r"(\d{1,2})[:：](\d{2})", hhmm)
        if match:
            hour, minute = int(match.group(1)), int(match.group(2))
    return datetime.combine(day, time(hour, minute), tzinfo=TAIPEI)


def http_get(session: requests.Session, url: str, *, attempts: int = 3, timeout: int = 28, **kwargs: Any) -> requests.Response:
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            headers = {**HEADERS, **kwargs.pop("headers", {})}
            response = session.get(url, headers=headers, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except Exception as exc:
            error = exc
            if attempt + 1 < attempts:
                time_module.sleep(1.2 * (attempt + 1))
    assert error is not None
    raise error


def http_json(session: requests.Session, url: str, **kwargs: Any) -> Any:
    return http_get(session, url, **kwargs).json()


def load_asset_maps() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    payload = read_json(ASSETS_PATH, {"items": []})
    by_market_symbol: dict[str, dict[str, Any]] = {}
    by_symbol: dict[str, dict[str, Any]] = {}
    for item in payload.get("items", []):
        symbol = clean(item.get("symbol")).upper()
        market = clean(item.get("market")).upper()
        if not symbol:
            continue
        by_market_symbol[f"{market}:{symbol}"] = item
        by_symbol.setdefault(symbol, item)
    return by_market_symbol, by_symbol


ASSET_BY_KEY, ASSET_BY_SYMBOL = load_asset_maps()


def asset_info(symbol: str, name: str = "", market: str = "TW") -> dict[str, Any]:
    symbol = clean(symbol).upper()
    item = ASSET_BY_KEY.get(f"{market}:{symbol}") or ASSET_BY_SYMBOL.get(symbol) or {}
    resolved_name = clean(item.get("name_zh") or item.get("name") or name or symbol)
    asset_class = clean(item.get("asset_class") or "")
    is_etf = asset_class in {"etf", "fund"} or (market == "TW" and symbol.startswith("00"))
    is_active = is_etf and ("主動" in resolved_name or "主動" in name)
    return {
        "asset_id": item.get("id") or f"{market}:{symbol}",
        "symbol": symbol,
        "name": resolved_name,
        "asset_class": "etf" if is_etf else (asset_class or "stock"),
        "is_etf": is_etf,
        "is_active_etf": is_active,
        "industry": item.get("official_industry") or item.get("industry") or "",
    }


def base_event(
    *,
    event_id: str,
    title: str,
    start: datetime,
    category: str,
    region: str,
    impact: str,
    description: str,
    market_effect: str,
    source_name: str,
    source_url: str,
    origin: str,
    all_day: bool = False,
    is_estimated: bool = False,
    assets: list[str] | None = None,
    tags: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    event = {
        "id": event_id,
        "title": clean(title),
        "start": iso_taipei(start),
        "category": category,
        "event_type": extra.pop("event_type", category),
        "event_group": extra.pop("event_group", category),
        "region": region,
        "impact": impact,
        "description": clean(description),
        "market_effect": clean(market_effect),
        "assets": assets or [],
        "tags": tags or [],
        "source_name": source_name,
        "source_url": source_url,
        "origin": origin,
        "all_day": all_day,
        "is_estimated": is_estimated,
        "verification_status": extra.pop("verification_status", "confirmed"),
        "time_status": extra.pop("time_status", "estimated" if is_estimated else "confirmed"),
    }
    event.update({key: value for key, value in extra.items() if value not in (None, "", [], {})})
    return event


def translate_release(summary: str, mapping: dict[str, tuple[str, str, list[str]]]) -> tuple[str, str, list[str]] | None:
    for needle, translated in mapping.items():
        if needle.lower() in summary.lower():
            return translated
    return None


def fetch_bls(session: requests.Session) -> SourceResult:
    url = "https://www.bls.gov/schedule/news_release/bls.ics"
    if Calendar is None:
        raise RuntimeError("icalendar package is required")
    response = http_get(session, url)
    calendar = Calendar.from_ical(response.content)
    events: list[dict[str, Any]] = []
    for component in calendar.walk("VEVENT"):
        summary = clean(component.get("summary"))
        translated = translate_release(summary, BLS_TRANSLATIONS)
        if not translated:
            continue
        raw_dt = component.decoded("dtstart")
        if isinstance(raw_dt, date) and not isinstance(raw_dt, datetime):
            raw_dt = datetime.combine(raw_dt, time(8, 30), tzinfo=NEW_YORK)
        elif raw_dt.tzinfo is None:
            raw_dt = raw_dt.replace(tzinfo=NEW_YORK)
        dt = raw_dt.astimezone(TAIPEI)
        if not (NOW - timedelta(days=14) <= dt <= NOW + timedelta(days=400)):
            continue
        title, impact, assets = translated
        events.append(base_event(
            event_id=stable_id("bls", summary, dt.isoformat()),
            title=title, start=dt, category="macro", region="US", impact=impact,
            description=clean(component.get("description")) or f"BLS 發布 {summary}。",
            market_effect="數據與市場預期的落差可能改變聯準會政策、美債殖利率、美元與股票評價。",
            source_name="U.S. BLS", source_url=url, origin="bls",
            assets=assets, tags=["BLS", summary], event_type="economic-release", event_group="macro",
        ))
    return SourceResult("bls", "U.S. BLS release calendar", url, events)


def fetch_bea(session: requests.Session) -> SourceResult:
    url = "https://www.bea.gov/news/schedule"
    soup = BeautifulSoup(http_get(session, url).text, "html.parser")
    raw_text = soup.get_text("\n", strip=True)
    pattern = re.compile(
        r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(?P<day>\d{1,2})\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s+(?P<ampm>AM|PM)\s+(?:News|Data)\s+(?P<title>[^\n]+)",
        re.I,
    )
    events: list[dict[str, Any]] = []
    for match in pattern.finditer(raw_text):
        raw_title = clean(match.group("title"))
        translated = translate_release(raw_title, BEA_TRANSLATIONS)
        if not translated:
            continue
        month = datetime.strptime(match.group("month"), "%B").month
        hour = int(match.group("hour")) % 12 + (12 if match.group("ampm").upper() == "PM" else 0)
        candidates = [NOW.year - 1, NOW.year, NOW.year + 1]
        dt = min(
            (datetime(year, month, int(match.group("day")), hour, int(match.group("minute")), tzinfo=NEW_YORK).astimezone(TAIPEI) for year in candidates),
            key=lambda value: abs((value - NOW).total_seconds()),
        )
        if not (NOW - timedelta(days=14) <= dt <= NOW + timedelta(days=400)):
            continue
        title, impact, assets = translated
        events.append(base_event(
            event_id=stable_id("bea", raw_title, dt.date()),
            title=title, start=dt, category="macro", region="US", impact=impact,
            description=f"BEA 發布 {raw_title}。",
            market_effect="成長、所得、消費與通膨資料可能改變美債、美元及風險資產定價。",
            source_name="U.S. BEA", source_url=url, origin="bea",
            assets=assets, tags=["BEA", raw_title], event_type="economic-release", event_group="macro",
        ))
    if not events:
        raise RuntimeError("BEA schedule returned no recognized events")
    return SourceResult("bea", "U.S. BEA release schedule", url, events)


def report_datetime(us_day: date, timing: str) -> tuple[datetime, bool, str]:
    text = clean(timing).lower()
    if "after" in text or "post" in text:
        return datetime.combine(us_day, time(17, 0), tzinfo=NEW_YORK).astimezone(TAIPEI), False, "美股盤後"
    if "before" in text or "pre" in text:
        return datetime.combine(us_day, time(7, 0), tzinfo=NEW_YORK).astimezone(TAIPEI), False, "美股盤前"
    return datetime.combine(us_day, time(9, 0), tzinfo=TAIPEI), True, "時間待確認"


def nasdaq_rows(session: requests.Session, endpoint: str, us_day: date) -> list[dict[str, Any]]:
    payload = http_json(
        session,
        f"https://api.nasdaq.com/api/calendar/{endpoint}",
        headers=NASDAQ_HEADERS,
        params={"date": us_day.isoformat()},
        attempts=2,
    )
    data = (payload or {}).get("data") or {}
    return data.get("rows") or []


def fetch_nasdaq_earnings(session: requests.Session) -> SourceResult:
    page_url = "https://www.nasdaq.com/market-activity/earnings"
    events: list[dict[str, Any]] = []
    errors = 0
    for offset in range(0, 46):
        us_day = (NOW.astimezone(NEW_YORK) + timedelta(days=offset)).date()
        if us_day.weekday() >= 5:
            continue
        try:
            rows = nasdaq_rows(session, "earnings", us_day)
        except Exception:
            errors += 1
            continue
        for row in rows:
            symbol = clean(row.get("symbol")).upper()
            name = clean(row.get("name"))
            if not symbol:
                continue
            market_cap = parse_number(row.get("marketCap")) or 0
            timing = clean(row.get("time") or row.get("timeOfDay"))
            dt, estimated, timing_label = report_datetime(us_day, timing)
            impact = "high" if symbol in WATCHLIST or market_cap >= 100_000_000_000 else ("medium" if market_cap >= 10_000_000_000 else "low")
            forecast_eps = clean(row.get("epsForecast"))
            fiscal_quarter = clean(row.get("fiscalQuarterEnding"))
            events.append(base_event(
                event_id=stable_id("us-earnings", symbol, us_day),
                title=f"{symbol} {name} 財報".strip(),
                start=dt, category="earnings", region="US", impact=impact,
                description=f"{name or symbol} 預計於美股 {us_day.isoformat()} {timing_label}公布財報。",
                market_effect="營收、EPS、毛利率與財測相對預期的落差，可能影響公司及同產業供應鏈。",
                source_name="Nasdaq Earnings Calendar", source_url=page_url, origin="nasdaq-earnings",
                all_day=estimated, is_estimated=estimated,
                assets=[symbol, name], tags=[symbol, "財報", timing_label],
                event_type="earnings-release", event_group="earnings",
                market="US", symbol=symbol, asset_name=name, asset_id=f"US:{symbol}",
                eps_forecast=forecast_eps, fiscal_period=fiscal_quarter,
                release_stage="財報發布", time_status="estimated" if estimated else "confirmed",
            ))
        time_module.sleep(0.06)
    if not events and errors:
        raise RuntimeError(f"Nasdaq earnings failed on {errors} dates")
    return SourceResult("nasdaq-earnings", "Nasdaq earnings calendar", page_url, events, "warning" if errors else "ok", f"{errors} dates failed" if errors else "")


def parse_us_date(value: Any) -> date | None:
    text = clean(value)
    if not text:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    try:
        return date_parser.parse(text).date()
    except Exception:
        return None


def fetch_nasdaq_dividends(session: requests.Session) -> SourceResult:
    page_url = "https://www.nasdaq.com/market-activity/dividends"
    events: list[dict[str, Any]] = []
    errors = 0
    for offset in range(0, 46):
        us_day = (NOW.astimezone(NEW_YORK) + timedelta(days=offset)).date()
        if us_day.weekday() >= 5:
            continue
        try:
            rows = nasdaq_rows(session, "dividends", us_day)
        except Exception:
            errors += 1
            continue
        for row in rows:
            symbol = clean(row.get("symbol")).upper()
            name = clean(row.get("companyName") or row.get("name"))
            ex_day = parse_us_date(row.get("dividend_Ex_Date") or row.get("exOrEffDate") or row.get("exDate")) or us_day
            payment_day = parse_us_date(row.get("payment_Date") or row.get("paymentDate"))
            record_day = parse_us_date(row.get("record_Date") or row.get("recordDate"))
            amount = parse_number(row.get("amount") or row.get("dividend_Rate") or row.get("dividendRate"))
            if not symbol:
                continue
            impact = "medium" if symbol in WATCHLIST else "low"
            events.append(base_event(
                event_id=stable_id("us-exdiv", symbol, ex_day),
                title=f"{symbol} {name} 除息".strip(),
                start=at_taipei(ex_day, default_hour=9), category="ex-dividend", region="US", impact=impact,
                description=f"{name or symbol} 除息日。{('每股股利約 ' + fmt_number(amount) + ' 美元。') if amount is not None else ''}",
                market_effect="除息日股價理論上會反映股利金額；實際走勢仍受市場及公司基本面影響。",
                source_name="Nasdaq Dividend Calendar", source_url=page_url, origin="nasdaq-dividends",
                all_day=True, assets=[symbol, name], tags=[symbol, "除息", "股利"],
                event_type="ex-dividend", event_group="dividend",
                market="US", symbol=symbol, asset_name=name, asset_id=f"US:{symbol}",
                cash_dividend=amount, currency="USD",
                ex_date=ex_day.isoformat(), record_date=record_day.isoformat() if record_day else None,
                payment_date=payment_day.isoformat() if payment_day else None,
            ))
            if payment_day:
                events.append(base_event(
                    event_id=stable_id("us-dividend-payment", symbol, payment_day),
                    title=f"{symbol} {name} 股利發放".strip(),
                    start=at_taipei(payment_day, default_hour=9), category="dividend-payment", region="US", impact="low",
                    description=f"{name or symbol} 預定股利發放日。",
                    market_effect="此為現金流事件，通常不等同新的公司利多或利空。",
                    source_name="Nasdaq Dividend Calendar", source_url=page_url, origin="nasdaq-dividends",
                    all_day=True, assets=[symbol, name], tags=[symbol, "股利發放"],
                    event_type="dividend-payment", event_group="dividend",
                    market="US", symbol=symbol, asset_name=name, asset_id=f"US:{symbol}",
                    cash_dividend=amount, currency="USD", payment_date=payment_day.isoformat(),
                ))
        time_module.sleep(0.06)
    if not events and errors:
        raise RuntimeError(f"Nasdaq dividend calendar failed on {errors} dates")
    return SourceResult("nasdaq-dividends", "Nasdaq dividend calendar", page_url, events, "warning" if errors else "ok", f"{errors} dates failed" if errors else "")


def fetch_nasdaq_splits(session: requests.Session) -> SourceResult:
    page_url = "https://www.nasdaq.com/market-activity/stock-splits"
    events: list[dict[str, Any]] = []
    errors = 0
    for offset in range(0, 46):
        us_day = (NOW.astimezone(NEW_YORK) + timedelta(days=offset)).date()
        if us_day.weekday() >= 5:
            continue
        try:
            rows = nasdaq_rows(session, "splits", us_day)
        except Exception:
            errors += 1
            continue
        for row in rows:
            symbol = clean(row.get("symbol")).upper()
            name = clean(row.get("companyName") or row.get("name"))
            effective_day = parse_us_date(row.get("executionDate") or row.get("exOrEffDate") or row.get("effectiveDate")) or us_day
            ratio = clean(row.get("ratio") or row.get("splitRatio"))
            if not symbol:
                continue
            events.append(base_event(
                event_id=stable_id("us-split", symbol, effective_day, ratio),
                title=f"{symbol} {name} 股票分割{(' ' + ratio) if ratio else ''}".strip(),
                start=at_taipei(effective_day), category="corporate-action", region="US",
                impact="medium" if symbol in WATCHLIST else "low",
                description=f"{name or symbol} 股票分割／反向分割生效。",
                market_effect="分割不直接改變公司總價值，但會改變每股價格、股數與部分交易行為。",
                source_name="Nasdaq Stock Split Calendar", source_url=page_url, origin="nasdaq-splits",
                all_day=True, assets=[symbol, name], tags=[symbol, "股票分割"],
                event_type="stock-split", event_group="corporate",
                market="US", symbol=symbol, asset_name=name, asset_id=f"US:{symbol}", split_ratio=ratio,
            ))
        time_module.sleep(0.04)
    if not events and errors:
        raise RuntimeError(f"Nasdaq split calendar failed on {errors} dates")
    return SourceResult("nasdaq-splits", "Nasdaq stock split calendar", page_url, events, "warning" if errors else "ok", f"{errors} dates failed" if errors else "")


def make_tw_exdiv_event(
    *,
    market: str,
    symbol: str,
    name: str,
    day: date,
    kind: str,
    cash: float | None,
    stock_ratio: float | None,
    source_name: str,
    source_url: str,
    origin: str,
) -> dict[str, Any]:
    asset = asset_info(symbol, name, "TW")
    has_right = "權" in kind
    has_dividend = "息" in kind
    label = "除權息" if has_right and has_dividend else ("除權" if has_right else "除息")
    category = "etf-distribution" if asset["is_etf"] else "ex-dividend"
    amount_parts = []
    if cash is not None and cash != 0:
        amount_parts.append(f"現金 {fmt_number(cash)} 元")
    if stock_ratio is not None and stock_ratio != 0:
        amount_parts.append(f"股票股利率 {fmt_number(stock_ratio)}")
    active_text = "主動型 ETF" if asset["is_active_etf"] else ("ETF" if asset["is_etf"] else "股票")
    title = f"{symbol} {asset['name']} {label}"
    if cash is not None and cash != 0:
        title += f"（{fmt_number(cash)} 元）"
    return base_event(
        event_id=stable_id("tw-exdiv", market, symbol, day, label),
        title=title, start=at_taipei(day), category=category, region="TW",
        impact="medium" if asset["is_active_etf"] or symbol in {"0050","0056","00878","00919","00929","00940","00981A","00982A","2330","2882","2603"} else "low",
        description=f"{market} {active_text}的{label}日。{'、'.join(amount_parts) if amount_parts else '實際金額以交易所公告為準。'}",
        market_effect="除權息會調整參考價；ETF 配息也會使淨值與市價反映分配金額，不代表投資人額外創造報酬。",
        source_name=source_name, source_url=source_url, origin=origin,
        all_day=True, assets=[symbol, asset["name"], active_text], tags=[label, market, active_text],
        event_type="etf-distribution" if asset["is_etf"] else "ex-dividend",
        event_group="dividend", market=market, symbol=symbol, asset_name=asset["name"],
        asset_id=asset["asset_id"], asset_class=asset["asset_class"], is_active_etf=asset["is_active_etf"],
        cash_dividend=cash, stock_dividend_ratio=stock_ratio, currency="TWD", ex_date=day.isoformat(),
    )


def fetch_twse_exdiv(session: requests.Session) -> SourceResult:
    rows = http_json(session, TWSE_EXDIV_URL)
    events = []
    for row in rows if isinstance(rows, list) else []:
        day = parse_roc_date(row.get("Date"))
        symbol = clean(row.get("Code"))
        if not day or not symbol:
            continue
        events.append(make_tw_exdiv_event(
            market="TWSE", symbol=symbol, name=clean(row.get("Name")), day=day,
            kind=clean(row.get("Exdividend")), cash=parse_number(row.get("CashDividend")),
            stock_ratio=parse_number(row.get("StockDividendRatio")),
            source_name="TWSE 上市股票除權除息預告表", source_url=TWSE_EXDIV_URL, origin="twse-exdiv",
        ))
    return SourceResult("twse-exdiv", "TWSE listed ex-right/ex-dividend", TWSE_EXDIV_URL, events)


def fetch_tpex_exdiv(session: requests.Session) -> SourceResult:
    rows = http_json(session, TPEX_EXDIV_URL)
    events = []
    for row in rows if isinstance(rows, list) else []:
        day = parse_roc_date(row.get("ExRrightsExDividendDate"))
        symbol = clean(row.get("SecuritiesCompanyCode"))
        if not day or not symbol:
            continue
        events.append(make_tw_exdiv_event(
            market="TPEX", symbol=symbol, name=clean(row.get("CompanyName")), day=day,
            kind=clean(row.get("ExRrightsExDividend")), cash=parse_number(row.get("CashDividend")),
            stock_ratio=parse_number(row.get("StockDividendRatio")),
            source_name="TPEx 上櫃股票除權除息預告表", source_url=TPEX_EXDIV_URL, origin="tpex-exdiv",
        ))
    return SourceResult("tpex-exdiv", "TPEx OTC ex-right/ex-dividend", TPEX_EXDIV_URL, events)


def first_value(row: dict[str, Any], names: Iterable[str]) -> str:
    for name in names:
        value = clean(row.get(name))
        if value:
            return value
    return ""


def dividend_total(row: dict[str, Any], contains: str) -> float:
    total = 0.0
    for key, value in row.items():
        if contains in key and ("元/股" in key or "每股" in key):
            number = parse_number(value)
            if number:
                total += number
    return total


def parse_dividend_plan_rows(rows: Any, market: str, source_url: str, origin: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return events
    for row in rows:
        symbol = first_value(row, ["公司代號", "CompanyCode", "SecuritiesCompanyCode", "Code"])
        name = first_value(row, ["公司名稱", "CompanyName", "Name"])
        if not symbol:
            continue
        asset = asset_info(symbol, name, "TW")
        decision_day = parse_roc_date(first_value(row, ["董事會（擬議）股利分派日", "董事會股利分派日", "BoardMeetingDate"]))
        shareholder_day = parse_roc_date(first_value(row, ["股東會日期", "ShareholdersMeetingDate"]))
        progress = first_value(row, ["決議（擬議）進度", "Progress"])
        period = first_value(row, ["股利所屬年(季)度", "股利年度", "DividendYear"])
        cash = dividend_total(row, "現金")
        stock = dividend_total(row, "配股")
        description = f"{progress or '公司'}公布{period or ''}股利方案。現金股利 {fmt_number(cash)} 元／股；股票股利 {fmt_number(stock)} 元／股。"
        if decision_day and NOW.date() - timedelta(days=60) <= decision_day <= NOW.date() + timedelta(days=240):
            events.append(base_event(
                event_id=stable_id("tw-dividend-plan", market, symbol, decision_day, period),
                title=f"{symbol} {asset['name']} 股利方案決議",
                start=at_taipei(decision_day), category="dividend-decision", region="TW", impact="medium" if cash or stock else "low",
                description=description,
                market_effect="股利方案影響現金殖利率、保留盈餘與市場對公司資本配置的評價；除息日另列為獨立事件。",
                source_name=f"{market} 股利分派資料", source_url=source_url, origin=origin,
                all_day=True, assets=[symbol, asset["name"]], tags=["股利方案", progress, period],
                event_type="dividend-decision", event_group="dividend",
                market=market, symbol=symbol, asset_name=asset["name"], asset_id=asset["asset_id"],
                cash_dividend=cash or None, stock_dividend=stock or None, currency="TWD",
                announcement_date=decision_day.isoformat(), fiscal_period=period, release_stage=progress,
            ))
        if shareholder_day and NOW.date() - timedelta(days=30) <= shareholder_day <= NOW.date() + timedelta(days=240):
            events.append(base_event(
                event_id=stable_id("tw-shareholder-dividend", market, symbol, shareholder_day, period),
                title=f"{symbol} {asset['name']} 股東會確認股利案",
                start=at_taipei(shareholder_day), category="shareholder-meeting", region="TW", impact="low",
                description=f"股東會預定確認{period or ''}財報與盈餘分派等議案。",
                market_effect="股東會通常是已公告股利案的正式確認階段，仍需留意議案是否調整。",
                source_name=f"{market} 股利分派資料", source_url=source_url, origin=origin,
                all_day=True, assets=[symbol, asset["name"]], tags=["股東會", "股利"],
                event_type="shareholder-meeting", event_group="corporate",
                market=market, symbol=symbol, asset_name=asset["name"], asset_id=asset["asset_id"],
                cash_dividend=cash or None, stock_dividend=stock or None, currency="TWD",
                shareholder_meeting_date=shareholder_day.isoformat(), fiscal_period=period,
            ))
    return events


def fetch_twse_dividend_plans(session: requests.Session) -> SourceResult:
    rows = http_json(session, TWSE_DIVIDEND_PLAN_URL)
    return SourceResult("twse-dividend-plan", "TWSE/MOPS listed dividend plans", TWSE_DIVIDEND_PLAN_URL, parse_dividend_plan_rows(rows, "TWSE", TWSE_DIVIDEND_PLAN_URL, "twse-dividend-plan"))


def fetch_tpex_dividend_plans(session: requests.Session) -> SourceResult:
    rows = http_json(session, TPEX_DIVIDEND_PLAN_URL)
    return SourceResult("tpex-dividend-plan", "TPEx/MOPS OTC dividend plans", TPEX_DIVIDEND_PLAN_URL, parse_dividend_plan_rows(rows, "TPEX", TPEX_DIVIDEND_PLAN_URL, "tpex-dividend-plan"))


MATERIAL_CLASSIFIERS = [
    (re.compile(r"財務報告|財報|合併財務報表|季報|年度財務"), "earnings", "financial-report", "earnings"),
    (re.compile(r"法說|法人說明會|業績說明會"), "investor-conference", "investor-conference", "corporate"),
    (re.compile(r"股利|盈餘分派|現金股息|配息"), "dividend-decision", "dividend-decision", "dividend"),
    (re.compile(r"股東會|股東常會|股東臨時會"), "shareholder-meeting", "shareholder-meeting", "corporate"),
    (re.compile(r"月營收|營業收入"), "monthly-revenue", "monthly-revenue", "earnings"),
    (re.compile(r"減資|增資|合併|分割|股份轉換|下市|終止上市|更名|公開收購|處分重要資產"), "corporate-action", "corporate-action", "corporate"),
]


def classify_material(text: str) -> tuple[str, str, str] | None:
    for pattern, category, event_type, group in MATERIAL_CLASSIFIERS:
        if pattern.search(text):
            return category, event_type, group
    return None


def extract_first_market_date(text: str) -> date | None:
    for token in re.findall(r"(?<!\d)(\d{3}[/-]?\d{2}[/-]?\d{2}|\d{4}[/-]\d{1,2}[/-]\d{1,2})(?!\d)", text):
        parsed = parse_roc_date(token)
        if parsed:
            return parsed
    return None


def parse_material_rows(rows: Any, market: str, source_url: str, origin: str) -> list[dict[str, Any]]:
    events = []
    if not isinstance(rows, list):
        return events
    for row in rows:
        text = " ".join(clean(value) for value in row.values())
        classified = classify_material(text)
        if not classified:
            continue
        category, event_type, group = classified
        symbol = first_value(row, ["公司代號", "CompanyCode", "SecuritiesCompanyCode", "Code"])
        name = first_value(row, ["公司名稱", "CompanyName", "Name"])
        subject = first_value(row, ["主旨", "Subject", "說明", "Description"]) or text[:180]
        announcement_day = parse_roc_date(first_value(row, ["發言日期", "出表日期", "Date"])) or NOW.date()
        payment_day = extract_first_market_date(subject) if re.search(r"現金股利.{0,16}(?:發放日|支付日)|(?:發放日|支付日).{0,16}現金股利|收益分配.{0,16}發放", subject) else None
        if payment_day:
            category, event_type, group = "dividend-payment", "dividend-payment", "dividend"
        day = payment_day or announcement_day
        hhmm = first_value(row, ["發言時間", "Time"]) if not payment_day else ""
        if not symbol:
            continue
        asset = asset_info(symbol, name, "TW")
        impact = "medium" if category in {"earnings","dividend-decision","corporate-action"} else "low"
        events.append(base_event(
            event_id=stable_id("tw-material", market, symbol, day, subject),
            title=f"{symbol} {asset['name']}｜{subject[:70]}",
            start=at_taipei(day, hhmm), category=category, region="TW", impact=impact,
            description=subject,
            market_effect="公司重大訊息可能影響個股評價；應點入公開資訊觀測站閱讀完整說明與附件。",
            source_name=f"{market} 每日重大訊息", source_url=source_url, origin=origin,
            all_day=not bool(hhmm), assets=[symbol, asset["name"]], tags=[category, "重大訊息"],
            event_type=event_type, event_group=group,
            market=market, symbol=symbol, asset_name=asset["name"], asset_id=asset["asset_id"],
            announcement_date=announcement_day.isoformat(), payment_date=payment_day.isoformat() if payment_day else None,
        ))
    return events


def fetch_twse_material(session: requests.Session) -> SourceResult:
    rows = http_json(session, TWSE_MATERIAL_URL)
    return SourceResult("twse-material", "TWSE listed daily material information", TWSE_MATERIAL_URL, parse_material_rows(rows, "TWSE", TWSE_MATERIAL_URL, "twse-material"))


def fetch_tpex_material(session: requests.Session) -> SourceResult:
    rows = http_json(session, TPEX_MATERIAL_URL)
    return SourceResult("tpex-material", "TPEx OTC daily material information", TPEX_MATERIAL_URL, parse_material_rows(rows, "TPEX", TPEX_MATERIAL_URL, "tpex-material"))


def parse_monthly_revenue_rows(rows: Any, market: str, source_url: str, origin: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not isinstance(rows, list):
        return events
    major = {"2330","2317","2454","2308","2382","3231","2881","2882","2886","2603","2609","2615","1216","1301","1303"}
    for row in rows:
        symbol = first_value(row, ["公司代號","CompanyCode","SecuritiesCompanyCode","Code"])
        name = first_value(row, ["公司名稱","CompanyName","Name"])
        day = parse_roc_date(first_value(row, ["出表日期","Date"]))
        period = first_value(row, ["資料年月","DataYearMonth","YearMonth"])
        if not symbol or not day:
            continue
        asset = asset_info(symbol, name, "TW")
        revenue = parse_number(first_value(row, ["營業收入-當月營收","當月營收","CurrentMonthRevenue","MonthlyRevenue"]))
        yoy = parse_number(first_value(row, ["營業收入-去年同月增減(%)","去年同月增減(%)","MonthlyYoY"]))
        mom = parse_number(first_value(row, ["營業收入-上月比較增減(%)","上月比較增減(%)","MonthlyMoM"]))
        detail = []
        if revenue is not None:
            detail.append(f"當月營收 {revenue:,.0f}")
        if yoy is not None:
            detail.append(f"年增 {yoy:g}%")
        if mom is not None:
            detail.append(f"月增 {mom:g}%")
        events.append(base_event(
            event_id=stable_id("tw-monthly-revenue", market, symbol, period, day),
            title=f"{symbol} {asset['name']} {period or ''}月營收".strip(),
            start=at_taipei(day, default_hour=9), category="monthly-revenue", region="TW",
            impact="medium" if symbol in major else "low",
            description="；".join(detail) if detail else f"{asset['name']}公布月營收。",
            market_effect="月營收反映近期出貨與需求，但不等同獲利；仍需搭配毛利率、匯率與產品組合。",
            source_name=f"{market}／MOPS 每月營業收入", source_url=source_url, origin=origin,
            all_day=True, assets=[symbol,asset["name"]], tags=["月營收",period],
            event_type="monthly-revenue-release", event_group="earnings",
            market=market, symbol=symbol, asset_name=asset["name"], asset_id=asset["asset_id"],
            fiscal_period=period, revenue_actual=revenue, revenue_yoy=yoy, revenue_mom=mom,
            announcement_date=day.isoformat(),
        ))
    return events


def fetch_twse_monthly_revenue(session: requests.Session) -> SourceResult:
    rows = http_json(session, TWSE_REVENUE_URL)
    return SourceResult("twse-monthly-revenue", "TWSE/MOPS listed monthly revenue", TWSE_REVENUE_URL, parse_monthly_revenue_rows(rows,"TWSE",TWSE_REVENUE_URL,"twse-monthly-revenue"))


def fetch_tpex_monthly_revenue(session: requests.Session) -> SourceResult:
    rows = http_json(session, TPEX_REVENUE_URL)
    return SourceResult("tpex-monthly-revenue", "TPEx/MOPS OTC monthly revenue", TPEX_REVENUE_URL, parse_monthly_revenue_rows(rows,"TPEX",TPEX_REVENUE_URL,"tpex-monthly-revenue"))


def parse_date_range(text: str) -> tuple[date | None, date | None]:
    matches = re.findall(r"(?<!\d)(\d{3}/\d{1,2}/\d{1,2}|\d{4}/\d{1,2}/\d{1,2}|\d{7}|\d{8})(?!\d)", text)
    days = [parse_roc_date(value) for value in matches]
    valid = [day for day in days if day]
    return (valid[0], valid[-1]) if valid else (None, None)


def parse_mops_conference_html(html: str, market: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table#myTable") or soup.find("table")
    if table is None:
        raise ValueError("MOPS conference table not found")
    events = []
    for tr in table.select("tr[data-type='body'], tbody tr"):
        cells = tr.find_all("td", recursive=False)
        if len(cells) < 6:
            continue
        symbol = clean(cells[0].get_text(" ", strip=True))
        name = clean(cells[1].get_text(" ", strip=True))
        start_day, _ = parse_date_range(cells[2].get_text(" ", strip=True))
        hhmm = clean(cells[3].get_text(" ", strip=True))
        summary = clean(cells[5].get_text(" ", strip=True))
        if not symbol or not start_day:
            continue
        asset = asset_info(symbol, name, "TW")
        financial = bool(re.search(r"財務報告|財報|營運成果|業績", summary))
        category = "earnings" if financial else "investor-conference"
        title = f"{symbol} {asset['name']} {'財報暨法說會' if financial else '法人說明會'}"
        event = base_event(
            event_id=stable_id("mops-conference", market, symbol, start_day, hhmm, summary),
            title=title, start=at_taipei(start_day, hhmm, default_hour=14), category=category, region="TW",
            impact="medium" if financial else "low",
            description=summary or "公司預定舉行法人說明會。",
            market_effect="法說會可能更新營運、訂單、資本支出與財測，是個股重要資訊事件。",
            source_name="MOPS 法人說明會一覽表", source_url=MOPS_CONFERENCE_PAGE, origin="mops-conference",
            all_day=not bool(hhmm), assets=[symbol, asset["name"]], tags=["法說會", "財報" if financial else "營運"],
            event_type="financial-report" if financial else "investor-conference",
            event_group="earnings" if financial else "corporate",
            market=market, symbol=symbol, asset_name=asset["name"], asset_id=asset["asset_id"],
            financial_report_related=financial, release_stage="法人說明會",
        )
        events.append(event)
    return events


def fetch_mops_conferences(session: requests.Session) -> SourceResult:
    events: list[dict[str, Any]] = []
    errors = 0
    windows = []
    year, month = NOW.year, NOW.month
    for offset in range(3):
        zero = month - 1 + offset
        windows.append((year + zero // 12, zero % 12 + 1))
    for market_kind, market in (("sii", "TWSE"), ("otc", "TPEX")):
        for win_year, win_month in windows:
            try:
                redirect = session.post(
                    MOPS_REDIRECT_URL,
                    headers={**HEADERS, "Content-Type":"application/json", "Referer":"https://mops.twse.com.tw/mops/"},
                    json={
                        "apiName":"ajax_t100sb02_1",
                        "parameters":{
                            "TYPEK":market_kind, "year":str(win_year - 1911), "month":f"{win_month:02d}",
                            "co_id":"", "encodeURIComponent":1, "step":1, "firstin":1, "off":1,
                        },
                    },
                    timeout=28,
                )
                redirect.raise_for_status()
                result_url = clean((((redirect.json() or {}).get("result") or {}).get("url")))
                if not result_url.startswith("https://"):
                    raise ValueError("MOPS signed result URL missing")
                html = http_get(session, result_url, attempts=2, headers={"Referer":"https://mops.twse.com.tw/mops/"}).text
                events.extend(parse_mops_conference_html(html, market))
            except Exception:
                errors += 1
    if not events and errors:
        raise RuntimeError(f"MOPS conference failed on {errors} windows")
    return SourceResult("mops-conference", "MOPS investor conference calendar", MOPS_CONFERENCE_PAGE, events, "warning" if errors else "ok", f"{errors} windows failed" if errors else "")


def next_weekday(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def recurring_deadlines() -> list[dict[str, Any]]:
    events = []
    for offset in range(-1, 7):
        zero = NOW.month - 1 + offset
        year = NOW.year + zero // 12
        month = zero % 12 + 1
        revenue_day = next_weekday(date(year, month, 10))
        previous_month = 12 if month == 1 else month - 1
        previous_year = year - 1 if month == 1 else year
        events.append(base_event(
            event_id=f"tw-monthly-revenue-deadline-{year}-{month:02d}",
            title=f"台灣上市櫃公司 {previous_year} 年 {previous_month} 月營收公告期限",
            start=at_taipei(revenue_day, default_hour=23), category="monthly-revenue", region="TW", impact="medium",
            description="多數上市櫃公司應在每月 10 日前公告上月營收；遇假日可能順延，個別公司可提早發布。",
            market_effect="月營收可快速反映景氣、出貨與需求，但仍需搭配毛利率、匯率及一次性因素判讀。",
            source_name="MOPS 月營收制度", source_url="https://mops.twse.com.tw/", origin="rule-deadline",
            all_day=True, is_estimated=True, assets=["台股", "上市櫃公司"], tags=["月營收", "公告期限"],
            event_type="monthly-revenue-deadline", event_group="earnings", verification_status="rule-based", time_status="deadline-window",
        ))
    quarterly = [
        (3, 31, "年度財務報告", "年度"),
        (5, 15, "第一季財務報告", "Q1"),
        (8, 14, "第二季財務報告", "Q2"),
        (11, 14, "第三季財務報告", "Q3"),
    ]
    for year in range(NOW.year - 1, NOW.year + 2):
        for month, day_num, label, period in quarterly:
            try:
                day = next_weekday(date(year, month, day_num))
            except ValueError:
                continue
            events.append(base_event(
                event_id=f"tw-{period.lower()}-deadline-{year}-{day.month:02d}-{day.day:02d}",
                title=f"台灣多數上市櫃公司 {label}申報期限",
                start=at_taipei(day, default_hour=23), category="report-deadline", region="TW", impact="high" if period in {"Q2","年度"} else "medium",
                description="此為多數一般公司的法定申報截止日；金融、保險、特殊產業及個別公司期限可能不同。",
                market_effect="截止日前後通常是台股財報密集期，個股可能因 EPS、毛利率與展望落差出現較大波動。",
                source_name="MOPS 財務報告申報制度", source_url="https://mops.twse.com.tw/", origin="rule-deadline",
                all_day=True, is_estimated=True, assets=["台股", "上市櫃公司"], tags=["財報", "申報期限", period],
                event_type="financial-report-deadline", event_group="earnings", fiscal_period=period,
                verification_status="rule-based", time_status="deadline-window",
            ))
    return events


def default_event(event: dict[str, Any]) -> dict[str, Any]:
    row = dict(event)
    row.setdefault("impact", "low")
    row.setdefault("category", "macro")
    row.setdefault("event_type", row["category"])
    row.setdefault("event_group", GROUP_BY_CATEGORY.get(row["category"], row["category"]))
    row.setdefault("region", "GLOBAL")
    row.setdefault("assets", [])
    row.setdefault("tags", [])
    row.setdefault("all_day", False)
    row.setdefault("is_estimated", False)
    row.setdefault("origin", "manual")
    row.setdefault("verification_status", "confirmed")
    row.setdefault("time_status", "confirmed")
    row["id"] = row.get("id") or stable_id("event", row.get("title"), row.get("start"))
    return row


def deduplicate(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for raw in events:
        event = default_event(raw)
        current = by_id.get(event["id"])
        if current is None:
            by_id[event["id"]] = event
            continue
        # Live official data wins over bootstrap; curated manual wins over generated macro duplicates.
        rank = {"bootstrap-official":0, "rule-deadline":1, "manual":4}
        old_rank = rank.get(current.get("origin"), 2)
        new_rank = rank.get(event.get("origin"), 2)
        if new_rank >= old_rank:
            by_id[event["id"]] = event
    return sorted(by_id.values(), key=lambda item: date_parser.isoparse(item["start"]))


def retain_previous(previous: dict[str, Any], key: str) -> list[dict[str, Any]]:
    allowed = {
        "twse-material": 120, "tpex-material": 120, "mops-conference": 120,
        "nasdaq-earnings": 75, "nasdaq-dividends": 90, "nasdaq-splits": 90,
        "twse-exdiv": 180, "tpex-exdiv": 180,
        "twse-dividend-plan": 365, "tpex-dividend-plan": 365,
        "twse-monthly-revenue": 90, "tpex-monthly-revenue": 90,
        "bls": 400, "bea": 400,
    }
    days = allowed.get(key, 180)
    cutoff = NOW - timedelta(days=days)
    return [
        row for row in previous.get("events", [])
        if row.get("origin") == key and date_parser.isoparse(row["start"]).astimezone(TAIPEI) >= cutoff
    ]


def run_source(
    key: str,
    name: str,
    url: str,
    fetcher: Callable[[requests.Session], SourceResult],
    session: requests.Session,
    previous: dict[str, Any],
    offline: bool,
) -> SourceResult:
    if offline:
        rows = retain_previous(previous, key)
        return SourceResult(key, name, url, rows, "warning", f"offline mode; retained {len(rows)} rows")
    try:
        result = fetcher(session)
        if not result.events:
            fallback = retain_previous(previous, key)
            if fallback:
                result.events = fallback
                result.status = "warning"
                result.message = f"new feed empty; retained {len(fallback)} previous rows"
        return result
    except Exception as exc:
        fallback = retain_previous(previous, key)
        print(f"[warning] {key}: {exc}", file=sys.stderr)
        return SourceResult(key, name, url, fallback, "warning", f"{type(exc).__name__}: {str(exc)[:130]}; retained {len(fallback)} rows")


def event_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        key = event.get("event_group") or event.get("category") or "other"
        counts[key] = counts.get(key, 0) + 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manual = read_json(MANUAL_PATH, [])
    bootstrap = read_json(BOOTSTRAP_PATH, [])
    previous = read_json(EVENTS_PATH, {"events": [], "sources": []})
    previous_sources = {row.get("name"): row for row in previous.get("sources", [])}

    session = requests.Session()
    definitions = [
        ("bls", "U.S. BLS release calendar", "https://www.bls.gov/schedule/news_release/bls.ics", fetch_bls),
        ("bea", "U.S. BEA release schedule", "https://www.bea.gov/news/schedule", fetch_bea),
        ("nasdaq-earnings", "Nasdaq earnings calendar", "https://www.nasdaq.com/market-activity/earnings", fetch_nasdaq_earnings),
        ("nasdaq-dividends", "Nasdaq dividend calendar", "https://www.nasdaq.com/market-activity/dividends", fetch_nasdaq_dividends),
        ("nasdaq-splits", "Nasdaq stock split calendar", "https://www.nasdaq.com/market-activity/stock-splits", fetch_nasdaq_splits),
        ("twse-exdiv", "TWSE listed ex-right/ex-dividend", TWSE_EXDIV_URL, fetch_twse_exdiv),
        ("tpex-exdiv", "TPEx OTC ex-right/ex-dividend", TPEX_EXDIV_URL, fetch_tpex_exdiv),
        ("twse-dividend-plan", "TWSE/MOPS listed dividend plans", TWSE_DIVIDEND_PLAN_URL, fetch_twse_dividend_plans),
        ("tpex-dividend-plan", "TPEx/MOPS OTC dividend plans", TPEX_DIVIDEND_PLAN_URL, fetch_tpex_dividend_plans),
        ("twse-material", "TWSE listed daily material information", TWSE_MATERIAL_URL, fetch_twse_material),
        ("tpex-material", "TPEx OTC daily material information", TPEX_MATERIAL_URL, fetch_tpex_material),
        ("twse-monthly-revenue", "TWSE/MOPS listed monthly revenue", TWSE_REVENUE_URL, fetch_twse_monthly_revenue),
        ("tpex-monthly-revenue", "TPEx/MOPS OTC monthly revenue", TPEX_REVENUE_URL, fetch_tpex_monthly_revenue),
        ("mops-conference", "MOPS investor conference calendar", MOPS_CONFERENCE_PAGE, fetch_mops_conferences),
    ]
    results = [run_source(*definition, session, previous, args.offline) for definition in definitions]

    generated: list[dict[str, Any]] = []
    for event in bootstrap:
        event = dict(event)
        event.setdefault("origin", "bootstrap-official")
        generated.append(event)
    for event in manual:
        event = dict(event)
        event["origin"] = "manual"
        generated.append(event)
    generated.extend(recurring_deadlines())
    for result in results:
        generated.extend(result.events)

    cutoff_past = NOW - timedelta(days=180)
    cutoff_future = NOW + timedelta(days=550)
    events = [
        event for event in deduplicate(generated)
        if cutoff_past <= date_parser.isoparse(event["start"]).astimezone(TAIPEI) <= cutoff_future
    ]
    # Protect GitHub Pages from an unexpectedly huge upstream response.
    if len(events) > 9000:
        events = sorted(events, key=lambda row: (
            row.get("impact") == "high",
            row.get("event_group") in {"earnings","dividend","macro"},
            date_parser.isoparse(row["start"]),
        ), reverse=True)[:9000]
        events.sort(key=lambda row: date_parser.isoparse(row["start"]))

    source_rows = []
    for result in results:
        previous_row = previous_sources.get(result.name, {})
        source_rows.append({
            "name": result.name,
            "status": result.status,
            "last_success": iso_taipei(NOW) if result.status == "ok" else previous_row.get("last_success"),
            "url": result.url,
            "message": result.message or f"{len(result.events)} events",
            "event_count": len(result.events),
        })
    source_rows.extend([
        {"name":"Curated central-bank and policy events","status":"ok","last_success":iso_taipei(NOW),"url":"","message":f"{len(manual)} curated events","event_count":len(manual)},
        {"name":"Taiwan regulatory deadline rules","status":"ok","last_success":iso_taipei(NOW),"url":"https://mops.twse.com.tw/","message":"monthly revenue and quarterly report deadlines"},
    ])

    payload = {
        "metadata": {
            "updated_at": iso_taipei(NOW),
            "timezone": "Asia/Taipei",
            "generation_mode": "offline" if args.offline else "multi-source-live",
            "event_count": len(events),
            "group_counts": event_counts(events),
            "calendar_version": "v11.0.0",
            "coverage_note": "Company events include low-impact rows; use calendar filters and portfolio priority.",
            "sources_healthy": sum(1 for row in source_rows if row.get("status") == "ok"),
            "source_count": len(source_rows),
        },
        "sources": source_rows,
        "events": events,
    }
    EVENTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED_PATH.write_text("window.__MARKET_EVENT_SEED__ = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"Wrote {len(events)} events; groups={payload['metadata']['group_counts']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
