#!/usr/bin/env python3
"""Build Market Event Radar v11.4.31 event data from official schedules.

The updater keeps the last verified archive, refreshes selected official sources,
and records when an exact date first appears or changes. It never invents dates.
The first state-building run is treated as a baseline so old events are not
incorrectly labelled as newly announced today.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time as time_module
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EVENTS_PATH = DATA / "events.json"
SEED_PATH = DATA / "events-seed.js"
MANUAL_PATH = DATA / "manual-events.json"
STATE_PATH = DATA / "event-source-state.json"
NOW = datetime.now(ZoneInfo("Asia/Taipei"))
TAIPEI = NOW.tzinfo
NEW_YORK = ZoneInfo("America/New_York")
OFFLINE = os.getenv("EVENT_OFFLINE", "").strip() == "1"
ARCHIVE_START = date(2026, 1, 1)
ARCHIVE_START_DT = datetime.combine(ARCHIVE_START, time.min, tzinfo=TAIPEI)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.4.31; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}
TWSE_EXDIV_URL = "https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL"
TWSE_EXDIV_HISTORY_URL = "https://www.twse.com.tw/exchangeReport/TWT49U"
TPEX_EXDIV_HISTORY_URL = "https://www.tpex.org.tw/openapi/v1/tpex_exright_daily"
TPEX_EXDIV_URL = "https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost"
TWSE_DIVIDEND_PLAN_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap45_L"
TPEX_DIVIDEND_PLAN_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap39_O"
TWSE_MATERIAL_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
TPEX_MATERIAL_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"
BLS_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
BLS_HTML_URL = f"https://www.bls.gov/schedule/{NOW.year}/home.htm"
BEA_URL = "https://www.bea.gov/news/schedule"
BEA_FULL_URL = "https://www.bea.gov/index.php/news/schedule/full"
FOMC_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"

BLS_TRANSLATIONS = {
    "Employment Situation": ("美國非農就業報告", "high", ["NASDAQ", "美債", "美元", "黃金", "台股"]),
    "Consumer Price Index": ("美國 CPI 通膨", "high", ["NASDAQ", "美債", "美元", "黃金", "台股"]),
    "Producer Price Index": ("美國 PPI 生產者物價", "medium", ["美債", "美元", "NASDAQ"]),
    "Job Openings and Labor Turnover Survey": ("美國 JOLTS 職缺數", "medium", ["美債", "美元", "NASDAQ"]),
    "Employment Cost Index": ("美國就業成本指數", "high", ["美債", "美元", "NASDAQ"]),
    "Productivity and Costs": ("美國生產力與單位勞動成本", "medium", ["美債", "NASDAQ", "美元"]),
}
BEA_TRANSLATIONS = {
    "GDP": ("美國 GDP", "high", ["S&P 500", "美債", "美元", "台股"]),
    "Gross Domestic Product": ("美國 GDP", "high", ["S&P 500", "美債", "美元", "台股"]),
    "Personal Income and Outlays": ("美國個人所得與支出／PCE", "high", ["NASDAQ", "美債", "美元", "黃金"]),
    "U.S. International Trade in Goods and Services": ("美國貿易收支", "medium", ["美元", "美債", "航運"]),
    "Corporate Profits": ("美國企業獲利", "medium", ["S&P 500", "NASDAQ"]),
}

MATERIAL_CLASSIFIERS = [
    (re.compile(r"法說|法人說明會|業績說明會"), "investor-conference", "investor-conference", "corporate"),
    (re.compile(r"現金股利.{0,24}(?:發放日|支付日)|(?:發放日|支付日).{0,24}現金股利|收益分配.{0,24}發放"), "dividend-payment", "dividend-payment", "dividend"),
    (re.compile(r"股東會|股東常會|股東臨時會"), "shareholder-meeting", "shareholder-meeting", "corporate"),
    (re.compile(r"財務報告|財報|合併財務報表|季報|年度財務|營運成果"), "earnings", "financial-report", "earnings"),
    (re.compile(r"除權|除息|配息基準日|收益分配"), "ex-dividend", "ex-dividend", "dividend"),
    (re.compile(r"減資|增資|合併|分割|股份轉換|下市|終止上市|更名|公開收購"), "corporate-action", "corporate-action", "corporate"),
]

@dataclass
class SourceResult:
    key: str
    name: str
    url: str
    origins: tuple[str, ...]
    events: list[dict[str, Any]]
    message: str = ""


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
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


def at_taipei(day: date, hour: int = 9, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=TAIPEI)


def parse_number(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("$", "").rstrip("%")
    if not text or text in {"-", "--", "N/A", "尚未公告"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def fmt_number(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.4f}".rstrip("0").rstrip(".")


def parse_market_date(value: Any) -> date | None:
    text = clean(value).replace("年", "/").replace("月", "/").replace("日", "")
    compact = re.sub(r"[^0-9]", "", text)
    try:
        if len(compact) == 7:
            return date(int(compact[:3]) + 1911, int(compact[3:5]), int(compact[5:7]))
        if len(compact) == 8:
            return date(int(compact[:4]), int(compact[4:6]), int(compact[6:8]))
        parsed = date_parser.parse(text, fuzzy=False)
        return parsed.date()
    except (ValueError, TypeError, OverflowError):
        return None


def first_value(row: dict[str, Any], names: Iterable[str]) -> str:
    for name in names:
        value = clean(row.get(name))
        if value:
            return value
    return ""


def http_get(session: requests.Session, url: str, *, timeout: int = 20, attempts: int = 2, **kwargs: Any) -> requests.Response:
    if OFFLINE:
        raise RuntimeError("offline test mode")
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            headers = {**HEADERS, **kwargs.pop("headers", {})}
            response = session.get(url, headers=headers, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except Exception as exc:  # noqa: BLE001 - source failure must be isolated
            last_error = exc
            if attempt + 1 < attempts:
                time_module.sleep(1.0 + attempt)
    raise RuntimeError(str(last_error or "request failed"))


def http_json(session: requests.Session, url: str) -> Any:
    return http_get(session, url).json()


def make_event(
    *, event_id: str, tracking_key: str, title: str, start: datetime,
    category: str, event_type: str, event_group: str, region: str,
    impact: str, description: str, market_effect: str,
    source_name: str, source_url: str, origin: str,
    all_day: bool = False, assets: list[str] | None = None,
    tags: list[str] | None = None, **extra: Any,
) -> dict[str, Any]:
    row = {
        "id": event_id,
        "tracking_key": tracking_key,
        "title": clean(title),
        "start": iso_taipei(start),
        "local_date": start.astimezone(TAIPEI).date().isoformat(),
        "category": category,
        "event_type": event_type,
        "event_group": event_group,
        "region": region,
        "impact": impact,
        "description": clean(description),
        "market_effect": clean(market_effect),
        "source_name": source_name,
        "source_url": source_url,
        "origin": origin,
        "all_day": all_day,
        "assets": assets or [],
        "tags": tags or [],
        "verification_status": "confirmed",
        "time_status": "confirmed",
    }
    row.update({key: value for key, value in extra.items() if value not in (None, "", [], {})})
    return row


def translate(summary: str, mapping: dict[str, tuple[str, str, list[str]]]):
    for needle, value in mapping.items():
        if needle.lower() in summary.lower():
            return value
    return None


def unfold_ics(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw.startswith((" ", "\t")) and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    return lines


def parse_ics_datetime(key: str, value: str) -> datetime:
    value = value.strip()
    if re.fullmatch(r"\d{8}", value):
        return datetime.strptime(value, "%Y%m%d").replace(hour=8, minute=30, tzinfo=NEW_YORK).astimezone(TAIPEI)
    if value.endswith("Z"):
        return datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(TAIPEI)
    parsed = datetime.strptime(value, "%Y%m%dT%H%M%S")
    tzid_match = re.search(r"TZID=([^;:]+)", key)
    zone = ZoneInfo(tzid_match.group(1)) if tzid_match else NEW_YORK
    return parsed.replace(tzinfo=zone).astimezone(TAIPEI)


def _bls_event(summary: str, start: datetime, uid: str) -> dict[str, Any] | None:
    translated = translate(summary, BLS_TRANSLATIONS)
    if not translated or not ARCHIVE_START_DT <= start <= NOW + timedelta(days=370):
        return None
    title, impact, assets = translated
    key = f"bls|{clean(uid)}"
    return make_event(
        event_id=stable_id("bls", key, start.date()), tracking_key=key, title=title, start=start,
        category="macro", event_type="economic-release", event_group="macro", region="US", impact=impact,
        description=f"BLS 發布 {summary}。", market_effect="數據與市場預期的落差可能改變聯準會政策、美債殖利率、美元與股票評價。",
        source_name="U.S. BLS", source_url=BLS_HTML_URL, origin="bls", assets=assets, tags=["BLS", summary],
        date_basis="BLS official release schedule",
    )


def fetch_bls_html(session: requests.Session) -> list[dict[str, Any]]:
    soup = BeautifulSoup(http_get(session, BLS_HTML_URL).text, "html.parser")
    events: list[dict[str, Any]] = []
    for row in soup.select("tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in row.select("th,td")]
        if len(cells) < 2:
            continue
        joined = " | ".join(cells)
        date_match = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,\s*(20\d{2}))?", joined, re.I)
        time_match = re.search(r"(\d{1,2}:\d{2})\s*(AM|PM)", joined, re.I)
        if not date_match or not time_match:
            continue
        year = int(date_match.group(3) or NOW.year)
        raw_date = f"{date_match.group(1)} {date_match.group(2)}, {year} {time_match.group(1)} {time_match.group(2)}"
        try:
            start = date_parser.parse(raw_date).replace(tzinfo=NEW_YORK).astimezone(TAIPEI)
        except Exception:
            continue
        summary = next((cell for cell in reversed(cells) if translate(cell, BLS_TRANSLATIONS)), "")
        event = _bls_event(summary, start, f"html|{summary}|{start.date()}") if summary else None
        if event: events.append(event)
    if not events:
        text = soup.get_text(" ", strip=True)
        pattern = re.compile(r"(?:Monday|Tuesday|Wednesday|Thursday|Friday)?[,]?\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})\s+(\d{1,2}:\d{2})\s*(AM|PM)\s+(.{3,120}?)(?=(?:Monday|Tuesday|Wednesday|Thursday|Friday|January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}|$)", re.I)
        for match in pattern.finditer(text):
            summary = clean(match.group(6))
            if not translate(summary, BLS_TRANSLATIONS): continue
            start = date_parser.parse(f"{match.group(1)} {match.group(2)}, {match.group(3)} {match.group(4)} {match.group(5)}").replace(tzinfo=NEW_YORK).astimezone(TAIPEI)
            event = _bls_event(summary, start, f"html-text|{summary}|{start.date()}")
            if event: events.append(event)
    return list({row["id"]: row for row in events}.values())


def fetch_bls(session: requests.Session) -> SourceResult:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        lines = unfold_ics(http_get(session, BLS_URL).text)
        blocks: list[dict[str, str]] = []; current: dict[str, str] | None = None
        for line in lines:
            if line == "BEGIN:VEVENT": current = {}
            elif line == "END:VEVENT" and current is not None: blocks.append(current); current = None
            elif current is not None and ":" in line:
                key, value = line.split(":", 1); current[key] = value
        for block in blocks:
            summary = next((v for k, v in block.items() if k.startswith("SUMMARY")), "")
            dt_pair = next(((k, v) for k, v in block.items() if k.startswith("DTSTART")), None)
            if not dt_pair: continue
            event = _bls_event(summary, parse_ics_datetime(*dt_pair), next((v for k, v in block.items() if k.startswith("UID")), summary))
            if event: events.append(event)
    except Exception as exc:
        errors.append(str(exc))
    if not events:
        try: events = fetch_bls_html(session)
        except Exception as exc: errors.append(str(exc))
    if not events: raise RuntimeError("BLS official calendars returned no recognized events: " + "; ".join(errors[:2]))
    return SourceResult("bls", "U.S. BLS release calendar", BLS_HTML_URL, ("bls",), events, "ICS with official annual HTML fallback")

def fetch_bea(session: requests.Session) -> SourceResult:
    errors=[];events=[]
    for url in (BEA_URL, BEA_FULL_URL):
        try:
            soup = BeautifulSoup(http_get(session, url).text, "html.parser")
            candidates=[]
            for row in soup.select("tr"):
                cells=[clean(cell.get_text(" ",strip=True)) for cell in row.select("th,td")]
                if len(cells)>=2:candidates.append(" | ".join(cells))
            candidates.append(soup.get_text(" ",strip=True))
            pattern = re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,\s*(20\d{2}))?\s+(\d{1,2}:\d{2})\s*(AM|PM)\s+(?:N\s*ews|D\s*ata|News|Data)?\s*[|:-]*\s*(.{3,180}?)(?=(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}|$)",re.I)
            for content in candidates:
                for match in pattern.finditer(content):
                    raw_title=clean(match.group(6)).strip(" |-")
                    translated=translate(raw_title,BEA_TRANSLATIONS)
                    if not translated:continue
                    year=int(match.group(3) or NOW.year)
                    start=date_parser.parse(f"{match.group(1)} {match.group(2)}, {year} {match.group(4)} {match.group(5)}").replace(tzinfo=NEW_YORK).astimezone(TAIPEI)
                    if not ARCHIVE_START_DT<=start<=NOW+timedelta(days=370):continue
                    title,impact,assets=translated;key=f"bea|{raw_title.lower()}"
                    events.append(make_event(event_id=stable_id("bea",key,start.date()),tracking_key=key,title=title,start=start,category="macro",event_type="economic-release",event_group="macro",region="US",impact=impact,description=f"BEA 發布 {raw_title}。",market_effect="成長、所得、消費與通膨資料可能改變美債、美元及風險資產定價。",source_name="U.S. BEA",source_url=url,origin="bea",assets=assets,tags=["BEA",raw_title],date_basis="BEA official release schedule"))
            if events:break
        except Exception as exc:errors.append(str(exc))
    events=list({row["id"]:row for row in events}.values())
    if not events:raise RuntimeError("BEA official schedules returned no recognized events: "+"; ".join(errors[:2]))
    return SourceResult("bea","U.S. BEA release schedule",BEA_URL,("bea",),events,"primary and full official schedule parsers")


def fetch_fomc(session: requests.Session) -> SourceResult:
    soup = BeautifulSoup(http_get(session, FOMC_URL).text, "html.parser")
    lines = [clean(value) for value in soup.get_text("\n", strip=True).splitlines() if clean(value)]
    active = False
    month_value: int | None = None
    events: list[dict[str, Any]] = []
    month_names = {name: index for index, name in enumerate((
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ), start=1)}
    for line in lines:
        if re.fullmatch(r"2026 FOMC Meetings", line, re.I):
            active = True; month_value = None; continue
        if active and re.fullmatch(r"20\d{2} FOMC Meetings", line, re.I): break
        if not active: continue
        if line in month_names: month_value = month_names[line]; continue
        if month_value is None: continue
        match = re.fullmatch(r"(\d{1,2})(?:-(\d{1,2}))?\*?", line)
        if not match: continue
        decision_day = int(match.group(2) or match.group(1))
        try: start = datetime(2026, month_value, decision_day, 14, 0, tzinfo=NEW_YORK).astimezone(TAIPEI)
        except ValueError: month_value = None; continue
        if not ARCHIVE_START_DT <= start <= NOW + timedelta(days=370): month_value = None; continue
        events.append(make_event(
            event_id=stable_id("fomc", start.date()), tracking_key=f"fomc|2026|{month_value:02d}",
            title="美國聯準會 FOMC 利率決策", start=start, category="macro",
            event_type="central-bank-decision", event_group="macro", region="US", impact="high",
            description="聯邦公開市場委員會公布利率決議與政策聲明。",
            market_effect="利率路徑與政策措辭可能影響美債殖利率、美元、美股及全球風險資產。",
            source_name="Federal Reserve FOMC calendar", source_url=FOMC_URL, origin="fomc",
            assets=["S&P 500", "NASDAQ", "美債", "美元", "台股"], tags=["FOMC", "聯準會", "利率決策"],
            date_basis="Federal Reserve official meeting calendar",
        ))
        month_value = None
    if not events: raise RuntimeError("FOMC calendar returned no 2026 meetings")
    return SourceResult("fomc", "Federal Reserve FOMC calendar", FOMC_URL, ("fomc",), events)

def tw_asset_type(symbol: str, name: str) -> tuple[str, str]:
    is_etf = symbol.startswith("00") or "ETF" in name.upper() or "基金" in name
    return ("etf", "ETF") if is_etf else ("stock", "股票")


def make_exdiv_event(market: str, symbol: str, name: str, day: date, kind: str, cash: float | None,
                     stock_ratio: float | None, source_name: str, source_url: str, origin: str) -> dict[str, Any]:
    asset_class, type_label = tw_asset_type(symbol, name)
    label = "除權息" if "權" in kind and "息" in kind else ("除權" if "權" in kind else "除息")
    category = "etf-distribution" if asset_class == "etf" else "ex-dividend"
    tracking = f"{origin}|{symbol}|{label}"
    amount = f"（{fmt_number(cash)} 元）" if cash not in (None, 0) else ""
    details = []
    if cash not in (None, 0): details.append(f"現金 {fmt_number(cash)} 元")
    if stock_ratio not in (None, 0): details.append(f"股票股利率 {fmt_number(stock_ratio)}")
    return make_event(
        event_id=stable_id("tw-exdiv", tracking, day), tracking_key=tracking,
        title=f"{symbol} {name} {label}{amount}", start=at_taipei(day), category=category,
        event_type=category, event_group="dividend", region="TW", impact="medium" if asset_class == "etf" else "low",
        description=f"{market} {type_label}的{label}日。{'、'.join(details) if details else '實際金額以交易所公告為準。'}",
        market_effect="除權息會調整參考價；ETF 配息也會使淨值與市價反映分配金額。",
        source_name=source_name, source_url=source_url, origin=origin, all_day=True,
        assets=[symbol, name, type_label], tags=[label, market, type_label], market=market,
        symbol=symbol, asset_name=name, asset_id=f"TW:{symbol}", asset_class=asset_class,
        cash_dividend=cash, stock_dividend_ratio=stock_ratio, currency="TWD", ex_date=day.isoformat(),
    )


def fetch_twse_exdiv(session: requests.Session) -> SourceResult:
    rows = http_json(session, TWSE_EXDIV_URL)
    events = []
    for row in rows if isinstance(rows, list) else []:
        day, symbol = parse_market_date(row.get("Date")), clean(row.get("Code"))
        if day and symbol:
            events.append(make_exdiv_event("TWSE", symbol, clean(row.get("Name")), day, clean(row.get("Exdividend")),
                parse_number(row.get("CashDividend")), parse_number(row.get("StockDividendRatio")),
                "TWSE 上市股票除權除息預告表", TWSE_EXDIV_URL, "twse-exdiv"))
    return SourceResult("twse-exdiv", "TWSE listed ex-right/ex-dividend", TWSE_EXDIV_URL, ("twse-exdiv",), events)


def fetch_tpex_exdiv(session: requests.Session) -> SourceResult:
    rows = http_json(session, TPEX_EXDIV_URL)
    events = []
    for row in rows if isinstance(rows, list) else []:
        day = parse_market_date(row.get("ExRrightsExDividendDate"))
        symbol = clean(row.get("SecuritiesCompanyCode"))
        if day and symbol:
            events.append(make_exdiv_event("TPEX", symbol, clean(row.get("CompanyName")), day,
                clean(row.get("ExRrightsExDividend")), parse_number(row.get("CashDividend")),
                parse_number(row.get("StockDividendRatio")), "TPEx 上櫃股票除權除息預告表",
                TPEX_EXDIV_URL, "tpex-exdiv"))
    return SourceResult("tpex-exdiv", "TPEx OTC ex-right/ex-dividend", TPEX_EXDIV_URL, ("tpex-exdiv",), events)



def _row_lookup(row: dict[str, Any], *needles: str) -> Any:
    for key, value in row.items():
        normalized = clean(key).lower()
        if any(needle.lower() in normalized for needle in needles):
            return value
    return None


def parse_twse_exdiv_history_payload(payload: Any, source_url: str = TWSE_EXDIV_HISTORY_URL) -> list[dict[str, Any]]:
    """Parse TWSE TWT49U historical ex-right/ex-dividend calculation rows."""
    fields: list[str] = []
    raw_rows: list[Any] = []
    if isinstance(payload, dict):
        fields = [clean(value) for value in (payload.get("fields") or payload.get("fields9") or [])]
        raw_rows = payload.get("data") or payload.get("data9") or payload.get("items") or []
    elif isinstance(payload, list):
        raw_rows = payload
    events: list[dict[str, Any]] = []
    for raw in raw_rows:
        if isinstance(raw, dict):
            row = raw
        elif isinstance(raw, (list, tuple)):
            row = {fields[index] if index < len(fields) else str(index): value for index, value in enumerate(raw)}
        else:
            continue
        day = parse_market_date(_row_lookup(row, "日期", "date"))
        symbol = clean(_row_lookup(row, "股票代號", "證券代號", "code"))
        name = clean(_row_lookup(row, "股票名稱", "證券名稱", "name"))
        if not day or day < ARCHIVE_START or day > NOW.date() or not symbol:
            continue
        cash = parse_number(_row_lookup(row, "息值", "現金股利", "cash"))
        stock = parse_number(_row_lookup(row, "權值", "股票股利", "stock"))
        kind_text = clean(_row_lookup(row, "除權息", "權息別", "type"))
        if not kind_text:
            kind_text = "除權息" if stock not in (None, 0) and cash not in (None, 0) else "除權" if stock not in (None, 0) else "除息"
        events.append(make_exdiv_event(
            "TWSE", symbol, name, day, kind_text, cash, stock,
            "TWSE 除權除息計算結果表", source_url, "twse-exdiv-history",
        ))
    return events


def fetch_twse_exdiv_history(session: requests.Session) -> SourceResult:
    events: list[dict[str, Any]] = []
    errors: list[str] = []
    month = date(ARCHIVE_START.year, ARCHIVE_START.month, 1)
    end = date(NOW.year, NOW.month, 1)
    while month <= end:
        try:
            response = http_get(session, TWSE_EXDIV_HISTORY_URL, params={"response": "json", "date": month.strftime("%Y%m01")})
            events.extend(parse_twse_exdiv_history_payload(response.json(), response.url))
        except Exception as exc:
            errors.append(f"{month:%Y-%m}: {exc}")
        month = date(month.year + (month.month == 12), 1 if month.month == 12 else month.month + 1, 1)
    events = list({row["id"]: row for row in events}.values())
    if not events:
        raise RuntimeError("TWSE historical ex-dividend returned no recognized rows: " + "; ".join(errors[:3]))
    return SourceResult(
        "twse-exdiv-history", "TWSE historical ex-right/ex-dividend", TWSE_EXDIV_HISTORY_URL,
        ("twse-exdiv-history",), events, f"{len(events)} historical events since 2026-01-01",
    )


def parse_tpex_exdiv_history_payload(payload: Any, source_url: str = TPEX_EXDIV_HISTORY_URL) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in payload if isinstance(payload, list) else []:
        if not isinstance(row, dict):
            continue
        day = parse_market_date(first_value(row, [
            "ExRrightsExDividendDate", "Date", "資料日期", "除權息日期", "除權除息日期",
        ]))
        symbol = first_value(row, ["SecuritiesCompanyCode", "Code", "證券代號", "股票代號"])
        name = first_value(row, ["CompanyName", "Name", "證券名稱", "股票名稱"])
        if not day or day < ARCHIVE_START or day > NOW.date() or not symbol:
            continue
        kind = first_value(row, ["ExRrightsExDividend", "Type", "除權息", "權息別"]) or "除息"
        cash = parse_number(first_value(row, ["CashDividend", "CashDividendValue", "息值", "現金股利"]))
        stock = parse_number(first_value(row, ["StockDividendRatio", "StockDividendValue", "權值", "股票股利"]))
        events.append(make_exdiv_event(
            "TPEX", clean(symbol), clean(name), day, clean(kind), cash, stock,
            "TPEx 上櫃除權除息計算結果表", source_url, "tpex-exdiv-history",
        ))
    return events


def fetch_tpex_exdiv_history(session: requests.Session) -> SourceResult:
    payload = http_json(session, TPEX_EXDIV_HISTORY_URL)
    events = parse_tpex_exdiv_history_payload(payload)
    if not events:
        raise RuntimeError("TPEx historical ex-dividend returned no recognized rows")
    return SourceResult(
        "tpex-exdiv-history", "TPEx historical ex-right/ex-dividend", TPEX_EXDIV_HISTORY_URL,
        ("tpex-exdiv-history",), events, f"{len(events)} historical events since 2026-01-01",
    )

def dividend_total(row: dict[str, Any], needle: str) -> float:
    total = 0.0
    for key, value in row.items():
        if needle in key and ("元/股" in key or "每股" in key):
            total += parse_number(value) or 0.0
    return total


def dividend_company_identity(row: dict[str, Any]) -> tuple[str, str]:
    """Read company identity from both split and combined MOPS/TPEx schemas."""
    symbol = first_value(row, ["公司代號", "CompanyCode", "SecuritiesCompanyCode", "Code"])
    name = first_value(row, ["公司名稱", "CompanyName", "Name"])
    if symbol:
        return symbol, name
    combined = first_value(row, ["公司代號名稱", "公司代號及名稱", "CompanyCodeName", "SecuritiesCompanyCodeName"])
    match = re.match(r"^\s*([0-9A-Za-z]{4,8})\s*[-－—:：]?\s*(.*?)\s*$", combined)
    if not match:
        return "", name
    return match.group(1), name or clean(match.group(2))


def parse_dividend_plans(rows: Any, market: str, source_url: str, origin: str) -> list[dict[str, Any]]:
    events = []
    if not isinstance(rows, list):
        return events
    for row in rows:
        symbol, name = dividend_company_identity(row)
        if not symbol:
            continue
        period = first_value(row, ["股利所屬年(季)度", "股利年度", "DividendYear"])
        term = first_value(row, ["期別", "股利期別", "DividendPeriod"])
        if term and term not in period:
            period = clean(f"{period} {term}")
        shareholder_day = parse_market_date(first_value(row, ["股東會日期", "ShareholdersMeetingDate"]))
        decision_day = parse_market_date(first_value(row, [
            "董事會決議通過股利分派日", "董事會（擬議）股利分派日",
            "董事會股利分派日", "BoardMeetingDate",
        ]))
        cash, stock = dividend_total(row, "現金"), dividend_total(row, "配股")
        if shareholder_day and ARCHIVE_START <= shareholder_day <= NOW.date() + timedelta(days=370):
            tracking = f"{origin}|{symbol}|shareholder-meeting|{period}"
            events.append(make_event(
                event_id=stable_id("tw-shareholder", tracking, shareholder_day), tracking_key=tracking,
                title=f"{symbol} {name} 股東會確認股利案", start=at_taipei(shareholder_day),
                category="shareholder-meeting", event_type="shareholder-meeting", event_group="corporate",
                region="TW", impact="low", description=f"股東會預定確認{period or ''}財報與盈餘分派等議案。",
                market_effect="股東會通常是已公告股利案的正式確認階段，仍需留意議案是否調整。",
                source_name=f"{market} 股利分派資料", source_url=source_url, origin=origin,
                all_day=True, assets=[symbol, name], tags=["股東會", "股利"], market=market,
                symbol=symbol, asset_name=name, asset_id=f"TW:{symbol}", cash_dividend=cash or None,
                stock_dividend=stock or None, currency="TWD", fiscal_period=period,
            ))
        if decision_day and ARCHIVE_START <= decision_day <= NOW.date() + timedelta(days=370):
            tracking = f"{origin}|{symbol}|dividend-decision|{period}"
            events.append(make_event(
                event_id=stable_id("tw-dividend-plan", tracking, decision_day), tracking_key=tracking,
                title=f"{symbol} {name} 股利方案決議", start=at_taipei(decision_day),
                category="dividend-decision", event_type="dividend-decision", event_group="dividend",
                region="TW", impact="medium" if cash or stock else "low",
                description=f"公司公布{period or ''}股利方案。現金股利 {fmt_number(cash)} 元／股；股票股利 {fmt_number(stock)} 元／股。",
                market_effect="股利方案影響現金殖利率、保留盈餘與市場對公司資本配置的評價。",
                source_name=f"{market} 股利分派資料", source_url=source_url, origin=origin,
                all_day=True, assets=[symbol, name], tags=["股利方案", period], market=market,
                symbol=symbol, asset_name=name, asset_id=f"TW:{symbol}", cash_dividend=cash or None,
                stock_dividend=stock or None, currency="TWD", fiscal_period=period,
            ))
    return events


def fetch_twse_dividend_plans(session: requests.Session) -> SourceResult:
    events = parse_dividend_plans(http_json(session, TWSE_DIVIDEND_PLAN_URL), "TWSE", TWSE_DIVIDEND_PLAN_URL, "twse-dividend-plan")
    return SourceResult("twse-dividend-plan", "TWSE/MOPS listed dividend plans", TWSE_DIVIDEND_PLAN_URL, ("twse-dividend-plan",), events)


def fetch_tpex_dividend_plans(session: requests.Session) -> SourceResult:
    events = parse_dividend_plans(http_json(session, TPEX_DIVIDEND_PLAN_URL), "TPEX", TPEX_DIVIDEND_PLAN_URL, "tpex-dividend-plan")
    return SourceResult("tpex-dividend-plan", "TPEx/MOPS OTC dividend plans", TPEX_DIVIDEND_PLAN_URL, ("tpex-dividend-plan",), events)


def extract_candidate_dates(text: str) -> list[date]:
    tokens = re.findall(r"(?<!\d)(?:\d{3}|\d{4})[年/.-]\d{1,2}[月/.-]\d{1,2}日?(?!\d)", text)
    values = []
    for token in tokens:
        parsed = parse_market_date(token)
        if parsed and ARCHIVE_START <= parsed <= NOW.date() + timedelta(days=370):
            values.append(parsed)
    return sorted(set(values))


DATE_TOKEN_RE = re.compile(r"(?<!\d)(?:\d{3}|\d{4})[年/.-]\d{1,2}[月/.-]\d{1,2}日?(?!\d)")

def labeled_date(text: str, patterns: list[str]) -> date | None:
    for pattern in patterns:
        match = re.search(pattern + r"[^0-9]{0,20}(?P<date>(?:\d{3}|\d{4})[年/.-]\d{1,2}[月/.-]\d{1,2}日?)", text, re.I)
        if match:
            parsed = parse_market_date(match.group("date"))
            if parsed and ARCHIVE_START <= parsed <= NOW.date()+timedelta(days=370): return parsed
    return None

def choose_material_target_date(subject: str, event_type: str, announcement_day: date) -> tuple[date | None, str]:
    rules={
      "financial-report":[r"提報董事會或經董事會決議日期",r"董事會決議日期",r"審計委員會通過日期"],
      "investor-conference":[r"法人說明會日期",r"召開法人說明會日期",r"召開日期",r"舉辦日期"],
      "dividend-payment":[r"現金股利發放日",r"股利發放日",r"發放日",r"支付日"],
      "ex-dividend":[r"除權息交易日",r"除息交易日",r"除權交易日",r"除權息日期"],
      "shareholder-meeting":[r"股東會日期",r"開會日期",r"股東常會日期"],
      "corporate-action":[r"合併基準日",r"減資基準日",r"增資基準日",r"股份轉換基準日",r"生效日",r"董事會決議日期",r"決議日期"],
    }
    selected=labeled_date(subject,rules.get(event_type,[]))
    if selected:return selected,"explicit-labeled-date"
    # Financial reports and decisions are announcements; the reporting period
    # start/end must never become the event date.
    if event_type in {"financial-report","corporate-action"}:return announcement_day,"official-announcement-date"
    return None,"missing-exact-event-date"


def normalized_subject(subject: str) -> str:
    without_dates = re.sub(r"(?<!\d)(?:\d{3}|\d{4})[年/.-]\d{1,2}[月/.-]\d{1,2}日?(?!\d)", "<DATE>", subject)
    return clean(without_dates).lower()[:180]


def concise_material_title(symbol: str, name: str, subject: str, event_type: str, target_day: date) -> str:
    prefix = clean(f"{symbol} {name}")
    text = clean(subject)
    day_label = f"{target_day.month}/{target_day.day}"
    if event_type == "investor-conference":
        return f"{prefix}｜{day_label} 法人說明會"
    if event_type == "financial-report":
        return f"{prefix}｜公布財務報告"
    if event_type == "dividend-payment":
        return f"{prefix}｜{day_label} 股利發放"
    if event_type == "ex-dividend":
        amount = re.search(r"(?:每股(?:配發)?|現金股利)[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)\s*元", text)
        return f"{prefix}｜{day_label} 除權息" + (f"，每股 {amount.group(1)} 元" if amount else "")
    if event_type == "corporate-action":
        for label, pattern in [
            ("現金增資", r"現金增資"), ("減資", r"減資"), ("合併", r"合併"),
            ("公開收購", r"公開收購"), ("股份轉換", r"股份轉換"), ("公司分割", r"分割"),
            ("終止上市櫃", r"下市|終止上市|終止上櫃"),
        ]:
            if re.search(pattern, text):
                shares = re.search(r"(?:發行(?:新股|總股數)|發行股數)[^0-9]{0,12}([0-9][0-9,]*)", text)
                return f"{prefix}｜{label}" + (f" {shares.group(1)} 股" if shares and label == "現金增資" else "")
    first = re.split(r"[。；;]", text, maxsplit=1)[0]
    first = re.sub(r"^\s*\d+[.)、．]\s*", "", first).strip()
    return f"{prefix}｜{first[:70]}"


def parse_material(rows: Any, market: str, source_url: str, origin: str) -> list[dict[str, Any]]:
    events = []
    if not isinstance(rows, list):
        return events
    for row in rows:
        text = " ".join(clean(value) for value in row.values())
        classified = next((value for pattern, *value in MATERIAL_CLASSIFIERS if pattern.search(text)), None)
        if not classified:
            continue
        category, event_type, group = classified
        symbol = first_value(row, ["公司代號", "CompanyCode", "SecuritiesCompanyCode", "Code"])
        name = first_value(row, ["公司名稱", "CompanyName", "Name"])
        subject = first_value(row, ["主旨", "Subject", "說明", "Description"]) or text[:220]
        if not symbol:
            continue
        announcement_day = parse_market_date(first_value(row, ["發言日期", "出表日期", "Date"]))
        if not announcement_day:
            continue  # source announcement date missing; never substitute today
        target_day, date_basis = choose_material_target_date(subject, event_type, announcement_day)
        if not target_day:
            continue  # exact event date unavailable; do not publish a guessed period date
        tracking = f"{origin}|{symbol}|{event_type}|{normalized_subject(subject)}"
        events.append(make_event(
            event_id=stable_id("tw-material-date", tracking, target_day), tracking_key=tracking,
            title=concise_material_title(symbol, name, subject, event_type, target_day), start=at_taipei(target_day), category=category,
            event_type=event_type, event_group=group, region="TW",
            impact="medium" if category in {"earnings", "corporate-action", "dividend-payment"} else "low",
            description=subject, market_effect="公司重大訊息可能影響個股評價；請閱讀官方完整說明與附件。",
            source_name=f"{market} 每日重大訊息", source_url=source_url, origin=origin,
            all_day=True, assets=[symbol, name], tags=[category, "重大訊息", "日期已確認"],
            market=market, symbol=symbol, asset_name=name, asset_id=f"TW:{symbol}",
            source_published_at=iso_taipei(at_taipei(announcement_day)), target_date=target_day.isoformat(), date_basis=date_basis,
        ))
    return events


def fetch_twse_material(session: requests.Session) -> SourceResult:
    events = parse_material(http_json(session, TWSE_MATERIAL_URL), "TWSE", TWSE_MATERIAL_URL, "twse-material")
    return SourceResult("twse-material", "TWSE listed daily material information", TWSE_MATERIAL_URL, ("twse-material",), events)


def fetch_tpex_material(session: requests.Session) -> SourceResult:
    events = parse_material(http_json(session, TPEX_MATERIAL_URL), "TPEX", TPEX_MATERIAL_URL, "tpex-material")
    return SourceResult("tpex-material", "TPEx OTC daily material information", TPEX_MATERIAL_URL, ("tpex-material",), events)


def parse_start(row: dict[str, Any]) -> datetime | None:
    try:
        value = date_parser.parse(str(row.get("start") or ""))
        if value.tzinfo is None:
            value = value.replace(tzinfo=TAIPEI)
        return value.astimezone(TAIPEI)
    except Exception:  # noqa: BLE001
        return None


def fallback_tracking_key(row: dict[str, Any]) -> str:
    if row.get("tracking_key"):
        return str(row["tracking_key"])
    symbol = clean(row.get("symbol") or "")
    base = clean(row.get("title") or "").lower()
    return f"legacy|{clean(row.get('origin'))}|{symbol}|{base[:160]}"


DATE_ALERT_SCHEDULE_ORIGINS = {"bls", "bea", "fomc", "twse-exdiv", "tpex-exdiv"}
DATE_ALERT_TYPES = {"economic-release", "central-bank-decision", "ex-dividend", "ex-right", "investor-conference", "shareholder-meeting", "dividend-payment"}


def parse_optional_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = date_parser.parse(str(value))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TAIPEI)
        return parsed.astimezone(TAIPEI)
    except Exception:  # noqa: BLE001
        return None


def date_alert_eligible(row: dict[str, Any]) -> bool:
    origin = clean(row.get("origin"))
    event_type = clean(row.get("event_type")).lower()
    date_basis = clean(row.get("date_basis")).lower()
    return origin in DATE_ALERT_SCHEDULE_ORIGINS or event_type in DATE_ALERT_TYPES or date_basis == "explicit-labeled-date"


def announcement_candidate(row: dict[str, Any], old_state: dict[str, Any] | None, today: date) -> tuple[str, str | None] | None:
    """Return a trustworthy date-announcement candidate.

    A row merely appearing in a newly expanded historical feed is not a new
    announcement.  A reused series key whose prior occurrence already passed
    represents a new occurrence, not a reschedule.
    """
    if not date_alert_eligible(row):
        return None
    current = parse_start(row)
    if current is None:
        return None
    published = parse_optional_datetime(row.get("source_published_at"))
    if old_state is None:
        if current.date() < today:
            return None
        if published is not None and published.date() < today - timedelta(days=1):
            return None
        return "new-date", None

    previous = parse_optional_datetime(old_state.get("start"))
    if previous is None or previous == current:
        return None
    if previous.date() >= today:
        return "date-changed", previous.isoformat(timespec="seconds")
    if current.date() >= today:
        # Same source/title reused for the next occurrence after the previous
        # one has already happened.  This is a newly published occurrence.
        if published is not None and published.date() < today - timedelta(days=1):
            return None
        return "new-date", None
    return None


def announcement_semantically_valid(row: dict[str, Any], today: date) -> bool:
    if clean(row.get("announcement_kind")) not in {"new-date", "date-changed"}:
        return False
    announced = parse_optional_datetime(row.get("announced_at"))
    current = parse_start(row)
    if announced is None or current is None or announced.date() != today or current.date() < today:
        return False
    if row.get("announcement_kind") == "date-changed":
        previous = parse_optional_datetime(row.get("previous_start"))
        if previous is None or previous.date() < today:
            return False
        # Large jumps are almost always a reused periodic key or parser churn,
        # not an actual reschedule.  Preserve a generous six-month window.
        if abs((current - previous).total_seconds()) > 183 * 86400:
            return False
    return date_alert_eligible(row)


def source_snapshot(result: SourceResult, previous_source: dict[str, Any] | None, status: str, message: str) -> dict[str, Any]:
    previous_source = previous_source or {}
    return {
        "key": result.key,
        "name": result.name,
        "status": status,
        "last_checked": NOW.isoformat(timespec="seconds"),
        "last_success": NOW.isoformat(timespec="seconds") if status == "ok" else previous_source.get("last_success"),
        "url": result.url,
        "message": message,
        "event_count": len(result.events),
    }


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    previous = load_json(EVENTS_PATH, {"events": [], "sources": []})
    manual_payload = load_json(MANUAL_PATH, [])
    manual = manual_payload if isinstance(manual_payload, list) else manual_payload.get("events", [])
    previous_events = previous.get("events") or []
    previous_sources = {str(row.get("key") or row.get("name")): row for row in previous.get("sources") or []}
    state_payload = load_json(STATE_PATH, {"initialized": False, "events": {}})
    state_initialized = bool(state_payload.get("initialized"))
    initialized_origins = set(state_payload.get("initialized_origins") or [])
    prior_state: dict[str, dict[str, Any]] = state_payload.get("events") or {}
    previous_by_tracking = {fallback_tracking_key(row): row for row in previous_events}

    fetchers: list[Callable[[requests.Session], SourceResult]] = [
        fetch_bls, fetch_bea, fetch_fomc, fetch_twse_exdiv, fetch_tpex_exdiv,
        fetch_twse_exdiv_history, fetch_tpex_exdiv_history,
        fetch_twse_dividend_plans, fetch_tpex_dividend_plans,
        fetch_twse_material, fetch_tpex_material,
    ]
    session = requests.Session()
    refreshed_origins: set[str] = set()
    official_events: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    successful_origins: set[str] = set()
    failed_origins: set[str] = set()

    for fetcher in fetchers:
        placeholder = SourceResult(fetcher.__name__, fetcher.__name__, "", (), [])
        try:
            result = fetcher(session)
            refreshed_origins.update(result.origins)
            successful_origins.update(result.origins)
            official_events.extend(result.events)
            previous_source = previous_sources.get(result.key) or previous_sources.get(result.name)
            sources.append(source_snapshot(result, previous_source, "ok", result.message or f"{len(result.events)} verified events"))
        except Exception as exc:  # noqa: BLE001 - isolate each source
            key = fetcher.__name__.replace("fetch_", "").replace("_", "-")
            origins = (key,)
            mapping = {
                "twse-exdiv": ("twse-exdiv",), "tpex-exdiv": ("tpex-exdiv",),
                "twse-exdiv-history": ("twse-exdiv-history",), "tpex-exdiv-history": ("tpex-exdiv-history",),
                "twse-dividend-plans": ("twse-dividend-plan",), "tpex-dividend-plans": ("tpex-dividend-plan",),
                "twse-material": ("twse-material",), "tpex-material": ("tpex-material",),
                "bls": ("bls",), "bea": ("bea",), "fomc": ("fomc",),
            }
            origins = mapping.get(key, origins)
            failed_origins.update(origins)
            retained = [row for row in previous_events if clean(row.get("origin")) in origins]
            official_events.extend(retained)
            old = previous_sources.get(key) or next((s for s in previous_sources.values() if clean(s.get("key")) == key), None)
            result = SourceResult(key, clean(old.get("name")) if old else key, clean(old.get("url")) if old else "", origins, retained)
            sources.append(source_snapshot(result, old, "warning", f"{exc}; retained {len(retained)} last verified events"))

    # Keep events from sources outside this monitor and from failed monitored sources.
    monitored = successful_origins | failed_origins
    untouched = [row for row in previous_events if clean(row.get("origin")) not in monitored]
    rows = [*untouched, *official_events, *manual]
    cutoff, horizon = ARCHIVE_START_DT, NOW + timedelta(days=370)
    merged: dict[str, dict[str, Any]] = {}
    next_state: dict[str, dict[str, Any]] = dict(prior_state)
    next_initialized_origins = set(initialized_origins)
    announced_today = 0

    for raw in rows:
        start = parse_start(raw)
        if not start or not cutoff <= start <= horizon:
            continue
        row = {**raw, "start": start.isoformat(timespec="seconds"), "local_date": start.date().isoformat()}
        tracking = fallback_tracking_key(row)
        row["tracking_key"] = tracking
        origin = clean(row.get("origin"))
        old_event = previous_by_tracking.get(tracking)
        old_state = prior_state.get(tracking)

        if old_event:
            for field in ("announced_at", "announcement_kind", "announcement_status", "previous_start"):
                if old_event.get(field) and not row.get(field):
                    row[field] = old_event[field]

        is_successfully_refreshed = origin in successful_origins
        source_has_baseline = origin in initialized_origins
        if state_initialized and source_has_baseline and is_successfully_refreshed:
            candidate = announcement_candidate(row, old_state, NOW.date())
            if candidate:
                kind, previous_start = candidate
                row["announced_at"] = NOW.isoformat(timespec="seconds")
                row["announcement_kind"] = kind
                row["announcement_status"] = "date_changed_today" if kind == "date-changed" else "new_date_today"
                if previous_start:
                    row["previous_start"] = previous_start
                else:
                    row.pop("previous_start", None)
                row["_announcement_candidate"] = True

        if is_successfully_refreshed:
            next_initialized_origins.add(origin)
            next_state[tracking] = {
                "start": row["start"], "title": row.get("title"), "origin": origin,
                "last_seen_at": NOW.isoformat(timespec="seconds"),
            }
        row_id = str(row.get("id") or stable_id("event", tracking, row["start"]))
        row["id"] = row_id
        merged[row_id] = row

    # Remove duplicate records exposed by overlapping official/legacy feeds.  Dividend
    # events are unique by Taipei date + symbol + ex-right/ex-dividend kind; other
    # events are unique by Taipei date + group + symbol + normalized title.
    canonical: dict[str, dict[str, Any]] = {}
    for row in merged.values():
        start = parse_start(row)
        day = clean(row.get("local_date") or row.get("target_date") or row.get("ex_date"))[:10] or (start.date().isoformat() if start else clean(row.get("start"))[:10])
        group = clean(row.get("event_group") or row.get("category") or "event").lower()
        symbol = clean(row.get("symbol") or "").upper()
        title = clean(row.get("title") or "")
        if group == "dividend" or "dividend" in clean(row.get("category")).lower():
            kind = "ex-right" if "除權" in title else "ex-dividend"
            key = f"{day}|dividend|{symbol}|{kind}"
        else:
            title_without_amount = re.sub(r"[（(][^）)]*(?:元|%)[^）)]*[）)]", "", title)
            normalized = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", title_without_amount.lower())[:180]
            key = f"{day}|{group}|{symbol}|{normalized}"
        existing = canonical.get(key)
        if existing is None:
            canonical[key] = row
            continue
        # Prefer the richer, directly sourced record while retaining announcement metadata.
        score = lambda value: sum(bool(value.get(field)) for field in (
            "source_url", "source_name", "description", "market_effect", "announced_at", "cash_dividend"
        ))
        winner, loser = (row, existing) if score(row) > score(existing) else (existing, row)
        for field in ("announced_at", "announcement_kind", "announcement_status", "previous_start"):
            if loser.get(field) and not winner.get(field):
                winner[field] = loser[field]
        if loser.get("_announcement_candidate") or winner.get("_announcement_candidate"):
            winner["_announcement_candidate"] = True
        canonical[key] = winner

    # A parser/key migration can make a large fraction of one source look new.
    # Treat that as a baseline refresh instead of flooding the user with alerts.
    source_totals: dict[str, int] = {}
    source_candidates: dict[str, int] = {}
    for row in canonical.values():
        origin = clean(row.get("origin"))
        if origin in successful_origins:
            source_totals[origin] = source_totals.get(origin, 0) + 1
        if row.pop("_announcement_candidate", False):
            source_candidates[origin] = source_candidates.get(origin, 0) + 1
    suppressed_origins = {
        origin for origin, count in source_candidates.items()
        if count >= 25 and count / max(source_totals.get(origin, count), 1) >= 0.30
    }
    if suppressed_origins:
        for row in canonical.values():
            if clean(row.get("origin")) not in suppressed_origins:
                continue
            announced = parse_optional_datetime(row.get("announced_at"))
            if announced and announced.date() == NOW.date():
                for field in ("announced_at", "announcement_kind", "announcement_status", "previous_start"):
                    row.pop(field, None)

    # Clean up false positives that may already exist in the restored live branch
    # from an older release.  Only today's invalid alerts are removed; historical
    # audit metadata remains untouched.
    for row in canonical.values():
        announced = parse_optional_datetime(row.get("announced_at"))
        if announced and announced.date() == NOW.date() and not announcement_semantically_valid(row, NOW.date()):
            for field in ("announced_at", "announcement_kind", "announcement_status", "previous_start"):
                row.pop(field, None)

    events = sorted(canonical.values(), key=lambda row: (str(row.get("start")), str(row.get("title"))))
    if not events and previous_events:
        raise SystemExit("No events after refresh; previous verified archive was not replaced.")

    recent_cutoff = NOW - timedelta(hours=24)
    announced_today = sum(
        1 for row in events
        if (stamp := parse_optional_datetime(row.get("announced_at"))) and stamp.date() == NOW.date()
        and row.get("announcement_kind") in {"new-date", "date-changed"}
    )
    announced_recent = sum(
        1 for row in events
        if (stamp := parse_optional_datetime(row.get("announced_at"))) and stamp >= recent_cutoff
        and row.get("announcement_kind") in {"new-date", "date-changed"}
    )
    payload = {
        "metadata": {
            "version": "v11.4.31",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "timezone": "Asia/Taipei",
            "event_count": len(events),
            "announced_today_count": announced_today,
            "announced_recent_count": announced_recent,
            "state_initialized": True,
            "announcement_integrity": "strict-v11.4.31",
            "announcement_suppressed_origins": sorted(suppressed_origins),
            "source_ok_count": sum(1 for source in sources if source.get("status") == "ok"),
            "source_warning_count": sum(1 for source in sources if source.get("status") != "ok"),
            "archive_start": ARCHIVE_START.isoformat(),
            "archive_policy": "retain verified events from 2026-01-01 through the official future horizon",
            "note": "Official-source date monitor with online historical backfill and last-known-good retention; no guessed dates.",
        },
        "sources": sources,
        "events": events,
    }
    EVENTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED_PATH.write_text("window.__EVENT_SEED__ = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    STATE_PATH.write_text(json.dumps({
        "version": "v11.4.31", "initialized": True,
        "initialized_origins": sorted(next_initialized_origins),
        "updated_at": NOW.isoformat(timespec="seconds"), "events": next_state,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("events", len(events), "announced_today", announced_today, "sources_ok", payload["metadata"]["source_ok_count"])


if __name__ == "__main__":
    main()
