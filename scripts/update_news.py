#!/usr/bin/env python3
"""Build the v11.4.2 final market/news feed with compact summaries and structured company notices.

Rules in this stage:
- keep only identifiable direct articles or direct announcement records;
- reject home, search, category, download-centre and generic portal pages;
- resolve Google News RSS article redirects before publishing;
- strip HTML and site-name suffixes;
- rewrite company-announcement titles when enough facts are present;
- keep ordinary company announcements out of the market-wide major section;
- never replace a valid archive with an empty result.
"""
from __future__ import annotations

import base64
import hashlib
import html
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit, urlunsplit

import feedparser
import requests
from bs4 import BeautifulSoup

from common import DATA, NOW, read_json, write_payload

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.4.2)"}
HOME_PATHS = {"", "/", "/index.html", "/index.php", "/home", "/home/", "/news", "/news/"}
LISTING_RE = re.compile(r"/(?:search|tag|tags|category|categories|topic|topics|section|sections|list|lists|download|downloads)/?$", re.I)
GENERIC_TITLE_RE = re.compile(
    r"^(?:公文公告|公告查詢|證交所新聞|櫃買中心公告|新聞中心|最新消息|上市公司\s*\[[^\]]+\]\s*除權除息|上櫃公司\s*\[[^\]]+\]\s*除權除息|公告|新聞)$",
    re.I,
)
SITE_SUFFIX_RE = re.compile(
    r"\s*(?:[-｜|]\s*)?(?:twse\.com\.tw|tpex\.org\.tw|臺灣證券交易所|台灣證券交易所|櫃買中心|Yahoo(?:奇摩)?股市|Google News)\s*$",
    re.I,
)
SENTENCE_RE = re.compile(r"(?<=[。！？.!?])\s+")
COMPANY_CODE_RE = re.compile(r"(?<!\d)(\d{4}|00\d{4}|00\d{3}[A-Z])(?!\d)", re.I)
COMPANY_EVENT_RE = re.compile(
    r"現金增資|增資|減資|除權|除息|股利|法說|財報|財務報告|股東會|停牌|復牌|公開收購|併購|合併|處分資產|取得資產|重大合約|融資融券|注意股票|處置股票",
    re.I,
)
MARKET_WIDE_RE = re.compile(
    r"FOMC|聯準會|Fed\b|央行|CPI|PCE|GDP|非農|JOLTS|PMI|利率決策|升息|降息|關稅|制裁|戰爭|金融危機|熔斷|交易制度|證交稅|最低工資|重大法規",
    re.I,
)
HIGH_RE = re.compile(r"FOMC|聯準會|Fed\b|央行|CPI|PCE|GDP|非農|升息|降息|戰爭|制裁|關稅|崩跌|暴跌|熔斷|金融危機", re.I)
MEDIUM_RE = re.compile(r"財報|營收|法說|政策|匯率|債券|半導體|AI|原油|除權|除息|增資|減資|融資融券", re.I)
POSITIVE_RE = re.compile(r"優於預期|上修|成長|創高|大增|獲利增加|降息|擴產|訂單增加|買超|利多", re.I)
NEGATIVE_RE = re.compile(r"低於預期|下修|衰退|虧損|暴跌|大跌|升息|制裁|關稅|減產|賣超|利空|違約", re.I)

CATEGORY_RULES = [
    ("央行與利率", "macro", re.compile(r"聯準會|Fed\b|FOMC|央行|升息|降息|利率|殖利率", re.I)),
    ("總體經濟", "macro", re.compile(r"CPI|PCE|GDP|非農|JOLTS|就業|失業|通膨|景氣|PMI|出口|進口", re.I)),
    ("企業財報", "earnings", re.compile(r"財報|營收|獲利|EPS|法說|展望|財測|季報|年報", re.I)),
    ("半導體與 AI", "technology", re.compile(r"AI|人工智慧|半導體|晶片|晶圓|GPU|伺服器|台積電|NVIDIA|輝達", re.I)),
    ("政策與法規", "policy", re.compile(r"政策|法規|關稅|制裁|補貼|金管會|行政院|立法院|交易制度", re.I)),
    ("地緣政治", "geopolitics", re.compile(r"戰爭|衝突|軍事|地緣|停火|攻擊|選舉", re.I)),
    ("能源與原物料", "commodities", re.compile(r"原油|石油|天然氣|黃金|銅價|原物料|OPEC", re.I)),
    ("匯率與債券", "rates", re.compile(r"美元|日圓|新台幣|韓元|匯率|債券|美債", re.I)),
    ("個股公告", "company", COMPANY_EVENT_RE),
]

ASSET_ALIAS_MAP: dict[str, str] = {}
EVENT_TERM_RULES = [
    (re.compile(r"JOLTS|職缺|離職率", re.I), ["JOLTS", "職缺", "離職率"]),
    (re.compile(r"CPI|消費者物價", re.I), ["CPI", "消費者物價"]),
    (re.compile(r"PCE|個人消費支出", re.I), ["PCE", "個人消費支出"]),
    (re.compile(r"FOMC|聯準會|Fed\b", re.I), ["FOMC", "聯準會", "Fed"]),
    (re.compile(r"日本銀行|日銀|BOJ", re.I), ["日本銀行", "日銀", "BOJ"]),
    (re.compile(r"非農|nonfarm|payroll", re.I), ["非農", "nonfarm", "payroll"]),
    (re.compile(r"GDP|國內生產毛額", re.I), ["GDP", "國內生產毛額"]),
    (re.compile(r"PMI|採購經理人", re.I), ["PMI", "採購經理人"]),
]

def build_asset_alias_map() -> dict[str, str]:
    payload = read_json(DATA / "assets.json", {"assets": []})
    aliases: dict[str, str] = {}
    for asset in payload.get("assets", []):
        if asset.get("market") != "TW" or not asset.get("symbol"):
            continue
        symbol = str(asset["symbol"]).upper()
        names = [asset.get("name"), asset.get("company_name"), *(asset.get("aliases") or [])]
        for name in names:
            cleaned = clean_text(name)
            if len(cleaned) >= 2:
                aliases[cleaned.lower()] = symbol
    return aliases

def infer_symbols(text: str) -> list[str]:
    found = extract_symbols(text)
    lowered = clean_text(text).lower()
    for alias, symbol in ASSET_ALIAS_MAP.items():
        if alias in lowered:
            found.append(symbol)
    return list(dict.fromkeys(found))[:12]

def event_terms(text: str) -> list[str]:
    values: list[str] = []
    for pattern, terms in EVENT_TERM_RULES:
        if pattern.search(text):
            values.extend(terms)
    return list(dict.fromkeys(values))[:12]

def impact_rationale(category: str, impact: str, direction: str, affected: list[str]) -> str:
    scope = "、".join(affected[:3]) if affected else "整體市場"
    if impact == "high":
        return f"此事件可能同時影響{scope}的風險偏好、估值或資金流向。"
    if impact == "medium":
        return f"此事件較可能影響{scope}，仍需配合實際數據與市場預期差判斷。"
    return f"目前判定影響範圍偏向{scope}，對大盤的直接衝擊有限。"

def clean_text(value: object) -> str:
    raw = html.unescape(str(value or ""))
    text = BeautifulSoup(raw, "html.parser").get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def strip_site_suffix(value: str) -> str:
    title = clean_text(value)
    previous = None
    while title != previous:
        previous = title
        title = SITE_SUFFIX_RE.sub("", title).strip(" -｜|")
    return title


def article_url(value: object) -> str | None:
    raw = html.unescape(str(value or "")).strip()
    if not re.match(r"^https?://", raw, re.I) or any(char in raw for char in "<>\n\r"):
        return None
    try:
        parts = urlsplit(raw)
    except ValueError:
        return None
    if not parts.netloc:
        return None
    path = re.sub(r"/+", "/", parts.path or "/").lower()
    query = parse_qs(parts.query)
    has_record_query = any(key.lower() in {"id", "newsid", "article", "sn", "seq", "document", "post", "content_number"} for key in query)
    if path in HOME_PATHS and not has_record_query:
        return None
    if LISTING_RE.search(path):
        return None
    if re.search(r"/(?:announcement|news|bulletin|material|mops)/?$", path, re.I) and not has_record_query:
        return None
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def decode_google_news_url(candidate: str) -> str | None:
    """Decode older Google News RSS article IDs when the publisher URL is embedded.

    Newer IDs cannot always be decoded locally, so failure is expected and the
    article-specific Google News URL remains a safe fallback.
    """
    try:
        token = urlsplit(candidate).path.rstrip("/").split("/")[-1]
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
        match = re.search(rb"https?://[^\x00-\x20\"<>]+", raw)
        if not match:
            return None
        return article_url(match.group(0).decode("utf-8", "ignore"))
    except Exception:
        return None


def resolve_url(session: requests.Session, value: object) -> tuple[str | None, str]:
    candidate = article_url(value)
    if not candidate:
        return None, "invalid"
    host = urlsplit(candidate).netloc.lower()
    if "news.google." not in host:
        return candidate, "direct"

    decoded = decode_google_news_url(candidate)
    if decoded and "news.google." not in urlsplit(decoded).netloc.lower():
        return decoded, "decoded"

    # Some Google records still use a normal redirect. Try it, but do not delete
    # a specific article merely because Google returned an intermediate page.
    try:
        response = session.get(candidate, headers=HEADERS, timeout=12, allow_redirects=True)
        response.raise_for_status()
        final = article_url(response.url)
        if final and "news.google." not in urlsplit(final).netloc.lower():
            return final, "redirect"
    except Exception:
        pass
    return candidate, "google-news-fallback"


def roc_date_to_ad(text: str) -> str | None:
    match = re.search(r"(?:民國|中華民國)?\s*(\d{2,3})[年/](\d{1,2})[月/](\d{1,2})日?", text)
    if not match:
        return None
    year, month, day = map(int, match.groups())
    return f"{year + 1911}/{month}/{day}"


def first_sentence(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"^(?:摘要|說明|主旨)[:：]\s*", "", text)
    sentences = [part.strip() for part in SENTENCE_RE.split(text) if len(part.strip()) >= 8]
    return (sentences[0] if sentences else text)[:180].strip()


def company_prefix(text: str) -> tuple[str | None, str | None]:
    # Official records commonly use either ``7792 安保`` or
    # ``安保（證券代號：7792）``.  Support both layouts.
    labelled = re.search(
        r"([\u4e00-\u9fffA-Za-z0-9]{2,14})[（(\s]*(?:證券|股票|公司)?代號[：:]\s*(\d{4,6}[A-Z]?)",
        text,
        re.I,
    )
    if labelled:
        name = re.sub(r"^(?:公告)?(?:(?:上市|上櫃)(?:公司|股票)?|公司|股票)+", "", labelled.group(1))
        return labelled.group(2).upper(), name or None
    code_match = COMPANY_CODE_RE.search(text)
    if not code_match:
        return None, None
    code = code_match.group(1).upper()
    tail = text[code_match.end():].lstrip(" 　-｜|：:")
    name_match = re.match(r"([\u4e00-\u9fffA-Za-z0-9]{2,14})", tail)
    name = name_match.group(1) if name_match else None
    return code, name


def rewrite_company_title(title: str, summary: str) -> str | None:
    title = strip_site_suffix(title)
    combined = clean_text(f"{title} {summary}")
    generic = not title or bool(GENERIC_TITLE_RE.fullmatch(title))
    code, name = company_prefix(combined)
    prefix = " ".join(part for part in (code, name) if part)

    if re.search(r"得為融資融券交易|開放融資融券|融資融券標的", combined):
        day = roc_date_to_ad(combined)
        if prefix:
            return f"{prefix}{f' 自 {day} 起' if day else ''}開放融資融券交易"
    if "現金增資" in combined:
        shares = re.search(r"(?:發行(?:新股|總股數)|發行股數)[^0-9]{0,12}([0-9][0-9,]*)", combined)
        if prefix:
            return f"{prefix}決議現金增資" + (f"發行 {shares.group(1)} 股" if shares else "")
    if re.search(r"除息|現金股利", combined):
        amount = re.search(r"(?:每股(?:配發)?|現金股利)[^0-9]{0,12}([0-9]+(?:\.[0-9]+)?)\s*元", combined)
        day = roc_date_to_ad(combined)
        if prefix:
            result = f"{prefix}" + (f"每股配息 {amount.group(1)} 元" if amount else "除息公告")
            return result + (f"，{day} 生效" if day else "")
    if re.search(r"減資", combined) and prefix:
        return f"{prefix}發布減資相關公告"
    if re.search(r"財務報告|財報", combined) and prefix:
        return f"{prefix}公布財務報告"
    if re.search(r"法人說明會|法說會", combined) and prefix:
        day = roc_date_to_ad(combined)
        return f"{prefix}{f'將於 {day}' if day else ''}舉行法人說明會"
    if re.search(r"停牌|停止買賣", combined) and prefix:
        return f"{prefix}發布停止買賣公告"
    if re.search(r"復牌|恢復買賣", combined) and prefix:
        return f"{prefix}發布恢復買賣公告"

    if generic:
        candidate = first_sentence(summary)
        if not candidate or GENERIC_TITLE_RE.fullmatch(strip_site_suffix(candidate)):
            return None
        # Generic portal titles without a company code and a concrete event are not
        # usable records and must not appear as news cards.
        if not COMPANY_CODE_RE.search(candidate) or not COMPANY_EVENT_RE.search(candidate):
            return None
        return strip_site_suffix(candidate)[:110]

    cleaned = re.sub(r"^\s*\d+[.)、．]\s*", "", title)
    return cleaned[:110] if len(cleaned) >= 6 else None


def summarize(title: str, summary: str) -> str:
    body = clean_text(summary)
    if not body:
        return title[:220]
    body = re.sub(re.escape(title), "", body, count=1, flags=re.I).strip(" -｜|:")
    body = re.sub(r"(?:閱讀全文|繼續閱讀|更多內容|查看原文).*$", "", body, flags=re.I)
    sentences = [sentence.strip() for sentence in SENTENCE_RE.split(body) if len(sentence.strip()) >= 8]
    outline = " ".join(sentences[:2]) if sentences else body
    return outline[:300].strip()


def extract_symbols(text: str) -> list[str]:
    values = []
    for match in COMPANY_CODE_RE.finditer(text):
        code = match.group(1).upper()
        if code.isdigit() and 1900 <= int(code) <= 2100:
            continue
        values.append(code)
    return list(dict.fromkeys(values))[:8]



def extract_key_facts(text: str) -> list[dict[str, str]]:
    """Extract a small display-safe set of facts from an official notice."""
    cleaned = clean_text(text)
    facts: list[dict[str, str]] = []

    def add(label: str, value: str | None) -> None:
        value = clean_text(value) if value else ""
        if value and not any(row["label"] == label for row in facts):
            facts.append({"label": label, "value": value[:120]})

    code, _name = company_prefix(cleaned)
    add("股票代碼", code)
    add("重要日期", roc_date_to_ad(cleaned))
    shares = re.search(r"(?:發行(?:新股|股數|總股數)|認購股數)[^0-9]{0,15}([0-9][0-9,]*)\s*股", cleaned)
    amount = re.search(r"(?:募集資金|發行總額|交易金額|每股配息|現金股利|金額)[^0-9]{0,15}([0-9][0-9,.]*(?:億|萬)?元)", cleaned)
    purpose = re.search(r"(?:資金用途|用途)[：:]?\s*([^。；;]{4,100})", cleaned)
    add("股數", f"{shares.group(1)} 股" if shares else None)
    add("金額", amount.group(1) if amount else None)
    add("用途", purpose.group(1) if purpose else None)
    return facts[:6]

def classify(title: str, summary: str, configured_topic: str) -> dict:
    text = f"{title} {summary}"
    symbols = infer_symbols(text)
    company_announcement = bool(symbols and COMPANY_EVENT_RE.search(text))
    scope = "company" if company_announcement else "market" if MARKET_WIDE_RE.search(text) else "general"

    category, ai_topic = "市場動態", configured_topic or "market"
    for label, topic, pattern in CATEGORY_RULES:
        if pattern.search(text):
            category, ai_topic = label, topic
            break
    if company_announcement:
        category, ai_topic = "個股公告", "company"

    if scope == "market" and HIGH_RE.search(text):
        impact = "high"
    elif MEDIUM_RE.search(text):
        impact = "medium"
    else:
        impact = "low"
    positive, negative = bool(POSITIVE_RE.search(text)), bool(NEGATIVE_RE.search(text))
    direction = "多空混合" if positive and negative else "偏多" if positive else "偏空" if negative else "中性"

    affected = []
    for pattern, labels in [
        (re.compile(r"台股|證交所|櫃買|新台幣", re.I), ["台股"]),
        (re.compile(r"半導體|晶片|台積電|NVIDIA|輝達|AI", re.I), ["半導體", "科技股"]),
        (re.compile(r"美股|NASDAQ|S&P|道瓊|聯準會|Fed\b", re.I), ["美股"]),
        (re.compile(r"韓國|KOSPI|KOSDAQ|韓元", re.I), ["韓股"]),
        (re.compile(r"美元|匯率|日圓|新台幣|韓元", re.I), ["匯率"]),
        (re.compile(r"債券|美債|殖利率", re.I), ["債券"]),
        (re.compile(r"原油|石油|天然氣|黃金|銅價", re.I), ["原物料"]),
        (re.compile(r"金融|銀行|保險", re.I), ["金融股"]),
        (re.compile(r"航運|海運|運價", re.I), ["航運股"]),
    ]:
        if pattern.search(text):
            affected.extend(labels)
    if company_announcement and symbols:
        affected = symbols
    affected = list(dict.fromkeys(affected))[:5] or ["整體市場"]
    return {
        "ai_category": category,
        "ai_topic": ai_topic,
        "impact": impact,
        "market_direction": direction,
        "affected_markets": affected,
        "confidence": "高" if scope == "market" and impact == "high" else "中",
        "scope": scope,
        "company_announcement": company_announcement,
        "symbols": symbols,
        "event_terms": event_terms(text),
        "importance_score": 90 if scope == "market" and impact == "high" else 65 if impact == "medium" else 35,
        "why_it_matters": impact_rationale(category, impact, direction, affected),
        # Ordinary single-company notices never enter the market-wide major area.
        "is_major": scope == "market" and impact == "high",
    }


def main() -> None:
    global ASSET_ALIAS_MAP
    ASSET_ALIAS_MAP = build_asset_alias_map()
    config = read_json(DATA / "news-sources.json", {"sources": []})
    old = read_json(DATA / "news.json", {"items": []})
    session = requests.Session()
    items, health = [], []

    for source in config.get("sources", []):
        try:
            feed = feedparser.parse(source["url"])
            count, rejected = 0, 0
            for entry in feed.entries[:30]:
                raw_title = clean_text(entry.get("title"))
                raw_summary = entry.get("summary") or entry.get("description") or ""
                summary_text = clean_text(raw_summary)
                title = rewrite_company_title(raw_title, summary_text)
                url, link_resolution = resolve_url(session, entry.get("link"))
                if not title or not url:
                    rejected += 1
                    continue
                summary = summarize(title, summary_text)
                analysis = classify(title, summary, source.get("topic", "market"))
                original_text = summary_text[:4000]
                key_facts = extract_key_facts(f"{title} {original_text}") if analysis.get("scope") == "company" else []
                items.append({
                    "id": hashlib.sha1((title + url).encode()).hexdigest()[:16],
                    "title": title,
                    "url": url,
                    "url_valid": True,
                    "link_resolution": link_resolution,
                    "summary": summary,
                    "ai_summary": summary,
                    "original_text": original_text,
                    "key_facts": key_facts,
                    "source": source["name"],
                    "topic": analysis["ai_topic"],
                    "published_at": entry.get("published") or entry.get("updated") or NOW.isoformat(timespec="seconds"),
                    **analysis,
                })
                count += 1
            health.append({"name": source["name"], "status": "ok" if count else "warning", "count": count, "rejected": rejected, "reason": None if count else "all records rejected or source returned no usable entries"})
        except Exception as exc:
            health.append({"name": source.get("name", "unknown"), "status": "warning", "error": str(exc)})

    # Keep last-known-good records even when only part of the current scrape
    # succeeds. This prevents a temporary resolver/source failure from shrinking
    # the feed to zero or a handful of cards.
    old_clean: list[dict] = []
    for row in old.get("items", []):
        title = rewrite_company_title(row.get("title", ""), row.get("summary", ""))
        url = article_url(row.get("url"))
        if not title or not url:
            continue
        analysis = classify(title, clean_text(row.get("summary")), row.get("topic", "market"))
        old_clean.append({**row, "title": title, "url": url, "url_valid": True, **analysis})

    minimum_fresh = 8
    fresh_count = len(items)
    if fresh_count < minimum_fresh and old_clean:
        items.extend(old_clean)

    seen, deduped = set(), []
    for item in sorted(items, key=lambda row: str(row.get("published_at") or ""), reverse=True):
        key = re.sub(r"\W+", "", item["title"].lower())[:140]
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    # Retain a rolling archive. Invalid timestamps are retained rather than
    # discarded because several official feeds use locale-specific dates.
    cutoff = NOW - timedelta(days=14)
    retained = []
    for item in deduped:
        raw = str(item.get("published_at") or "")
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=NOW.tzinfo)
            if dt.astimezone(NOW.tzinfo) < cutoff:
                continue
        except Exception:
            pass
        retained.append(item)

    if not retained:
        raise SystemExit("No valid news records; live-news was not replaced.")

    payload = {
        "metadata": {
            "version": "v11.4.2",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "item_count": len(retained),
            "fresh_item_count": fresh_count,
            "used_archive_fallback": fresh_count < minimum_fresh and bool(old_clean),
            "major_item_count": sum(bool(row.get("is_major")) for row in retained),
            "company_announcement_count": sum(row.get("scope") == "company" for row in retained),
            "retention_days": 14,
            "minimum_fresh_records": minimum_fresh,
            "summary_mode": "deterministic-impact-analysis-v4",
            "note": "Article-specific Google News links remain usable when publisher URL decoding fails; previous successful records are restored before every update and empty publication is blocked.",
        },
        "sources": health,
        "items": retained[:500],
    }
    write_payload("news.json", "__NEWS_SEED__", payload)


if __name__ == "__main__":
    main()
