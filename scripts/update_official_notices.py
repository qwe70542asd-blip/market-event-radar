#!/usr/bin/env python3
from __future__ import annotations
import requests
from bs4 import BeautifulSoup
from common import NOW
from news_pipeline import HEADERS,asset_aliases,normalize_item,save_channel,clean_text,direct_url

ALIASES=asset_aliases()
def value(row,*names):
 lowered={str(k).lower():v for k,v in row.items()}
 for name in names:
  if name in row:return row[name]
  if name.lower() in lowered:return lowered[name.lower()]
 return None

def twse_news():
 url="https://openapi.twse.com.tw/v1/news/newsList";r=requests.get(url,headers=HEADERS,timeout=25);r.raise_for_status();rows=r.json();items=[]
 for row in rows if isinstance(rows,list) else []:
  title=value(row,"Title","title","標題","主旨")
  link=value(row,"Url","URL","url","Link","網址") or "https://www.twse.com.tw/zh/about/news/news.html"
  item=normalize_item(title=title,url=link,source_id="official-notices",source_name="臺灣證券交易所",summary=value(row,"Content","Summary","內容","摘要"),published_at=value(row,"Date","PublishDate","日期","發布日期"),aliases=ALIASES,forced_scope="market")
  if item:items.append(item)
 return items

def tpex_press():
 page="https://www.tpex.org.tw/zh-tw/about/company/press/list.html";r=requests.get(page,headers=HEADERS,timeout=25);r.raise_for_status();soup=BeautifulSoup(r.text,"lxml");items=[]
 for a in soup.find_all("a",href=True):
  title=clean_text(a.get_text(" ",strip=True));href=direct_url(a["href"],page)
  if not href or len(title)<8:continue
  if "press" not in href and "about_otc_news" not in href and "storage" not in href:continue
  context=clean_text((a.find_parent(["li","tr","div"]) or a.parent).get_text(" ",strip=True))
  item=normalize_item(title=title,url=href,source_id="official-notices",source_name="櫃買中心",summary=context.replace(title,"",1),published_at=context,aliases=ALIASES,forced_scope="market")
  if item:items.append(item)
 return items

def main():
 items=[];sources=[]
 for name,fn in [("TWSE newsList",twse_news),("TPEx press list",tpex_press)]:
  try:
   rows=fn();items.extend(rows);sources.append({"name":name,"status":"ok" if rows else "warning","count":len(rows)})
  except Exception as exc:sources.append({"name":name,"status":"warning","error":str(exc)})
 payload=save_channel("official-market-notices.json","__OFFICIAL_NOTICE_SEED__","official-notices","官方市場公告",items,{"sources":sources},30,1)
 print(payload["metadata"])
if __name__=="__main__":main()
