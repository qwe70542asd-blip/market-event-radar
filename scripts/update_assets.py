#!/usr/bin/env python3
"""Build Taiwan and US security master plus bulk fundamentals.

Taiwan:
- TWSE listed basic data and ETF master
- TPEx OTC and emerging company master
- TWSE/TPEx quotes, valuation and bulk financial statements

United States:
- SEC ticker / CIK / exchange association
- Nasdaq Trader listed-security directories
- Nasdaq stock screener fields when available

The generated master is intentionally honest: missing classifications or metrics remain null.
"""
from __future__ import annotations
import csv, io, json, os, re, hashlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
ASSETS=DATA/"assets.json"
SEED=DATA/"assets-seed.js"
DETAILS=DATA/"asset-details"
TAIPEI=ZoneInfo("Asia/Taipei")
NOW=datetime.now(TAIPEI)
HEADERS={"User-Agent":"MarketEventRadar/10.3 contact: repository-owner","Accept-Language":"zh-TW,zh;q=0.9,en;q=0.7"}

URLS={
 "twse_basic":"https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
 "twse_etf":"https://openapi.twse.com.tw/v1/opendata/t187ap47_L",
 "tpex_basic":"https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
 "tpex_emerging":"https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_R",
 "sec_tickers":"https://www.sec.gov/files/company_tickers_exchange.json",
 "nasdaq_listed":"https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
 "other_listed":"https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
 "nasdaq_screener":"https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&offset=0&download=true",
}
TW_METRICS={
 "twse_quote":"https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
 "twse_value":"https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
 "tpex_quote":"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes",
 "tpex_value":"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis",
}
TW_FINANCIAL=[
 ("https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci","income"),
 ("https://openapi.twse.com.tw/v1/opendata/t187ap06_L_fh","income"),
 ("https://openapi.twse.com.tw/v1/opendata/t187ap06_L_basi","income"),
 ("https://openapi.twse.com.tw/v1/opendata/t187ap06_L_bd","income"),
 ("https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ins","income"),
 ("https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ci","balance"),
 ("https://openapi.twse.com.tw/v1/opendata/t187ap07_L_fh","balance"),
 ("https://openapi.twse.com.tw/v1/opendata/t187ap07_L_basi","balance"),
 ("https://openapi.twse.com.tw/v1/opendata/t187ap07_L_bd","balance"),
 ("https://openapi.twse.com.tw/v1/opendata/t187ap07_L_ins","balance"),
 ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_ciA","income"),
 ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_fhA","income"),
 ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_basiA","income"),
 ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_bdA","income"),
 ("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_insA","income"),
]
SECTOR_MAP_TW={
 "水泥工業":"materials","食品工業":"consumer","塑膠工業":"materials","紡織纖維":"materials",
 "電機機械":"industrial","電器電纜":"industrial","化學工業":"materials","生技醫療業":"healthcare",
 "玻璃陶瓷":"materials","造紙工業":"materials","鋼鐵工業":"materials","橡膠工業":"automotive",
 "汽車工業":"automotive","半導體業":"technology","電腦及週邊設備業":"technology","光電業":"technology",
 "通信網路業":"communication","電子零組件業":"technology","電子通路業":"technology","資訊服務業":"technology",
 "其他電子業":"technology","建材營造業":"real-estate","航運業":"shipping","觀光餐旅":"tourism",
 "金融保險業":"finance","貿易百貨":"consumer","油電燃氣業":"energy","綠能環保":"energy",
 "數位雲端":"technology","運動休閒":"consumer","居家生活":"consumer",
}
SECTOR_MAP_US={
 "Technology":"technology","Financial Services":"finance","Financials":"finance","Industrials":"industrial",
 "Consumer Cyclical":"consumer","Consumer Defensive":"consumer","Healthcare":"healthcare","Energy":"energy",
 "Basic Materials":"materials","Real Estate":"real-estate","Utilities":"utilities","Communication Services":"communication",
}

def get_json(url):
    r=requests.get(url,headers=HEADERS,timeout=35);r.raise_for_status();return r.json()
def get_text(url):
    r=requests.get(url,headers=HEADERS,timeout=35);r.raise_for_status();return r.text
def value(row,*needles):
    for key,val in row.items():
        k=str(key).replace(" ","")
        if any(n.replace(" ","") in k for n in needles):
            return val
    return None
def num(v):
    try:return float(str(v).replace(",","").replace("%","").replace("$","").strip())
    except:return None
def stable_id(market,symbol): return f"{market}:{symbol}"
def normalize_tw(row,exchange,asset_class="stock"):
    symbol=str(value(row,"公司代號","證券代號","股票代號","基金代號") or "").strip()
    name=str(value(row,"公司簡稱","證券名稱","股票名稱","基金簡稱","基金名稱") or "").strip()
    if not symbol or not name:return None
    industry=str(value(row,"產業別","產業類別") or ("ETF" if asset_class=="etf" else "其他")).strip()
    market="TW"
    return {"id":stable_id(market,symbol),"asset_class":asset_class,"market":market,"exchange":exchange,
      "symbol":symbol,"name":name,"official_industry":industry,"sector":SECTOR_MAP_TW.get(industry,"fund" if asset_class=="etf" else "other"),
      "sub_industry":industry,"currency":"TWD","aliases":[],"listing_status":"active","metrics":{},"financials":[]}
def parse_pipe(text):
    rows=list(csv.DictReader(io.StringIO(text),delimiter="|"))
    return [r for r in rows if r and not any(str(v).startswith("File Creation Time") for v in r.values())]
def main():
    previous=json.loads(ASSETS.read_text(encoding="utf-8")) if ASSETS.exists() else {"assets":[]}
    seed={x["id"]:x for x in previous.get("assets",[])}
    assets={}
    for key,url,exchange,cls in [
      ("twse",URLS["twse_basic"],"TWSE","stock"),("twse_etf",URLS["twse_etf"],"TWSE","etf"),
      ("tpex",URLS["tpex_basic"],"TPEx","stock"),("emerging",URLS["tpex_emerging"],"TPEx Emerging","stock")]:
        try:
            for row in get_json(url):
                a=normalize_tw(row,exchange,cls)
                if a: assets[a["id"]]={**seed.get(a["id"],{}),**a}
        except Exception as exc: print("warning",key,exc)
    # SEC master
    sec_map={}
    try:
        payload=get_json(URLS["sec_tickers"]); fields=payload["fields"]
        for raw in payload["data"]:
            row=dict(zip(fields,raw)); symbol=str(row.get("ticker") or "").strip().upper()
            if not symbol:continue
            sec_map[symbol]=row
            asset={"id":stable_id("US",symbol),"asset_class":"stock","market":"US","exchange":row.get("exchange") or "US",
              "symbol":symbol,"name":row.get("name") or symbol,"official_industry":"待產業資料同步","sector":"other",
              "sub_industry":"待產業資料同步","currency":"USD","aliases":[],"listing_status":"active",
              "detail":{"sec_cik":str(row.get("cik") or "").zfill(10)},"metrics":{},"financials":[]}
            assets[asset["id"]]={**seed.get(asset["id"],{}),**asset}
    except Exception as exc: print("warning sec",exc)
    # Nasdaq screener enrichment
    try:
        rows=((get_json(URLS["nasdaq_screener"]).get("data") or {}).get("rows") or [])
        for row in rows:
            symbol=str(row.get("symbol") or "").strip().upper(); aid=stable_id("US",symbol)
            if not symbol:continue
            sector=row.get("sector") or ""; industry=row.get("industry") or sector or "待分類"
            base=assets.get(aid,{"id":aid,"asset_class":"stock","market":"US","exchange":"US","symbol":symbol,
              "name":row.get("name") or symbol,"currency":"USD","aliases":[],"listing_status":"active","detail":{},"financials":[]})
            base.update({"name":row.get("name") or base["name"],"official_industry":industry,"sub_industry":industry,
              "sector":SECTOR_MAP_US.get(sector,"other"),"metrics":{
                **base.get("metrics",{}),"price":num(row.get("lastsale")),"market_cap":num(row.get("marketCap")),
                "pe":num(row.get("peRatio")),"eps":num(row.get("eps")),"dividend_yield":num(row.get("dividendYield"))
              }})
            assets[aid]=base
    except Exception as exc: print("warning nasdaq screener",exc)
    # Preserve seed crypto/manual funds and seeded classifications
    for aid,a in seed.items():
        if aid not in assets or a.get("asset_class") in {"crypto","fund"}:
            assets[aid]=a
        else:
            for k in ["aliases","sector","sub_industry","official_industry","detail"]:
                if a.get(k) and (not assets[aid].get(k) or assets[aid].get(k) in {"other","待分類","待產業資料同步"}):
                    assets[aid][k]=a[k]
    # Taiwan current quote/valuation
    for name,url in TW_METRICS.items():
        try:
            for row in get_json(url):
                symbol=str(value(row,"證券代號","股票代號","代號") or "").strip(); aid=stable_id("TW",symbol)
                if aid not in assets:continue
                m=assets[aid].setdefault("metrics",{})
                if "quote" in name:
                    m["price"]=num(value(row,"收盤價","Close","收盤"))
                    m["volume"]=num(value(row,"成交股數","成交量"))
                else:
                    m["pe"]=num(value(row,"本益比"))
                    m["pb"]=num(value(row,"股價淨值比"))
                    m["dividend_yield"]=num(value(row,"殖利率"))
        except Exception as exc: print("warning",name,exc)
    # Financial bulk, generic fields
    financial={}
    for url,kind in TW_FINANCIAL:
        try:
            for row in get_json(url):
                symbol=str(value(row,"公司代號","證券代號") or "").strip()
                if not symbol:continue
                key=(symbol,str(value(row,"年度","年") or ""),str(value(row,"季別","季") or ""))
                target=financial.setdefault(key,{"period":f'{key[1]}Q{key[2]}'})
                if kind=="income":
                    target["revenue"]=num(value(row,"營業收入","收益"))
                    target["operating_income"]=num(value(row,"營業利益","營業損益"))
                    target["net_income"]=num(value(row,"本期淨利","本期稅後淨利","淨利"))
                    target["eps"]=num(value(row,"基本每股盈餘","每股盈餘"))
                else:
                    target["assets"]=num(value(row,"資產總額"))
                    target["liabilities"]=num(value(row,"負債總額"))
                    target["equity"]=num(value(row,"權益總額"))
                    target["current_assets"]=num(value(row,"流動資產"))
                    target["current_liabilities"]=num(value(row,"流動負債"))
        except Exception as exc: print("warning financial",url,exc)
    for (symbol,_,_),row in financial.items():
        aid=stable_id("TW",symbol)
        if aid in assets: assets[aid].setdefault("financials",[]).append(row)
    # compute metrics/ranks
    for a in assets.values():
        a.setdefault("metrics",{}); fs=sorted(a.get("financials",[]),key=lambda x:x.get("period",""),reverse=True)
        a["financials"]=fs[:8]
        if fs:
            latest=fs[0]; m=a["metrics"]
            rev=latest.get("revenue"); op=latest.get("operating_income"); net=latest.get("net_income")
            eq=latest.get("equity"); liab=latest.get("liabilities"); ass=latest.get("assets")
            if rev: m["operating_margin"]=op/rev*100 if op is not None else None; m["net_margin"]=net/rev*100 if net is not None else None
            if eq and net is not None: m["roe"]=net/eq*100
            if ass and liab is not None: m["debt_ratio"]=liab/ass*100
            if latest.get("current_liabilities") and latest.get("current_assets") is not None:
                m["current_ratio"]=latest["current_assets"]/latest["current_liabilities"]
            if latest.get("eps") is not None:m["eps"]=latest["eps"]
    by_industry={}
    for a in assets.values(): by_industry.setdefault((a["market"],a.get("official_industry")),[]).append(a)
    for group in by_industry.values():
        for metric in ["eps","roe","pe","pb","dividend_yield","debt_ratio"]:
            values=sorted([x["metrics"].get(metric) for x in group if isinstance(x.get("metrics",{}).get(metric),(int,float))])
            if not values:continue
            median=values[len(values)//2]
            for a in group:a.setdefault("industry_median",{})[metric]=median
        for a in group:
            ranks={}
            for metric,label,reverse in [("eps","eps",True),("roe","roe",True),("pe","valuation",False)]:
                ranked=sorted([x for x in group if isinstance(x.get("metrics",{}).get(metric),(int,float))],
                              key=lambda x:x["metrics"][metric],reverse=reverse)
                try:ranks[label]=f'{ranked.index(a)+1}/{len(ranked)}'
                except ValueError:ranks[label]="資料不足"
            a["rankings"]=ranks
    payload={"metadata":{"version":"v11.0.0","updated_at":NOW.isoformat(timespec="seconds"),"asset_count":len(assets),
      "note":"TW official master + US SEC/Nasdaq master; missing data remains explicit."},"assets":sorted(assets.values(),key=lambda x:(x["asset_class"],x["market"],x["symbol"]))}
    ASSETS.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEED.write_text("window.__MARKET_ASSET_SEED__ = "+json.dumps(payload,ensure_ascii=False,indent=2)+";\n",encoding="utf-8")
    DETAILS.mkdir(exist_ok=True)
    for a in payload["assets"]:
        if a.get("metrics") or a.get("financials"):
            (DETAILS/f'{a["id"].replace(":","__")}.json').write_text(json.dumps({
              "metrics":a.get("metrics",{}),"financials":a.get("financials",[]),
              "industry_median":a.get("industry_median",{}),"rankings":a.get("rankings",{})
            },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("assets",len(assets))
if __name__=="__main__":main()
