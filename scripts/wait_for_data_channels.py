#!/usr/bin/env python3
"""Wait until isolated live-data branches all reach the requested release."""
from __future__ import annotations
import argparse, json, subprocess, time

CHANNELS = {
    "live-assets": ("assets.json", "asset-audit.json"),
    "live-tw-market": ("tw-market.json",),
    "live-monthly-revenue": ("monthly-revenue.json",),
    "live-dividend-history": ("dividend-history.json",),
    "live-secondary-reference": ("secondary-reference.json",),
    "live-yahoo-details": ("yahoo-details.json",),
    "live-etf-details": ("etf-details.json",),
}

def file_version(branch:str,path:str)->str:
    proc=subprocess.run(["git","show",f"origin/{branch}:{path}"],capture_output=True,text=True,encoding="utf-8")
    if proc.returncode:return ""
    try:return str((json.loads(proc.stdout).get("metadata") or {}).get("version") or "")
    except Exception:return ""

def snapshot(target:str)->dict[str,str]:
    out={}
    for branch,paths in CHANNELS.items():
        subprocess.run(["git","fetch","--quiet","origin",branch],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for path in paths:out[f"{branch}:{path}"]=file_version(branch,path)
    return out

def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("version");ap.add_argument("--attempts",type=int,default=60);ap.add_argument("--sleep",type=float,default=10)
    args=ap.parse_args()
    for attempt in range(1,args.attempts+1):
        versions=snapshot(args.version)
        pending={k:v for k,v in versions.items() if v!=args.version}
        if not pending:
            print(f"release barrier reached {args.version}: {len(versions)} channel files")
            return 0
        print(f"release barrier {attempt}/{args.attempts}; pending={pending}",flush=True)
        if attempt<args.attempts:time.sleep(args.sleep)
    print(f"timed out waiting for isolated data channels to reach {args.version}",flush=True)
    return 1
if __name__=="__main__":raise SystemExit(main())
