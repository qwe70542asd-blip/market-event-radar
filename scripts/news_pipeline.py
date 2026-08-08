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

VERSION="v11.4.32"
ARCHIVE_START=datetime(2026,1,1,tzinfo=NOW.tzinfo)
RECENT_FULL_DAYS=30
MID_ARCHIVE_DAYS=90
HEADERS={"User-Agent":"Mozilla/5.0 (compatible; MarketEventRadar/11.4.32; +https://github.com/qwe70542asd-blip/market-event-radar)"}
COMPANY_EVENT_RE=re.compile(r"增資|減資|除權|除息|股利|法說|財報|財務報告|股東會|停牌|復牌|公開收購|併購|合併|處分資產|取得資產|重大合約|融資融券|注意股票|處置股票|庫藏股|董事會|重大訊息",re.I)
MARKET_HIGH_RE=re.compile(r"FOMC|聯準會|Fed\b|央行|CPI|PCE|GDP|非農|JOLTS|PMI|利率決策|升息|降息|關稅|制裁|戰爭|金融危機|熔斷|重大法規|匯率干預|資本管制|銀行危機|債務危機|財政危機|信用危機",re.I)
ASIA_RISK_RE=re.compile(r"日本銀行|日銀|BOJ|日圓|日債|日本國債|日本政府債務|日本企業倒閉|日本企業破產|匯市干預|韓國央行|韓元|KOSPI|KOSDAQ|中國房地產|中國房企|地方債|人民幣|亞洲貨幣|亞洲資金外流|貨幣競貶",re.I)
ASIA_STRESS_RE=re.compile(r"(?:創|跌至|貶至|升至|突破|失守).{0,10}(?:年|低點|高點)|暴跌|重貶|急貶|干預匯市|企業倒閉.{0,8}(?:增加|創高|突破)|破產.{0,8}(?:增加|創高)|債務.{0,8}(?:危機|失控|惡化)|房企.{0,8}(?:違約|倒閉)|地方債.{0,8}(?:風險|危機)|資金外流|信用風險",re.I)
ASIA_CROSS_BORDER_RE=re.compile(r"亞洲|台灣|台股|出口|供應鏈|半導體|觀光|航空|壽險|金融|匯率|資金流向",re.I)
MEDIUM_RE=re.compile(r"財報|營收|法說|政策|匯率|債券|半導體|AI|原油|除權|除息|增資|減資|融資融券|出口|進口|景氣|日圓|日債|韓元|人民幣|企業倒閉|房地產|地方債",re.I)

LEADER_RE=re.compile(r"台積電|鴻海|聯發科|廣達|緯創|國巨|川湖|日月光|台達電|中華電|長榮|陽明|NVIDIA|輝達|Microsoft|微軟|Apple|蘋果|Amazon|亞馬遜|Meta|Google|Alphabet|AMD|Intel|Tesla|三星|SK\s*海力士|海力士|Sony|Toyota",re.I)
LEADING_SECTOR_RE=re.compile(r"AI\s*伺服器|人工智慧|半導體|晶圓代工|記憶體|HBM|封裝測試|散熱|PCB|電源供應|雲端|資料中心|金融|航運|能源|原物料|機器人",re.I)
EXECUTIVE_RE=re.compile(r"執行長|董事長|財務長|總經理|基金經理人|分析師|首席經濟學家|央行總裁|官員|法說會|投資人會議|發表會|開發者大會|展覽|論壇|供應鏈會議",re.I)
BUSINESS_RE=re.compile(r"財報|財測|展望|營收|獲利|EPS|訂單|資本支出|擴產|漲價|降價|新品|新產品|合作|併購|投資",re.I)
POSITIVE_RE=re.compile(r"優於預期|上修|成長|創高|大增|獲利增加|降息|擴產|訂單增加|買超|利多|回升|改善",re.I)
NEGATIVE_RE=re.compile(r"低於預期|下修|衰退|虧損|暴跌|大跌|升息|制裁|關稅|減產|賣超|利空|違約|下滑|惡化|倒閉|破產|重貶|急貶|資金外流|信用風險",re.I)
GENERIC_RE=re.compile(r"^(?:TWSE\s*)?(?:(?:臺灣|台灣)證券交易所[>：:\-\s]*)?(?:首頁|新聞|最新消息|公文公告|公告查詢|新聞中心|個股資訊|台股新聞|財經新聞|即時新聞)$",re.I)
CJK_RE=re.compile(r"[\u3400-\u9fff]")
MOJIBAKE_RE=re.compile(r"(?:Ã|Â|â€|å[\x80-\xff]|æ[\x80-\xff]|ç[\x80-\xff]|è[\x80-\xff]|é[\x80-\xff]|ï¿½|�)")
SITE_SUFFIX_RE=re.compile(r"\s*(?:[-｜|]\s*)?(?:中央社|MoneyDJ(?:理財網)?|鉅亨網|經濟日報|自由財經|財富自由|Yahoo(?:奇摩)?股市|科技新報|財經新報|工商時報|twse\.com\.tw|tpex\.org\.tw|Google News)\s*$",re.I)
CODE_RE=re.compile(r"(?<!\d)(\d{4}|00\d{3}[A-Z]|00\d{4})(?!\d)",re.I)

CATEGORY_RULES=[
 ("日本與亞洲風險","asia-risk",ASIA_RISK_RE),
 ("央行與利率","macro",re.compile(r"聯準會|Fed\b|FOMC|央行|升息|降息|利率|殖利率",re.I)),
 ("總體經濟","macro",re.compile(r"CPI|PCE|GDP|非農|JOLTS|就業|失業|通膨|景氣|PMI|出口|進口",re.I)),
 ("企業財報","earnings",re.compile(r"財報|營收|獲利|EPS|法說|展望|財測|季報|年報",re.I)),
 ("半導體與 AI","technology",re.compile(r"AI|人工智慧|半導體|晶片|晶圓|GPU|伺服器|台積電|NVIDIA|輝達|記憶體",re.I)),
 ("政策與法規","policy",re.compile(r"政策|法規|關稅|制裁|補貼|金管會|行政院|立法院|交易制度",re.I)),
 ("地緣政治","geopolitics",re.compile(r"戰爭|衝突|軍事|地緣|停火|攻擊|選舉",re.I)),
 ("能源與原物料","commodities",re.compile(r"原油|石油|天然氣|黃金|銅價|原物料|OPEC",re.I)),
 ("匯率與債券","rates",re.compile(r"美元|日圓|新台幣|韓元|人民幣|匯率|債券|美債|日債",re.I)),
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

def _stock_master_rows()->list[dict[str,Any]]:
 # The full official stock-basics channel is authoritative for current listed stocks,
 # while assets.json remains the official stock/ETF master and ETF authority.  Never let a tiny bootstrap
 # stock-basics seed replace the larger official assets master, and never drop
 # ETFs merely because the stock-only channel is healthy.
 payload=read_json(DATA/"stock-basics.json",{"items":{}});items=payload.get("items") or {}
 stock_rows=[value for value in items.values() if isinstance(value,dict)] if isinstance(items,dict) else []
 assets=read_json(DATA/"assets.json",{"assets":[]}).get("assets",[])
 assets_rows=[value for value in assets if isinstance(value,dict) and value.get("market")=="TW" and value.get("asset_class") in {"stock","etf"}]
 if len(stock_rows)>=500:
  etf_rows=[value for value in assets_rows if value.get("asset_class")=="etf"]
  return [*stock_rows,*etf_rows]
 return assets_rows or stock_rows

def asset_aliases()->dict[str,str]:
 out={}
 for a in _stock_master_rows():
  symbol=str(a.get("symbol") or "").upper()
  if not symbol:continue
  names=[a.get("short_name"),a.get("name"),a.get("company_name"),*((a.get("aliases") or []))]
  for name in names:
   n=clean_text(name).lower()
   if len(n)>=2 and (n not in out or len(symbol)>len(out[n])):out[n]=symbol
 return out

def asset_profiles()->dict[str,dict[str,Any]]:
 out={}
 for a in _stock_master_rows():
  symbol=str(a.get("symbol") or "").upper()
  if not symbol:continue
  name=clean_text(a.get("short_name") or a.get("name") or a.get("company_name") or symbol)
  industry=clean_text(a.get("industry_name") or a.get("official_industry") or a.get("sub_industry") or a.get("industry") or (a.get("etf") or {}).get("category") or "")
  out[symbol]={"symbol":symbol,"name":name or symbol,"industry":industry,"asset_class":a.get("asset_class") or "stock"}
 return out

def infer_symbols(text:str,aliases:dict[str,str])->list[str]:
 valid_symbols=set(aliases.values());low=text.lower();found=[]
 aliases_by_symbol={}
 for name,symbol in aliases.items():aliases_by_symbol.setdefault(symbol,[]).append(name)
 # A number that happens to equal a real stock code is not enough.  Accept a
 # numeric code only when the article gives explicit stock-code context,
 # puts it in brackets, or names the matching company close to the code.  This
 # prevents phrases such as「上漲1250點、1270家上漲」from becoming securities.
 for m in CODE_RE.finditer(text):
  code=m.group(1).upper()
  if code not in valid_symbols:continue
  start,end=m.span();context=low[max(0,start-24):min(len(low),end+24)]
  numeric_context=bool(re.search(rf"(?:股票|證券|代號|stock|ticker|etf)[^0-9a-z]{{0,8}}{re.escape(code.lower())}",context,re.I) or re.search(rf"[（(\[]\s*{re.escape(code.lower())}\s*[）)\]]",context,re.I))
  named=any(name and name in context for name in aliases_by_symbol.get(code,[]))
  if numeric_context or named:found.append(code)
 occupied=[]
 # Longest-name-first matching prevents 南亞 from matching inside 南亞科.
 for name,symbol in sorted(aliases.items(),key=lambda item:(-len(item[0]),item[0])):
  if symbol in found:continue
  for match in re.finditer(re.escape(name),low):
   span=match.span()
   if any(not (span[1]<=old[0] or span[0]>=old[1]) for old in occupied):continue
   found.append(symbol);occupied.append(span);break
 return list(dict.fromkeys(found))[:10]

def classify(title:str,summary:str,aliases:dict[str,str],forced_scope:str|None=None)->dict[str,Any]:
 text=f"{title} {summary}";symbols=infer_symbols(text,aliases)
 media_mode=forced_scope=="media"
 company=forced_scope=="company" or (not media_mode and bool(symbols and COMPANY_EVENT_RE.search(text)))
 stock_article=media_mode and bool(symbols)
 systemic=bool(MARKET_HIGH_RE.search(text))
 asia_risk=bool(ASIA_RISK_RE.search(text));asia_stress=bool(ASIA_STRESS_RE.search(text));asia_cross_border=bool(ASIA_CROSS_BORDER_RE.search(text))
 market=forced_scope=="market" or systemic or asia_risk
 scope="company" if company else "stock" if stock_article else "market" if market else "general"
 category,topic="市場動態","market"
 for label,tp,pat in CATEGORY_RULES:
  if pat.search(text):category,topic=label,tp;break
 if company:category,topic="個股公告","company"
 elif stock_article and category=="市場動態":category,topic="個股新聞","stock"
 impact="high" if systemic or (asia_risk and asia_stress) else "medium" if asia_risk or MEDIUM_RE.search(text) else "low"
 pos,neg=bool(POSITIVE_RE.search(text)),bool(NEGATIVE_RE.search(text))
 direction="多空混合" if pos and neg else "偏多" if pos else "偏空" if neg else "中性"
 affected=[]
 for pat,vals in [
  (re.compile(r"台灣|台股|證交所|櫃買|新台幣",re.I),["台股"]),(re.compile(r"半導體|晶片|台積電|NVIDIA|輝達|AI|記憶體",re.I),["半導體","科技股"]),
  (re.compile(r"美股|NASDAQ|S&P|道瓊|聯準會|Fed\b",re.I),["美股"]),(re.compile(r"日本|日經|日圓|日銀|日本銀行|日債",re.I),["日股","日圓"]),(re.compile(r"韓國|KOSPI|KOSDAQ|韓元|韓國央行",re.I),["韓股","韓元"]),(re.compile(r"中國|人民幣|港股|中國房地產|地方債",re.I),["中港股","人民幣"]),(re.compile(r"亞洲|資金外流|貨幣競貶",re.I),["亞洲市場"]),
  (re.compile(r"美元|匯率|日圓|新台幣|韓元",re.I),["匯率"]),(re.compile(r"債券|美債|殖利率",re.I),["債券"]),
  (re.compile(r"原油|石油|天然氣|黃金|銅價",re.I),["原物料"]),(re.compile(r"金融|銀行|保險",re.I),["金融股"]),
  (re.compile(r"航運|海運|運價",re.I),["航運股"]),(re.compile(r"航空|觀光|旅遊|赴日",re.I),["航空觀光"]),(re.compile(r"壽險|保險業|避險成本",re.I),["壽險金融"]),(re.compile(r"出口|供應鏈|競爭力",re.I),["台灣出口產業"])]:
  if pat.search(text):affected.extend(vals)
 if (company or stock_article) and symbols:affected=symbols
 affected=list(dict.fromkeys(affected))[:5] or ["整體市場"]
 score=0
 if systemic:score+=42
 if asia_risk:score+=18
 if asia_risk and asia_stress:score+=26
 if asia_risk and asia_cross_border:score+=10
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
 return {"scope":scope,"regional_risk":"asia" if asia_risk else None,"risk_signals":{"asia_topic":asia_risk,"stress":asia_stress,"cross_border":asia_cross_border},"company_announcement":company,"is_stock_news":stock_article,"is_major":is_major,"ai_category":category,"ai_topic":topic,"topic":topic,"impact":impact,"market_direction":direction,"affected_markets":affected,"confidence":"高" if score>=70 else "中","importance_score":score,"symbols":symbols,"verification_status":verification_status,"why_it_matters":f"此資訊可能影響{'、'.join(affected[:3])}的風險偏好、產業展望、估值或資金流向。" if is_major else f"此資訊主要影響{'、'.join(affected[:3])}，仍需配合正式數據與市場預期判斷。"}

def normalize_item(*,title:Any,url:Any,source_id:str,source_name:str,summary:Any="",published_at:Any=None,aliases:dict[str,str]|None=None,profiles:dict[str,dict[str,Any]]|None=None,forced_scope:str|None=None,base_url:str|None=None,extra:dict[str,Any]|None=None)->dict[str,Any]|None:
 title=clean_title(title);url=direct_url(url,base_url);summary=clean_text(summary)
 if len(title)<6 or GENERIC_RE.fullmatch(title) or not url or not readable_chinese(title,summary):return None
 # Unknown publication time is not equivalent to "published now".  The old
 # fallback polluted today's feed with undated navigation/category pages.
 dt=parse_datetime(published_at)
 if dt is None:return None
 analysis=classify(title,summary,aliases or {},forced_scope)
 profiles=profiles or {}
 companies=[profiles[symbol] for symbol in analysis.get("symbols",[]) if symbol in profiles]
 item={"id":hashlib.sha1(f"{source_id}|{title}|{url}".encode()).hexdigest()[:18],"source_id":source_id,"source":source_name,"title":title[:180],"url":url,"url_valid":True,"published_at":dt.isoformat(timespec="seconds"),"summary":summary[:400] or title,"ai_summary":summary[:400] or title,"language":"zh-Hant","companies":companies,**analysis}
 if extra:item.update(extra)
 final_symbols=[str(symbol).upper() for symbol in item.get("symbols") or [] if symbol]
 if forced_scope in {"company","media"} and final_symbols:
  item["symbols"]=list(dict.fromkeys(final_symbols))[:10]
  item["companies"]=[profiles[symbol] for symbol in item["symbols"] if symbol in profiles]
  item["affected_markets"]=item["symbols"][:5]
  item["why_it_matters"]=f"此資訊主要影響{'、'.join(item['affected_markets'][:3])}，仍需配合正式數據與市場預期判斷。"
 image=direct_url(item.get("image_url")) if item.get("image_url") else None
 if image:item["image_url"]=image
 else:item.pop("image_url",None)
 return item

def _news_datetime(item:dict[str,Any])->datetime|None:
 dt=parse_datetime(item.get("published_at") or item.get("date"))
 if dt and dt.tzinfo is None:dt=dt.replace(tzinfo=NOW.tzinfo)
 return dt.astimezone(NOW.tzinfo) if dt else None

def archive_priority(item:dict[str,Any],dt:datetime)->int:
 age=max(0,(NOW-dt).days)
 score=int(item.get("importance_score") or 0)
 if item.get("is_major"):score+=40
 if item.get("impact")=="high":score+=28
 elif item.get("impact")=="medium":score+=10
 if item.get("source_id") in {"official-notices","company-disclosures"}:score+=24
 if item.get("symbols") or item.get("companies"):score+=8
 if item.get("image_url"):score+=3
 if len(clean_text(item.get("ai_summary") or item.get("summary")))>=40:score+=4
 score+=max(0,40-min(age,120)//3)
 return score

def keep_in_archive(item:dict[str,Any],dt:datetime)->bool:
 if dt<ARCHIVE_START or dt>NOW+timedelta(days=1):return False
 age=max(0,(NOW-dt).days);priority=archive_priority(item,dt)
 if age<=RECENT_FULL_DAYS:return True
 if age<=MID_ARCHIVE_DAYS:return priority>=24 or bool(item.get("symbols"))
 return priority>=58 or bool(item.get("is_major")) or item.get("impact")=="high"

def dedupe(items:list[dict[str,Any]],days:int=14,limit:int=600)->list[dict[str,Any]]:
 prepared=[];seen=set();month_counts={}
 for raw in sorted(items,key=lambda x:str(x.get("published_at") or x.get("date") or ""),reverse=True):
  title=clean_title(raw.get("title"));summary=clean_text(raw.get("ai_summary") or raw.get("summary"))
  if not readable_chinese(title,summary):continue
  item={**raw,"title":title,"summary":summary or title,"ai_summary":summary or title,"language":"zh-Hant"}
  dt=_news_datetime(item)
  if not dt or not keep_in_archive(item,dt):continue
  key=re.sub(r"\W+","",str(item.get("title") or "").lower())[:150]
  if not key or key in seen:continue
  age=max(0,(NOW-dt).days);month=dt.strftime("%Y-%m")
  quota=9999 if age<=RECENT_FULL_DAYS else 90 if age<=MID_ARCHIVE_DAYS else 24
  if month_counts.get(month,0)>=quota:continue
  month_counts[month]=month_counts.get(month,0)+1
  seen.add(key);prepared.append((dt,archive_priority(item,dt),item))
 prepared.sort(key=lambda row:(row[0],row[1]),reverse=True)
 return [item for _,__,item in prepared[:limit]]

def legacy_now_fallback(item:dict[str,Any],old_metadata:dict[str,Any])->bool:
 # v11.4.30 and older normalized an unknown publication timestamp to the
 # updater's NOW.  On migration, any archived row stamped within five seconds
 # of that updater run is untrustworthy and must not outrank corrected source
 # timestamps in the new feed.
 if str(old_metadata.get("version") or "")==VERSION:return False
 updated=_news_datetime({"published_at":old_metadata.get("updated_at")})
 published=_news_datetime(item)
 return bool(updated and published and abs((published-updated).total_seconds())<=5)

def save_channel(filename:str,varname:str,source_id:str,source_name:str,items:list[dict[str,Any]],health:dict[str,Any],retention_days:int=14,min_records:int=1)->dict[str,Any]:
 path=DATA/filename;old=read_json(path,{"items":[]});old_metadata=old.get("metadata") or {}
 fetched=dedupe(items,retention_days)
 old_raw=[];legacy_removed=0
 for row in old.get("items",[]):
  suspicious_official=source_id=="official-notices" and bool(re.search(r"/(?:np|lp)-\d",str(row.get("url") or ""),re.I))
  if legacy_now_fallback(row,old_metadata) or suspicious_official:
   legacy_removed+=1;continue
  old_raw.append(row)
 old_items=dedupe(old_raw,retention_days)
 combined=dedupe(fetched+old_items,retention_days)
 used=bool(old_items and (not fetched or len(combined)>len(fetched)))
 recent_24h=sum(1 for item in combined if (lambda dt: bool(dt and timedelta(0)<=NOW-dt<=timedelta(hours=24)))(_news_datetime(item)))
 status="ok" if len(fetched)>=min_records else "partial" if fetched else "fallback" if old_items else "warning"
 payload={"metadata":{"version":VERSION,"source_id":source_id,"source_name":source_name,"updated_at":NOW.isoformat(timespec="seconds"),"status":status,"fresh_count":recent_24h,"fetched_count":len(fetched),"recent_24h_count":recent_24h,"item_count":len(combined),"used_archive_fallback":used,"legacy_archive_removed":legacy_removed,"recent_full_retention_days":RECENT_FULL_DAYS,"archive_start":ARCHIVE_START.date().isoformat(),"archive_limit":600,"archive_policy":"newest-first; older than 30 days requires higher importance; before 2026-01-01 is deleted","sort_order":"published_at_desc","language_policy":"zh-Hant-only","encoding_policy":"utf8-big5-cp950-auto"},"health":health,"items":combined}
 path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 (DATA/(path.stem+"-seed.js")).write_text(f"window.{varname}="+json.dumps(payload,ensure_ascii=False,separators=(",",":"))+";\n",encoding="utf-8")
 return payload
