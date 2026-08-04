#!/usr/bin/env python3
from __future__ import annotations
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
    item=normalize_item(title=title,url=official,source_id="company-disclosures",source_name=source,summary=body or subject,published_at=f"{date or ''} {spoke_time or ''}",aliases=ALIASES,forced_scope="company",extra={"symbols":[code] if code else [],"key_facts":[row for row in [{"label":"股票代碼","value":code},{"label":"公司","value":name},{"label":"事實發生日","value":str(fact_date or '')},{"label":"符合條款","value":str(clause or '')}] if row["value"]],"official_sequence":seq,"fact_date":fact_date,"clause":clause})
    if item:items.append(item);count+=1
   health.append({"name":source,"status":"ok" if count else "warning","count":count,"url":url})
  except Exception as exc:health.append({"name":source,"status":"warning","error":str(exc),"url":url})
 payload=save_channel("company-disclosures.json","__COMPANY_DISCLOSURE_SEED__","company-disclosures","個股重大訊息",items,{"sources":health},90,1)
 print(payload["metadata"])
if __name__=="__main__":main()
