#!/usr/bin/env python3
"""Build the official security master and financial-analysis fields.

Sources:
- TWSE/TPEx official company and ETF masters
- TWSE/TPEx official valuation tables
- TWSE/TPEx official comprehensive-income and balance-sheet OpenAPI tables

The updater enriches every listed stock for which official filings are available,
then computes comparable industry ranks. Missing values remain null; they are
never replaced with invented scores.
"""
from __future__ import annotations

import json
import math
import re
import time
from collections import defaultdict
from datetime import datetime
from io import StringIO
from pathlib import Path
from statistics import median
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "assets.json"
SEED = DATA / "assets-seed.js"
COVERAGE_OUT = DATA / "asset-coverage.json"
NOW = datetime.now(ZoneInfo("Asia/Taipei"))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.2.3)",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.7",
    "Accept": "application/json,text/plain,*/*",
}

TWSE_BASE = "https://openapi.twse.com.tw/v1"
TPEX_SWAGGER = "https://www.tpex.org.tw/openapi/swagger.json"

MASTER_SOURCES = [
    ("TWSE", "stock", f"{TWSE_BASE}/opendata/t187ap03_L"),
    ("TWSE", "etf", f"{TWSE_BASE}/opendata/t187ap47_L"),
    ("TPEx", "stock", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O"),
]

TWSE_INCOME_PATHS = [
    "/opendata/t187ap06_L_ci", "/opendata/t187ap06_L_mim",
    "/opendata/t187ap06_L_basi", "/opendata/t187ap06_L_bd",
    "/opendata/t187ap06_L_fh", "/opendata/t187ap06_L_ins",
]
TWSE_BALANCE_PATHS = [
    "/opendata/t187ap07_L_ci", "/opendata/t187ap07_L_mim",
    "/opendata/t187ap07_L_basi", "/opendata/t187ap07_L_bd",
    "/opendata/t187ap07_L_fh", "/opendata/t187ap07_L_ins",
]
TWSE_EPS_URL = f"{TWSE_BASE}/opendata/t187ap14_L"
TPEX_EPS_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap14_O"
TWSE_OPERATING_URL = f"{TWSE_BASE}/opendata/t187ap17_L"
TPEX_OPERATING_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_187ap17_O"
TWSE_REVENUE_URL = f"{TWSE_BASE}/opendata/t187ap05_L"
TPEX_REVENUE_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O"
TWSE_DIVIDEND_URL = f"{TWSE_BASE}/opendata/t187ap45_L"
TPEX_DIVIDEND_URL = "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap39_O"

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
    "TW:00663L": {"name": "國泰臺灣加權正2", "asset_class": "etf", "exchange": "TWSE",
        "sub_industry": "台灣槓桿型 ETF", "official_industry": "ETF",
        "aliases": ["國泰臺指正2", "國泰臺灣加權指數單日正向2倍基金"],
        "etf": {"issuer": "國泰證券投資信託股份有限公司", "manager": "蘇鼎宇",
                "category": "股票槓反ETF", "benchmark": "臺灣日報酬兩倍指數",
                "leverage": "單日正向 2 倍", "strategy": "追求臺灣加權指數單日報酬的兩倍。",
                "official_url": "https://www.twse.com.tw/zh/ETFortune/etfInfo/00663L"}},
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

KEY_ALIASES = {
    "code": ["公司代號","證券代號","股票代號","基金代號","code","securitiescompanycode"],
    "name": ["公司簡稱","證券名稱","股票名稱","基金簡稱","基金名稱","name","companyname"],
    "industry": ["產業別","產業類別","industry"],
    "year": ["年度","年","year"],
    "quarter": ["季別","季","quarter"],
    "revenue": ["營業收入","收入合計","收益合計","淨收益","利息淨收益"],
    "gross_profit": ["營業毛利（毛損）淨額","營業毛利(毛損)淨額","營業毛利"],
    "operating_income": ["營業利益（損失）","營業利益(損失)","營業淨利","繼續營業單位稅前淨利"],
    "net_income": ["歸屬於母公司業主之淨利（損）","歸屬於母公司業主之淨利(損)","本期淨利（淨損）","本期淨利(淨損)","本期稅後淨利","稅後淨利","本期淨利"],
    "eps": ["基本每股盈餘（元）","基本每股盈餘(元)","基本每股盈餘","每股盈餘","eps"],
    "current_assets": ["流動資產"],
    "total_assets": ["資產總額","資產合計"],
    "current_liabilities": ["流動負債"],
    "total_liabilities": ["負債總額","負債合計"],
    "equity": ["權益總額","權益合計","歸屬於母公司業主之權益合計","歸屬於母公司業主之權益"],
    "pe": ["本益比","peratio","peratio"],
    "pb": ["股價淨值比","pbratio"],
    "yield": ["殖利率(%)","殖利率","dividendyield"],
    "fund_type": ["基金類型","證券類別"],
    "fund_full_name": ["基金中文名稱","基金名稱"],
    "benchmark": ["標的指數/追蹤指數名稱","標的指數","追蹤指數名稱","績效指標中文名稱"],
    "fund_manager": ["基金經理人","經理人"],
    "issuer": ["經理公司名稱","基金經理公司","發行公司","證券投資信託事業"],
    "investment_ratio": ["股票及債券投資比例說明","投資比例說明"],
    "inception_date": ["成立日期"],
    "listing_date": ["上市日期"],
    "custodian": ["保管機構"],
    "manager_phone": ["經理公司總機"],
    "manager_address": ["經理公司地址"],
    "chairman": ["經理公司董事長"],
    "spokesperson": ["經理公司發言人"],
    "general_manager": ["經理公司總經理"],
}


def compact(value: object) -> str:
    return re.sub(r"[\s_（）()％%:/\-]+", "", str(value or "")).lower()


def number(value):
    try:
        text = str(value).strip().replace(",", "").replace("%", "")
        text = text.replace("(", "-").replace(")", "")
        if text in {"", "-", "--", "---", "null", "None", "N/A", "NA"}:
            return None
        result = float(text)
        return result if math.isfinite(result) else None
    except Exception:
        return None


def pick(row: dict, alias_name: str):
    aliases = [compact(alias) for alias in KEY_ALIASES[alias_name]]
    # Exact normalized key first.
    normalized = {compact(key): value for key, value in row.items()}
    for alias in aliases:
        if alias in normalized and normalized[alias] not in (None, ""):
            return normalized[alias]
    # Then prefer the shortest containing key to avoid selecting notes.
    matches = []
    for key, value in row.items():
        key_norm = compact(key)
        if value in (None, ""):
            continue
        if any(alias in key_norm for alias in aliases):
            matches.append((len(key_norm), value))
    return min(matches, default=(0, None))[1]


def valid_code(value) -> str:
    code = str(value or "").strip().upper()
    return code if re.fullmatch(r"(?:[1-9]\d{3}|00\d{2,4}[A-Z]?)", code) else ""


def load_previous() -> dict:
    try:
        return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:
        return {"assets": []}


def get_json(session: requests.Session, url: str, timeout=18):
    response = session.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else payload.get("data") or payload.get("aaData") or []


ISSUER_PREFIXES = {
    "元大":"元大證券投資信託股份有限公司","富邦":"富邦證券投資信託股份有限公司",
    "國泰":"國泰證券投資信託股份有限公司","群益":"群益證券投資信託股份有限公司",
    "統一":"統一證券投資信託股份有限公司","野村":"野村證券投資信託股份有限公司",
    "復華":"復華證券投資信託股份有限公司","中信":"中國信託證券投資信託股份有限公司",
    "凱基":"凱基證券投資信託股份有限公司","永豐":"永豐證券投資信託股份有限公司",
    "第一金":"第一金證券投資信託股份有限公司","台新":"台新證券投資信託股份有限公司",
    "新光":"新光證券投資信託股份有限公司","兆豐":"兆豐國際證券投資信託股份有限公司",
    "國票":"國票證券投資信託股份有限公司","大華銀":"大華銀證券投資信託股份有限公司",
    "街口":"街口證券投資信託股份有限公司","安聯":"安聯證券投資信託股份有限公司",
}

def infer_issuer(name: str, full_name: str) -> str | None:
    text = f"{name} {full_name}"
    for prefix, issuer in ISSUER_PREFIXES.items():
        if prefix in text:
            return issuer
    return None


def normalize_master(row: dict, exchange: str, cls: str) -> dict | None:
    symbol = valid_code(pick(row, "code"))
    name = str(pick(row, "name") or "").strip()
    if not symbol or not name:
        return None
    if cls == "stock" and not re.fullmatch(r"\d{4}", symbol):
        return None
    if cls == "etf" and not symbol.startswith("00"):
        return None
    industry = str(pick(row, "industry") or ("ETF" if cls == "etf" else "其他")).strip()
    asset = {
        "id": f"TW:{symbol}", "asset_class": cls, "market": "TW", "exchange": exchange,
        "symbol": symbol, "name": name, "sector": "fund" if cls == "etf" else SECTOR_MAP.get(industry, "other"),
        "sub_industry": "台灣 ETF" if cls == "etf" else industry, "official_industry": industry,
        "currency": "TWD", "aliases": [], "listing_status": "active",
    }
    if cls == "etf":
        full_name = str(pick(row, "fund_full_name") or name).strip()
        issuer = str(pick(row, "issuer") or "").strip() or infer_issuer(name, full_name)
        asset["aliases"] = list(dict.fromkeys([value for value in [full_name] if value and value != name]))
        asset["etf"] = {
            "issuer": issuer,
            "manager": str(pick(row, "fund_manager") or "").strip() or None,
            "category": str(pick(row, "fund_type") or "ETF").strip(),
            "benchmark": str(pick(row, "benchmark") or "").strip() or None,
            "strategy": str(pick(row, "investment_ratio") or "").strip() or None,
            "inception_date": str(pick(row, "inception_date") or "").strip() or None,
            "listing_date": str(pick(row, "listing_date") or "").strip() or None,
            "custodian": str(pick(row, "custodian") or "").strip() or None,
            "manager_phone": str(pick(row, "manager_phone") or "").strip() or None,
            "manager_address": str(pick(row, "manager_address") or "").strip() or None,
            "chairman": str(pick(row, "chairman") or "").strip() or None,
            "spokesperson": str(pick(row, "spokesperson") or "").strip() or None,
            "general_manager": str(pick(row, "general_manager") or "").strip() or None,
            "full_name": full_name,
            "official_url": f"https://www.twse.com.tw/zh/ETFortune/etfInfo/{symbol}",
        }
    return asset


def swagger_info(session: requests.Session):
    try:
        response = session.get(TPEX_SWAGGER, headers=HEADERS, timeout=15)
        response.raise_for_status()
        spec = response.json()
        scheme = (spec.get("schemes") or ["https"])[0]
        host = spec.get("host") or "www.tpex.org.tw"
        base_path = spec.get("basePath") or "/openapi/v1"
        return spec, f"{scheme}://{host}{base_path.rstrip('/')}"
    except Exception as exc:
        print("warning TPEx swagger", exc)
        return {}, "https://www.tpex.org.tw/openapi/v1"


def discover_paths(spec: dict, required: tuple[str, ...]) -> list[str]:
    found = []
    for path, operations in (spec.get("paths") or {}).items():
        operation = operations.get("get") or {}
        description = compact(f"{operation.get('summary','')} {operation.get('description','')} {path}")
        if all(compact(term) in description for term in required):
            found.append(path)
    return found


def recent_quarters(count=4) -> list[tuple[int, int]]:
    year = NOW.year
    quarter = (NOW.month - 1) // 3 + 1
    output = []
    for _ in range(count):
        output.append((year, quarter))
        quarter -= 1
        if quarter == 0:
            quarter = 4
            year -= 1
    return output


def flatten_columns(columns) -> list[str]:
    output = []
    for column in columns:
        parts = column if isinstance(column, tuple) else (column,)
        cleaned = []
        for part in parts:
            text = re.sub(r"^Unnamed:.*$", "", str(part)).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        output.append("".join(cleaned) or "欄位")
    return output


def read_html_tables(html_text: str):
    """Parse MOPS HTML with an explicit fallback chain.

    MOPS occasionally returns malformed HTML that lxml rejects. Pandas then
    needs html5lib for the fallback parser, so both engines are supported.
    """
    errors = []
    for flavor in ("lxml", "html5lib"):
        try:
            return pd.read_html(StringIO(html_text), header=None, flavor=flavor)
        except Exception as exc:
            errors.append(f"{flavor}: {exc}")
    raise RuntimeError("Unable to parse MOPS HTML; " + " | ".join(errors))


def fetch_mops_history(session: requests.Session, endpoint: str, market: str, quarters: list[tuple[int,int]]) -> list[dict]:
    rows: list[dict] = []
    endpoints = [endpoint]
    if endpoint.startswith("ajax_"):
        endpoints.append(endpoint.removeprefix("ajax_"))
    try:
        session.get("https://mops.twse.com.tw/mops/web/index", headers=HEADERS, timeout=12)
    except Exception:
        pass

    for year, quarter in quarters:
        roc_year = year - 1911
        parsed_this_period = False
        for endpoint_name in endpoints:
            url = f"https://mops.twse.com.tw/mops/web/{endpoint_name}"
            for attempt in range(2):
                try:
                    response = session.post(url, data={
                        "encodeURIComponent":"1","step":"1","firstin":"1","off":"1","isQuery":"Y",
                        "TYPEK":market,"year":str(roc_year),"season":f"{quarter:02d}"
                    }, headers={**HEADERS, "Content-Type":"application/x-www-form-urlencoded",
                                "Referer":f"https://mops.twse.com.tw/mops/web/{endpoint_name.removeprefix('ajax_')}"}, timeout=18)
                    response.raise_for_status()
                    response.encoding = "utf-8"
                    tables = read_html_tables(response.text)
                    period_rows = []
                    for table in tables:
                        if table.empty:
                            continue
                        header_index = None
                        for index in range(min(8, len(table))):
                            cells = [str(value).strip() for value in table.iloc[index].tolist()]
                            if any("公司代號" in value or "公司代碼" in value for value in cells):
                                header_index = index
                                break
                        if header_index is not None:
                            headers = [str(value).strip() for value in table.iloc[header_index].tolist()]
                            table = table.iloc[header_index + 1:].copy()
                            table.columns = headers
                        else:
                            table.columns = flatten_columns(table.columns)
                        for record in table.to_dict(orient="records"):
                            code = valid_code(record.get("公司代號") or record.get("公司代碼") or record.get("證券代號"))
                            if not code:
                                continue
                            record["公司代號"] = code
                            record["年度"] = str(roc_year)
                            record["季別"] = str(quarter)
                            period_rows.append(record)
                    if period_rows:
                        rows.extend(period_rows)
                        parsed_this_period = True
                        break
                except Exception as exc:
                    if attempt == 1:
                        print("warning MOPS history", endpoint_name, market, year, quarter, exc)
                    time.sleep(.15)
            if parsed_this_period:
                break
        time.sleep(.08)
    return rows

def fetch_financial_rows(session: requests.Session, urls: list[str]) -> list[dict]:
    rows = []
    for url in urls:
        try:
            data = get_json(session, url)
            if isinstance(data, list):
                rows.extend(row for row in data if isinstance(row, dict))
        except Exception as exc:
            print("warning financial", url, exc)
    return rows


def period_key(row: dict) -> tuple[int, int]:
    year = int(number(pick(row, "year")) or 0)
    quarter = int(number(pick(row, "quarter")) or 0)
    # ROC years.
    if 0 < year < 1911:
        year += 1911
    return year, quarter


def parse_income(rows: list[dict]) -> dict[str, list[dict]]:
    merged: dict[tuple[str, int, int], dict] = {}
    for row in rows:
        code = valid_code(pick(row, "code"))
        if not code:
            continue
        year, quarter = period_key(row)
        parsed = {
            "year": year or None, "quarter": quarter or None,
            "revenue": number(pick(row, "revenue")),
            "gross_profit": number(pick(row, "gross_profit")),
            "operating_income": number(pick(row, "operating_income")),
            "net_income": number(pick(row, "net_income")),
            "eps": number(pick(row, "eps")),
        }
        if not any(value is not None for key, value in parsed.items() if key not in {"year","quarter"}):
            continue
        key = (code, year, quarter)
        current = merged.get(key, {"year": year or None, "quarter": quarter or None})
        for field, value in parsed.items():
            if value is not None:
                current[field] = value
        merged[key] = current

    out = defaultdict(list)
    for (code, _, _), row in merged.items():
        out[code].append(row)
    for code in out:
        out[code].sort(key=lambda item: (item.get("year") or 0, item.get("quarter") or 0), reverse=True)
    return out

def parse_balance(rows: list[dict]) -> dict[str, list[dict]]:
    merged: dict[tuple[str, int, int], dict] = {}
    for row in rows:
        code = valid_code(pick(row, "code"))
        if not code:
            continue
        year, quarter = period_key(row)
        parsed = {
            "year": year or None, "quarter": quarter or None,
            "current_assets": number(pick(row, "current_assets")),
            "total_assets": number(pick(row, "total_assets")),
            "current_liabilities": number(pick(row, "current_liabilities")),
            "total_liabilities": number(pick(row, "total_liabilities")),
            "equity": number(pick(row, "equity")),
        }
        if not any(value is not None for key, value in parsed.items() if key not in {"year","quarter"}):
            continue
        key = (code, year, quarter)
        current = merged.get(key, {"year": year or None, "quarter": quarter or None})
        for field, value in parsed.items():
            if value is not None:
                current[field] = value
        merged[key] = current

    out = defaultdict(list)
    for (code, _, _), row in merged.items():
        out[code].append(row)
    for code in out:
        out[code].sort(key=lambda item: (item.get("year") or 0, item.get("quarter") or 0), reverse=True)
    return out

def parse_valuation(rows: list[dict]) -> dict[str, dict]:
    out = {}
    for row in rows:
        code = valid_code(pick(row, "code"))
        if not code:
            continue
        values = {
            "pe": number(pick(row, "pe")),
            "pb": number(pick(row, "pb")),
            "dividend_yield": number(pick(row, "yield")),
        }
        if any(value is not None for value in values.values()):
            out[code] = values
    return out


def safe_ratio(numerator, denominator, multiplier=1.0):
    if numerator is None or denominator in (None, 0):
        return None
    value = numerator / denominator * multiplier
    return value if math.isfinite(value) else None


def merge_financial_history(previous: list[dict], current: list[dict], limit=12) -> list[dict]:
    merged: dict[tuple[int, int], dict] = {}
    for row in [*(previous or []), *(current or [])]:
        key = (int(row.get("year") or 0), int(row.get("quarter") or 0))
        base = merged.get(key, {})
        merged[key] = {**base, **{field:value for field,value in row.items() if value is not None}}
    return sorted(merged.values(), key=lambda row:(row.get("year") or 0,row.get("quarter") or 0), reverse=True)[:limit]


def latest_by_code(rows: list[dict]) -> dict[str, dict]:
    output = {}
    for row in rows:
        code = valid_code(pick(row, "code"))
        if not code:
            continue
        year, quarter = period_key(row)
        candidate = {**row, "__period": (year, quarter)}
        if code not in output or candidate["__period"] > output[code]["__period"]:
            output[code] = candidate
    return output


def parse_monthly_revenue(rows: list[dict]) -> dict[str, dict]:
    output: dict[str, dict] = {}
    periods: dict[str, tuple[int, int]] = {}
    for row in rows:
        code = valid_code(pick(row, "code"))
        if not code:
            continue
        year = int(number(pick(row, "year")) or 0)
        if 0 < year < 1911:
            year += 1911
        month = int(number(row.get("月份") or row.get("月") or row.get("month")) or 0)
        period = (year, month)
        if code in periods and period < periods[code]:
            continue
        periods[code] = period
        output[code] = {
            "year": year or None,
            "month": month or None,
            "revenue": number(pick(row, "revenue")),
            "monthly_yoy_percent": number(row.get("去年同月增減(%)") or row.get("去年同月增減％") or row.get("去年同月增減")),
            "monthly_mom_percent": number(row.get("上月比較增減(%)") or row.get("上月比較增減％") or row.get("上月比較增減")),
        }
    return output

def parse_dividends(rows: list[dict]) -> dict[str, dict]:
    output = {}
    for code, row in latest_by_code(rows).items():
        cash = number(row.get("盈餘分配之現金股利(元/股)") or row.get("現金股利") or row.get("股東配發-盈餘分配之現金股利(元/股)"))
        stock = number(row.get("盈餘轉增資配股(元/股)") or row.get("股票股利") or row.get("股東配發-盈餘轉增資配股(元/股)"))
        output[code] = {
            "cash_dividend": cash,
            "stock_dividend": stock,
            "ex_dividend_date": str(row.get("除息交易日") or row.get("除權息交易日") or "").strip() or None,
            "ex_right_date": str(row.get("除權交易日") or "").strip() or None,
            "announcement_date": str(row.get("董事會決議日期") or row.get("資料日期") or "").strip() or None,
        }
    return output


def analysis_for(code: str, income_map, balance_map, valuation_map) -> tuple[dict, list[dict], str]:
    incomes = income_map.get(code, [])
    balances = balance_map.get(code, [])
    income = incomes[0] if incomes else {}
    balance = balances[0] if balances else {}
    metrics = {**valuation_map.get(code, {})}
    for key in ("eps", "revenue", "gross_profit", "operating_income", "net_income"):
        if income.get(key) is not None:
            metrics[key] = income[key]
    metrics["gross_margin"] = safe_ratio(income.get("gross_profit"), income.get("revenue"), 100)
    metrics["operating_margin"] = safe_ratio(income.get("operating_income"), income.get("revenue"), 100)
    metrics["net_margin"] = safe_ratio(income.get("net_income"), income.get("revenue"), 100)
    metrics["debt_ratio"] = safe_ratio(balance.get("total_liabilities"), balance.get("total_assets"), 100)
    metrics["current_ratio"] = safe_ratio(balance.get("current_assets"), balance.get("current_liabilities"))
    annualizer = 4 / (income.get("quarter") or 4) if income.get("quarter") else 1
    metrics["roe"] = safe_ratio(income.get("net_income"), balance.get("equity"), 100)
    if metrics["roe"] is not None:
        metrics["roe"] *= annualizer
    metrics = {key: value for key, value in metrics.items() if value is not None}

    history = []
    balances_by_period = {(row.get("year"), row.get("quarter")): row for row in balances}
    for row in incomes[:8]:
        b = balances_by_period.get((row.get("year"), row.get("quarter")), {})
        history.append({
            **row,
            "total_assets": b.get("total_assets"),
            "total_liabilities": b.get("total_liabilities"),
            "equity": b.get("equity"),
        })
    coverage = sum(key in metrics for key in ("eps","pe","pb","dividend_yield","roe","debt_ratio","current_ratio","net_margin"))
    status = "complete" if coverage >= 6 else "partial" if coverage >= 2 else "basic"
    return metrics, history, status


def stability_score(metrics: dict) -> float | None:
    parts = []
    if metrics.get("roe") is not None:
        parts.append(max(0, min(100, 50 + metrics["roe"] * 2)))
    if metrics.get("debt_ratio") is not None:
        parts.append(max(0, min(100, 100 - metrics["debt_ratio"])))
    if metrics.get("current_ratio") is not None:
        parts.append(max(0, min(100, metrics["current_ratio"] * 40)))
    if metrics.get("net_margin") is not None:
        parts.append(max(0, min(100, 50 + metrics["net_margin"] * 2)))
    if metrics.get("pe") is not None and metrics["pe"] > 0:
        parts.append(max(0, min(100, 100 - metrics["pe"] * 2)))
    return sum(parts) / len(parts) if parts else None


def rank_assets(assets: list[dict]) -> None:
    groups = defaultdict(list)
    for asset in assets:
        if asset.get("market") == "TW" and asset.get("asset_class") == "stock":
            groups[asset.get("official_industry") or "其他"].append(asset)

    for group in groups.values():
        total = len(group)
        for metric, label, reverse in [
            ("eps", "eps", True), ("roe", "roe", True), ("stability_score", "stability", True)
        ]:
            ranked = [asset for asset in group if asset.get("metrics", {}).get(metric) is not None]
            ranked.sort(key=lambda asset: asset["metrics"][metric], reverse=reverse)
            for index, asset in enumerate(ranked, 1):
                asset.setdefault("rankings", {})[label] = f"第 {index} / {len(ranked)}"
        pes = sorted(asset["metrics"]["pe"] for asset in group
                     if asset.get("metrics", {}).get("pe") is not None and asset["metrics"]["pe"] > 0)
        for asset in group:
            pe = asset.get("metrics", {}).get("pe")
            if pe is not None and pe > 0 and pes:
                lower = sum(1 for value in pes if value <= pe)
                asset.setdefault("rankings", {})["valuation"] = f"{lower / len(pes) * 100:.0f} 百分位"
            asset.setdefault("rankings", {})["industry_total"] = total


def dependency_preflight() -> None:
    missing = []
    for module_name in ("pandas", "lxml", "html5lib"):
        try:
            __import__(module_name)
        except Exception:
            missing.append(module_name)
    if missing:
        raise SystemExit(
            "Missing HTML parser dependencies: " + ", ".join(missing) +
            ". Run pip install -r requirements.txt."
        )


def main() -> None:
    dependency_preflight()
    previous = load_previous()
    previous_map = {row.get("id"): row for row in previous.get("assets", []) if row.get("id")}
    session = requests.Session()
    assets: dict[str, dict] = {}
    official_rows = 0

    for exchange, cls, url in MASTER_SOURCES:
        try:
            for row in get_json(session, url):
                asset = normalize_master(row, exchange, cls)
                if not asset:
                    continue
                old = previous_map.get(asset["id"], {})
                merged_asset = {
                    **old, **asset,
                    "metrics": old.get("metrics") or {},
                    "financials": old.get("financials") or [],
                    "rankings": old.get("rankings") or {},
                }
                if asset.get("asset_class") == "etf":
                    merged_asset["etf"] = {**(old.get("etf") or {}), **(asset.get("etf") or {})}
                assets[asset["id"]] = merged_asset
                official_rows += 1
        except Exception as exc:
            print("warning master", exchange, cls, exc)

    # Preserve markets and manually curated rows that are outside the current official response.
    for aid, row in previous_map.items():
        assets.setdefault(aid, row)

    spec, tpex_base = swagger_info(session)
    tpex_income_paths = discover_paths(spec, ("上櫃公司", "綜合損益表"))
    tpex_balance_paths = discover_paths(spec, ("上櫃公司", "資產負債表"))
    tpex_valuation_paths = discover_paths(spec, ("本益比", "殖利率", "股價淨值比"))
    if not tpex_income_paths:
        tpex_income_paths = [f"/mopsfin_t187ap06_O_{suffix}" for suffix in ("ci","mim","basi","bd","fh","ins")]
    if not tpex_balance_paths:
        tpex_balance_paths = [f"/mopsfin_t187ap07_O_{suffix}" for suffix in ("ci","mim","basi","bd","fh","ins")]
    tpex_income_urls = [urljoin(tpex_base + "/", path.lstrip("/")) for path in tpex_income_paths]
    tpex_balance_urls = [urljoin(tpex_base + "/", path.lstrip("/")) for path in tpex_balance_paths]
    tpex_valuation_urls = [urljoin(tpex_base + "/", path.lstrip("/")) for path in tpex_valuation_paths[:3]]
    if not tpex_valuation_urls:
        tpex_valuation_urls = [
            "https://www.tpex.org.tw/web/stock/aftertrading/peratio_analysis/pera_result.php?l=zh-tw&o=json"
        ]

    income_rows = fetch_financial_rows(session, [TWSE_BASE + path for path in TWSE_INCOME_PATHS] + tpex_income_urls)
    balance_rows = fetch_financial_rows(session, [TWSE_BASE + path for path in TWSE_BALANCE_PATHS] + tpex_balance_urls)

    eps_rows = fetch_financial_rows(session, [TWSE_EPS_URL, TPEX_EPS_URL])
    operating_rows = fetch_financial_rows(session, [TWSE_OPERATING_URL, TPEX_OPERATING_URL])

    # Current-quarter OpenAPI tables only contain companies that have already
    # filed. Pull the latest four official MOPS quarters so a company that has
    # not filed the newest quarter still uses its most recent published report.
    quarters = recent_quarters(4)
    mops_income_rows: list[dict] = []
    mops_balance_rows: list[dict] = []
    mops_operating_rows: list[dict] = []
    for market in ("sii", "otc"):
        mops_income_rows.extend(fetch_mops_history(session, "ajax_t163sb04", market, quarters))
        mops_balance_rows.extend(fetch_mops_history(session, "ajax_t163sb05", market, quarters))
        mops_operating_rows.extend(fetch_mops_history(session, "ajax_t163sb06", market, quarters))

    income_rows.extend(eps_rows)
    income_rows.extend(operating_rows)
    income_rows.extend(mops_income_rows)
    income_rows.extend(mops_operating_rows)
    balance_rows.extend(mops_balance_rows)
    revenue_rows = fetch_financial_rows(session, [TWSE_REVENUE_URL, TPEX_REVENUE_URL])
    dividend_rows = fetch_financial_rows(session, [TWSE_DIVIDEND_URL, TPEX_DIVIDEND_URL])

    valuation_rows = []
    try:
        valuation_rows.extend(get_json(session, f"{TWSE_BASE}/exchangeReport/BWIBBU_ALL"))
    except Exception as exc:
        print("warning TWSE valuation", exc)
    valuation_rows.extend(fetch_financial_rows(session, tpex_valuation_urls))

    income_map = parse_income(income_rows)
    balance_map = parse_balance(balance_rows)
    valuation_map = parse_valuation(valuation_rows)
    revenue_map = parse_monthly_revenue(revenue_rows)
    dividend_map = parse_dividends(dividend_rows)

    enriched = 0
    coverage_fields = ("eps","pe","pb","dividend_yield","roe","debt_ratio","current_ratio","net_margin")
    for asset in assets.values():
        if asset.get("market") != "TW" or asset.get("asset_class") != "stock":
            continue
        symbol = asset["symbol"]
        metrics, current_history, _ = analysis_for(symbol, income_map, balance_map, valuation_map)
        asset["metrics"] = {**(asset.get("metrics") or {}), **metrics}
        asset["financials"] = merge_financial_history(asset.get("financials") or [], current_history)
        if symbol in revenue_map:
            asset["monthly_revenue"] = revenue_map[symbol]
        if symbol in dividend_map:
            asset["dividend"] = dividend_map[symbol]
        score = stability_score(asset["metrics"])
        if score is not None:
            asset["metrics"]["stability_score"] = round(score, 2)

        present = [field for field in coverage_fields if asset["metrics"].get(field) is not None]
        missing = [field for field in coverage_fields if asset["metrics"].get(field) is None]
        coverage = len(present)
        if coverage >= 6:
            status = "complete"
        elif coverage >= 2:
            status = "partial"
        elif coverage >= 1:
            status = "basic"
        else:
            status = "missing"
        if coverage:
            enriched += 1
        asset["analysis_status"] = status
        asset["analysis_coverage"] = {"present": present, "missing": missing, "count": coverage, "total": len(coverage_fields)}
        asset["analysis_note"] = (
            "官方最新財報與估值欄位已整合"
            if status == "complete"
            else "部分產業欄位不適用或官方來源尚未回傳，已列入覆蓋稽核"
            if status in {"partial","basic"}
            else "官方來源未回傳可用欄位，已列入缺漏清單"
        )
        asset["analysis_updated_at"] = NOW.isoformat(timespec="seconds")
        asset["analysis_source"] = "TWSE／TPEx 官方財報、EPS、營益分析、估值、月營收與股利資料"

    for aid, override in OVERRIDES.items():
        symbol = aid.split(":", 1)[1]
        base = assets.get(aid, {
            "id": aid, "market": "TW", "symbol": symbol, "currency": "TWD",
            "sector": "fund", "listing_status": "active", "metrics": {}, "financials": [],
        })
        aliases = list(dict.fromkeys([*(base.get("aliases") or []), *(override.get("aliases") or [])]))
        merged_override = {**base, **override, "id": aid, "market": "TW", "symbol": symbol,
                           "currency": "TWD", "sector": "fund", "aliases": aliases}
        merged_override["etf"] = {**(override.get("etf") or {}), **(base.get("etf") or {})}
        assets[aid] = merged_override

    rows = sorted(assets.values(), key=lambda row: (row.get("market",""), row.get("symbol","")))
    rank_assets(rows)

    stocks = [row for row in rows if row.get("market") == "TW" and row.get("asset_class") == "stock"]
    complete = [row for row in stocks if row.get("analysis_status") == "complete"]
    partial = [row for row in stocks if row.get("analysis_status") in {"partial","basic"}]
    missing = [row for row in stocks if row.get("analysis_status") == "missing"]
    field_counts = {
        field: sum(1 for row in stocks if row.get("metrics", {}).get(field) is not None)
        for field in ("eps","pe","pb","dividend_yield","roe","debt_ratio","current_ratio","net_margin")
    }
    coverage_payload = {
        "metadata": {
            "version":"v11.2.3","updated_at":NOW.isoformat(timespec="seconds"),
            "source":"TWSE／TPEx official OpenAPI coverage audit"
        },
        "summary": {
            "total_stocks":len(stocks),"complete":len(complete),"partial_or_basic":len(partial),
            "missing":len(missing),"with_any_analysis":len(stocks)-len(missing),
            "coverage_percent":round((len(stocks)-len(missing))/len(stocks)*100,2) if stocks else 0,
            "field_counts":field_counts
        },
        "missing_stocks": [
            {"symbol":row.get("symbol"),"name":row.get("name"),"exchange":row.get("exchange"),
             "industry":row.get("official_industry"),"missing":row.get("analysis_coverage",{}).get("missing",[])}
            for row in missing
        ],
        "partial_stocks": [
            {"symbol":row.get("symbol"),"name":row.get("name"),
             "coverage":row.get("analysis_coverage",{}).get("count",0),
             "missing":row.get("analysis_coverage",{}).get("missing",[])}
            for row in partial
        ]
    }
    if len(rows) < 20:
        raise SystemExit(f"Only {len(rows)} securities; previous master was not replaced.")
    if len(stocks) < 1000:
        raise SystemExit(f"Only {len(stocks)} listed/OTC stocks; official master is incomplete.")

    # Coverage gaps must be reported, not allowed to block the entire market update.
    # A single company can be absent from a current-quarter endpoint because of
    # filing timing, industry-specific statements, or an upstream schema change.
    target_1595 = next((row for row in stocks if row.get("symbol") == "1595"), None)
    quality_warnings = []
    if not target_1595:
        quality_warnings.append("TPEx stock 1595 is absent from the official security master.")
    elif target_1595.get("metrics", {}).get("eps") is None:
        quality_warnings.append("TPEx stock 1595 has no parsed EPS; listed in asset-coverage.json for follow-up.")
    if missing:
        quality_warnings.append(f"{len(missing)} stocks have no analysis fields and are listed in asset-coverage.json.")
    coverage_payload["quality_checks"] = {
        "master_stock_count_ok": len(stocks) >= 1000,
        "target_1595_present": bool(target_1595),
        "target_1595_eps_present": bool(target_1595 and target_1595.get("metrics", {}).get("eps") is not None),
        "warnings": quality_warnings,
    }
    COVERAGE_OUT.write_text(json.dumps(coverage_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for warning in quality_warnings:
        print("coverage warning:", warning)

    payload = {
        "metadata": {
            "version": "v11.2.3", "updated_at": NOW.isoformat(timespec="seconds"),
            "asset_count": len(rows), "official_rows": official_rows,
            "financially_enriched_stocks": enriched,
            "income_rows": len(income_rows), "balance_rows": len(balance_rows),
            "eps_rows": len(eps_rows), "operating_rows": len(operating_rows),
            "mops_income_rows": len(mops_income_rows), "mops_balance_rows": len(mops_balance_rows),
            "mops_operating_rows": len(mops_operating_rows),
            "revenue_rows": len(revenue_rows), "dividend_rows": len(dividend_rows),
            "coverage_percent": coverage_payload["summary"]["coverage_percent"],
            "note": "Official master, EPS, operating analysis, valuation, financial statements, monthly revenue, dividends and coverage audit.",
        },
        "assets": rows,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED.write_text("window.__ASSET_SEED__ = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    print("assets", len(rows), "financially enriched", enriched)


if __name__ == "__main__":
    main()
