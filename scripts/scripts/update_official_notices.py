#!/usr/bin/env python3
from __future__ import annotations
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup
from news_pipeline import HEADERS,asset_aliases,normalize_item,save_channel,clean_text,decode_response

ALIASES=asset_aliases()
ADMIN_RE=re.compile(r"個人資料|隱私權|資訊安全|網站使用|網站導覽|常見問題|下載專區|系統維護|服務條款|無障礙|徵才|採購公告",re.I)
MARKET_RE=re.compile(r"利率|匯率|外匯|貨幣|金融|銀行|信用|房貸|債券|資本市場|證券|交易制度|上市|指數|ETF|經濟|GDP|物價|CPI|就業|失業|薪資|出口|進口|景氣|統計|央行|金管會",re.I)

def value(row,*names):
 lowered={str(k).lower():v for k,v in row.items()}
 for name in names:
  if name in row:return row[name]
  if name.lower() in lowered:return lowered[name.lower()]
 return None

def twse_news():
 url="https://openapi.twse.com.tw/v1/news/newsList";r=requests.get(url,headers=HEADERS,timeout=25);r.raise_for_status();rows=r.json();items=[]
 for row in rows if isinstance(rows,list) else []:
  title=clean_text(value(row,"Title","title","標題","主旨"));summary=clean_text(value(row,"Content","Summary","內容","摘要"))
  if ADMIN_RE.search(title) or not MARKET_RE.search(f"{title} {summary}"):continue
  link=value(row,"Url","URL","url","Link","網址") or "https://www.twse.com.tw/zh/about/news/news.html"
  item=normalize_item(title=title,url=link,source_id="official-notices",source_name="臺灣證券交易所",summary=summary,published_at=value(row,"Date","PublishDate","日期","發布日期"),aliases=ALIASES,forced_scope="market",extra={"verification_status":"official","official_agency":"TWSE"})
  if item:items.append(item)
 return items

def scrape_official_list(page:str,source_name:str,agency:str,href_hint:re.Pattern[str]|None=None):
 r=requests.get(page,headers=HEADERS,timeout=28);r.raise_for_status();soup=BeautifulSoup(decode_response(r),"lxml");items=[];seen=set()
 for a in soup.find_all("a",href=True):
  title=clean_text(a.get_text(" ",strip=True));href=urljoin(page,a.get("href"))
  if not title or len(title)<8 or href in seen or ADMIN_RE.search(title):continue
  if href_hint and not href_hint.search(href):continue
  parent=a.find_parent(["li","tr","article","div"]) or a.parent
  context=clean_text(parent.get_text(" ",strip=True)) if parent else title
  if not MARKET_RE.search(f"{title} {context}"):continue
  date_match=re.search(r"(?:20\d{2}|\d{3})[./-]\d{1,2}[./-]\d{1,2}",context)
  item=normalize_item(title=title,url=href,source_id="official-notices",source_name=source_name,summary=context.replace(title,"",1),published_at=date_match.group(0) if date_match else None,aliases=ALIASES,forced_scope="market",extra={"verification_status":"official","official_agency":agency})
  if item:items.append(item);seen.add(href)
 return items

def cbc_news():
 return scrape_official_list("https://www.cbc.gov.tw/tw/np-1040-1.html","中央銀行","CBC",re.compile(r"cbc\.gov\.tw/tw/(?:cp|news|lp|np)-",re.I))

def dgbas_news():
 return scrape_official_list("https://www.dgbas.gov.tw/News.aspx?n=3602","行政院主計總處","DGBAS",re.compile(r"dgbas\.gov\.tw/News_Content\.aspx|dgbas\.gov\.tw/News\.aspx",re.I))

def main():
 items=[];sources=[]
 for name,fn in [("TWSE newsList",twse_news),("CBC latest news",cbc_news),("DGBAS news",dgbas_news)]:
  try:
   rows=fn();items.extend(rows);sources.append({"name":name,"status":"ok" if rows else "warning","count":len(rows)})
  except Exception as exc:sources.append({"name":name,"status":"warning","error":str(exc)})
 payload=save_channel("official-market-notices.json","__OFFICIAL_NOTICE_SEED__","official-notices","官方市場公告",items,{"sources":sources,"disabled_sources":[{"name":"TPEx 網頁新聞與公告","status":"disabled","reason":"資料正確性待重新驗證；上櫃結構化行情與財務資料仍保留。"}]},30,1)
 print(payload["metadata"])
if __name__=="__main__":main()
