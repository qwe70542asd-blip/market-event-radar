#!/usr/bin/env python3
"""Build a clean v11.3.0 news feed.

Only identifiable article/announcement URLs are kept. HTML fragments are removed,
and a deterministic no-key classifier creates category, impact, direction and a short
article outline. A future AI API can replace these fields without changing the UI.
"""
from __future__ import annotations

import hashlib
import html
import re
from urllib.parse import urlsplit

import feedparser
from bs4 import BeautifulSoup

from common import DATA, NOW, read_json, write_payload

HOME_PATHS = {"", "/", "/index.html", "/index.php", "/home", "/home/", "/news", "/news/"}
LISTING_RE = re.compile(r"/(?:search|tag|tags|category|categories|topic|topics|section|sections)/?$", re.I)
SENTENCE_RE = re.compile(r"(?<=[。！？.!?])\s+")

CATEGORY_RULES = [
    ("央行與利率", "macro", re.compile(r"聯準會|Fed\b|FOMC|央行|升息|降息|利率|殖利率", re.I)),
    ("總體經濟", "macro", re.compile(r"CPI|PCE|GDP|非農|就業|失業|通膨|景氣|PMI|出口|進口", re.I)),
    ("企業財報", "earnings", re.compile(r"財報|營收|獲利|EPS|法說|展望|財測|季報|年報", re.I)),
    ("半導體與 AI", "technology", re.compile(r"AI|人工智慧|半導體|晶片|晶圓|GPU|伺服器|台積電|NVIDIA|輝達", re.I)),
    ("政策與法規", "material", re.compile(r"政策|法規|關稅|制裁|補貼|金管會|行政院|立法院|證交所|櫃買", re.I)),
    ("地緣政治", "market", re.compile(r"戰爭|衝突|軍事|地緣|停火|攻擊|選舉", re.I)),
    ("能源與原物料", "market", re.compile(r"原油|石油|天然氣|黃金|銅價|原物料|OPEC", re.I)),
    ("匯率與債券", "market", re.compile(r"美元|日圓|新台幣|匯率|債券|美債", re.I)),
    ("公司公告", "material", re.compile(r"重大訊息|公告|除權|除息|增資|減資|併購|收購|處分|取得", re.I)),
]

HIGH_RULE = re.compile(r"FOMC|聯準會|Fed\b|央行|CPI|PCE|GDP|非農|升息|降息|戰爭|制裁|關稅|崩跌|暴跌|熔斷|重大訊息|財測下修|財測上修", re.I)
MEDIUM_RULE = re.compile(r"財報|營收|法說|政策|匯率|債券|半導體|AI|原油|除權|除息|增資|減資", re.I)
POSITIVE_RULE = re.compile(r"優於預期|上修|成長|創高|大增|獲利增加|降息|擴產|訂單增加|買超|利多", re.I)
NEGATIVE_RULE = re.compile(r"低於預期|下修|衰退|虧損|暴跌|大跌|升息|制裁|關稅|減產|賣超|利空|違約", re.I)


def clean_text(value: object) -> str:
    raw = html.unescape(str(value or ""))
    text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def article_url(value: object) -> str | None:
    raw = html.unescape(str(value or "")).strip()
    if not re.match(r"^https?://", raw, re.I) or any(c in raw for c in "<>\n\r"):
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if not parts.netloc:
        return None
    path = re.sub(r"/+", "/", parts.path or "/").lower()
    # Root/home/listing links are not articles unless a query clearly identifies a record.
    query = parts.query.lower()
    has_record_query = bool(re.search(r"(?:id|newsid|article|sn|seq|document|post)=", query))
    if path in HOME_PATHS and not has_record_query:
        return None
    if LISTING_RE.search(path):
        return None
    # Google News RSS article routes are article records, not the Google News homepage.
    if "news.google." in parts.netloc.lower() and not re.search(r"/(?:rss/)?articles/", path):
        return None
    return raw


def summarize(title: str, summary: str) -> str:
    body = clean_text(summary)
    if not body:
        return title[:220]
    # Remove duplicated title and common feed boilerplate.
    body = re.sub(re.escape(title), "", body, count=1, flags=re.I).strip(" -｜|:")
    body = re.sub(r"(?:閱讀全文|繼續閱讀|更多內容|查看原文).*$", "", body, flags=re.I)
    sentences = [s.strip() for s in SENTENCE_RE.split(body) if len(s.strip()) >= 8]
    outline = " ".join(sentences[:2]) if sentences else body
    return outline[:260].strip()


def classify(title: str, summary: str, configured_topic: str) -> dict:
    text = f"{title} {summary}"
    category, ai_topic = "市場動態", configured_topic or "market"
    for label, topic, pattern in CATEGORY_RULES:
        if pattern.search(text):
            category, ai_topic = label, topic
            break
    if HIGH_RULE.search(text):
        impact = "high"
    elif MEDIUM_RULE.search(text):
        impact = "medium"
    else:
        impact = "low"
    positive, negative = bool(POSITIVE_RULE.search(text)), bool(NEGATIVE_RULE.search(text))
    direction = "多空混合" if positive and negative else "偏多" if positive else "偏空" if negative else "中性"
    affected = []
    for pattern, labels in [
        (re.compile(r"台股|證交所|櫃買|新台幣", re.I), ["台股"]),
        (re.compile(r"半導體|晶片|台積電|NVIDIA|輝達|AI", re.I), ["半導體", "科技股"]),
        (re.compile(r"美股|NASDAQ|S&P|道瓊|聯準會|Fed\b", re.I), ["美股"]),
        (re.compile(r"美元|匯率|日圓|新台幣", re.I), ["匯率"]),
        (re.compile(r"債券|美債|殖利率", re.I), ["債券"]),
        (re.compile(r"原油|石油|天然氣|黃金|銅價", re.I), ["原物料"]),
        (re.compile(r"金融|銀行|保險", re.I), ["金融股"]),
        (re.compile(r"航運|海運|運價", re.I), ["航運股"]),
    ]:
        if pattern.search(text):
            affected.extend(labels)
    affected = list(dict.fromkeys(affected))[:4] or ["整體市場"]
    confidence = "高" if impact == "high" and category != "市場動態" else "中"
    return {
        "ai_category": category,
        "ai_topic": ai_topic,
        "impact": impact,
        "market_direction": direction,
        "affected_markets": affected,
        "confidence": confidence,
        "is_major": impact == "high" or configured_topic == "material",
    }


def main() -> None:
    cfg = read_json(DATA / "news-sources.json", {"sources": []})
    old = read_json(DATA / "news.json", {"items": []})
    items, health = [], []
    for src in cfg.get("sources", []):
        try:
            feed = feedparser.parse(src["url"])
            count, rejected = 0, 0
            for entry in feed.entries[:30]:
                title = clean_text(entry.get("title"))
                url = article_url(entry.get("link"))
                raw_summary = entry.get("summary") or entry.get("description") or ""
                summary = summarize(title, raw_summary)
                if not title or not url or title.lower() in {"home", "首頁", "新聞", "news"}:
                    rejected += 1
                    continue
                analysis = classify(title, summary, src.get("topic", "market"))
                items.append({
                    "id": hashlib.sha1((title + url).encode()).hexdigest()[:16],
                    "title": title,
                    "url": url,
                    "url_valid": True,
                    "summary": summary,
                    "ai_summary": summary,
                    "source": src["name"],
                    "topic": analysis["ai_topic"],
                    "published_at": entry.get("published") or entry.get("updated") or NOW.isoformat(timespec="seconds"),
                    "symbols": [],
                    **analysis,
                })
                count += 1
            health.append({"name": src["name"], "status": "ok", "count": count, "rejected": rejected})
        except Exception as exc:  # isolate source failure
            health.append({"name": src.get("name", "unknown"), "status": "warning", "error": str(exc)})
    if not items:
        items = [x for x in old.get("items", []) if article_url(x.get("url"))]
    seen, deduped = set(), []
    for item in sorted(items, key=lambda x: str(x.get("published_at") or ""), reverse=True):
        key = re.sub(r"\W+", "", item["title"].lower())[:140]
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    payload = {
        "metadata": {
            "version": "v11.3.0",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "item_count": len(deduped),
            "major_item_count": sum(bool(x.get("is_major")) for x in deduped),
            "retention_days": 14,
            "summary_mode": "deterministic-rule-based",
            "note": "Article-only links, sanitized text, rule-based category/impact/direction/outline.",
        },
        "sources": health,
        "items": deduped[:500],
    }
    write_payload("news.json", "__NEWS_SEED__", payload)


if __name__ == "__main__":
    main()
