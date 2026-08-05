#!/usr/bin/env python3
"""Progressively collect Yahoo Taiwan / Yahoo Finance detail references.

Official TWSE/TPEx/MOPS values remain primary. Yahoo fills missing profile,
financial, ownership and ETF fields. Calculated metrics retain formula/status
metadata and are never presented as official values.
"""
from __future__ import annotations

import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.19"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6",
}
BATCH = 30
PRIORITY_SYMBOLS = ["00981A", "00403A", "00631L", "006208", "0050", "0056", "00878", "00919", "2330", "2317", "2454"]
TIMEOUT = 22
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def raw(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("raw", "fmt", "longFmt"):
            if key in value:
                return value[key]
    return value


def num(value: Any) -> float | None:
    value = raw(value)
    try:
        if value is None or str(value).strip() in {"", "-", "--", "N/A", "None"}:
            return None
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def text(value: Any) -> str | None:
    value = raw(value)
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def ticker(asset: dict[str, Any]) -> str:
    suffix = "TWO" if str(asset.get("exchange") or "").upper() == "TPEX" else "TW"
    return f"{asset.get('symbol')}.{suffix}"


def get_json(url: str) -> dict[str, Any]:
    response = SESSION.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()


def quote_summary(ticker_value: str, is_etf: bool) -> dict[str, Any]:
    modules = [
        "price", "summaryDetail", "defaultKeyStatistics", "financialData",
        "assetProfile", "calendarEvents", "majorHoldersBreakdown",
        "institutionOwnership", "insiderHolders",
    ]
    if is_etf:
        modules += ["fundProfile", "topHoldings"]
    url = (
        "https://query2.finance.yahoo.com/v10/finance/quoteSummary/"
        f"{ticker_value}?modules={','.join(modules)}&formatted=false&lang=zh-Hant-TW&region=TW"
    )
    payload = get_json(url)
    return (((payload.get("quoteSummary") or {}).get("result") or [{}])[0]) or {}


def timeseries(ticker_value: str) -> dict[str, list[dict[str, Any]]]:
    end = int(datetime.now(timezone.utc).timestamp())
    start = int((datetime.now(timezone.utc) - timedelta(days=365 * 7)).timestamp())
    types = [
        "quarterlyTotalRevenue", "quarterlyGrossProfit", "quarterlyOperatingIncome",
        "quarterlyPretaxIncome", "quarterlyNetIncome", "quarterlyNetIncomeCommonStockholders",
        "quarterlyDilutedEPS", "quarterlyBasicEPS", "quarterlyBasicAverageShares",
        "quarterlyDilutedAverageShares", "quarterlyTotalAssets",
        "quarterlyTotalLiabilitiesNetMinorityInterest", "quarterlyStockholdersEquity",
        "quarterlyCurrentAssets", "quarterlyCurrentLiabilities", "quarterlyInventory",
        "quarterlyAccountsReceivable", "quarterlyCashCashEquivalentsAndShortTermInvestments",
        "quarterlyOperatingCashFlow", "quarterlyCapitalExpenditure", "quarterlyFreeCashFlow",
    ]
    url = (
        "https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/"
        f"{ticker_value}?symbol={ticker_value}&type={','.join(types)}&period1={start}&period2={end}"
        "&lang=zh-Hant-TW&region=TW"
    )
    try:
        payload = get_json(url)
    except Exception:
        return {}
    output: dict[str, list[dict[str, Any]]] = {}
    for block in ((payload.get("timeseries") or {}).get("result") or []):
        meta = block.get("meta") or {}
        type_name = (meta.get("type") or [None])[0]
        if type_name:
            output[type_name] = block.get(type_name) or []
    return output


ALIASES = {
    "quarterlyTotalRevenue": "revenue",
    "quarterlyGrossProfit": "gross_profit",
    "quarterlyOperatingIncome": "operating_income",
    "quarterlyPretaxIncome": "pretax_income",
    "quarterlyNetIncome": "net_income",
    "quarterlyNetIncomeCommonStockholders": "net_income_common",
    "quarterlyDilutedEPS": "diluted_eps",
    "quarterlyBasicEPS": "basic_eps",
    "quarterlyBasicAverageShares": "basic_average_shares",
    "quarterlyDilutedAverageShares": "diluted_average_shares",
    "quarterlyTotalAssets": "total_assets",
    "quarterlyTotalLiabilitiesNetMinorityInterest": "total_liabilities",
    "quarterlyStockholdersEquity": "total_equity",
    "quarterlyCurrentAssets": "current_assets",
    "quarterlyCurrentLiabilities": "current_liabilities",
    "quarterlyInventory": "inventory",
    "quarterlyAccountsReceivable": "accounts_receivable",
    "quarterlyCashCashEquivalentsAndShortTermInvestments": "cash",
    "quarterlyOperatingCashFlow": "operating_cash_flow",
    "quarterlyCapitalExpenditure": "capital_expenditure",
    "quarterlyFreeCashFlow": "free_cash_flow",
}


def ratio(numerator: Any, denominator: Any) -> float | None:
    n, d = num(numerator), num(denominator)
    if n is None or d in (None, 0):
        return None
    return n / d * 100


def period_from_date(value: str) -> str:
    try:
        year, month = map(int, value[:7].split("-"))
        return f"{year}Q{(month - 1) // 3 + 1}"
    except Exception:
        return value


def financial_rows(series: dict[str, list[dict[str, Any]]], fallback_shares: float | None = None) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for type_name, field in ALIASES.items():
        for item in series.get(type_name, []):
            date_value = item.get("asOfDate") or item.get("date")
            if not date_value:
                continue
            reported = num(item.get("reportedValue"))
            if reported is None:
                continue
            date_key = str(date_value)
            rows.setdefault(date_key, {
                "date": date_key,
                "period": period_from_date(date_key),
                "source": "Yahoo Finance fundamentals",
                "calculation_notes": [],
            })[field] = reported
    ascending = sorted(rows.values(), key=lambda row: row["date"])
    for index, row in enumerate(ascending):
        row["gross_margin"] = ratio(row.get("gross_profit"), row.get("revenue"))
        row["operating_margin"] = ratio(row.get("operating_income"), row.get("revenue"))
        row["net_margin"] = ratio(row.get("net_income_common") or row.get("net_income"), row.get("revenue"))
        row["debt_ratio"] = ratio(row.get("total_liabilities"), row.get("total_assets"))
        row["current_ratio"] = ratio(row.get("current_assets"), row.get("current_liabilities"))
        if row.get("free_cash_flow") is None and row.get("operating_cash_flow") is not None and row.get("capital_expenditure") is not None:
            capex = float(row["capital_expenditure"])
            row["free_cash_flow"] = float(row["operating_cash_flow"]) + capex if capex < 0 else float(row["operating_cash_flow"]) - capex
            row["calculation_notes"].append("自由現金流＝營業現金流－資本支出")
        official_eps = row.get("diluted_eps") if row.get("diluted_eps") is not None else row.get("basic_eps")
        if official_eps is not None:
            row["eps"] = official_eps
            row["eps_status"] = "reference_reported"
        else:
            income = row.get("net_income_common") if row.get("net_income_common") is not None else row.get("net_income")
            shares = row.get("diluted_average_shares") or row.get("basic_average_shares")
            if income is not None and shares not in (None, 0):
                row["eps"] = float(income) / float(shares)
                row["eps_status"] = "calculated"
                row["calculation_notes"].append("EPS＝歸屬普通股股東損益÷加權平均流通股數")
            elif income is not None and fallback_shares not in (None, 0):
                row["eps"] = float(income) / float(fallback_shares)
                row["eps_status"] = "estimated"
                row["calculation_notes"].append("估算EPS＝淨利÷期末流通股數；非官方精確EPS")
        previous = ascending[index - 1] if index else None
        current_equity, current_assets = row.get("total_equity"), row.get("total_assets")
        average_equity = None
        average_assets = None
        if previous and previous.get("total_equity") is not None and current_equity is not None:
            average_equity = (float(previous["total_equity"]) + float(current_equity)) / 2
        elif current_equity is not None:
            average_equity = float(current_equity)
        if previous and previous.get("total_assets") is not None and current_assets is not None:
            average_assets = (float(previous["total_assets"]) + float(current_assets)) / 2
        elif current_assets is not None:
            average_assets = float(current_assets)
        income = row.get("net_income_common") if row.get("net_income_common") is not None else row.get("net_income")
        if income is not None and average_equity not in (None, 0):
            row["roe"] = float(income) / average_equity * 4 * 100
            row["calculation_notes"].append("單季ROE年化＝單季淨利×4÷平均股東權益")
        if income is not None and average_assets not in (None, 0):
            row["roa"] = float(income) / average_assets * 4 * 100
            row["calculation_notes"].append("單季ROA年化＝單季淨利×4÷平均總資產")
    return list(reversed(ascending[-20:]))


def trailing_metrics(financials: list[dict[str, Any]]) -> dict[str, Any]:
    chronological = list(reversed(financials[:4]))
    if not chronological:
        return {}
    sums = {}
    for key in ("revenue", "gross_profit", "operating_income", "net_income", "net_income_common", "operating_cash_flow", "free_cash_flow"):
        values = [num(row.get(key)) for row in chronological]
        values = [value for value in values if value is not None]
        if values:
            sums[key] = sum(values)
    first, last = chronological[0], chronological[-1]
    avg_equity = None
    avg_assets = None
    if num(first.get("total_equity")) is not None and num(last.get("total_equity")) is not None:
        avg_equity = (float(first["total_equity"]) + float(last["total_equity"])) / 2
    if num(first.get("total_assets")) is not None and num(last.get("total_assets")) is not None:
        avg_assets = (float(first["total_assets"]) + float(last["total_assets"])) / 2
    income = sums.get("net_income_common", sums.get("net_income"))
    result = {
        "gross_margin": ratio(sums.get("gross_profit"), sums.get("revenue")),
        "operating_margin": ratio(sums.get("operating_income"), sums.get("revenue")),
        "net_margin": ratio(income, sums.get("revenue")),
        "roe": ratio(income, avg_equity),
        "roa": ratio(income, avg_assets),
        "free_cash_flow": sums.get("free_cash_flow"),
        "operating_cash_flow": sums.get("operating_cash_flow"),
    }
    latest = financials[0]
    result["debt_ratio"] = latest.get("debt_ratio")
    result["current_ratio"] = latest.get("current_ratio")
    result["eps"] = sum(value for value in (num(row.get("eps")) for row in financials[:4]) if value is not None) if any(num(row.get("eps")) is not None for row in financials[:4]) else None
    return {key: value for key, value in result.items() if value is not None}


def chart_reference(ticker_value: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker_value}?range=20y&interval=1d&events=div%2Csplits&lang=zh-Hant-TW&region=TW"
    try:
        payload = get_json(url)
        result = (((payload.get("chart") or {}).get("result") or [{}])[0]) or {}
    except Exception:
        return [], {}
    meta = result.get("meta") or {}
    events = ((result.get("events") or {}).get("dividends") or {})
    output = []
    for item in events.values():
        timestamp = item.get("date")
        amount = num(item.get("amount"))
        if timestamp and amount is not None:
            date_value = datetime.fromtimestamp(int(timestamp), timezone.utc).date().isoformat()
            output.append({
                "date": date_value,
                "ex_date": date_value,
                "period": date_value[:4],
                "year": date_value[:4],
                "cash": amount,
                "cash_dividend": amount,
                "source": "Yahoo Finance dividend event",
                "url": f"https://tw.stock.yahoo.com/quote/{ticker_value}/dividend",
            })
    return sorted(output, key=lambda row: row["date"], reverse=True), meta


def parse_one(asset: dict[str, Any]) -> tuple[str, dict[str, Any] | None, str | None]:
    symbol = str(asset.get("symbol") or "").upper()
    ticker_value = ticker(asset)
    is_etf = asset.get("asset_class") == "etf"
    try:
        source_errors = []
        try:
            summary_payload = quote_summary(ticker_value, is_etf)
        except Exception as exc:
            summary_payload = {}
            source_errors.append(f"quoteSummary: {exc}")
        time.sleep(random.uniform(0.12, 0.35))
        price = summary_payload.get("price") or {}
        profile = summary_payload.get("assetProfile") or {}
        summary = summary_payload.get("summaryDetail") or {}
        stats = summary_payload.get("defaultKeyStatistics") or {}
        financial = summary_payload.get("financialData") or {}
        calendar = summary_payload.get("calendarEvents") or {}
        holders = summary_payload.get("majorHoldersBreakdown") or {}
        fund = summary_payload.get("fundProfile") or {}
        top = summary_payload.get("topHoldings") or {}
        fallback_shares = num(stats.get("sharesOutstanding"))
        series = {} if is_etf else timeseries(ticker_value)
        time.sleep(random.uniform(0.12, 0.35))
        financials = financial_rows(series, fallback_shares)
        trailing = trailing_metrics(financials)
        dividends, chart_meta = chart_reference(ticker_value)
        if not price:
            price = {
                "longName": chart_meta.get("longName"),
                "shortName": chart_meta.get("shortName"),
                "currency": chart_meta.get("currency"),
                "quoteType": chart_meta.get("instrumentType"),
            }
        if not summary_payload and not financials and not dividends:
            raise ValueError("; ".join(source_errors) or "all Yahoo references empty")
        officers = profile.get("companyOfficers") or []
        def officer(keyword: str) -> str | None:
            return next((text(row.get("name")) for row in officers if keyword.lower() in str(row.get("title") or "").lower()), None)
        metrics = {
            "pe": num(summary.get("trailingPE")) or num(stats.get("trailingPE")),
            "forward_pe": num(summary.get("forwardPE")),
            "pb": num(stats.get("priceToBook")),
            "dividend_yield": num(summary.get("dividendYield")),
            "eps": num(stats.get("trailingEps")) or num(financial.get("epsTrailingTwelveMonths")) or trailing.get("eps"),
            "book_value": num(stats.get("bookValue")),
            "market_cap": num(price.get("marketCap")),
            "roe": num(financial.get("returnOnEquity")) or trailing.get("roe"),
            "roa": num(financial.get("returnOnAssets")) or trailing.get("roa"),
            "gross_margin": num(financial.get("grossMargins")) or trailing.get("gross_margin"),
            "operating_margin": num(financial.get("operatingMargins")) or trailing.get("operating_margin"),
            "net_margin": num(financial.get("profitMargins")) or trailing.get("net_margin"),
            "debt_to_equity": num(financial.get("debtToEquity")),
            "debt_ratio": trailing.get("debt_ratio"),
            "current_ratio": num(financial.get("currentRatio")) or trailing.get("current_ratio"),
            "free_cash_flow": num(financial.get("freeCashflow")) or trailing.get("free_cash_flow"),
            "operating_cash_flow": num(financial.get("operatingCashflow")) or trailing.get("operating_cash_flow"),
            "shares_outstanding": fallback_shares,
        }
        for key in ("roe", "roa", "gross_margin", "operating_margin", "net_margin", "dividend_yield"):
            if metrics.get(key) is not None and abs(float(metrics[key])) <= 1:
                metrics[key] = float(metrics[key]) * 100
        if metrics.get("current_ratio") is not None and abs(float(metrics["current_ratio"])) < 20:
            metrics["current_ratio"] = float(metrics["current_ratio"]) * 100
        metrics = {key: value for key, value in metrics.items() if value is not None}
        metrics_meta = {}
        for key in metrics:
            if key in {"roe", "roa", "gross_margin", "operating_margin", "net_margin", "debt_ratio", "current_ratio", "free_cash_flow", "operating_cash_flow"} and key in trailing:
                metrics_meta[key] = {"status": "calculated", "source": "Yahoo 財報欄位計算", "period": "近四季／最新季", "formula": key}
            else:
                metrics_meta[key] = {"status": "reference", "source": "Yahoo Finance"}
        if financials and financials[0].get("eps_status") == "estimated" and metrics.get("eps") == financials[0].get("eps"):
            metrics_meta["eps"] = {"status": "estimated", "source": "Yahoo 財報欄位計算", "formula": "淨利÷期末流通股數"}
        profile_out = {
            "company_name": text(price.get("longName")) or text(price.get("shortName")),
            "industry": text(profile.get("industry")),
            "sector": text(profile.get("sector")),
            "website": text(profile.get("website")),
            "address": " ".join(filter(None, [text(profile.get("address1")), text(profile.get("city")), text(profile.get("country"))])),
            "phone": text(profile.get("phone")),
            "business_summary": text(profile.get("longBusinessSummary")),
            "employees": num(profile.get("fullTimeEmployees")),
            "chairperson": officer("chair"),
            "general_manager": officer("chief executive") or officer("general manager"),
            "market_cap": num(price.get("marketCap")),
            "currency": text(price.get("currency")),
            "quote_type": text(price.get("quoteType")),
        }
        etf_out = {}
        if is_etf:
            fees = fund.get("feesExpensesInvestment") or {}
            holdings = []
            for holding in top.get("holdings") or []:
                holding_symbol = text(holding.get("symbol"))
                name = text(holding.get("holdingName"))
                weight = num(holding.get("holdingPercent"))
                if holding_symbol or name:
                    holdings.append({
                        "symbol": holding_symbol,
                        "name": name,
                        "weight": weight * 100 if weight is not None and abs(weight) <= 1 else weight,
                        "source": "Yahoo Finance top holdings",
                    })
            sectors = []
            for sector_row in top.get("sectorWeightings") or []:
                if isinstance(sector_row, dict):
                    for key, value in sector_row.items():
                        weight = num(value)
                        sectors.append({"name": key, "weight": weight * 100 if weight is not None and abs(weight) <= 1 else weight})
            etf_out = {
                "category": text(fund.get("categoryName")),
                "family": text(fund.get("family")),
                "issuer": text(fund.get("family")),
                "legal_type": text(fund.get("legalType")),
                "management_fee": num(fees.get("annualReportExpenseRatio")),
                "holdings": holdings[:20],
                "allocations": sectors,
                "source": "Yahoo Finance fund profile",
            }
        row = {
            "symbol": symbol,
            "ticker": ticker_value,
            "asset_class": "etf" if is_etf else "stock",
            "source": "Yahoo 股市 / Yahoo Finance",
            "source_status": "partial" if source_errors else "ok",
            "source_errors": source_errors,
            "source_url": f"https://tw.stock.yahoo.com/quote/{ticker_value}",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "profile": {key: value for key, value in profile_out.items() if value not in (None, "")},
            "metrics": metrics,
            "metrics_meta": metrics_meta,
            "financials": financials,
            "dividends": dividends,
            "calendar": {
                "earnings_date": text(((calendar.get("earnings") or {}).get("earningsDate") or [None])[0]),
                "ex_dividend_date": text(calendar.get("exDividendDate")),
                "dividend_date": text(calendar.get("dividendDate")),
            },
            "holders": {key: num(value) for key, value in holders.items() if num(value) is not None},
            "etf": {key: value for key, value in etf_out.items() if value not in (None, "", [])},
        }
        return symbol, row, None
    except Exception as exc:
        return symbol, None, str(exc)


def main() -> None:
    assets = read_json(DATA / "assets.json", {"assets": []}).get("assets", [])
    old = read_json(DATA / "yahoo-details.json", {"items": {}, "state": {}})
    items = dict(old.get("items") or {})
    state = dict(old.get("state") or {})
    candidates = [
        asset for asset in assets
        if asset.get("market") == "TW" and asset.get("asset_class") in {"stock", "etf"} and asset.get("symbol")
    ]
    priority = {symbol: index for index, symbol in enumerate(PRIORITY_SYMBOLS)}
    candidates.sort(key=lambda asset: (priority.get(str(asset.get("symbol")).upper(), 9999), asset.get("asset_class") != "stock", str(asset.get("symbol"))))
    cursor = int(state.get("cursor") or 0)
    cursor = cursor if cursor < len(candidates) else 0
    rolling = candidates[cursor:cursor + BATCH]
    if len(rolling) < BATCH:
        rolling += candidates[:BATCH - len(rolling)]
    missing_priority = [asset for asset in candidates if str(asset.get("symbol")).upper() in priority and str(asset.get("symbol")).upper() not in items]
    batch, seen = [], set()
    for asset in missing_priority + rolling:
        symbol = str(asset.get("symbol")).upper()
        if symbol in seen:
            continue
        batch.append(asset); seen.add(symbol)
        if len(batch) >= BATCH:
            break
    success = 0
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(parse_one, asset) for asset in batch]
        for future in as_completed(futures):
            symbol, row, error = future.result()
            if row:
                items[symbol] = row
                success += 1
            elif error:
                errors.append({"symbol": symbol, "error": error[:300]})
    next_cursor = (cursor + len(batch)) % len(candidates) if candidates else 0
    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": "ok" if success == len(batch) and success else "partial" if success or items else "warning",
            "item_count": len(items),
            "batch_size": len(batch),
            "batch_success": success,
            "note": "Official values remain primary. Yahoo data fills missing fields; calculated and estimated values retain formula labels.",
        },
        "state": {"cursor": next_cursor, "last_batch_at": NOW.isoformat(timespec="seconds")},
        "errors": errors[:100],
        "items": items,
    }
    write_payload("yahoo-details.json", "__YAHOO_DETAILS_SEED__", payload)
    print(payload["metadata"])


if __name__ == "__main__":
    main()
