#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,re,os
from typing import Any
from datetime import date,datetime,timedelta
from urllib.parse import quote_plus
from urllib.parse import urlsplit
import feedparser,requests
from bs4 import BeautifulSoup
from common import DATA,NOW,read_json
from news_pipeline import HEADERS,asset_aliases,asset_profiles,clean_text,normalize_item,save_channel,direct_url,decode_response

CONFIG=json.loads((DATA/"news-channels.json").read_text(encoding="utf-8"))

HISTORY_QUERIES={
 "cna":"site:cna.com.tw 財經 OR 科技",
 "moneydj":"site:moneydj.com 台股 OR 美股 OR 財經",
 "cnyes":"site:cnyes.com 台股 OR 美股 OR 財經",
 "udn":"site:money.udn.com 財經 OR 台股 OR 國際",
 "ltn":"site:ec.ltn.com.tw OR site:news.ltn.com.tw/business 財經",
 "wealth":"site:stock.ltn.com.tw 台股 OR 投資",
 "yahoo":"site:tw.stock.yahoo.com 台股 OR 美股 OR 財經",
 "technews":"site:technews.tw OR site:finance.technews.tw 半導體 OR AI OR 財經",
 "ctee":"site:ctee.com.tw 台股 OR 財經 OR 產業",
 "asia-risk":"日圓 OR 日銀 OR 韓國央行 OR 韓元 OR KOSPI OR 中國房地產 OR 人民幣 OR 亞洲資金外流",
}
HISTORY_START=date(2026,1,1)

def month_iter(start:date,end:date):
 year,month=start.year,start.month
 while (year,month)<=(end.year,end.month):
  nxt=date(year+1,1,1) if month==12 else date(year,month+1,1)
  yield date(year,month,1),nxt
  year,month=nxt.year,nxt.month

def archive_month_counts(cfg):
 payload=read_json(DATA/cfg["file"],{"items":[]});counts={}
 for item in payload.get("items",[]):
  raw=str(item.get("published_at") or item.get("date") or "")
  if len(raw)>=7:counts[raw[:7]]=counts.get(raw[:7],0)+1
 return counts

def parse_history_google_news(cfg,aliases,profiles):
 if os.getenv("NEWS_HISTORY_BACKFILL","0").strip()=="0":return [],{"enabled":False,"queries":0,"items":0}
 query=HISTORY_QUERIES.get(cfg["id"]);counts=archive_month_counts(cfg)
 if not query:return [],{"enabled":False,"queries":0,"items":0}
 session=requests.Session();items=[];queries=0
 today=NOW.date()
 for start,end in month_iter(HISTORY_START,today):
  month=start.strftime("%Y-%m")
  if counts.get(month,0)>=3:continue
  before=min(end,today+timedelta(days=1))
  q=f"{query} after:{start.isoformat()} before:{before.isoformat()}"
  url=f"https://news.google.com/rss/search?q={quote_plus(q)}&hl=zh-TW&gl=TW&ceid=TW%3Azh-Hant"
  feed=feedparser.parse(url);queries+=1
  for entry in feed.entries[:12]:
   publisher=clean_text((entry.get("source") or {}).get("title") if isinstance(entry.get("source"),dict) else "") or cfg["name"]
   article_url=resolve_google_news(session,entry.get("link"))
   item=normalize_item(title=entry.get("title"),url=article_url,source_id=cfg["id"],source_name=cfg["name"],summary=entry.get("summary") or entry.get("description"),published_at=entry.get("published") or entry.get("updated"),aliases=aliases,profiles=profiles,forced_scope="media",extra={"image_url":rss_image(entry),"discovery_source":"google-news-history","discovery_channel":cfg["name"],"publisher":publisher,"history_month":month})
   if item:items.append(item)
 return items,{"enabled":True,"queries":queries,"items":len(items),"archive_start":HISTORY_START.isoformat()}


GENERIC_IMAGE_RE=re.compile(r"(?:og-image|default(?:_og)?|logo|placeholder|no[-_]?image|blank|icon|avatar|sprite|favicon)(?:[._/-]|$)",re.I)

def usable_image_url(value:Any)->str|None:
 url=direct_url(value) if value else None
 if not url or GENERIC_IMAGE_RE.search(url):return None
 return url

def image_value(value:Any)->str|None:
 if isinstance(value,str):return usable_image_url(value)
 if isinstance(value,list):
  for row in value:
   found=image_value(row)
   if found:return found
 if isinstance(value,dict):return value.get("url") or value.get("@id") or value.get("contentUrl")
 return None

def json_candidates(value:Any):
 if isinstance(value,dict):
  title=value.get("headline") or value.get("title") or value.get("name")
  url=value.get("url") or value.get("mainEntityOfPage")
  if isinstance(url,dict):url=url.get("@id") or url.get("url")
  date=value.get("datePublished") or value.get("published_at") or value.get("publishAt") or value.get("date")
  desc=value.get("description") or value.get("summary") or value.get("abstract")
  image=image_value(value.get("image") or value.get("thumbnailUrl"))
  if title and url:yield title,url,date,desc,image
  for child in value.values():yield from json_candidates(child)
 elif isinstance(value,list):
  for child in value:yield from json_candidates(child)



def excluded_item(cfg,title,url):
 host=urlsplit(str(url or "")).netloc.lower()
 if any(domain.lower() in host for domain in cfg.get("exclude_domains",[])):return True
 return any(re.search(pattern,str(title or ""),re.I) for pattern in cfg.get("exclude_title_patterns",[]))

def resolve_google_news(session,url):
 if "news.google." not in urlsplit(str(url or "")).netloc.lower():return url
 try:
  response=session.get(url,headers=HEADERS,timeout=15,allow_redirects=True)
  response.raise_for_status()
  final=direct_url(response.url)
  if final and "news.google." not in urlsplit(final).netloc.lower():return final
  soup=BeautifulSoup(decode_response(response),"lxml")
  for selector,attr in (('link[rel="canonical"]',"href"),('meta[property="og:url"]',"content")):
   node=soup.select_one(selector)
   candidate=direct_url(node.get(attr),response.url) if node else None
   if candidate and "news.google." not in urlsplit(candidate).netloc.lower():return candidate
 except Exception:pass
 return url

def rss_image(entry):
 for key in ("media_content","media_thumbnail","enclosures"):
  for row in entry.get(key,[]) or []:
   if isinstance(row,dict) and usable_image_url(row.get("url")):return usable_image_url(row.get("url"))
 image=entry.get("image")
 if isinstance(image,dict):return usable_image_url(image.get("href") or image.get("url"))
 return None

IMAGE_META_SELECTORS=(
 ('meta[property="og:image"]','content'),('meta[property="og:image:secure_url"]','content'),
 ('meta[name="twitter:image"]','content'),('meta[name="twitter:image:src"]','content'),
 ('meta[itemprop="image"]','content'),('link[rel="image_src"]','href')
)

def article_image_candidates_from_soup(soup,base):
 candidates=[]
 def add(value):
  found=usable_image_url(direct_url(value,base)) if value else None
  if found and found not in candidates:candidates.append(found)
 for selector,attribute in IMAGE_META_SELECTORS:
  for node in soup.select(selector):add(node.get(attribute))
 for script in soup.select('script[type="application/ld+json"]'):
  try:data=json.loads(script.string or script.get_text())
  except Exception:continue
  def walk(value):
   if isinstance(value,dict):
    for key in ("image","thumbnailUrl","contentUrl"):
     candidate=image_value(value.get(key))
     if candidate:add(candidate)
    for child in value.values():walk(child)
   elif isinstance(value,list):
    for child in value:walk(child)
  walk(data)
 for img in soup.find_all("img"):
  raw=img.get("src") or img.get("data-src") or img.get("data-original") or img.get("data-lazy-src")
  if not raw:
   srcset=img.get("srcset") or img.get("data-srcset")
   if srcset:
    values=[part.strip().split(" ")[0] for part in str(srcset).split(",") if part.strip()]
    raw=values[-1] if values else None
  found=usable_image_url(direct_url(raw,base)) if raw else None
  if not found:continue
  marker=f"{found} {img.get('class') or ''} {img.get('alt') or ''}".lower()
  if any(word in marker for word in ("logo","icon","avatar","sprite","loading","blank","advert","banner")):continue
  try:
   width=int(re.sub(r"\D","",str(img.get("width") or "0")) or 0);height=int(re.sub(r"\D","",str(img.get("height") or "0")) or 0)
  except Exception:width=height=0
  if width and height and (width<240 or height<120):continue
  if found not in candidates:candidates.append(found)
 return candidates[:10]

def article_image_from_soup(soup,base):
 candidates=article_image_candidates_from_soup(soup,base)
 return candidates[0] if candidates else None

def fallback_image_slug(title:Any,summary:Any="",category:Any=""):
 text=clean_text(f"{title or ''} {summary or ''} {category or ''}")
 mapping=[(r"台積電|鴻海|聯發科|廣達|緯創|半導體|晶圓|記憶體|AI|伺服器|輝達|NVIDIA|AMD|Intel|科技","technology"),(r"財報|EPS|營收|獲利|法說|展望|毛利|淨利","earnings"),(r"聯準會|央行|升息|降息|利率|殖利率|債券|FOMC|BOJ|日銀","rates"),(r"關稅|政策|法案|行政命令|監管|禁令|財政部|商務部|白宮","policy"),(r"戰爭|以伊|中東|俄烏|制裁|地緣|軍事","geopolitics"),(r"原油|石油|金價|黃金|銅價|天然氣|原物料|運價","commodities"),(r"GDP|CPI|PCE|非農|PMI|景氣|通膨|衰退|失業|總經","macro"),(r"美股|日股|韓股|歐股|中國|全球|國際|亞股|道瓊|NASDAQ|S&P","global"),(r"台股|加權|大盤|指數|成交量|盤中|創高|跌點","market")]
 for pattern,slug in mapping:
  if re.search(pattern,text,re.I):return slug
 return "stock"

def enrich_article_images(session,items,limit=48):
 cache={};attempts=0
 for item in items:
  candidates=[]
  for value in [item.get("image_url"),*(item.get("image_candidates") or [])]:
   found=usable_image_url(value)
   if found and found not in candidates:candidates.append(found)
  url=item.get("url")
  if url and attempts<limit:
   if url in cache:page_candidates=cache[url]
   else:
    attempts+=1;page_candidates=[]
    try:
     response=session.get(url,headers=HEADERS,timeout=18,allow_redirects=True)
     response.raise_for_status()
     if "html" in str(response.headers.get("content-type") or "").lower():
      soup=BeautifulSoup(decode_response(response),"lxml")
      page_candidates=article_image_candidates_from_soup(soup,response.url or url)
    except Exception:pass
    cache[url]=page_candidates
   for found in page_candidates:
    if found not in candidates:candidates.append(found)
  if candidates:
   item["image_url"]=candidates[0];item["image_candidates"]=candidates[:6];item["image_status"]="remote-candidates"
  else:
   item.pop("image_url",None);item.pop("image_candidates",None);item["image_status"]="fallback-required"
  if not item.get("fallback_image_slug"):
   item["fallback_image_slug"]=fallback_image_slug(item.get("title"),item.get("summary"),item.get("ai_category") or item.get("source_name"))
 return items

def parse_rss(cfg,aliases,profiles):
 session=requests.Session();items=[]
 for url in cfg.get("urls",[]):
  feed=feedparser.parse(url)
  for entry in feed.entries[:80]:
   title=entry.get("title");url=entry.get("link")
   if excluded_item(cfg,title,url):continue
   url=resolve_google_news(session,url)
   publisher=clean_text((entry.get("source") or {}).get("title") if isinstance(entry.get("source"),dict) else "") or cfg["name"]
   item=normalize_item(title=title,url=url,source_id=cfg["id"],source_name=publisher if cfg["id"]=="asia-risk" else cfg["name"],summary=entry.get("summary") or entry.get("description"),published_at=entry.get("published") or entry.get("updated"),aliases=aliases,profiles=profiles,forced_scope="media",extra={"image_url":rss_image(entry),"discovery_source":"google-news-search" if "news.google." in str(entry.get("link") or "") else "direct-feed","discovery_channel":cfg["name"],"publisher":publisher})
   if item:items.append(item)
 return enrich_article_images(session,items,int(cfg.get("image_fetch_limit",48)))

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

def parse_html(cfg,aliases,profiles):
 session=requests.Session();items=[]
 for page in cfg.get("urls",[]):
  r=session.get(page,headers=HEADERS,timeout=25);r.raise_for_status();soup=BeautifulSoup(decode_response(r),"lxml")
  for script in soup.select('script[type="application/ld+json"]'):
   try:data=json.loads(script.string or script.get_text())
   except Exception:continue
   for title,url,date,desc,image in json_candidates(data):
    item=normalize_item(title=title,url=url,source_id=cfg["id"],source_name=cfg["name"],summary=desc,published_at=date,aliases=aliases,profiles=profiles,forced_scope="media",base_url=page,extra={"image_url":direct_url(image,page) if image else None})
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
   img=(parent.find("img") if parent else None) or a.find("img")
   image=direct_url(img.get("src") or img.get("data-src") or img.get("data-original"),page) if img else None
   item=normalize_item(title=title,url=href,source_id=cfg["id"],source_name=cfg["name"],summary=summary,published_at=nearest_date(context),aliases=aliases,profiles=profiles,forced_scope="media",extra={"image_url":image})
   if item:items.append(item)
 return enrich_article_images(session,items,int(cfg.get("image_fetch_limit",48)))

def image_priority(item):
 published=0.0
 try:published=datetime.fromisoformat(str(item.get("published_at") or "").replace("Z","+00:00")).timestamp()
 except Exception:pass
 importance=float(item.get("importance_score") or 0)+(35 if item.get("impact")=="high" else 15 if item.get("impact")=="medium" else 0)
 return (1 if usable_image_url(item.get("image_url")) else 0,importance,published)

def enrich_merged_article_images(cfg,items):
 # Current and historical rows share the same image pass. Missing high-impact and recent rows are attempted first.
 ordered=sorted(items,key=image_priority,reverse=True)
 session=requests.Session()
 limit=max(int(cfg.get("image_fetch_limit",48)),120)
 enrich_article_images(session,ordered,limit)
 return items

def main():
 ap=argparse.ArgumentParser();ap.add_argument("--channel",required=True);args=ap.parse_args()
 cfg=next(x for x in CONFIG["media"] if x["id"]==args.channel);aliases=asset_aliases();profiles=asset_profiles();error=None;items=[]
 try:items=parse_rss(cfg,aliases,profiles) if cfg["kind"]=="rss" else parse_html(cfg,aliases,profiles)
 except Exception as exc:error=str(exc)
 history_items=[];history_health={"enabled":False,"queries":0,"items":0}
 try:history_items,history_health=parse_history_google_news(cfg,aliases,profiles)
 except Exception as exc:history_health={"enabled":True,"queries":0,"items":0,"error":str(exc)}
 items.extend(history_items)
 try:items=enrich_merged_article_images(cfg,items)
 except Exception as exc:
  history_health={**history_health,"image_enrichment_error":str(exc)}
 health={"status":"ok" if items else "warning","error":error,"requested_urls":cfg.get("urls",[]),"parsed_items":len(items),"history_backfill":history_health,"image_policy":"current-and-history-merged; high-impact and recent missing images first; generic placeholders rejected"}
 payload=save_channel(cfg["file"],cfg["var"],cfg["id"],cfg["name"],items,health,cfg.get("retention_days",7),cfg.get("minimum_records",1))
 print(cfg["id"],payload["metadata"]["status"],payload["metadata"]["item_count"])
if __name__=="__main__":main()
