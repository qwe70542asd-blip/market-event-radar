from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_events as ev
import update_tw_chips as chips


def test_market_date_non_zero_padded_gregorian_and_roc():
    assert ev.parse_market_date("2026/8/7").isoformat() == "2026-08-07"
    assert ev.parse_market_date("115/8/7").isoformat() == "2026-08-07"
    assert ev.parse_market_date("1150807").isoformat() == "2026-08-07"
    assert ev.parse_market_date("20260807").isoformat() == "2026-08-07"


def test_tpex_exdiv_documented_chinese_schema():
    payload = [{
        "除權息日期": "115/8/7",
        "代號": "1234",
        "名稱": "測試公司",
        "權或息": "息",
        "現金股利": "2.5",
        "每仟股無償配股": "0",
    }]
    rows = ev.parse_tpex_exdiv_history_payload(payload, "https://example.test/tpex")
    assert len(rows) == 1
    assert rows[0]["symbol"] == "1234"
    assert rows[0].get("cash_dividend") == 2.5


def test_tpex_dividend_plan_current_schema():
    payload = [{
        "公司代號": "1234",
        "公司名稱": "測試公司",
        "股利年度": "115",
        "期別": "年度",
        "董事會決議通過股利分派日": "115/2/25",
        "股東會日期配盈餘/待彌補虧損(元)": "999999999",
        "股東配發內容-盈餘分配之現金股利(元/股)": "3.0",
        "股東配發內容-盈餘轉增資配股(元/股)": "0.5",
    }]
    rows = ev.parse_dividend_plans(payload, "TPEX", "https://example.test/tpex", "tpex-dividend-plan")
    assert rows
    decision = next(row for row in rows if row["event_type"] == "dividend-decision")
    assert decision["local_date"] == "2026-02-25"
    assert decision.get("cash_dividend") == 3.0


def test_tpex_day_trade_market_aggregate_aliases():
    rows = [{
        "資料日期": "115/08/07",
        "當日沖銷交易成交股數": "1,500,000",
        "當日沖銷交易買進成交金額": "123456789",
        "當日沖銷交易賣出成交金額": "123400000",
        "當日沖銷交易成交股數占市場比重": "18.5",
    }]
    market, traded = chips.parse_tpex_day_trade_market(rows, "2026-08-07")
    assert traded == "2026-08-07"
    assert market["volume"] == 1500
    assert market["buy_amount"] == 123456789
    assert "symbol" not in market
