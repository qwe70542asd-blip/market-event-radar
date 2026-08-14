#!/usr/bin/env python3
"""Build a full-market Taiwan stock basic-information channel.

Coverage scope:
- Every currently listed TWSE company returned by the official TWSE company master.
- Every currently listed TPEx company returned by the official TPEx company master.

Source priority:
1. TWSE / TPEx official company master (all-market baseline)
2. Existing official assets.json fields
3. Previous stock-basics archive
4. Yahoo Taiwan profile, updated progressively for display-only gaps

The script never limits the universe to the portfolio or a hand-picked symbol list.
Advanced valuation and historical financial data are separate channels and are not
counted as missing basic company information.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any

import requests
from bs4 import BeautifulSoup

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.44"
TIMEOUT = 25
YAHOO_BATCH = 48
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


INDUSTRY_NAMES = {
    "01":"水泥工業","02":"食品工業","03":"塑膠工業","04":"紡織纖維","05":"電機機械",
    "06":"電器電纜","08":"玻璃陶瓷","09":"造紙工業","10":"鋼鐵工業","11":"橡膠工業",
    "12":"汽車工業","14":"建材營造","15":"航運業","16":"觀光餐旅","17":"金融保險",
    "18":"貿易百貨","19":"綜合企業","20":"其他業","21":"化學工業","22":"生技醫療業",
    "23":"油電燃氣業","24":"半導體業","25":"電腦及週邊設備業","26":"光電業",
    "27":"通信網路業","28":"電子零組件業","29":"電子通路業","30":"資訊服務業",
    "31":"其他電子業","32":"文化創意業","33":"農業科技業","34":"電子商務業",
    "35":"綠能環保","36":"數位雲端","37":"運動休閒","38":"居家生活",
}

def normalized_industry(value: Any) -> tuple[str | None, str | None]:
    raw = clean(value)
    if not raw:
        return None, None
    # Four-to-six digit values are security codes accidentally copied into the
    # industry field by a few upstream rows. Never expose them as industries.
    if raw.isdigit() and len(raw) > 2:
        return None, None
    code = raw.zfill(2) if raw.isdigit() and len(raw) <= 2 else None
    return code, INDUSTRY_NAMES.get(code, raw)


def normalized_industry_candidates(*values: Any) -> tuple[str | None, str]:
    """Return the first valid industry from code/name/archive candidates.

    Old archives can contain a security code in both ``industry`` and
    ``industry_name``.  v11.4.32 only sanitized the first candidate, then could
    accidentally restore the numeric value from ``industry_name``.
    """
    for value in values:
        code, name = normalized_industry(value)
        if name and not str(name).isdigit():
            return code, name
    return None, "其他業"

OFFICIAL_ENDPOINTS = [
    ("TWSE 上市公司基本資料", "https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "TWSE"),
    ("TPEx 上櫃公司基本資料", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", "TPEx"),
]


def clean(value: Any) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text or None


def number(value: Any) -> float | None:
    text = clean(value)
    if not text:
        return None
    match = re.search(r"[-+]?\d[\d,]*(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def normalize_date(value: Any) -> str | None:
    """Normalize Gregorian/ROC company dates with calendar validation.

    Company masters contain both old Gregorian dates (for example 1950-12-29)
    and ROC dates.  Four-digit years are always treated as Gregorian; two/three
    digit years are ROC.  Compact YYYYMMDD and YY/YYYMMDD are both supported.
    """
    text = clean(value)
    if not text:
        return None
    token = re.sub(r"[年.]", "/", text).replace("月", "/").replace("日", "")

    year = month = day = None
    match = re.search(r"(?<!\d)(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?!\d)", token)
    if match:
        year, month, day = map(int, match.groups())
    else:
        match = re.search(r"(?<!\d)(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})(?!\d)", token)
        if match:
            roc, month, day = map(int, match.groups())
            year = roc + 1911
        else:
            compact = re.search(r"(?<!\d)(\d{8}|\d{6,7})(?!\d)", re.sub(r"\s+", "", text))
            if not compact:
                return None
            raw = compact.group(1)
            if len(raw) == 8:
                year, month, day = int(raw[:4]), int(raw[4:6]), int(raw[6:8])
            else:
                roc_digits = len(raw) - 4
                roc, month, day = int(raw[:roc_digits]), int(raw[roc_digits:roc_digits + 2]), int(raw[-2:])
                year = roc + 1911
    # Reject implausible four-digit values instead of silently interpreting them
    # as company dates.  Taiwan listed-company records legitimately reach back
    # well before 2000, so the lower bound must not be 20xx-only.
    if year is None or year < 1800 or year > NOW.year + 1:
        return None
    try:
        return date(year, month, day).isoformat()
    except (TypeError, ValueError):
        return None


def sane_company_date(value: Any, *, listed_date: Any = None, field: str = "established_date") -> str | None:
    day = normalize_date(value)
    if not day:
        return None
    parsed = date.fromisoformat(day)
    # Company master data must never move into the future.  Establishment also
    # cannot happen after the security is listed.  This catches schema drift
    # such as TPEx rows where a report date was previously mistaken for setup date.
    if parsed > NOW.date():
        return None
    if field == "established_date":
        listed = normalize_date(listed_date)
        if listed and parsed > date.fromisoformat(listed):
            return None
    return day


def sanitize_company_dates(record: dict[str, Any]) -> dict[str, Any]:
    row = dict(record or {})
    listed = sane_company_date(row.get("listed_date"), field="listed_date")
    established = sane_company_date(row.get("established_date"), listed_date=listed, field="established_date")
    if listed:
        row["listed_date"] = listed
    else:
        row.pop("listed_date", None)
    if established:
        row["established_date"] = established
    else:
        row.pop("established_date", None)
    return row


def value_from(row: dict[str, Any], *labels: str) -> Any:
    for label in labels:
        if label in row and clean(row.get(label)):
            return row.get(label)
    for key, value in row.items():
        if any(label in str(key) for label in labels) and clean(value):
            return value
    return None


def company_links(symbol: str, exchange: str) -> dict[str, str]:
    yahoo_symbol = f"{symbol}.TWO" if exchange == "TPEx" else symbol
    return {
        "official_url": f"https://mops.twse.com.tw/mops/web/t05st03?step=1&off=1&firstin=1&co_id={symbol}",
        "profile_url": f"https://tw.stock.yahoo.com/quote/{yahoo_symbol}/profile",
        "quote_url": f"https://tw.stock.yahoo.com/quote/{yahoo_symbol}",
        "financial_url": f"https://tw.stock.yahoo.com/quote/{yahoo_symbol}/income-statement",
    }


def official_record(row: dict[str, Any], source_name: str, source_url: str, exchange: str) -> dict[str, Any] | None:
    symbol = clean(value_from(row, "公司代號", "公司代碼", "SecuritiesCompanyCode"))
    if not symbol or not re.fullmatch(r"\d{4,6}[A-Z]?", symbol, re.I):
        return None
    symbol = symbol.upper()
    links = company_links(symbol, exchange)
    industry_code, industry_name = normalized_industry(value_from(row, "產業別", "產業類別", "Industry"))
    return {
        "symbol": symbol,
        "company_name": clean(value_from(row, "公司名稱", "CompanyName")),
        "short_name": clean(value_from(row, "公司簡稱", "CompanyAbbreviation")),
        "exchange": exchange,
        "market": "TW",
        "market_label": "上市" if exchange == "TWSE" else "上櫃",
        "asset_class": "stock",
        "currency": "TWD",
        "industry": industry_name,
        "industry_code": industry_code,
        "industry_name": industry_name,
        "address": clean(value_from(row, "住址", "地址", "Address")),
        "tax_id": clean(value_from(row, "營利事業統一編號", "統一編號", "UnifiedBusinessNo")),
        "chairperson": clean(value_from(row, "董事長", "Chairman")),
        "general_manager": clean(value_from(row, "總經理", "GeneralManager")),
        "spokesperson": clean(value_from(row, "發言人", "Spokesman")),
        "spokesperson_title": clean(value_from(row, "發言人職稱")),
        "deputy_spokesperson": clean(value_from(row, "代理發言人")),
        "phone": clean(value_from(row, "總機電話", "Telephone")),
        "fax": clean(value_from(row, "傳真機號碼", "Fax")),
        "established_date": normalize_date(value_from(row, "成立日期", "DateOfIncorporation")),
        "listed_date": normalize_date(value_from(row, "上市日期", "上櫃日期", "DateOfListing")),
        "par_value": clean(value_from(row, "普通股每股面額")),
        "paid_in_capital": number(value_from(row, "實收資本額", "PaidinCapital")),
        "private_placement_shares": number(value_from(row, "私募股數")),
        "preferred_shares": number(value_from(row, "特別股")),
        "issued_shares": number(value_from(row, "已發行普通股數", "已發行普通股數或TDR原股發行股數", "TDR原發行股數", "IssuedShares")),
        "transfer_agent": clean(value_from(row, "股票過戶機構")),
        "accounting_firm": clean(value_from(row, "簽證會計師事務所")),
        "auditor_1": clean(value_from(row, "簽證會計師1")),
        "auditor_2": clean(value_from(row, "簽證會計師2")),
        "website": clean(value_from(row, "網址", "URL", "公司網站")),
        "email": clean(value_from(row, "電子郵件信箱", "Email")),
        "english_name": clean(value_from(row, "英文簡稱", "EnglishAbbreviation")),
        "business_scope": clean(value_from(row, "主要經營業務", "BusinessScope")),
        "source": source_name,
        "source_level": "official",
        "source_url": source_url,
        **links,
    }


def fetch_official() -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    output: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    counts = {"TWSE": 0, "TPEx": 0}
    for source_name, url, exchange in OFFICIAL_ENDPOINTS:
        try:
            response = SESSION.get(url, timeout=TIMEOUT)
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list):
                raise ValueError("official endpoint did not return a list")
            for row in rows:
                record = official_record(row, source_name, url, exchange)
                if not record:
                    continue
                output[record["symbol"]] = sanitize_company_dates(record)
                counts[exchange] += 1
        except Exception as exc:
            errors.append({"source": source_name, "error": str(exc)[:500]})
    return output, errors, counts


PROFILE_LABELS = {
    "company_name": ("公司名稱",),
    "industry": ("產業類別",),
    "website": ("公司網站",),
    "chairperson": ("董事長",),
    "general_manager": ("總經理",),
    "phone": ("總機電話",),
    "address": ("公司地址",),
    "established_date": ("成立時間",),
    "listed_date": ("掛牌日期",),
    "paid_in_capital": ("股本",),
    "issued_shares": ("已發行普通股數",),
    "business_scope": ("主要經營業務",),
}


def lines_from_html(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    return [line for line in (clean(x) for x in soup.get_text("\n").splitlines()) if line]


def next_value(lines: list[str], labels: tuple[str, ...]) -> str | None:
    for index, line in enumerate(lines):
        if any(line == label or line.startswith(label + "：") for label in labels):
            inline = line.split("：", 1)[1].strip() if "：" in line else ""
            if inline:
                return inline
            for candidate in lines[index + 1:index + 5]:
                if candidate and candidate not in PROFILE_LABELS:
                    return candidate
    return None


def parse_yahoo_profile(symbol: str, exchange: str) -> dict[str, Any]:
    ticker_value = f"{symbol}.TWO" if exchange == "TPEx" else symbol
    url = f"https://tw.stock.yahoo.com/quote/{ticker_value}/profile"
    response = SESSION.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    lines = lines_from_html(response.text)
    result: dict[str, Any] = {
        "profile_url": url,
        "quote_url": f"https://tw.stock.yahoo.com/quote/{ticker_value}",
        "financial_url": f"https://tw.stock.yahoo.com/quote/{ticker_value}/income-statement",
        "reference_source": "Yahoo 股市公司基本資料",
        "reference_updated_at": NOW.isoformat(timespec="seconds"),
    }
    for key, labels in PROFILE_LABELS.items():
        value = next_value(lines, labels)
        if key in {"paid_in_capital", "issued_shares"}:
            result[key] = number(value)
        elif key in {"established_date", "listed_date"}:
            result[key] = normalize_date(value)
        else:
            result[key] = clean(value)
    return {key: value for key, value in result.items() if value not in (None, "", [])}


def merge_nonempty(*records: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for record in records:
        for key, value in (record or {}).items():
            if value in (None, "", []):
                continue
            if key == "metrics":
                output[key] = {**(output.get(key) or {}), **value}
            elif key == "financials":
                old = output.get(key) or []
                merged = {str(row.get("period") or row.get("date")): row for row in old if isinstance(row, dict)}
                for row in value:
                    if isinstance(row, dict):
                        merged[str(row.get("period") or row.get("date"))] = row
                output[key] = list(merged.values())
            elif key not in output:
                output[key] = value
    return output


def basic_coverage(row: dict[str, Any]) -> float:
    # These are the minimum fields every listed company page should provide.
    fields = [
        row.get("symbol"),
        row.get("company_name") or row.get("short_name"),
        row.get("asset_class"),
        row.get("market"),
        row.get("exchange"),
        row.get("industry"),
        row.get("currency"),
        row.get("listed_date"),
        row.get("paid_in_capital"),
        row.get("issued_shares"),
        row.get("official_url"),
        row.get("profile_url") or row.get("quote_url"),
    ]
    return round(sum(value not in (None, "", []) for value in fields) / len(fields) * 100, 1)


def financial_coverage(row: dict[str, Any]) -> float:
    metrics = row.get("metrics") or {}
    fields = [metrics.get(key) for key in ("pe", "pb", "dividend_yield", "eps", "roe", "debt_ratio", "net_margin", "current_ratio")]
    metric_score = sum(value not in (None, "", []) for value in fields) / len(fields)
    statements = row.get("financials") or []
    statement_score = min(len(statements), 12) / 12
    return round((metric_score * 0.6 + statement_score * 0.4) * 100, 1)


def existing_asset_records() -> dict[str, dict[str, Any]]:
    rows = read_json(DATA / "assets.json", {"assets": []}).get("assets", [])
    output: dict[str, dict[str, Any]] = {}
    for asset in rows:
        if asset.get("market") != "TW" or asset.get("asset_class") != "stock" or not asset.get("symbol"):
            continue
        symbol = str(asset["symbol"]).upper()
        output[symbol] = sanitize_company_dates({
            "symbol": symbol,
            "company_name": asset.get("company_name") or asset.get("name"),
            "short_name": asset.get("name"),
            "asset_class": "stock",
            "market": "TW",
            "exchange": asset.get("exchange"),
            "currency": asset.get("currency") or "TWD",
            "industry": asset.get("official_industry") or asset.get("sub_industry"),
            "address": asset.get("address"),
            "tax_id": asset.get("tax_id"),
            "chairperson": asset.get("chairperson"),
            "general_manager": asset.get("general_manager"),
            "spokesperson": asset.get("spokesperson"),
            "phone": asset.get("phone"),
            "established_date": asset.get("established_date"),
            "listed_date": asset.get("listed_date"),
            "paid_in_capital": asset.get("paid_in_capital"),
            "issued_shares": asset.get("issued_shares"),
            "website": asset.get("website"),
            "business_scope": asset.get("business_scope"),
            "accounting_firm": asset.get("accounting_firm"),
            "metrics": asset.get("metrics"),
            "financials": asset.get("financials"),
        })
    return output


def main() -> None:
    old = read_json(DATA / "stock-basics.json", {"items": {}, "state": {}})
    old_items = old.get("items") or {}
    state = old.get("state") or {}
    official, errors, counts = fetch_official()
    asset_records = existing_asset_records()

    # Never collapse the market universe if one endpoint temporarily fails.
    universe = set(official) or set(old_items)
    if errors:
        universe.update(old_items)
    universe.update(symbol for symbol in asset_records if symbol in official or not official)
    symbols = sorted(universe)

    # All official companies are emitted immediately. Yahoo is only a progressive
    # enhancement and never controls whether a company exists in the dataset.
    cursor = int(state.get("yahoo_cursor") or 0)
    cursor = cursor if cursor < len(symbols) else 0
    yahoo_batch = symbols[cursor:cursor + YAHOO_BATCH]
    if len(yahoo_batch) < YAHOO_BATCH:
        yahoo_batch += symbols[:YAHOO_BATCH - len(yahoo_batch)]
    yahoo_results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(parse_yahoo_profile, symbol, str((official.get(symbol) or old_items.get(symbol) or {}).get("exchange") or "TWSE")): symbol
            for symbol in yahoo_batch
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                yahoo_results[symbol] = future.result()
            except Exception as exc:
                errors.append({"symbol": symbol, "source": "Yahoo profile", "error": str(exc)[:400]})

    items: dict[str, dict[str, Any]] = {}
    below_90: list[str] = []
    for symbol in symbols:
        # Official record has highest priority, followed by existing official fields,
        # then the preserved archive and the new Yahoo reference-only enhancement.
        merged = merge_nonempty(
            sanitize_company_dates(official.get(symbol) or {}),
            sanitize_company_dates(asset_records.get(symbol) or {}),
            sanitize_company_dates(old_items.get(symbol) or {}),
            sanitize_company_dates(yahoo_results.get(symbol) or {}),
        )
        merged = sanitize_company_dates(merged)
        if not merged:
            continue
        exchange = str(merged.get("exchange") or "TWSE")
        merged = merge_nonempty(merged, company_links(symbol, exchange))
        merged["symbol"] = symbol
        merged["asset_class"] = "stock"
        merged["market"] = "TW"
        merged["currency"] = merged.get("currency") or "TWD"
        code, industry_name = normalized_industry_candidates(
            merged.get("industry_code"),
            merged.get("industry"),
            merged.get("industry_name"),
        )
        merged["industry_code"] = code
        merged["industry_name"] = industry_name
        merged["industry"] = industry_name
        merged["basic_coverage_percent"] = basic_coverage(merged)
        merged["financial_coverage_percent"] = financial_coverage(merged)
        merged["updated_at"] = NOW.isoformat(timespec="seconds")
        merged["source_summary"] = "公司主檔與財務資料分開計算；TWSE／TPEx 官方主檔優先，Yahoo 僅補空白欄位"
        if merged["basic_coverage_percent"] < 90:
            below_90.append(symbol)
        items[symbol] = merged

    next_cursor = (cursor + len(yahoo_batch)) % len(symbols) if symbols else 0
    average = round(sum(row.get("basic_coverage_percent", 0) for row in items.values()) / max(1, len(items)), 1)
    financial_average = round(sum(row.get("financial_coverage_percent", 0) for row in items.values()) / max(1, len(items)), 1)
    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": "ok" if items and not [error for error in errors if not error.get("symbol")] else "partial" if items else "warning",
            "item_count": len(items),
            "twse_count": sum(row.get("exchange") == "TWSE" for row in items.values()),
            "tpex_count": sum(row.get("exchange") == "TPEx" for row in items.values()),
            "official_endpoint_counts": counts,
            "average_basic_coverage_percent": average,
            "average_financial_coverage_percent": financial_average,
            "below_90_count": len(below_90),
            "scope": "all-currently-listed-twse-and-tpex-stocks",
            "note": "Company-master coverage and financial-data coverage are separate metrics. A high company-master score never implies complete financial statements.",
        },
        "state": {
            "yahoo_cursor": next_cursor,
            "yahoo_batch_size": len(yahoo_batch),
            "last_yahoo_batch_at": NOW.isoformat(timespec="seconds"),
        },
        "below_90_symbols": below_90[:500],
        "errors": errors[:200],
        "items": items,
    }
    write_payload("stock-basics.json", "__STOCK_BASICS_SEED__", payload)
    print(payload["metadata"])


if __name__ == "__main__":
    main()
