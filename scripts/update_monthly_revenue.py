#!/usr/bin/env python3
"""Update the isolated monthly-revenue channel for v11.4.3.

Latest official OpenAPI rows and a small rolling MOPS history batch are merged
without touching the asset master. A failed month never clears successful data.
"""
from __future__ import annotations

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import DATA, NOW, read_json, write_payload
from update_assets import (
    MONTHLY_REVENUE_SOURCES,
    MOPS_REVENUE_ARCHIVES,
    fetch_mops_revenue_month,
    fetch_rows,
    merge_period_rows,
    pick,
    recent_year_months,
    symbol_of,
    year_month_of,
)

VERSION = "v11.4.3"
HISTORY_MONTHS = 60
BATCH_MONTHS = 4


def main() -> None:
    old = read_json(DATA / "monthly-revenue.json", {"items": {}})
    state_path = DATA / "monthly-revenue-state.json"
    state = read_json(state_path, {"metadata": {"version": VERSION, "month_cursor": 0}})
    meta = state.setdefault("metadata", {})
    existing = old.get("items") if isinstance(old.get("items"), dict) else {}
    updates: dict[str, list[dict]] = defaultdict(list)
    health: list[dict] = []

    current_success = 0
    for source_name, url, _exchange in MONTHLY_REVENUE_SOURCES:
        rows = fetch_rows(source_name, url, health)
        if rows:
            current_success += 1
        for row in rows:
            symbol = symbol_of(row)
            year, month = year_month_of(row)
            if not symbol or not year or not month or not 1 <= month <= 12:
                continue
            revenue = pick(row, "當月營收", "當月營業收入淨額", "本月營業收入淨額", "CurrentMonthRevenue", "Revenue")
            if revenue is None:
                continue
            updates[symbol].append({
                "period": f"{year:04d}-{month:02d}",
                "revenue": revenue,
                "mom": pick(row, "上月比較增減(%)", "上月比較增減％", "月增率", "MoM"),
                "yoy": pick(row, "去年同月增減(%)", "去年同月增減％", "年增率", "YoY"),
                "cumulative_revenue": pick(row, "當月累計營收", "累計營業收入淨額", "累計營收", "CumulativeRevenue"),
                "cumulative_yoy": pick(row, "前期比較增減(%)", "累計年增率", "CumulativeYoY"),
                "unit": "千元",
                "source": source_name,
                "source_updated_at": NOW.isoformat(timespec="seconds"),
            })

    months = recent_year_months(HISTORY_MONTHS)
    cursor = int(meta.get("month_cursor") or 0) % len(months)
    selected = [months[(cursor + offset) % len(months)] for offset in range(BATCH_MONTHS)]
    jobs = [(source_name, market_path, year, month) for year, month in selected for source_name, market_path in MOPS_REVENUE_ARCHIVES]
    history_success = 0
    failed_month_markets: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(fetch_mops_revenue_month, *job): job for job in jobs}
        for future in as_completed(futures):
            source_name, parsed, error = future.result()
            job = futures[future]
            if error:
                failed_month_markets.append(f"{job[2]:04d}-{job[3]:02d}:{job[1]}")
                health.append({"name": source_name, "status": "warning", "error": error})
                continue
            history_success += 1
            health.append({"name": source_name, "status": "ok", "period": f"{job[2]:04d}-{job[3]:02d}", "market": job[1], "companies": len(parsed)})
            for symbol, rows in parsed.items():
                updates[symbol].extend(rows)

    # Progress always advances. Failed month/market pairs are reported and will
    # be retried on the next full cycle instead of blocking every other month.
    meta["month_cursor"] = (cursor + BATCH_MONTHS) % len(months)
    meta["last_batch_months"] = [f"{year:04d}-{month:02d}" for year, month in selected]
    meta["last_batch_requested"] = len(jobs)
    meta["last_batch_success"] = history_success
    meta["last_batch_failures"] = failed_month_markets
    meta["version"] = VERSION
    meta["updated_at"] = NOW.isoformat(timespec="seconds")

    merged: dict[str, list[dict]] = {}
    all_symbols = set(existing) | set(updates)
    for symbol in all_symbols:
        rows = merge_period_rows(existing.get(symbol, []), updates.get(symbol, []), "period", HISTORY_MONTHS)
        rows = [row for row in rows if row.get("period") and row.get("revenue") is not None]
        if rows:
            merged[symbol] = rows

    fresh_records = sum(len(rows) for rows in updates.values())
    total_records = sum(len(rows) for rows in merged.values())
    if current_success and history_success == len(jobs):
        status = "ok"
    elif fresh_records:
        status = "partial"
    elif merged:
        status = "fallback"
    else:
        status = "warning"

    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": status,
            "symbol_count": len(merged),
            "record_count": total_records,
            "fresh_record_count": fresh_records,
            "history_months": HISTORY_MONTHS,
            "batch_months": BATCH_MONTHS,
            "history_requested": len(jobs),
            "history_success": history_success,
            "next_month_cursor": meta["month_cursor"],
            "note": "Monthly revenue is an isolated channel. Each run advances a small history batch and preserves prior successful months.",
        },
        "sources": health,
        "items": merged,
    }
    write_payload("monthly-revenue.json", "__MONTHLY_REVENUE_SEED__", payload)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(payload["metadata"])


if __name__ == "__main__":
    main()
