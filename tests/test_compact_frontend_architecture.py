from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def read(path): return (ROOT/path).read_text(encoding='utf-8')

def test_home_never_boots_full_heavy_archives():
    home=read('assets/home.js')
    for name in ('assets.json','events.json','tw-chips.json','dividend-history.json'):
        assert f'loadData("{name}"' not in home
    for name in ('home-assets.json','home-events.json','tw-market-compact.json','tw-chips-compact.json'):
        assert f'loadData("{name}"' in home

def test_institutional_never_downloads_yahoo_or_full_chip_archive():
    inst=read('assets/institutional.js')
    assert 'loadData("tw-chips.json"' not in inst
    assert 'loadData("yahoo-details.json"' not in inst
    assert 'loadData("tw-chips-compact.json"' in inst
    assert 'loadData("tw-market-compact.json"' in inst

def test_event_page_uses_compact_archive_before_full_fallback():
    event=read('assets/event.js')
    assert event.index('loadData("home-events.json"') < event.index('loadData("events.json"')

def test_asset_shards_are_two_digit_buckets():
    asset=read('assets/asset.js'); builder=read('scripts/update_asset_detail_shards.py')
    assert 'symbol.slice(0,2)' in asset
    assert 'first-two-symbol-characters' in builder
    assert 'range(100)' in builder

def test_frontend_payload_budget_files_exist_and_are_json():
    budgets={'home-assets.json':800_000,'home-events.json':2_000_000,'tw-market-compact.json':2_000_000,'tw-chips-compact.json':4_000_000}
    for name,budget in budgets.items():
        path=ROOT/'data'/name
        assert path.exists(), name
        json.loads(path.read_text(encoding='utf-8'))
        assert path.stat().st_size <= budget

def test_current_release_has_no_old_active_version_refs():
    version=json.loads(read('VERSION.json'))['version']
    assert version=='v11.5.0'
    for path in ['index.html','asset.html','institutional.html','news.html','tw-market.html','portfolio.html','data-status.html','404.html','service-worker.js','assets/shared.js']:
        text=read(path)
        assert 'v11.4.62' not in text
        assert '11.4.62' not in text

def test_compact_channels_are_registered_on_live_verification_branch():
    shared=read('assets/shared.js')
    for name in ('home-assets.json','home-events.json','tw-market-compact.json','tw-chips-compact.json'):
        assert f'"{name}":"live-data-verification"' in shared


def test_legacy_duplicate_mobile_quick_nav_system_is_removed():
    shared=read('assets/shared.js'); css=read('assets/v11.5.0-overrides.css')
    assert 'installGlobalMobileQuickNav' not in shared
    assert 'mobile-global-quick-nav' not in shared
    assert 'mobile-global-quick-nav' not in css

def test_no_primary_page_boots_known_full_heavy_archives():
    files=['assets/home.js','assets/institutional.js','assets/portfolio.js','assets/tw-market.js','assets/asset.js','assets/date-alerts.js','assets/stale-market-guard.js']
    text='\n'.join(read(f) for f in files)
    for name in ('assets.json','tw-market.json','tw-chips.json','dividend-history.json','yahoo-details.json'):
        assert f'loadData("{name}"' not in text
    assert 'loadData("events.json"' not in text
