#!/usr/bin/env python3
"""Market Event Radar v10.3 multi-source finance-news updater.

v10.1 priorities:
- Traditional-Chinese financial coverage first.
- Official Taiwan market disclosures are separated from editorial media.
- Extended sources rotate across four 15-minute runs to reduce throttling.
- Previous successful rows are preserved when an individual source fails.
- English sources remain available, but the website defaults to Chinese-first display.

Only headline metadata, short summaries and original links are stored.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
import unicodedata
from difflib import SequenceMatcher
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus
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
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/10.3; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language": "zh-TW,zh;q=0.95,en-US;q=0.75,en;q=0.65",
}

# Direct RSS feeds are fetched every run.
DIRECT_RSS = [
    {
        "name": "中央社產經證券",
        "url": "https://feeds.feedburner.com/rsscna/finance",
        "region": "TW", "topic": "market", "language": "zh-Hant",
        "source_group": "tw-media", "quality_score": 96,
    },
    {
        "name": "中央社科技",
        "url": "https://feeds.feedburner.com/rsscna/technology",
        "region": "TW", "topic": "tech", "language": "zh-Hant",
        "source_group": "tw-media", "quality_score": 95,
    },
    {
        "name": "經濟日報",
        "url": "https://money.udn.com/rssfeed/news/1001/5588/5601",
        "region": "TW", "topic": "market", "language": "zh-Hant",
        "source_group": "tw-media", "quality_score": 92,
    },
    {
        "name": "臺灣證券交易所",
        "url": "https://www.twse.com.tw/rwd/zh/news/feed?type=rss",
        "region": "TW", "topic": "official", "language": "zh-Hant",
        "source_group": "official-tw", "quality_score": 100,
    },
]

# Always fetched on every run.
CORE_SEARCH_SOURCES = [
    {"name":"Yahoo 股市","query":"site:tw.stock.yahoo.com (台股 OR 美股 OR 財報 OR ETF OR 基金)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":80},
    {"name":"鉅亨網","query":"site:cnyes.com (台股 OR 美股 OR 央行 OR PMI OR 基金 OR 關稅)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":86},
    {"name":"MoneyDJ","query":"site:moneydj.com (台股 OR 美股 OR 半導體 OR 基金 OR 債券)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":85},
    {"name":"工商時報","query":"site:ctee.com.tw (台股 OR 產業 OR 財報 OR 基金 OR 政策)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":84},
    {"name":"科技新報／財經新報","query":"(site:technews.tw OR site:finance.technews.tw) (半導體 OR AI OR 財經 OR 台股 OR 美股)","region":"TW","topic":"tech","language":"zh-Hant","source_group":"tw-media","quality_score":87},
    {"name":"自由財經","query":"site:ec.ltn.com.tw (台股 OR 國際財經 OR 證券 OR 基金 OR 政策)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":79},
    {"name":"中央銀行","query":"site:cbc.gov.tw (新聞稿 OR 利率 OR 匯率 OR 貨幣政策 OR 理監事會)","region":"TW","topic":"official","language":"zh-Hant","source_group":"official-tw","quality_score":100},
    {"name":"公開資訊觀測站","query":"site:mops.twse.com.tw (重大訊息 OR 法說會 OR 財務報告 OR 股東會)","region":"TW","topic":"official","language":"zh-Hant","source_group":"official-tw","quality_score":100},
]

# One bucket is fetched per run. Cron minutes 07/22/37/52 naturally cycle buckets.
ROTATING_SEARCH_SOURCES = [
    # Bucket 0: Taiwan investment and long-form media
    {"rotation_group":0,"name":"今周刊","query":"site:businesstoday.com.tw (投資理財 OR 財經時事 OR 台股 OR ETF OR 基金)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":75},
    {"rotation_group":0,"name":"商業周刊","query":"site:businessweekly.com.tw (財經 OR 投資 OR 產業 OR 台股 OR 美股)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":75},
    {"rotation_group":0,"name":"財訊","query":"site:wealth.com.tw (投資 OR 台股 OR 產業 OR 基金 OR 全球市場)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":76},
    {"rotation_group":0,"name":"ETtoday 財經雲","query":"site:finance.ettoday.net (台股 OR 財經 OR 產業 OR 房市 OR 基金)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":70},
    {"rotation_group":0,"name":"證券櫃檯買賣中心","query":"site:tpex.org.tw (新聞稿 OR 上櫃 OR 興櫃 OR ETF OR 處置股票)","region":"TW","topic":"official","language":"zh-Hant","source_group":"official-tw","quality_score":100},

    # Bucket 1: Technology, business and policy
    {"rotation_group":1,"name":"數位時代","query":"site:bnext.com.tw (AI OR 半導體 OR 科技產業 OR 新創 OR 數位經濟)","region":"TW","topic":"tech","language":"zh-Hant","source_group":"tw-media","quality_score":75},
    {"rotation_group":1,"name":"iThome","query":"site:ithome.com.tw (AI OR 雲端 OR 資安 OR 半導體 OR 企業科技)","region":"TW","topic":"tech","language":"zh-Hant","source_group":"tw-media","quality_score":76},
    {"rotation_group":1,"name":"INSIDE","query":"site:inside.com.tw (科技 OR AI OR 新創 OR 商業 OR 半導體)","region":"TW","topic":"tech","language":"zh-Hant","source_group":"tw-media","quality_score":72},
    {"rotation_group":1,"name":"風傳媒財經","query":"site:storm.mg (財經 OR 台股 OR 產業 OR 關稅 OR 基金)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":69},
    {"rotation_group":1,"name":"金管會","query":"site:fsc.gov.tw (新聞稿 OR 證券 OR 銀行 OR 保險 OR ETF OR 投資人)","region":"TW","topic":"official","language":"zh-Hant","source_group":"official-tw","quality_score":100},
    {"rotation_group":1,"name":"經濟部統計處","query":"site:moea.gov.tw (統計處 OR 外銷訂單 OR 工業生產 OR 景氣 OR 批發零售)","region":"TW","topic":"macro","language":"zh-Hant","source_group":"official-tw","quality_score":100},

    # Bucket 2: Additional Taiwan and official macro
    {"rotation_group":2,"name":"信傳媒財經","query":"site:cmmedia.com.tw (財經 OR 台股 OR 產業 OR 政策 OR 基金)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":67},
    {"rotation_group":2,"name":"聯合新聞網財經","query":"site:udn.com (財經 OR 台股 OR 產業 OR 投資 OR 基金)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":72},
    {"rotation_group":2,"name":"華視財經","query":"site:news.cts.com.tw (財經 OR 台股 OR 經濟 OR 產業)","region":"TW","topic":"market","language":"zh-Hant","source_group":"tw-media","quality_score":62},
    {"rotation_group":2,"name":"主計總處","query":"site:dgbas.gov.tw (新聞稿 OR CPI OR GDP OR 失業率 OR 薪資 OR 經濟成長)","region":"TW","topic":"macro","language":"zh-Hant","source_group":"official-tw","quality_score":100},
    {"rotation_group":2,"name":"財政部","query":"site:mof.gov.tw (新聞稿 OR 出口 OR 進口 OR 稅收 OR 關稅 OR 統計)","region":"TW","topic":"official","language":"zh-Hant","source_group":"official-tw","quality_score":100},

    # Bucket 3: Hong Kong Traditional-Chinese market coverage
    {"rotation_group":3,"name":"AASTOCKS","query":"site:aastocks.com/tc (港股 OR 美股 OR 日股 OR 財經 OR 公司業績)","region":"HK","topic":"market","language":"zh-Hant","source_group":"hk-media","quality_score":78},
    {"rotation_group":3,"name":"經濟通 ET Net","query":"site:etnet.com.hk (港股 OR 國際財經 OR 美股 OR 日股 OR 基金)","region":"HK","topic":"market","language":"zh-Hant","source_group":"hk-media","quality_score":78},
    {"rotation_group":3,"name":"香港經濟日報","query":"site:hket.com (港股 OR 財經 OR 國際 OR 科技 OR 基金)","region":"HK","topic":"market","language":"zh-Hant","source_group":"hk-media","quality_score":77},
    {"rotation_group":3,"name":"信報財經新聞","query":"site:hkej.com (港股 OR 財經 OR 國際市場 OR 中國經濟)","region":"HK","topic":"market","language":"zh-Hant","source_group":"hk-media","quality_score":79},
    {"rotation_group":3,"name":"明報財經","query":"site:finance.mingpao.com (港股 OR 財經 OR 美股 OR 中國經濟)","region":"HK","topic":"market","language":"zh-Hant","source_group":"hk-media","quality_score":72},
    {"rotation_group":3,"name":"香港01財經","query":"site:hk01.com/財經快訊 (港股 OR 財經 OR 國際市場 OR 科技)","region":"HK","topic":"market","language":"zh-Hant","source_group":"hk-media","quality_score":68},
]


# Broad-industry queries rotate with the same 15-minute schedule.
# The feed parser reads the original publisher from each Google News item,
# so these labels do not appear as fake publishers on the website.
SECTOR_SEARCH_SOURCES = [
    {"rotation_group":0,"name":"產業雷達・金融","query":"(銀行 OR 金控 OR 保險 OR 證券 OR 金融股 OR 淨利差 OR 金管會)","region":"TW","topic":"industry","industry_hint":"finance","language":"zh-Hant","source_group":"sector-search","quality_score":74},
    {"rotation_group":0,"name":"產業雷達・航運運輸","query":"(貨櫃 OR 散裝 OR 航運 OR 海運 OR 航空 OR 物流 OR 運價 OR SCFI)","region":"TW","topic":"industry","industry_hint":"shipping","language":"zh-Hant","source_group":"sector-search","quality_score":74},
    {"rotation_group":0,"name":"產業雷達・鋼鐵原物料","query":"(鋼鐵 OR 水泥 OR 塑化 OR 化工 OR 紙業 OR 原物料 OR 銅價 OR 鋼價)","region":"TW","topic":"industry","industry_hint":"materials","language":"zh-Hant","source_group":"sector-search","quality_score":73},
    {"rotation_group":1,"name":"產業雷達・機械工業","query":"(工具機 OR 機械 OR 工業電腦 OR 自動化 OR 重電 OR 電機 OR 製造業)","region":"TW","topic":"industry","industry_hint":"industrial","language":"zh-Hant","source_group":"sector-search","quality_score":74},
    {"rotation_group":1,"name":"產業雷達・汽車零組件","query":"(汽車 OR 電動車 OR 汽車零組件 OR 輪胎 OR 車用電子 OR 新車銷售)","region":"TW","topic":"industry","industry_hint":"automotive","language":"zh-Hant","source_group":"sector-search","quality_score":73},
    {"rotation_group":1,"name":"產業雷達・營建房市","query":"(營建 OR 建材 OR 房市 OR 房貸 OR 不動產 OR 商用地產 OR REIT)","region":"TW","topic":"industry","industry_hint":"real-estate","language":"zh-Hant","source_group":"sector-search","quality_score":73},
    {"rotation_group":2,"name":"產業雷達・消費零售","query":"(零售 OR 百貨 OR 電商 OR 餐飲 OR 食品 OR 飲料 OR 消費股 OR 通路)","region":"TW","topic":"industry","industry_hint":"consumer","language":"zh-Hant","source_group":"sector-search","quality_score":73},
    {"rotation_group":2,"name":"產業雷達・生技醫療","query":"(生技 OR 製藥 OR 醫療 OR 新藥 OR 臨床試驗 OR FDA OR 健保)","region":"TW","topic":"industry","industry_hint":"healthcare","language":"zh-Hant","source_group":"sector-search","quality_score":75},
    {"rotation_group":2,"name":"產業雷達・觀光休閒","query":"(觀光 OR 飯店 OR 旅行社 OR 餐飲 OR 航空客運 OR 娛樂 OR 遊戲)","region":"TW","topic":"industry","industry_hint":"tourism","language":"zh-Hant","source_group":"sector-search","quality_score":71},
    {"rotation_group":3,"name":"產業雷達・能源公用","query":"(電力 OR 綠能 OR 太陽能 OR 風電 OR 天然氣 OR 石油 OR 儲能 OR 公用事業)","region":"TW","topic":"industry","industry_hint":"energy","language":"zh-Hant","source_group":"sector-search","quality_score":74},
    {"rotation_group":3,"name":"產業雷達・電信媒體","query":"(電信 OR 5G OR 寬頻 OR 有線電視 OR 媒體 OR 廣告 OR 電信股)","region":"TW","topic":"industry","industry_hint":"telecom","language":"zh-Hant","source_group":"sector-search","quality_score":72},
    {"rotation_group":3,"name":"產業雷達・農業食品","query":"(農業 OR 農產品 OR 食品加工 OR 飼料 OR 黃豆 OR 玉米 OR 小麥 OR 漁業)","region":"TW","topic":"industry","industry_hint":"agriculture","language":"zh-Hant","source_group":"sector-search","quality_score":72},
]


CRYPTO_SEARCH_SOURCES = [
    {"rotation_group":0,"name":"動區動趨 BlockTempo","query":"site:blocktempo.com (比特幣 OR 以太坊 OR 穩定幣 OR DeFi OR 加密貨幣 OR 區塊鏈)","region":"GLOBAL","topic":"crypto","industry_hint":"crypto","language":"zh-Hant","source_group":"crypto-media","quality_score":82},
    {"rotation_group":1,"name":"鏈新聞 ABMedia","query":"site:abmedia.io (比特幣 OR 以太坊 OR 穩定幣 OR DeFi OR 加密貨幣 OR 交易所)","region":"GLOBAL","topic":"crypto","industry_hint":"crypto","language":"zh-Hant","source_group":"crypto-media","quality_score":82},
    {"rotation_group":2,"name":"CoinDesk","query":"site:coindesk.com (bitcoin OR ethereum OR stablecoin OR defi OR crypto regulation OR exchange)","region":"GLOBAL","topic":"crypto","industry_hint":"crypto","language":"en","source_group":"crypto-media","quality_score":86,"hl":"en-US","gl":"US","ceid":"US:en"},
    {"rotation_group":3,"name":"Cointelegraph","query":"site:cointelegraph.com (bitcoin OR ethereum OR stablecoin OR defi OR regulation OR exchange)","region":"GLOBAL","topic":"crypto","industry_hint":"crypto","language":"en","source_group":"crypto-media","quality_score":80,"hl":"en-US","gl":"US","ceid":"US:en"},
]

ENGLISH_SEARCH_SOURCES = [
    {"name":"Reuters","query":"site:reuters.com/markets (markets OR economy OR earnings OR tariff)","region":"GLOBAL","topic":"market","language":"en","source_group":"international","quality_score":90,"hl":"en-US","gl":"US","ceid":"US:en"},
    {"name":"CNBC","query":"site:cnbc.com (markets OR earnings OR economy OR Federal Reserve)","region":"US","topic":"market","language":"en","source_group":"international","quality_score":82,"hl":"en-US","gl":"US","ceid":"US:en"},
    {"name":"Nikkei Asia","query":"site:asia.nikkei.com (markets OR technology OR economy OR Japan)","region":"ASIA","topic":"market","language":"en","source_group":"international","quality_score":84,"hl":"en-US","gl":"US","ceid":"US:en"},
    {"name":"White House","query":"site:whitehouse.gov (tariff OR trade OR semiconductor OR executive order OR economy)","region":"US","topic":"policy","language":"en","source_group":"official-global","quality_score":100,"hl":"en-US","gl":"US","ceid":"US:en"},
    {"name":"PMI／ISM","query":"(ISM manufacturing PMI OR ISM services PMI OR S&P Global PMI)","region":"US","topic":"macro","language":"en","source_group":"official-global","quality_score":92,"hl":"en-US","gl":"US","ceid":"US:en"},
]

BREAKING_TERMS = [
    "breaking","速報","快訊","宣布","關稅","tariff","制裁","sanction","降息","升息",
    "rate cut","rate hike","出口管制","executive order","緊急","unexpected","重大訊息"
]

SOURCE_META = {}
for source in DIRECT_RSS + CORE_SEARCH_SOURCES + ROTATING_SEARCH_SOURCES + SECTOR_SEARCH_SOURCES + CRYPTO_SEARCH_SOURCES + ENGLISH_SEARCH_SOURCES:
    SOURCE_META[source["name"]] = source

def clean(value):
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()

KNOWN_SOURCE_SUFFIXES = [
    "Yahoo股市", "Yahoo 股市", "中央社", "經濟日報", "鉅亨網", "Anue鉅亨",
    "MoneyDJ理財網", "MoneyDJ", "工商時報", "中時新聞網", "科技新報",
    "財經新報", "自由財經", "今周刊", "商業周刊", "財訊", "ETtoday財經雲",
    "ETtoday", "數位時代", "iThome", "INSIDE", "風傳媒", "信傳媒",
    "聯合新聞網", "udn", "AASTOCKS", "經濟通", "香港經濟日報",
    "信報財經新聞", "明報財經", "香港01", "Reuters", "CNBC", "Nikkei Asia",
]

def strip_publisher_suffix(title):
    """Remove publisher names appended by aggregators, only for title comparison/display."""
    value = clean(title)
    # Remove common Google News style suffix: "headline - Publisher".
    suffix_pattern = "|".join(re.escape(x) for x in sorted(KNOWN_SOURCE_SUFFIXES, key=len, reverse=True))
    value = re.sub(
        rf"\s*(?:[-–—｜|]\s*)(?:{suffix_pattern})\s*$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    # Remove harmless presentation tails which frequently create false duplicates.
    value = re.sub(r"\s*[（(](?:圖|影音|更新|全文)[）)]\s*$", "", value)
    return clean(value)

def canonical_title(title):
    """Canonical key used to identify the same headline across syndicated outlets."""
    value = unicodedata.normalize("NFKC", strip_publisher_suffix(title)).lower()
    value = re.sub(r"^(?:快訊|速報|即時|獨家)\s*[：:｜|／/ -]*", "", value)
    value = re.sub(r"[\s\u3000]+", "", value)
    value = re.sub(r"[^\w\u3400-\u9fff]+", "", value, flags=re.UNICODE)
    return value

def title_ngrams(value, size=3):
    if len(value) <= size:
        return {value} if value else set()
    return {value[i:i+size] for i in range(len(value) - size + 1)}

def title_similarity(left, right):
    """Conservative near-duplicate detection for slightly edited syndicated headlines."""
    a = canonical_title(left)
    b = canonical_title(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    short, long = sorted((a, b), key=len)
    if len(short) >= 14 and short in long and len(short) / len(long) >= 0.72:
        return 0.96
    sequence = SequenceMatcher(None, a, b).ratio()
    grams_a, grams_b = title_ngrams(a), title_ngrams(b)
    union = grams_a | grams_b
    jaccard = len(grams_a & grams_b) / len(union) if union else 0.0
    return max(sequence, jaccard)

def published_timestamp(item):
    value = item.get("published_at")
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value).timestamp()
    except Exception:
        return 0.0

def same_news_window(left, right, hours=72):
    a = published_timestamp(left)
    b = published_timestamp(right)
    if not a or not b:
        return True
    return abs(a - b) <= hours * 3600

def representative_rank(item):
    """Prefer official/original/direct sources over republished aggregator copies."""
    group = item.get("source_group")
    origin = item.get("origin")
    source_priority = {
        "official-tw": 5,
        "official-global": 5,
        "tw-media": 3,
        "hk-media": 2,
        "international": 3,
        "event-related": 1,
    }.get(group, 0)
    origin_priority = {
        "official": 5,
        "direct-rss": 4,
        "direct-page": 3,
        "publisher-search": 2,
        "event-search": 1,
        "fallback": 0,
    }.get(origin, 0)
    return (
        source_priority,
        origin_priority,
        int(item.get("quality_score") or 0),
        len(clean(item.get("summary"))),
        published_timestamp(item),
    )

def merge_duplicate_metadata(keeper, duplicate):
    sources = set(keeper.get("duplicate_sources") or [])
    sources.add(keeper.get("source") or "")
    sources.add(duplicate.get("source") or "")
    sources.discard("")
    keeper["duplicate_sources"] = sorted(sources)
    keeper["duplicate_count"] = max(0, len(sources) - 1)
    if not keeper.get("summary") and duplicate.get("summary"):
        keeper["summary"] = duplicate["summary"]
    keeper["is_breaking"] = bool(keeper.get("is_breaking") or duplicate.get("is_breaking"))
    return keeper

def deduplicate_headlines(items):
    """Remove duplicate and near-duplicate titles while keeping the strongest source."""
    clusters = []
    removed = 0

    # Strongest candidates are considered first, so syndicated copies naturally lose.
    ordered = sorted(items, key=representative_rank, reverse=True)
    for raw in ordered:
        item = dict(raw)
        item["title"] = strip_publisher_suffix(item.get("title"))
        key = canonical_title(item.get("title"))
        if not key:
            continue

        match_index = None
        for index, keeper in enumerate(clusters):
            if not same_news_window(item, keeper):
                continue
            if canonical_title(keeper.get("title")) == key:
                match_index = index
                break
            if title_similarity(item.get("title"), keeper.get("title")) >= 0.90:
                match_index = index
                break

        if match_index is None:
            item.setdefault("duplicate_sources", [item.get("source")] if item.get("source") else [])
            item.setdefault("duplicate_count", 0)
            clusters.append(item)
            continue

        keeper = clusters[match_index]
        if representative_rank(item) > representative_rank(keeper):
            item = merge_duplicate_metadata(item, keeper)
            clusters[match_index] = item
        else:
            clusters[match_index] = merge_duplicate_metadata(keeper, item)
        removed += 1

    return clusters, removed

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


INDUSTRY_KEYWORDS = {
    "finance": ["金控","銀行","保險","證券","金融","利差","放款","存款","壽險","產險","信用卡","FinTech"],
    "shipping": ["航運","海運","貨櫃","散裝","運價","SCFI","航空","物流","快遞","港口","造船"],
    "industrial": ["機械","工具機","自動化","重電","電機","工業電腦","製造業","設備","工程"],
    "materials": ["鋼鐵","水泥","塑化","化工","紙業","原物料","銅","鋁","礦業","玻璃","紡織"],
    "real-estate": ["營建","建材","房市","房貸","不動產","商用地產","住宅","土地","REIT"],
    "consumer": ["零售","百貨","電商","餐飲","食品","飲料","通路","消費","服飾","家庭用品"],
    "healthcare": ["生技","製藥","醫療","新藥","臨床","FDA","醫材","醫院","健保"],
    "energy": ["能源","石油","原油","天然氣","綠能","太陽能","風電","儲能","電力","公用事業"],
    "telecom": ["電信","5G","寬頻","有線電視","媒體","廣告","通訊服務"],
    "tourism": ["觀光","飯店","旅行社","旅遊","休閒","航空客運","娛樂","遊戲"],
    "automotive": ["汽車","電動車","車用","輪胎","汽車零組件","新車","機車"],
    "agriculture": ["農業","農產品","飼料","黃豆","玉米","小麥","漁業","畜牧"],
    "technology": ["科技","半導體","晶片","AI","人工智慧","伺服器","軟體","雲端","電子","面板","PCB","記憶體"],
    "macro-policy": ["央行","利率","通膨","CPI","PPI","GDP","PMI","非農","匯率","關稅","政策","選舉"],
}

INDUSTRY_LABELS = {
    "finance": "金融保險",
    "shipping": "航運運輸",
    "industrial": "機械工業",
    "materials": "原物料傳產",
    "real-estate": "營建房市",
    "consumer": "消費零售",
    "healthcare": "生技醫療",
    "energy": "能源公用",
    "telecom": "電信媒體",
    "tourism": "觀光休閒",
    "automotive": "汽車零組件",
    "agriculture": "農業食品",
    "technology": "科技電子",
    "macro-policy": "總經政策",
    "other": "其他產業",
}

def classify_industries(title, summary="", hint=None):
    text = f"{title} {summary}".lower()
    scores = {}
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.lower() in text)
        if score:
            scores[industry] = score
    if hint:
        scores[hint] = scores.get(hint, 0) + 2
    if not scores:
        return ["other"]
    return [key for key, _ in sorted(scores.items(), key=lambda row: (-row[1], row[0]))[:3]]



CRYPTO_CATEGORY_KEYWORDS = {
    "bitcoin": ["bitcoin","btc","比特幣"],
    "ethereum": ["ethereum","ether","eth","以太坊"],
    "stablecoin": ["stablecoin","usdt","usdc","穩定幣","泰達幣"],
    "defi": ["defi","去中心化金融","uniswap","aave","流動性挖礦"],
    "exchange": ["交易所","binance","coinbase","kraken","幣安"],
    "regulation": ["監管","法規","sec","cftc","立法","牌照","稅務"],
    "layer1": ["solana","cardano","avalanche","layer 1","公鏈","sol","ada","avax"],
    "meme": ["meme","迷因幣","dogecoin","shib","狗狗幣"],
    "nft-gaming": ["nft","gamefi","鏈遊","元宇宙"],
    "mining": ["礦工","挖礦","算力","mining","hashrate"],
}

FUND_KEYWORDS = ["基金","ETF","受益憑證","淨值","配息","投信","資產配置","共同基金","bond fund","mutual fund"]
CRYPTO_KEYWORDS = ["加密貨幣","虛擬貨幣","區塊鏈","比特幣","以太坊","穩定幣","DeFi","bitcoin","ethereum","crypto","stablecoin","blockchain"]

def classify_asset_class(title, summary, topic):
    text = f"{title} {summary}".lower()
    if topic == "crypto" or any(word.lower() in text for word in CRYPTO_KEYWORDS):
        return "crypto"
    if topic == "fund" or any(word.lower() in text for word in FUND_KEYWORDS):
        return "fund"
    return "stock"

def classify_crypto_categories(title, summary):
    text = f"{title} {summary}".lower()
    rows = []
    for category, keywords in CRYPTO_CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            rows.append(category)
    return rows or ["market"]

def parse_feed(content, source, origin):
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
            feed_publisher = text_from(node, ["source", "{http://www.w3.org/2005/Atom}source"])
            display_source = feed_publisher if origin in {"publisher-search", "event-search"} and feed_publisher else source["name"]
            industries = classify_industries(title, summary, source.get("industry_hint"))
            rows.append({
                "id": stable_id(display_source, link),
                "title": title,
                "link": link,
                "source": display_source,
                "query_source": source["name"],
                "summary": summary[:320],
                "published_at": parse_date(pub),
                "region": source["region"],
                "topic": source["topic"],
                "industries": industries,
                "primary_industry": industries[0],
                "asset_class": classify_asset_class(title, summary, source["topic"]),
                "crypto_categories": classify_crypto_categories(title, summary) if classify_asset_class(title, summary, source["topic"]) == "crypto" else [],
                "industry_label": INDUSTRY_LABELS.get(industries[0], "其他產業"),
                "language": source.get("language", "zh-Hant"),
                "source_group": source.get("source_group", "tw-media"),
                "origin": origin,
                "quality_score": source.get("quality_score", 70),
                "is_breaking": any(term.lower() in lowered for term in BREAKING_TERMS),
                "fetched_at": iso(NOW),
            })
    return rows

def enrich_previous(item):
    row = dict(item)
    meta = SOURCE_META.get(row.get("source"), {})
    row.setdefault("language", meta.get("language", "zh-Hant"))
    row.setdefault("source_group", meta.get("source_group", "tw-media"))
    row.setdefault("quality_score", meta.get("quality_score", 65))
    industries = row.get("industries") or classify_industries(row.get("title"), row.get("summary"), meta.get("industry_hint"))
    row["industries"] = industries
    row["primary_industry"] = row.get("primary_industry") or industries[0]
    row["industry_label"] = row.get("industry_label") or INDUSTRY_LABELS.get(row["primary_industry"], "其他產業")
    return row

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
                time.sleep(1.1 * (index + 1))
    raise error

def google_url(source):
    hl = source.get("hl", "zh-TW")
    gl = source.get("gl", "TW")
    ceid = source.get("ceid", "TW:zh-Hant")
    return "https://news.google.com/rss/search?" + (
        f"q={quote_plus(source['query'])}&hl={hl}&gl={gl}&ceid={ceid}"
    )

def previous_by_source(previous):
    result = {}
    for raw in previous.get("items", []):
        item = enrich_previous(raw)
        result.setdefault(item.get("source") or "未知來源", []).append(item)
    return result

def still_recent(item, days=12):
    value = item.get("published_at")
    if not value:
        return True
    try:
        return datetime.fromisoformat(value).astimezone(TAIPEI) >= NOW - timedelta(days=days)
    except Exception:
        return True

def preserve_previous(source_name, previous_map, items, days=12):
    stale = [x for x in previous_map.get(source_name, []) if still_recent(x, days)]
    for row in stale:
        row = dict(row)
        row["stale"] = True
        items.append(row)
    return stale

def active_search_sources():
    bucket = (NOW.minute // 15) % 4
    rotating = [x for x in ROTATING_SEARCH_SOURCES if x["rotation_group"] == bucket]
    sectors = [x for x in SECTOR_SEARCH_SOURCES if x["rotation_group"] == bucket]
    crypto = [x for x in CRYPTO_SEARCH_SOURCES if x["rotation_group"] == bucket]
    return CORE_SEARCH_SOURCES + rotating + sectors + crypto + ENGLISH_SEARCH_SOURCES, bucket

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
            rows.append((event, clean(f'{event.get("title","")} {assets} 市場')))
    return rows[:10]

def main():
    previous = read_json(NEWS_PATH, {"items": [], "sources": []})
    previous_map = previous_by_source(previous)
    session = requests.Session()
    items = []
    statuses = []

    for source in DIRECT_RSS:
        try:
            response = get_with_retry(session, source["url"])
            rows = parse_feed(response.content, source, "direct-rss")
            items.extend(rows)
            statuses.append({
                "name": source["name"], "status": "ok" if rows else "empty",
                "count": len(rows), "mode": "direct-rss",
                "language": source["language"], "source_group": source["source_group"],
                "url": source["url"],
            })
        except Exception as exc:
            stale = preserve_previous(source["name"], previous_map, items)
            statuses.append({
                "name": source["name"], "status": "stale" if stale else "warning",
                "count": len(stale), "mode": "direct-rss",
                "language": source["language"], "source_group": source["source_group"],
                "message": str(exc)[:160],
            })

    sources, bucket = active_search_sources()
    for source in sources:
        try:
            response = get_with_retry(session, google_url(source))
            rows = parse_feed(response.content, source, "publisher-search")[:12]
            if rows:
                items.extend(rows)
                status = "ok"
                count = len(rows)
            else:
                stale = preserve_previous(source["name"], previous_map, items)
                status = "stale" if stale else "empty"
                count = len(stale)
            statuses.append({
                "name": source["name"], "status": status, "count": count,
                "mode": "publisher-search", "language": source["language"],
                "source_group": source["source_group"],
            })
        except Exception as exc:
            stale = preserve_previous(source["name"], previous_map, items)
            statuses.append({
                "name": source["name"], "status": "stale" if stale else "warning",
                "count": len(stale), "mode": "publisher-search",
                "language": source["language"], "source_group": source["source_group"],
                "message": str(exc)[:160],
            })
        time.sleep(.12)

    # Preserve non-active rotating sources so the combined feed remains broad.
    active_names = {x["name"] for x in DIRECT_RSS + sources}
    for source in ROTATING_SEARCH_SOURCES + SECTOR_SEARCH_SOURCES + CRYPTO_SEARCH_SOURCES:
        if source["name"] in active_names:
            continue
        stale = preserve_previous(source["name"], previous_map, items, days=20)
        statuses.append({
            "name": source["name"], "status": "rotating-cache" if stale else "scheduled",
            "count": len(stale), "mode": f"rotation-{source['rotation_group']}",
            "language": source["language"], "source_group": source["source_group"],
        })

    # Event-related Chinese search.
    events = read_json(EVENTS_PATH, {"events":[]}).get("events", [])
    for event, query in event_queries(events):
        try:
            source = {
                "name": "事件相關報導", "query": query,
                "region": event.get("region", "GLOBAL"),
                "topic": "earnings" if event.get("category") == "earnings" else "macro",
                "language": "zh-Hant", "source_group": "event-related",
                "quality_score": 68,
            }
            response = get_with_retry(session, google_url(source), attempts=2)
            rows = parse_feed(response.content, source, "event-search")
            for row in rows[:3]:
                row["event_id"] = event.get("id")
                row["event_title"] = event.get("title")
                items.append(row)
        except Exception:
            pass

    # First remove identical URLs, then cluster identical and near-identical titles.
    link_dedup = {}
    for raw in items:
        item = enrich_previous(raw)
        key = clean(item.get("link")) or canonical_title(item.get("title"))
        if not key:
            continue
        current = link_dedup.get(key)
        if current is None or representative_rank(item) > representative_rank(current):
            link_dedup[key] = item

    headline_dedup, duplicate_title_count = deduplicate_headlines(link_dedup.values())
    final = [x for x in headline_dedup if still_recent(x, days=20)]
    final.sort(key=lambda x: (
        x.get("language") == "zh-Hant",
        bool(x.get("is_breaking")),
        int(x.get("quality_score") or 0),
        x.get("published_at") or "",
    ), reverse=True)

    if not final:
        final = [enrich_previous(x) for x in previous.get("items", []) if still_recent(x, days=20)]

    source_ok = sum(1 for x in statuses if x["status"] == "ok")
    chinese_items = sum(1 for x in final if x.get("language") == "zh-Hant")
    industry_counts = {}
    for item in final:
        key = item.get("primary_industry", "other")
        industry_counts[key] = industry_counts.get(key, 0) + 1
    payload = {
        "metadata": {
            "updated_at": iso(NOW),
            "timezone": "Asia/Taipei",
            "item_count": len(final[:220]),
            "chinese_item_count": chinese_items,
            "healthy_sources": source_ok,
            "source_count": len(statuses),
            "rotation_bucket": bucket,
            "version": "v10.3",
            "industry_counts": industry_counts,
            "duplicate_titles_removed": duplicate_title_count,
            "note": "All-industry coverage prioritized. Headlines are classified into broad industry groups and deduplicated.",
        },
        "source": {
            "name": "多來源財經新聞",
            "status": "ok" if final else "warning",
            "message": "" if final else "No new or cached headlines were available.",
        },
        "sources": statuses,
        "items": final[:220],
    }
    NEWS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED_PATH.write_text(
        "window.__MARKET_NEWS_SEED__ = " +
        json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {len(payload['items'])} items "
        f"({chinese_items} Traditional Chinese); "
        f"healthy sources {source_ok}/{len(statuses)}; "
        f"removed duplicate titles {duplicate_title_count}; rotation bucket {bucket}"
    )

if __name__ == "__main__":
    main()
