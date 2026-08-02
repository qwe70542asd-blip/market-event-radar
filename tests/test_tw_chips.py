from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("update_tw_chips", ROOT / "scripts" / "update_tw_chips.py")
chips = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(chips)


def test_rows_from_twse_tables_and_individual_day_trading():
    payload = {
        "tables": [{
            "fields": ["日期", "證券代號", "證券名稱", "當日沖銷成交股數", "當日沖銷成交金額", "當沖成交比率"],
            "data": [["20260731", "2330", "台積電", "2,000,000", "2,400,000,000", "12.5"]],
        }]
    }
    rows = chips.rows_from_payload(payload)
    items, market, reported = chips.parse_day_rows(rows, "TWSE")
    assert items["TWSE:2330"]["day_trading"]["volume"] == 2_000_000
    assert items["TWSE:2330"]["day_trading"]["ratio_percent"] == 12.5
    assert market["trade_value"] == 2_400_000_000
    assert reported == "2026-07-31"


def test_margin_and_short_missing_values_stay_none():
    rows = [{
        "日期": "115/07/31", "證券代號": "2330", "證券名稱": "台積電",
        "融資今日餘額": "12,000", "融資增減": "-500", "融券今日餘額": "800",
    }]
    items, margin, short, reported = chips.parse_margin_rows(rows, "TWSE")
    row = items["TWSE:2330"]
    assert row["margin"]["balance_shares"] == 12_000
    assert row["margin"]["change_shares"] == -500
    assert row["short"]["balance_shares"] == 800
    assert row["short"]["change_shares"] is None
    assert margin["balance_shares"] == 12_000
    assert short["balance_shares"] == 800
    assert reported == "2026-07-31"
