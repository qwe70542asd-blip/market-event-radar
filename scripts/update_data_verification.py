#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.25"


def num(value: Any) -> float | None:
    try:
        if value is None or str(value).strip() in {"", "-", "—"}:
            return None
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def close(a: Any, b: Any, tolerance: float = .005) -> bool:
    left, right = num(a), num(b)
    if left is None or right is None:
        return False
    return abs(left - right) <= max(abs(left), abs(right), 1) * tolerance


def normalize_rows(value: Any) -> list[dict]:
    """Accept channel payloads stored either as a list or as {rows:[...]}.

    Older branches used both shapes. Validation must never crash merely because a
    retained last-known-good file uses the other representation.
    """
    if isinstance(value, dict):
        value = value.get("rows") or value.get("items") or []
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def latest(rows: Any, key: str = "period") -> dict:
    normalized = normalize_rows(rows)
    return sorted((row for row in normalized if row.get(key)), key=lambda row: str(row.get(key)), reverse=True)[0] if normalized else {}


def status_for(official: Any, reference: Any, tolerance: float = .005, reference_status: str = "reference") -> tuple[str, list[Any]]:
    official_number, reference_number = num(official), num(reference)
    if official_number is not None:
        if reference_number is not None and close(official_number, reference_number, tolerance):
            return "multi_source", [official_number, reference_number]
        if reference_number is not None and not close(official_number, reference_number, tolerance * 6):
            return "conflict", [official_number, reference_number]
        return "official", [official_number]
    if reference_number is not None:
        return reference_status, [reference_number]
    return "missing", []


def main() -> None:
    assets = read_json(DATA / "assets.json", {"assets": []}).get("assets", [])
    market = read_json(DATA / "tw-market.json", {"items": []}).get("items", [])
    revenue = read_json(DATA / "monthly-revenue.json", {"items": {}}).get("items", {})
    dividends = read_json(DATA / "dividend-history.json", {"items": {}}).get("items", {})
    secondary = read_json(DATA / "secondary-reference.json", {"items": {}}).get("items", {})
    yahoo = read_json(DATA / "yahoo-details.json", {"items": {}}).get("items", {})
    etf_details = read_json(DATA / "etf-details.json", {"items": {}}).get("items", {})
    quotes = {str(row.get("symbol") or "").upper(): row for row in market}
    output = {}
    counts = {"official": 0, "multi_source": 0, "reference": 0, "calculated": 0, "estimated": 0, "conflict": 0, "missing": 0, "expired": 0}
    for asset in assets:
        symbol = str(asset.get("symbol") or "").upper()
        if not symbol or asset.get("market") != "TW":
            continue
        fields = {}
        official_quote = quotes.get(symbol) or {}
        secondary_quote = secondary.get(symbol) or {}
        quote_status, quote_values = status_for(official_quote.get("price"), secondary_quote.get("price"), .01)
        fields["quote"] = {
            "status": quote_status,
            "sources": [source for source, value in [("TWSE／TPEx official close", official_quote.get("price")), ("Yahoo Finance chart", secondary_quote.get("price"))] if num(value) is not None],
            "values": quote_values,
        }
        embedded_revenue = latest(asset.get("monthly_revenue") or [])
        channel_revenue = latest(revenue.get(symbol) or [])
        rev_status, rev_values = status_for(embedded_revenue.get("revenue"), channel_revenue.get("revenue"), .001)
        fields["monthly_revenue"] = {
            "status": rev_status,
            "sources": [source for source in [embedded_revenue.get("source"), channel_revenue.get("source")] if source],
            "period": channel_revenue.get("period") or embedded_revenue.get("period"),
            "values": rev_values,
        }
        embedded_dividend = latest(asset.get("dividends") or [])
        channel_dividend = latest(dividends.get(symbol) or [])
        div_status, div_values = status_for(embedded_dividend.get("cash"), channel_dividend.get("cash"), .001)
        fields["dividends"] = {
            "status": div_status,
            "sources": [source for source in [embedded_dividend.get("source"), channel_dividend.get("source")] if source],
            "period": channel_dividend.get("period") or embedded_dividend.get("period"),
            "values": div_values,
        }
        official_metrics = asset.get("metrics") or {}
        yahoo_row = yahoo.get(symbol) or {}
        reference_metrics = yahoo_row.get("metrics") or {}
        metric_meta = yahoo_row.get("metrics_meta") or {}
        metric_fields = {}
        for key in sorted(set(official_metrics) | set(reference_metrics)):
            status, values = status_for(official_metrics.get(key), reference_metrics.get(key), .01, metric_meta.get(key, {}).get("status") or "reference")
            metric_fields[key] = {
                "status": status,
                "values": values,
                "sources": [source for source, value in [(asset.get("metric_sources", {}).get(key) or "official financial data", official_metrics.get(key)), (metric_meta.get(key, {}).get("source") or "Yahoo Finance", reference_metrics.get(key))] if num(value) is not None],
                "formula": metric_meta.get(key, {}).get("formula"),
            }
        available_statuses = [row["status"] for row in metric_fields.values()]
        metric_overall = "conflict" if "conflict" in available_statuses else "multi_source" if "multi_source" in available_statuses else "official" if "official" in available_statuses else "calculated" if "calculated" in available_statuses else "estimated" if "estimated" in available_statuses else "reference" if "reference" in available_statuses else "missing"
        fields["metrics"] = {"status": metric_overall, "fields": metric_fields, "available": list(metric_fields)}
        if asset.get("asset_class") == "etf":
            official_etf = asset.get("etf") or {}
            reference_etf = etf_details.get(symbol) or {}
            checks = {}
            for key in ("issuer", "manager", "benchmark", "aum", "beneficiary_count", "nav", "premium_discount", "holdings", "allocations", "distributions"):
                official_value, reference_value = official_etf.get(key), reference_etf.get(key)
                if isinstance(official_value, (list, dict)) or isinstance(reference_value, (list, dict)):
                    if official_value:
                        status = "official"
                    elif reference_value:
                        status = reference_etf.get("verification", {}).get(key, {}).get("status", "reference")
                    else:
                        status = "missing"
                    values = [len(value) if isinstance(value, list) else bool(value) for value in (official_value, reference_value) if value]
                else:
                    status, values = status_for(official_value, reference_value, .02, reference_etf.get("verification", {}).get(key, {}).get("status", "reference"))
                checks[key] = {"status": status, "values": values, "source": reference_etf.get("field_sources", {}).get(key)}
            statuses = [row["status"] for row in checks.values()]
            fields["etf"] = {
                "status": "conflict" if "conflict" in statuses else "official" if "official" in statuses else "multi_source" if "multi_source" in statuses else "reference" if "reference" in statuses else "missing",
                "fields": checks,
            }
        statuses = [field["status"] for field in fields.values()]
        overall = "conflict" if "conflict" in statuses else "multi_source" if "multi_source" in statuses else "official" if "official" in statuses else "calculated" if "calculated" in statuses else "estimated" if "estimated" in statuses else "reference" if "reference" in statuses else "missing"
        counts[overall] = counts.get(overall, 0) + 1
        suffix = "TWO" if str(asset.get("exchange") or "").upper() == "TPEX" else "TW"
        output[symbol] = {
            "symbol": symbol,
            "overall": overall,
            "fields": fields,
            "reference_links": {
                "yahoo": f"https://tw.stock.yahoo.com/quote/{symbol}.{suffix}",
                "goodinfo": f"https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={symbol}",
                "moneydj_etf": f"https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={symbol}.TW" if asset.get("asset_class") == "etf" else None,
                "histock_etf": "https://histock.tw/stock/active-etf.aspx" if asset.get("asset_class") == "etf" else None,
            },
            "updated_at": NOW.isoformat(timespec="seconds"),
        }
    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": "partial" if counts.get("conflict") or counts.get("missing") else "ok",
            "counts": counts,
            "note": "Official values are primary. Yahoo, MoneyDJ and HiStock fill gaps; formulas and estimates are explicitly labeled.",
        },
        "items": output,
    }
    write_payload("data-verification.json", "__DATA_VERIFICATION_SEED__", payload)
    print(payload["metadata"])


if __name__ == "__main__":
    main()
