from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_guard_has_independent_market_and_chip_states():
    js=(ROOT/'assets/stale-market-guard.js').read_text(encoding='utf-8')
    assert 'const marketStale=' in js and 'const chipsStale=' in js
    assert '(!referenceDate&&fallbackTooOld(marketDate))' in js
    assert 'const chipsStale=!marketStale&&(!chipDate||chipDate<marketDate)' in js
    assert 'applyChipStale' in js
    assert 'Keep valid price/breadth/volume conclusions' in js
    assert 'if(state.marketStale)applyMarketStale();else if(state.chipsStale)applyChipStale()' in js

def test_long_holiday_uses_verified_reference_before_calendar_age():
    js=(ROOT/'assets/stale-market-guard.js').read_text(encoding='utf-8')
    assert 'referenceAhead=!!(referenceDate&&marketDate&&referenceDate>marketDate)' in js
    assert '!referenceDate&&fallbackTooOld(marketDate)' in js


def test_guard_truth_table_with_node():
    import subprocess, json
    js=(ROOT/'assets/stale-market-guard.js').read_text(encoding='utf-8')
    prefix='global.window={MR:null};global.document={readyState:"loading",addEventListener:()=>{},getElementById:()=>null};\n'
    suffix='\nconst f=global.__MR_ASSESS_TW_DATES__;console.log(JSON.stringify([f("2026-02-13","2026-02-13","2026-02-13"),f("2026-08-28","2026-08-27","2026-08-28"),f("2026-08-27","2026-08-27","2026-08-28"),f("","2026-08-27","2026-08-28")]));'
    try:
        run=subprocess.run(['node','-e',prefix+js+suffix],text=True,capture_output=True,check=True)
    except FileNotFoundError:
        return
    rows=json.loads(run.stdout.strip().splitlines()[-1])
    assert rows[0]['marketStale'] is False and rows[0]['chipsStale'] is False
    assert rows[1]['marketStale'] is False and rows[1]['chipsStale'] is True
    assert rows[2]['marketStale'] is True
    assert rows[3]['marketStale'] is True
