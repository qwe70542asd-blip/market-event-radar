#!/usr/bin/env python3
from common import *
import requests
def main():
 old=read_json(DATA/"assets.json",{"assets":[]});by={x.get("id") or f"{x.get('market')}:{x.get('symbol')}":x for x in old.get("assets",[])};warn=[]
 for url,ex in [("https://openapi.twse.com.tw/v1/opendata/t187ap03_L","TWSE"),("https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O","TPEx")]:
  try:
   rows=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},timeout=25).json()
   for x in rows:
    s=str(x.get("公司代號") or x.get("SecuritiesCompanyCode") or "").strip();n=x.get("公司簡稱") or x.get("CompanyAbbreviation") or x.get("公司名稱") or ""
    if not s:continue
    key=f"TW:{s}";by[key]={**by.get(key,{}),"id":key,"asset_class":"stock","market":"TW","exchange":ex,"symbol":s,"name":n,"company_name":x.get("公司名稱") or n,"official_industry":x.get("產業別") or x.get("Industry") or by.get(key,{}).get("official_industry"),"currency":"TWD"}
  except Exception as e:warn.append(f"{ex}:{e}")
 payload={"metadata":{"version":"v11.3.0","updated_at":NOW.isoformat(timespec="seconds"),"warnings":warn},"assets":sorted(by.values(),key=lambda x:(x.get("market","") ,x.get("symbol","")))};write_payload("assets.json","__ASSET_SEED__",payload)
if __name__=="__main__":main()
