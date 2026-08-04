#!/usr/bin/env python3
from common import *
import requests
SYMBOLS=[("^TWII","台灣加權","TW"),("^TWOII","台灣櫃買指數","TW"),("^GSPC","S&P 500","US"),("^DJI","道瓊工業","US"),("^IXIC","NASDAQ","US"),("^SOX","費城半導體","US"),("^N225","日經225","JP"),("NVDA","NVIDIA","US")]
def one(s,n,m):
 r=requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{requests.utils.quote(s,safe='')}",params={"range":"2d","interval":"5m"},headers={"User-Agent":"Mozilla/5.0"},timeout=12);r.raise_for_status();x=r.json()["chart"]["result"][0];meta=x["meta"];q=x.get("indicators",{}).get("quote",[{}])[0];prices=[v for v in q.get("close",[]) if v is not None];price=meta.get("regularMarketPrice") or (prices[-1] if prices else None);prev=meta.get("chartPreviousClose") or meta.get("previousClose");chg=(price-prev) if price is not None and prev is not None else None;return{"symbol":s,"name":n,"market":m,"price":price,"previous_close":prev,"change":chg,"change_percent":chg/prev*100 if chg is not None and prev else None,"open":meta.get("regularMarketOpen"),"high":meta.get("regularMarketDayHigh"),"low":meta.get("regularMarketDayLow"),"volume":meta.get("regularMarketVolume"),"market_at":NOW.isoformat(timespec="seconds")}
def main():
 old=read_json(DATA/"market-snapshot.json",{"items":[]});rows=[];errors=[]
 for x in SYMBOLS:
  try:rows.append(one(*x))
  except Exception as e:errors.append(f"{x[0]}:{e}")
 if len(rows)<4: rows=old.get("items",[])
 payload={"metadata":{"version":"v11.3.0","updated_at":NOW.isoformat(timespec="seconds"),"source":"Yahoo public chart API","warnings":errors},"items":rows};write_payload("market-snapshot.json","__MARKET_SNAPSHOT_SEED__",payload)
if __name__=="__main__":main()
