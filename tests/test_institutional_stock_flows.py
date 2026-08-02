from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path


if "requests" not in sys.modules:
    requests_stub = types.ModuleType("requests")
    requests_stub.Session = object
    sys.modules["requests"] = requests_stub

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("update_institutional_history", ROOT / "scripts" / "update_institutional_history.py")
institutional = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(institutional)


def test_t86_keeps_per_stock_buy_sell_and_net():
    payload = {
        "fields": [
            "證券代號", "證券名稱", "外陸資買進股數(不含外資自營商)",
            "外陸資賣出股數(不含外資自營商)", "外陸資買賣超股數(不含外資自營商)",
            "投信買進股數", "投信賣出股數", "投信買賣超股數",
            "自營商買進股數(自行買賣)", "自營商賣出股數(自行買賣)",
            "自營商買進股數(避險)", "自營商賣出股數(避險)",
            "自營商買賣超股數", "三大法人買賣超股數",
        ],
        "data": [["2330", "台積電", "2000", "1000", "1000", "800", "200", "600", "100", "50", "300", "150", "200", "1800"]],
    }
    rankings, stocks = institutional.parse_t86(payload, "2026-07-31")
    assert rankings["foreign"]["buys"][0]["symbol"] == "2330"
    assert stocks["2330"]["flows"]["foreign"] == {"buy": 2000.0, "sell": 1000.0, "net": 1000.0}
    assert stocks["2330"]["flows"]["dealer"]["buy"] == 400.0
