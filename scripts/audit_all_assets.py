#!/usr/bin/env python3
"""Audit every Taiwan stock and ETF after multi-source enrichment."""
from __future__ import annotations

import csv
from typing import Any

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.16"


def present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def rows(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        return value["rows"]
    return []


def first_value(*values: Any) -> Any:
    return next((value for value in values if present(value)), None)


def first_rows(*values: Any) -> list:
    return next((rows(value) for value in values if rows(value)), [])


def merge_nonempty(*objects: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for obj in objects:
        for key, value in (obj or {}).items():
            if present(value) and not present(result.get(key)):
                result[key] = value
    return result


def derive_allocations(holdings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    totals: dict[str, float] = {}
    for holding in holdings or []:
        sector = holding.get("sector") or holding.get("industry") or holding.get("industry_name")
        try:
            weight = float(holding.get("weight"))
        except (TypeError, ValueError):
            continue
        if sector:
            totals[str(sector)] = totals.get(str(sector), 0) + weight
    return [{"name": name, "weight": weight} for name, weight in totals.items()]


def stock_checks(asset: dict[str, Any], yahoo: dict[str, Any]) -> list[tuple[str, bool, str]]:
    metrics = merge_nonempty(asset.get("metrics") or {}, yahoo.get("metrics") or {})
    status = asset.get("metric_status") or {}
    financials = first_rows(asset.get("financials"), yahoo.get("financials"))
    profile = yahoo.get("profile") or {}
    checks = [
        ("公司名稱", present(asset.get("company_name") or asset.get("name") or profile.get("company_name")), "company_master_missing"),
        ("市場", present(asset.get("exchange")), "company_master_missing"),
        ("產業", present(asset.get("official_industry") or asset.get("sub_industry") or profile.get("industry") or profile.get("sector")), "company_master_missing"),
        ("上市／上櫃日期", present(asset.get("listed_date")), "company_master_field_missing"),
        ("發行股數", present(asset.get("issued_shares") or metrics.get("shares_outstanding")), "company_master_field_missing"),
        ("本益比狀態", present(metrics.get("pe")) or status.get("pe") in {"available", "not_applicable"}, "valuation_source_missing"),
        ("股價淨值比狀態", present(metrics.get("pb")) or status.get("pb") in {"available", "not_applicable"}, "valuation_source_missing"),
        ("殖利率狀態", present(metrics.get("dividend_yield")) or status.get("dividend_yield") in {"available", "not_applicable"}, "valuation_source_missing"),
        ("EPS", present(metrics.get("eps")) or status.get("eps") == "not_applicable", "financial_statement_missing"),
        ("ROE", present(metrics.get("roe")) or status.get("roe") == "not_applicable", "financial_statement_missing"),
        ("負債比", present(metrics.get("debt_ratio")) or status.get("debt_ratio") == "not_applicable", "financial_statement_missing"),
        ("淨利率", present(metrics.get("net_margin")) or status.get("net_margin") == "not_applicable", "financial_statement_missing"),
        ("最近季度財報", bool(financials), "financial_statement_missing"),
        ("歷季財報", len(financials) >= 4, "quarter_history_incomplete"),
    ]
    return checks


def etf_checks(asset: dict[str, Any], yahoo: dict[str, Any], details: dict[str, Any], dividend_channel: Any) -> list[tuple[str, bool, str]]:
    official = asset.get("etf") or {}
    yahoo_etf = yahoo.get("etf") or {}
    etf = merge_nonempty(official, details, yahoo_etf)
    distributions = first_rows(official.get("distributions"), details.get("distributions"), yahoo.get("dividends"), dividend_channel)
    holdings = first_rows(official.get("holdings"), details.get("holdings"), yahoo_etf.get("holdings"))
    allocations = first_rows(official.get("allocations"), official.get("sector_allocation"), details.get("allocations"), details.get("sector_allocation"), yahoo_etf.get("allocations"), yahoo_etf.get("sector_allocation"))
    if not allocations:
        allocations = derive_allocations(holdings)
    category = first_value(official.get("category"), asset.get("sub_industry"), details.get("category"), yahoo_etf.get("category"))
    strategy = first_value(official.get("strategy"), details.get("strategy"), yahoo_etf.get("strategy"))
    active = "主動" in str(category or strategy or asset.get("name") or "")
    return [
        ("基金名稱", present(first_value(official.get("formal_name"), asset.get("name"), details.get("formal_name"))), "etf_master_missing"),
        ("市場", present(asset.get("exchange")), "etf_master_missing"),
        ("發行投信", present(first_value(official.get("issuer"), official.get("family"), details.get("issuer"), details.get("family"), yahoo_etf.get("issuer"), yahoo_etf.get("family"))), "etf_prospectus_missing"),
        ("基金經理人", present(first_value(official.get("manager"), details.get("manager"), yahoo_etf.get("manager"))), "etf_prospectus_missing"),
        ("保管銀行", present(first_value(official.get("custodian"), details.get("custodian"), yahoo_etf.get("custodian"))), "etf_prospectus_missing"),
        ("基金類型", present(category), "etf_master_missing"),
        ("成立日期", present(first_value(official.get("inception_date"), details.get("inception_date"), yahoo_etf.get("inception_date"))), "etf_master_field_missing"),
        ("上市／上櫃日期", present(first_value(official.get("listing_date"), asset.get("listed_date"), details.get("listing_date"), yahoo_etf.get("listing_date"))), "etf_master_field_missing"),
        ("追蹤指數／主動式", present(first_value(official.get("benchmark"), details.get("benchmark"), yahoo_etf.get("benchmark"))) or active, "etf_benchmark_not_applicable_or_missing"),
        ("投資策略", present(strategy or category), "etf_prospectus_missing"),
        ("配息資訊", bool(distributions) or present(first_value(official.get("distribution_frequency"), details.get("distribution_frequency"), yahoo_etf.get("distribution_frequency"))), "etf_distribution_missing"),
        ("成分股揭露狀態", bool(holdings) or present(first_value(official.get("holdings_status"), details.get("holdings_status"))), "etf_holdings_not_disclosed"),
        ("產業配置", bool(allocations), "etf_allocation_missing"),
    ]


def main() -> None:
    payload = read_json(DATA / "assets.json", {"assets": []})
    yahoo_items = read_json(DATA / "yahoo-details.json", {"items": {}}).get("items", {})
    etf_items = read_json(DATA / "etf-details.json", {"items": {}}).get("items", {})
    dividend_items = read_json(DATA / "dividend-history.json", {"items": {}}).get("items", {})
    audit_rows = []
    field_totals: dict[str, dict[str, int]] = {}
    for asset in payload.get("assets", []):
        if asset.get("market") != "TW" or asset.get("asset_class") not in {"stock", "etf"}:
            continue
        symbol = str(asset.get("symbol") or "").upper()
        yahoo = yahoo_items.get(symbol) or {}
        if asset.get("asset_class") == "stock":
            checks = stock_checks(asset, yahoo)
        else:
            checks = etf_checks(asset, yahoo, etf_items.get(symbol) or {}, dividend_items.get(symbol) or {})
        missing = [label for label, ok, _reason in checks if not ok]
        reasons = [reason for _label, ok, reason in checks if not ok]
        coverage = round((len(checks) - len(missing)) / len(checks) * 100, 2)
        for label, ok, _reason in checks:
            field_totals.setdefault(label, {"available": 0, "missing": 0})["available" if ok else "missing"] += 1
        audit_rows.append({
            "symbol": asset.get("symbol"),
            "name": asset.get("name"),
            "asset_class": asset.get("asset_class"),
            "exchange": asset.get("exchange"),
            "status": "complete" if not missing else "partial",
            "coverage_percent": coverage,
            "missing_fields": missing,
            "missing_reasons": reasons,
            "multi_source": bool(yahoo or etf_items.get(symbol) or dividend_items.get(symbol)),
        })

    summary = {
        "audited_assets": len(audit_rows),
        "stock_count": sum(row["asset_class"] == "stock" for row in audit_rows),
        "etf_count": sum(row["asset_class"] == "etf" for row in audit_rows),
        "complete": sum(row["status"] == "complete" for row in audit_rows),
        "partial": sum(row["status"] == "partial" for row in audit_rows),
        "unresolved": sum(row["coverage_percent"] == 0 for row in audit_rows),
        "audit_coverage_percent": 100.0,
        "average_field_coverage_percent": round(sum(row["coverage_percent"] for row in audit_rows) / len(audit_rows), 2) if audit_rows else 0,
    }
    audit = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "note": "Audit uses the final merged view: official asset master first, then Yahoo, ETF detail and dividend channels. Existing reference data is no longer reported as missing.",
        },
        "summary": summary,
        "field_coverage": field_totals,
        "assets": audit_rows,
    }
    write_payload("asset-audit.json", "__ASSET_AUDIT_SEED__", audit)
    (DATA / "asset-coverage.json").write_text(
        __import__("json").dumps({"metadata": audit["metadata"], "summary": summary, "field_coverage": field_totals}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (DATA / "asset-audit-failures.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["symbol", "name", "asset_class", "exchange", "status", "coverage_percent", "missing_fields", "missing_reasons"])
        for row in audit_rows:
            if row["missing_fields"]:
                writer.writerow([
                    row["symbol"], row["name"], row["asset_class"], row["exchange"], row["status"], row["coverage_percent"],
                    " | ".join(row["missing_fields"]), " | ".join(row["missing_reasons"]),
                ])


if __name__ == "__main__":
    main()
