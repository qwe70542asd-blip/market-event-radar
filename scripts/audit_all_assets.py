#!/usr/bin/env python3
from common import *
import csv
REQ_STOCK=["name","exchange","official_industry","metrics","financials"];REQ_ETF=["name","exchange","etf"]
def main():
 p=read_json(DATA/"assets.json",{"assets":[]});out=[]
 for x in p.get("assets",[]):
  if x.get("market")!="TW" or x.get("asset_class") not in {"stock","etf"}:continue
  req=REQ_ETF if x.get("asset_class")=="etf" else REQ_STOCK;missing=[k for k in req if not x.get(k)];pct=round((len(req)-len(missing))/len(req)*100,2);out.append({"symbol":x.get("symbol"),"name":x.get("name"),"asset_class":x.get("asset_class"),"exchange":x.get("exchange"),"status":"complete" if not missing else "partial","coverage_percent":pct,"missing_fields":missing,"missing_reasons":["official_source_or_parser_missing"]*len(missing)})
 s={"audited_assets":len(out),"stock_count":sum(x["asset_class"]=="stock" for x in out),"etf_count":sum(x["asset_class"]=="etf" for x in out),"complete":sum(x["status"]=="complete" for x in out),"partial":sum(x["status"]=="partial" for x in out),"unresolved":0,"audit_coverage_percent":100.0};payload={"metadata":{"version":"v11.3.0","updated_at":NOW.isoformat(timespec="seconds")},"summary":s,"assets":out};write_payload("asset-audit.json","__ASSET_AUDIT_SEED__",payload);(DATA/"asset-coverage.json").write_text(__import__('json').dumps({"metadata":payload["metadata"],"summary":s},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 with (DATA/"asset-audit-failures.csv").open("w",newline="",encoding="utf-8-sig") as f:
  wr=csv.writer(f);wr.writerow(["symbol","name","asset_class","exchange","status","coverage_percent","missing_fields","missing_reasons"])
  for x in out:
   if x["missing_fields"]:wr.writerow([x["symbol"],x["name"],x["asset_class"],x["exchange"],x["status"],x["coverage_percent"]," | ".join(x["missing_fields"])," | ".join(x["missing_reasons"])])
if __name__=="__main__":main()
