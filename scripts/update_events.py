#!/usr/bin/env python3
"""Merge manual events with the previous verified event archive.

This updater deliberately never invents release dates. Existing live-data events
are retained until their configured expiry window; manual events can be added in
data/manual-events.json. The workflow restores the previous live file before run.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil import parser as dateparser

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
OUT=DATA/"events.json"
SEED=DATA/"events-seed.js"
MANUAL=DATA/"manual-events.json"
NOW=datetime.now(ZoneInfo("Asia/Taipei"))


def load(path:Path,default):
    try:return json.loads(path.read_text(encoding="utf-8"))
    except Exception:return default


def stable_id(row:dict)->str:
    if row.get("id"):return str(row["id"])
    raw=f'{row.get("title","")}|{row.get("start","")}|{row.get("region","")}'
    return "manual-"+hashlib.sha1(raw.encode("utf-8")).hexdigest()[:14]


def main()->None:
    previous=load(OUT,{"events":[],"sources":[]})
    manual=load(MANUAL,[])
    rows=[*(previous.get("events") or []),*(manual if isinstance(manual,list) else manual.get("events",[]))]
    cutoff=NOW-timedelta(days=35)
    end=NOW+timedelta(days=370)
    merged={}
    for raw in rows:
        try:
            start=dateparser.parse(str(raw.get("start") or ""))
            if not start.tzinfo:start=start.replace(tzinfo=NOW.tzinfo)
            start=start.astimezone(NOW.tzinfo)
        except Exception:
            continue
        if not cutoff<=start<=end:continue
        row={**raw,"id":stable_id(raw),"start":start.isoformat(timespec="seconds")}
        merged[row["id"]]=row
    events=sorted(merged.values(),key=lambda row:row["start"])
    if not events and previous.get("events"):
        raise SystemExit("No events after merge; previous archive was not replaced.")
    payload={"metadata":{"version":"v11.1.5","updated_at":NOW.isoformat(timespec="seconds"),
        "timezone":"Asia/Taipei","event_count":len(events),
        "note":"Verified previous archive plus manual official-source events; no guessed dates."},
        "sources":previous.get("sources") or [],"events":events}
    OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    SEED.write_text("window.__EVENT_SEED__ = "+json.dumps(payload,ensure_ascii=False)+";\n",encoding="utf-8")
    print("events",len(events))


if __name__=="__main__":
    main()
