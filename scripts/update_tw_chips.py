#!/usr/bin/env python3
"""Refresh official Taiwan institutional and margin summaries when endpoints respond.

The script is conservative: missing or schema-changed fields remain null, and an
existing successful payload is preserved by the workflow when no official values
can be verified.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
OUT=DATA/"tw-chips.json"
SEED=DATA/"tw-chips-seed.js"
NOW=datetime.now(ZoneInfo("Asia/Taipei"))
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; MarketEventRadar/11.1)","Accept-Language":"zh-TW,zh;q=0.9"}
TWSE_T86="https://www.twse.com.tw/rwd/zh/fund/T86"
TWSE_MARGIN="https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"


def number(value):
    try:
        text=str(value).replace(",","").replace("%","").strip()
        return float(text) if text not in {"","--","-"} else None
    except Exception:return None


def recent_trade_date()->str:
    date=NOW.date()
    while date.weekday()>=5:date-=timedelta(days=1)
    return date.strftime("%Y%m%d")


def load_previous():
    try:return json.loads(OUT.read_text(encoding="utf-8"))
    except Exception:return {"markets":{},"items":{}}


def fetch_twse(session:requests.Session,date:str):
    result={"institutional":{"foreign_net":None,"trust_net":None,"dealer_net":None,"total_net":None},
            "day_trading":{"ratio_percent":None,"trade_value":None},
            "margin":{"balance_shares":None},"short":{"balance_shares":None}}
    items={}
    try:
        response=session.get(TWSE_T86,params={"date":date,"selectType":"ALLBUT0999","response":"json"},headers=HEADERS,timeout=30)
        response.raise_for_status();payload=response.json()
        fields=payload.get("fields") or []
        for raw in payload.get("data") or []:
            row=dict(zip(fields,raw))
            symbol=str(row.get("證券代號") or "").strip()
            if not symbol:continue
            foreign=number(row.get("外陸資買賣超股數(不含外資自營商)"))
            trust=number(row.get("投信買賣超股數"))
            dealer=number(row.get("自營商買賣超股數"))
            total=number(row.get("三大法人買賣超股數"))
            items[symbol]={"symbol":symbol,"name":str(row.get("證券名稱") or "").strip(),"market":"twse",
                "foreign_net":foreign,"trust_net":trust,"dealer_net":dealer,"total_net":total}
        if items:
            result["institutional"]["foreign_net"]=sum((row["foreign_net"] or 0) for row in items.values())
            result["institutional"]["trust_net"]=sum((row["trust_net"] or 0) for row in items.values())
            result["institutional"]["dealer_net"]=sum((row["dealer_net"] or 0) for row in items.values())
            result["institutional"]["total_net"]=sum((row["total_net"] or 0) for row in items.values())
    except Exception as exc:print("warning T86",exc)
    try:
        response=session.get(TWSE_MARGIN,params={"date":date,"selectType":"MS","response":"json"},headers=HEADERS,timeout=30)
        response.raise_for_status();payload=response.json()
        fields=payload.get("fields") or []
        rows=payload.get("data") or []
        for raw in rows:
            row=dict(zip(fields,raw))
            label=str(row.get(fields[0],"")) if fields else ""
            if "融資" in label:
                values=[number(value) for value in raw]
                values=[value for value in values if value is not None]
                if values:result["margin"]["balance_shares"]=values[-1]
            if "融券" in label:
                values=[number(value) for value in raw]
                values=[value for value in values if value is not None]
                if values:result["short"]["balance_shares"]=values[-1]
    except Exception as exc:print("warning margin",exc)
    return result,items


def main()->None:
    previous=load_previous()
    date=recent_trade_date()
    market,items=fetch_twse(requests.Session(),date)
    verified=bool(items) or any(value is not None for section in market.values() for value in section.values())
    if not verified:
        if previous.get("metadata",{}).get("updated_at"):
            raise SystemExit("No verified official chip values; previous payload was not replaced.")
    markets={**(previous.get("markets") or {}),"twse":market}
    payload={"metadata":{"version":"v11.1.1","updated_at":NOW.isoformat(timespec="seconds") if verified else None,
        "trading_date":date,"source":"TWSE／TPEx 官方盤後資料",
        "note":"缺值保留 null，不以 0 冒充。"},"markets":markets,"items":{**(previous.get("items") or {}),**items}}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEED.write_text("window.__TW_CHIPS_SEED__ = "+json.dumps(payload,ensure_ascii=False)+";\n",encoding="utf-8")
    print("chips",len(payload["items"]))


if __name__=="__main__":
    main()
