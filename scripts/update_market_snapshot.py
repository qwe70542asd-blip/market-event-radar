#!/usr/bin/env python3
"""Refresh compact global index, ETF and U.S. equity snapshot using Yahoo chart data."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
OUT=DATA/"market-snapshot.json"
SEED=DATA/"market-snapshot-seed.js"
NOW=datetime.now(ZoneInfo("Asia/Taipei"))
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; MarketEventRadar/11.1)","Accept":"application/json"}
SYMBOLS=[
 ("^TWII","台灣加權指數","TW",""),
 ("^TWOII","台灣櫃買指數","TW",""),
 ("^GSPC","S&P 500","US",""),
 ("^DJI","道瓊工業","US",""),
 ("^IXIC","NASDAQ","US",""),
 ("^SOX","費城半導體","US",""),
 ("^N225","日經 225","JP",""),
 ("^KS11","韓國 KOSPI","KR",""),
 ("NVDA","NVIDIA","US","USD"),
 ("AAPL","Apple","US","USD"),
 ("MSFT","Microsoft","US","USD"),
]


def fetch_one(session:requests.Session,symbol:str,name:str,market:str,currency_hint:str)->dict|None:
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(symbol,safe='')}?range=5d&interval=5m&includePrePost=false"
    try:
        response=session.get(url,headers=HEADERS,timeout=18)
        response.raise_for_status()
        payload=response.json()
        result=payload.get("chart",{}).get("result",[None])[0]
        if not result:return None
        meta=result.get("meta") or {}
        closes=(result.get("indicators",{}).get("quote") or [{}])[0].get("close") or []
        points=[value for value in closes if isinstance(value,(int,float))]
        price=meta.get("regularMarketPrice")
        if price is None and points:price=points[-1]
        previous=meta.get("chartPreviousClose") or meta.get("previousClose")
        if price is None:return None
        change=price-previous if previous not in (None,0) else None
        pct=change/previous*100 if change is not None else None
        return {"symbol":symbol,"name":name,"market":market,"currency":meta.get("currency") or currency_hint,
            "price":price,"previous_close":previous,"change":change,"change_percent":pct,
            "open":meta.get("regularMarketOpen"),"high":meta.get("regularMarketDayHigh"),
            "low":meta.get("regularMarketDayLow"),"volume":meta.get("regularMarketVolume"),
            "market_at":meta.get("regularMarketTime"),"market_state":meta.get("marketState"),
            "source":"Yahoo 公開行情"}
    except Exception as exc:
        print("warning",symbol,exc)
        return None


def main()->None:
    session=requests.Session()
    items=[row for args in SYMBOLS if (row:=fetch_one(session,*args))]
    if len(items)<4:
        raise SystemExit(f"Only {len(items)} market rows; previous snapshot was not replaced.")
    payload={"metadata":{"version":"v11.1.5","updated_at":NOW.isoformat(timespec="seconds"),
        "source":"Yahoo 公開行情","note":"公開行情可能延遲；失敗時保留上次成功資料。"},"items":items}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEED.write_text("window.__MARKET_SNAPSHOT_SEED__ = "+json.dumps(payload,ensure_ascii=False)+";\n",encoding="utf-8")
    print("market snapshot",len(items))


if __name__=="__main__":
    main()
