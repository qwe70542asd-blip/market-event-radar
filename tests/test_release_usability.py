from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
def read(path): return (ROOT/path).read_text(encoding="utf-8")

def test_v11450_major_information_is_one_plus_three_equal_height():
    css=read("assets/v11.4.50-overrides.css");home=read("assets/home.js")
    assert "height:360px" in css
    assert "grid-template-rows:238px 122px" in css
    assert "grid-template-rows:repeat(3,minmax(0,1fr))" in css
    assert "slice(0,4)" in home
    assert "featured.slice(1,4)" in home

def test_v11450_breaking_requires_breaking_signal_and_ranks_first():
    home=read("assets/home.js")
    assert 'BREAKING_RE.test(storyText)&&item._majorScore>=70?"突發／關鍵"' in home
    assert 'const featureRank={"突發／關鍵":0' in home
    assert "item._majorScore>=35" in home

def test_v11450_date_only_events_never_claim_invented_time():
    shared=read("assets/shared.js");home=read("assets/home.js");events=read("scripts/update_events.py")
    assert "formatEventTime" in shared
    assert "時間未公告" in home
    assert 'start:`${day}T00:00:00+08:00`' in home
    assert "start=at_taipei(day, 0, 0)" in events or "start = at_taipei(day, 0, 0)" in events

def test_v11450_homepage_uses_compact_event_index_and_lazy_full_archive():
    home=read("assets/home.js");index=read("index.html");workflow=read(".github/workflows/update-events.yml")
    assert 'loadData("events-index.json"' in home
    assert "ensureFullEventArchive" in home
    assert "events-index-seed.js" in index
    assert "python scripts/build_event_index.py" in workflow
    assert "data/events-index.json" in workflow

def test_v11450_service_worker_upgrade_is_resilient():
    sw=read("service-worker.js");register=read("assets/sw-register.js")
    assert "CORE_STATIC" in sw and "OPTIONAL_STATIC" in sw
    assert "Promise.allSettled" in sw
    core=sw.split("const CORE_STATIC=",1)[1].split(";",1)[0]
    assert "events-seed.js" not in core
    assert 'register("service-worker.js",{updateViaCache:"none"})' in register
    assert 'const VERSION="11.4.46"' not in register

def test_v11450_runtime_worker_is_schema_gated_not_patch_gated():
    runtime=read("assets/runtime-config.js");readiness=read("scripts/production_readiness.py")
    assert 'body?.schema_version===SCHEMA_VERSION' in runtime
    assert "body?.version===VERSION" not in runtime
    assert "workerVersion" in runtime
    assert "frontend runtime must use schema compatibility" in readiness

def test_v11450_calendar_has_eu_uk_and_rollover():
    index=read("index.html");home=read("assets/home.js")
    assert '<option value="EU">歐洲</option>' in index
    assert '<option value="UK">英國</option>' in index
    assert "refreshDayKeys" in home and "checkDayBoundary" in home
    assert "mr-calendar-mode-v1" in home

def test_v11450_foreign_direction_uses_both_markets_and_stale_date_guard():
    home=read("assets/home.js")
    assert "markets.tpex?.institutional?.foreign_net" in home
    assert "chipsCurrent" in home
    assert "法人 ${chipDate" in home

def test_v11450_producers_use_version_source_of_truth():
    common=read("scripts/common.py")
    assert 'VERSION_INFO=read_json(ROOT/"VERSION.json"' in common
    for file in (ROOT/"scripts").glob("update_*.py"):
        text=file.read_text(encoding="utf-8")
        assert not re.search(r'^VERSION\s*=\s*"v\d+\.\d+\.\d+"',text,re.M), file
