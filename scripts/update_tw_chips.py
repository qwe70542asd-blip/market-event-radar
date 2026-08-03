#!/usr/bin/env python3
"""Refresh official Taiwan institutional and margin data.

The official TWSE daily tables are published after the trading session.  A run
before publication must therefore search backwards for the latest available
business date instead of treating today's empty response as a fatal error.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
OUT=DATA/"tw-chips.json"
SEED=DATA/"tw-chips-seed.js"
NOW=datetime.now(ZoneInfo("Asia/Taipei"))
HEADERS={
    "User-Agent":"Mozilla/5.0 (compatible; MarketEventRadar/11.2.2)",
    "Accept-Language":"zh-TW,zh;q=0.9",
}
TWSE_T86="https://www.twse.com.tw/rwd/zh/fund/T86"
TWSE_MARGIN="https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"


def number(value):
    try:
        text=str(value).replace(",","").replace("%","").strip()
        return float(text) if text not in {"","--","-","None"} else None
    except Exception:
        return None


def candidate_trade_dates(days: int=14):
    date=NOW.date()
    output=[]
    while len(output)<days:
        if date.weekday()<5:
            output.append(date.strftime("%Y%m%d"))
        date-=timedelta(days=1)
    return output


def load_previous():
    try:
        payload=json.loads(OUT.read_text(encoding="utf-8"))
        return payload if isinstance(payload,dict) else {"markets":{},"items":{}}
    except Exception:
        return {"markets":{},"items":{}}


def first(row: dict, *keys):
    for key in keys:
        value=row.get(key)
        if value not in (None,""):
            return value
    return None


def empty_market():
    return {
        "institutional":{"foreign_net":None,"trust_net":None,"dealer_net":None,"total_net":None},
        "day_trading":{"ratio_percent":None,"trade_value":None},
        "margin":{"balance_shares":None},
        "short":{"balance_shares":None},
    }


def fetch_twse(session: requests.Session, date: str):
    result=empty_market()
    items={}
    messages=[]

    try:
        response=session.get(
            TWSE_T86,
            params={"date":date,"selectType":"ALLBUT0999","response":"json"},
            headers=HEADERS,
            timeout=35,
        )
        response.raise_for_status()
        payload=response.json()
        fields=payload.get("fields") or []
        for raw in payload.get("data") or []:
            row=dict(zip(fields,raw))
            symbol=str(first(row,"證券代號","股票代號") or "").strip()
            if not symbol:
                continue
            foreign=number(first(row,
                "外陸資買賣超股數(不含外資自營商)",
                "外資及陸資買賣超股數(不含外資自營商)",
                "外資買賣超股數"))
            trust=number(first(row,"投信買賣超股數"))
            dealer=number(first(row,"自營商買賣超股數"))
            total=number(first(row,"三大法人買賣超股數"))
            items[symbol]={
                "symbol":symbol,
                "name":str(first(row,"證券名稱","股票名稱") or "").strip(),
                "market":"twse",
                "foreign_net":foreign,
                "trust_net":trust,
                "dealer_net":dealer,
                "total_net":total,
            }
        if items:
            result["institutional"]["foreign_net"]=sum((row["foreign_net"] or 0) for row in items.values())
            result["institutional"]["trust_net"]=sum((row["trust_net"] or 0) for row in items.values())
            result["institutional"]["dealer_net"]=sum((row["dealer_net"] or 0) for row in items.values())
            result["institutional"]["total_net"]=sum((row["total_net"] or 0) for row in items.values())
        else:
            messages.append(f"T86 {payload.get('stat') or 'empty'}")
    except Exception as exc:
        messages.append(f"T86 error: {exc}")

    try:
        response=session.get(
            TWSE_MARGIN,
            params={"date":date,"selectType":"MS","response":"json"},
            headers=HEADERS,
            timeout=35,
        )
        response.raise_for_status()
        payload=response.json()
        fields=payload.get("fields") or []
        for raw in payload.get("data") or []:
            row=dict(zip(fields,raw))
            label=" ".join(str(value) for value in raw[:2])
            values=[number(value) for value in raw]
            values=[value for value in values if value is not None]
            if not values:
                continue
            if "融資" in label:
                result["margin"]["balance_shares"]=values[-1]
            if "融券" in label:
                result["short"]["balance_shares"]=values[-1]
        if not payload.get("data"):
            messages.append(f"margin {payload.get('stat') or 'empty'}")
    except Exception as exc:
        messages.append(f"margin error: {exc}")

    verified=bool(items) or any(
        value is not None
        for section in result.values()
        for value in section.values()
    )
    return result,items,verified,messages


def write_payload(payload):
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEED.write_text(
        "window.__TW_CHIPS_SEED__ = "+json.dumps(payload,ensure_ascii=False)+";\n",
        encoding="utf-8",
    )


def main()->None:
    previous=load_previous()
    session=requests.Session()
    chosen_date=None
    market=None
    items={}
    attempts=[]

    for date in candidate_trade_dates():
        current,current_items,verified,messages=fetch_twse(session,date)
        attempts.append({"date":date,"verified":verified,"messages":messages})
        if verified:
            chosen_date=date
            market=current
            items=current_items
            break
        time.sleep(.3)

    previous_markets=previous.get("markets") or {}
    previous_items=previous.get("items") or {}

    if chosen_date:
        markets={**previous_markets,"twse":market}
        payload={
            "metadata":{
                "version":"v11.2.2",
                "updated_at":NOW.isoformat(timespec="seconds"),
                "trading_date":chosen_date,
                "source":"TWSE 官方盤後資料",
                "status":"ok",
                "note":"自動向前尋找最近有官方資料的交易日；缺值保留 null，不以 0 冒充。",
                "attempted_dates":[row["date"] for row in attempts],
            },
            "markets":markets,
            "items":{**previous_items,**items},
        }
    else:
        # A temporary network or publication delay must not make the entire
        # independent chip channel fail. Preserve the last verified payload.
        payload={
            **previous,
            "metadata":{
                **(previous.get("metadata") or {}),
                "version":"v11.2.2",
                "updated_at":(previous.get("metadata") or {}).get("updated_at") or NOW.isoformat(timespec="seconds"),
                "last_attempt_at":NOW.isoformat(timespec="seconds"),
                "status":"warning",
                "note":"本次未取得官方盤後資料，已保留上一筆資料；稍後排程會自動重試。",
                "attempted_dates":[row["date"] for row in attempts],
            },
            "markets":previous_markets or {"twse":empty_market()},
            "items":previous_items,
        }

    write_payload(payload)
    print("chips",len(payload.get("items") or {}),payload["metadata"].get("trading_date"),payload["metadata"].get("status"))


if __name__=="__main__":
    main()
