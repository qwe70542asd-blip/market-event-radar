from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
def read(path): return (ROOT/path).read_text(encoding="utf-8")

def test_v11451_major_information_stays_one_plus_three_equal_height():
    css=read("assets/v11.4.53-overrides.css");home=read("assets/home.js")
    assert "height:360px" in css
    assert "grid-template-rows:238px 122px" in css
    assert "grid-template-rows:repeat(3,minmax(0,1fr))" in css
    assert "slice(0,4)" in home and "featured.slice(1,4)" in home

def test_v11451_full_event_archive_is_the_only_home_calendar_authority():
    home=read("assets/home.js");alerts=read("assets/date-alerts.js");index=read("index.html");workflow=read(".github/workflows/update-events.yml");shared=read("assets/shared.js")
    assert 'loadData("events.json"' in home
    assert 'loadData("events.json"' in alerts
    assert "data/events-seed.js" in index
    for text in (home,alerts,index,workflow,shared):
        assert "events-index" not in text
    assert not (ROOT/"data/events-index.json").exists()
    assert not (ROOT/"data/events-index-seed.js").exists()
    assert not (ROOT/"scripts/build_event_index.py").exists()

def test_v11451_event_fallback_is_never_mistaken_for_complete_live_data():
    home=read("assets/home.js")
    assert "eventFeedReady" in home
    assert "線上事件資料同步中" in home
    assert 'briefEventCount:eventCountText' in home

def test_v11451_breaking_date_only_and_region_fixes_are_preserved():
    home=read("assets/home.js");shared=read("assets/shared.js");index=read("index.html")
    assert 'BREAKING_RE.test(storyText)&&item._majorScore>=70?"突發／關鍵"' in home
    assert 'const featureRank={"突發／關鍵":0' in home
    assert "formatEventTime" in shared and "時間未公告" in home
    assert '<option value="EU">歐洲</option>' in index
    assert '<option value="UK">英國</option>' in index

def test_v11451_foreign_direction_and_rollover_fixes_are_preserved():
    home=read("assets/home.js")
    assert "markets.tpex?.institutional?.foreign_net" in home
    assert "chipsCurrent" in home
    assert "refreshDayKeys" in home and "checkDayBoundary" in home

def test_v11451_service_worker_does_not_precache_full_event_archive_as_core():
    sw=read("service-worker.js");register=read("assets/sw-register.js")
    assert "CORE_STATIC" in sw and "OPTIONAL_STATIC" in sw and "Promise.allSettled" in sw
    core=sw.split("const CORE_STATIC=",1)[1].split(";",1)[0]
    assert "events-seed.js" not in core
    assert "events-index" not in sw
    assert 'register("service-worker.js",{updateViaCache:"none"})' in register

def test_v11451_runtime_worker_remains_schema_gated():
    runtime=read("assets/runtime-config.js")
    assert 'body?.schema_version===SCHEMA_VERSION' in runtime
    assert "body?.version===APP_VERSION" not in runtime
    assert "direct-worker-verified" in runtime and "github-fallback-only" in runtime

def test_v11451_producers_still_use_version_source_of_truth():
    common=read("scripts/common.py")
    assert 'VERSION_INFO=read_json(ROOT/"VERSION.json"' in common
    for file in (ROOT/"scripts").glob("update_*.py"):
        text=file.read_text(encoding="utf-8")
        assert not re.search(r'^VERSION\s*=\s*"v\d+\.\d+\.\d+"',text,re.M), file

def test_v11452_live_payloads_cannot_silently_replace_complete_archives():
    shared=read("assets/shared.js");common=read("scripts/common.py");events=read("scripts/update_events.py")
    for token in ("ARCHIVE_REGRESSION_FILES","isCatastrophicPayloadRegression","payloadCardinality","Rejected catastrophic"):
        assert token in shared
    assert 'if(Array.isArray(payload.items))return payload.items.length>0;' in shared
    assert 'Object.keys(payload.items).length>0;' in shared
    assert 'PROTECTED_COLLECTION_FILES' in common and 'guard_against_catastrophic_shrink' in common
    assert 'assert_event_archive_not_catastrophically_shrunk' in events


def test_v11452_service_worker_uses_new_atomic_cache_namespace():
    sw=read("service-worker.js")
    assert 'market-event-radar-v11-4-53' in sw
    assert 'market-event-radar-v11-4-50' not in sw


def test_v11452_verification_publisher_restores_its_previous_archive_before_replace():
    workflow=read(".github/workflows/update-data-verification.yml")
    assert 'restore_data_branch.sh live-data-verification "data-verification.json:data/data-verification.json"' in workflow
    assert workflow.index('restore_data_branch.sh live-data-verification') < workflow.index('python scripts/update_data_verification.py')
