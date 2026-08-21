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

def write_payload(name,var,payload):
    target=DATA/name
    target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if var:
        (DATA/(target.stem+"-seed.js")).write_text(
            f"window.{var} = "+json.dumps(payload,ensure_ascii=False,separators=(",",":"))+";\n",
            encoding="utf-8",
        )
