#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime
import re,requests
from common import NOW
from news_pipeline import HEADERS,asset_aliases,normalize_item,save_channel,clean_text
ALIASES=asset_aliases()
ENDPOINTS=[("上市重大訊息","https://openapi.twse.com.tw/v1/opendata/t187ap04_L"),("上櫃重大訊息","https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O")]
def norm(s):return re.sub(r"[^0-9a-z\u3400-\u9fff]+","",str(s or "").lower())
def val(row,*aliases):
 keyed={norm(k):v for k,v in row.items()}
 for a in aliases:
  n=norm(a)
  if n in keyed:return keyed[n]
 for a in aliases:
  n=norm(a)
  for k,v in keyed.items():
   if n and (n in k or k in n):return v
 return None



def publication_datetime(date_value,time_value):
 date_digits=re.sub(r"\D","",str(date_value or ""));time_digits=re.sub(r"\D","",str(time_value or ""))
 try:
  if len(date_digits)==7:y,mo,day=int(date_digits[:3])+1911,int(date_digits[3:5]),int(date_digits[5:7])
  elif len(date_digits)>=8:y,mo,day=int(date_digits[:4]),int(date_digits[4:6]),int(date_digits[6:8])
  else:return None
  clock=time_digits.zfill(6)[-6:] if time_digits else "000000"
  hour,minute,second=int(clock[:2]),int(clock[2:4]),int(clock[4:6])
  return datetime(y,mo,day,hour,minute,second,tzinfo=NOW.tzinfo).isoformat(timespec="seconds")
 except (TypeError,ValueError):return None

def format_fact_date(value):
 text=str(value or "").strip()
 digits=re.sub(r"\D","",text)
 if len(digits)==7:
  return f"{int(digits[:3])+1911}/{digits[3:5]}/{digits[5:7]}"
 if len(digits)==8:
  return f"{digits[:4]}/{digits[4:6]}/{digits[6:8]}"
 m=re.search(r"(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})",text)
 if m:return f"{int(m.group(1))+1911}/{int(m.group(2)):02d}/{int(m.group(3)):02d}"
 return text

def concise_disclosure_summary(subject,body,name):
 body=clean_text(body);subject=clean_text(subject)
 candidates=[]
 for label in ("發生緣由","說明","因應措施","報導內容","其他應敘明事項"):
  m=re.search(rf"(?:^|\s)\d*[.、．]?\s*{label}[：:]\s*(.*?)(?=\s+\d+[.、．]\s*[^：:]{1,18}[：:]|$)",body)
  if m:candidates.append(m.group(1))
 for candidate in candidates+[body]:
  text=clean_text(candidate)
  text=re.sub(r"民國\s*(\d{2,3})年(\d{1,2})月(\d{1,2})日",lambda m:f"{int(m.group(1))+1911}/{int(m.group(2)):02d}/{int(m.group(3)):02d}",text)
  text=re.sub(r"(?<!\d)(\d{2,3})/(\d{1,2})/(\d{1,2})(?!\d)",lambda m:f"{int(m.group(1))+1911}/{int(m.group(2)):02d}/{int(m.group(3)):02d}",text)
  text=re.sub(r"\s*\((\d+)\)\s*","；",text).strip("； ")
  text=re.sub(r"^(?:本公司|公司)?(?:公告)?[：:]?\s*","",text)
  text=re.sub(r"\s*\d+[.、．]\s*[^：:]{1,18}[：:].*$","",text)
  if subject and text.startswith(subject):text=text[len(subject):].lstrip("：:，,。 ")
  if len(text)>=12:
   if len(text)>125:text=text[:125].rstrip("，,；;：: ")+"…"
   return text
 return f"{name or '公司'}發布重大訊息，詳細內容可展開查看。"

def main():
 items=[];health=[]
 for source,url in ENDPOINTS:
  try:
   r=requests.get(url,headers=HEADERS,timeout=28);r.raise_for_status();rows=r.json();count=0
   for row in rows if isinstance(rows,list) else []:
    code=str(val(row,"公司代號","證券代號","股票代號","CompanyCode") or "").strip();name=clean_text(val(row,"公司簡稱","公司名稱","證券名稱","CompanyName"));subject=clean_text(val(row,"主旨","重大訊息主旨","Subject","Title"));body=clean_text(val(row,"說明","內容","Description","Content"))
    title=" ".join(x for x in [code,name,subject] if x).strip()
    date=val(row,"發言日期","發布日期","日期","Date");spoke_time=val(row,"發言時間","發布時間","Time");seq=val(row,"序號","Sequence","Seq");fact_date=val(row,"事實發生日","EventDate");clause=val(row,"符合條款","Clause")
    official=val(row,"網址","URL","Link")
    if not official and code:
     official=f"https://mops.twse.com.tw/mops/web/t05sr01_1?step=1&firstin=1&off=1&TYPEK=all&co_id={code}&spoke_date={date or ''}&spoke_time={spoke_time or ''}&seq_no={seq or ''}"
    if not official:official=url
    short_summary=concise_disclosure_summary(subject,body,name)
    published=publication_datetime(date,spoke_time)
    item=normalize_item(title=title,url=official,source_id="company-disclosures",source_name=source,summary=short_summary,published_at=published,aliases=ALIASES,forced_scope="company",extra={"symbols":[code] if code else [],"short_summary":short_summary,"full_text":body[:6000],"key_facts":[fact for fact in [{"label":"股票代碼","value":code},{"label":"公司","value":name},{"label":"事實發生日","value":format_fact_date(fact_date)},{"label":"符合條款","value":str(clause or '')}] if fact["value"]],"official_sequence":seq,"fact_date":fact_date,"clause":clause,"publication_date_verified":bool(published)})
    if item:items.append(item);count+=1
   health.append({"name":source,"status":"ok" if count else "warning","count":count,"url":url})
  except Exception as exc:health.append({"name":source,"status":"warning","error":str(exc),"url":url})
 payload=save_channel("company-disclosures.json","__COMPANY_DISCLOSURE_SEED__","company-disclosures","個股重大訊息",items,{"sources":health},90,1)
 print(payload["metadata"])
if __name__=="__main__":main()
