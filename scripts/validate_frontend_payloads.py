#!/usr/bin/env python3
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
BUDGETS={
 'home-assets.json': 800_000,
 'home-events.json': 2_000_000,
 'tw-market-compact.json': 2_000_000,
 'tw-chips-compact.json': 4_000_000,
}

def main():
    failures=[]
    for name,budget in BUDGETS.items():
        path=DATA/name
        if not path.exists(): failures.append(f'{name}: missing'); continue
        size=path.stat().st_size
        try: json.loads(path.read_text(encoding='utf-8'))
        except Exception as e: failures.append(f'{name}: invalid json {e}'); continue
        print(f'{name}: {size:,} / {budget:,} bytes')
        if size>budget: failures.append(f'{name}: {size:,} exceeds {budget:,}')
    if failures:
        raise SystemExit('frontend payload budget failed: '+'; '.join(failures))

if __name__=='__main__': main()
