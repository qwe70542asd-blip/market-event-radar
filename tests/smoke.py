from pathlib import Path
import json,py_compile
R=Path(__file__).resolve().parents[1]
for p in (R/"scripts").glob("*.py"):py_compile.compile(str(p),doraise=True)
for p in (R/"data").glob("*.json"):json.loads(p.read_text(encoding="utf-8"))
print("PASS")
