from pathlib import Path
import json
import re

ROOT=Path(__file__).resolve().parents[1]
def read(path): return (ROOT/path).read_text(encoding="utf-8")


def test_home_bootstrap_is_single_deferred_seed_bundle():
    html=read("index.html")
    scripts=re.findall(r'<script\s+([^>]*?)src="([^"]+)"[^>]*></script>',html,re.I)
    assert len(scripts)<=10
    assert 'data/home-bootstrap-seed.js?v=11.5.1' in html
    for attrs,src in scripts:
        assert 'defer' in attrs, src
    for old in (
        'data/events-seed.js','data/assets-seed.js','data/news-cna-seed.js',
        'data/stock-news-seed.js','data/tw-market-seed.js','data/tw-chips-seed.js',
        'data/market-snapshot-seed.js','data/market-kline-seed.js'):
        assert old not in html
    bundle=read('data/home-bootstrap-seed.js')
    for token in ('__EVENT_SEED__','__ASSET_SEED__','__TW_MARKET_SEED__','__MARKET_SNAPSHOT_SEED__'):
        assert token in bundle


def test_shared_runtime_dedupes_requests_and_defers_legacy_storage_cleanup():
    shared=read('assets/shared.js')
    for token in ('HTTP_INFLIGHT=new Map()','DATA_INFLIGHT','canonicalJsonKey','FAST_BOOT_WINDOW_MS=15000',
                  'STORAGE_CLEANUP_KEY="mr-storage-cleanup-v11.5.1"','market-radar-last-good-v11.5.1',
                  'scheduleLegacyBrowserCleanup','requestIdleCallback'):
        assert token in shared
    assert 'for(const name of Object.keys(CHANNELS))' not in shared
    assert 'mr-data-last-good-v11.4' not in shared
    assert 'market-radar-last-good-v1' in shared  # deletion target only


def test_home_live_refresh_and_news_boot_are_bounded():
    home=read('assets/home.js')
    assert 'startNewsChannels({concurrency:1,startDelay:1200,staggerMs:120' in home
    assert 'lastLiveRefreshAt=Date.now()' in home
    assert 'Date.now()-lastLiveRefreshAt<liveRefreshGap()' in home
    assert 'window.addEventListener("focus",()=>refreshLiveMarketData())' in home


def test_stale_guard_does_not_force_duplicate_market_requests_during_first_paint():
    guard=read('assets/stale-market-guard.js')
    assert 'const start=()=>assess(false)' in guard
    assert 'setTimeout(()=>assess(true),15000)' in guard
    assert 'setTimeout(()=>assess(true),2000)' not in guard


def test_service_worker_has_atomic_build_cache_without_version_mix_or_reload_loop():
    sw=read('service-worker.js'); reg=read('assets/sw-register.js')
    assert 'CACHE_NAME="market-event-radar-v11-5-1"' in sw
    assert 'NETWORK_INFLIGHT=new Map()' in sw
    assert 'cacheFirst(request)' in sw
    assert 'ignoreSearch:false' in sw and 'ignoreSearch:true' not in sw
    assert 'keys.filter(key=>key.startsWith(CACHE_PREFIX)&&key!==CACHE_NAME)' in sw
    assert 'location.reload()' not in reg
    assert 'purgeLegacyCaches' in reg
    assert 'updateViaCache:"none"' in reg


def test_workflows_resolve_release_version_instead_of_embedding_release_number():
    workflows='\n'.join(p.read_text(encoding='utf-8') for p in (ROOT/'.github/workflows').glob('*.yml'))
    assert 'group: release-verification-${{ github.ref }}' in workflows
    assert '--require-live --version "$EXPECTED_VERSION"' in workflows
    assert '=="v11.5.1"' not in workflows
    assert 'verify-v11-5-1-${{ github.ref }}' not in workflows


def test_active_data_metadata_is_current_release():
    expected=json.loads(read('VERSION.json'))['version']
    assert expected=='v11.5.1'
    mismatches=[]
    for path in (ROOT/'data').glob('*.json'):
        try: payload=json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError: continue
        metadata=payload.get('metadata') if isinstance(payload,dict) else None
        if isinstance(metadata,dict) and metadata.get('version') and metadata.get('version')!=expected:
            mismatches.append((path.name,metadata.get('version')))
    assert not mismatches, mismatches
