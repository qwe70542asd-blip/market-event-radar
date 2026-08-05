#!/usr/bin/env python3
from __future__ import annotations
import hashlib, html, json, re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from common import DATA, NOW, read_json

VERSION="v11.4.10"
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; MarketEventRadar/11.4.10; +https://github.com/qwe70542asd-blip/market-event-radar)"}
COMPANY_EVENT_RE=re.compile(r"增資|減資|除權|除息|股利|法說|財報|財務報告|股東會|停牌|復牌|公開收購|併購|合併|處分資產|取得資產|重大合約|融資融券|注意股票|處置股票|庫藏股|董事會|重大訊息",re.I)
MARKET_HIGH_RE=re.compile(r"FOMC|聯準會|Fed\b|央行|CPI|PCE|GDP|非農|JOLTS|PMI|利率決策|升息|降息|關稅|制裁|戰爭|金融危機|熔斷|重大法規|匯率干預|資本管制",re.I)
MEDIUM_RE=re.compile(r"財報|營收|法說|政策|匯率|債券|半導體|AI|原油|除權|除息|增資|減資|融資融券|出口|進口|景氣",re.I)

LEADER_RE=re.compile(r"台積電|鴻海|聯發科|廣達|緯創|國巨|川湖|日月光|台達電|中華電|長榮|陽明|NVIDIA|輝達|Microsoft|微軟|Apple|蘋果|Amazon|亞馬遜|Meta|Google|Alphabet|AMD|Intel|Tesla|三星|SK\s*海力士|海力士|Sony|Toyota",re.I)
LEADING_SECTOR_RE=re.compile(r"AI\s*伺服器|人工智慧|半導體|晶圓代工|記憶體|HBM|封裝測試|散熱|PCB|電源供應|雲端|資料中心|金融|航運|能源|原物料|機器人",re.I)
EXECUTIVE_RE=re.compile(r"執行長|董事長|財務長|總經理|基金經理人|分析師|首席經濟學家|央行總裁|官員|法說會|投資人會議|發表會|開發者大會|展覽|論壇|供應鏈會議",re.I)
BUSINESS_RE=re.compile(r"財報|財測|展望|營收|獲利|EPS|訂單|資本支出|擴產|漲價|降價|新品|新產品|合作|併購|投資",re.I)
POSITIVE_RE=re.compile(r"優於預期|上修|成長|創高|大增|獲利增加|降息|擴產|訂單增加|買超|利多|回升|改善",re.I)
NEGATIVE_RE=re.compile(r"低於預期|下修|衰退|虧損|暴跌|大跌|升息|制裁|關稅|減產|賣超|利空|違約|下滑|惡化",re.I)
GENERIC_RE=re.compile(r"^(?:TWSE\s*)?(?:(?:臺灣|台灣)證券交易所[>：:\-\s]*)?(?:首頁|新聞|最新消息|公文公告|公告查詢|新聞中心|個股資訊|台股新聞|財經新聞|即時新聞)$",re.I)
CJK_RE=re.compile(r"[\u3400-\u9fff]")
MOJIBAKE_RE=re.compile(r"(?:Ã|Â|â€|å[\x80-\xff]|æ[\x80-\xff]|ç[\x80-\xff]|è[\x80-\xff]|é[\x80-\xff]|ï¿½|�)")
SITE_SUFFIX_RE=re.compile(r"\s*(?:[-｜|]\s*)?(?:中央社|MoneyDJ(?:理財網)?|鉅亨網|經濟日報|自由財經|財富自由|Yahoo(?:奇摩)?股市|科技新報|財經新報|工商時報|twse\.com\.tw|tpex\.org\.tw|Google News)\s*$",re.I)
CODE_RE=re.compile(r"(?<!\d)(\d{4}|00\d{3}[A-Z]|00\d{4})(?!\d)",re.I)

CATEGORY_RULES=[
 ("央行與利率","macro",re.compile(r"聯準會|Fed\b|FOMC|央行|升息|降息|利率|殖利率",re.I)),
 ("總體經濟","macro",re.compile(r"CPI|PCE|GDP|非農|JOLTS|就業|失業|通膨|景氣|PMI|出口|進口",re.I)),
 ("企業財報","earnings",re.compile(r"財報|營收|獲利|EPS|法說|展望|財測|季報|年報",re.I)),
 ("半導體與 AI","technology",re.compile(r"AI|人工智慧|半導體|晶片|晶圓|GPU|伺服器|台積電|NVIDIA|輝達|記憶體",re.I)),
 ("政策與法規","policy",re.compile(r"政策|法規|關稅|制裁|補貼|金管會|行政院|立法院|交易制度",re.I)),
 ("地緣政治","geopolitics",re.compile(r"戰爭|衝突|軍事|地緣|停火|攻擊|選舉",re.I)),
 ("能源與原物料","commodities",re.compile(r"原油|石油|天然氣|黃金|銅價|原物料|OPEC",re.I)),
 ("匯率與債券","rates",re.compile(r"美元|日圓|新台幣|韓元|匯率|債券|美債",re.I)),
]

def _text_score(value:str)->int:
 text=str(value or "")
 return len(CJK_RE.findall(text))*8-len(MOJIBAKE_RE.findall(text))*25-text.count("�")*40

def repair_mojibake(value:Any)->str:
 text=str(value or "")
 candidates=[text]
 for source in ("latin1","cp1252"):
  try:candidates.append(text.encode(source).decode("utf-8"))
  except Exception:pass
 return max(candidates,key=_text_score)

def decode_response(response)->str:
 data=response.content or b""
 declared=[]
 for value in (getattr(response,"encoding",None),getattr(response,"apparent_encoding",None)):
  if value:declared.append(str(value))
 content_type=str(response.headers.get("content-type") or "")
 match=re.search(r"charset=([^;\s]+)",content_type,re.I)
 if match:declared.insert(0,match.group(1).strip("\"'"))
 encodings=[]
 for value in [*declared,"utf-8-sig","utf-8","cp950","big5"]:
  key=value.lower().replace("_","-")
  if key not in encodings:encodings.append(key)
 candidates=[]
 for encoding in encodings:
  try:candidates.append(data.decode(encoding))
  except Exception:pass
 if not candidates:return data.decode("utf-8","replace")
 return max(candidates,key=_text_score)

def clean_text(value:Any)->str:
 raw=html.unescape(repair_mojibake(value))
 return re.sub(r"\s+"," ",BeautifulSoup(raw,"html.parser").get_text(" ",strip=True)).strip()

def readable_chinese(title:str,summary:str="")->bool:
 title=clean_text(title);summary=clean_text(summary)
 if MOJIBAKE_RE.search(title) or "�" in title:return False
 cjk=len(CJK_RE.findall(title))
 visible=len(re.findall(r"[0-9A-Za-z\u3400-\u9fff]",title)) or 1
 if cjk<4 or cjk/visible<0.24:return False
 if summary and len(summary)>=24:
  if MOJIBAKE_RE.search(summary) or "�" in summary:return False
  if len(CJK_RE.findall(summary))<4:return False
 return True

def clean_title(value:Any)->str:
 title=clean_text(value)
 old=None
 while old!=title:
  old=title; title=SITE_SUFFIX_RE.sub("",title).strip(" -｜|")
 return title

def direct_url(value:Any,base:str|None=None)->str|None:
 raw=html.unescape(str(value or "")).strip()
 if base: raw=urljoin(base,raw)
 if not re.match(r"^https?://",raw,re.I) or any(c in raw for c in "<>\n\r"): return None
 try: p=urlsplit(raw)
 except Exception:return None
 if not p.netloc:return None
 path=re.sub(r"/+","/",p.path or "/")
 if path.lower() in {"/","/index.html","/index.php","/home","/news"} and not p.query:return None
 return urlunsplit((p.scheme,p.netloc,p.path,p.query,""))

def parse_datetime(value:Any)->datetime|None:
 if not value:return None
 text=str(value).strip()
 digits=re.sub(r"\D","",text)
 if len(digits)>=7:
  date_digits=digits[:8] if len(digits)>=8 and int(digits[:4])>=1911 else digits[:7]
  try:
   if len(date_digits)==8:
    y,mo,d=int(date_digits[:4]),int(date_digits[4:6]),int(date_digits[6:8])
    rest=digits[8:]
   else:
    y,mo,d=int(date_digits[:3])+1911,int(date_digits[3:5]),int(date_digits[5:7])
    rest=digits[7:]
   h=int(rest[:2]) if len(rest)>=2 else 0;mi=int(rest[2:4]) if len(rest)>=4 else 0;sec=int(rest[4:6]) if len(rest)>=6 else 0
   return datetime(y,mo,d,h,mi,sec,tzinfo=NOW.tzinfo)
  except Exception:pass
 for parser in (lambda s:date_parser.parse(s),lambda s:parsedate_to_datetime(s)):
  try:
   dt=parser(text)
   if dt.tzinfo is None:dt=dt.replace(tzinfo=NOW.tzinfo)
   return dt.astimezone(NOW.tzinfo)
  except Exception:pass
 for pat in (r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})\s*(\d{1,2})?[:：]?(\d{1,2})?",r"(\d{3})[/-](\d{1,2})[/-](\d{1,2})\s*(\d{1,2})?[:：]?(\d{1,2})?"):
  m=re.search(pat,text)
  if m:
   y,mo,d,h,mi=m.groups();y=int(y)+(1911 if len(y)==3 else 0)
   try:return datetime(y,int(mo),int(d),int(h or 0),int(mi or 0),tzinfo=NOW.tzinfo)
   except Exception:return None
 return None

def asset_aliases()->dict[str,str]:
 payload=read_json(DATA/"assets.json",{"assets":[]});out={}
 for a in payload.get("assets",[]):
  symbol=str(a.get("symbol") or "").upper()
  if not symbol:continue
  for name in [a.get("name"),a.get("company_name"),*((a.get("aliases") or []))]:
   n=clean_text(name).lower()
   if len(n)>=2:out[n]=symbol
 return out

def asset_profiles()->dict[str,dict[str,Any]]:
 payload=read_json(DATA/"assets.json",{"assets":[]});out={}
 for a in payload.get("assets",[]):
  symbol=str(a.get("symbol") or "").upper()
  if not symbol:continue
  name=clean_text(a.get("name") or a.get("company_name") or symbol)
  industry=clean_text(a.get("official_industry") or a.get("sub_industry") or (a.get("etf") or {}).get("category") or "")
  out[symbol]={"symbol":symbol,"name":name or symbol,"industry":industry,"asset_class":a.get("asset_class") or "stock"}
 return out

def infer_symbols(text:str,aliases:dict[str,str])->list[str]:
 found=[]
 for m in CODE_RE.finditer(text):
  code=m.group(1).upper()
  if code.isdigit() and 1900<=int(code)<=2100:continue
  found.append(code)
 low=text.lower()
 for name,symbol in aliases.items():
  if name in low:found.append(symbol)
 return list(dict.fromkeys(found))[:10]

def classify(title:str,summary:str,aliases:dict[str,str],forced_scope:str|None=None)->dict[str,Any]:
 text=f"{title} {summary}";symbols=infer_symbols(text,aliases)
 media_mode=forced_scope=="media"
 company=forced_scope=="company" or (not media_mode and bool(symbols and COMPANY_EVENT_RE.search(text)))
 stock_article=media_mode and bool(symbols)
 systemic=bool(MARKET_HIGH_RE.search(text))
 market=forced_scope=="market" or systemic
 scope="company" if company else "stock" if stock_article else "market" if market else "general"
 category,topic="市場動態","market"
 for label,tp,pat in CATEGORY_RULES:
  if pat.search(text):category,topic=label,tp;break
 if company:category,topic="個股公告","company"
 elif stock_article and category=="市場動態":category,topic="個股新聞","stock"
 impact="high" if systemic else "medium" if MEDIUM_RE.search(text) else "low"
 pos,neg=bool(POSITIVE_RE.search(text)),bool(NEGATIVE_RE.search(text))
 direction="多空混合" if pos and neg else "偏多" if pos else "偏空" if neg else "中性"
 affected=[]
 for pat,vals in [
  (re.compile(r"台股|證交所|櫃買|新台幣",re.I),["台股"]),(re.compile(r"半導體|晶片|台積電|NVIDIA|輝達|AI|記憶體",re.I),["半導體","科技股"]),
  (re.compile(r"美股|NASDAQ|S&P|道瓊|聯準會|Fed\b",re.I),["美股"]),(re.compile(r"韓國|KOSPI|KOSDAQ|韓元",re.I),["韓股"]),
  (re.compile(r"美元|匯率|日圓|新台幣|韓元",re.I),["匯率"]),(re.compile(r"債券|美債|殖利率",re.I),["債券"]),
  (re.compile(r"原油|石油|天然氣|黃金|銅價",re.I),["原物料"]),(re.compile(r"金融|銀行|保險",re.I),["金融股"]),
  (re.compile(r"航運|海運|運價",re.I),["航運股"])]:
  if pat.search(text):affected.extend(vals)
 if (company or stock_article) and symbols:affected=symbols
 affected=list(dict.fromkeys(affected))[:5] or ["整體市場"]
 score=0
 if systemic:score+=42
 if LEADER_RE.search(text):score+=24
 if LEADING_SECTOR_RE.search(text):score+=18
 if EXECUTIVE_RE.search(text):score+=16
 if BUSINESS_RE.search(text):score+=14
 if impact=="high":score+=12
 elif impact=="medium":score+=5
 if forced_scope=="market":score+=12
 is_major=(not company) and score>=45
 if is_major and impact=="low":impact="medium"
 verification_status="official" if forced_scope in {"market","company"} else "reference"
 return {"scope":scope,"company_announcement":company,"is_stock_news":stock_article,"is_major":is_major,"ai_category":category,"ai_topic":topic,"topic":topic,"impact":impact,"market_direction":direction,"affected_markets":affected,"confidence":"高" if score>=70 else "中","importance_score":score,"symbols":symbols,"verification_status":verification_status,"why_it_matters":f"此資訊可能影響{'、'.join(affected[:3])}的風險偏好、產業展望、估值或資金流向。" if is_major else f"此資訊主要影響{'、'.join(affected[:3])}，仍需配合正式數據與市場預期判斷。"}

def normalize_item(*,title:Any,url:Any,source_id:str,source_name:str,summary:Any="",published_at:Any=None,aliases:dict[str,str]|None=None,profiles:dict[str,dict[str,Any]]|None=None,forced_scope:str|None=None,base_url:str|None=None,extra:dict[str,Any]|None=None)->dict[str,Any]|None:
 title=clean_title(title);url=direct_url(url,base_url);summary=clean_text(summary)
 if len(title)<6 or GENERIC_RE.fullmatch(title) or not url or not readable_chinese(title,summary):return None
 dt=parse_datetime(published_at) or NOW
 analysis=classify(title,summary,aliases or {},forced_scope)
 profiles=profiles or {}
 companies=[profiles[symbol] for symbol in analysis.get("symbols",[]) if symbol in profiles]
 item={"id":hashlib.sha1(f"{source_id}|{title}|{url}".encode()).hexdigest()[:18],"source_id":source_id,"source":source_name,"title":title[:180],"url":url,"url_valid":True,"published_at":dt.isoformat(timespec="seconds"),"summary":summary[:400] or title,"ai_summary":summary[:400] or title,"language":"zh-Hant","companies":companies,**analysis}
 if extra:item.update(extra)
 image=direct_url(item.get("image_url")) if item.get("image_url") else None
 if image:item["image_url"]=image
 else:item.pop("image_url",None)
 return item

def dedupe(items:list[dict[str,Any]],days:int=14,limit:int=300)->list[dict[str,Any]]:
 cutoff=NOW-timedelta(days=days);out=[];seen=set()
 for item in sorted(items,key=lambda x:str(x.get("published_at") or ""),reverse=True):
  title=clean_title(item.get("title"));summary=clean_text(item.get("ai_summary") or item.get("summary"))
  if not readable_chinese(title,summary):continue
  item={**item,"title":title,"summary":summary or title,"ai_summary":summary or title,"language":"zh-Hant"}
  dt=parse_datetime(item.get("published_at"))
  if not dt or dt<cutoff:continue
  key=re.sub(r"\W+","",str(item.get("title") or "").lower())[:150]
  if not key or key in seen:continue
  seen.add(key);out.append(item)
 return out[:limit]

def save_channel(filename:str,varname:str,source_id:str,source_name:str,items:list[dict[str,Any]],health:dict[str,Any],retention_days:int=14,min_records:int=1)->dict[str,Any]:
 path=DATA/filename;old=read_json(path,{"items":[]})
 fresh=dedupe(items,retention_days)
 old_items=dedupe(old.get("items",[]),retention_days)
 if len(fresh)<min_records and old_items:
  combined=dedupe(fresh+old_items,retention_days)
  used=True
 else:combined=fresh;used=False
 status="ok" if len(fresh)>=min_records else "partial" if fresh else "fallback" if old_items else "warning"
 payload={"metadata":{"version":VERSION,"source_id":source_id,"source_name":source_name,"updated_at":NOW.isoformat(timespec="seconds"),"status":status,"fresh_count":len(fresh),"item_count":len(combined),"used_archive_fallback":used,"retention_days":retention_days,"language_policy":"zh-Hant-only","encoding_policy":"utf8-big5-cp950-auto"},"health":health,"items":combined}
 path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (DATA/(path.stem+"-seed.js")).write_text(f"window.{varname}="+json.dumps(payload,ensure_ascii=False,separators=(",",":"))+";\n",encoding="utf-8")
 return payload
