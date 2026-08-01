#!/usr/bin/env python3
"""Market Event Radar v10 multi-source news updater.

Design goals:
- Keep working when one publisher blocks requests or returns zero rows.
- Use language/region settings that match each source.
- Preserve the previous successful rows per source.
- Mark empty and stale sources honestly instead of reporting zero rows as OK.
- Store only headline metadata and original links.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus, urljoin
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EVENTS_PATH = DATA / "events.json"
NEWS_PATH = DATA / "news.json"
SEED_PATH = DATA / "news-seed.js"
TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime.now(TAIPEI)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/10.0; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}

DIRECT_RSS = [
    {"name":"中央社產經證券","url":"https://feeds.feedburner.com/rsscna/finance","region":"TW","topic":"market"},
    {"name":"中央社科技","url":"https://feeds.feedburner.com/rsscna/technology","region":"TW","topic":"tech"},
    {"name":"經濟日報","url":"https://money.udn.com/rssfeed/news/1001/5588/5601","region":"TW","topic":"market"},
]

SEARCH_SOURCES = [
    {"name":"Yahoo 股市","query":"site:tw.stock.yahoo.com (台股 OR 美股 OR 財報 OR ETF)","region":"TW","topic":"market","hl":"zh-TW","gl":"TW","ceid":"TW:zh-Hant"},
    {"name":"鉅亨網","query":"site:cnyes.com (台股 OR 美股 OR 央行 OR PMI OR 基金)","region":"TW","topic":"market","hl":"zh-TW","gl":"TW","ceid":"TW:zh-Hant"},
    {"name":"MoneyDJ","query":"site:moneydj.com (台股 OR 美股 OR 半導體 OR 基金)","region":"TW","topic":"tech","hl":"zh-TW","gl":"TW","ceid":"TW:zh-Hant"},
    {"name":"工商時報","query":"site:ctee.com.tw (台股 OR 產業 OR 財報 OR 基金)","region":"TW","topic":"market","hl":"zh-TW","gl":"TW","ceid":"TW:zh-Hant"},
    {"name":"Reuters","query":"site:reuters.com/markets (markets OR economy OR earnings OR tariff)","region":"GLOBAL","topic":"market","hl":"en-US","gl":"US","ceid":"US:en"},
    {"name":"CNBC","query":"site:cnbc.com (markets OR earnings OR economy OR Federal Reserve)","region":"US","topic":"market","hl":"en-US","gl":"US","ceid":"US:en"},
    {"name":"Nikkei Asia","query":"site:asia.nikkei.com (markets OR technology OR economy OR Japan)","region":"ASIA","topic":"market","hl":"en-US","gl":"US","ceid":"US:en"},
    {"name":"White House","query":"site:whitehouse.gov (tariff OR trade OR semiconductor OR executive order OR economy)","region":"US","topic":"policy","hl":"en-US","gl":"US","ceid":"US:en"},
    {"name":"PMI／ISM","query":"(ISM manufacturing PMI OR ISM services PMI OR S&P Global PMI)","region":"US","topic":"macro","hl":"en-US","gl":"US","ceid":"US:en"},
    {"name":"基金與 ETF","query":"(基金 OR ETF OR 淨值 OR 債券基金 OR 科技基金)","region":"TW","topic":"fund","hl":"zh-TW","gl":"TW","ceid":"TW:zh-Hant"},
]

BREAKING_TERMS = [
    "breaking","速報","快訊","宣布","關稅","tariff","制裁","sanction","降息","升息",
    "rate cut","rate hike","出口管制","executive order","緊急","unexpected"
]

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()

def stable_id(*parts):
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]

def iso(dt):
    return dt.astimezone(TAIPEI).isoformat(timespec="seconds")

def parse_date(value):
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TAIPEI)
        return iso(dt)
    except Exception:
        try:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TAIPEI)
            return iso(dt)
        except Exception:
            return None

def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def text_from(node, names):
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return clean(found.text)
    return ""

def parse_feed(content, source, region, topic, origin, quality_score):
    root = ET.fromstring(content)
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    rows = []
    for node in nodes[:50]:
        title = text_from(node, ["title", "{http://www.w3.org/2005/Atom}title"])
        link = text_from(node, ["link"])
        if not link:
            link_node = node.find("{http://www.w3.org/2005/Atom}link")
            if link_node is not None:
                link = clean(link_node.attrib.get("href"))
        summary = text_from(node, ["description", "summary", "{http://www.w3.org/2005/Atom}summary"])
        summary = clean(BeautifulSoup(summary, "html.parser").get_text(" "))
        pub = text_from(node, ["pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"])
        if title and link:
            lowered = title.lower()
            rows.append({
                "id": stable_id(source, link),
                "title": title,
                "link": link,
                "source": source,
                "summary": summary[:320],
                "published_at": parse_date(pub),
                "region": region,
                "topic": topic,
                "origin": origin,
                "quality_score": quality_score,
                "is_breaking": any(term.lower() in lowered for term in BREAKING_TERMS),
                "fetched_at": iso(NOW)
            })
    return rows

def get_with_retry(session, url, attempts=3, timeout=22):
    error = None
    for index in range(attempts):
        try:
            response = session.get(url, headers=HEADERS, timeout=timeout)
            response.raise_for_status()
            return response
        except Exception as exc:
            error = exc
            if index + 1 < attempts:
                time.sleep(1.2 * (index + 1))
    raise error

def google_url(source):
    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(source['query'])}&hl={source['hl']}&gl={source['gl']}&ceid={source['ceid']}"
    )

def previous_by_source(previous):
    result = {}
    for item in previous.get("items", []):
        result.setdefault(item.get("source") or "未知來源", []).append(item)
    return result

def still_recent(item, days=8):
    value = item.get("published_at")
    if not value:
        return True
    try:
        return datetime.fromisoformat(value).astimezone(TAIPEI) >= NOW - timedelta(days=days)
    except Exception:
        return True

def event_queries(events):
    rows = []
    cutoff = NOW + timedelta(days=21)
    for event in events:
        try:
            start = datetime.fromisoformat(event["start"]).astimezone(TAIPEI)
        except Exception:
            continue
        if NOW - timedelta(hours=12) <= start <= cutoff and event.get("impact") in {"high","medium"}:
            assets = " ".join(event.get("assets", [])[:3])
            rows.append((event, clean(f'{event.get("title","")} {assets} market')))
    return rows[:12]

def main():
    previous = read_json(NEWS_PATH, {"items": [], "sources": []})
    previous_map = previous_by_source(previous)
    session = requests.Session()
    items = []
    statuses = []

    for source in DIRECT_RSS:
        try:
            response = get_with_retry(session, source["url"])
            rows = parse_feed(response.content, source["name"], source["region"], source["topic"], "direct-rss", 95)
            items.extend(rows)
            statuses.append({"name":source["name"],"status":"ok" if rows else "empty","count":len(rows),"mode":"direct-rss","url":source["url"]})
        except Exception as exc:
            stale = [x for x in previous_map.get(source["name"], []) if still_recent(x)]
            for row in stale:
                row = dict(row)
                row["stale"] = True
                items.append(row)
            statuses.append({"name":source["name"],"status":"stale" if stale else "warning","count":len(stale),"mode":"direct-rss","message":str(exc)[:160]})

    for source in SEARCH_SOURCES:
        try:
            response = get_with_retry(session, google_url(source))
            rows = parse_feed(response.content, source["name"], source["region"], source["topic"], "publisher-search", 75)
            rows = rows[:14]
            if not rows:
                stale = [x for x in previous_map.get(source["name"], []) if still_recent(x)]
                for row in stale:
                    row = dict(row)
                    row["stale"] = True
                    items.append(row)
                statuses.append({"name":source["name"],"status":"stale" if stale else "empty","count":len(stale),"mode":"publisher-search"})
            else:
                items.extend(rows)
                statuses.append({"name":source["name"],"status":"ok","count":len(rows),"mode":"publisher-search"})
        except Exception as exc:
            stale = [x for x in previous_map.get(source["name"], []) if still_recent(x)]
            for row in stale:
                row = dict(row)
                row["stale"] = True
                items.append(row)
            statuses.append({"name":source["name"],"status":"stale" if stale else "warning","count":len(stale),"mode":"publisher-search","message":str(exc)[:160]})
        time.sleep(.15)

    events = read_json(EVENTS_PATH, {"events":[]}).get("events", [])
    event_source = {"hl":"zh-TW","gl":"TW","ceid":"TW:zh-Hant"}
    for event, query in event_queries(events):
        try:
            source = {**event_source, "query": query}
            response = get_with_retry(session, google_url(source), attempts=2)
            rows = parse_feed(response.content, "事件相關報導", event.get("region","GLOBAL"),
                              "earnings" if event.get("category")=="earnings" else "macro",
                              "event-search", 68)
            for row in rows[:3]:
                row["event_id"] = event.get("id")
                row["event_title"] = event.get("title")
                items.append(row)
        except Exception:
            pass

    dedup = {}
    for item in items:
        key = clean(item.get("link")) or clean(item.get("title")).lower()
        if key and key not in dedup:
            dedup[key] = item
    final = [x for x in dedup.values() if still_recent(x, days=10)]
    final.sort(key=lambda x: (
        bool(x.get("is_breaking")),
        int(x.get("quality_score") or 0),
        x.get("published_at") or ""
    ), reverse=True)

    if not final:
        final = [x for x in previous.get("items", []) if still_recent(x, days=14)]

    source_ok = sum(1 for x in statuses if x["status"] == "ok")
    payload = {
        "metadata": {
            "updated_at": iso(NOW),
            "timezone": "Asia/Taipei",
            "item_count": len(final[:180]),
            "healthy_sources": source_ok,
            "source_count": len(statuses),
            "version": "v10",
            "note": "Headlines, short summaries and original links only."
        },
        "source": {
            "name": "多來源財經新聞",
            "status": "ok" if final else "warning",
            "message": "" if final else "No new or cached headlines were available."
        },
        "sources": statuses,
        "items": final[:180]
    }
    NEWS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED_PATH.write_text("window.__MARKET_NEWS_SEED__ = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"Wrote {len(payload['items'])} items; healthy sources {source_ok}/{len(statuses)}")

if __name__ == "__main__":
    main()
