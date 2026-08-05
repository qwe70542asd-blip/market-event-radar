#!/usr/bin/env python3
"""Audit every Taiwan stock and ETF for the v11.4.7 final release."""
from __future__ import annotations

import csv
from typing import Any

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.7"


def present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def stock_checks(asset: dict[str, Any]) -> list[tuple[str, bool, str]]:
    metrics = asset.get("metrics") or {}
    status = asset.get("metric_status") or {}
    financials = asset.get("financials") or []
    checks = [
        ("公司名稱", present(asset.get("company_name") or asset.get("name")), "company_master_missing"),
        ("市場", present(asset.get("exchange")), "company_master_missing"),
        ("產業", present(asset.get("official_industry")), "company_master_missing"),
        ("上市／上櫃日期", present(asset.get("listed_date")), "company_master_field_missing"),
        ("發行股數", present(asset.get("issued_shares")), "company_master_field_missing"),
        ("本益比狀態", status.get("pe") in {"available", "not_applicable"}, "valuation_source_missing"),
        ("股價淨值比狀態", status.get("pb") in {"available", "not_applicable"}, "valuation_source_missing"),
        ("殖利率狀態", status.get("dividend_yield") in {"available", "not_applicable"}, "valuation_source_missing"),
        ("EPS", present(metrics.get("eps")) or status.get("eps") == "not_applicable", "financial_statement_missing"),
        ("ROE", present(metrics.get("roe")) or status.get("roe") == "not_applicable", "financial_statement_missing"),
        ("負債比", present(metrics.get("debt_ratio")) or status.get("debt_ratio") == "not_applicable", "financial_statement_missing"),
        ("淨利率", present(metrics.get("net_margin")) or status.get("net_margin") == "not_applicable", "financial_statement_missing"),
        ("最近季度財報", bool(financials), "financial_statement_missing"),
        ("歷季財報", len(financials) >= 4, "quarter_history_incomplete"),
    ]
    return checks


def etf_checks(asset: dict[str, Any]) -> list[tuple[str, bool, str]]:
    etf = asset.get("etf") or {}
    active = "主動" in str(etf.get("category") or etf.get("management_style") or asset.get("name") or "")
    return [
        ("基金名稱", present(etf.get("formal_name") or asset.get("name")), "etf_master_missing"),
        ("市場", present(asset.get("exchange")), "etf_master_missing"),
        ("發行投信", present(etf.get("issuer")), "etf_prospectus_missing"),
        ("基金經理人", present(etf.get("manager")), "etf_prospectus_missing"),
        ("保管銀行", present(etf.get("custodian")), "etf_prospectus_missing"),
        ("基金類型", present(etf.get("category") or asset.get("sub_industry")), "etf_master_missing"),
        ("成立日期", present(etf.get("inception_date")), "etf_master_field_missing"),
        ("上市／上櫃日期", present(etf.get("listing_date") or asset.get("listed_date")), "etf_master_field_missing"),
        ("追蹤指數／主動式", present(etf.get("benchmark")) or active, "etf_benchmark_not_applicable_or_missing"),
        ("投資策略", present(etf.get("strategy")), "etf_prospectus_missing"),
        ("配息資訊", present(etf.get("distribution_frequency") or etf.get("distributions")), "etf_distribution_missing"),
        ("成分股揭露狀態", present(etf.get("holdings")) or present(etf.get("holdings_status")), "etf_holdings_not_disclosed"),
    ]


def main() -> None:
    payload = read_json(DATA / "assets.json", {"assets": []})
    rows = []
    field_totals: dict[str, dict[str, int]] = {}
    for asset in payload.get("assets", []):
        if asset.get("market") != "TW" or asset.get("asset_class") not in {"stock", "etf"}:
            continue
        checks = stock_checks(asset) if asset.get("asset_class") == "stock" else etf_checks(asset)
        missing = [label for label, ok, _reason in checks if not ok]
        reasons = [reason for _label, ok, reason in checks if not ok]
        coverage = round((len(checks) - len(missing)) / len(checks) * 100, 2)
        for label, ok, _reason in checks:
            field_totals.setdefault(label, {"available": 0, "missing": 0})["available" if ok else "missing"] += 1
        rows.append(
            {
                "symbol": asset.get("symbol"),
                "name": asset.get("name"),
                "asset_class": asset.get("asset_class"),
                "exchange": asset.get("exchange"),
                "status": "complete" if not missing else "partial",
                "coverage_percent": coverage,
                "missing_fields": missing,
                "missing_reasons": reasons,
            }
        )

    summary = {
        "audited_assets": len(rows),
        "stock_count": sum(row["asset_class"] == "stock" for row in rows),
        "etf_count": sum(row["asset_class"] == "etf" for row in rows),
        "complete": sum(row["status"] == "complete" for row in rows),
        "partial": sum(row["status"] == "partial" for row in rows),
        "unresolved": sum(row["coverage_percent"] == 0 for row in rows),
        "audit_coverage_percent": 100.0,
        "average_field_coverage_percent": round(sum(row["coverage_percent"] for row in rows) / len(rows), 2) if rows else 0,
    }
    audit = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "note": "Every Taiwan stock and ETF is audited separately; stock financial fields and ETF fund disclosures are never mixed.",
        },
        "summary": summary,
        "field_coverage": field_totals,
        "assets": rows,
    }
    write_payload("asset-audit.json", "__ASSET_AUDIT_SEED__", audit)
    (DATA / "asset-coverage.json").write_text(
        __import__("json").dumps({"metadata": audit["metadata"], "summary": summary, "field_coverage": field_totals}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with (DATA / "asset-audit-failures.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["symbol", "name", "asset_class", "exchange", "status", "coverage_percent", "missing_fields", "missing_reasons"])
        for row in rows:
            if row["missing_fields"]:
                writer.writerow(
                    [
                        row["symbol"],
                        row["name"],
                        row["asset_class"],
                        row["exchange"],
                        row["status"],
                        row["coverage_percent"],
                        " | ".join(row["missing_fields"]),
                        " | ".join(row["missing_reasons"]),
                    ]
                )


if __name__ == "__main__":
    main()
