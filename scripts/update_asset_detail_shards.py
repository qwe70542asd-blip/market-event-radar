#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from common import DATA, NOW, VERSION, read_json, write_payload

SHARDS = tuple(f"{value:02d}" for value in range(100))


def mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def compact_verification(row: dict[str, Any]) -> dict[str, Any]:
    fields = mapping(row.get("fields"))
    metric_block = mapping(fields.get("metrics"))
    metric_fields = mapping(metric_block.get("fields"))
    return {
        "overall": row.get("overall"),
        "trust_overall": row.get("trust_overall"),
        "completeness_status": row.get("completeness_status"),
        "coverage_percent": row.get("coverage_percent"),
        "missing_fields": (row.get("missing_fields") or [])[:12],
        "fields": {
            "quote": {"status": mapping(fields.get("quote")).get("status")},
            "monthly_revenue": {"status": mapping(fields.get("monthly_revenue")).get("status")},
            "dividends": {"status": mapping(fields.get("dividends")).get("status")},
            "metrics": {
                "status": metric_block.get("status"),
                "fields": {key: {"status": mapping(value).get("status")} for key, value in metric_fields.items()},
            },
        },
        "reference_links": mapping(row.get("reference_links")),
        "updated_at": row.get("updated_at"),
    }


def source_status(payload: dict[str, Any]) -> dict[str, Any]:
    meta = mapping(payload.get("metadata"))
    return {key: value for key, value in meta.items() if key not in {"errors", "source_snapshots"}}


def main() -> None:
    assets_payload = mapping(read_json(DATA / "assets.json", {}))
    assets = {str(row.get("symbol") or "").upper(): row for row in assets_payload.get("assets") or [] if isinstance(row, dict) and row.get("symbol")}
    chip_payload = mapping(read_json(DATA / "tw-chips.json", {})); chips = mapping(chip_payload.get("items"))
    revenue_payload = mapping(read_json(DATA / "monthly-revenue.json", {})); revenue = mapping(revenue_payload.get("items"))
    dividend_payload = mapping(read_json(DATA / "dividend-history.json", {})); dividends = mapping(dividend_payload.get("items"))
    secondary_payload = mapping(read_json(DATA / "secondary-reference.json", {})); secondary = mapping(secondary_payload.get("items"))
    yahoo_payload = mapping(read_json(DATA / "yahoo-details.json", {})); yahoo = mapping(yahoo_payload.get("items"))
    etf_payload = mapping(read_json(DATA / "etf-details.json", {})); etf = mapping(etf_payload.get("items"))
    basics_payload = mapping(read_json(DATA / "stock-basics.json", {})); basics = mapping(basics_payload.get("items"))
    verification_payload = mapping(read_json(DATA / "data-verification.json", {})); verification = mapping(verification_payload.get("items"))

    symbols = set(assets) | set(chips) | set(revenue) | set(dividends) | set(secondary) | set(yahoo) | set(etf) | set(basics) | set(verification)
    buckets: dict[str, dict[str, Any]] = {key: {} for key in SHARDS}
    for symbol in sorted(symbols):
        key = symbol[:2] if len(symbol) >= 2 and symbol[:2].isdigit() and symbol[:2] in buckets else "00"
        row: dict[str, Any] = {}
        if symbol in assets: row["asset"] = assets[symbol]
        if symbol in chips: row["chip"] = chips[symbol]
        if symbol in revenue: row["revenue"] = revenue[symbol]
        if symbol in dividends: row["dividends"] = dividends[symbol]
        if symbol in secondary: row["secondary"] = secondary[symbol]
        if symbol in yahoo: row["yahoo"] = yahoo[symbol]
        if symbol in etf: row["etf"] = etf[symbol]
        if symbol in basics: row["stock_basic"] = basics[symbol]
        if symbol in verification: row["verification"] = compact_verification(mapping(verification[symbol]))
        buckets[key][symbol] = row

    sources = {
        "assets": source_status(assets_payload), "tw_chips": source_status(chip_payload),
        "monthly_revenue": source_status(revenue_payload), "dividend_history": source_status(dividend_payload),
        "secondary_reference": source_status(secondary_payload), "yahoo_details": source_status(yahoo_payload),
        "etf_details": source_status(etf_payload), "stock_basics": source_status(basics_payload),
        "data_verification": source_status(verification_payload),
    }
    for key in SHARDS:
        payload = {
            "metadata": {
                "version": VERSION,
                "updated_at": NOW.isoformat(timespec="seconds"),
                "status": "ok" if buckets[key] else "waiting",
                "item_count": len(buckets[key]),
                "shard": key,
                "shard_basis": "first-two-symbol-characters",
                "payload_mode": "single-asset-detail-bounded",
                "sources": sources,
                "note": "Asset pages load only one symbol-prefix shard instead of all full historical datasets.",
            },
            "items": buckets[key],
        }
        write_payload(f"asset-detail-shard-{key}.json", None, payload)
    print({key: len(value) for key, value in buckets.items()})


if __name__ == "__main__":
    main()
