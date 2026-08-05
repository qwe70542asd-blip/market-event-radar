#!/usr/bin/env python3
from __future__ import annotations
import json
from typing import Any
from common import DATA,NOW,read_json
VERSION="v11.4.8"

def num(v:Any)->float|None:
 try:
  if v is None or str(v).strip() in {"","-","—"}:return None
  return float(str(v).replace(",",""))
 except (TypeError,ValueError):return None

def close(a:Any,b:Any,tol:float=.005)->bool:
 x,y=num(a),num(b)
 if x is None or y is None:return False
 return abs(x-y)<=max(abs(x),abs(y),1)*tol

def latest(rows:list[dict],key:str="period")->dict:
 return sorted((r for r in rows or [] if r.get(key)),key=lambda r:str(r.get(key)),reverse=True)[0] if rows else {}

def main()->None:
 assets=read_json(DATA/"assets.json",{"assets":[]}).get("assets",[])
 market=read_json(DATA/"tw-market.json",{"items":[]}).get("items",[])
 revenue=read_json(DATA/"monthly-revenue.json",{"items":{}}).get("items",{})
 dividends=read_json(DATA/"dividend-history.json",{"items":{}}).get("items",{})
 secondary=read_json(DATA/"secondary-reference.json",{"items":{}}).get("items",{})
 quotes={str(r.get("symbol") or "").upper():r for r in market}
 output={};counts={"official":0,"multi_source":0,"reference":0,"conflict":0,"missing":0,"expired":0}
 for asset in assets:
  symbol=str(asset.get("symbol") or "").upper()
  if not symbol or asset.get("market")!="TW":continue
  fields={};official_quote=quotes.get(symbol) or {};secondary_quote=secondary.get(symbol) or {}
  op=num(official_quote.get("price"));sp=num(secondary_quote.get("price"))
  if op is not None:
   if sp is not None and close(op,sp,.01):status="multi_source";sources=["TWSE／TPEx official close","Yahoo Finance chart"]
   elif sp is not None and not close(op,sp,.03):status="conflict";sources=["TWSE／TPEx official close","Yahoo Finance chart"]
   else:status="official";sources=["TWSE／TPEx official close"]
  elif sp is not None:status="reference";sources=["Yahoo Finance chart"]
  else:status="missing";sources=[]
  fields["quote"]={"status":status,"sources":sources,"official_value":op,"reference_value":sp}
  embedded_rev=latest(asset.get("monthly_revenue") or []);channel_rev=latest((revenue.get(symbol) or {}).get("rows") or revenue.get(symbol) or [])
  er,cr=num(embedded_rev.get("revenue")),num(channel_rev.get("revenue"))
  if er is not None and cr is not None:rs="multi_source" if close(er,cr,.001) else "conflict"
  elif er is not None or cr is not None:rs="official"
  else:rs="missing"
  fields["monthly_revenue"]={"status":rs,"sources":[s for s in [embedded_rev.get("source"),channel_rev.get("source")] if s],"period":channel_rev.get("period") or embedded_rev.get("period"),"values":[v for v in [er,cr] if v is not None]}
  embedded_div=latest(asset.get("dividends") or []);channel_div=latest((dividends.get(symbol) or {}).get("rows") or dividends.get(symbol) or [])
  ed,cd=num(embedded_div.get("cash")),num(channel_div.get("cash"))
  if ed is not None and cd is not None:ds="multi_source" if close(ed,cd,.001) else "conflict"
  elif ed is not None or cd is not None:ds="official"
  else:ds="missing"
  fields["dividends"]={"status":ds,"sources":[s for s in [embedded_div.get("source"),channel_div.get("source")] if s],"period":channel_div.get("period") or embedded_div.get("period"),"values":[v for v in [ed,cd] if v is not None]}
  metric_sources=asset.get("metric_sources") or {};available_metrics=[k for k,v in (asset.get("metrics") or {}).items() if num(v) is not None]
  fields["metrics"]={"status":"official" if available_metrics else "missing","sources":sorted(set(str(metric_sources.get(k) or "official financial data") for k in available_metrics)),"available":available_metrics}
  statuses=[f["status"] for f in fields.values()]
  overall="conflict" if "conflict" in statuses else "multi_source" if "multi_source" in statuses else "official" if "official" in statuses else "reference" if "reference" in statuses else "missing"
  counts[overall]=counts.get(overall,0)+1
  suffix="TWO" if str(asset.get("exchange") or "").upper()=="TPEX" else "TW"
  output[symbol]={"symbol":symbol,"overall":overall,"fields":fields,"reference_links":{"yahoo":f"https://tw.stock.yahoo.com/quote/{symbol}.{suffix}","goodinfo":f"https://goodinfo.tw/tw/StockDetail.asp?STOCK_ID={symbol}"},"updated_at":NOW.isoformat(timespec="seconds")}
 payload={"metadata":{"version":VERSION,"updated_at":NOW.isoformat(timespec="seconds"),"status":"partial" if counts.get("conflict") or counts.get("missing") else "ok","counts":counts,"note":"Official data is primary. Secondary values are used only as references or when official quotes are missing; conflicts are never auto-resolved."},"items":output}
 (DATA/"data-verification.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (DATA/"data-verification-seed.js").write_text("window.__DATA_VERIFICATION_SEED__="+json.dumps(payload,ensure_ascii=False,separators=(",",":"))+";\n",encoding="utf-8")
 print(payload["metadata"])
if __name__=="__main__":main()
