#!/usr/bin/env python3
"""Build homepage important announcements and Taiwan institutional flow.

Free/public coverage:
- Official TWSE/TPEx three-institution summary and important notices
- Taiwan regulators/government official announcements
- Federal Reserve, SEC, Treasury, BLS, BEA, White House
- BOJ, JPX, Japan MOF, METI and FSA

Individual foreign-broker branch flows are not presented unless a licensed source is configured.
"""
from __future__ import annotations
import json, re, html, hashlib, os, time, xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"
OUT=DATA/"announcements.json"; SEED=DATA/"announcements-seed.js"
TAIPEI=ZoneInfo("Asia/Taipei"); NOW=datetime.now(TAIPEI)
HEADERS={"User-Agent":"MarketEventRadar/10.3 contact: repository-owner","Accept-Language":"zh-TW,zh;q=.9,en;q=.7,ja;q=.6"}

SEARCHES=[
 ("金融監督管理委員會","TW","government","site:fsc.gov.tw (新聞稿 OR 證券 OR 銀行 OR 保險 OR ETF)","zh-TW","TW","TW:zh-Hant"),
 ("中央銀行","TW","central-bank","site:cbc.gov.tw (新聞稿 OR 利率 OR 匯率 OR 貨幣政策)","zh-TW","TW","TW:zh-Hant"),
 ("主計總處","TW","government","site:dgbas.gov.tw (CPI OR GDP OR 薪資 OR 失業率 OR 新聞稿)","zh-TW","TW","TW:zh-Hant"),
 ("財政部","TW","government","site:mof.gov.tw (關稅 OR 出口 OR 進口 OR 稅收 OR 新聞稿)","zh-TW","TW","TW:zh-Hant"),
 ("經濟部","TW","government","site:moea.gov.tw (工業生產 OR 外銷訂單 OR 能源 OR 產業政策 OR 新聞稿)","zh-TW","TW","TW:zh-Hant"),
 ("Federal Reserve","US","central-bank","site:federalreserve.gov (press release OR monetary policy OR financial stability)","en-US","US","US:en"),
 ("U.S. SEC","US","regulator","site:sec.gov/newsroom/press-releases (market OR rule OR enforcement OR crypto OR reporting)","en-US","US","US:en"),
 ("U.S. Treasury","US","government","site:home.treasury.gov/news/press-releases (sanctions OR debt OR tax OR financial markets)","en-US","US","US:en"),
 ("White House","US","government","site:whitehouse.gov (tariff OR trade OR semiconductor OR executive order OR economy)","en-US","US","US:en"),
 ("Bank of Japan","JP","central-bank","site:boj.or.jp/en (monetary policy OR outlook OR statistics OR speech)","en-US","US","US:en"),
 ("Japan Exchange Group","JP","exchange","site:jpx.co.jp/english (news OR market OR listing OR regulation)","en-US","US","US:en"),
 ("Japan MOF","JP","government","site:mof.go.jp/english (foreign exchange OR government bonds OR economy OR press release)","en-US","US","US:en"),
 ("Japan METI","JP","government","site:meti.go.jp/english (industry OR trade OR energy OR semiconductor OR press release)","en-US","US","US:en"),
 ("Japan FSA","JP","regulator","site:fsa.go.jp/en (financial markets OR securities OR banks OR crypto)","en-US","US","US:en"),
]
TRANSLATIONS={
 "press release":"新聞稿","monetary policy":"貨幣政策","financial stability":"金融穩定","interest rate":"利率",
 "securities":"證券","enforcement":"執法","rule":"規則","reporting":"申報","crypto":"虛擬資產",
 "tariff":"關稅","trade":"貿易","semiconductor":"半導體","executive order":"行政命令",
 "government bonds":"政府公債","foreign exchange":"外匯","statistics":"統計","outlook":"展望報告",
 "listing":"上市掛牌","regulation":"監管","banks":"銀行","energy":"能源","industry":"產業",
}
def clean(v):return re.sub(r"\s+"," ",html.unescape(v or "")).strip()
def parse_date(v):
    try:
        d=parsedate_to_datetime(v);return d.astimezone(TAIPEI).isoformat(timespec="seconds")
    except:return None
def text(node,names):
    for n in names:
        x=node.find(n)
        if x is not None and x.text:return clean(x.text)
    return ""
def translate_rule(title):
    out=title
    changed=False
    for en,zh in TRANSLATIONS.items():
        new=re.sub(re.escape(en),zh,out,flags=re.I)
        if new!=out:changed=True;out=new
    return out if changed else f"官方公告：{title}"
def google_feed(query,hl,gl,ceid):
    url=f"https://news.google.com/rss/search?q={quote_plus(query)}&hl={hl}&gl={gl}&ceid={ceid}"
    r=requests.get(url,headers=HEADERS,timeout=25);r.raise_for_status()
    root=ET.fromstring(r.content);rows=[]
    for item in root.findall(".//item")[:8]:
        title=text(item,["title"]);link=text(item,["link"]);pub=text(item,["pubDate"])
        if title and link:rows.append((title,link,parse_date(pub)))
    return rows
def n(v):
    try:return float(str(v).replace(",","").strip())/100000000
    except:return None
def twse_institutional():
    url="https://www.twse.com.tw/rwd/zh/fund/BFI82U?response=json&type=day"
    r=requests.get(url,headers=HEADERS,timeout=25);r.raise_for_status();p=r.json()
    result={"foreign":None,"investment_trust":None,"dealer":None,"total":None}
    for row in p.get("data",[]):
        label=str(row[0]);net=n(row[-1])
        if "外資" in label and "自營" not in label:result["foreign"]=net
        elif "投信" in label:result["investment_trust"]=net
        elif "自營商" in label:result["dealer"]=(result["dealer"] or 0)+(net or 0)
        elif "合計" in label:result["total"]=net
    return result
def tpex_institutional():
    url="https://www.tpex.org.tw/openapi/v1/tpex_3insti_summary"
    rows=requests.get(url,headers=HEADERS,timeout=25).json()
    result={"foreign":None,"investment_trust":None,"dealer":None,"total":None}
    for row in rows:
        label=" ".join(map(str,row.values()))
        val=None
        for k,v in row.items():
            if "買賣超" in k or "差額" in k: val=n(v)
        if "外資" in label:result["foreign"]=val
        elif "投信" in label:result["investment_trust"]=val
        elif "自營" in label:result["dealer"]=val
        elif "合計" in label:result["total"]=val
    return result
def main():
    previous=json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"items":[]}
    items=[]
    # official TWSE/TPEx endpoints
    for source,region,category,url in [
      ("臺灣證券交易所","TW","exchange","https://openapi.twse.com.tw/v1/news/newsList"),
      ("臺灣證券交易所重大訊息","TW","company","https://openapi.twse.com.tw/v1/opendata/t187ap04_L"),
      ("證券櫃檯買賣中心重大訊息","TW","company","https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O")]:
        try:
            rows=requests.get(url,headers=HEADERS,timeout=25).json()
            for row in rows[:15]:
                blob={str(k):v for k,v in row.items()}
                title=next((clean(str(v)) for k,v in blob.items() if any(x in k for x in ["標題","主旨","重大訊息"] ) and clean(str(v))),None)
                link=next((clean(str(v)) for k,v in blob.items() if "網址" in k and str(v).startswith("http")),None) or ("https://mops.twse.com.tw/" if "訊息" in source else "https://www.twse.com.tw/zh/")
                if title:items.append({"id":hashlib.sha1((source+title).encode()).hexdigest()[:16],"region":region,"category":category,"source":source,
                  "title_zh":title,"title_original":title,"link":link,"published_at":None,"importance":"high","translation_status":"official-zh"})
        except Exception as e:print("warning",source,e)
    for source,region,category,query,hl,gl,ceid in SEARCHES:
        try:
            for title,link,pub in google_feed(query,hl,gl,ceid):
                zh=title if region=="TW" else translate_rule(title)
                items.append({"id":hashlib.sha1((source+link).encode()).hexdigest()[:16],"region":region,"category":category,"source":source,
                  "title_zh":zh,"title_original":title,"link":link,"published_at":pub,"importance":"high","translation_status":"official-zh" if region=="TW" else "rule-based"})
        except Exception as e:print("warning",source,e)
        time.sleep(.1)
    # dedupe titles
    dedup={}
    for item in items:
        key=re.sub(r"\W+","",item["title_original"].lower())
        if key not in dedup:dedup[key]=item
    if not dedup:
        dedup={x["id"]:x for x in previous.get("items",[])}
    try:twse=twse_institutional()
    except Exception as e:print("warning twse institutional",e);twse=previous.get("institutional",{}).get("twse",{})
    try:tpex=tpex_institutional()
    except Exception as e:print("warning tpex institutional",e);tpex=previous.get("institutional",{}).get("tpex",{})
    payload={"metadata":{"version":"v10.3","updated_at":NOW.isoformat(timespec="seconds"),"translation_note":"Known official phrases use rule-based Chinese translation; original title is preserved."},
      "institutional":{"date":NOW.date().isoformat(),"twse":twse,"tpex":tpex,
      "note":"三大法人為官方公開彙總；個別外資券商分點需授權資料源，本站不以推測代替。"},
      "items":sorted(dedup.values(),key=lambda x:x.get("published_at") or "",reverse=True)[:100]}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEED.write_text("window.__MARKET_ANNOUNCEMENT_SEED__ = "+json.dumps(payload,ensure_ascii=False,indent=2)+";\n",encoding="utf-8")
    print("announcements",len(payload["items"]))
if __name__=="__main__":main()
