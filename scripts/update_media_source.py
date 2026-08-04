#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re
from pathlib import Path
from typing import Any
import feedparser,requests
from bs4 import BeautifulSoup
from common import DATA,NOW
from news_pipeline import HEADERS,asset_aliases,clean_text,normalize_item,save_channel,direct_url,decode_response

CONFIG=json.loads((DATA/"news-channels.json").read_text(encoding="utf-8"))

def json_candidates(value:Any):
 if isinstance(value,dict):
  title=value.get("headline") or value.get("title") or value.get("name")
  url=value.get("url") or value.get("mainEntityOfPage")
  if isinstance(url,dict):url=url.get("@id") or url.get("url")
  date=value.get("datePublished") or value.get("published_at") or value.get("publishAt") or value.get("date")
  desc=value.get("description") or value.get("summary") or value.get("abstract")
  if title and url:yield title,url,date,desc
  for child in value.values():yield from json_candidates(child)
 elif isinstance(value,list):
  for child in value:yield from json_candidates(child)

def parse_rss(cfg,aliases):
 items=[]
 for url in cfg.get("urls",[]):
  feed=feedparser.parse(url)
  for entry in feed.entries[:60]:
   item=normalize_item(title=entry.get("title"),url=entry.get("link"),source_id=cfg["id"],source_name=cfg["name"],summary=entry.get("summary") or entry.get("description"),published_at=entry.get("published") or entry.get("updated"),aliases=aliases)
   if item:items.append(item)
 return items

def nearest_date(text:str):
 for p in [r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}\s+\d{1,2}:\d{2}",r"20\d{2}[/-]\d{1,2}[/-]\d{1,2}"]:
  m=re.search(p,text)
  if m:return m.group(0)
 m=re.search(r"(\d{1,2})[/-](\d{1,2})\s+(\d{1,2}:\d{2})",text)
 if m:return f"{NOW.year}/{m.group(1)}/{m.group(2)} {m.group(3)}"
 m=re.search(r"(\d{1,2})月(\d{1,2})日?\s*(\d{1,2}:\d{2})?",text)
 if m:return f"{NOW.year}/{m.group(1)}/{m.group(2)} {m.group(3) or '00:00'}"
 m=re.search(r"(?:今天|今日)\s*(\d{1,2}:\d{2})",text)
 if m:return f"{NOW:%Y/%m/%d} {m.group(1)}"
 return None

def parse_html(cfg,aliases):
 session=requests.Session();items=[]
 for page in cfg.get("urls",[]):
  r=session.get(page,headers=HEADERS,timeout=25);r.raise_for_status();soup=BeautifulSoup(decode_response(r),"lxml")
  for script in soup.select('script[type="application/ld+json"]'):
   try:data=json.loads(script.string or script.get_text())
   except Exception:continue
   for title,url,date,desc in json_candidates(data):
    item=normalize_item(title=title,url=url,source_id=cfg["id"],source_name=cfg["name"],summary=desc,published_at=date,aliases=aliases,base_url=page)
    if item:items.append(item)
  patterns=[re.compile(p,re.I) for p in cfg.get("article_patterns",[])]
  for a in soup.find_all("a",href=True):
   href=direct_url(a.get("href"),page)
   if not href or patterns and not any(p.search(href) for p in patterns):continue
   title=clean_text(a.get("title") or a.get_text(" ",strip=True))
   if not 8<=len(title)<=180:continue
   parent=a.find_parent(["article","li","div"]) or a.parent
   context=clean_text(parent.get_text(" ",strip=True) if parent else "")
   summary=context.replace(title,"",1).strip()[:350]
   item=normalize_item(title=title,url=href,source_id=cfg["id"],source_name=cfg["name"],summary=summary,published_at=nearest_date(context),aliases=aliases)
   if item:items.append(item)
 return items

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--channel",required=True);args=ap.parse_args()
 cfg=next(x for x in CONFIG["media"] if x["id"]==args.channel);aliases=asset_aliases();error=None;items=[]
 try:items=parse_rss(cfg,aliases) if cfg["kind"]=="rss" else parse_html(cfg,aliases)
 except Exception as exc:error=str(exc)
 health={"status":"ok" if items else "warning","error":error,"requested_urls":cfg.get("urls",[]),"parsed_items":len(items)}
 payload=save_channel(cfg["file"],cfg["var"],cfg["id"],cfg["name"],items,health,cfg.get("retention_days",7),cfg.get("minimum_records",1))
 print(cfg["id"],payload["metadata"]["status"],payload["metadata"]["item_count"])
if __name__=="__main__":main()
