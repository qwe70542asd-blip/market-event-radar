#!/usr/bin/env python3
"""Refresh official announcements and institutional flow for v11.0.0.

Key fixes:
- Weekend/holiday runs show the latest available trading day instead of today's empty date.
- Google Search and Google News redirect URLs are never published.
- Unresolved items are withheld; official open-data rows may use the official department page.
- Previous successful institutional figures and announcements are retained on partial failure.
- Official sources are clearly separated from licensed broker-branch data, which is not guessed.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
from zoneinfo import ZoneInfo

import requests
from update_news import resolve_google_news_url, valid_direct_candidate

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "announcements.json"
SEED = DATA / "announcements-seed.js"
TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime.now(TAIPEI)
ANNOUNCEMENT_RETENTION_DAYS = 30

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.0.0; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language": "zh-TW,zh;q=0.95,en-US;q=0.75,en;q=0.65,ja;q=0.55",
}

SEARCHES = [
    ("金融監督管理委員會", "TW", "government", "site:fsc.gov.tw (新聞稿 OR 證券 OR 銀行 OR 保險 OR ETF)", "zh-TW", "TW", "TW:zh-Hant"),
    ("中央銀行", "TW", "central-bank", "site:cbc.gov.tw (新聞稿 OR 利率 OR 匯率 OR 貨幣政策)", "zh-TW", "TW", "TW:zh-Hant"),
    ("主計總處", "TW", "government", "site:dgbas.gov.tw (CPI OR GDP OR 薪資 OR 失業率 OR 新聞稿)", "zh-TW", "TW", "TW:zh-Hant"),
    ("財政部", "TW", "government", "site:mof.gov.tw (關稅 OR 出口 OR 進口 OR 稅收 OR 新聞稿)", "zh-TW", "TW", "TW:zh-Hant"),
    ("經濟部", "TW", "government", "site:moea.gov.tw (工業生產 OR 外銷訂單 OR 能源 OR 產業政策 OR 新聞稿)", "zh-TW", "TW", "TW:zh-Hant"),
    ("Federal Reserve", "US", "central-bank", "site:federalreserve.gov (press release OR monetary policy OR financial stability)", "en-US", "US", "US:en"),
    ("U.S. SEC", "US", "regulator", "site:sec.gov/newsroom/press-releases (market OR rule OR enforcement OR crypto OR reporting)", "en-US", "US", "US:en"),
    ("U.S. Treasury", "US", "government", "site:home.treasury.gov/news/press-releases (sanctions OR debt OR tax OR financial markets)", "en-US", "US", "US:en"),
    ("White House", "US", "government", "site:whitehouse.gov (tariff OR trade OR semiconductor OR executive order OR economy)", "en-US", "US", "US:en"),
    ("Bank of Japan", "JP", "central-bank", "site:boj.or.jp/en (monetary policy OR outlook OR statistics OR speech)", "en-US", "US", "US:en"),
    ("Japan Exchange Group", "JP", "exchange", "site:jpx.co.jp/english (news OR market OR listing OR regulation)", "en-US", "US", "US:en"),
    ("Japan MOF", "JP", "government", "site:mof.go.jp/english (foreign exchange OR government bonds OR economy OR press release)", "en-US", "US", "US:en"),
    ("Japan METI", "JP", "government", "site:meti.go.jp/english (industry OR trade OR energy OR semiconductor OR press release)", "en-US", "US", "US:en"),
    ("Japan FSA", "JP", "regulator", "site:fsa.go.jp/en (financial markets OR securities OR banks OR crypto)", "en-US", "US", "US:en"),
]

TRANSLATIONS = {
    "press release": "新聞稿", "monetary policy": "貨幣政策", "financial stability": "金融穩定",
    "interest rate": "利率", "securities": "證券", "enforcement": "執法", "rule": "規則",
    "reporting": "申報", "crypto": "虛擬資產", "tariff": "關稅", "trade": "貿易",
    "semiconductor": "半導體", "executive order": "行政命令", "government bonds": "政府公債",
    "foreign exchange": "外匯", "statistics": "統計", "outlook": "展望報告",
    "listing": "上市掛牌", "regulation": "監管", "banks": "銀行", "energy": "能源",
    "industry": "產業", "sanctions": "制裁", "market": "市場",
}

STABLE_SOURCE_URLS = {
    "金融監督管理委員會": "https://www.fsc.gov.tw/",
    "中央銀行": "https://www.cbc.gov.tw/",
    "主計總處": "https://www.dgbas.gov.tw/",
    "財政部": "https://www.mof.gov.tw/",
    "經濟部": "https://www.moea.gov.tw/",
    "Federal Reserve": "https://www.federalreserve.gov/newsevents/pressreleases.htm",
    "U.S. SEC": "https://www.sec.gov/newsroom/press-releases",
    "U.S. Treasury": "https://home.treasury.gov/news/press-releases",
    "White House": "https://www.whitehouse.gov/briefings-statements/",
    "Bank of Japan": "https://www.boj.or.jp/en/whatsnew/",
    "Japan Exchange Group": "https://www.jpx.co.jp/english/news/",
    "Japan MOF": "https://www.mof.go.jp/english/",
    "Japan METI": "https://www.meti.go.jp/english/press/",
    "Japan FSA": "https://www.fsa.go.jp/en/news/",
}


def clean(value) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def parse_date(value):
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TAIPEI)
        return parsed.astimezone(TAIPEI).isoformat(timespec="seconds")
    except Exception:
        pass
    try:
        parsed = datetime.fromisoformat(clean(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TAIPEI)
        return parsed.astimezone(TAIPEI).isoformat(timespec="seconds")
    except Exception:
        pass
    parsed_day = parse_any_market_date(value)
    if parsed_day:
        return datetime.combine(parsed_day, datetime.min.time(), TAIPEI).isoformat(timespec="seconds")
    return None


def parse_any_market_date(value) -> date | None:
    text = clean(value)
    if not text:
        return None
    roc = re.search(r"(?<!\d)(\d{3})[年/-](\d{1,2})[月/-](\d{1,2})", text)
    if roc:
        try:
            return date(int(roc.group(1)) + 1911, int(roc.group(2)), int(roc.group(3)))
        except ValueError:
            pass
    greg = re.search(r"(?<!\d)(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})", text)
    if greg:
        try:
            return date(int(greg.group(1)), int(greg.group(2)), int(greg.group(3)))
        except ValueError:
            pass
    compact = re.search(r"(?<!\d)(20\d{6}|\d{7})(?!\d)", text)
    if compact:
        token = compact.group(1)
        try:
            if len(token) == 8:
                return date(int(token[:4]), int(token[4:6]), int(token[6:8]))
            return date(int(token[:3]) + 1911, int(token[3:5]), int(token[5:7]))
        except ValueError:
            pass
    return None


def latest_weekday(day: date) -> date:
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day


def search_url(title: str, source: str = "") -> str:
    query = " ".join(part for part in [f'"{clean(title)}"', clean(source)] if part)
    return ""


def is_google_news_url(value: str) -> bool:
    return bool(re.match(r"^https?://news\.google\.com/(?:rss/)?(?:articles|read)/", clean(value), re.I))


def stable_link(link: str, title: str, source: str) -> str:
    value = clean(link)
    if value and not is_google_news_url(value):
        return value
    return ""


def translate_rule(title: str) -> str:
    output = title
    changed = False
    for english, chinese in TRANSLATIONS.items():
        updated = re.sub(re.escape(english), chinese, output, flags=re.I)
        if updated != output:
            changed = True
            output = updated
    return output if changed else f"官方公告：{title}"


def text(node, names):
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return clean(found.text)
    return ""


def google_feed(query: str, hl: str, gl: str, ceid: str):
    url = f"https://news.google.com/rss/search?q={quote_plus(query + ' when:30d')}&hl={hl}&gl={gl}&ceid={ceid}"
    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    rows = []
    for item in root.findall(".//item")[:12]:
        title = text(item, ["title"])
        link = text(item, ["link"])
        published = text(item, ["pubDate"])
        if title:
            rows.append((title, stable_link(link, title, ""), link, parse_date(published)))
    return rows


def to_hundred_million(value):
    try:
        return float(str(value).replace(",", "").strip()) / 100_000_000
    except Exception:
        return None


def parse_institution_rows(rows):
    result = {"foreign": None, "investment_trust": None, "dealer": None, "total": None}
    for row in rows or []:
        values = list(row.values()) if isinstance(row, dict) else list(row)
        label = " ".join(map(str, values))
        net = None
        if isinstance(row, dict):
            for key, value in row.items():
                if "買賣超" in key or "差額" in key or "Net" in key:
                    candidate = to_hundred_million(value)
                    if candidate is not None:
                        net = candidate
        else:
            if values:
                net = to_hundred_million(values[-1])
        if "合計" in label:
            result["total"] = net
        elif "外資自營商" in label and "不含外資自營商" not in label:
            # TWSE states this row is already included in dealer trading amounts,
            # so adding it again would double-count dealer net flow.
            continue
        elif "外資及陸資" in label or ("外資" in label and "自營商" not in label):
            result["foreign"] = net
        elif "投信" in label:
            result["investment_trust"] = net
        elif "自營商" in label or "自營" in label:
            result["dealer"] = (result["dealer"] or 0) + (net or 0)
    if result["total"] is None:
        parts = [result["foreign"], result["investment_trust"], result["dealer"]]
        if any(value is not None for value in parts):
            result["total"] = sum(value or 0 for value in parts)
    return result


def twse_institutional():
    today = NOW.date()
    for offset in range(0, 14):
        candidate = today - timedelta(days=offset)
        if candidate.weekday() >= 5:
            continue
        url = "https://www.twse.com.tw/rwd/zh/fund/BFI82U"
        response = requests.get(
            url,
            headers=HEADERS,
            params={"response": "json", "type": "day", "dayDate": candidate.strftime("%Y%m%d")},
            timeout=25,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data") or []
        if not rows:
            continue
        result = parse_institution_rows(rows)
        reported = parse_any_market_date(payload.get("title")) or candidate
        if any(value is not None for value in result.values()):
            return result, reported.isoformat(), response.url
    raise RuntimeError("TWSE did not return a recent trading day")


def tpex_institutional():
    url = "https://www.tpex.org.tw/openapi/v1/tpex_3insti_summary"
    response = requests.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    rows = response.json()
    result = parse_institution_rows(rows)
    reported = None
    for row in rows if isinstance(rows, list) else []:
        for key, value in row.items():
            if any(token in key for token in ["日期", "Date", "資料日"]):
                reported = parse_any_market_date(value)
                if reported:
                    break
        if reported:
            break
    reported = reported or latest_weekday(NOW.date())
    if not any(value is not None for value in result.values()):
        raise RuntimeError("TPEx summary has no values")
    return result, reported.isoformat(), url


def official_open_data_items():
    items = []
    feeds = [
        ("臺灣證券交易所", "TW", "exchange", "https://openapi.twse.com.tw/v1/news/newsList", "https://www.twse.com.tw/zh/"),
        ("臺灣證券交易所重大訊息", "TW", "company", "https://openapi.twse.com.tw/v1/opendata/t187ap04_L", "https://mops.twse.com.tw/"),
        ("證券櫃檯買賣中心重大訊息", "TW", "company", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O", "https://mops.twse.com.tw/"),
    ]
    for source, region, category, url, fallback in feeds:
        try:
            rows = requests.get(url, headers=HEADERS, timeout=25).json()
            for row in (rows if isinstance(rows, list) else [])[:18]:
                blob = {str(key): value for key, value in row.items()}
                title = next(
                    (clean(value) for key, value in blob.items()
                     if any(token in key for token in ["標題", "主旨", "重大訊息"]) and clean(value)),
                    None,
                )
                direct = next(
                    (clean(value) for key, value in blob.items()
                     if any(token in key for token in ["網址", "URL", "Url"]) and clean(value).startswith("http")),
                    None,
                )
                date_value = next(
                    (clean(value) for key, value in blob.items() if any(token in key for token in ["日期", "時間", "Date"])),
                    None,
                )
                if not title:
                    continue
                items.append({
                    "id": hashlib.sha1((source + title).encode()).hexdigest()[:16],
                    "region": region,
                    "category": category,
                    "source": source,
                    "title_zh": title,
                    "title_original": title,
                    "link": direct or fallback,
                    "published_at": parse_date(date_value),
                    "importance": "high",
                    "translation_status": "official-zh",
                    "link_status": "direct-official" if direct else "official-homepage",
                })
        except Exception as exc:
            print("warning official feed", source, exc)
    return items


def still_recent(item, days: int = ANNOUNCEMENT_RETENTION_DAYS) -> bool:
    value = item.get("published_at")
    if not value:
        return True
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=TAIPEI)
        return parsed.astimezone(TAIPEI) >= NOW - timedelta(days=days)
    except Exception:
        return True


def announcement_rank(item) -> tuple[int, float]:
    direct = item.get("link_status") in {"direct", "direct-official"}
    try:
        published = datetime.fromisoformat(item.get("published_at") or "").timestamp()
    except Exception:
        published = 0.0
    return int(direct), published


def main():
    previous = read_json(OUT, {"items": [], "institutional": {}})
    items = official_open_data_items()
    session = requests.Session()

    for source, region, category, query, hl, gl, ceid in SEARCHES:
        try:
            for title, _link, original_link, published in google_feed(query, hl, gl, ceid):
                source_home = STABLE_SOURCE_URLS.get(source, "")
                direct, method = resolve_google_news_url(session, original_link, source, source_home)
                link = direct if valid_direct_candidate(direct) else source_home
                chinese = title if region == "TW" else translate_rule(title)
                items.append({
                    "id": hashlib.sha1((source + title).encode()).hexdigest()[:16],
                    "region": region,
                    "category": category,
                    "source": source,
                    "title_zh": chinese,
                    "title_original": title,
                    "link": link,
                    "direct_link": direct if valid_direct_candidate(direct) else "",
                    "original_link": original_link,
                    "source_home": source_home,
                    "published_at": published,
                    "importance": "high",
                    "translation_status": "official-zh" if region == "TW" else "rule-based",
                    "link_status": "direct" if valid_direct_candidate(direct) else "official-homepage",
                    "link_type": method or "official-homepage",
                })
        except Exception as exc:
            print("warning search", source, exc)
        time.sleep(0.08)

    # Keep every still-valid official item from the previous successful run.
    # This avoids an empty/short list when an official feed only returns the
    # latest page or one source has a temporary outage.
    if previous.get("metadata", {}).get("updated_at"):
        items.extend(item for item in previous.get("items", []) if still_recent(item))

    deduplicated = {}
    for item in items:
        key = re.sub(r"\W+", "", clean(item["title_original"]).lower())
        if key not in deduplicated or announcement_rank(item) > announcement_rank(deduplicated[key]):
            deduplicated[key] = item
    if not deduplicated and previous.get("metadata", {}).get("updated_at"):
        deduplicated = {item.get("id", str(index)): item for index, item in enumerate(previous.get("items", [])) if still_recent(item)}

    previous_inst = previous.get("institutional", {})
    institutional_status = "ok"
    try:
        twse, twse_date, twse_url = twse_institutional()
    except Exception as exc:
        print("warning twse institutional", exc)
        twse = previous_inst.get("twse", {})
        twse_date = previous_inst.get("twse_date") or previous_inst.get("date")
        twse_url = previous_inst.get("twse_url") or "https://www.twse.com.tw/zh/trading/foreign/bfi82u.html"
        institutional_status = "stale"

    try:
        tpex, tpex_date, tpex_url = tpex_institutional()
    except Exception as exc:
        print("warning tpex institutional", exc)
        tpex = previous_inst.get("tpex", {})
        tpex_date = previous_inst.get("tpex_date") or previous_inst.get("date")
        tpex_url = previous_inst.get("tpex_url") or "https://www.tpex.org.tw/zh-tw/mainboard/trading/major-institutional/summary/day.html"
        institutional_status = "stale"

    available_dates = [value for value in [twse_date, tpex_date] if value]
    data_date = max(available_dates) if available_dates else latest_weekday(NOW.date()).isoformat()
    is_weekend_or_lag = data_date != NOW.date().isoformat()

    payload = {
        "metadata": {
            "version": "v11.0.0",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": "ok" if deduplicated else "warning",
            "retention_days": ANNOUNCEMENT_RETENTION_DAYS,
            "translation_note": "Known official phrases use rule-based Chinese translation; original title is preserved.",
            "link_note": "Official article links are resolved when possible; otherwise the row opens the source's official announcement page.",
        },
        "institutional": {
            "date": data_date,
            "twse_date": twse_date,
            "tpex_date": tpex_date,
            "twse": twse,
            "tpex": tpex,
            "twse_url": twse_url,
            "tpex_url": tpex_url,
            "status": institutional_status,
            "is_previous_trading_day": is_weekend_or_lag,
            "note": "週末與休市日顯示最近交易日資料；三大法人為官方公開彙總。個別外資券商分點需授權資料源。",
        },
        "items": sorted(
            deduplicated.values(),
            key=lambda item: item.get("published_at") or "",
            reverse=True,
        )[:120],
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED.write_text(
        "window.__MARKET_ANNOUNCEMENT_SEED__ = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    print("announcements", len(payload["items"]), "institutional date", data_date, institutional_status)


if __name__ == "__main__":
    main()
