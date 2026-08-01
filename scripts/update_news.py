#!/usr/bin/env python3
"""Aggregate event-related and general financial news from multiple sources.

Sources:
- Direct RSS: CNA finance/technology and Economic Daily RSS (best effort)
- Direct public pages: MoneyDJ latest news (headline links only)
- Google News RSS searches constrained to named publishers as fallback

Only title, short summary, source and original link are stored.
"""
from __future__ import annotations
import argparse, hashlib, html, json, os, re, sys, time
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
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/2.0; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
}

DIRECT_RSS = [
    ("中央社產經證券", "https://feeds.feedburner.com/rsscna/finance", "TW", "market"),
    ("中央社科技", "https://feeds.feedburner.com/rsscna/technology", "TW", "tech"),
    ("經濟日報", "https://money.udn.com/rssfeed/news/1001/5588/5601", "TW", "market"),
]
PUBLISHER_QUERIES = [
    ("Yahoo 股市", "site:tw.stock.yahoo.com 台股 OR 美股 OR 財報", "TW", "market"),
    ("鉅亨網", "site:cnyes.com 台股 OR 美股 OR 央行", "TW", "market"),
    ("MoneyDJ", "site:moneydj.com 台股 OR 美股 OR 半導體", "TW", "tech"),
    ("工商時報", "site:ctee.com.tw 台股 OR 產業 OR 財報", "TW", "market"),
    ("Reuters", "site:reuters.com markets economy earnings", "GLOBAL", "market"),
    ("CNBC", "site:cnbc.com markets earnings economy", "US", "market"),
    ("Nikkei Asia", "site:asia.nikkei.com markets technology economy", "ASIA", "market"),
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
        if dt.tzinfo is None: dt = dt.replace(tzinfo=TAIPEI)
        return iso(dt)
    except Exception:
        try:
            return iso(datetime.fromisoformat(value))
        except Exception:
            return None

def read_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except Exception: return default

def text_from(node, names):
    for name in names:
        found = node.find(name)
        if found is not None and found.text:
            return clean(found.text)
    return ""

def parse_feed(content, source, region, topic):
    root = ET.fromstring(content)
    nodes = root.findall(".//item")
    if not nodes:
        nodes = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    rows = []
    for node in nodes[:30]:
        title = text_from(node, ["title", "{http://www.w3.org/2005/Atom}title"])
        link = text_from(node, ["link"])
        if not link:
            link_node = node.find("{http://www.w3.org/2005/Atom}link")
            if link_node is not None: link = clean(link_node.attrib.get("href"))
        summary = text_from(node, ["description", "summary", "{http://www.w3.org/2005/Atom}summary"])
        summary = clean(BeautifulSoup(summary, "html.parser").get_text(" "))
        pub = text_from(node, ["pubDate", "published", "updated", "{http://www.w3.org/2005/Atom}published", "{http://www.w3.org/2005/Atom}updated"])
        if title and link:
            rows.append({
                "id": stable_id(source, link),
                "title": title, "link": link, "source": source,
                "summary": summary[:260], "published_at": parse_date(pub),
                "region": region, "topic": topic, "origin": "direct-rss"
            })
    return rows

def fetch_direct_rss(session):
    items, statuses = [], []
    for source, url, region, topic in DIRECT_RSS:
        try:
            r = session.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            rows = parse_feed(r.content, source, region, topic)
            items.extend(rows)
            statuses.append({"name": source, "status": "ok", "count": len(rows), "url": url})
        except Exception as exc:
            statuses.append({"name": source, "status": "warning", "count": 0, "url": url, "message": str(exc)[:120]})
    return items, statuses

def fetch_google_query(session, source, query, region, topic):
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    r = session.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    rows = parse_feed(r.content, source, region, topic)
    for row in rows:
        row["origin"] = "publisher-search"
    return rows

def fetch_moneydj(session):
    url = "https://www.moneydj.com/KMDJ/News/NewsRealList.aspx"
    rows = []
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a[href]"):
            title = clean(a.get_text(" "))
            href = a.get("href", "")
            if len(title) < 12 or "news" not in href.lower():
                continue
            link = urljoin(url, href)
            rows.append({
                "id": stable_id("MoneyDJ", link), "title": title, "link": link,
                "source": "MoneyDJ", "summary": "", "published_at": None,
                "region": "TW", "topic": "market", "origin": "direct-page"
            })
            if len(rows) >= 18: break
    except Exception:
        pass
    return rows

def event_queries(events):
    now = NOW - timedelta(hours=12)
    cutoff = NOW + timedelta(days=30)
    queries = []
    for event in events:
        try: start = datetime.fromisoformat(event["start"]).astimezone(TAIPEI)
        except Exception: continue
        if now <= start <= cutoff and event.get("impact") in {"high", "medium"}:
            assets = " ".join(event.get("assets", [])[:2])
            queries.append((event, clean(f'{event.get("title","")} {assets} 市場')))
    return queries[:10]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    previous = read_json(NEWS_PATH, {"items": [], "sources": []})
    if args.offline:
        print(f"Offline: kept {len(previous.get('items', []))} items")
        return 0

    session = requests.Session()
    items, statuses = fetch_direct_rss(session)
    items.extend(fetch_moneydj(session))

    for source, query, region, topic in PUBLISHER_QUERIES:
        try:
            rows = fetch_google_query(session, source, query, region, topic)
            items.extend(rows[:10])
            statuses.append({"name": source, "status": "ok", "count": len(rows[:10]), "mode": "publisher-search"})
        except Exception as exc:
            statuses.append({"name": source, "status": "warning", "count": 0, "message": str(exc)[:120]})
        time.sleep(.2)

    events = read_json(EVENTS_PATH, {"events": []}).get("events", [])
    for event, query in event_queries(events):
        try:
            rows = fetch_google_query(session, "事件相關報導", query, event.get("region","GLOBAL"), "earnings" if event.get("category")=="earnings" else "macro")
            for row in rows[:3]:
                row["event_id"] = event.get("id")
                row["event_title"] = event.get("title")
            items.extend(rows[:3])
        except Exception:
            pass
        time.sleep(.15)

    dedup = {}
    for item in items:
        key = clean(item.get("link")) or clean(item.get("title")).lower()
        if key and key not in dedup:
            dedup[key] = item
    final = list(dedup.values())
    final.sort(key=lambda x: x.get("published_at") or "", reverse=True)

    if not final:
        final = previous.get("items", [])
    payload = {
        "metadata": {
            "updated_at": iso(NOW),
            "timezone": "Asia/Taipei",
            "item_count": len(final),
            "note": "Multi-source finance headlines. Titles and links remain property of original publishers."
        },
        "source": {"name": "多來源財經新聞", "status": "ok" if final else "warning", "message": ""},
        "sources": statuses,
        "items": final[:120]
    }
    NEWS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED_PATH.write_text("window.__MARKET_NEWS_SEED__ = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n", encoding="utf-8")
    print(f"Wrote {len(payload['items'])} items from {len(statuses)} sources")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
