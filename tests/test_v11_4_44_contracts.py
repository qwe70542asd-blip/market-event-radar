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


def test_tpex_exdiv_current_english_schema():
    payload = [{
        "Date": "1150810",
        "SecuritiesCompanyCode": "2948",
        "CompanyName": "寶陞",
        "CashDividend": "1.928650",
        "StockDividend": "1.147542",
        "ExRightsDiviend": "除權息",
    }]
    rows = ev.parse_tpex_exdiv_history_payload(payload, "https://example.test/tpex")
    assert len(rows) == 1
    assert rows[0]["symbol"] == "2948"
    assert rows[0].get("cash_dividend") == 1.92865


def test_tpex_dividend_plan_current_schema():
    payload = [{
        "出表日期": "1150804",
        "公司代號": "1234",
        "公司名稱": "測試公司",
        "股利年度": "115",
        "期別": "年度",
        "董事會決議通過股利分派日": "1150225",
        "股東會日期配盈餘/待彌補虧損(元)": "1150617",
        "股東配發內容-盈餘分配之現金股利(元/股)": "3.0",
        "股東配發內容-盈餘轉增資配股(元/股)": "0.5",
    }]
    rows = ev.parse_dividend_plans(payload, "TPEX", "https://example.test/tpex", "tpex-dividend-plan")
    assert rows
    decision = next(row for row in rows if row["event_type"] == "dividend-decision")
    assert decision["local_date"] == "2026-02-25"
    assert decision.get("cash_dividend") == 3.0
    meeting = next(row for row in rows if row["event_type"] == "shareholder-meeting")
    assert meeting["local_date"] == "2026-06-17"


def test_tpex_dividend_eligible_count_accepts_legacy_shareholder_date_header():
    payload = [{
        "公司代號": "1240",
        "公司名稱": "茂生農經",
        "董事會決議通過股利分派日": "1080311",
        "股東會日期配盈餘/待彌補虧損(元)": "1080617",
    }]
    # Both official dates are in 2019, outside the 2026 archive window. The
    # legacy header is still parsed as a date rather than discarded as money.
    board, meeting = ev.dividend_plan_candidate_dates(payload[0])
    assert board.isoformat() == "2019-03-11"
    assert meeting.isoformat() == "2019-06-17"
    assert ev.dividend_plan_eligible_count(payload) == 0


def test_tpex_day_trade_current_openapi_schema_selects_latest_session():
    rows = [
        {
            "Date": "1150803",
            "DayTradingVolume": "354631000",
            "DayTradingVolumeOfTheMarket": "22.56%",
            "DayTradingValueOfBuys": "62782492410",
            "DayTradingValueOfBuyOfTheMarket": "45.06%",
            "DayTradingValueOfSells": "63139673940",
            "DayTradingValueOfSellsOfTheMarket": "45.32%",
        },
        {
            "Date": "1150807",
            "DayTradingVolume": "400000000",
            "DayTradingVolumeOfTheMarket": "23.00%",
            "DayTradingValueOfBuys": "70000000000",
            "DayTradingValueOfBuyOfTheMarket": "46.00%",
            "DayTradingValueOfSells": "71000000000",
            "DayTradingValueOfSellsOfTheMarket": "46.50%",
        },
    ]
    market, traded = chips.parse_tpex_day_trade_market(rows, "2026-08-07")
    assert traded == "2026-08-07"
    assert market == {
        "volume": 400000,
        "buy_amount": 70000000000.0,
        "sell_amount": 71000000000.0,
        "volume_ratio_percent": 23.0,
        "buy_amount_ratio_percent": 46.0,
        "sell_amount_ratio_percent": 46.5,
    }


def test_tpex_day_trade_partial_core_fails_closed():
    rows = [{
        "Date": "1150807",
        "DayTradingVolume": "400000000",
        "DayTradingValueOfBuys": "70000000000",
        # sell field intentionally absent
    }]
    market, traded = chips.parse_tpex_day_trade_market(rows, "2026-08-07")
    assert market == {}
    assert traded is None


def test_tpex_institutional_amount_summary_parser():
    rows=[
      {'Date':'1150807','InstitutionalInvestors':'外資及陸資(不含自營商)','BuyAmount':'500','SellAmount':'800','Difference':'-300'},
      {'Date':'1150807','InstitutionalInvestors':'投信','BuyAmount':'200','SellAmount':'100','Difference':'100'},
      {'Date':'1150807','InstitutionalInvestors':'自營商合計','BuyAmount':'150','SellAmount':'110','Difference':'40'},
      {'Date':'1150807','InstitutionalInvestors':'三大法人合計','BuyAmount':'850','SellAmount':'1010','Difference':'-160'},
    ]
    values,traded=chips.parse_tpex_institutional_amounts(rows,'2026-08-07')
    assert traded == '2026-08-07'
    assert values['foreign']['net'] == -300
    assert values['trust']['net'] == 100
    assert values['dealer']['net'] == 40
    assert values['total']['net'] == -160


def test_twse_day_trade_market_aggregates_official_detail_rows():
    rows = [
        {"_source_date":"2026-08-07","證券代號":"2330","當日沖銷交易成交股數":"120000","當日沖銷交易買進成交金額":"10000000","當日沖銷交易賣出成交金額":"10100000"},
        {"_source_date":"2026-08-07","證券代號":"2317","當日沖銷交易成交股數":"80000","當日沖銷交易買進成交金額":"5000000","當日沖銷交易賣出成交金額":"4900000"},
    ]
    market, traded = chips.parse_twse_day_trade_market(rows, "2026-08-07")
    assert traded == "2026-08-07"
    assert market == {"volume":200,"buy_amount":15000000,"sell_amount":15000000,"stock_count":2}


def test_tpex_amount_summary_accepts_schema_variants():
    rows = [
        {"Date":"1150807","InvestorType":"外資及陸資(不含自營商)","TotalBuyAmount":"500","TotalSellAmount":"800","NetBuySellAmount":"-300"},
        {"Date":"1150807","InvestorType":"投信","TotalBuyAmount":"200","TotalSellAmount":"100","NetBuySellAmount":"100"},
        {"Date":"1150807","InvestorType":"自營商合計","TotalBuyAmount":"150","TotalSellAmount":"110","NetBuySellAmount":"40"},
        {"Date":"1150807","InvestorType":"三大法人合計","TotalBuyAmount":"850","TotalSellAmount":"1010","NetBuySellAmount":"-160"},
    ]
    values, traded = chips.parse_tpex_institutional_amounts(rows, "2026-08-07")
    assert traded == "2026-08-07"
    assert values["foreign"]["net"] == -300
    assert values["total"]["net"] == -160
