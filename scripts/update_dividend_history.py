#!/usr/bin/env python3
"""Update the isolated dividend-history channel for v11.4.45.

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

VERSION = "v11.4.45"
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
        "board_date": format_date(exact_row_value(row, ("董事會（擬議）股利分派日", "董事會決議通過股利分派日", "董事會決議日", "董事會日期"))),
        "shareholder_meeting_date": format_date(exact_row_value(row, ("股東會日期", "股東會日期配盈餘/待彌補虧損(元)"))),
        "ex_date": format_date(exact_row_value(row, ("除權息交易日", "除息日", "除權日", "ExDate"))),
        "payment_date": format_date(exact_row_value(row, ("現金股利發放日", "發放日", "PaymentDate"))),
        "record_date": format_date(exact_row_value(row, ("除權息基準日", "基準日", "RecordDate"))),
        "source": source_name,
        "url": text_value(row, "網址", "公告網址", "URL") or None,
        "source_updated_at": NOW.isoformat(timespec="seconds"),
    }


def dividend_source_priority(row: dict) -> int:
    source=str(row.get("source") or "").lower()
    if source.startswith("twse") or source.startswith("tpex") or source.startswith("mops"): return 3
    if row.get("source_level") == "reference" or "yahoo" in source: return 1
    return 2

def dividend_record_key(row: dict) -> str:
    ex_date=str(row.get("ex_date") or row.get("ex_dividend_date") or row.get("date") or "").strip()
    if ex_date:return f"ex:{ex_date}"
    period=str(row.get("period") or row.get("year") or "").strip()
    term=str(row.get("term") or "").strip()
    return f"period:{period}|term:{term}" if period else ""

def _same_period_candidates(records: list[dict], row: dict) -> list[int]:
    period=str(row.get("period") or row.get("year") or "").strip()
    term=str(row.get("term") or "").strip()
    if not period:return []
    out=[]
    for index,current in enumerate(records):
        if str(current.get("period") or current.get("year") or "").strip()!=period:continue
        current_term=str(current.get("term") or "").strip()
        if term and current_term and term!=current_term:continue
        out.append(index)
    return out

def merge_dividend_records(existing_rows: list[dict], update_rows: list[dict], limit: int = MAX_RECORDS) -> list[dict]:
    # Merge exact ex-dates first because Yahoo uses ex-date year as its period while
    # official sources may use a fiscal/dividend period.  When one side lacks an
    # ex-date, a period fallback is allowed only if that period identifies exactly
    # one record; this preserves semiannual/multiple distributions in the same year.
    records: list[dict] = []
    for row in sorted((r for r in [*(existing_rows or []),*(update_rows or [])] if isinstance(r,dict)), key=dividend_source_priority):
        if not dividend_record_key(row):continue
        ex_date=str(row.get("ex_date") or row.get("ex_dividend_date") or row.get("date") or "").strip()
        exact=[i for i,current in enumerate(records) if ex_date and str(current.get("ex_date") or current.get("ex_dividend_date") or current.get("date") or "").strip()==ex_date]
        if exact:
            matches=exact
        elif ex_date:
            # Different known ex-dates are distinct distributions.  Period
            # fallback is only safe against a candidate whose ex-date is absent.
            matches=[i for i in _same_period_candidates(records,row) if not str(records[i].get("ex_date") or records[i].get("ex_dividend_date") or records[i].get("date") or "").strip()]
        else:
            matches=_same_period_candidates(records,row)
        target=matches[0] if len(matches)==1 else None
        if target is None:
            records.append(dict(row));continue
        current=records[target]
        if dividend_source_priority(row) < dividend_source_priority(current):continue
        upgraded=dividend_source_priority(row) > dividend_source_priority(current)
        merged={**current,**{k:v for k,v in row.items() if v is not None}}
        if upgraded and row.get("source_level") is None:
            merged.pop("source_level",None);merged.pop("period_basis",None)
        records[target]=merged
    def sort_key(row:dict)->tuple[str,str]:
        return (str(row.get("ex_date") or row.get("ex_dividend_date") or row.get("date") or ""),str(row.get("period") or row.get("year") or ""))
    return sorted(records,key=sort_key,reverse=True)[:limit]


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

    # Yahoo dividend events are reference-only historical backfill.  They never
    # overwrite a current official TWSE/TPEx row for the same period.
    yahoo_payload = read_json(DATA / "yahoo-details.json", {"items": {}})
    yahoo_items = yahoo_payload.get("items") if isinstance(yahoo_payload.get("items"), dict) else {}
    yahoo_reference_symbols: set[str] = set()
    yahoo_reference_records = 0
    for symbol, item in yahoo_items.items():
        if not isinstance(item, dict):
            continue
        for row in item.get("dividends") or []:
            if not isinstance(row, dict):
                continue
            period = str(row.get("period") or row.get("year") or "").strip()
            cash = row.get("cash_dividend") if row.get("cash_dividend") is not None else row.get("cash")
            if not period or cash is None:
                continue
            updates[str(symbol).upper()].append({
                "period": period, "period_basis": "ex_date_year", "cash": cash, "stock": row.get("stock_dividend") or row.get("stock"),
                "ex_date": row.get("ex_date") or row.get("date"), "payment_date": row.get("payment_date"),
                "source": "Yahoo Finance dividend event", "source_level": "reference",
                "url": row.get("url"), "source_updated_at": row.get("source_updated_at") or item.get("updated_at") or (yahoo_payload.get("metadata") or {}).get("updated_at"),
            })
            yahoo_reference_symbols.add(str(symbol).upper()); yahoo_reference_records += 1
    if yahoo_reference_records:
        health.append({"name":"Yahoo dividend history reference","status":"ok","symbols":len(yahoo_reference_symbols),"records":yahoo_reference_records})

    assets = read_json(DATA / "assets.json", {"assets": []})
    symbols = sorted({str(row.get("symbol") or "") for row in assets.get("assets", []) if row.get("market") == "TW" and row.get("asset_class") == "stock" and row.get("symbol")})
    cursor = int(meta.get("cursor") or 0)
    if symbols:
        cursor %= len(symbols)
    retry = [str(value) for value in meta.get("retry_symbols", []) if str(value) in symbols]
    circuit_remaining = max(0, int(meta.get("mops_circuit_remaining") or 0))
    retry_targets = retry[:RETRY_BATCH] if circuit_remaining == 0 else []
    new_targets = [symbols[(cursor + offset) % len(symbols)] for offset in range(min(NEW_BATCH, len(symbols)))] if symbols and circuit_remaining == 0 else []
    targets = list(dict.fromkeys(retry_targets + new_targets))

    successful: set[str] = set()
    failed: list[str] = []
    mops_errors: list[dict[str, str]] = []
    if circuit_remaining:
        meta["mops_circuit_remaining"] = circuit_remaining - 1
        health.append({
            "name": "MOPS dividend history", "status": "degraded", "mode": "circuit-open",
            "message": "Previous batch was broadly unavailable; this run skips MOPS to avoid repeated requests.",
            "remaining_runs": circuit_remaining - 1,
        })
    else:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {pool.submit(fetch_mops_dividend_history, symbol): symbol for symbol in targets}
            for future in as_completed(futures):
                symbol, rows, error = future.result()
                if rows:
                    updates[symbol].extend(rows)
                    successful.add(symbol)
                else:
                    failed.append(symbol)
                    mops_errors.append({"symbol": symbol, "error": error or "no rows parsed"})
        if targets:
            failure_ratio = len(failed) / len(targets)
            if failure_ratio >= .9 and len(targets) >= 5:
                meta["mops_circuit_remaining"] = 2
            else:
                meta["mops_circuit_remaining"] = 0
            health.append({
                "name": "MOPS dividend history",
                "status": "ok" if not failed else "degraded" if successful else "warning",
                "attempted": len(targets), "success": len(successful), "failures": len(failed),
                "failure_ratio": round(failure_ratio, 4),
                "sample_errors": mops_errors[:5],
            })

    # Advance through new symbols regardless of individual failures. Failed
    # symbols remain in a separate bounded retry queue.
    if symbols and new_targets:
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
        rows=merge_dividend_records(existing.get(symbol, []), updates.get(symbol, []), MAX_RECORDS)
        rows = [row for row in rows if row.get("period") and (row.get("cash") is not None or row.get("stock") is not None)]
        if rows: merged[symbol] = rows

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

    circuit_after = int(meta.get("mops_circuit_remaining") or 0)
    if circuit_after > 0:
        mops_status = "circuit-open"
    elif circuit_remaining > 0 and not targets:
        mops_status = "cooldown-complete"
    elif targets and not failed:
        mops_status = "ok"
    elif successful:
        mops_status = "degraded"
    elif targets:
        mops_status = "unavailable"
    else:
        mops_status = "idle"

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
            "mops_circuit_remaining": circuit_after,
            "mops_status": mops_status,
            "reference_symbol_count": len(yahoo_reference_symbols),
            "reference_record_count": yahoo_reference_records,
            "note": "Official TWSE/TPEx rows stay primary; Yahoo dividend events backfill history as reference-only data. MOPS is best-effort with a circuit breaker when broad failures occur.",
        },
        "sources": health,
        "items": merged,
    }
    write_payload("dividend-history.json", "__DIVIDEND_HISTORY_SEED__", payload)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(payload["metadata"])


if __name__ == "__main__":
    main()
