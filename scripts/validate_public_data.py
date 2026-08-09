#!/usr/bin/env python3
from __future__ import annotations
import json,sys,re
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/"data"

def load(name):return json.loads((DATA/name).read_text(encoding="utf-8"))
def fail(message):raise SystemExit(message)
def iso_day(value):
 try:return date.fromisoformat(str(value))
 except Exception:return None

def market():
 p=load("market-snapshot.json")
 for row in p.get("items",[]):
  price=row.get("price");prev=row.get("previous_close");change=row.get("change");pct=row.get("change_percent")
  if price is not None and prev is not None:
   exp=price-prev
   if change is None or abs(change-exp)>max(1e-6,abs(exp)*1e-8):fail(f"bad market change {row.get('symbol')}")
   ep=exp/prev*100 if prev else None
   if ep is not None and (pct is None or abs(pct-ep)>1e-7):fail(f"bad market percent {row.get('symbol')}")
  o,h,l,cl=(row.get(k) for k in ("open","high","low","close"))
  if None not in (o,h,l,cl):
   if h<max(o,cl) or l>min(o,cl) or (price is not None and not l<=price<=h):fail(f"mixed-session market row {row.get('symbol')}")
  dates=[row.get(k) for k in ("session_date","price_date","ohlc_date") if row.get(k)]
  if dates and len(set(dates))!=1:fail(f"mixed-session dates {row.get('symbol')}")
  market_at_local=str(row.get("market_at_local") or "")[:10]
  if dates and market_at_local and re.fullmatch(r"\d{4}-\d{2}-\d{2}",market_at_local) and market_at_local!=dates[0]:
   fail(f"market local timestamp/session mismatch {row.get('symbol')}: {market_at_local} != {dates[0]}")
  candles=row.get("candles") or []
  for c in candles:
   o,h,l,cl=(c.get(k) for k in ("open","high","low","close"))
   if None in (o,h,l,cl) or h<max(o,cl) or l>min(o,cl):fail(f"bad candle {row.get('symbol')} {c.get('date')}")
  if dates and candles:
   latest=max((str(c.get("date")) for c in candles if c.get("date")),default="")
   if latest and latest>str(dates[0]):fail(f"top-level market session older than candle {row.get('symbol')}: {dates[0]} < {latest}")

 tw=load("tw-market.json")
 meta=tw.get("metadata") or {}; trading=str(meta.get("trading_date") or "")
 items=tw.get("items") or []
 if items and trading:
  day=iso_day(trading)
  if not day or day.weekday()>=5:fail(f"invalid Taiwan trading date {trading}")
  for row in items:
   q=str(row.get("quote_date") or "")
   if q and q!=trading:fail(f"Taiwan quote date mismatch {row.get('symbol')}: {q} != {trading}")

 hist=load("market-volume-history.json")
 rows=hist.get("items") or []
 if rows:
  seen=set(); complete=[]
  for row in rows:
   raw=str(row.get("date") or ""); day=iso_day(raw)
   if not day or day.weekday()>=5:fail(f"invalid turnover session {raw}")
   if raw in seen:fail(f"duplicate turnover session {raw}")
   seen.add(raw)
   if trading and raw>trading:fail(f"turnover newer than trading date {raw}>{trading}")
   if row.get("complete_total") is True:
    complete.append(day)
   if row.get("total_coverage")=="partial-single-market" and row.get("complete_total") is True:
    fail(f"partial turnover marked complete {raw}")
  if meta.get("volume_history_complete") is True:
   complete=sorted(set(complete),reverse=True)
   if len(complete)<21 or (complete[0]-complete[20]).days>45:
    fail("volume_history_complete true without 20-session recent complete totals")

def events():
 p=load("events.json")
 for row in p.get("events",[]):
  if row.get("origin") in {"twse-material","tpex-material"}:
   if row.get("event_type")=="financial-report" and row.get("date_basis") not in {"explicit-labeled-date","official-announcement-date"}:fail(f"unverified financial date {row.get('id')}")
   desc=str(row.get("description") or "")
   if row.get("target_date")=="2026-01-01" and "起訖日期" in desc and str(row.get("source_published_at") or "")[:10]>"2026-01-02":fail(f"period start leaked into event date {row.get('id')}")

def news(name):
 p=load(name);master=load("stock-basics.json").get("items") or {};valid=set(master)
 for row in p.get("items",[]):
  invalid=[s for s in row.get("symbols") or [] if s not in valid]
  if invalid:fail(f"invalid news symbols {name}: {invalid} {row.get('title')}")

def basics():
 p=load("stock-basics.json")
 for s,row in (p.get("items") or {}).items():
  if "financial_coverage_percent" not in row:fail(f"missing financial coverage {s}")
  for field in ("industry","industry_name"):
   if str(row.get(field) or "").isdigit():fail(f"industry code exposed {s} {field}={row.get(field)}")
  code=str(row.get("industry_code") or "")
  if code and (not code.isdigit() or len(code)>2):fail(f"invalid industry_code {s}: {code}")

if __name__=="__main__":
 scope=sys.argv[1] if len(sys.argv)>1 else "all"
 if scope in {"all","market"}:market()
 if scope in {"all","events"}:events()
 if scope in {"all","basics"}:basics()
 if scope in {"all","news"}:
  for path in sorted(DATA.glob("news-*.json")):news(path.name)
  if (DATA/"stock-news.json").exists():news("stock-news.json")
 print("validation ok",scope)
