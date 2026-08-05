#!/usr/bin/env python3
"""Progressively collect Yahoo Taiwan / Yahoo Finance detail references.

Official TWSE/TPEx/MOPS values remain primary. This channel fills gaps only and
stores source/time metadata so the frontend can label the value as a reference.
The updater is deliberately low-concurrency and retains the last successful row.
"""
from __future__ import annotations
import json, time, random
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from typing import Any
import requests
from common import DATA, NOW, read_json, write_payload

VERSION="v11.4.7"
HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36","Accept":"application/json,text/plain,*/*","Accept-Language":"zh-TW,zh;q=0.9,en;q=0.6"}
BATCH=30
TIMEOUT=22
SESSION=requests.Session();SESSION.headers.update(HEADERS)

def raw(v:Any)->Any:
 if isinstance(v,dict):
  for k in ("raw","fmt","longFmt"):
   if k in v:return v[k]
 return v

def num(v:Any)->float|None:
 v=raw(v)
 try:
  if v is None or str(v).strip() in {"","-","--","N/A"}:return None
  return float(str(v).replace(",",""))
 except (ValueError,TypeError):return None

def text(v:Any)->str|None:
 v=raw(v)
 if v is None:return None
 s=str(v).strip();return s or None

def ticker(asset:dict)->str:
 return f"{asset.get('symbol')}.{'TWO' if str(asset.get('exchange') or '').upper()=='TPEX' else 'TW'}"

def get_json(url:str)->dict:
 r=SESSION.get(url,timeout=TIMEOUT);r.raise_for_status();return r.json()

def quote_summary(tk:str,etf:bool)->dict:
 modules=["price","summaryDetail","defaultKeyStatistics","financialData","assetProfile","calendarEvents","majorHoldersBreakdown"]
 if etf:modules += ["fundProfile","topHoldings"]
 url=f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{tk}?modules={','.join(modules)}&formatted=false&lang=zh-Hant-TW&region=TW"
 p=get_json(url);return (((p.get("quoteSummary") or {}).get("result") or [{}])[0]) or {}

def timeseries(tk:str)->dict[str,list[dict]]:
 end=int(datetime.now(timezone.utc).timestamp());start=int((datetime.now(timezone.utc)-timedelta(days=365*6)).timestamp())
 types=["quarterlyTotalRevenue","quarterlyGrossProfit","quarterlyOperatingIncome","quarterlyPretaxIncome","quarterlyNetIncome","quarterlyDilutedEPS","quarterlyBasicEPS","quarterlyTotalAssets","quarterlyTotalLiabilitiesNetMinorityInterest","quarterlyStockholdersEquity","quarterlyCurrentAssets","quarterlyCurrentLiabilities","quarterlyOperatingCashFlow","quarterlyCapitalExpenditure","quarterlyFreeCashFlow"]
 url=f"https://query2.finance.yahoo.com/ws/fundamentals-timeseries/v1/finance/timeseries/{tk}?symbol={tk}&type={','.join(types)}&period1={start}&period2={end}&lang=zh-Hant-TW&region=TW"
 try:p=get_json(url)
 except Exception:return {}
 out={}
 for block in ((p.get("timeseries") or {}).get("result") or []):
  meta=block.get("meta") or {};typ=(meta.get("type") or [None])[0]
  if typ:out[typ]=block.get(typ) or []
 return out

def financial_rows(series:dict)->list[dict]:
 aliases={"quarterlyTotalRevenue":"revenue","quarterlyGrossProfit":"gross_profit","quarterlyOperatingIncome":"operating_income","quarterlyPretaxIncome":"pretax_income","quarterlyNetIncome":"net_income","quarterlyDilutedEPS":"eps","quarterlyBasicEPS":"eps","quarterlyTotalAssets":"total_assets","quarterlyTotalLiabilitiesNetMinorityInterest":"total_liabilities","quarterlyStockholdersEquity":"total_equity","quarterlyCurrentAssets":"current_assets","quarterlyCurrentLiabilities":"current_liabilities","quarterlyOperatingCashFlow":"operating_cash_flow","quarterlyCapitalExpenditure":"capital_expenditure","quarterlyFreeCashFlow":"free_cash_flow"}
 rows={}
 for typ,field in aliases.items():
  for item in series.get(typ,[]):
   date=item.get("asOfDate") or item.get("date")
   if not date:continue
   value=num(item.get("reportedValue"))
   if value is None:continue
   d=str(date);period=d
   try:
    y,m=map(int,d[:7].split("-"));period=f"{y}Q{(m-1)//3+1}"
   except Exception:pass
   rows.setdefault(d,{"date":d,"period":period,"source":"Yahoo Finance fundamentals"})[field]=value
 out=sorted(rows.values(),key=lambda x:x["date"],reverse=True)
 for row in out:
  assets=row.get("total_assets");liab=row.get("total_liabilities");equity=row.get("total_equity");rev=row.get("revenue");net=row.get("net_income");ca=row.get("current_assets");cl=row.get("current_liabilities")
  if assets not in (None,0) and liab is not None:row["debt_ratio"]=liab/assets*100
  if equity not in (None,0) and net is not None:row["roe"]=net/equity*100
  if assets not in (None,0) and net is not None:row["roa"]=net/assets*100
  if rev not in (None,0) and net is not None:row["net_margin"]=net/rev*100
  if ca is not None and cl not in (None,0):row["current_ratio"]=ca/cl*100
 return out[:20]

def chart_reference(tk:str)->tuple[list[dict],dict]:
 url=f"https://query1.finance.yahoo.com/v8/finance/chart/{tk}?range=20y&interval=1d&events=div%2Csplits&lang=zh-Hant-TW&region=TW"
 try:p=get_json(url);result=(((p.get("chart") or {}).get("result") or [{}])[0]) or {}
 except Exception:return [],{}
 meta=result.get("meta") or {}
 events=((result.get("events") or {}).get("dividends") or {})
 out=[]
 for item in events.values():
  stamp=item.get("date");amount=num(item.get("amount"))
  if stamp and amount is not None:d=datetime.fromtimestamp(int(stamp),timezone.utc).date().isoformat();out.append({"date":d,"ex_date":d,"period":d[:4],"year":d[:4],"cash":amount,"cash_dividend":amount,"source":"Yahoo Finance dividend event","url":f"https://tw.stock.yahoo.com/quote/{tk}/dividend"})
 return sorted(out,key=lambda x:x["date"],reverse=True),meta

def parse_one(asset:dict)->tuple[str,dict|None,str|None]:
 symbol=str(asset.get("symbol") or "").upper();tk=ticker(asset);etf=asset.get("asset_class")=="etf"
 try:
  source_errors=[]
  try:q=quote_summary(tk,etf)
  except Exception as exc:q={};source_errors.append(f"quoteSummary: {exc}")
  time.sleep(random.uniform(.15,.45))
  series={} if etf else timeseries(tk);time.sleep(random.uniform(.15,.45))
  divs,chart_meta=chart_reference(tk)
  if not q and not series and not divs:raise ValueError("; ".join(source_errors) or "all Yahoo references empty")
  price=q.get("price") or {};profile=q.get("assetProfile") or {};summary=q.get("summaryDetail") or {};stats=q.get("defaultKeyStatistics") or {};financial=q.get("financialData") or {};calendar=q.get("calendarEvents") or {};holders=q.get("majorHoldersBreakdown") or {};fund=q.get("fundProfile") or {};top=q.get("topHoldings") or {}
  if not price:
   price={"longName":chart_meta.get("longName"),"shortName":chart_meta.get("shortName"),"currency":chart_meta.get("currency"),"quoteType":chart_meta.get("instrumentType")}
  officers=profile.get("companyOfficers") or []
  officer=lambda title: next((text(x.get("name")) for x in officers if title.lower() in str(x.get("title") or "").lower()),None)
  financials=financial_rows(series)
  latest=financials[0] if financials else {}
  metrics={
   "pe":num(summary.get("trailingPE")) or num(stats.get("trailingPE")),"forward_pe":num(summary.get("forwardPE")),"pb":num(stats.get("priceToBook")),"dividend_yield":((num(summary.get("dividendYield")) or 0)*100 if num(summary.get("dividendYield")) is not None and num(summary.get("dividendYield"))<1 else num(summary.get("dividendYield"))),"eps":num(stats.get("trailingEps")) or num(financial.get("epsTrailingTwelveMonths")) or latest.get("eps"),"book_value":num(stats.get("bookValue")),"market_cap":num(price.get("marketCap")),"roe":num(financial.get("returnOnEquity")),"roa":num(financial.get("returnOnAssets")),"gross_margin":num(financial.get("grossMargins")),"operating_margin":num(financial.get("operatingMargins")),"net_margin":num(financial.get("profitMargins")),"debt_to_equity":num(financial.get("debtToEquity")),"current_ratio":num(financial.get("currentRatio")),"free_cash_flow":num(financial.get("freeCashflow")),"operating_cash_flow":num(financial.get("operatingCashflow")),"shares_outstanding":num(stats.get("sharesOutstanding"))}
  for k in ("roe","roa","gross_margin","operating_margin","net_margin"):
   if metrics[k] is not None and abs(metrics[k])<=1:metrics[k]*=100
  if metrics.get("current_ratio") is not None and abs(metrics["current_ratio"])<20:metrics["current_ratio"]*=100
  if metrics.get("roe") is None:metrics["roe"]=latest.get("roe")
  if metrics.get("roa") is None:metrics["roa"]=latest.get("roa")
  if metrics.get("net_margin") is None:metrics["net_margin"]=latest.get("net_margin")
  metrics["debt_ratio"]=latest.get("debt_ratio")
  profile_out={"company_name":text(price.get("longName")) or text(price.get("shortName")),"industry":text(profile.get("industry")),"sector":text(profile.get("sector")),"website":text(profile.get("website")),"address":" ".join(filter(None,[text(profile.get("address1")),text(profile.get("city")),text(profile.get("country"))])),"phone":text(profile.get("phone")),"business_summary":text(profile.get("longBusinessSummary")),"employees":num(profile.get("fullTimeEmployees")),"chairperson":officer("chair"),"general_manager":officer("chief executive") or officer("general manager"),"market_cap":num(price.get("marketCap")),"currency":text(price.get("currency")),"quote_type":text(price.get("quoteType"))}
  etf_out={}
  if etf:
   fees=(fund.get("feesExpensesInvestment") or {})
   holdings=[]
   for h in top.get("holdings") or []:
    sym=text(h.get("symbol"));name=text(h.get("holdingName"));weight=num(h.get("holdingPercent"));
    if sym or name:holdings.append({"symbol":sym,"name":name,"weight":weight*100 if weight is not None and abs(weight)<=1 else weight,"source":"Yahoo Finance top holdings"})
   sectors=[]
   for row in top.get("sectorWeightings") or []:
    if isinstance(row,dict):
     for k,v in row.items():
      n=num(v);sectors.append({"sector":k,"weight":n*100 if n is not None and abs(n)<=1 else n})
   etf_out={"category":text(fund.get("categoryName")),"family":text(fund.get("family")),"issuer":text(fund.get("family")),"legal_type":text(fund.get("legalType")),"management_fee":num(fees.get("annualReportExpenseRatio")),"holdings":holdings[:20],"sector_allocation":sectors,"source":"Yahoo Finance fund profile"}
  row={"symbol":symbol,"ticker":tk,"asset_class":"etf" if etf else "stock","source":"Yahoo 股市 / Yahoo Finance","source_status":"partial" if source_errors else "ok","source_errors":source_errors,"source_url":f"https://tw.stock.yahoo.com/quote/{tk}","updated_at":NOW.isoformat(timespec="seconds"),"profile":profile_out,"metrics":{k:v for k,v in metrics.items() if v is not None},"financials":financials,"dividends":divs,"calendar":{"earnings_date":text(((calendar.get("earnings") or {}).get("earningsDate") or [None])[0]),"ex_dividend_date":text(calendar.get("exDividendDate")),"dividend_date":text(calendar.get("dividendDate"))},"holders":{k:num(v) for k,v in holders.items() if num(v) is not None},"etf":etf_out}
  return symbol,row,None
 except Exception as exc:return symbol,None,str(exc)

def main()->None:
 assets=read_json(DATA/"assets.json",{"assets":[]}).get("assets",[]);old=read_json(DATA/"yahoo-details.json",{"items":{},"state":{}});items=dict(old.get("items") or {});state=dict(old.get("state") or {})
 candidates=[a for a in assets if a.get("market")=="TW" and a.get("asset_class") in {"stock","etf"} and a.get("symbol")];candidates.sort(key=lambda a:(a.get("asset_class")!="stock",str(a.get("symbol"))))
 cursor=int(state.get("cursor") or 0);cursor=cursor if cursor<len(candidates) else 0;batch=candidates[cursor:cursor+BATCH]
 if len(batch)<BATCH:batch+=candidates[:BATCH-len(batch)]
 success=0;errors=[]
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(parse_one,a) for a in batch]
  for f in as_completed(futures):
   symbol,row,error=f.result()
   if row:items[symbol]=row;success+=1
   elif error:errors.append({"symbol":symbol,"error":error[:240]})
 next_cursor=(cursor+len(batch))%len(candidates) if candidates else 0
 payload={"metadata":{"version":VERSION,"updated_at":NOW.isoformat(timespec="seconds"),"status":"ok" if success==len(batch) and success else "partial" if success or items else "warning","item_count":len(items),"batch_size":len(batch),"batch_success":success,"note":"Official values remain primary. Yahoo data fills missing fields and is labeled as a reference."},"state":{"cursor":next_cursor,"last_batch_at":NOW.isoformat(timespec="seconds")},"errors":errors[:80],"items":items}
 write_payload("yahoo-details.json","__YAHOO_DETAILS_SEED__",payload);print(payload["metadata"])
if __name__=="__main__":main()
