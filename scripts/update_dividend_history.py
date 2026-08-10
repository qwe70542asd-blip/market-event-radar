#!/usr/bin/env python3
"""Update the isolated dividend-history channel for v11.4.37.

Current official dividend rows are merged with a bounded MOPS company batch.
The main cursor advances even when individual companies fail; failures enter a
retry queue and cannot permanently block the rest of the market.
"""
from __future__ import annotations

import json
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from common import DATA, NOW, read_json, write_payload
from update_assets import (
    DIVIDEND_SOURCES,
    dividend_year_label,
    exact_row_value,
    fetch_mops_dividend_history,
    fetch_rows,
    format_date,
    merge_period_rows,
    sum_exact_numbers,
    symbol_of,
    text_value,
)

VERSION = "v11.4.37"
NEW_BATCH = 15
RETRY_BATCH = 5
MAX_RECORDS = 40


def current_row(row: dict, source_name: str) -> tuple[str, dict] | None:
    symbol = symbol_of(row)
    if not symbol:
        return None
    year_raw = exact_row_value(row, ("股利年度", "年度", "Year"))
    period_raw = exact_row_value(row, ("股利所屬期間", "股利所屬年(季)度", "Period"))
    cash = sum_exact_numbers(row, (
        "股東配發-盈餘分配之現金股利(元/股)",
        "股東配發-法定盈餘公積發放之現金(元/股)",
        "股東配發-資本公積發放之現金(元/股)",
        "盈餘分配之現金股利(元/股)",
        "法定盈餘公積發放之現金(元/股)",
        "資本公積發放之現金(元/股)",
    ))
    stock = sum_exact_numbers(row, (
        "股東配發-盈餘轉增資配股(元/股)",
        "股東配發-法定盈餘公積轉增資配股(元/股)",
        "股東配發-資本公積轉增資配股(元/股)",
        "盈餘轉增資配股(元/股)",
        "法定盈餘公積轉增資配股(元/股)",
        "資本公積轉增資配股(元/股)",
    ))
    period = dividend_year_label(year_raw, period_raw)
    if not period or (cash is None and stock is None):
        return None
    return symbol, {
        "period": period,
        "period_raw": str(period_raw or "").strip() or None,
        "term": str(exact_row_value(row, ("期別",)) or "").strip() or None,
        "cash": cash,
        "stock": stock,
        "board_date": format_date(exact_row_value(row, ("董事會（擬議）股利分派日", "董事會決議日", "董事會日期"))),
        "shareholder_meeting_date": format_date(exact_row_value(row, ("股東會日期",))),
        "ex_date": format_date(exact_row_value(row, ("除權息交易日", "除息日", "除權日", "ExDate"))),
        "payment_date": format_date(exact_row_value(row, ("現金股利發放日", "發放日", "PaymentDate"))),
        "record_date": format_date(exact_row_value(row, ("除權息基準日", "基準日", "RecordDate"))),
        "source": source_name,
        "url": text_value(row, "網址", "公告網址", "URL") or None,
        "source_updated_at": NOW.isoformat(timespec="seconds"),
    }


def main() -> None:
    old = read_json(DATA / "dividend-history.json", {"items": {}})
    state_path = DATA / "dividend-history-state.json"
    state = read_json(state_path, {"metadata": {"version": VERSION, "cursor": 0, "retry_symbols": []}})
    meta = state.setdefault("metadata", {})
    existing = old.get("items") if isinstance(old.get("items"), dict) else {}
    updates: dict[str, list[dict]] = defaultdict(list)
    health: list[dict] = []

    current_success = 0
    for source_name, url, _exchange in DIVIDEND_SOURCES:
        rows = fetch_rows(source_name, url, health)
        if rows:
            current_success += 1
        for row in rows:
            parsed = current_row(row, source_name)
            if parsed:
                symbol, values = parsed
                updates[symbol].append(values)

    assets = read_json(DATA / "assets.json", {"assets": []})
    symbols = sorted({str(row.get("symbol") or "") for row in assets.get("assets", []) if row.get("market") == "TW" and row.get("asset_class") == "stock" and row.get("symbol")})
    cursor = int(meta.get("cursor") or 0)
    if symbols:
        cursor %= len(symbols)
    retry = [str(value) for value in meta.get("retry_symbols", []) if str(value) in symbols]
    retry_targets = retry[:RETRY_BATCH]
    new_targets = [symbols[(cursor + offset) % len(symbols)] for offset in range(min(NEW_BATCH, len(symbols)))] if symbols else []
    targets = list(dict.fromkeys(retry_targets + new_targets))

    successful: set[str] = set()
    failed: list[str] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(fetch_mops_dividend_history, symbol): symbol for symbol in targets}
        for future in as_completed(futures):
            symbol, rows, error = future.result()
            if rows:
                updates[symbol].extend(rows)
                successful.add(symbol)
                health.append({"name": "MOPS dividend history", "status": "ok", "symbol": symbol, "records": len(rows)})
            else:
                failed.append(symbol)
                health.append({"name": "MOPS dividend history", "status": "warning", "symbol": symbol, "error": error or "no rows parsed"})

    # Advance through new symbols regardless of individual failures. Failed
    # symbols remain in a separate bounded retry queue.
    if symbols:
        meta["cursor"] = (cursor + len(new_targets)) % len(symbols)
    remaining_retry = [symbol for symbol in retry if symbol not in successful and symbol not in retry_targets]
    meta["retry_symbols"] = list(dict.fromkeys(remaining_retry + failed))[:300]
    meta["last_targets"] = targets
    meta["last_successful_symbols"] = sorted(successful)
    meta["last_failed_symbols"] = failed
    meta["version"] = VERSION
    meta["updated_at"] = NOW.isoformat(timespec="seconds")

    merged: dict[str, list[dict]] = {}
    for symbol in set(existing) | set(updates):
        rows = merge_period_rows(existing.get(symbol, []), updates.get(symbol, []), "period", MAX_RECORDS)
        rows = [row for row in rows if row.get("period") and (row.get("cash") is not None or row.get("stock") is not None)]
        if rows:
            merged[symbol] = rows

    fresh_records = sum(len(rows) for rows in updates.values())
    total_records = sum(len(rows) for rows in merged.values())
    if current_success and targets and len(successful) == len(targets):
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
            "batch_size": len(targets),
            "batch_success": len(successful),
            "batch_failures": len(failed),
            "next_cursor": meta.get("cursor", 0),
            "retry_queue_size": len(meta.get("retry_symbols", [])),
            "note": "Dividend history is an isolated channel. The main cursor always advances while failed companies enter a separate retry queue.",
        },
        "sources": health,
        "items": merged,
    }
    write_payload("dividend-history.json", "__DIVIDEND_HISTORY_SEED__", payload)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(payload["metadata"])


if __name__ == "__main__":
    main()
