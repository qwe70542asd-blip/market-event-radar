#!/usr/bin/env python3
"""Cross-source trust + completeness verification for Market Event Radar.

v11.4.39 rebuilds this verifier around isolated stock / ETF adapters.  Every
asset is evaluated with local immutable source rows, so an optional channel can
never leak an uninitialised variable into another asset class.  The output
schema remains backwards-compatible with v11.4.39.
"""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.39"

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
TRUST_ORDER = ("conflict", "multi_source", "official", "calculated", "estimated", "reference", "missing")


def mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def sequence(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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


def normalize_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = value.get("rows") or value.get("items") or []
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def latest(rows: Any, key: str = "period") -> dict[str, Any]:
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


def clean_text_value(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return None if text in {"", "-", "—"} else text


def normalized_text_value(value: Any) -> str:
    text = clean_text_value(value) or ""
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "", text).lower()


def normalize_benchmark_value(value: Any) -> str | None:
    text = clean_text_value(value)
    if not text:
        return None
    text = re.split(r"\s+(?=投資策略|主題/因子|基金特色|資產規模|受益人次)", text, maxsplit=1)[0].strip()
    return "不適用" if text in {"無", "不適用", "N/A", "NA", "-", "—"} else text


def text_status_for(official: Any, reference: Any, reference_status: str = "reference") -> tuple[str, list[Any]]:
    left, right = clean_text_value(official), clean_text_value(reference)
    if left:
        if right:
            a, b = normalized_text_value(left), normalized_text_value(right)
            equivalent = bool(a and b and (a == b or (min(len(a), len(b)) >= 3 and (a in b or b in a))))
            if equivalent:
                return "multi_source", [left, right]
            if reference_status == "official":
                return "conflict", [left, right]
        return "official", [left]
    if right:
        return reference_status, [right]
    return "missing", []


def row_stamp(row: dict[str, Any], fallback: Any = None, *keys: str) -> Any:
    for key in keys:
        if row.get(key):
            return row.get(key)
    return fallback


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
    metadata = mapping(payload.get("metadata"))
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


def overall_status(fields: dict[str, Any]) -> str:
    statuses = [str(mapping(field).get("status") or "") for field in fields.values() if mapping(field).get("status") != "not_applicable"]
    return next((status for status in TRUST_ORDER if status in statuses), "missing")


def build_quote_field(symbol: str, payloads: dict[str, dict[str, Any]], quotes: dict[str, dict[str, Any]], secondary: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    official_quote = mapping(quotes.get(symbol))
    secondary_quote = mapping(secondary.get(symbol))
    official_date = str(official_quote.get("quote_date") or mapping(payloads["tw_market"].get("metadata")).get("trading_date") or "")
    reference_date = str(secondary_quote.get("quote_date") or "")
    sessions_match = bool(official_date and reference_date and official_date == reference_date)
    reference_price = secondary_quote.get("price") if sessions_match else None
    status, values = status_for(official_quote.get("price"), reference_price, .01)
    field = {
        "status": status,
        "sources": [source for source, value in [
            ("TWSE／TPEx official latest close", official_quote.get("price")),
            ("Yahoo Finance chart", reference_price),
        ] if num(value) is not None],
        "values": values,
        "official_date": official_date or None,
        "reference_date": reference_date or None,
        "reference_session_match": sessions_match,
    }
    return field, official_quote, secondary_quote


def build_revenue_field(asset: dict[str, Any], symbol: str, revenue: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if asset.get("asset_class") != "stock":
        return {"status": "not_applicable", "sources": [], "values": []}, {}
    embedded = latest(asset.get("monthly_revenue") or [])
    channel = latest(revenue.get(symbol) or [])
    status, values = status_for(embedded.get("revenue"), channel.get("revenue"), .001)
    return {
        "status": status,
        "sources": [source for source in [embedded.get("source"), channel.get("source")] if source],
        "period": channel.get("period") or embedded.get("period"),
        "values": values,
    }, channel


def build_dividend_field(asset: dict[str, Any], symbol: str, dividends: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    embedded = latest(asset.get("dividends") or [])
    channel = latest(dividends.get(symbol) or [])
    status, values = status_for(embedded.get("cash"), channel.get("cash"), .001)
    return {
        "status": status,
        "sources": [source for source in [embedded.get("source"), channel.get("source")] if source],
        "period": channel.get("period") or embedded.get("period"),
        "values": values,
    }, channel


def build_metrics_field(asset: dict[str, Any], yahoo_row: dict[str, Any]) -> dict[str, Any]:
    if asset.get("asset_class") != "stock":
        return {"status": "not_applicable", "fields": {}, "available": []}
    official_metrics = mapping(asset.get("metrics"))
    reference_metrics = mapping(yahoo_row.get("metrics"))
    metric_meta = mapping(yahoo_row.get("metrics_meta"))
    metric_fields: dict[str, Any] = {}
    for key in sorted(set(official_metrics) | set(reference_metrics)):
        meta = mapping(metric_meta.get(key))
        status, values = status_for(official_metrics.get(key), reference_metrics.get(key), .01, str(meta.get("status") or "reference"))
        metric_fields[key] = {
            "status": status,
            "values": values,
            "sources": [source for source, value in [
                (mapping(asset.get("metric_sources")).get(key) or "official financial data", official_metrics.get(key)),
                (meta.get("source") or "Yahoo Finance", reference_metrics.get(key)),
            ] if num(value) is not None],
            "formula": meta.get("formula"),
        }
    return {"status": overall_status(metric_fields), "fields": metric_fields, "available": list(metric_fields)}


def build_etf_field(asset: dict[str, Any], symbol: str, etf_details: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if asset.get("asset_class") != "etf":
        return None, {}
    official_etf = mapping(asset.get("etf"))
    reference_etf = mapping(etf_details.get(symbol))
    verification = mapping(reference_etf.get("verification"))
    field_sources = mapping(reference_etf.get("field_sources"))
    checks: dict[str, Any] = {}
    text_fields = {"issuer", "manager", "benchmark"}
    for key in ("issuer", "manager", "benchmark", "aum", "beneficiary_count", "nav", "premium_discount", "holdings", "allocations", "distributions"):
        official_value, reference_value = official_etf.get(key), reference_etf.get(key)
        if key == "benchmark":
            official_value, reference_value = normalize_benchmark_value(official_value), normalize_benchmark_value(reference_value)
        reference_status = str(mapping(verification.get(key)).get("status") or "reference")
        if isinstance(official_value, (list, dict)) or isinstance(reference_value, (list, dict)):
            if official_value:
                status = "official"
            elif reference_value:
                status = reference_status
            else:
                status = "missing"
            values = [len(value) if isinstance(value, list) else bool(value) for value in (official_value, reference_value) if value]
        elif key in text_fields:
            status, values = text_status_for(official_value, reference_value, reference_status)
        else:
            status, values = status_for(official_value, reference_value, .02, reference_status)
        checks[key] = {"status": status, "values": values, "source": field_sources.get(key)}
    return {"status": overall_status(checks), "fields": checks}, reference_etf


def completeness_for(fields: dict[str, Any], audit: dict[str, Any]) -> tuple[str, float | int | None]:
    if audit:
        raw_coverage = audit.get("coverage_percent")
        coverage = num(raw_coverage)
        completeness = "unresolved" if coverage is None or coverage <= 0 else str(audit.get("status") or "partial")
        if completeness not in {"complete", "partial", "unresolved"}:
            completeness = "partial"
        return completeness, raw_coverage if raw_coverage is not None else coverage
    required = [mapping(row) for row in fields.values() if mapping(row).get("status") != "not_applicable"]
    missing = [row for row in required if row.get("status") == "missing"]
    coverage = round((len(required) - len(missing)) / len(required) * 100, 2) if required else 0
    return ("unresolved" if not required else "complete" if not missing else "partial"), coverage


def build_asset_verification(
    asset: dict[str, Any], *, payloads: dict[str, dict[str, Any]], quotes: dict[str, dict[str, Any]],
    revenue: dict[str, Any], dividends: dict[str, Any], secondary: dict[str, Any], yahoo: dict[str, Any],
    etf_details: dict[str, Any], audit_map: dict[str, dict[str, Any]], source_snapshots: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], str, str] | None:
    symbol = str(asset.get("symbol") or "").upper()
    if not symbol or asset.get("market") != "TW":
        return None
    asset_class = str(asset.get("asset_class") or "")

    fields: dict[str, Any] = {}
    fields["quote"], official_quote, secondary_quote = build_quote_field(symbol, payloads, quotes, secondary)
    fields["monthly_revenue"], channel_revenue = build_revenue_field(asset, symbol, revenue)
    fields["dividends"], channel_dividend = build_dividend_field(asset, symbol, dividends)
    yahoo_row = mapping(yahoo.get(symbol))
    fields["metrics"] = build_metrics_field(asset, yahoo_row)
    etf_field, reference_etf = build_etf_field(asset, symbol, etf_details)
    if etf_field is not None:
        fields["etf"] = etf_field

    trust_overall = overall_status(fields)
    audit = mapping(audit_map.get(symbol))
    completeness, coverage = completeness_for(fields, audit)
    suffix = "TWO" if str(asset.get("exchange") or "").upper() == "TPEX" else "TW"

    verified_against = {
        "assets": row_stamp(asset, source_snapshots["assets"].get("updated_at"), "master_updated_at", "updated_at"),
        "asset_audit": row_stamp(audit, source_snapshots["asset_audit"].get("updated_at"), "updated_at"),
        "tw_market": row_stamp(official_quote, source_snapshots["tw_market"].get("updated_at"), "updated_at", "market_at", "market_at_local"),
        "monthly_revenue": row_stamp(channel_revenue, source_snapshots["monthly_revenue"].get("updated_at"), "source_updated_at", "updated_at") if asset_class == "stock" else None,
        "dividend_history": row_stamp(channel_dividend, source_snapshots["dividend_history"].get("updated_at"), "source_updated_at", "updated_at"),
        "secondary_reference": row_stamp(secondary_quote, source_snapshots["secondary_reference"].get("updated_at"), "updated_at", "market_at"),
        "yahoo_details": row_stamp(yahoo_row, source_snapshots["yahoo_details"].get("updated_at"), "updated_at"),
        "etf_details": row_stamp(reference_etf, source_snapshots["etf_details"].get("updated_at"), "updated_at") if asset_class == "etf" else None,
    }

    row = {
        "symbol": symbol,
        "overall": trust_overall,
        "trust_overall": trust_overall,
        "completeness_status": completeness,
        "coverage_percent": coverage,
        "missing_fields": sequence(audit.get("missing_fields")),
        "fields": fields,
        "reference_links": {
            "yahoo": f"https://tw.stock.yahoo.com/quote/{symbol}.{suffix}",
            "goodinfo": f"https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={symbol}",
            "moneydj_etf": f"https://www.moneydj.com/ETF/X/Basic/Basic0004.xdjhtm?etfid={symbol}.TW" if asset_class == "etf" else None,
            "histock_etf": "https://histock.tw/stock/active-etf.aspx" if asset_class == "etf" else None,
        },
        "verified_against": verified_against,
        "snapshot_verified_against": {key: snapshot.get("updated_at") for key, snapshot in source_snapshots.items()},
        "updated_at": NOW.isoformat(timespec="seconds"),
    }
    return row, trust_overall, completeness


def main() -> None:
    payloads = {key: mapping(read_json(DATA / filename, {})) for key, filename in SOURCE_FILES.items()}
    assets = sequence(payloads["assets"].get("assets"))
    market = sequence(payloads["tw_market"].get("items"))
    revenue = mapping(payloads["monthly_revenue"].get("items"))
    dividends = mapping(payloads["dividend_history"].get("items"))
    secondary = mapping(payloads["secondary_reference"].get("items"))
    yahoo = mapping(payloads["yahoo_details"].get("items"))
    etf_details = mapping(payloads["etf_details"].get("items"))
    audit_rows = sequence(payloads["asset_audit"].get("assets"))
    audit_map = {str(mapping(row).get("symbol") or "").upper(): mapping(row) for row in audit_rows if isinstance(row, dict)}
    audit_summary = mapping(payloads["asset_audit"].get("summary"))
    quotes = {str(mapping(row).get("symbol") or "").upper(): mapping(row) for row in market if isinstance(row, dict)}

    source_snapshots = {key: snapshot_info(payload, key) for key, payload in payloads.items()}
    stale_sources = [key for key, row in source_snapshots.items() if row["stale"]]
    version_mismatch_sources = [key for key, row in source_snapshots.items() if row.get("version") != VERSION]
    output: dict[str, Any] = {}
    trust_counts = {status: 0 for status in TRUST_ORDER}
    completeness_counts = {"complete": 0, "partial": 0, "unresolved": 0}

    for raw_asset in assets:
        if not isinstance(raw_asset, dict):
            continue
        built = build_asset_verification(
            raw_asset,
            payloads=payloads, quotes=quotes, revenue=revenue, dividends=dividends,
            secondary=secondary, yahoo=yahoo, etf_details=etf_details,
            audit_map=audit_map, source_snapshots=source_snapshots,
        )
        if not built:
            continue
        row, trust, completeness = built
        output[row["symbol"]] = row
        trust_counts[trust] = trust_counts.get(trust, 0) + 1
        completeness_counts[completeness] = completeness_counts.get(completeness, 0) + 1

    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": "partial" if trust_counts.get("conflict") or completeness_counts.get("unresolved") or stale_sources or version_mismatch_sources else "ok",
            "counts": trust_counts,
            "trust_counts": trust_counts,
            "completeness_counts": completeness_counts,
            "average_field_coverage_percent": audit_summary.get("average_field_coverage_percent"),
            "source_snapshots": source_snapshots,
            "stale_sources": stale_sources,
            "version_mismatch_sources": version_mismatch_sources,
            "verification_basis": "isolated stock/ETF adapters; per-symbol source timestamps when available; channel snapshots retained separately",
            "note": "Official values are primary. Optional channels are fail-closed and never leak state across asset classes.",
        },
        "items": output,
    }
    write_payload("data-verification.json", "__DATA_VERIFICATION_SEED__", payload)
    print(payload["metadata"])


if __name__ == "__main__":
    main()
