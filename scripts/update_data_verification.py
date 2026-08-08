#!/usr/bin/env python3
"""Cross-source trust + completeness verification for Market Event Radar.

v11.4.31 separates two concepts that v11.4.30 mixed together:
1. trust: official / multi-source / reference / conflict;
2. completeness: complete / partial / unresolved, using the full asset audit.

The output also records the exact updated_at/version of every source snapshot so a
verification run can never pretend that an older upstream snapshot was current.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.31"

SOURCE_FILES = {
    "assets": "assets.json",
    "asset_audit": "asset-audit.json",
    "tw_market": "tw-market.json",
    "monthly_revenue": "monthly-revenue.json",
    "dividend_history": "dividend-history.json",
    "secondary_reference": "secondary-reference.json",
    "yahoo_details": "yahoo-details.json",
    "etf_details": "etf-details.json",
}
SOURCE_MAX_AGE_SECONDS = {
    "assets": 18 * 3600,
    "asset_audit": 18 * 3600,
    "tw_market": 90 * 60,
    "monthly_revenue": 8 * 3600,
    "dividend_history": 8 * 3600,
    "secondary_reference": 12 * 3600,
    "yahoo_details": 3 * 3600,
    "etf_details": 6 * 3600,
}


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
    if isinstance(value, dict):
        value = value.get("rows") or value.get("items") or []
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def latest(rows: Any, key: str = "period") -> dict:
    normalized = normalize_rows(rows)
    candidates = [row for row in normalized if row.get(key)]
    return sorted(candidates, key=lambda row: str(row.get(key)), reverse=True)[0] if candidates else {}


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


def parse_stamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=NOW.tzinfo)
        return stamp.astimezone(NOW.tzinfo)
    except (TypeError, ValueError):
        return None


def snapshot_info(payload: dict[str, Any], key: str) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    stamp = parse_stamp(metadata.get("updated_at"))
    age = (NOW - stamp).total_seconds() if stamp else None
    limit = SOURCE_MAX_AGE_SECONDS[key]
    return {
        "file": SOURCE_FILES[key],
        "version": metadata.get("version"),
        "updated_at": metadata.get("updated_at"),
        "status": metadata.get("status"),
        "age_seconds": round(age, 1) if age is not None else None,
        "max_age_seconds": limit,
        "stale": age is None or age < 0 or age > limit,
    }


def main() -> None:
    payloads = {key: read_json(DATA / filename, {}) for key, filename in SOURCE_FILES.items()}
    assets = payloads["assets"].get("assets", [])
    market = payloads["tw_market"].get("items", [])
    revenue = payloads["monthly_revenue"].get("items", {})
    dividends = payloads["dividend_history"].get("items", {})
    secondary = payloads["secondary_reference"].get("items", {})
    yahoo = payloads["yahoo_details"].get("items", {})
    etf_details = payloads["etf_details"].get("items", {})
    audit_rows = payloads["asset_audit"].get("assets", [])
    audit_map = {str(row.get("symbol") or "").upper(): row for row in audit_rows}
    audit_summary = payloads["asset_audit"].get("summary") or {}
    quotes = {str(row.get("symbol") or "").upper(): row for row in market}

    source_snapshots = {key: snapshot_info(payload, key) for key, payload in payloads.items()}
    stale_sources = [key for key, row in source_snapshots.items() if row["stale"]]

    output: dict[str, Any] = {}
    trust_counts = {"official": 0, "multi_source": 0, "reference": 0, "calculated": 0, "estimated": 0, "conflict": 0, "missing": 0}
    completeness_counts = {"complete": 0, "partial": 0, "unresolved": 0}

    for asset in assets:
        symbol = str(asset.get("symbol") or "").upper()
        if not symbol or asset.get("market") != "TW":
            continue
        asset_class = asset.get("asset_class")
        fields: dict[str, Any] = {}
        official_quote = quotes.get(symbol) or {}
        secondary_quote = secondary.get(symbol) or {}
        official_date = str(official_quote.get("quote_date") or payloads["tw_market"].get("metadata", {}).get("trading_date") or "")
        reference_date = str(secondary_quote.get("quote_date") or "")
        sessions_match = bool(official_date and reference_date and official_date == reference_date)
        quote_status, quote_values = status_for(official_quote.get("price"), secondary_quote.get("price") if sessions_match else None, .01)
        fields["quote"] = {
            "status": quote_status,
            "sources": [source for source, value in [("TWSE／TPEx official latest close", official_quote.get("price")), ("Yahoo Finance chart", secondary_quote.get("price") if sessions_match else None)] if num(value) is not None],
            "values": quote_values,
            "official_date": official_date or None,
            "reference_date": reference_date or None,
            "reference_session_match": sessions_match,
        }

        if asset_class == "stock":
            embedded_revenue = latest(asset.get("monthly_revenue") or [])
            channel_revenue = latest(revenue.get(symbol) or [])
            rev_status, rev_values = status_for(embedded_revenue.get("revenue"), channel_revenue.get("revenue"), .001)
            fields["monthly_revenue"] = {
                "status": rev_status,
                "sources": [source for source in [embedded_revenue.get("source"), channel_revenue.get("source")] if source],
                "period": channel_revenue.get("period") or embedded_revenue.get("period"),
                "values": rev_values,
            }
        else:
            fields["monthly_revenue"] = {"status": "not_applicable", "sources": [], "values": []}

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
        if asset_class == "stock":
            for key in sorted(set(official_metrics) | set(reference_metrics)):
                status, values = status_for(official_metrics.get(key), reference_metrics.get(key), .01, metric_meta.get(key, {}).get("status") or "reference")
                metric_fields[key] = {
                    "status": status,
                    "values": values,
                    "sources": [source for source, value in [(asset.get("metric_sources", {}).get(key) or "official financial data", official_metrics.get(key)), (metric_meta.get(key, {}).get("source") or "Yahoo Finance", reference_metrics.get(key))] if num(value) is not None],
                    "formula": metric_meta.get(key, {}).get("formula"),
                }
            metric_statuses = [row["status"] for row in metric_fields.values()]
            metric_overall = "conflict" if "conflict" in metric_statuses else "multi_source" if "multi_source" in metric_statuses else "official" if "official" in metric_statuses else "calculated" if "calculated" in metric_statuses else "estimated" if "estimated" in metric_statuses else "reference" if "reference" in metric_statuses else "missing"
        else:
            metric_overall = "not_applicable"
        fields["metrics"] = {"status": metric_overall, "fields": metric_fields, "available": list(metric_fields)}

        if asset_class == "etf":
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
                "status": "conflict" if "conflict" in statuses else "multi_source" if "multi_source" in statuses else "official" if "official" in statuses else "calculated" if "calculated" in statuses else "reference" if "reference" in statuses else "missing",
                "fields": checks,
            }

        trust_statuses = [field.get("status") for field in fields.values() if field.get("status") != "not_applicable"]
        trust_overall = "conflict" if "conflict" in trust_statuses else "multi_source" if "multi_source" in trust_statuses else "official" if "official" in trust_statuses else "calculated" if "calculated" in trust_statuses else "estimated" if "estimated" in trust_statuses else "reference" if "reference" in trust_statuses else "missing"
        trust_counts[trust_overall] = trust_counts.get(trust_overall, 0) + 1

        audit = audit_map.get(symbol) or {}
        coverage = audit.get("coverage_percent")
        if audit:
            completeness = "unresolved" if float(coverage or 0) <= 0 else str(audit.get("status") or "partial")
        else:
            required = [row for row in fields.values() if row.get("status") != "not_applicable"]
            missing_required = [row for row in required if row.get("status") == "missing"]
            coverage = round((len(required) - len(missing_required)) / len(required) * 100, 2) if required else 0
            completeness = "unresolved" if not required else "complete" if not missing_required else "partial"
        if completeness not in completeness_counts:
            completeness = "partial"
        completeness_counts[completeness] += 1

        suffix = "TWO" if str(asset.get("exchange") or "").upper() == "TPEX" else "TW"
        output[symbol] = {
            "symbol": symbol,
            "overall": trust_overall,  # backwards-compatible trust field
            "trust_overall": trust_overall,
            "completeness_status": completeness,
            "coverage_percent": coverage,
            "missing_fields": audit.get("missing_fields") or [],
            "fields": fields,
            "reference_links": {
                "yahoo": f"https://tw.stock.yahoo.com/quote/{symbol}.{suffix}",
                "goodinfo": f"https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={symbol}",
                "moneydj_etf": f"https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={symbol}.TW" if asset_class == "etf" else None,
                "histock_etf": "https://histock.tw/stock/active-etf.aspx" if asset_class == "etf" else None,
            },
            "verified_against": {key: row.get("updated_at") for key, row in source_snapshots.items()},
            "updated_at": NOW.isoformat(timespec="seconds"),
        }

    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": "partial" if trust_counts.get("conflict") or completeness_counts.get("unresolved") or stale_sources else "ok",
            "counts": trust_counts,
            "trust_counts": trust_counts,
            "completeness_counts": completeness_counts,
            "average_field_coverage_percent": audit_summary.get("average_field_coverage_percent"),
            "source_snapshots": source_snapshots,
            "stale_sources": stale_sources,
            "verification_basis": "exact live-channel snapshot timestamps recorded; trust and field completeness are separate",
            "note": "Official values are primary. Trust status does not imply field completeness; see completeness_counts and coverage_percent.",
        },
        "items": output,
    }
    write_payload("data-verification.json", "__DATA_VERIFICATION_SEED__", payload)
    print(payload["metadata"])


if __name__ == "__main__":
    main()
