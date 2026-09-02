from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_v1151_version_marker():
    text=(ROOT/"VERSION.json").read_text(encoding="utf-8")
    assert '"version": "v11.5.1"' in text

def test_fast_boot_precedes_runtime_and_scripts_are_deferred():
    html=(ROOT/"index.html").read_text(encoding="utf-8")
    assert 'assets/v11.5.1-fast-boot.js?v=11.5.1' in html
    assert html.index("v11.5.1-fast-boot.js") < html.index("data/assets-seed.js")
    external=[part for part in html.split("<script ")[1:] if 'src="' in part]
    assert external
    assert all("defer" in part.split(">",1)[0] for part in external)

def test_stale_guard_does_not_force_duplicate_boot_fetch():
    text=(ROOT/"assets"/"stale-market-guard.js").read_text(encoding="utf-8")
    assert "{force:true}" not in text
    assert "requestIdleCallback" in text
    assert "setTimeout(assess,15000)" in text

def test_shared_has_clean_version_and_shorter_mirror_timeout():
    text=(ROOT/"assets"/"shared.js").read_text(encoding="utf-8")
    assert 'APP_VERSION="v11.5.1"' in text
    assert "timeout=6200" not in text
    assert "timeout=2600" in text
    assert "mr-data-cache-v11.4.46" not in text

def test_service_worker_does_not_reload_page_on_controller_change():
    text=(ROOT/"assets"/"sw-register.js").read_text(encoding="utf-8")
    assert 'BUILD="v11.5.1"' in text
    assert "location.reload()" not in text
    assert "requestIdleCallback" in text

def test_service_worker_precache_is_small_and_versioned():
    text=(ROOT/"service-worker.js").read_text(encoding="utf-8")
    assert 'CACHE_NAME="market-event-radar-v11-5-1"' in text
    assert "events-seed.js" not in text
    assert "market-snapshot-seed.js" not in text
    assert "v11.5.1-fast-boot.js" in text
