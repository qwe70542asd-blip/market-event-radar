#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_events as ev
import update_tw_chips as chips

ENDPOINTS = {
    "day_trade": chips.TPEX_DAY_TRADE,
    "exdiv_history": ev.TPEX_EXDIV_HISTORY_URL,
    "dividend_plan": ev.TPEX_DIVIDEND_PLAN_URL,
    "exdiv_prepost": ev.TPEX_EXDIV_URL,
    "material": ev.TPEX_MATERIAL_URL,
}

SAFE_RESPONSE_HEADERS = (
    "content-type",
    "content-length",
    "server",
    "date",
    "cache-control",
    "etag",
    "last-modified",
    "cf-ray",
)


def short(value: Any, limit: int = 240) -> Any:
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = str(value)
    return text if len(text) <= limit else text[:limit] + "…"


def normalize_key(value: Any) -> str:
    try:
        return chips.normalized_key(value)
    except Exception:
        return "".join(ch.lower() for ch in str(value) if ch.isalnum())


def rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "aaData", "rows", "items", "result", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def fetch_with_attempts(session: requests.Session, url: str, attempts: int = 3) -> dict[str, Any]:
    report: dict[str, Any] = {"url": url, "attempts": []}
    final_payload: Any = None
    final_text = ""
    for attempt in range(1, attempts + 1):
        started = time.monotonic()
        entry: dict[str, Any] = {"attempt": attempt}
        try:
            response = session.get(url, timeout=(10, 25))
            elapsed_ms = round((time.monotonic() - started) * 1000, 1)
            entry.update({
                "status": response.status_code,
                "elapsed_ms": elapsed_ms,
                "bytes": len(response.content),
                "headers": {key: response.headers.get(key) for key in SAFE_RESPONSE_HEADERS if response.headers.get(key) is not None},
            })
            final_text = response.text
            if response.ok:
                try:
                    final_payload = response.json()
                    entry["json_ok"] = True
                    entry["top_level_type"] = type(final_payload).__name__
                except Exception as exc:
                    entry["json_ok"] = False
                    entry["json_error"] = f"{type(exc).__name__}: {exc}"[:300]
                    entry["body_prefix"] = short(response.text, 600)
            else:
                entry["json_ok"] = False
                entry["body_prefix"] = short(response.text, 600)
        except Exception as exc:
            entry.update({
                "exception": f"{type(exc).__name__}: {exc}"[:400],
                "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
            })
        report["attempts"].append(entry)
        if final_payload is not None:
            break
        if attempt < attempts:
            time.sleep(attempt * 2)

    report["success"] = final_payload is not None
    if final_payload is not None:
        report["payload"] = final_payload
    elif final_text:
        report["body_prefix"] = short(final_text, 1000)
    return report


def inspect_row(row: dict[str, Any], index: int) -> dict[str, Any]:
    date_candidates = []
    for key, value in row.items():
        chip_date = chips.date_value(value)
        event_date = None
        try:
            parsed = ev.first_market_date(value)
            event_date = parsed.isoformat() if parsed else None
        except Exception:
            event_date = None
        if chip_date or event_date or "日期" in str(key) or "date" in normalize_key(key):
            date_candidates.append({
                "key": str(key),
                "value": short(value),
                "chip_date_value": chip_date,
                "event_first_market_date": event_date,
            })

    return {
        "index": index,
        "keys": [str(key) for key in row.keys()],
        "normalized_keys": {str(key): normalize_key(key) for key in row.keys()},
        "sample": {str(key): short(value) for key, value in row.items()},
        "current_chip_row_date": chips.row_date(row),
        "current_chip_valid_date": chips.valid_chip_date(chips.row_date(row)),
        "date_candidates": date_candidates,
    }


def match_field(row: dict[str, Any], aliases: tuple[str, ...], semantic_any: tuple[str, ...] = (), exclude: tuple[str, ...] = ()) -> dict[str, Any]:
    key, value = chips.field_pair(row, *aliases)
    mode = "alias" if value is not None else None
    if value is None and semantic_any:
        key, value = chips.semantic_pair(row, any_terms=semantic_any, exclude_terms=exclude)
        if value is not None:
            mode = "semantic"
    return {"mode": mode, "key": key, "value": short(value)}


def diagnose_day_trade(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid_dates = [chips.valid_chip_date(chips.row_date(row)) for row in rows]
    valid_dates = [value for value in valid_dates if value]
    ceiling = max(valid_dates) if valid_dates else chips.valid_chip_date(chips.NOW.date().isoformat())
    market, traded = chips.parse_tpex_day_trade_market(rows, ceiling)

    row_diagnostics = []
    for index, row in enumerate(rows[:10]):
        explicit = chips.valid_chip_date(chips.row_date(row))
        selected = explicit or (ceiling if len(rows) == 1 else None)
        row_diagnostics.append({
            "index": index,
            "explicit_date": explicit,
            "ceiling": ceiling,
            "row_count": len(rows),
            "fallback_allowed_by_current_parser": len(rows) == 1,
            "selected_date_by_current_parser": selected,
            "dropped_before_field_parse": not bool(selected) or bool(ceiling and selected and selected > ceiling),
            "volume_match": match_field(
                row,
                ("DayTradingVolume", "當日沖銷交易總成交股數", "當日沖銷交易成交股數", "現股當沖成交股數", "TotalIntradayTradingVolume", "IntradayTradingVolume"),
                semantic_any=("當沖成交股數", "沖銷成交股數", "intradaytradingvolume", "daytradingvolume"),
                exclude=("比重", "比例", "ratio"),
            ),
            "buy_match": match_field(
                row,
                ("DayTradingValueOfBuys", "當日沖銷交易總買進成交金額", "當日沖銷交易買進成交金額", "現股當沖買進成交金額", "TotalIntradayTradingBuyAmount", "IntradayTradingBuyAmount"),
                semantic_any=("當沖買進成交金額", "沖銷買進成交金額", "intradaytradingbuyamount", "daytradingvalueofbuys"),
                exclude=("比重", "比例", "ratio"),
            ),
            "sell_match": match_field(
                row,
                ("DayTradingValueOfSells", "當日沖銷交易總賣出成交金額", "當日沖銷交易賣出成交金額", "現股當沖賣出成交金額", "TotalIntradayTradingSellAmount", "IntradayTradingSellAmount"),
                semantic_any=("當沖賣出成交金額", "沖銷賣出成交金額", "intradaytradingsellamount", "daytradingvalueofsells"),
                exclude=("比重", "比例", "ratio"),
            ),
        })

    return {
        "row_count": len(rows),
        "ceiling": ceiling,
        "parsed_market": market,
        "parsed_traded_date": traded,
        "parsed_field_count": len(market),
        "rows": row_diagnostics,
    }


def diagnose_event_parser(name: str, payload: Any, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if name == "exdiv_history":
        parsed = ev.parse_tpex_exdiv_history_payload(payload)
    elif name == "dividend_plan":
        parsed = ev.parse_dividend_plans(payload, "TPEX", ev.TPEX_DIVIDEND_PLAN_URL, "tpex-dividend-plan")
    elif name == "exdiv_prepost":
        # The production helper fetch_tpex_exdiv performs its own HTTP request.
        # Keep this diagnostic read-only and deterministic against the payload
        # already captured above; raw schema/date inspection is the evidence we
        # need here, so do not issue a duplicate parser-side request.
        return {"row_count": len(rows), "parser_note": "raw-schema-only; production helper would refetch endpoint"}
    elif name == "material":
        try:
            parsed = ev.parse_material(payload, "TPEX", ev.TPEX_MATERIAL_URL, "tpex-material")
        except Exception as exc:
            return {"parser_exception": f"{type(exc).__name__}: {exc}"[:500]}
    else:
        parsed = []
    return {
        "row_count": len(rows),
        "parsed_count": len(parsed),
        "parsed_samples": parsed[:3],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture TPEx live HTTP/schema/parser diagnostics without changing production parsers.")
    parser.add_argument("--output", default="artifacts/tpex-live-diagnostic.json")
    args = parser.parse_args()

    session = requests.Session()
    headers = dict(getattr(ev, "HEADERS", {}) or {})
    headers.setdefault("User-Agent", "Mozilla/5.0 (compatible; market-event-radar-diagnostic/11.4.58)")
    headers.setdefault("Accept", "application/json,text/plain,*/*")
    session.headers.update(headers)

    report: dict[str, Any] = {
        "diagnostic_version": "v11.4.58-tpex-stable-schema-1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "Read-only TPEx live source diagnosis. No parser or site behavior is modified.",
        "endpoints": {},
    }

    for name, url in ENDPOINTS.items():
        print(f"\n=== {name} ===")
        fetched = fetch_with_attempts(session, url)
        endpoint_report: dict[str, Any] = {
            "url": url,
            "attempts": fetched["attempts"],
            "success": fetched["success"],
        }
        if not fetched["success"]:
            endpoint_report["body_prefix"] = fetched.get("body_prefix")
            report["endpoints"][name] = endpoint_report
            last = fetched["attempts"][-1] if fetched["attempts"] else {}
            print(f"HTTP/JSON unavailable after {len(fetched['attempts'])} attempts; last={last.get('status') or last.get('exception')}")
            continue

        payload = fetched["payload"]
        rows = rows_from_payload(payload)
        endpoint_report.update({
            "top_level_type": type(payload).__name__,
            "row_count": len(rows),
            "top_level_keys": list(payload.keys()) if isinstance(payload, dict) else None,
            "row_schema_samples": [inspect_row(row, i) for i, row in enumerate(rows[:5])],
        })

        if name == "day_trade":
            endpoint_report["parser_diagnostic"] = diagnose_day_trade(rows)
        else:
            endpoint_report["parser_diagnostic"] = diagnose_event_parser(name, payload, rows)

        report["endpoints"][name] = endpoint_report
        print(f"status={fetched['attempts'][-1].get('status')} rows={len(rows)}")
        if rows:
            print("keys[0]=", list(rows[0].keys()))
            print("row[0]=", json.dumps({k: short(v) for k, v in rows[0].items()}, ensure_ascii=False))
        diag = endpoint_report.get("parser_diagnostic", {})
        if name == "day_trade":
            print("day_trade_parser=", json.dumps({
                "ceiling": diag.get("ceiling"),
                "parsed_traded_date": diag.get("parsed_traded_date"),
                "parsed_market": diag.get("parsed_market"),
                "first_row_reason": (diag.get("rows") or [None])[0],
            }, ensure_ascii=False))
        else:
            print("parsed_count=", diag.get("parsed_count"))

    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"\nDiagnostic artifact written: {output}")
    print("This diagnostic intentionally exits 0 even when TPEx returns 4xx/5xx; HTTP failures are evidence, not test failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
