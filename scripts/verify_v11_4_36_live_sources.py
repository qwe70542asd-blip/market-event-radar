#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import requests
import update_events as ev
import update_tw_chips as chips


def fail(message: str) -> None:
    raise SystemExit(f"v11.4.36 live source gate failed: {message}")


def check_exdiv(session: requests.Session) -> None:
    payload = ev.http_json(session, ev.TPEX_EXDIV_HISTORY_URL)
    rows = ev.payload_dict_rows(payload)
    parsed = ev.parse_tpex_exdiv_history_payload(payload)
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
        fail(f"TPEx ex-dividend rows={len(rows)}, eligible={eligible}, parsed=0")
    print(f"TPEx ex-dividend gate: rows={len(rows)} eligible={eligible} parsed={len(parsed)}")


def check_dividend_plans(session: requests.Session) -> None:
    payload = ev.http_json(session, ev.TPEX_DIVIDEND_PLAN_URL)
    rows = ev.payload_dict_rows(payload)
    parsed = ev.parse_dividend_plans(payload, "TPEX", ev.TPEX_DIVIDEND_PLAN_URL, "tpex-dividend-plan")
    eligible = 0
    for row in rows:
        decision = ev.first_value(row, [
            "董事會決議通過股利分派日", "董事會通過股利分派日", "董事會決議通過股利分派日期",
            "董事會（擬議）股利分派日", "董事會(擬議)股利分派日", "董事會股利分派日",
            "董事會擬議日期", "董事會決議日期", "董事會決議日", "董事會日期",
            "現金股利經董事會決議、增資配股經董事會擬議日期",
            "BoardMeetingDate", "BoardDecisionDate",
        ])
        shareholder = ev.first_value(row, ["股東會日期", "ShareholdersMeetingDate"])
        for raw in (decision, shareholder):
            day = ev.first_market_date(raw)
            if day and ev.ARCHIVE_START <= day <= ev.NOW.date() + timedelta(days=370):
                eligible += 1
                break
    if rows and eligible and not parsed:
        fail(f"TPEx dividend-plan rows={len(rows)}, eligible={eligible}, parsed=0")
    print(f"TPEx dividend-plan gate: rows={len(rows)} eligible={eligible} parsed={len(parsed)}")


def check_day_trade() -> None:
    rows = chips.get_rows(chips.TPEX_DAY_TRADE)
    valid_dates = [chips.valid_chip_date(chips.row_date(row)) for row in rows]
    valid_dates = [value for value in valid_dates if value]
    ceiling = max(valid_dates) if valid_dates else chips.valid_chip_date(chips.NOW.date().isoformat())
    market, traded = chips.parse_tpex_day_trade_market(rows, ceiling)
    if rows and not market:
        fail(f"TPEx day-trading rows={len(rows)} parsed=0")
    if market and (not traded or (ceiling and traded > ceiling)):
        fail(f"TPEx day-trading invalid selected session traded={traded} ceiling={ceiling}")
    print(f"TPEx day-trading gate: rows={len(rows)} date={traded} fields={sorted(market)}")


def main() -> None:
    session = requests.Session()
    session.headers.update(ev.HEADERS)
    check_exdiv(session)
    check_dividend_plans(session)
    check_day_trade()
    print("v11.4.36 live source gate ok")


if __name__ == "__main__":
    main()
