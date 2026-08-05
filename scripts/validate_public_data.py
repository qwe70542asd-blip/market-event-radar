#!/usr/bin/env python3
from __future__ import annotations
import json,sys,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/"data"

def load(name):return json.loads((DATA/name).read_text(encoding="utf-8"))
def fail(message):raise SystemExit(message)

def market():
 p=load("market-snapshot.json")
 for row in p.get("items",[]):
  price=row.get("price");prev=row.get("previous_close");change=row.get("change");pct=row.get("change_percent")
  if price is not None and prev is not None:
   exp=price-prev
   if change is None or abs(change-exp)>max(1e-6,abs(exp)*1e-8):fail(f"bad market change {row.get('symbol')}")
   ep=exp/prev*100 if prev else None
   if ep is not None and (pct is None or abs(pct-ep)>1e-7):fail(f"bad market percent {row.get('symbol')}")
  for c in row.get("candles") or []:
   o,h,l,cl=(c.get(k) for k in ("open","high","low","close"))
   if None in (o,h,l,cl) or h<max(o,cl) or l>min(o,cl):fail(f"bad candle {row.get('symbol')} {c.get('date')}")

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
  if str(row.get("industry") or "").isdigit():fail(f"industry code exposed {s}")

if __name__=="__main__":
 scope=sys.argv[1] if len(sys.argv)>1 else "all"
 if scope in {"all","market"}:market()
 if scope in {"all","events"}:events()
 if scope in {"all","basics"}:basics()
 if scope in {"all","news"}:
  for path in sorted(DATA.glob("news-*.json")):news(path.name)
  if (DATA/"stock-news.json").exists():news("stock-news.json")
 print("validation ok",scope)
