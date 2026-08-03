#!/usr/bin/env python3
"""Refresh official Taiwan institutional, margin and short-balance data.

Data sources:
- TWSE T86: listed-stock institutional trading by date.
- TWSE MI_MARGN: listed-stock margin/short balances by date.
- TPEx OpenAPI: latest OTC institutional and margin/short details.

The output keeps up to 20 verified trading-date snapshots so the web page can
work as a query page instead of showing only one hard-coded table.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date as date_type
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
    "User-Agent":"Mozilla/5.0 (compatible; MarketEventRadar/11.2.7)",
    "Accept":"application/json,text/plain,*/*",
    "Accept-Language":"zh-TW,zh;q=0.9",
}
TWSE_T86="https://www.twse.com.tw/rwd/zh/fund/T86"
TWSE_MARGIN="https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
TPEX_INST="https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading"
TPEX_MARGIN="https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance"
TWSE_DAY_TRADE="https://openapi.twse.com.tw/v1/exchangeReport/TWTB4U"
TPEX_DAY_TRADE="https://www.tpex.org.tw/openapi/v1/tpex_intraday_trading_statistics"
REQUEST_TIMEOUT=10
HISTORY_LIMIT=20


def number(value):
    try:
        text=str(value).replace(",","").replace("%","").replace("＋","+").strip()
        if text in {"","--","-","None","null","N/A"}:
            return None
        return float(text)
    except Exception:
        return None


def integer(value):
    result=number(value)
    return int(result) if result is not None else None


def normalize_date(value):
    text=str(value or "").strip().replace("/","").replace("-","")
    if re.fullmatch(r"\d{8}",text):
        return text
    # ROC dates such as 1150727 or 115/07/27
    if re.fullmatch(r"\d{7}",text):
        year=int(text[:3])+1911
        return f"{year:04d}{text[3:]}"
    return None


def candidate_trade_dates(days: int=7):
    current=NOW.date()
    output=[]
    while len(output)<days:
        if current.weekday()<5:
            output.append(current.strftime("%Y%m%d"))
        current-=timedelta(days=1)
    return output


def load_previous():
    try:
        payload=json.loads(OUT.read_text(encoding="utf-8"))
        return payload if isinstance(payload,dict) else {}
    except Exception:
        return {}


def first(row: dict, *keys):
    normalized={re.sub(r"\s+","",str(key)):value for key,value in row.items()}
    for key in keys:
        value=row.get(key)
        if value not in (None,""):
            return value
        value=normalized.get(re.sub(r"\s+","",key))
        if value not in (None,""):
            return value
    return None


def table_rows(payload):
    """Yield row dictionaries from both TWSE flat and table-array responses."""
    fields=payload.get("fields") or []
    data=payload.get("data") or []
    if fields and data:
        for raw in data:
            yield dict(zip(fields,raw))
    for table in payload.get("tables") or []:
        fields=table.get("fields") or []
        for raw in table.get("data") or []:
            yield dict(zip(fields,raw))


def empty_market():
    return {
        "institutional":{"foreign_net":None,"trust_net":None,"dealer_net":None,"total_net":None},
        "margin":{"previous_balance":None,"balance":None,"change":None},
        "short":{"previous_balance":None,"balance":None,"change":None},
        "day_trading":{"volume":None,"buy_amount":None,"sell_amount":None,"stock_count":0},
        "stock_count":0,
    }


def empty_item(symbol="",name="",market="twse"):
    return {
        "symbol":symbol,
        "name":name,
        "market":market,
        "foreign_buy":None,
        "foreign_sell":None,
        "foreign_net":None,
        "trust_buy":None,
        "trust_sell":None,
        "trust_net":None,
        "dealer_buy":None,
        "dealer_sell":None,
        "dealer_net":None,
        "total_net":None,
        "margin":{
            "previous_balance":None,"buy":None,"sell":None,"cash_repayment":None,
            "balance":None,"limit":None,"utilization_percent":None,
        },
        "short":{
            "previous_balance":None,"sell":None,"buy":None,"repayment":None,
            "balance":None,"limit":None,"utilization_percent":None,
        },
        "offset_shares":None,
        "day_trading":{
            "eligible":None,"volume":None,"buy_amount":None,"sell_amount":None,
            "volume_ratio_percent":None,"amount_ratio_percent":None,
        },
        "note":"",
    }


def institutional_values(row):
    dealer_direct=number(first(row,"自營商買賣超股數","自營商買賣超"))
    dealer_prop=number(first(row,"自營商買賣超股數(自行買賣)","自營商(自行買賣)買賣超股數"))
    dealer_hedge=number(first(row,"自營商買賣超股數(避險)","自營商(避險)買賣超股數"))
    dealer_net=dealer_direct
    if dealer_net is None and (dealer_prop is not None or dealer_hedge is not None):
        dealer_net=(dealer_prop or 0)+(dealer_hedge or 0)
    return {
        "foreign_buy":number(first(row,
            "外陸資買進股數(不含外資自營商)","外資及陸資買進股數(不含外資自營商)",
            "外資及陸資買進股數","ForeignInvestorsBuy","Foreign_Investors_Buy")),
        "foreign_sell":number(first(row,
            "外陸資賣出股數(不含外資自營商)","外資及陸資賣出股數(不含外資自營商)",
            "外資及陸資賣出股數","ForeignInvestorsSell","Foreign_Investors_Sell")),
        "foreign_net":number(first(row,
            "外陸資買賣超股數(不含外資自營商)","外資及陸資買賣超股數(不含外資自營商)",
            "外資買賣超股數","外資及陸資買賣超股數","ForeignInvestorsDifference",
            "Foreign_Investors_Difference")),
        "trust_buy":number(first(row,"投信買進股數","InvestmentTrustBuy","Investment_Trust_Buy")),
        "trust_sell":number(first(row,"投信賣出股數","InvestmentTrustSell","Investment_Trust_Sell")),
        "trust_net":number(first(row,"投信買賣超股數","InvestmentTrustDifference","Investment_Trust_Difference")),
        "dealer_buy":number(first(row,"自營商買進股數","DealerBuy","Dealer_Buy")),
        "dealer_sell":number(first(row,"自營商賣出股數","DealerSell","Dealer_Sell")),
        "dealer_net":dealer_net if dealer_net is not None else number(first(row,"DealerDifference","Dealer_Difference")),
        "total_net":number(first(row,"三大法人買賣超股數","合計買賣超股數","TotalDifference","Total_Difference")),
    }


def margin_values(row):
    return {
        "margin":{
            "previous_balance":integer(first(row,"融資前日餘額","前資餘額(張)","前資餘額","MarginPurchasePreviousBalance","PreviousMarginBalance")),
            "buy":integer(first(row,"融資買進","資買","MarginPurchase","MarginBuy")),
            "sell":integer(first(row,"融資賣出","資賣","MarginSales","MarginSell")),
            "cash_repayment":integer(first(row,"融資現金償還","現償","CashRedemption","CashRepayment")),
            "balance":integer(first(row,"融資今日餘額","資餘額","融資餘額","MarginPurchaseTodayBalance","TodayMarginBalance")),
            "limit":integer(first(row,"融資限額","資限額","MarginPurchaseLimit","MarginLimit")),
            "utilization_percent":number(first(row,"融資使用率","資使用率(%)","資使用率","MarginPurchaseRatio","MarginUtilization")),
        },
        "short":{
            "previous_balance":integer(first(row,"融券前日餘額","前券餘額(張)","前券餘額","ShortSalePreviousBalance","PreviousShortBalance")),
            "sell":integer(first(row,"融券賣出","券賣","ShortSale","ShortSell")),
            "buy":integer(first(row,"融券買進","券買","ShortCover","ShortBuy")),
            "repayment":integer(first(row,"融券現券償還","券償","StockRedemption","ShortRepayment")),
            "balance":integer(first(row,"融券今日餘額","券餘額","融券餘額","ShortSaleTodayBalance","TodayShortBalance")),
            "limit":integer(first(row,"融券限額","券限額","ShortSaleLimit","ShortLimit")),
            "utilization_percent":number(first(row,"融券使用率","券使用率(%)","券使用率","ShortSaleRatio","ShortUtilization")),
        },
        "offset_shares":integer(first(row,"資券互抵","資券相抵(張)","資券相抵","Offset","OffsetShares")),
        "note":str(first(row,"註記","備註","Note") or "").strip(),
    }


def day_trading_values(row):
    eligible_raw=first(
        row,"現股當沖交易標的註記","現股當沖交易標的","當沖交易標的",
        "DayTradingFlag","DayTradingEligible","暫停現股賣出後現款買進當沖註記"
    )
    eligible=None
    if eligible_raw not in (None,""):
        text=str(eligible_raw).strip().upper()
        eligible=text not in {"N","NO","否","不適用","-","0"}
    return {
        "eligible":eligible,
        "volume":integer(first(
            row,"當日沖銷交易成交股數","當沖成交股數","現股當沖成交股數",
            "DayTradingVolume","TradingVolume"
        )),
        "buy_amount":integer(first(
            row,"當日沖銷交易買進成交金額","當沖買進成交金額",
            "DayTradingBuyAmount","BuyAmount"
        )),
        "sell_amount":integer(first(
            row,"當日沖銷交易賣出成交金額","當沖賣出成交金額",
            "DayTradingSellAmount","SellAmount"
        )),
        "volume_ratio_percent":number(first(
            row,"當日沖銷交易成交股數占市場比重","當沖成交股數占比(%)",
            "DayTradingVolumeRatio","VolumeRatio"
        )),
        "amount_ratio_percent":number(first(
            row,"當日沖銷交易成交金額占市場比重","當沖成交金額占比(%)",
            "DayTradingAmountRatio","AmountRatio"
        )),
    }


def fetch_openapi_rows(session,url):
    response=session.get(url,headers=HEADERS,timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    payload=response.json()
    if isinstance(payload,list):
        return [row for row in payload if isinstance(row,dict)]
    return [row for row in (payload.get("data") or payload.get("items") or payload.get("aaData") or []) if isinstance(row,dict)]


def symbol_name(row):
    symbol=str(first(row,
        "證券代號","股票代號","代號","公司代號","SecuritiesCompanyCode",
        "SecuritiesCode","Code","股票代碼") or "").strip()
    name=str(first(row,
        "證券名稱","股票名稱","名稱","公司名稱","CompanyName","SecuritiesCompanyName",
        "Name") or "").strip()
    return symbol,name


def item_key(market,symbol):
    return f"{market}:{symbol}"


def merge_item(items,market,symbol,name="",institutional=None,margin=None,day_trading=None):
    if not symbol:
        return
    key=item_key(market,symbol)
    row=items.get(key) or empty_item(symbol,name,market)
    if name:
        row["name"]=name
    if institutional:
        for field,value in institutional.items():
            if value is not None:
                row[field]=value
    if margin:
        for section in ("margin","short"):
            for field,value in margin[section].items():
                if value is not None:
                    row[section][field]=value
        if margin.get("offset_shares") is not None:
            row["offset_shares"]=margin["offset_shares"]
        if margin.get("note"):
            row["note"]=margin["note"]
    if day_trading:
        for field,value in day_trading.items():
            if value is not None:
                row["day_trading"][field]=value
    if row.get("total_net") is None:
        values=[row.get("foreign_net"),row.get("trust_net"),row.get("dealer_net")]
        if any(value is not None for value in values):
            row["total_net"]=sum(value or 0 for value in values)
    items[key]=row


def summarize(items,market):
    rows=[row for row in items.values() if row.get("market")==market]
    result=empty_market()
    result["stock_count"]=len(rows)
    for field in ("foreign_net","trust_net","dealer_net","total_net"):
        values=[row.get(field) for row in rows if row.get(field) is not None]
        result["institutional"][field]=sum(values) if values else None
    day_rows=[row.get("day_trading") or {} for row in rows]
    for field in ("volume","buy_amount","sell_amount"):
        values=[row.get(field) for row in day_rows if row.get(field) is not None]
        result["day_trading"][field]=sum(values) if values else None
    result["day_trading"]["stock_count"]=sum(1 for row in day_rows if row.get("volume") is not None)
    for section in ("margin","short"):
        current=[row.get(section,{}).get("balance") for row in rows]
        previous=[row.get(section,{}).get("previous_balance") for row in rows]
        current=[value for value in current if value is not None]
        previous=[value for value in previous if value is not None]
        result[section]["balance"]=sum(current) if current else None
        result[section]["previous_balance"]=sum(previous) if previous else None
        if result[section]["balance"] is not None and result[section]["previous_balance"] is not None:
            result[section]["change"]=result[section]["balance"]-result[section]["previous_balance"]
    return result


def fetch_twse(session,date):
    items={}
    messages=[]
    try:
        response=session.get(
            TWSE_T86,
            params={"date":date,"selectType":"ALLBUT0999","response":"json"},
            headers=HEADERS,timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload=response.json()
        for row in table_rows(payload):
            symbol,name=symbol_name(row)
            if symbol:
                merge_item(items,"twse",symbol,name,institutional=institutional_values(row))
        if not items:
            messages.append(f"T86 {payload.get('stat') or 'empty'}")
    except Exception as exc:
        messages.append(f"T86 error: {exc}")

    try:
        response=session.get(
            TWSE_MARGIN,
            params={"date":date,"selectType":"ALL","response":"json"},
            headers=HEADERS,timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload=response.json()
        margin_rows=0
        for row in table_rows(payload):
            symbol,name=symbol_name(row)
            if not symbol or not re.fullmatch(r"[0-9A-Z]{4,7}",symbol):
                continue
            values=margin_values(row)
            if any(value is not None for section in ("margin","short") for value in values[section].values()):
                merge_item(items,"twse",symbol,name,margin=values)
                margin_rows+=1
        if not margin_rows:
            messages.append(f"MI_MARGN {payload.get('stat') or 'no individual rows'}")
    except Exception as exc:
        messages.append(f"MI_MARGN error: {exc}")

    verified=bool(items)
    return items,verified,messages


def fetch_tpex(session):
    items={}
    messages=[]
    source_date=None
    try:
        response=session.get(TPEX_INST,headers=HEADERS,timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload=response.json()
        rows=payload if isinstance(payload,list) else payload.get("data") or payload.get("items") or []
        for row in rows:
            if not isinstance(row,dict):
                continue
            symbol,name=symbol_name(row)
            if not symbol:
                continue
            source_date=source_date or normalize_date(first(row,"Date","資料日期","日期"))
            merge_item(items,"tpex",symbol,name,institutional=institutional_values(row))
        if not rows:
            messages.append("TPEx institutional empty")
    except Exception as exc:
        messages.append(f"TPEx institutional error: {exc}")

    try:
        response=session.get(TPEX_MARGIN,headers=HEADERS,timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload=response.json()
        rows=payload if isinstance(payload,list) else payload.get("data") or payload.get("items") or []
        margin_rows=0
        for row in rows:
            if not isinstance(row,dict):
                continue
            symbol,name=symbol_name(row)
            if not symbol:
                continue
            source_date=source_date or normalize_date(first(row,"Date","資料日期","日期"))
            values=margin_values(row)
            merge_item(items,"tpex",symbol,name,margin=values)
            margin_rows+=1
        if not margin_rows:
            messages.append("TPEx margin empty")
    except Exception as exc:
        messages.append(f"TPEx margin error: {exc}")

    return items,bool(items),source_date,messages


def fetch_day_trading(session):
    items={}
    messages=[]
    for market,url in (("twse",TWSE_DAY_TRADE),("tpex",TPEX_DAY_TRADE)):
        try:
            rows=fetch_openapi_rows(session,url)
            count=0
            for row in rows:
                symbol,name=symbol_name(row)
                if not symbol:
                    continue
                values=day_trading_values(row)
                if not any(value is not None for value in values.values()):
                    continue
                merge_item(items,market,symbol,name,day_trading=values)
                count+=1
            if not count:
                messages.append(f"{market} day trading empty")
        except Exception as exc:
            messages.append(f"{market} day trading error: {exc}")
    return items,messages


def write_payload(payload):
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEED.write_text(
        "window.__TW_CHIPS_SEED__ = "+json.dumps(payload,ensure_ascii=False)+";\n",
        encoding="utf-8",
    )


def main():
    previous=load_previous()
    previous_history=previous.get("history") or {}
    session=requests.Session()
    attempts=[]

    chosen_date=None
    current_items={}
    for trade_date in candidate_trade_dates():
        rows,verified,messages=fetch_twse(session,trade_date)
        attempts.append({"market":"twse","date":trade_date,"verified":verified,"messages":messages})
        if verified:
            chosen_date=trade_date
            current_items.update(rows)
            break
        time.sleep(.15)

    tpex_rows,tpex_verified,tpex_date,tpex_messages=fetch_tpex(session)
    attempts.append({"market":"tpex","date":tpex_date,"verified":tpex_verified,"messages":tpex_messages})
    if tpex_verified:
        current_items.update(tpex_rows)
        chosen_date=chosen_date or tpex_date

    day_rows,day_messages=fetch_day_trading(session)
    attempts.append({"market":"twse+tpex","date":chosen_date,"verified":bool(day_rows),"messages":day_messages})
    for key,row in day_rows.items():
        existing=current_items.get(key)
        if existing:
            merge_item(
                current_items,row.get("market") or key.split(":",1)[0],
                row.get("symbol") or key.split(":",1)[-1],row.get("name") or "",
                day_trading=row.get("day_trading") or {}
            )
        else:
            current_items[key]=row

    # If an official source is temporarily unavailable, retain that market's
    # latest verified rows rather than replacing them with empty data.
    previous_items=previous.get("items") or {}
    current_markets={row.get("market") for row in current_items.values()}
    for key,row in previous_items.items():
        if row.get("market") not in current_markets:
            current_items.setdefault(key,row)

    if not chosen_date:
        payload={
            **previous,
            "metadata":{
                **(previous.get("metadata") or {}),
                "version":"v11.2.7",
                "last_attempt_at":NOW.isoformat(timespec="seconds"),
                "status":"warning",
                "note":"本次官方來源未回傳可驗證資料，保留上一筆成功快照。",
                "attempts":attempts,
            },
        }
        write_payload(payload)
        print("chips preserved",len(payload.get("items") or {}))
        return

    markets={
        "twse":summarize(current_items,"twse"),
        "tpex":summarize(current_items,"tpex"),
    }
    snapshot={
        "date":chosen_date,
        "markets":markets,
        "items":current_items,
    }
    history={**previous_history,chosen_date:snapshot}
    ordered_dates=sorted(history.keys(),reverse=True)[:HISTORY_LIMIT]
    history={key:history[key] for key in ordered_dates}

    payload={
        "metadata":{
            "version":"v11.2.7",
            "updated_at":NOW.isoformat(timespec="seconds"),
            "trading_date":chosen_date,
            "source":"TWSE T86／MI_MARGN、TPEx OpenAPI",
            "status":"ok",
            "note":"支援依交易日與個股查詢；缺值保留 null，不以 0 冒充。",
            "attempts":attempts,
        },
        "available_dates":ordered_dates,
        "markets":markets,
        "items":current_items,
        "history":history,
    }
    write_payload(payload)
    margin_count=sum(
        1 for row in current_items.values()
        if row.get("margin",{}).get("balance") is not None or row.get("short",{}).get("balance") is not None
    )
    print("chips",len(current_items),"margin",margin_count,"date",chosen_date)


if __name__=="__main__":
    main()
