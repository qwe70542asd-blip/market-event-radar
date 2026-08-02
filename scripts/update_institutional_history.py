#!/usr/bin/env python3
"""Update TWSE institutional history and stock rankings for v10.6.0."""
from __future__ import annotations
import json, re, time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "institutional-history.json"
SEED = DATA / "institutional-history-seed.js"
TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime.now(TAIPEI)
HEADERS = {
    "User-Agent":"Mozilla/5.0 (compatible; MarketEventRadar/10.6.0; +https://github.com/qwe70542asd-blip/market-event-radar)",
    "Accept-Language":"zh-TW,zh;q=0.9,en;q=0.8",
    "Referer":"https://www.twse.com.tw/zh/trading/foreign/bfi82u.html",
}
BFI82U = "https://www.twse.com.tw/rwd/zh/fund/BFI82U"
T86 = "https://www.twse.com.tw/rwd/zh/fund/T86"


def read_json(path: Path, default: Any) -> Any:
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError,json.JSONDecodeError): return default


def clean(value: Any) -> str:
    return re.sub(r"\s+"," ",str(value or "")).strip()


def number(value: Any) -> float | None:
    text=clean(value).replace(",","")
    try: return float(text)
    except ValueError: return None


def request_json(session: requests.Session, url: str, params: dict[str,Any], attempts: int=3) -> dict[str,Any]:
    error=None
    for attempt in range(attempts):
        try:
            response=session.get(url,params=params,headers=HEADERS,timeout=25)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            error=exc
            if attempt+1<attempts: time.sleep(1.0*(attempt+1))
    raise error


def row_amount(row: list[Any]) -> dict[str,float|None]:
    buy=number(row[1]) if len(row)>1 else None
    sell=number(row[2]) if len(row)>2 else None
    net=number(row[3]) if len(row)>3 else None
    return {
        "buy": buy/1e8 if buy is not None else None,
        "sell": sell/1e8 if sell is not None else None,
        "net": net/1e8 if net is not None else None,
    }


def add_amount(*parts: dict[str,float|None]) -> dict[str,float|None]:
    result={}
    for key in ("buy","sell","net"):
        values=[part.get(key) for part in parts if part.get(key) is not None]
        result[key]=sum(values) if values else None
    return result


def parse_bfi(payload: dict[str,Any], requested: date) -> dict[str,Any] | None:
    rows=payload.get("data") or []
    if not rows: return None
    mapped={clean(row[0]):row_amount(row) for row in rows if row}
    dealer_self=next((value for key,value in mapped.items() if "自行買賣" in key),{"buy":None,"sell":None,"net":None})
    dealer_hedge=next((value for key,value in mapped.items() if "避險" in key),{"buy":None,"sell":None,"net":None})
    trust=next((value for key,value in mapped.items() if "投信" in key),{"buy":None,"sell":None,"net":None})
    foreign=next((value for key,value in mapped.items() if "外資及陸資" in key),{"buy":None,"sell":None,"net":None})
    total=next((value for key,value in mapped.items() if key=="合計"),add_amount(foreign,trust,dealer_self,dealer_hedge))
    title=clean(payload.get("title"))
    match=re.search(r"(\d{3})年(\d{2})月(\d{2})日",title)
    reported=date(int(match.group(1))+1911,int(match.group(2)),int(match.group(3))) if match else requested
    return {
        "date":reported.isoformat(),
        "foreign":foreign,
        "investment_trust":trust,
        "dealer_self":dealer_self,
        "dealer_hedge":dealer_hedge,
        "dealer":add_amount(dealer_self,dealer_hedge),
        "total":total,
        "source":"TWSE BFI82U",
    }


def fetch_history(session: requests.Session, days: int=105) -> list[dict[str,Any]]:
    rows=[]
    start=NOW.date()-timedelta(days=days)
    current=start
    while current<=NOW.date():
        if current.weekday()<5:
            try:
                payload=request_json(session,BFI82U,{"response":"json","type":"day","dayDate":current.strftime("%Y%m%d")},attempts=2)
                parsed=parse_bfi(payload,current)
                if parsed and parsed["date"]==current.isoformat(): rows.append(parsed)
            except Exception as exc:
                print("warning BFI82U",current,exc)
            time.sleep(0.07)
        current+=timedelta(days=1)
    dedup={row["date"]:row for row in rows}
    return [dedup[key] for key in sorted(dedup)]


def find_index(fields: list[str], include: list[str], exclude: list[str]|None=None) -> int | None:
    exclude=exclude or []
    for index,field in enumerate(fields):
        text=clean(field)
        if all(token in text for token in include) and not any(token in text for token in exclude): return index
    return None


def cell(row: list[Any], index: int|None) -> float:
    value=number(row[index]) if index is not None and index<len(row) else None
    return value or 0


def parse_t86(payload: dict[str,Any], reported_date: str) -> dict[str,Any]:
    fields=[clean(value) for value in payload.get("fields") or []]
    rows=payload.get("data") or []
    symbol_i=find_index(fields,["證券代號"])
    name_i=find_index(fields,["證券名稱"])
    indexes={
        "foreign":{"buy":find_index(fields,["外陸資買進"],["自營商"]),"sell":find_index(fields,["外陸資賣出"],["自營商"]),"net":find_index(fields,["外陸資買賣超"],["自營商"])},
        "investment_trust":{"buy":find_index(fields,["投信買進"]),"sell":find_index(fields,["投信賣出"]),"net":find_index(fields,["投信買賣超"])},
        "dealer":{"buy":None,"sell":None,"net":find_index(fields,["自營商買賣超股數"],["自行買賣","避險"])},
        "total":{"buy":None,"sell":None,"net":find_index(fields,["三大法人買賣超股數"])},
    }
    dealer_buy=[find_index(fields,["自營商買進股數","自行買賣"]),find_index(fields,["自營商買進股數","避險"])]
    dealer_sell=[find_index(fields,["自營商賣出股數","自行買賣"]),find_index(fields,["自營商賣出股數","避險"])]
    parsed={key:[] for key in indexes}
    for row in rows:
        symbol=clean(row[symbol_i]) if symbol_i is not None and symbol_i<len(row) else ""
        name=clean(row[name_i]) if name_i is not None and name_i<len(row) else ""
        if not symbol: continue
        for key,idx in indexes.items():
            buy=cell(row,idx["buy"])
            sell=cell(row,idx["sell"])
            if key=="dealer":
                buy=sum(cell(row,i) for i in dealer_buy)
                sell=sum(cell(row,i) for i in dealer_sell)
            net=cell(row,idx["net"])
            parsed[key].append({"symbol":symbol,"name":name,"buy":buy,"sell":sell,"net":net})
    rankings={}
    for key,items in parsed.items():
        rankings[key]={
            "buys":sorted(items,key=lambda item:item["net"],reverse=True)[:10],
            "sells":sorted(items,key=lambda item:item["net"])[:10],
        }
    return rankings


def fetch_rankings(session: requests.Session, dates: list[str]) -> tuple[str|None,dict[str,Any]]:
    for date_text in reversed(dates[-10:]):
        for select_type in ("ALLBUT0999","01"):
            try:
                payload=request_json(session,T86,{"response":"json","date":date_text.replace("-",""),"selectType":select_type},attempts=2)
                if payload.get("data"):
                    return date_text,parse_t86(payload,date_text)
            except Exception as exc:
                print("warning T86",date_text,select_type,exc)
        time.sleep(0.1)
    return None,{}


def main() -> int:
    DATA.mkdir(parents=True,exist_ok=True)
    previous=read_json(OUT,{"daily":[],"rankings":{}})
    session=requests.Session()
    history=fetch_history(session)
    if not history:
        history=previous.get("daily",[])
    ranking_date,rankings=fetch_rankings(session,[row["date"] for row in history]) if history else (None,{})
    if not rankings:
        rankings=previous.get("rankings",{})
        ranking_date=previous.get("ranking_date")
    payload={
        "metadata":{
            "version":"v10.6.0",
            "updated_at":NOW.isoformat(timespec="seconds"),
            "latest_date":history[-1]["date"] if history else None,
            "history_count":len(history),
            "mode":"live" if history else "seed",
            "source":"TWSE BFI82U + T86",
            "license_note":"個別券商分點不包含於免費報表，需另購授權資料。",
        },
        "daily":history,
        "ranking_date":ranking_date,
        "rankings":rankings,
    }
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEED.write_text("window.__INSTITUTIONAL_HISTORY_SEED__ = "+json.dumps(payload,ensure_ascii=False,indent=2)+";\n",encoding="utf-8")
    print("history",len(history),"ranking date",ranking_date)
    return 0

if __name__=="__main__": raise SystemExit(main())
