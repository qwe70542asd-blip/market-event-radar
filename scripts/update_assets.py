#!/usr/bin/env python3
"""Update the v11.4.1 Taiwan stock and ETF master with detailed official data.

The updater is intentionally defensive:
- official TWSE/TPEx endpoints are parsed with bilingual/format-tolerant keys;
- one failed source never clears the last successful asset archive;
- valuation, income statement and balance sheet states are kept separately;
- up to twelve quarterly snapshots are preserved for every stock;
- missing, not-applicable and source-failure states remain distinguishable.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable

import requests

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.1"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.4.1)"}
SESSION = requests.Session()

MASTER_SOURCES = [
    ("TWSE company master", "https://openapi.twse.com.tw/v1/opendata/t187ap03_L", "TWSE"),
    ("TPEx company master", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O", "TPEx"),
]
VALUATION_SOURCES = [
    ("TWSE valuation", "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", "TWSE"),
    ("TPEx valuation", "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis", "TPEx"),
]
EPS_SOURCES = [
    ("TWSE EPS", "https://openapi.twse.com.tw/v1/opendata/t187ap14_L", "TWSE"),
    ("TPEx EPS", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap14_O", "TPEx"),
]
SECTOR_SUFFIXES = ("ci", "fh", "basi", "bd", "ins", "mim")

FUND_SOURCES = [
    ("TWSE fund master", "https://openapi.twse.com.tw/v1/opendata/t187ap47_L", "TWSE"),
]
MONTHLY_REVENUE_SOURCES = [
    ("TWSE monthly revenue", "https://openapi.twse.com.tw/v1/opendata/t187ap05_L", "TWSE"),
    ("TPEx monthly revenue", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O", "TPEx"),
]
DIVIDEND_SOURCES = [
    ("TWSE dividend", "https://openapi.twse.com.tw/v1/opendata/t187ap45_L", "TWSE"),
    ("TPEx dividend", "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap39_O", "TPEx"),
]
INDUSTRY_NAMES = {
    "01":"水泥工業","02":"食品工業","03":"塑膠工業","04":"紡織纖維","05":"電機機械","06":"電器電纜",
    "07":"化學生技醫療","08":"玻璃陶瓷","09":"造紙工業","10":"鋼鐵工業","11":"橡膠工業","12":"汽車工業",
    "13":"電子工業","14":"建材營造","15":"航運業","16":"觀光餐旅","17":"金融保險業","18":"貿易百貨",
    "20":"其他業","21":"化學工業","22":"生技醫療業","23":"油電燃氣業","24":"半導體業",
    "25":"電腦及週邊設備業","26":"光電業","27":"通信網路業","28":"電子零組件業","29":"電子通路業",
    "30":"資訊服務業","31":"其他電子業","32":"文化創意業","33":"農業科技業","34":"電子商務",
    "35":"綠能環保","36":"數位雲端","37":"運動休閒","38":"居家生活",
}


# Python str has no normalize method; keep this small helper explicit.
def normalized_key(value: Any) -> str:  # type: ignore[no-redef]
    import unicodedata

    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", text)


def row_value(row: dict[str, Any], aliases: Iterable[str]) -> Any:
    keyed = {normalized_key(key): value for key, value in row.items()}
    normalized_aliases = [normalized_key(alias) for alias in aliases]
    for alias in normalized_aliases:
        if alias in keyed:
            return keyed[alias]
    for alias in normalized_aliases:
        for key, value in keyed.items():
            if alias and (alias in key or key in alias):
                return value
    return None


def number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "").replace("％", "").replace("%", "")
    if not text or text in {"-", "--", "---", "N/A", "NA", "不適用", "無"}:
        return None
    negative_parentheses = text.startswith("(") and text.endswith(")")
    text = re.sub(r"[^0-9.+-]", "", text)
    try:
        value_float = float(text)
        if negative_parentheses:
            value_float = -abs(value_float)
    except (TypeError, ValueError):
        return None
    return value_float if value_float == value_float else None


def status_for_raw(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"-", "--", "---", "N/A", "NA", "不適用", "無"}:
        return "not_applicable"
    return "available" if number(value) is not None else "missing"


def symbol_of(row: dict[str, Any]) -> str:
    value = row_value(
        row,
        (
            "公司代號",
            "證券代號",
            "股票代號",
            "Code",
            "SecuritiesCompanyCode",
            "CompanyCode",
            "StockNo",
        ),
    )
    return str(value or "").strip().upper()


def fetch_rows(name: str, url: str, health: list[dict[str, Any]], timeout: int = 28) -> list[dict[str, Any]]:
    try:
        response = SESSION.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("official response is not a list")
        health.append({"name": name, "status": "ok", "rows": len(payload), "url": url})
        return [row for row in payload if isinstance(row, dict)]
    except Exception as exc:
        health.append({"name": name, "status": "warning", "error": str(exc), "url": url})
        return []


def roc_year(value: Any) -> int | None:
    match = re.search(r"(\d{2,4})", str(value or ""))
    if not match:
        return None
    year = int(match.group(1))
    return year + 1911 if year < 1911 else year


def quarter_of(row: dict[str, Any]) -> tuple[str | None, int | None, int | None]:
    year = roc_year(row_value(row, ("年度", "年", "Year", "FiscalYear")))
    quarter_raw = row_value(row, ("季別", "季度", "季", "Quarter", "Season"))
    quarter_match = re.search(r"([1-4])", str(quarter_raw or ""))
    quarter = int(quarter_match.group(1)) if quarter_match else None
    if not year:
        date_raw = row_value(row, ("資料日期", "出表日期", "報告日期", "Date", "ReportDate"))
        date_match = re.search(r"(\d{3,4})[/-](\d{1,2})", str(date_raw or ""))
        if date_match:
            year = int(date_match.group(1))
            year = year + 1911 if year < 1911 else year
            month = int(date_match.group(2))
            quarter = quarter or (month - 1) // 3 + 1
    period = f"{year}Q{quarter}" if year and quarter else None
    return period, year, quarter


def pick(row: dict[str, Any], *aliases: str) -> float | None:
    return number(row_value(row, aliases))


def financial_row(row: dict[str, Any], kind: str, source_name: str) -> tuple[str, dict[str, Any]] | None:
    symbol = symbol_of(row)
    period, year, quarter = quarter_of(row)
    if not symbol or not period:
        return None
    base: dict[str, Any] = {
        "period": period,
        "year": year,
        "quarter": quarter,
        "source": source_name,
        "source_updated_at": NOW.isoformat(timespec="seconds"),
    }
    if kind == "income":
        base.update(
            revenue=pick(row, "營業收入", "營業收益", "收益", "利息淨收益", "收入合計", "Revenue", "OperatingRevenue", "TotalRevenue"),
            gross_profit=pick(row, "營業毛利（毛損）", "營業毛利毛損", "營業毛利", "GrossProfit"),
            operating_income=pick(row, "營業利益（損失）", "營業利益損失", "營業利益", "OperatingIncome", "OperatingProfitLoss"),
            pretax_income=pick(row, "稅前淨利（淨損）", "稅前淨利淨損", "稅前淨利", "ProfitBeforeTax"),
            net_income=pick(row, "本期淨利（淨損）", "本期淨利淨損", "本期淨利", "本期稅後淨利", "稅後淨利", "NetIncome", "ProfitLoss"),
            eps=pick(row, "基本每股盈餘（元）", "基本每股盈餘元", "基本每股盈餘", "每股盈餘", "EPS", "BasicEarningsPerShare"),
        )
    else:
        base.update(
            total_assets=pick(row, "資產總額", "資產總計", "資產合計", "TotalAssets"),
            total_liabilities=pick(row, "負債總額", "負債總計", "負債合計", "TotalLiabilities"),
            total_equity=pick(row, "權益總額", "權益總計", "權益合計", "股東權益總額", "TotalEquity"),
            current_assets=pick(row, "流動資產", "流動資產合計", "CurrentAssets"),
            current_liabilities=pick(row, "流動負債", "流動負債合計", "CurrentLiabilities"),
        )
    return symbol, base


def merge_financial(existing: list[dict[str, Any]], updates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in existing or []:
        period = str(row.get("period") or "")
        if period:
            merged[period] = dict(row)
    for row in updates:
        period = str(row.get("period") or "")
        if not period:
            continue
        clean = {key: value for key, value in row.items() if value is not None}
        merged[period] = {**merged.get(period, {}), **clean}

    def order_key(row: dict[str, Any]) -> tuple[int, int]:
        match = re.match(r"(\d{4})Q([1-4])", str(row.get("period") or ""))
        return (int(match.group(1)), int(match.group(2))) if match else (0, 0)

    return sorted(merged.values(), key=order_key, reverse=True)[:12]


def ratio(numerator: Any, denominator: Any, multiplier: float = 100.0) -> float | None:
    n, d = number(numerator), number(denominator)
    if n is None or d in (None, 0):
        return None
    return n / d * multiplier


def apply_metrics(asset: dict[str, Any], valuation: dict[str, Any] | None, eps_value: float | None) -> None:
    financials = asset.get("financials") or []
    latest = financials[0] if financials else {}
    old_metrics = dict(asset.get("metrics") or {})
    statuses = dict(asset.get("metric_status") or {})
    sources = dict(asset.get("metric_sources") or {})

    if valuation is not None:
        for key in ("pe", "pb", "dividend_yield"):
            old_metrics[key] = valuation.get(key)
            statuses[key] = valuation.get(f"{key}_status", "missing")
            sources[key] = valuation.get("source")
    eps = latest.get("eps") if number(latest.get("eps")) is not None else eps_value
    if eps is not None:
        old_metrics["eps"] = eps
        statuses["eps"] = "available"
        sources["eps"] = latest.get("source") or "official EPS ranking"
    elif "eps" not in old_metrics:
        old_metrics["eps"] = None
        statuses["eps"] = "missing"

    calculated = {
        "roe": ratio(latest.get("net_income"), latest.get("total_equity")),
        "debt_ratio": ratio(latest.get("total_liabilities"), latest.get("total_assets")),
        "net_margin": ratio(latest.get("net_income"), latest.get("revenue")),
        "current_ratio": ratio(latest.get("current_assets"), latest.get("current_liabilities")),
    }
    for key, value in calculated.items():
        if value is not None:
            old_metrics[key] = value
            statuses[key] = "available"
            sources[key] = latest.get("source") or "official financial statement calculation"
        elif key not in old_metrics:
            old_metrics[key] = None
            statuses[key] = "not_applicable" if key == "current_ratio" and any(word in str(asset.get("official_industry") or "") for word in ("金融", "保險", "銀行", "證券")) else "missing"

    asset["metrics"] = old_metrics
    asset["metric_status"] = statuses
    asset["metric_sources"] = sources
    asset["metrics_updated_at"] = NOW.isoformat(timespec="seconds") if valuation or financials or eps_value is not None else asset.get("metrics_updated_at")



def text_value(row: dict[str, Any], *aliases: str) -> str:
    return str(row_value(row, aliases) or "").strip()


def format_date(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    if len(digits) == 8 and digits[:4].isdigit():
        return f"{digits[:4]}/{digits[4:6]}/{digits[6:8]}"
    match = re.search(r"(\d{2,4})[年/.-](\d{1,2})[月/.-](\d{1,2})", text)
    if match:
        year, month, day = map(int, match.groups())
        if year < 1911:
            year += 1911
        return f"{year:04d}/{month:02d}/{day:02d}"
    return text


def industry_name(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    return INDUSTRY_NAMES.get(text.zfill(2), text)


def fund_symbol(row: dict[str, Any]) -> str:
    return text_value(row, "基金代號", "證券代號", "基金證券代號", "SecuritiesCode", "Code").upper()


def parse_fund_row(row: dict[str, Any], source_name: str, exchange: str) -> tuple[str, dict[str, Any]] | None:
    symbol = fund_symbol(row)
    if not symbol:
        return None
    name = text_value(row, "基金簡稱", "證券簡稱", "基金名稱", "ETF名稱", "Name", "SecuritiesName")
    formal_name = text_value(row, "基金全名", "基金名稱", "證券名稱", "FullName") or name
    category = text_value(row, "基金類型", "商品類型", "類別", "基金分類", "Category")
    management_style = text_value(row, "主動被動", "管理方式", "ManagementStyle")
    combined = f"{name} {formal_name} {category} {management_style}"
    if "ETF" not in combined.upper() and "指數股票型" not in combined and "主動式" not in combined :
        return None
    benchmark = text_value(row, "標的指數", "追蹤指數", "績效指標", "UnderlyingIndex", "Benchmark")
    is_active = "主動" in combined
    fund = {
        "formal_name": formal_name or None,
        "issuer": text_value(row, "投信事業", "證券投資信託事業", "基金經理公司", "發行公司", "發行人", "Issuer") or None,
        "manager": text_value(row, "基金經理人", "經理人", "FundManager", "Manager") or None,
        "custodian": text_value(row, "基金保管機構", "保管機構", "保管銀行", "Custodian") or None,
        "inception_date": format_date(row_value(row, ("成立日期", "基金成立日", "InceptionDate"))),
        "listing_date": format_date(row_value(row, ("上市日期", "上櫃日期", "掛牌日期", "ListingDate"))),
        "category": category or ("主動式 ETF" if is_active else "ETF"),
        "management_style": management_style or ("主動式管理" if is_active else "被動式管理"),
        "benchmark": benchmark or ("主動式管理，不追蹤特定指數" if is_active else None),
        "strategy": text_value(row, "投資策略", "基金特色", "Strategy") or None,
        "region": text_value(row, "投資區域", "Region") or None,
        "focus": text_value(row, "投資標的", "投資主題", "InvestmentFocus") or None,
        "currency": text_value(row, "計價幣別", "Currency") or "TWD",
        "management_fee": text_value(row, "經理費", "管理費", "ManagementFee") or None,
        "custody_fee": text_value(row, "保管費", "CustodyFee") or None,
        "distribution_frequency": text_value(row, "收益分配", "配息頻率", "Distribution") or None,
        "risk_level": text_value(row, "風險收益等級", "風險等級", "RiskLevel") or None,
        "leverage": text_value(row, "槓桿倍數", "正反向倍數", "Leverage") or None,
        "creation_redemption": text_value(row, "申購買回方式", "申贖方式", "CreationRedemption") or None,
        "aum": number(row_value(row, ("基金規模", "資產規模", "AUM"))),
        "units": number(row_value(row, ("受益權單位數", "發行受益權單位數", "Units"))),
        "beneficiary_count": number(row_value(row, ("受益人數", "BeneficiaryCount"))),
        "official_url": text_value(row, "網址", "基金網站", "Website", "URL") or None,
        "source": source_name,
        "updated_at": NOW.isoformat(timespec="seconds"),
    }
    return symbol, {
        "id": f"TW:{symbol}", "asset_class": "etf", "market": "TW", "exchange": exchange,
        "symbol": symbol, "name": name or formal_name or symbol, "company_name": formal_name or name or symbol,
        "currency": fund.get("currency") or "TWD", "sub_industry": fund.get("category") or "ETF", "etf": fund,
        "listed_date": fund.get("listing_date"), "master_updated_at": NOW.isoformat(timespec="seconds"),
    }


def year_month_of(row: dict[str, Any]) -> tuple[int | None, int | None]:
    raw = str(row_value(row, ("資料年月", "營業收入資料年月", "年月", "Period")) or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 5:  # ROC YYYMM
        return int(digits[:3]) + 1911, int(digits[3:])
    if len(digits) == 6:  # AD YYYYMM or short ROC YYYYMM
        year = int(digits[:4])
        return (year if year >= 1911 else year + 1911), int(digits[4:])
    match = re.search(r"(\d{2,4})[年/.-](\d{1,2})", raw)
    if match:
        year, month = map(int, match.groups())
        return (year if year >= 1911 else year + 1911), month
    year = roc_year(row_value(row, ("年度", "年", "Year")))
    month_match = re.search(r"(\d{1,2})", str(row_value(row, ("資料月份", "月份", "Month")) or ""))
    return year, int(month_match.group(1)) if month_match else None


def merge_period_rows(existing: list[dict[str, Any]], updates: Iterable[dict[str, Any]], key_name: str = "period", limit: int = 24) -> list[dict[str, Any]]:
    merged = {str(row.get(key_name) or ""): dict(row) for row in existing or [] if row.get(key_name)}
    for row in updates:
        key = str(row.get(key_name) or "")
        if key:
            merged[key] = {**merged.get(key, {}), **{k: v for k, v in row.items() if v is not None}}
    return sorted(merged.values(), key=lambda row: str(row.get(key_name) or ""), reverse=True)[:limit]

def financial_endpoint(exchange: str, statement: str, suffix: str) -> list[tuple[str, str]]:
    if exchange == "TWSE":
        code = "06" if statement == "income" else "07"
        return [
            (f"TWSE {statement} {suffix}", f"https://openapi.twse.com.tw/v1/opendata/t187ap{code}_L_{suffix}"),
            (f"TWSE public {statement} {suffix}", f"https://openapi.twse.com.tw/v1/opendata/t187ap{code}_X_{suffix}"),
        ]
    code = "06" if statement == "income" else "07"
    return [(f"TPEx {statement} {suffix}", f"https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap{code}_O_{suffix}")]


def main() -> None:
    old = read_json(DATA / "assets.json", {"assets": []})
    assets: dict[str, dict[str, Any]] = {
        str(row.get("id") or f"{row.get('market')}:{row.get('symbol')}"): dict(row)
        for row in old.get("assets", [])
        if row.get("symbol")
    }
    health: list[dict[str, Any]] = []

    # Preserve and bootstrap securities discovered by the latest official quote channel.
    market_payload = read_json(DATA / "tw-market.json", {"items": []})
    for quote in market_payload.get("items", []):
        symbol = str(quote.get("symbol") or "").strip().upper()
        if not symbol or quote.get("asset_class") not in {"stock", "etf"}:
            continue
        key = f"TW:{symbol}"
        previous = assets.get(key, {})
        assets[key] = {
            **previous,
            "id": key,
            "asset_class": quote.get("asset_class"),
            "market": "TW",
            "exchange": quote.get("exchange") or previous.get("exchange"),
            "symbol": symbol,
            "name": quote.get("name") or previous.get("name") or symbol,
            "currency": previous.get("currency") or "TWD",
        }

    # Official fund master.  ETF records override stock-like placeholders and are
    # kept separate from company financial statements.
    for source_name, url, exchange in FUND_SOURCES:
        for row in fetch_rows(source_name, url, health):
            parsed = parse_fund_row(row, source_name, exchange)
            if not parsed:
                continue
            symbol, fund_asset = parsed
            key = f"TW:{symbol}"
            previous = assets.get(key, {})
            old_fund = previous.get("etf") or {}
            fund_asset["etf"] = {**old_fund, **{k: v for k, v in (fund_asset.get("etf") or {}).items() if v not in (None, "")}}
            assets[key] = {**previous, **{k: v for k, v in fund_asset.items() if v not in (None, "")}}

    # Company master.
    for name, url, exchange in MASTER_SOURCES:
        for row in fetch_rows(name, url, health):
            symbol = symbol_of(row)
            if not symbol:
                continue
            key = f"TW:{symbol}"
            previous = assets.get(key, {})
            company_name = row_value(row, ("公司名稱", "CompanyName", "CompanyFullName"))
            short_name = row_value(row, ("公司簡稱", "CompanyAbbreviation", "證券名稱", "Name"))
            listed_date = format_date(row_value(row, ("上市日期", "上櫃日期", "ListingDate", "DateOfListing")))
            issued_shares = number(row_value(row, ("已發行普通股數或TDR原發行股數", "發行股數", "IssuedShares", "SharesOutstanding")))
            paid_in_capital = number(row_value(row, ("實收資本額", "PaidInCapital", "Capital")))
            industry = industry_name(row_value(row, ("產業別", "產業類別", "Industry", "IndustryName")))
            assets[key] = {
                **previous,
                "id": key,
                "asset_class": "stock",
                "market": "TW",
                "exchange": exchange,
                "symbol": symbol,
                "name": str(short_name or previous.get("name") or company_name or symbol).strip(),
                "company_name": str(company_name or previous.get("company_name") or short_name or "").strip(),
                "official_industry": industry or previous.get("official_industry"),
                "listed_date": listed_date or previous.get("listed_date"),
                "established_date": format_date(row_value(row, ("公司成立日期", "成立日期", "EstablishedDate"))) or previous.get("established_date"),
                "tax_id": text_value(row, "營利事業統一編號", "統一編號", "TaxID") or previous.get("tax_id"),
                "chairperson": text_value(row, "董事長", "Chairperson", "Chairman") or previous.get("chairperson"),
                "general_manager": text_value(row, "總經理", "GeneralManager", "President") or previous.get("general_manager"),
                "spokesperson": text_value(row, "發言人", "Spokesperson") or previous.get("spokesperson"),
                "phone": text_value(row, "總機電話", "公司電話", "Phone") or previous.get("phone"),
                "address": text_value(row, "住址", "公司地址", "Address") or previous.get("address"),
                "website": text_value(row, "公司網址", "網址", "Website") or previous.get("website"),
                "business_scope": text_value(row, "主要經營業務", "所營事業資料", "BusinessScope") or previous.get("business_scope"),
                "accounting_firm": text_value(row, "簽證會計師事務所名稱", "會計師事務所", "AccountingFirm") or previous.get("accounting_firm"),
                "employee_count": number(row_value(row, ("員工人數", "EmployeeCount"))) if number(row_value(row, ("員工人數", "EmployeeCount"))) is not None else previous.get("employee_count"),
                "issued_shares": issued_shares if issued_shares is not None else previous.get("issued_shares"),
                "paid_in_capital": paid_in_capital if paid_in_capital is not None else previous.get("paid_in_capital"),
                "currency": "TWD",
                "master_updated_at": NOW.isoformat(timespec="seconds"),
            }

    # Daily valuation.
    valuations: dict[str, dict[str, Any]] = {}
    for name, url, exchange in VALUATION_SOURCES:
        for row in fetch_rows(name, url, health):
            symbol = symbol_of(row)
            if not symbol:
                continue
            pe_raw = row_value(row, ("本益比", "PEratio", "PriceEarningRatio", "P/E"))
            pb_raw = row_value(row, ("股價淨值比", "PBratio", "PriceBookRatio", "P/B"))
            yield_raw = row_value(row, ("殖利率(%)", "殖利率", "DividendYield", "Yield"))
            valuations[symbol] = {
                "pe": number(pe_raw),
                "pb": number(pb_raw),
                "dividend_yield": number(yield_raw),
                "pe_status": status_for_raw(pe_raw),
                "pb_status": status_for_raw(pb_raw),
                "dividend_yield_status": status_for_raw(yield_raw),
                "source": name,
                "source_updated_at": NOW.isoformat(timespec="seconds"),
                "exchange": exchange,
            }

    # EPS ranking fallback.
    eps_values: dict[str, float] = {}
    for name, url, _exchange in EPS_SOURCES:
        for row in fetch_rows(name, url, health):
            symbol = symbol_of(row)
            eps = pick(row, "基本每股盈餘（元）", "基本每股盈餘", "每股盈餘", "EPS", "BasicEarningsPerShare")
            if symbol and eps is not None:
                eps_values[symbol] = eps


    # Monthly revenue history.
    revenue_updates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source_name, url, _exchange in MONTHLY_REVENUE_SOURCES:
        for row in fetch_rows(source_name, url, health):
            symbol = symbol_of(row)
            if not symbol:
                continue
            year, month = year_month_of(row)
            if not year or not month or not 1 <= month <= 12:
                continue
            revenue_updates[symbol].append({
                "period": f"{year:04d}-{month:02d}",
                "revenue": pick(row, "當月營收", "當月營業收入淨額", "本月營業收入淨額", "CurrentMonthRevenue", "Revenue"),
                "mom": pick(row, "上月比較增減(%)", "上月比較增減％", "月增率", "MoM"),
                "yoy": pick(row, "去年同月增減(%)", "去年同月增減％", "年增率", "YoY"),
                "cumulative_revenue": pick(row, "當月累計營收", "累計營業收入淨額", "累計營收", "CumulativeRevenue"),
                "cumulative_yoy": pick(row, "前期比較增減(%)", "累計年增率", "CumulativeYoY"),
                "source": source_name,
                "source_updated_at": NOW.isoformat(timespec="seconds"),
            })

    # Cash / stock dividend history.
    dividend_updates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source_name, url, _exchange in DIVIDEND_SOURCES:
        for row in fetch_rows(source_name, url, health):
            symbol = symbol_of(row)
            if not symbol:
                continue
            year_raw = row_value(row, ("股利所屬期間", "股利年度", "年度", "Year"))
            period = str(year_raw or format_date(row_value(row, ("除權息交易日", "資料日期", "Date"))) or "").strip()
            dividend_updates[symbol].append({
                "period": period,
                "cash": pick(row, "盈餘分配之現金股利(元/股)", "現金股利", "每股現金股利", "CashDividend"),
                "stock": pick(row, "盈餘轉增資配股(元/股)", "股票股利", "每股股票股利", "StockDividend"),
                "ex_date": format_date(row_value(row, ("除權息交易日", "除息日", "除權日", "ExDate"))),
                "payment_date": format_date(row_value(row, ("現金股利發放日", "發放日", "PaymentDate"))),
                "record_date": format_date(row_value(row, ("除權息基準日", "基準日", "RecordDate"))),
                "source": source_name,
                "url": text_value(row, "網址", "公告網址", "URL") or None,
                "source_updated_at": NOW.isoformat(timespec="seconds"),
            })

    # Financial statements are fetched concurrently so the complete official
    # refresh remains inside the GitHub Actions time budget.  Duplicate L/X
    # candidates are harmless because quarterly rows are merged by period.
    financial_updates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    jobs: list[tuple[str, str, str]] = []
    for exchange in ("TWSE", "TPEx"):
        for statement in ("income", "balance"):
            for suffix in SECTOR_SUFFIXES:
                for source_name, url in financial_endpoint(exchange, statement, suffix):
                    jobs.append((source_name, url, statement))
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_rows, source_name, url, health, 20): (source_name, statement) for source_name, url, statement in jobs}
        for future in as_completed(futures):
            source_name, statement = futures[future]
            for row in future.result():
                parsed = financial_row(row, statement, source_name)
                if not parsed:
                    continue
                symbol, values = parsed
                financial_updates[symbol].append(values)

    for key, asset in list(assets.items()):
        if asset.get("market") != "TW":
            continue
        symbol = str(asset.get("symbol") or "")
        if dividend_updates.get(symbol):
            asset["dividends"] = merge_period_rows(asset.get("dividends") or [], dividend_updates[symbol], "period", 24)
            asset["dividend_updated_at"] = NOW.isoformat(timespec="seconds")
        if asset.get("asset_class") == "etf":
            # ETFs do not use company EPS/ROE/debt metrics. Preserve disclosed
            # fund data and hide company-only sections on the front end.
            asset.pop("financials", None)
            asset.pop("metrics", None)
            asset.pop("metric_status", None)
            asset.pop("metric_sources", None)
            fund = dict(asset.get("etf") or {})
            if asset.get("dividends") and not fund.get("distributions"):
                fund["distributions"] = asset.get("dividends")
            asset["etf"] = fund
            assets[key] = asset
            continue
        if asset.get("asset_class") != "stock":
            continue
        if financial_updates.get(symbol):
            asset["financials"] = merge_financial(asset.get("financials") or [], financial_updates[symbol])
            asset["financial_updated_at"] = NOW.isoformat(timespec="seconds")
        else:
            asset.setdefault("financials", [])
        if revenue_updates.get(symbol):
            asset["monthly_revenue"] = merge_period_rows(asset.get("monthly_revenue") or [], revenue_updates[symbol], "period", 24)
            asset["revenue_updated_at"] = NOW.isoformat(timespec="seconds")
        apply_metrics(asset, valuations.get(symbol), eps_values.get(symbol))
        assets[key] = asset

    rows = sorted(assets.values(), key=lambda row: (str(row.get("market") or ""), str(row.get("symbol") or "")))
    stock_count = sum(row.get("market") == "TW" and row.get("asset_class") == "stock" for row in rows)
    etf_count = sum(row.get("market") == "TW" and row.get("asset_class") == "etf" for row in rows)
    metrics_count = sum(row.get("market") == "TW" and row.get("asset_class") == "stock" and any(value is not None for value in (row.get("metrics") or {}).values()) for row in rows)
    financial_count = sum(row.get("market") == "TW" and row.get("asset_class") == "stock" and bool(row.get("financials")) for row in rows)
    revenue_count = sum(row.get("market") == "TW" and row.get("asset_class") == "stock" and bool(row.get("monthly_revenue")) for row in rows)
    success_sources = sum(row.get("status") == "ok" for row in health)
    warning_sources = sum(row.get("status") != "ok" for row in health)

    if stock_count < 1000 and sum(row.get("market") == "TW" and row.get("asset_class") == "stock" for row in old.get("assets", [])) >= 1000:
        raise SystemExit(f"Official master returned only {stock_count} stocks; previous archive was not replaced.")

    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "stock_count": stock_count,
            "etf_count": etf_count,
            "stock_with_metrics": metrics_count,
            "stock_with_financials": financial_count,
            "stock_with_monthly_revenue": revenue_count,
            "source_success_count": success_sources,
            "source_warning_count": warning_sources,
            "note": "Separate official stock and ETF masters; company profile, valuation, financial statements, monthly revenue, dividends and fund disclosures are preserved independently.",
        },
        "sources": health,
        "assets": rows,
    }
    write_payload("assets.json", "__ASSET_SEED__", payload)
    (DATA / "asset-update-status.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "version": VERSION,
                    "updated_at": NOW.isoformat(timespec="seconds"),
                    "status": "ok" if success_sources else "warning",
                    "successful_sources": success_sources,
                    "warning_sources": warning_sources,
                    "stock_count": stock_count,
                    "etf_count": etf_count,
                    "stock_with_metrics": metrics_count,
                    "stock_with_financials": financial_count,
                    "stock_with_monthly_revenue": revenue_count,
                    "message": "Official stock and ETF detail refresh completed; warning sources retained their last successful values.",
                },
                "sources": health,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
