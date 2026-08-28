#!/usr/bin/env python3
"""Progressively collect non-official quote references for cross-checking.

Only Yahoo chart data is consumed automatically. Goodinfo and Yahoo Taiwan page
URLs are emitted as reference links; their page values are never scraped or
used to overwrite official records.
"""
from __future__ import annotations
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
import requests
from common import DATA, NOW, read_json, write_payload, VERSION

HEADERS={"User-Agent":"Mozilla/5.0 (compatible; MarketEventRadar/11.4.52)"}
BATCH=120
TAIPEI=ZoneInfo("Asia/Taipei")

def number(value:Any)->float|None:
 try:
  if value is None:return None
  return float(value)
 except (TypeError,ValueError):return None

def yahoo_ticker(asset:dict)->str:
 suffix="TWO" if str(asset.get("exchange") or "").upper()=="TPEX" else "TW"
 return f"{asset.get('symbol')}.{suffix}"

def fetch_one(asset:dict)->tuple[str,dict|None,str|None]:
 symbol=str(asset.get("symbol") or "").upper();ticker=yahoo_ticker(asset)
 url=f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=5d&interval=1d&events=div%2Csplits"
 try:
  r=requests.get(url,headers=HEADERS,timeout=18);r.raise_for_status();payload=r.json()
  result=((payload.get("chart") or {}).get("result") or [None])[0]
  if not result:raise ValueError("empty chart result")
  meta=result.get("meta") or {};timestamps=result.get("timestamp") or []
  quote=((result.get("indicators") or {}).get("quote") or [{}])[0]
  closes=((result.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose") or quote.get("close") or []
  pairs=[]
  for index,stamp in enumerate(timestamps):
   close=number(closes[index]) if index<len(closes) else None
   if close is not None:pairs.append((int(stamp),close))
  market_time=meta.get("regularMarketTime")
  if market_time is None and pairs:market_time=pairs[-1][0]
  if market_time is None:raise ValueError("missing verified market time")
  market_dt=datetime.fromtimestamp(int(market_time),TAIPEI);quote_date=market_dt.date().isoformat()
  price=number(meta.get("regularMarketPrice")) or (pairs[-1][1] if pairs else None)
  previous=None;previous_date=None
  if pairs:
   latest_dt=datetime.fromtimestamp(pairs[-1][0],TAIPEI)
   if latest_dt.date().isoformat()==quote_date and len(pairs)>1:
    previous=pairs[-2][1];previous_date=datetime.fromtimestamp(pairs[-2][0],TAIPEI).date().isoformat()
   elif latest_dt.date().isoformat()<quote_date:
    previous=pairs[-1][1];previous_date=latest_dt.date().isoformat()
  if price is None:raise ValueError("missing price")
  return symbol,{
   "symbol":symbol,"ticker":ticker,"price":price,"previous_close":previous,
   "currency":meta.get("currency") or "TWD","exchange_name":meta.get("exchangeName"),
   "market_time":int(market_time),"market_at":market_dt.isoformat(timespec="seconds"),"quote_date":quote_date,"previous_reference_date":previous_date,"source":"Yahoo Finance chart",
   "source_url":f"https://tw.stock.yahoo.com/quote/{ticker}",
   "goodinfo_url":f"https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={symbol}",
   "updated_at":NOW.isoformat(timespec="seconds")
  },None
 except Exception as exc:return symbol,None,str(exc)

def main()->None:
 assets=read_json(DATA/"assets.json",{"assets":[]}).get("assets",[])
 old=read_json(DATA/"secondary-reference.json",{"metadata":{},"items":{},"state":{}})
 items=dict(old.get("items") or {});state=dict(old.get("state") or {})
 candidates=[a for a in assets if a.get("market")=="TW" and a.get("asset_class") in {"stock","etf"} and a.get("symbol")]
 candidates.sort(key=lambda a:str(a.get("symbol")))
 cursor=int(state.get("cursor") or 0)
 if cursor>=len(candidates):cursor=0
 batch=candidates[cursor:cursor+BATCH]
 if len(batch)<BATCH:batch+=candidates[:BATCH-len(batch)]
 success=0;errors=[]
 with ThreadPoolExecutor(max_workers=6) as pool:
  futures=[pool.submit(fetch_one,a) for a in batch]
  for future in as_completed(futures):
   symbol,row,error=future.result()
   if row:items[symbol]=row;success+=1
   elif error:errors.append({"symbol":symbol,"error":error[:180]})
 next_cursor=(cursor+len(batch))%len(candidates) if candidates else 0
 payload={
  "metadata":{"version":VERSION,"updated_at":NOW.isoformat(timespec="seconds"),"status":"ok" if success else "partial" if items else "warning","item_count":len(items),"batch_size":len(batch),"batch_success":success,"note":"Yahoo chart is a progressive secondary quote reference only; every row carries its verified market date and official TWSE/TPEx values remain primary."},
  "state":{"cursor":next_cursor,"last_batch_at":NOW.isoformat(timespec="seconds")},
  "errors":errors[:50],"items":items
 }
 write_payload("secondary-reference.json","__SECONDARY_REFERENCE_SEED__",payload)
 print(payload["metadata"])
if __name__=="__main__":main()
