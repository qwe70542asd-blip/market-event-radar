#!/usr/bin/env python3
"""Build an official Taiwan security master while preserving curated metadata."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "assets.json"
SEED = DATA / "assets-seed.js"
NOW = datetime.now(ZoneInfo("Asia/Taipei"))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.1)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
}
SOURCES = [
    ("TWSE", "stock", "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"),
    ("TWSE", "etf", "https://openapi.twse.com.tw/v1/opendata/t187ap47_L"),
    ("TPEx", "stock", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"),
]
OVERRIDES = {
    "TW:00403A": {"name": "主動統一升級50", "asset_class": "etf", "exchange": "TWSE",
        "sub_industry": "台灣主動式 ETF", "official_industry": "ETF",
        "aliases": ["統一升級50", "統一台股升級50主動式ETF"],
        "etf": {"issuer": "統一證券投資信託股份有限公司", "category": "主動式 ETF",
                "benchmark": "臺灣證券交易所發行量加權股價報酬指數",
                "strategy": "以前 50 大企業為核心，搭配 51–200 大增強選股池。",
                "official_url": "https://www.twse.com.tw/zh/ETFortune/etfInfo/00403A"}},
    "TW:00981A": {"name": "主動統一台股增長", "asset_class": "etf", "exchange": "TWSE",
        "sub_industry": "台灣主動式 ETF", "official_industry": "ETF",
        "aliases": ["統一台股增長", "統一台股增長主動式ETF"],
        "etf": {"issuer": "統一證券投資信託股份有限公司", "category": "主動式 ETF",
                "benchmark": "臺灣證券交易所發行量加權股價報酬指數",
                "strategy": "大型、創新、成長為核心選股邏輯。",
                "official_url": "https://www.twse.com.tw/zh/ETFortune/etfInfo/00981A"}},
    "TW:009816": {"name": "凱基台灣TOP50", "asset_class": "etf", "exchange": "TWSE",
        "sub_industry": "台灣市值型 ETF", "official_industry": "ETF",
        "aliases": ["凱基台灣 TOP 50"],
        "etf": {"issuer": "凱基證券投資信託股份有限公司", "category": "台股 ETF",
                "benchmark": "臺灣指數公司特選臺灣 TOP 50 指數",
                "strategy": "追蹤臺灣大型權值企業。",
                "official_url": "https://www.twse.com.tw/zh/ETFortune/etfInfo/009816"}},
    "TW:00631L": {"name": "元大台灣50正2", "asset_class": "etf", "exchange": "TWSE",
        "sub_industry": "台灣槓桿型 ETF", "official_industry": "ETF",
        "aliases": ["台灣50正2", "元大台灣50單日正向2倍"],
        "etf": {"issuer": "元大證券投資信託股份有限公司", "category": "股票槓反 ETF",
                "benchmark": "臺灣 50 指數", "leverage": "單日正向 2 倍",
                "official_url": "https://www.twse.com.tw/zh/ETFortune/etfInfo/00631L"}},
}

SECTOR_MAP = {
    "半導體業":"technology","電腦及週邊設備業":"technology","光電業":"technology",
    "通信網路業":"technology","電子零組件業":"technology","電子通路業":"technology",
    "資訊服務業":"technology","其他電子業":"technology","金融保險業":"finance",
    "航運業":"shipping","鋼鐵工業":"materials","水泥工業":"materials",
    "塑膠工業":"materials","化學工業":"materials","生技醫療業":"healthcare",
    "食品工業":"consumer","汽車工業":"automotive","電機機械":"industrial",
    "油電燃氣業":"energy","綠能環保":"energy","觀光餐旅":"tourism",
}


def value(row: dict, *needles: str):
    for key, val in row.items():
        compact = re.sub(r"\s+", "", str(key))
        if any(re.sub(r"\s+", "", needle) in compact for needle in needles):
            if val not in (None, ""):
                return val
    return None


def load_previous() -> dict:
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {"assets": []}


def normalize(row: dict, exchange: str, cls: str) -> dict | None:
    symbol = str(value(row, "公司代號", "證券代號", "股票代號", "基金代號") or "").strip().upper()
    name = str(value(row, "公司簡稱", "證券名稱", "股票名稱", "基金簡稱", "基金名稱") or "").strip()
    if not symbol or not name:
        return None
    if cls == "stock" and not re.fullmatch(r"\d{4}", symbol):
        return None
    if cls == "etf" and not re.fullmatch(r"00\d{2,4}[A-Z]?", symbol):
        return None
    industry = str(value(row, "產業別", "產業類別") or ("ETF" if cls == "etf" else "其他")).strip()
    return {
        "id": f"TW:{symbol}", "asset_class": cls, "market": "TW", "exchange": exchange,
        "symbol": symbol, "name": name, "sector": "fund" if cls == "etf" else SECTOR_MAP.get(industry, "other"),
        "sub_industry": "台灣 ETF" if cls == "etf" else industry, "official_industry": industry,
        "currency": "TWD", "aliases": [], "listing_status": "active", "metrics": {}, "financials": [],
    }


def main() -> None:
    previous = load_previous()
    seed = {row.get("id"): row for row in previous.get("assets", []) if row.get("id")}
    assets: dict[str, dict] = {}
    session = requests.Session()
    success = 0
    for exchange, cls, url in SOURCES:
        try:
            response = session.get(url, headers=HEADERS, timeout=35)
            response.raise_for_status()
            payload = response.json()
            rows = payload if isinstance(payload, list) else payload.get("data", [])
            for row in rows:
                asset = normalize(row, exchange, cls)
                if not asset:
                    continue
                assets[asset["id"]] = {**seed.get(asset["id"], {}), **asset}
                success += 1
        except Exception as exc:
            print("warning", exchange, cls, exc)

    # Preserve U.S., crypto, manual funds and any Taiwan rows omitted temporarily.
    for aid, row in seed.items():
        if aid not in assets:
            assets[aid] = row

    for aid, override in OVERRIDES.items():
        symbol = aid.split(":", 1)[1]
        base = assets.get(aid, {
            "id": aid, "market": "TW", "symbol": symbol, "currency": "TWD",
            "sector": "fund", "listing_status": "active", "metrics": {}, "financials": [],
        })
        aliases = list(dict.fromkeys([*(base.get("aliases") or []), *(override.get("aliases") or [])]))
        assets[aid] = {**base, **override, "id": aid, "market": "TW", "symbol": symbol,
                       "currency": "TWD", "sector": "fund", "aliases": aliases}

    if len(assets) < 20:
        raise SystemExit(f"Only {len(assets)} securities; previous master was not replaced.")

    payload = {
        "metadata": {
            "version": "v11.1.0", "updated_at": NOW.isoformat(timespec="seconds"),
            "asset_count": len(assets), "official_rows": success,
            "note": "TWSE/TPEx official master plus curated aliases and ETF metadata.",
        },
        "assets": sorted(assets.values(), key=lambda row: (row.get("market",""), row.get("symbol",""))),
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED.write_text("window.__ASSET_SEED__ = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    print("assets", len(assets))


if __name__ == "__main__":
    main()
