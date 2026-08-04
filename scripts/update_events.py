#!/usr/bin/env python3
"""Build Market Event Radar v11.4.1 event data from official schedules.

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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.3; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}
TWSE_EXDIV_URL = "https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL"
TPEX_EXDIV_URL = "https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost"
TWSE_DIVIDEND_PLAN_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap45_L"
TPEX_DIVIDEND_PLAN_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap45_O"
TWSE_MATERIAL_URL = "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
TPEX_MATERIAL_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"
BLS_URL = "https://www.bls.gov/schedule/news_release/bls.ics"
BEA_URL = "https://www.bea.gov/news/schedule"

BLS_TRANSLATIONS = {
    "Employment Situation": ("美國非農就業報告", "high", ["NASDAQ", "美債", "美元", "黃金", "台股"]),
    "Consumer Price Index": ("美國 CPI 通膨", "high", ["NASDAQ", "美債", "美元", "黃金", "台股"]),
    "Producer Price Index": ("美國 PPI 生產者物價", "medium", ["美債", "美元", "NASDAQ"]),
    "Job Openings and Labor Turnover Survey": ("美國 JOLTS 職缺數", "medium", ["美債", "美元", "NASDAQ"]),
    "Employment Cost Index": ("美國就業成本指數", "high", ["美債", "美元", "NASDAQ"]),
    "Productivity and Costs": ("美國生產力與單位勞動成本", "medium", ["美債", "NASDAQ", "美元"]),
}
BEA_TRANSLATIONS = {
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


def fetch_bls(session: requests.Session) -> SourceResult:
    lines = unfold_ics(http_get(session, BLS_URL).text)
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
        elif line == "END:VEVENT" and current is not None:
            blocks.append(current)
            current = None
        elif current is not None and ":" in line:
            key, value = line.split(":", 1)
            current[key] = value
    events = []
    for block in blocks:
        summary = next((v for k, v in block.items() if k.startswith("SUMMARY")), "")
        translated = translate(summary, BLS_TRANSLATIONS)
        dt_pair = next(((k, v) for k, v in block.items() if k.startswith("DTSTART")), None)
        if not translated or not dt_pair:
            continue
        start = parse_ics_datetime(*dt_pair)
        if not NOW - timedelta(days=14) <= start <= NOW + timedelta(days=370):
            continue
        uid = next((v for k, v in block.items() if k.startswith("UID")), summary)
        title, impact, assets = translated
        key = f"bls|{clean(uid)}"
        events.append(make_event(
            event_id=stable_id("bls", key, start.date()), tracking_key=key,
            title=title, start=start, category="macro", event_type="economic-release", event_group="macro",
            region="US", impact=impact, description=f"BLS 發布 {summary}。",
            market_effect="數據與市場預期的落差可能改變聯準會政策、美債殖利率、美元與股票評價。",
            source_name="U.S. BLS", source_url=BLS_URL, origin="bls", assets=assets, tags=["BLS", summary],
        ))
    if not events:
        raise RuntimeError("BLS calendar returned no recognized events")
    return SourceResult("bls", "U.S. BLS release calendar", BLS_URL, ("bls",), events)


def fetch_bea(session: requests.Session) -> SourceResult:
    soup = BeautifulSoup(http_get(session, BEA_URL).text, "html.parser")
    raw_text = soup.get_text("\n", strip=True)
    pattern = re.compile(
        r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)\s+"
        r"(?P<day>\d{1,2})\s+(?P<hour>\d{1,2}):(?P<minute>\d{2})\s+(?P<ampm>AM|PM)\s+(?:News|Data)\s+(?P<title>[^\n]+)", re.I,
    )
    events = []
    for match in pattern.finditer(raw_text):
        raw_title = clean(match.group("title"))
        translated = translate(raw_title, BEA_TRANSLATIONS)
        if not translated:
            continue
        month = datetime.strptime(match.group("month"), "%B").month
        hour = int(match.group("hour")) % 12 + (12 if match.group("ampm").upper() == "PM" else 0)
        candidates = [
            datetime(year, month, int(match.group("day")), hour, int(match.group("minute")), tzinfo=NEW_YORK).astimezone(TAIPEI)
            for year in (NOW.year - 1, NOW.year, NOW.year + 1)
        ]
        start = min(candidates, key=lambda value: abs((value - NOW).total_seconds()))
        if not NOW - timedelta(days=14) <= start <= NOW + timedelta(days=370):
            continue
        title, impact, assets = translated
        key = f"bea|{raw_title.lower()}"
        events.append(make_event(
            event_id=stable_id("bea", key, start.date()), tracking_key=key,
            title=title, start=start, category="macro", event_type="economic-release", event_group="macro",
            region="US", impact=impact, description=f"BEA 發布 {raw_title}。",
            market_effect="成長、所得、消費與通膨資料可能改變美債、美元及風險資產定價。",
            source_name="U.S. BEA", source_url=BEA_URL, origin="bea", assets=assets, tags=["BEA", raw_title],
        ))
    if not events:
        raise RuntimeError("BEA schedule returned no recognized events")
    return SourceResult("bea", "U.S. BEA release schedule", BEA_URL, ("bea",), events)


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


def dividend_total(row: dict[str, Any], needle: str) -> float:
    total = 0.0
    for key, value in row.items():
        if needle in key and ("元/股" in key or "每股" in key):
            total += parse_number(value) or 0.0
    return total


def parse_dividend_plans(rows: Any, market: str, source_url: str, origin: str) -> list[dict[str, Any]]:
    events = []
    if not isinstance(rows, list):
        return events
    for row in rows:
        symbol = first_value(row, ["公司代號", "CompanyCode", "SecuritiesCompanyCode", "Code"])
        name = first_value(row, ["公司名稱", "CompanyName", "Name"])
        if not symbol:
            continue
        period = first_value(row, ["股利所屬年(季)度", "股利年度", "DividendYear"])
        shareholder_day = parse_market_date(first_value(row, ["股東會日期", "ShareholdersMeetingDate"]))
        decision_day = parse_market_date(first_value(row, ["董事會（擬議）股利分派日", "董事會股利分派日", "BoardMeetingDate"]))
        cash, stock = dividend_total(row, "現金"), dividend_total(row, "配股")
        if shareholder_day and NOW.date() - timedelta(days=30) <= shareholder_day <= NOW.date() + timedelta(days=370):
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
        if decision_day and NOW.date() - timedelta(days=30) <= decision_day <= NOW.date() + timedelta(days=370):
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
        if parsed and NOW.date() - timedelta(days=1) <= parsed <= NOW.date() + timedelta(days=370):
            values.append(parsed)
    return sorted(set(values))


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
        announcement_day = parse_market_date(first_value(row, ["發言日期", "出表日期", "Date"])) or NOW.date()
        dates = [value for value in extract_candidate_dates(subject) if value != announcement_day]
        if not dates:
            continue  # exact target date was not published; do not guess one
        target_day = dates[0]
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
            source_published_at=iso_taipei(at_taipei(announcement_day)), target_date=target_day.isoformat(),
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
        fetch_bls, fetch_bea, fetch_twse_exdiv, fetch_tpex_exdiv,
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
                "twse-dividend-plans": ("twse-dividend-plan",), "tpex-dividend-plans": ("tpex-dividend-plan",),
                "twse-material": ("twse-material",), "tpex-material": ("tpex-material",),
                "bls": ("bls",), "bea": ("bea",),
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
    cutoff, horizon = NOW - timedelta(days=35), NOW + timedelta(days=370)
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
            if old_state is None:
                row["announced_at"] = NOW.isoformat(timespec="seconds")
                row["announcement_kind"] = "new-date"
                row["announcement_status"] = "new_date_today"
                announced_today += 1
            elif str(old_state.get("start")) != row["start"]:
                row["previous_start"] = old_state.get("start")
                row["announced_at"] = NOW.isoformat(timespec="seconds")
                row["announcement_kind"] = "date-changed"
                row["announcement_status"] = "date_changed_today"
                announced_today += 1

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
        canonical[key] = winner

    events = sorted(canonical.values(), key=lambda row: (str(row.get("start")), str(row.get("title"))))
    if not events and previous_events:
        raise SystemExit("No events after refresh; previous verified archive was not replaced.")

    recent_cutoff = NOW - timedelta(hours=24)
    announced_recent = sum(
        1 for row in events
        if row.get("announced_at") and (date_parser.parse(str(row["announced_at"])).astimezone(TAIPEI) >= recent_cutoff)
    )
    payload = {
        "metadata": {
            "version": "v11.4.1",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "timezone": "Asia/Taipei",
            "event_count": len(events),
            "announced_today_count": announced_today,
            "announced_recent_count": announced_recent,
            "state_initialized": True,
            "source_ok_count": sum(1 for source in sources if source.get("status") == "ok"),
            "source_warning_count": sum(1 for source in sources if source.get("status") != "ok"),
            "note": "Official-source date monitor with last-known-good retention; no guessed dates.",
        },
        "sources": sources,
        "events": events,
    }
    EVENTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED_PATH.write_text("window.__EVENT_SEED__ = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    STATE_PATH.write_text(json.dumps({
        "version": "v11.4.1", "initialized": True,
        "initialized_origins": sorted(next_initialized_origins),
        "updated_at": NOW.isoformat(timespec="seconds"), "events": next_state,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("events", len(events), "announced_today", announced_today, "sources_ok", payload["metadata"]["source_ok_count"])


if __name__ == "__main__":
    main()
