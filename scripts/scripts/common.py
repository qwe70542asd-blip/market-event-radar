from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
DATA=Path(__file__).resolve().parents[1]/"data"
NOW=datetime.now(ZoneInfo("Asia/Taipei"))
def read_json(path,default):
 try:return json.loads(Path(path).read_text(encoding="utf-8"))
 except Exception:return default
def write_payload(name,var,payload):
 p=DATA/name;p.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 if var:(DATA/(p.stem+"-seed.js")).write_text(f"window.{var} = "+json.dumps(payload,ensure_ascii=False,separators=(",",":"))+";\n",encoding="utf-8")
