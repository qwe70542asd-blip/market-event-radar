#!/usr/bin/env python3
"""Build a resilient Taiwan-focused finance-news and material-information archive.

Design goals:
- All configured sources are visible in source health, even when a source has no
  current article or is checked in another rotation bucket.
- Official material information is fetched every run.
- High-priority publishers are fetched every run; long-tail publisher, broker,
  technology and fund-house searches are rotated to avoid Google News throttling.
- RSS parsing uses the supported feedparser.parse API and
  includes a stdlib XML fallback.
- A failed run never replaces the last successful archive with an empty file.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo
import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET

try:
    import feedparser
except ImportError:  # stdlib XML fallback remains available
    feedparser = None
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "news.json"
SEED = DATA / "news-seed.js"
REGISTRY = DATA / "news-sources.json"

TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime.now(TAIPEI)
RETENTION_DAYS = 20
REQUEST_TIMEOUT = 16
MAX_WORKERS = 16
ROTATION_BUCKETS = 4

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; MarketEventRadar/11.2.7; "
        "+https://github.com/qwe70542asd-blip/market-event-radar)"
    ),
    "Accept": "application/json,application/rss+xml,application/atom+xml,text/xml,text/html,*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
}

TOPIC_RULES = [
    ("material", re.compile(
        r"重大訊息|重大公告|停止交易|恢復交易|處置|注意股票|合併|收購|併購|"
        r"增資|減資|庫藏股|董事會|股東會|法說會|更換董事|更換總經理|"
        r"簽訂.*契約|重大投資|訴訟|災害|違約|下市|終止上市|終止上櫃", re.I)),
    ("earnings", re.compile(r"財報|季報|年報|營收|EPS|獲利|虧損|財測|法說", re.I)),
    ("dividend", re.compile(r"股利|配息|除權|除息|填息|現金股息|股票股利", re.I)),
    ("fund", re.compile(r"ETF|基金|淨值|折溢價|成分股|投信基金", re.I)),
    ("policy", re.compile(r"央行|聯準會|利率|CPI|PPI|PMI|GDP|關稅|政策|制裁|匯率", re.I)),
    ("industry", re.compile(r"半導體|AI|伺服器|航運|金融|生技|軍工|能源|記憶體|PCB", re.I)),
    ("crypto", re.compile(r"比特幣|以太坊|加密|虛擬貨幣|區塊鏈|Bitcoin|Ethereum", re.I)),
]
REGION_RULES = [
    ("TW", re.compile(r"台股|臺股|台灣|臺灣|上市|上櫃|新台幣|證交所|櫃買|金管會", re.I)),
    ("US", re.compile(r"美股|美國|聯準會|那斯達克|道瓊|標普|NASDAQ|S&P", re.I)),
    ("JP", re.compile(r"日股|日本|日銀|日圓|東證|日經", re.I)),
    ("KR", re.compile(r"韓股|韓國|三星|KOSPI", re.I)),
    ("CN", re.compile(r"陸股|中國|人民幣|滬深|上海|深圳|港股|恒生", re.I)),
    ("EU", re.compile(r"歐股|歐洲|ECB|歐洲央行|德國|英國|法國", re.I)),
]

IMPORTANCE_PATTERNS = [
    (35, re.compile(r"重大訊息|停止交易|恢復交易|下市|終止上市|終止上櫃|違約|重大災害", re.I)),
    (25, re.compile(r"財報|法說|財測|股利|增資|減資|合併|收購|併購|庫藏股", re.I)),
    (18, re.compile(r"央行|利率決策|關稅|制裁|地緣政治|金融危機|熔斷", re.I)),
    (12, re.compile(r"營收|EPS|獲利|虧損|除權息|成分股調整", re.I)),
]

GROUP_PRIORITY = {
    "official-company": 60,
    "official": 50,
    "publisher": 35,
    "portal": 32,
    "technology": 30,
    "broker": 24,
    "fund-house": 22,
    "broad": 18,
    "discovered": 15,
}


def clean_text(value: object) -> str:
    soup = BeautifulSoup(html.unescape(str(value or "")), "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def normalized_title(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value.lower())


def stable_id(source: str, title: str, link: str) -> str:
    return hashlib.sha1(f"{source}|{title}|{link}".encode("utf-8")).hexdigest()[:18]


def parse_time(value: object, default: datetime | None = None) -> datetime:
    default = default or NOW
    if not value:
        return default
    try:
        parsed = dateparser.parse(str(value))
        if not parsed.tzinfo:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(TAIPEI)
    except Exception:
        return default


def parse_roc_datetime(date_value: object, time_value: object = "") -> datetime:
    date_digits = re.sub(r"\D", "", str(date_value or ""))
    time_digits = re.sub(r"\D", "", str(time_value or "")).ljust(6, "0")[:6]
    try:
        if len(date_digits) == 7:
            year = int(date_digits[:3]) + 1911
            month = int(date_digits[3:5])
            day = int(date_digits[5:7])
        elif len(date_digits) >= 8:
            year = int(date_digits[:4])
            month = int(date_digits[4:6])
            day = int(date_digits[6:8])
        else:
            return NOW
        return datetime(
            year, month, day,
            int(time_digits[:2]), int(time_digits[2:4]), int(time_digits[4:6]),
            tzinfo=TAIPEI,
        )
    except Exception:
        return NOW


def classify(title: str, summary: str, group: str = "") -> tuple[str, str]:
    text = f"{title} {summary}"
    topic = "market"
    for candidate, pattern in TOPIC_RULES:
        if pattern.search(text):
            topic = candidate
            break
    region = "TW" if group.startswith("official") else "GLOBAL"
    for candidate, pattern in REGION_RULES:
        if pattern.search(text):
            region = candidate
            break
    return topic, region


def importance_score(title: str, summary: str, group: str, source_priority: int = 0) -> int:
    text = f"{title} {summary}"
    score = GROUP_PRIORITY.get(group, 10) + int(source_priority or 0)
    for points, pattern in IMPORTANCE_PATTERNS:
        if pattern.search(text):
            score += points
    return score


def canonical_cluster_key(item: dict) -> str:
    title = clean_text(item.get("title"))
    date_key = str(item.get("published_at") or "")[:10]
    code_match = re.search(r"(?:\(|（|\s)(\d{4,6}[A-Z]?)(?:\)|）|\s)", title)
    cleaned = re.sub(r"【[^】]{0,40}】|\[[^\]]{0,40}\]", " ", title)
    cleaned = re.sub(
        r"\b(?:Yahoo|MoneyDJ|鉅亨網|中央社|經濟日報|工商時報|證交所|臺灣證券交易所)\b",
        " ", cleaned, flags=re.I,
    )
    normalized = normalized_title(cleaned)
    if code_match and re.search(r"重大訊息|公告|財報|法說|股利|增資|減資|合併|收購", title):
        family = "material" if re.search(r"重大訊息|公告|增資|減資|合併|收購", title) else "financial"
        return f"company:{date_key}:{code_match.group(1)}:{family}:{normalized[:48]}"
    if re.search(r"(?:排行|排名).*?(?:前|Top)\s*\d+\s*名", cleaned, re.I):
        market = "上市" if "上市" in cleaned else "上櫃" if "上櫃" in cleaned else "市場"
        family = "籌碼" if re.search(r"外資|投信|自營商|融資|融券|借券", cleaned) else "排行"
        return f"template:{date_key}:{market}:{family}"
    return f"exact:{normalized}"


def cluster_news(items: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[canonical_cluster_key(item)].append(item)

    output = []
    for cluster_key, rows in groups.items():
        rows.sort(
            key=lambda row: (
                int(row.get("importance_score") or 0),
                bool(row.get("summary")),
                str(row.get("published_at") or ""),
            ),
            reverse=True,
        )
        primary = dict(rows[0])
        related_sources: list[str] = []
        related_links: list[dict] = []
        for row in rows:
            source = str(row.get("source") or "其他來源")
            if source not in related_sources:
                related_sources.append(source)
            link = row.get("article_link") or row.get("direct_link") or row.get("link")
            if link and all(existing.get("link") != link for existing in related_links):
                related_links.append({
                    "source": source,
                    "title": row.get("title"),
                    "link": link,
                })
        primary["cluster_id"] = hashlib.sha1(cluster_key.encode("utf-8")).hexdigest()[:16]
        primary["duplicate_count"] = max(0, len(rows) - 1)
        primary["related_sources"] = related_sources
        primary["related_links"] = related_links[:20]
        output.append(primary)
    return output


def interleave_sources(items: list[dict]) -> list[dict]:
    queues: dict[str, list[dict]] = defaultdict(list)
    for item in sorted(
        items,
        key=lambda row: (
            str(row.get("published_at") or ""),
            int(row.get("importance_score") or 0),
        ),
        reverse=True,
    ):
        queues[str(item.get("source") or "其他來源")].append(item)

    result = []
    last_source = None
    while any(queues.values()):
        candidates = [
            (source, queue) for source, queue in queues.items()
            if queue and source != last_source
        ] or [(source, queue) for source, queue in queues.items() if queue]
        source, queue = max(
            candidates,
            key=lambda pair: (
                str(pair[1][0].get("published_at") or ""),
                int(pair[1][0].get("importance_score") or 0),
            ),
        )
        result.append(queue.pop(0))
        last_source = source
    return result


def row_value(row: dict, *needles: str):
    normalized = {
        re.sub(r"[\s_\-（）()%:/]+", "", str(key)).lower(): value
        for key, value in row.items()
    }
    targets = [
        re.sub(r"[\s_\-（）()%:/]+", "", needle).lower()
        for needle in needles
    ]
    for target in targets:
        if target in normalized and normalized[target] not in (None, ""):
            return normalized[target]
    for key, value in normalized.items():
        if value not in (None, "") and any(target in key for target in targets):
            return value
    return None


def google_news_url(query_text: str) -> str:
    return (
        "https://news.google.com/rss/search?"
        f"q={quote(query_text)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    )


def xml_fallback_entries(content: bytes) -> list[dict]:
    """Minimal RSS/Atom parser used only when feedparser cannot parse a feed."""
    try:
        root = ET.fromstring(content)
    except Exception:
        return []

    entries = []
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(".//{*}entry")
    for node in nodes:
        def text_of(*names: str) -> str:
            for name in names:
                child = node.find(name) or node.find(f"{{*}}{name}")
                if child is not None and child.text:
                    return child.text.strip()
            return ""

        link = text_of("link")
        if not link:
            link_node = node.find("{*}link")
            if link_node is not None:
                link = str(link_node.attrib.get("href") or "")
        entries.append({
            "title": text_of("title"),
            "link": link,
            "summary": text_of("description", "summary", "content"),
            "published": text_of("pubDate", "published", "updated"),
        })
    return entries


def parse_feed(content: bytes) -> list[dict]:
    """Use the supported feedparser.parse API and fall back to stdlib XML."""
    entries: list[dict] = []
    try:
        if feedparser is not None:
            parsed = feedparser.parse(content)
            entries = [dict(entry) for entry in getattr(parsed, "entries", [])]
    except Exception:
        entries = []
    return entries or xml_fallback_entries(content)


def feed_entry_time(entry: dict) -> datetime:
    for key in ("published", "updated", "pubDate"):
        if entry.get(key):
            return parse_time(entry.get(key))
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct:
        try:
            return datetime(*struct[:6], tzinfo=timezone.utc).astimezone(TAIPEI)
        except Exception:
            pass
    return NOW


def feed_entry_source(entry: dict) -> str:
    source = entry.get("source")
    if isinstance(source, dict):
        return clean_text(source.get("title") or source.get("href"))
    return clean_text(source)


def item_from_feed_entry(
    entry: dict,
    configured_source: dict,
    *,
    dynamic_source: bool = False,
) -> dict | None:
    title = clean_text(entry.get("title"))
    link = str(entry.get("link") or "").strip()
    summary = clean_text(
        entry.get("summary") or entry.get("description") or entry.get("content") or ""
    )
    if not title or not link.startswith(("http://", "https://")):
        return None

    source = configured_source["name"]
    if dynamic_source:
        source = feed_entry_source(entry) or source
    group = configured_source.get("group") or "publisher"
    published = feed_entry_time(entry)
    topic, region = classify(title, summary, group)
    priority = int(configured_source.get("priority") or 0)

    return {
        "id": stable_id(source, title, link),
        "title": title,
        "summary": summary[:900],
        "source": source,
        "source_key": configured_source["name"],
        "source_group": group if not dynamic_source else "discovered",
        "link": link,
        "direct_link": link,
        "article_link": link,
        "published_at": published.isoformat(timespec="seconds"),
        "topic": topic,
        "region": region,
        "asset_class": "fund" if topic == "fund" else "crypto" if topic == "crypto" else "stock",
        "tags": [topic, region],
        "importance_score": importance_score(title, summary, group, priority),
    }


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def source_status(source: dict, status: str, message: str, item_count: int = 0) -> dict:
    return {
        "name": source["name"],
        "group": source.get("group") or "publisher",
        "method": source.get("method") or "google",
        "homepage": source.get("homepage"),
        "priority": int(source.get("priority") or 0),
        "status": status,
        "message": message[:180],
        "item_count": int(item_count),
        "last_checked_at": NOW.isoformat(timespec="seconds"),
    }


def fetch_feed_source(source: dict) -> tuple[list[dict], dict]:
    url = source.get("url") or google_news_url(str(source.get("query") or ""))
    session = make_session()
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        entries = parse_feed(response.content)
        items = []
        for entry in entries[:100]:
            item = item_from_feed_entry(
                entry,
                source,
                dynamic_source=bool(source.get("dynamic_source")),
            )
            if item:
                items.append(item)
        state = "ok" if items else "empty"
        message = f"{len(items)} 筆" if items else "本輪沒有符合新聞"
        return items, source_status(source, state, message, len(items))
    except Exception as exc:
        return [], source_status(source, "warning", f"{type(exc).__name__}: {exc}")


def fetch_moneydj(source: dict) -> tuple[list[dict], dict]:
    url = "https://www.moneydj.com/kmdj/common/listnewarticles.aspx?a=X1500001&svc=NW"
    session = make_session()
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        seen = set()
        for anchor in soup.select(
            'a[href*="/KMDJ/News/NewsViewer.aspx"], a[href*="/news/"]'
        ):
            title = clean_text(anchor.get_text(" ", strip=True))
            href = str(anchor.get("href") or "")
            if len(title) < 8:
                continue
            link = requests.compat.urljoin(url, href)
            key = normalized_title(title)
            if not key or key in seen:
                continue
            seen.add(key)
            topic, region = classify(title, "", "publisher")
            items.append({
                "id": stable_id(source["name"], title, link),
                "title": title,
                "summary": "",
                "source": source["name"],
                "source_key": source["name"],
                "source_group": "publisher",
                "link": link,
                "direct_link": link,
                "article_link": link,
                "published_at": NOW.isoformat(timespec="seconds"),
                "topic": topic,
                "region": region,
                "asset_class": "fund" if topic == "fund" else "stock",
                "tags": [topic, region],
                "importance_score": importance_score(title, "", "publisher", 5),
            })
            if len(items) >= 60:
                break
        state = "ok" if items else "empty"
        return items, source_status(
            source, state,
            f"{len(items)} 筆" if items else "本輪沒有抓到文章",
            len(items),
        )
    except Exception as exc:
        return [], source_status(source, "warning", f"{type(exc).__name__}: {exc}")


def fetch_twse_news(source: dict) -> tuple[list[dict], dict]:
    session = make_session()
    try:
        response = session.get(
            "https://openapi.twse.com.tw/v1/news/newsList",
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload if isinstance(payload, list) else payload.get("data") or []
        items = []
        for row in rows[:200]:
            if not isinstance(row, dict):
                continue
            title = clean_text(row_value(row, "title", "subject", "head_text", "標題", "主旨"))
            summary = clean_text(row_value(row, "summary", "content", "text", "說明"))
            uid = str(row_value(row, "id", "uuid", "seqno", "編號") or "").strip()
            date_value = row_value(row, "date", "datetime", "發布時間", "時間")
            if not title:
                continue
            published = parse_time(date_value)
            link = (
                f"https://www.twse.com.tw/zh/news/newsDetail/{uid}"
                if uid else source["homepage"]
            )
            topic, region = classify(title, summary, "official")
            items.append({
                "id": stable_id(source["name"], title, link),
                "title": title,
                "summary": summary[:900],
                "source": source["name"],
                "source_key": source["name"],
                "source_group": "official",
                "link": link,
                "direct_link": link,
                "article_link": link,
                "published_at": published.isoformat(timespec="seconds"),
                "topic": topic,
                "region": "TW" if region == "GLOBAL" else region,
                "asset_class": "fund" if topic == "fund" else "stock",
                "tags": ["official", topic, "TW"],
                "importance_score": importance_score(title, summary, "official", 5),
            })
        state = "ok" if items else "empty"
        return items, source_status(
            source, state,
            f"{len(items)} 筆" if items else "官方目前沒有新資料",
            len(items),
        )
    except Exception as exc:
        return [], source_status(source, "warning", f"{type(exc).__name__}: {exc}")


def fetch_company_announcements(source: dict) -> tuple[list[dict], dict]:
    is_listed = source.get("method") == "mops_listed"
    market = "TWSE" if is_listed else "TPEx"
    url = (
        "https://openapi.twse.com.tw/v1/opendata/t187ap04_L"
        if is_listed else
        "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O"
    )
    session = make_session()
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        rows = payload if isinstance(payload, list) else payload.get("data") or []
        items = []
        for row in rows[:1500]:
            if not isinstance(row, dict):
                continue
            code = str(row_value(row, "公司代號", "證券代號", "股票代號") or "").strip().upper()
            company = clean_text(row_value(row, "公司簡稱", "公司名稱", "證券名稱"))
            subject = clean_text(row_value(row, "主旨", "重大訊息主旨", "subject", "title"))
            explanation = clean_text(row_value(row, "說明", "內容", "content"))
            date_value = row_value(row, "發言日期", "發布日期", "日期", "date")
            time_value = row_value(row, "發言時間", "發布時間", "時間", "time")
            if not code or not subject:
                continue
            published = parse_roc_datetime(date_value, time_value)
            title = (
                f"{company}（{code}）{subject}"
                if company and company not in subject else f"{code} {subject}"
            )
            link = "https://mops.twse.com.tw/mops/web/t05st01"
            topic, _ = classify(title, explanation, "official-company")
            items.append({
                "id": stable_id(source["name"], title, f"{date_value}-{time_value}-{code}"),
                "title": title,
                "summary": explanation[:1200],
                "source": "公開資訊觀測站",
                "source_key": source["name"],
                "source_group": "official-company",
                "link": link,
                "direct_link": link,
                "article_link": link,
                "published_at": published.isoformat(timespec="seconds"),
                "topic": topic,
                "region": "TW",
                "asset_class": "stock",
                "asset_symbols": [code],
                "tags": [code, company, market, "重大訊息", "official-company"],
                "importance_score": importance_score(
                    title, explanation, "official-company", 5
                ),
            })
        state = "ok" if items else "empty"
        return items, source_status(
            source, state,
            f"{len(items)} 筆" if items else "官方目前沒有重大訊息",
            len(items),
        )
    except Exception as exc:
        return [], source_status(source, "warning", f"{type(exc).__name__}: {exc}")


def fetch_source(source: dict) -> tuple[list[dict], dict]:
    method = source.get("method")
    if method in {"rss", "google"}:
        return fetch_feed_source(source)
    if method == "moneydj":
        return fetch_moneydj(source)
    if method == "twse_news":
        return fetch_twse_news(source)
    if method in {"mops_listed", "mops_otc"}:
        return fetch_company_announcements(source)
    return [], source_status(source, "disabled", f"不支援的方法：{method}")


def load_registry() -> list[dict]:
    payload = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = payload.get("sources") or []
    return [
        dict(row) for row in rows
        if isinstance(row, dict) and row.get("enabled", True) and row.get("name")
    ]


def load_previous() -> dict:
    try:
        payload = json.loads(OUT.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {"items": [], "sources": []}


def source_bucket(name: str) -> int:
    return int(hashlib.sha1(name.encode("utf-8")).hexdigest()[:8], 16) % ROTATION_BUCKETS


def should_check(source: dict, current_bucket: int) -> bool:
    method = source.get("method")
    priority = int(source.get("priority") or 0)
    group = source.get("group")
    if method != "google":
        return True
    if group in {"official-company", "broad"} or priority >= 5:
        return True
    return source_bucket(source["name"]) == current_bucket


def merge_source_status(
    configured: list[dict],
    current_statuses: list[dict],
    previous_sources: list[dict],
    current_bucket: int,
) -> list[dict]:
    previous_map = {str(row.get("name")): dict(row) for row in previous_sources if row.get("name")}
    current_map = {str(row.get("name")): dict(row) for row in current_statuses if row.get("name")}
    output = []

    for source in configured:
        name = source["name"]
        previous = previous_map.get(name, {})
        current = current_map.get(name)
        if current:
            if current["status"] in {"ok", "empty"}:
                current["last_success_at"] = NOW.isoformat(timespec="seconds")
            else:
                current["last_success_at"] = previous.get("last_success_at")
            output.append(current)
            continue

        row = {
            **previous,
            "name": name,
            "group": source.get("group"),
            "method": source.get("method"),
            "homepage": source.get("homepage"),
            "priority": int(source.get("priority") or 0),
            "status": previous.get("status") if previous.get("status") in {"ok", "empty"} else "scheduled",
            "message": (
                f"輪替來源；本輪 bucket {current_bucket + 1}/{ROTATION_BUCKETS} 未檢查"
            ),
            "check_state": "deferred",
            "item_count": int(previous.get("item_count") or 0),
            "last_checked_at": previous.get("last_checked_at"),
            "last_success_at": previous.get("last_success_at"),
        }
        output.append(row)

    output.sort(key=lambda row: (
        -int(row.get("priority") or 0),
        str(row.get("group") or ""),
        str(row.get("name") or ""),
    ))
    return output


def normalize_archive_items(items: list[dict]) -> list[dict]:
    cutoff = NOW - timedelta(days=RETENTION_DAYS)
    dedup: dict[str, dict] = {}

    for raw in items:
        title = clean_text(raw.get("title"))
        link = str(raw.get("link") or raw.get("article_link") or "").strip()
        if not title or not link.startswith(("http://", "https://")):
            continue
        published = parse_time(raw.get("published_at"))
        if published < cutoff or published > NOW + timedelta(hours=3):
            continue

        row = {
            **raw,
            "title": title,
            "link": link,
            "published_at": published.isoformat(timespec="seconds"),
        }
        if row.get("importance_score") is None:
            row["importance_score"] = importance_score(
                title,
                clean_text(row.get("summary")),
                str(row.get("source_group") or ""),
                0,
            )

        key = f"{normalized_title(title)}|{row.get('source') or ''}"
        existing = dedup.get(key)
        if not existing or published > parse_time(existing.get("published_at")):
            dedup[key] = row

    return sorted(
        dedup.values(),
        key=lambda row: (
            str(row.get("published_at") or ""),
            int(row.get("importance_score") or 0),
        ),
        reverse=True,
    )


def discovered_source_statuses(items: list[dict], configured_names: set[str]) -> list[dict]:
    counts: dict[str, int] = defaultdict(int)
    for item in items:
        source = str(item.get("source") or "").strip()
        if source and source not in configured_names:
            counts[source] += 1
    return [{
        "name": name,
        "group": "discovered",
        "method": "broad-google",
        "homepage": None,
        "priority": 0,
        "status": "discovered",
        "message": f"廣域搜尋發現 · {count} 筆",
        "item_count": count,
        "last_checked_at": NOW.isoformat(timespec="seconds"),
        "last_success_at": NOW.isoformat(timespec="seconds"),
    } for name, count in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))]


def main() -> None:
    started = time.monotonic()
    DATA.mkdir(parents=True, exist_ok=True)
    configured = load_registry()
    previous = load_previous()
    current_bucket = int(NOW.timestamp() // 300) % ROTATION_BUCKETS
    scheduled = [source for source in configured if should_check(source, current_bucket)]

    collected: list[dict] = []
    statuses: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {
            executor.submit(fetch_source, source): source
            for source in scheduled
        }
        for future in as_completed(future_map):
            source = future_map[future]
            try:
                items, status = future.result()
            except Exception as exc:
                items = []
                status = source_status(
                    source, "warning", f"Unhandled {type(exc).__name__}: {exc}"
                )
            collected.extend(items)
            statuses.append(status)

    merged_raw = normalize_archive_items([
        *(previous.get("items") or []),
        *collected,
    ])
    clustered = cluster_news(merged_raw)
    final_items = interleave_sources(clustered)
    if not final_items:
        raise SystemExit("No usable news items; previous archive was not replaced.")

    configured_statuses = merge_source_status(
        configured,
        statuses,
        previous.get("sources") or [],
        current_bucket,
    )
    configured_names = {source["name"] for source in configured}
    discovered = discovered_source_statuses(final_items, configured_names)
    all_statuses = [*configured_statuses, *discovered]

    active_sources = {
        str(item.get("source") or "").strip()
        for item in final_items
        if item.get("source")
    }
    healthy = sum(1 for row in configured_statuses if row.get("status") in {"ok", "empty"})
    warnings = sum(1 for row in configured_statuses if row.get("status") == "warning")
    material_count = sum(1 for item in final_items if item.get("topic") == "material")
    elapsed = time.monotonic() - started

    payload = {
        "metadata": {
            "version": "v11.2.7",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "timezone": "Asia/Taipei",
            "retention_days": RETENTION_DAYS,
            "item_count": len(final_items),
            "raw_item_count": len(merged_raw),
            "clustered_item_count": len(final_items),
            "material_item_count": material_count,
            "configured_source_count": len(configured),
            "checked_source_count": len(scheduled),
            "healthy_source_count": healthy,
            "warning_source_count": warnings,
            "active_source_count": len(active_sources),
            "discovered_source_count": len(discovered),
            "rotation_bucket": current_bucket + 1,
            "rotation_buckets": ROTATION_BUCKETS,
            "elapsed_seconds": round(elapsed, 3),
            "note": (
                "Taiwan-focused official, publisher, technology, broker and fund-house "
                "archive. Official material information and priority publishers update "
                "every run; long-tail sources rotate across four buckets."
            ),
        },
        "sources": all_statuses,
        "items": final_items,
    }
    OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    SEED.write_text(
        "window.__NEWS_SEED__ = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "news": len(final_items),
        "material": material_count,
        "configured_sources": len(configured),
        "checked_sources": len(scheduled),
        "active_sources": len(active_sources),
        "warnings": warnings,
        "seconds": round(elapsed, 3),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
