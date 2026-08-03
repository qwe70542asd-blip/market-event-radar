#!/usr/bin/env python3
"""Exhaustively audit every Taiwan stock and ETF in the generated master.

This audit never samples. Every TW asset receives a row in asset-audit.json.
Missing values are classified as unavailable, not applicable, awaiting filing,
source failure, or parser mismatch so unresolved cases can be fixed in batches.
"""
from __future__ import annotations

import csv
import json
import math
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = DATA / "assets.json"
MARKET = DATA / "tw-market.json"
CHIPS = DATA / "tw-chips.json"
NEWS = DATA / "news.json"
UPDATE_STATUS = DATA / "asset-update-status.json"
OUT = DATA / "asset-audit.json"
SEED = DATA / "asset-audit-seed.js"
FAILURES_CSV = DATA / "asset-audit-failures.csv"
NOW = datetime.now(ZoneInfo("Asia/Taipei"))

FIELD_LABELS = {
    "master.full_name": "公司／基金全名",
    "master.listing_date": "上市／上櫃日期",
    "master.industry": "產業分類",
    "profile.issued_shares": "發行股數",
    "metrics.eps": "EPS",
    "metrics.pe": "本益比",
    "metrics.pb": "股價淨值比",
    "metrics.dividend_yield": "殖利率",
    "metrics.roe": "ROE",
    "metrics.debt_ratio": "負債比",
    "metrics.current_ratio": "流動比率",
    "metrics.net_margin": "淨利率",
    "financials.latest": "最近財報",
    "financials.history": "歷季財報",
    "dividend.history": "股利／除權息",
    "etf.issuer": "ETF 發行公司",
    "etf.manager": "ETF 基金經理人",
    "etf.category": "ETF 類型",
    "etf.benchmark": "ETF 追蹤指數／績效指標",
    "etf.strategy": "ETF 投資策略",
    "etf.inception_date": "ETF 成立日期",
    "etf.listing_date": "ETF 上市日期",
    "etf.custodian": "ETF 保管機構",
    "market.quote": "最近行情",
    "chips.institutional": "三大法人",
    "chips.margin": "融資",
    "chips.short": "融券",
    "chips.day_trading": "當沖",
    "news.recent": "近期新聞／公告",
}

FINANCIAL_INDUSTRY = re.compile(r"金融|銀行|保險|證券|期貨|金控", re.I)


def load(path: Path, default):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else default
    except Exception:
        return default


def finite(value):
    try:
        if value in (None, "", "-", "--", "NA", "N/A"):
            return None
        number = float(str(value).replace(",", "").replace("%", ""))
        return number if math.isfinite(number) else None
    except Exception:
        return None


def value_present(value) -> bool:
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (int, float)):
        return finite(value) is not None
    return value is not None


def parse_date(value):
    text = str(value or "").strip()
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    try:
        if len(digits) >= 8:
            year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
        elif len(digits) == 7:
            year, month, day = int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:7])
        else:
            return None
        return datetime(year, month, day, tzinfo=NOW.tzinfo)
    except Exception:
        return None


def expected_financial_periods(asset: dict) -> int:
    listing = parse_date((asset.get("profile") or {}).get("listing_date"))
    if listing is None:
        return 4
    months = max(0, (NOW.year - listing.year) * 12 + NOW.month - listing.month)
    return max(1, min(12, months // 3))


def market_key(asset: dict) -> tuple[str, str]:
    exchange = "tpex" if "TPEX" in str(asset.get("exchange") or "").upper() else "twse"
    return exchange, str(asset.get("symbol") or "").upper()


def build_maps(market_payload: dict, chips_payload: dict, news_payload: dict):
    quote_map = {}
    for row in market_payload.get("items") or []:
        exchange = "tpex" if "TPEX" in str(row.get("exchange") or "").upper() else "twse"
        symbol = str(row.get("symbol") or "").upper()
        if symbol:
            quote_map[(exchange, symbol)] = row

    chip_map = {}
    for key, row in (chips_payload.get("items") or {}).items():
        if not isinstance(row, dict):
            continue
        exchange = str(row.get("market") or str(key).split(":", 1)[0] or "twse").lower()
        symbol = str(row.get("symbol") or str(key).split(":")[-1]).upper()
        if symbol:
            chip_map[("tpex" if "tpex" in exchange else "twse", symbol)] = row

    news_counts = Counter()
    for item in news_payload.get("items") or []:
        symbols = item.get("asset_symbols") or []
        if not symbols:
            symbols = re.findall(r"(?<!\d)(\d{4,6}[A-Z]?)(?!\d)", f"{item.get('title','')} {item.get('summary','')}")
        for symbol in symbols:
            news_counts[str(symbol).upper()] += 1
    return quote_map, chip_map, news_counts


def field_result(field: str, available: bool, reason: str | None = None, value=None, *, required=True):
    return {
        "field": field,
        "label": FIELD_LABELS.get(field, field),
        "required": required,
        "available": bool(available),
        "reason": None if available else reason,
        "value": value if available else None,
    }


def audit_stock(asset: dict, quote: dict | None, chip: dict | None, news_count: int):
    profile = asset.get("profile") or {}
    metrics = asset.get("metrics") or {}
    financials = [row for row in (asset.get("financials") or []) if isinstance(row, dict)]
    dividend = asset.get("dividend") or {}
    dividend_history = asset.get("dividend_history") or []
    industry = str(asset.get("official_industry") or asset.get("sub_industry") or "")
    results = []

    results.append(field_result("master.full_name", value_present(profile.get("full_name")), "master_parse_missing", profile.get("full_name")))
    results.append(field_result("master.listing_date", value_present(profile.get("listing_date")), "master_parse_missing", profile.get("listing_date")))
    results.append(field_result("master.industry", value_present(industry), "master_parse_missing", industry))
    results.append(field_result("profile.issued_shares", value_present(profile.get("issued_shares")), "master_parse_missing", profile.get("issued_shares")))

    for field in ("eps", "pb", "dividend_yield", "roe", "debt_ratio", "net_margin"):
        value = metrics.get(field)
        reason = "awaiting_filing_or_parser_mismatch" if field in {"eps", "roe", "debt_ratio", "net_margin"} else "valuation_source_missing"
        results.append(field_result(f"metrics.{field}", value_present(value), reason, value))

    if FINANCIAL_INDUSTRY.search(industry):
        results.append(field_result("metrics.current_ratio", False, "not_applicable_financial_industry", required=False))
    else:
        results.append(field_result("metrics.current_ratio", value_present(metrics.get("current_ratio")), "balance_sheet_parser_mismatch", metrics.get("current_ratio")))

    eps = finite(metrics.get("eps"))
    if eps is not None and eps <= 0:
        results.append(field_result("metrics.pe", False, "not_applicable_non_positive_eps", required=False))
    else:
        results.append(field_result("metrics.pe", value_present(metrics.get("pe")), "valuation_source_missing", metrics.get("pe")))

    results.append(field_result("financials.latest", bool(financials), "no_parsed_financial_statement", financials[0] if financials else None))
    expected = expected_financial_periods(asset)
    history_ok = len(financials) >= expected
    results.append(field_result(
        "financials.history", history_ok,
        "quarter_history_incomplete",
        {"periods": len(financials), "expected": expected},
    ))

    dividend_available = bool(dividend_history) or any(value_present(value) for value in dividend.values())
    results.append(field_result(
        "dividend.history", dividend_available,
        "no_dividend_record_or_parser_missing",
        dividend_history or dividend,
        required=False,
    ))

    results.append(field_result("market.quote", bool(quote and finite(quote.get("price")) is not None), "market_source_missing", quote, required=False))
    institutional = chip and any(finite(chip.get(field)) is not None for field in ("foreign_net", "trust_net", "dealer_net", "total_net"))
    results.append(field_result("chips.institutional", bool(institutional), "chip_source_missing", chip, required=False))
    results.append(field_result("chips.margin", bool(chip and any(finite((chip.get("margin") or {}).get(field)) is not None for field in ("balance", "buy", "sell"))), "non_credit_or_source_missing", chip.get("margin") if chip else None, required=False))
    results.append(field_result("chips.short", bool(chip and any(finite((chip.get("short") or {}).get(field)) is not None for field in ("balance", "buy", "sell"))), "non_credit_or_source_missing", chip.get("short") if chip else None, required=False))
    results.append(field_result("chips.day_trading", bool(chip and any(value_present(value) for value in (chip.get("day_trading") or {}).values())), "not_eligible_or_source_missing", chip.get("day_trading") if chip else None, required=False))
    results.append(field_result("news.recent", news_count > 0, "no_recent_matching_news", news_count, required=False))
    return results


def audit_etf(asset: dict, quote: dict | None, chip: dict | None, news_count: int):
    etf = asset.get("etf") or {}
    results = []
    fields = (
        "issuer", "manager", "category", "benchmark", "strategy",
        "inception_date", "listing_date", "custodian",
    )
    for field in fields:
        results.append(field_result(f"etf.{field}", value_present(etf.get(field)), "etf_master_or_prospectus_missing", etf.get(field)))
    results.append(field_result("master.full_name", value_present(etf.get("full_name") or asset.get("name")), "etf_master_missing", etf.get("full_name") or asset.get("name")))
    results.append(field_result("market.quote", bool(quote and finite(quote.get("price")) is not None), "market_source_missing", quote, required=False))
    institutional = chip and any(finite(chip.get(field)) is not None for field in ("foreign_net", "trust_net", "dealer_net", "total_net"))
    results.append(field_result("chips.institutional", bool(institutional), "chip_source_missing", chip, required=False))
    results.append(field_result("chips.margin", bool(chip and any(finite((chip.get("margin") or {}).get(field)) is not None for field in ("balance", "buy", "sell"))), "non_credit_or_source_missing", chip.get("margin") if chip else None, required=False))
    results.append(field_result("chips.short", bool(chip and any(finite((chip.get("short") or {}).get(field)) is not None for field in ("balance", "buy", "sell"))), "non_credit_or_source_missing", chip.get("short") if chip else None, required=False))
    results.append(field_result("chips.day_trading", bool(chip and any(value_present(value) for value in (chip.get("day_trading") or {}).values())), "not_eligible_or_source_missing", chip.get("day_trading") if chip else None, required=False))
    results.append(field_result("news.recent", news_count > 0, "no_recent_matching_news", news_count, required=False))
    return results


def summarize_asset(asset: dict, results: list[dict]):
    required = [row for row in results if row["required"]]
    missing_required = [row for row in required if not row["available"]]
    optional_missing = [row for row in results if not row["required"] and not row["available"]]
    status = "complete" if not missing_required else "partial" if len(missing_required) < len(required) else "unresolved"
    return {
        "id": asset.get("id"),
        "symbol": asset.get("symbol"),
        "name": asset.get("name"),
        "exchange": asset.get("exchange"),
        "asset_class": asset.get("asset_class"),
        "industry": asset.get("official_industry") or asset.get("sub_industry"),
        "status": status,
        "required_count": len(required),
        "available_required_count": len(required) - len(missing_required),
        "coverage_percent": round((len(required) - len(missing_required)) / len(required) * 100, 2) if required else 100.0,
        "missing_required": [{"field": row["field"], "label": row["label"], "reason": row["reason"]} for row in missing_required],
        "missing_optional": [{"field": row["field"], "label": row["label"], "reason": row["reason"]} for row in optional_missing],
        "checks": results,
    }


def main():
    started = time.monotonic()
    assets_payload = load(ASSETS, {"assets": []})
    market_payload = load(MARKET, {"items": []})
    chips_payload = load(CHIPS, {"items": {}})
    news_payload = load(NEWS, {"items": []})
    update_status = load(UPDATE_STATUS, {"metadata": {"status": "unknown"}})
    assets = [row for row in assets_payload.get("assets") or [] if row.get("market") == "TW" and row.get("asset_class") in {"stock", "etf"}]
    if not assets:
        raise SystemExit("No Taiwan assets available for exhaustive audit.")

    quote_map, chip_map, news_counts = build_maps(market_payload, chips_payload, news_payload)
    rows = []
    field_stats = defaultdict(lambda: Counter(applicable=0, available=0, missing=0, not_applicable=0))
    reason_counts = Counter()

    for asset in sorted(assets, key=lambda row: (row.get("asset_class") or "", row.get("exchange") or "", row.get("symbol") or "")):
        key = market_key(asset)
        quote = quote_map.get(key)
        chip = chip_map.get(key)
        news_count = news_counts.get(str(asset.get("symbol") or "").upper(), 0)
        checks = audit_stock(asset, quote, chip, news_count) if asset.get("asset_class") == "stock" else audit_etf(asset, quote, chip, news_count)
        summary = summarize_asset(asset, checks)
        rows.append(summary)
        for check in checks:
            stats = field_stats[check["field"]]
            if check["required"]:
                stats["applicable"] += 1
                if check["available"]:
                    stats["available"] += 1
                else:
                    stats["missing"] += 1
                    reason_counts[check["reason"] or "unknown"] += 1
            else:
                stats["not_applicable"] += 1
                if check["available"]:
                    stats["available"] += 1

    complete = [row for row in rows if row["status"] == "complete"]
    partial = [row for row in rows if row["status"] == "partial"]
    unresolved = [row for row in rows if row["status"] == "unresolved"]
    field_summary = {}
    for field, stats in sorted(field_stats.items()):
        applicable = stats["applicable"]
        field_summary[field] = {
            "label": FIELD_LABELS.get(field, field),
            **dict(stats),
            "coverage_percent": round(stats["available"] / applicable * 100, 2) if applicable else None,
        }

    elapsed = time.monotonic() - started
    payload = {
        "metadata": {
            "version": "v11.2.8",
            "updated_at": NOW.isoformat(timespec="seconds"),
            "source": "Exhaustive full-universe audit of generated TW stock and ETF data",
            "audit_mode": "all-assets-no-sampling",
            "elapsed_seconds": round(elapsed, 3),
            "asset_payload_updated_at": (assets_payload.get("metadata") or {}).get("updated_at"),
            "market_payload_updated_at": (market_payload.get("metadata") or {}).get("updated_at"),
            "chips_payload_updated_at": (chips_payload.get("metadata") or {}).get("updated_at"),
            "news_payload_updated_at": (news_payload.get("metadata") or {}).get("updated_at"),
            "asset_update_status": (update_status.get("metadata") or {}).get("status"),
            "asset_update_message": (update_status.get("metadata") or {}).get("message"),
        },
        "summary": {
            "audited_assets": len(rows),
            "stock_count": sum(1 for row in rows if row["asset_class"] == "stock"),
            "etf_count": sum(1 for row in rows if row["asset_class"] == "etf"),
            "complete": len(complete),
            "partial": len(partial),
            "unresolved": len(unresolved),
            "audit_coverage_percent": 100.0,
            "field_stats": field_summary,
            "reason_counts": dict(reason_counts.most_common()),
        },
        "assets": rows,
        "unresolved_assets": [row for row in rows if row["missing_required"]],
    }
    if payload["summary"]["audited_assets"] != len(assets):
        raise SystemExit("Audit did not cover every Taiwan asset.")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SEED.write_text("window.__ASSET_AUDIT_SEED__ = " + json.dumps(payload, ensure_ascii=False) + ";\n", encoding="utf-8")
    with FAILURES_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "symbol", "name", "asset_class", "exchange", "status",
            "coverage_percent", "missing_fields", "missing_reasons",
        ])
        writer.writeheader()
        for row in payload["unresolved_assets"]:
            writer.writerow({
                "symbol": row.get("symbol"),
                "name": row.get("name"),
                "asset_class": row.get("asset_class"),
                "exchange": row.get("exchange"),
                "status": row.get("status"),
                "coverage_percent": row.get("coverage_percent"),
                "missing_fields": " | ".join(item.get("label") or item.get("field") or "" for item in row.get("missing_required") or []),
                "missing_reasons": " | ".join(item.get("reason") or "" for item in row.get("missing_required") or []),
            })
    print(json.dumps({
        "audited": len(rows),
        "complete": len(complete),
        "partial": len(partial),
        "unresolved": len(unresolved),
        "seconds": round(elapsed, 3),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
