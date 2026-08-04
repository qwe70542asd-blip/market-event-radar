#!/usr/bin/env python3
from common import *
import requests
def num(v):
 try:return float(str(v).replace(",","").strip())
 except:return None
def fetch(url,exchange):
 r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=20);r.raise_for_status();out=[]
 for x in r.json():
  s=str(x.get("Code") or x.get("SecuritiesCompanyCode") or x.get("SecuritiesCompanyCode") or "").strip();n=x.get("Name") or x.get("CompanyName") or x.get("SecuritiesCompanyName") or "";price=num(x.get("ClosingPrice") or x.get("Close") or x.get("ClosePrice"));chg=num(x.get("Change") or x.get("ChangeAmount"));prev=price-chg if price is not None and chg is not None else None
  if not s or price is None:continue
  is_etf=s.startswith("00") or not s.isdigit() or len(s)>4 or "ETF" in str(n).upper() or "基金" in str(n)
  out.append({"symbol":s,"name":n,"exchange":exchange,"asset_class":"etf" if is_etf else "stock","price":price,"previous_close":prev,"change":chg,"change_percent":chg/prev*100 if chg is not None and prev else None,"open":num(x.get("OpeningPrice") or x.get("Open")),"high":num(x.get("HighestPrice") or x.get("High")),"low":num(x.get("LowestPrice") or x.get("Low")),"volume":num(x.get("TradeVolume") or x.get("TradingShares") or x.get("TradingVolume")),"trade_value":num(x.get("TradeValue") or x.get("TransactionAmount")),"quote_date":NOW.date().isoformat(),"quote_time":NOW.strftime("%H:%M"),"status":"official-close"})
 return out
def main():
 old=read_json(DATA/"tw-market.json",{"items":[]});rows=[];warn=[]
 for url,ex in [("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL","TWSE"),("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes","TPEx")]:
  try:rows+=fetch(url,ex)
  except Exception as e:warn.append(f"{ex}:{e}")
 if len(rows)<100:rows=old.get("items",[])
 up=sum((x.get("change_percent") or 0)>0 for x in rows);down=sum((x.get("change_percent") or 0)<0 for x in rows);payload={"metadata":{"version":"v11.3.0","updated_at":NOW.isoformat(timespec="seconds"),"trading_date":NOW.date().isoformat(),"market_status":"official-close","source":"TWSE／TPEx official open data","warnings":warn},"breadth":{"up":up,"down":down,"flat":len(rows)-up-down},"items":rows};write_payload("tw-market.json","__TW_MARKET_SEED__",payload)
if __name__=="__main__":main()
