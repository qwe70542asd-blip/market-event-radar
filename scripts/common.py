from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
NOW=datetime.now(ZoneInfo("Asia/Taipei"))

def read_json(path,default):
    try:return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:return default

VERSION_INFO=read_json(ROOT/"VERSION.json",{"version":"v0.0.0"})
VERSION=str(VERSION_INFO.get("version") or "v0.0.0")
VERSION_NUMBER=VERSION.removeprefix("v")

PROTECTED_COLLECTION_FILES={
    "assets.json","stock-basics.json","yahoo-details.json","etf-details.json",
    "monthly-revenue.json","dividend-history.json","data-verification.json",
    "market-kline.json","market-volume-history.json","tw-chips.json","tw-market.json","secondary-reference.json",
    *(f"asset-detail-shard-{index}.json" for index in range(10)),
}

def payload_cardinality(payload):
    if not isinstance(payload,dict): return 0
    items=payload.get("items")
    if isinstance(items,(list,dict)): return len(items)
    assets=payload.get("assets")
    if isinstance(assets,list): return len(assets)
    return 0

def guard_against_catastrophic_shrink(name,previous,current):
    """Block partial scraper output from replacing a large last-known-good dataset."""
    if name not in PROTECTED_COLLECTION_FILES: return
    before,after=payload_cardinality(previous),payload_cardinality(current)
    if before < 100: return
    minimum=max(25,int(before*0.45))
    if after < minimum:
        raise RuntimeError(f"Catastrophic dataset shrink blocked for {name}: {before} -> {after}; minimum {minimum}")

def write_payload(name,var,payload):
    target=DATA/name
    previous=read_json(target,{}) if target.exists() else {}
    guard_against_catastrophic_shrink(name,previous,payload)
    target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if var:
        (DATA/(target.stem+"-seed.js")).write_text(
            f"window.{var} = "+json.dumps(payload,ensure_ascii=False,separators=(",",":"))+";\n",
            encoding="utf-8",
        )
