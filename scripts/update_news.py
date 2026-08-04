#!/usr/bin/env python3
from common import *
import feedparser, hashlib
from dateutil import parser as dp
def main():
 cfg=read_json(DATA/"news-sources.json",{"sources":[]});old=read_json(DATA/"news.json",{"items":[]});items=[];health=[]
 for src in cfg.get("sources",[]):
  try:
   f=feedparser.parse(src["url"]);count=0
   for e in f.entries[:30]:
    title=(e.get("title") or "").strip();url=e.get("link") or "";summary=(e.get("summary") or "").replace("<br>"," ")
    if not title:continue
    items.append({"id":hashlib.sha1((title+url).encode()).hexdigest()[:16],"title":title,"url":url,"summary":summary,"source":src["name"],"topic":src.get("topic","market"),"published_at":e.get("published") or e.get("updated") or NOW.isoformat(timespec="seconds"),"symbols":[]});count+=1
   health.append({"name":src["name"],"status":"ok","count":count})
  except Exception as e:health.append({"name":src["name"],"status":"warning","error":str(e)})
 if not items:items=old.get("items",[])
 seen=set();ded=[]
 for x in items:
  key=x["title"].lower()
  if key in seen:continue
  seen.add(key);ded.append(x)
 payload={"metadata":{"version":"v11.3.0","updated_at":NOW.isoformat(timespec="seconds"),"item_count":len(ded),"retention_days":14},"sources":health,"items":ded[:500]};write_payload("news.json","__NEWS_SEED__",payload)
if __name__=="__main__":main()
