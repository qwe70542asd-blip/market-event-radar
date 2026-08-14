#!/usr/bin/env python3
"""Reachability-aware TPEx live contract verification for v11.4.45.

Deterministic application tests must not fail because an external official host
returns a transient 5xx.  This gate therefore distinguishes:

* unavailable: network/HTTP/JSON failure -> warning, release continues quickly;
* healthy zero: reachable schema but no row in the monitored date window -> pass;
* contract failure: reachable JSON rows that should parse but do not -> fail.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import requests
import update_events as ev
import update_tw_chips as chips

VERSION = "v11.4.45"


@dataclass
class FetchResult:
    ok: bool
    payload: Any = None
    error: str = ""
    status_code: int | None = None


def fetch_json(session: requests.Session, url: str, *, attempts: int = 2, timeout: int = 12) -> FetchResult:
    last_error = "request failed"
    last_status: int | None = None
    for attempt in range(attempts):
        try:
            response = session.get(url, headers=ev.HEADERS, timeout=timeout)
            last_status = response.status_code
            response.raise_for_status()
            try:
                return FetchResult(True, response.json(), status_code=response.status_code)
            except json.JSONDecodeError as exc:
                last_error = f"HTTP {response.status_code} returned non-JSON: {exc}"
        except requests.RequestException as exc:
            last_error = str(exc)
        if attempt + 1 < attempts:
            time.sleep(1.0 + attempt)
    return FetchResult(False, error=last_error, status_code=last_status)



def chip_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    source_date = chips.date_value(payload.get("date") or payload.get("Date") or payload.get("tradeDate") or payload.get("stat") or "")
    if isinstance(payload.get("data"), list) and payload.get("fields"):
        fields = payload.get("fields") or []
        rows = [dict(zip(fields, row)) for row in payload.get("data") or [] if isinstance(row, list)]
        return [{**row, "_source_date": source_date} if source_date else row for row in rows]
    for key in ("data", "items", "results"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [{**row, "_source_date": source_date} if source_date else row for row in rows if isinstance(row, dict)]
    return []

def contract_fail(message: str) -> None:
    raise RuntimeError(message)


def check_exdiv(session: requests.Session) -> tuple[str, str]:
    fetched = fetch_json(session, ev.TPEX_EXDIV_HISTORY_URL)
    if not fetched.ok:
        return "unavailable", f"TPEx ex-dividend unavailable: {fetched.error}"
    rows = ev.payload_dict_rows(fetched.payload)
    parsed = ev.parse_tpex_exdiv_history_payload(fetched.payload)
    eligible = 0
    for row in rows:
        raw = ev.first_value(row, [
            "ExRrightsExDividendDate", "ExRightsExDividendDate", "ExDate", "Date",
            "資料日期", "交易日期", "除權息日期", "除權除息日期", "除權息交易日",
        ]) or ev.semantic_field(row, all_terms=("日期",), any_terms=("除權", "除息", "權息"))
        day = ev.first_market_date(raw)
        if day and ev.ARCHIVE_START <= day <= ev.NOW.date():
            eligible += 1
    if rows and eligible and not parsed:
        keys = sorted({str(key) for row in rows[:3] for key in row})
        contract_fail(f"TPEx ex-dividend rows={len(rows)} eligible={eligible} parsed=0 keys={keys}")
    return "ok", f"TPEx ex-dividend: rows={len(rows)} eligible={eligible} parsed={len(parsed)}"


def check_dividend_plans(session: requests.Session) -> tuple[str, str]:
    fetched = fetch_json(session, ev.TPEX_DIVIDEND_PLAN_URL)
    if not fetched.ok:
        return "unavailable", f"TPEx dividend-plan unavailable: {fetched.error}"
    rows = ev.payload_dict_rows(fetched.payload)
    eligible = ev.dividend_plan_eligible_count(fetched.payload)
    parsed = ev.parse_dividend_plans(fetched.payload, "TPEX", ev.TPEX_DIVIDEND_PLAN_URL, "tpex-dividend-plan")
    if rows and eligible and not parsed:
        keys = sorted({str(key) for row in rows[:3] for key in row})
        contract_fail(f"TPEx dividend-plan rows={len(rows)} eligible={eligible} parsed=0 keys={keys}")
    return "ok", f"TPEx dividend-plan: rows={len(rows)} eligible={eligible} parsed={len(parsed)}"


def check_day_trade(session: requests.Session) -> tuple[str, str]:
    fetched = fetch_json(session, chips.TPEX_DAY_TRADE)
    if not fetched.ok:
        return "unavailable", f"TPEx day-trading unavailable: {fetched.error}"
    rows = chip_rows(fetched.payload)
    valid_dates = [chips.valid_chip_date(chips.row_date(row)) for row in rows]
    valid_dates = [value for value in valid_dates if value]
    ceiling = max(valid_dates) if valid_dates else chips.valid_chip_date(chips.NOW.date().isoformat())
    market, traded = chips.parse_tpex_day_trade_market(rows, ceiling)
    required = {"volume", "buy_amount", "sell_amount"}
    if rows and (not market or not required.issubset(market)):
        keys = sorted({str(key) for row in rows[:3] for key in row})
        contract_fail(
            f"TPEx day-trading rows={len(rows)} parsed_fields={sorted(market)} "
            f"missing={sorted(required - set(market))} keys={keys}"
        )
    if market and (not traded or (ceiling and traded > ceiling)):
        contract_fail(f"TPEx day-trading invalid selected session traded={traded} ceiling={ceiling}")
    return "ok", f"TPEx day-trading: rows={len(rows)} date={traded} fields={sorted(market)}"



def check_tpex_institutional_amounts(session: requests.Session) -> tuple[str, str]:
    fetched = fetch_json(session, chips.TPEX_INSTITUTIONAL_AMOUNTS)
    if not fetched.ok:
        return "unavailable", f"TPEx institutional amounts unavailable: {fetched.error}"
    rows = chip_rows(fetched.payload)
    values, traded = chips.parse_tpex_institutional_amounts(rows, chips.valid_chip_date(chips.NOW.date().isoformat()))
    if rows and not values:
        keys = sorted({str(key) for row in rows[:5] for key in row})
        contract_fail(f"TPEx institutional amounts rows={len(rows)} parsed=0 keys={keys}")
    return "ok", f"TPEx institutional amounts: rows={len(rows)} date={traded} groups={sorted(values)}"


def check_twse_day_trade(session: requests.Session) -> tuple[str, str]:
    # Intentionally reuse the production source selector and parser so verifier
    # and updater cannot silently drift to different TWSE endpoint contracts.
    errors: list[dict[str, str]] = []
    fallback = chips.valid_chip_date(chips.NOW.date().isoformat())
    rows, url = chips.try_twse_day_trade_rows(fallback, errors, attempts=1)
    if not rows:
        detail = "; ".join(item.get("error", "") for item in errors[-3:])
        # A reachable JSON response with the wrong semantic schema is a real
        # contract regression. Pure DNS/timeout/HTTP failures remain warnings.
        semantic = [item for item in errors if "semantic mismatch" in str(item.get("error", "")).lower() and "rows=0" not in str(item.get("error", "")).lower()]
        if semantic:
            contract_fail(f"TWSE day-trading production candidates reachable but semantically invalid: {detail}")
        return "unavailable", f"TWSE day-trading unavailable across production candidates: {detail}"
    market, traded = chips.parse_twse_day_trade_market(rows, fallback)
    required = {"volume", "buy_amount", "sell_amount"}
    if not required.issubset(market):
        contract_fail(f"TWSE day-trading production parser fields={sorted(market)} url={url}")
    return "ok", f"TWSE day-trading: rows={len(rows)} date={traded} fields={sorted(market)} source={url}"


def main() -> None:
    session = requests.Session()
    checks = (check_exdiv, check_dividend_plans, check_day_trade, check_tpex_institutional_amounts, check_twse_day_trade)
    warnings: list[str] = []
    failures: list[str] = []
    for check in checks:
        try:
            status, message = check(session)
            print(message)
            if status == "unavailable":
                warnings.append(message)
        except RuntimeError as exc:
            failures.append(str(exc))
            print(f"CONTRACT FAILURE: {exc}", file=sys.stderr)
    if failures:
        raise SystemExit(f"{VERSION} live contract gate failed: {'; '.join(failures)}")
    print(f"{VERSION} live contract gate ok; external_warnings={len(warnings)}")


if __name__ == "__main__":
    main()
