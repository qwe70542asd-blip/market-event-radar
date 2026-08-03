#!/usr/bin/env python3
"""Refresh a rolling, multi-source finance-news archive.

Direct publisher feeds/pages are preferred. Broker and research-house coverage is
supplemented with tightly scoped Google News RSS queries. A failed run never
replaces the last successful archive with an empty payload.
"""
from __future__ import annotations

import hashlib
from collections import defaultdict
import html
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "news.json"
SEED = DATA / "news-seed.js"
TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime.now(TAIPEI)
RETENTION_DAYS = 20
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.1; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
}

RSS_SOURCES = [
    ("Yahoo 股市", "portal", "https://tw.stock.yahoo.com/rss?category=news"),
    ("Yahoo 台股", "portal", "https://tw.stock.yahoo.com/rss?category=tw-market"),
    ("Yahoo 國際股市", "portal", "https://tw.stock.yahoo.com/rss?category=intl-markets"),
    ("Yahoo ETF／基金", "portal", "https://tw.stock.yahoo.com/rss?category=funds-news"),
    ("鉅亨網台股", "publisher", "https://m.cnyes.com/news/cat/tw_stock_news?type=rss"),
    ("鉅亨網國際", "publisher", "https://m.cnyes.com/news/cat/wd_stock?type=rss"),
]

BROKER_QUERIES = [
    ("永豐金證券", "broker", 'site:sinotrade.com.tw (台股 OR 美股 OR ETF OR 財經)'),
    ("元大投顧／元大證券", "broker", 'site:yuanta-consulting.com.tw OR site:yuanta.com.tw (台股 OR 美股 OR 財經)'),
    ("國泰證券", "broker", 'site:cathaysec.com.tw (台股 OR 美股 OR ETF OR 財經)'),
    ("凱基投顧／凱基證券", "broker", 'site:kgieworld.com.tw OR site:kgi.com.tw (台股 OR 美股 OR 財經)'),
    ("富邦投顧／富邦證券", "broker", 'site:fubon.com/securities OR site:fubon.com/asset-management (台股 OR ETF OR 財經)'),
]

TOPIC_RULES = [
    ("fund", re.compile(r"ETF|基金|淨值|折溢價|配息|成分股", re.I)),
    ("earnings", re.compile(r"財報|營收|EPS|獲利|法說|財測|季報", re.I)),
    ("policy", re.compile(r"央行|聯準會|利率|CPI|PPI|PMI|關稅|政策|選舉|制裁", re.I)),
    ("crypto", re.compile(r"比特幣|以太坊|加密|虛擬貨幣|區塊鏈|Bitcoin|Ethereum", re.I)),
]
REGION_RULES = [
    ("TW", re.compile(r"台股|台灣|上市|上櫃|新台幣|證交所|櫃買", re.I)),
    ("US", re.compile(r"美股|美國|聯準會|那斯達克|道瓊|標普|NASDAQ|S&P", re.I)),
    ("JP", re.compile(r"日股|日本|日銀|日圓|東證|日經", re.I)),
    ("KR", re.compile(r"韓股|韓國|三星|KOSPI", re.I)),
    ("EU", re.compile(r"歐股|歐洲|ECB|歐洲央行|德國|英國|法國", re.I)),
]


def clean_text(value: object) -> str:
    soup = BeautifulSoup(html.unescape(str(value or "")), "html.parser")
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def normalized_title(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value.lower())


def canonical_cluster_key(item: dict) -> str:
    """Create a conservative event identity and collapse repeated ranking templates."""
    title = clean_text(item.get("title"))
    published = str(item.get("published_at") or "")[:10]
    cleaned = re.sub(r"【[^】]{0,30}】|\\[[^\\]]{0,30}\\]", " ", title)
    cleaned = re.sub(r"\\b(?:Yahoo|MoneyDJ|鉅亨網|證交所|臺灣證券交易所)\\b", " ", cleaned, flags=re.I)
    # MoneyDJ and similar sites often publish many nearly identical top-20 cards
    # at the same timestamp. Keep one representative and preserve the rest as
    # related links rather than filling an entire screen with one template.
    if re.search(r"(?:排行|排名).*?(?:前|Top)\\s*\\d+\\s*名", cleaned, flags=re.I):
        market = "上市" if "上市" in cleaned else "上櫃" if "上櫃" in cleaned else "市場"
        family = "法人籌碼" if re.search(r"外資|投信|自營商|融資|融券|借券", cleaned) else "市場排行"
        return f"template:{published}:{market}:{family}"
    normalized = normalized_title(cleaned)
    return f"exact:{normalized}"


def source_priority(item: dict) -> int:
    group = str(item.get("source_group") or "")
    return {"official-tw": 5, "official": 5, "publisher": 4, "broker": 3, "portal": 2}.get(group, 1)


def cluster_news(items: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        groups[canonical_cluster_key(item)].append(item)

    clustered = []
    for cluster_id, rows in groups.items():
        rows.sort(key=lambda row: (
            source_priority(row),
            bool(row.get("summary")),
            str(row.get("published_at") or ""),
        ), reverse=True)
        primary = dict(rows[0])
        sources = []
        links = []
        for row in rows:
            source = str(row.get("source") or "其他來源")
            if source not in sources:
                sources.append(source)
            link = row.get("pdf_link") or row.get("article_link") or row.get("direct_link") or row.get("link")
            if link and all(existing.get("link") != link for existing in links):
                links.append({"source": source, "title": row.get("title"), "link": link})
        primary["cluster_id"] = hashlib.sha1(cluster_id.encode("utf-8")).hexdigest()[:16]
        primary["duplicate_count"] = max(0, len(rows) - 1)
        primary["related_sources"] = sources
        primary["related_links"] = links[:12]
        clustered.append(primary)
    return clustered


def interleave_sources(items: list[dict]) -> list[dict]:
    queues: dict[str, list[dict]] = defaultdict(list)
    for item in sorted(items, key=lambda row: str(row.get("published_at") or ""), reverse=True):
        queues[str(item.get("source") or "其他來源")].append(item)
    result = []
    last_source = None
    while any(queues.values()):
        candidates = [(source, queue) for source, queue in queues.items() if queue and source != last_source]
        if not candidates:
            candidates = [(source, queue) for source, queue in queues.items() if queue]
        source, queue = max(candidates, key=lambda row: str(row[1][0].get("published_at") or ""))
        result.append(queue.pop(0))
        last_source = source
    return result


def parsed_time(entry: dict) -> datetime:
    for key in ("published", "updated", "pubDate"):
        value = entry.get(key)
        if not value:
            continue
        try:
            dt = dateparser.parse(str(value))
            if not dt.tzinfo:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(TAIPEI)
        except Exception:
            pass
    struct = entry.get("published_parsed") or entry.get("updated_parsed")
    if struct:
        try:
            return datetime(*struct[:6], tzinfo=timezone.utc).astimezone(TAIPEI)
        except Exception:
            pass
    return NOW


def classify(title: str, summary: str) -> tuple[str, str]:
    text = f"{title} {summary}"
    topic = "market"
    for candidate, pattern in TOPIC_RULES:
        if pattern.search(text):
            topic = candidate
            break
    region = "GLOBAL"
    for candidate, pattern in REGION_RULES:
        if pattern.search(text):
            region = candidate
            break
    return topic, region


def stable_id(source: str, title: str, link: str) -> str:
    return hashlib.sha1(f"{source}|{title}|{link}".encode("utf-8")).hexdigest()[:16]


def publisher_from_link(link: str, fallback: str) -> str:
    host = urlparse(link).hostname or ""
    host = host.lower().replace("www.", "")
    known = {
        "news.cnyes.com": "鉅亨網",
        "m.cnyes.com": "鉅亨網",
        "tw.stock.yahoo.com": "Yahoo 股市",
        "moneydj.com": "MoneyDJ",
        "www.moneydj.com": "MoneyDJ",
        "sinotrade.com.tw": "永豐金證券",
        "www.sinotrade.com.tw": "永豐金證券",
        "yuanta-consulting.com.tw": "元大投顧",
        "cathaysec.com.tw": "國泰證券",
        "kgieworld.com.tw": "凱基證券",
    }
    return known.get(host, fallback)


def resolve_google_link(session: requests.Session, link: str) -> str:
    """Best-effort publisher URL resolution. A Google News URL remains valid if resolution fails."""
    if "news.google.com" not in link:
        return link
    try:
        response = session.get(link, headers=HEADERS, timeout=12, allow_redirects=True)
        final = response.url
        if "news.google.com" not in final:
            return final
        soup = BeautifulSoup(response.text, "html.parser")
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href") and "news.google.com" not in canonical["href"]:
            return canonical["href"]
    except Exception:
        pass
    return link


def resolve_official_article(session: requests.Session, link: str) -> tuple[str, str | None]:
    """Turn official JSON-detail endpoints into readable article/PDF links."""
    parsed = urlparse(link)
    host = (parsed.hostname or "").lower()
    if host.endswith("twse.com.tw") and re.search(r"/rwd/(?:zh|en)/news/newsDetail/", parsed.path, re.I):
        human = re.sub(r"/rwd/(zh|en)/news/newsDetail/", r"/\1/news/newsDetail/", link, flags=re.I)
        try:
            response = session.get(link, headers=HEADERS, timeout=15)
            response.raise_for_status()
            payload = response.json()
            for table in payload.get("tables") or []:
                fields = table.get("fields") or []
                for data in table.get("data") or []:
                    row = dict(zip(fields, data))
                    pdf = str(row.get("pdf") or "").strip()
                    html_path = str(row.get("html") or "").strip()
                    if pdf:
                        return human, requests.compat.urljoin("https://www.twse.com.tw", pdf)
                    if html_path and html_path.startswith(("http://", "https://")):
                        return html_path, None
        except Exception:
            pass
        return human, None
    return link, None


def entry_to_item(entry: dict, source: str, group: str, session: requests.Session, resolve_links: bool = False) -> dict | None:
    title = clean_text(entry.get("title"))
    link = str(entry.get("link") or "").strip()
    summary = clean_text(entry.get("summary") or entry.get("description") or "")
    if not title or not link.startswith(("http://", "https://")):
        return None
    if resolve_links:
        link = resolve_google_link(session, link)
    article_link, pdf_link = resolve_official_article(session, link)
    published = parsed_time(entry)
    topic, region = classify(title, summary)
    actual_source = publisher_from_link(article_link, source)
    return {
        "id": stable_id(actual_source, title, link),
        "title": title,
        "summary": summary[:700],
        "source": actual_source,
        "source_group": group,
        "link": article_link,
        "direct_link": article_link,
        "article_link": article_link,
        "pdf_link": pdf_link,
        "published_at": published.isoformat(timespec="seconds"),
        "topic": topic,
        "region": region,
        "asset_class": "fund" if topic == "fund" else "crypto" if topic == "crypto" else "stock",
        "tags": [],
    }


def fetch_feed(session: requests.Session, name: str, group: str, url: str, resolve_links: bool = False) -> tuple[list[dict], dict]:
    status = {"name": name, "group": group, "status": "warning", "message": "抓取失敗"}
    try:
        response = session.get(url, headers=HEADERS, timeout=25)
        response.raise_for_status()
        feed = feedparser.loads(response.content)
        items = []
        for entry in feed.entries[:80]:
            item = entry_to_item(entry, name, group, session, resolve_links)
            if item:
                items.append(item)
        status.update(status="ok" if items else "warning", message=f"{len(items)} 筆")
        return items, status
    except Exception as exc:
        status["message"] = str(exc)[:120]
        return [], status


def fetch_moneydj(session: requests.Session) -> tuple[list[dict], dict]:
    name, group = "MoneyDJ", "publisher"
    url = "https://www.moneydj.com/kmdj/common/listnewarticles.aspx?a=X1500001&svc=NW"
    status = {"name": name, "group": group, "status": "warning", "message": "抓取失敗"}
    try:
        response = session.get(url, headers=HEADERS, timeout=25)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        items = []
        for anchor in soup.select('a[href*="/KMDJ/News/NewsViewer.aspx"], a[href*="/news/"]'):
            title = clean_text(anchor.get_text(" ", strip=True))
            href = anchor.get("href") or ""
            if len(title) < 8:
                continue
            link = requests.compat.urljoin(url, href)
            topic, region = classify(title, "")
            item = {
                "id": stable_id(name, title, link), "title": title, "summary": "",
                "source": name, "source_group": group, "link": link, "direct_link": link,
                "published_at": NOW.isoformat(timespec="seconds"), "topic": topic, "region": region,
                "asset_class": "fund" if topic == "fund" else "stock", "tags": [],
            }
            items.append(item)
        unique = {normalized_title(item["title"]): item for item in items}
        items = list(unique.values())[:60]
        status.update(status="ok" if items else "warning", message=f"{len(items)} 筆")
        return items, status
    except Exception as exc:
        status["message"] = str(exc)[:120]
        return [], status


def row_value(row: dict, *needles: str):
    normalized = {re.sub(r"[\s_\\-]+", "", str(key)).lower(): value for key, value in row.items()}
    for needle in needles:
        target = re.sub(r"[\s_\\-]+", "", needle).lower()
        if target in normalized and normalized[target] not in (None, ""):
            return normalized[target]
    for key, value in normalized.items():
        if value not in (None, "") and any(re.sub(r"[\s_\\-]+", "", needle).lower() in key for needle in needles):
            return value
    return None


def fetch_twse_news(session: requests.Session) -> tuple[list[dict], dict]:
    name, group = "臺灣證券交易所", "official-tw"
    status = {"name": name, "group": group, "status": "warning", "message": "抓取失敗"}
    try:
        response = session.get("https://openapi.twse.com.tw/v1/news/newsList", headers=HEADERS, timeout=25)
        response.raise_for_status()
        payload = response.json()
        rows = payload if isinstance(payload, list) else payload.get("data") or []
        items = []
        for row in rows[:100]:
            if not isinstance(row, dict):
                continue
            title = clean_text(row_value(row, "title", "subject", "head_text", "標題", "主旨"))
            uid = str(row_value(row, "id", "uuid", "seqno", "編號") or "").strip()
            summary = clean_text(row_value(row, "summary", "content", "text", "說明") or "")
            date_value = str(row_value(row, "date", "datetime", "發布時間", "時間") or "")
            if not title:
                continue
            published = NOW
            try:
                digits = re.sub(r"\D", "", date_value)
                if len(digits) >= 12:
                    published = datetime.strptime(digits[:12], "%Y%m%d%H%M").replace(tzinfo=TAIPEI)
                elif date_value:
                    parsed = dateparser.parse(date_value)
                    if not parsed.tzinfo:
                        parsed = parsed.replace(tzinfo=TAIPEI)
                    published = parsed.astimezone(TAIPEI)
            except Exception:
                pass
            api_link = f"https://www.twse.com.tw/rwd/zh/news/newsDetail/{uid}" if uid else "https://www.twse.com.tw/zh/about/news/news/list.html"
            article_link, pdf_link = resolve_official_article(session, api_link)
            topic, region = classify(title, summary)
            items.append({
                "id": stable_id(name, title, article_link),
                "title": title, "summary": summary[:700], "source": name,
                "source_group": group, "link": article_link, "direct_link": article_link,
                "article_link": article_link, "pdf_link": pdf_link,
                "published_at": published.isoformat(timespec="seconds"),
                "topic": topic, "region": region if region != "GLOBAL" else "TW",
                "asset_class": "fund" if topic == "fund" else "stock", "tags": ["official", "official-tw"],
            })
        status.update(status="ok" if items else "warning", message=f"{len(items)} 筆")
        return items, status
    except Exception as exc:
        status["message"] = str(exc)[:120]
        return [], status


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
        return datetime(year, month, day, int(time_digits[:2]), int(time_digits[2:4]), int(time_digits[4:6]), tzinfo=TAIPEI)
    except Exception:
        return NOW


def fetch_company_announcements(session: requests.Session) -> tuple[list[dict], list[dict]]:
    sources = [
        ("上市公司重大訊息", "https://openapi.twse.com.tw/v1/opendata/t187ap04_L", "TWSE"),
        ("上櫃公司重大訊息", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O", "TPEx"),
    ]
    items: list[dict] = []
    statuses: list[dict] = []
    for source_name, url, market in sources:
        status = {"name": source_name, "group": "official-company", "status": "warning", "message": "抓取失敗"}
        try:
            response = session.get(url, headers=HEADERS, timeout=35)
            response.raise_for_status()
            payload = response.json()
            rows = payload if isinstance(payload, list) else payload.get("data") or []
            count = 0
            for row in rows[:500]:
                if not isinstance(row, dict):
                    continue
                code = str(row_value(row, "公司代號", "證券代號", "股票代號") or "").strip().upper()
                company = clean_text(row_value(row, "公司簡稱", "公司名稱", "證券名稱") or "")
                subject = clean_text(row_value(row, "主旨", "重大訊息主旨", "subject", "title") or "")
                explanation = clean_text(row_value(row, "說明", "內容", "content") or "")
                date_value = row_value(row, "發言日期", "發布日期", "日期", "date")
                time_value = row_value(row, "發言時間", "發布時間", "時間", "time")
                if not code or not subject:
                    continue
                published = parse_roc_datetime(date_value, time_value)
                title = f"{company}（{code}）{subject}" if company and company not in subject else f"{code} {subject}"
                link = "https://mops.twse.com.tw/mops/web/t05st01"
                items.append({
                    "id": stable_id(source_name, title, f"{date_value}-{time_value}-{code}"),
                    "title": title,
                    "summary": explanation[:900],
                    "source": "公開資訊觀測站",
                    "source_group": "official-company",
                    "link": link,
                    "direct_link": link,
                    "article_link": link,
                    "pdf_link": None,
                    "published_at": published.isoformat(timespec="seconds"),
                    "topic": "earnings" if re.search(r"財報|營收|獲利|股利|法說", subject) else "market",
                    "region": "TW",
                    "asset_class": "stock",
                    "asset_symbols": [code],
                    "tags": [code, company, market, "重大訊息", "official-company"],
                })
                count += 1
            status.update(status="ok" if count else "warning", message=f"{count} 筆")
        except Exception as exc:
            status["message"] = str(exc)[:120]
        statuses.append(status)
    return items, statuses


def google_news_url(query_text: str) -> str:
    return f"https://news.google.com/rss/search?q={quote(query_text)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"


def load_previous() -> dict:
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {"items": [], "sources": []}


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    previous = load_previous()
    session = requests.Session()
    collected: list[dict] = []
    statuses: list[dict] = []

    for source in RSS_SOURCES:
        items, status = fetch_feed(session, *source)
        collected.extend(items)
        statuses.append(status)
        time.sleep(0.25)

    items, status = fetch_moneydj(session)
    collected.extend(items)
    statuses.append(status)

    items, status = fetch_twse_news(session)
    collected.extend(items)
    statuses.append(status)

    company_items, company_statuses = fetch_company_announcements(session)
    collected.extend(company_items)
    statuses.extend(company_statuses)

    for name, group, query_text in BROKER_QUERIES:
        items, status = fetch_feed(session, name, group, google_news_url(query_text), resolve_links=True)
        collected.extend(items)
        statuses.append(status)
        time.sleep(0.25)

    cutoff = NOW - timedelta(days=RETENTION_DAYS)
    merged = [*(previous.get("items") or []), *collected]
    dedup: dict[str, dict] = {}
    for item in merged:
        title = clean_text(item.get("title"))
        if not title:
            continue
        try:
            published = dateparser.parse(str(item.get("published_at") or ""))
            if not published.tzinfo:
                published = published.replace(tzinfo=TAIPEI)
            published = published.astimezone(TAIPEI)
        except Exception:
            published = NOW
        if published < cutoff or published > NOW + timedelta(hours=2):
            continue
        item = {**item, "title": title, "published_at": published.isoformat(timespec="seconds")}
        key = normalized_title(title)
        existing = dedup.get(key)
        if not existing or published > dateparser.parse(existing["published_at"]):
            dedup[key] = item

    raw_items = sorted(dedup.values(), key=lambda row: row["published_at"], reverse=True)
    items = interleave_sources(cluster_news(raw_items))
    if not items:
        raise SystemExit("No usable news items; previous live archive was not replaced.")

    status_by_name = {row["name"]: row for row in (previous.get("sources") or [])}
    status_by_name.update({row["name"]: row for row in statuses})
    payload = {
        "metadata": {
            "version": "v11.1.5",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "timezone": "Asia/Taipei",
            "retention_days": RETENTION_DAYS,
            "item_count": len(items),
            "raw_item_count": len(raw_items),
            "clustered_item_count": len(items),
            "source_count": len(status_by_name),
            "note": "Multi-source archive with event clustering and source interleaving; repeated ranking templates are grouped.",
        },
        "sources": list(status_by_name.values()),
        "items": items,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED.write_text("window.__NEWS_SEED__ = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    print("news", len(items), "sources", len(status_by_name))


if __name__ == "__main__":
    main()
