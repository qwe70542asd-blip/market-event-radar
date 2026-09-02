from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(path): return (ROOT/path).read_text(encoding="utf-8")


def test_home_never_exposes_unknown_numeric_industry_codes():
    home=read("assets/home.js")
    assert "normalizeHomeIndustry" in home
    assert 'if(/^\\d+$/.test(raw))return""' in home
    assert "HOME_INDUSTRY_NAMES" in home
    assert "normalizeHomeIndustry(asset.official_industry" in home


def test_yahoo_supplement_is_freshness_gated_on_asset_and_chips_pages():
    asset=read("assets/asset.js"); chips=read("assets/institutional.js")
    assert "yahooIsFresh" in asset
    assert "Yahoo 過期補充已停用" in asset
    assert "freshYahooRow" in chips
    assert "Date.now()-yahooStamp<=96*3600*1000" in asset
    assert "Date.now()-stamp<=96*3600*1000" in chips


def test_institutional_current_cards_require_verified_market_session():
    chips=read("assets/institutional.js")
    assert "verifiedMarketDate" in chips
    assert "lotsCurrent" in chips
    assert "等待 ${escapeHtml(expected)}" in chips
    assert "sameCurrentSession" in chips


def test_health_page_uses_compact_health_index_only():
    shared=read("assets/shared.js"); status=read("assets/data-status.js")
    assert '"channel-health.json":"live-data-verification"' in shared
    assert 'loadData("channel-health.json"' in status
    assert "Promise.allSettled(jobs)" not in status
    assert "critical_bad_count" in status


def test_verification_workflow_refreshes_health_four_times_hourly_and_version_is_dynamic():
    workflow=read(".github/workflows/update-data-verification.yml")
    for minute in ("13","28","43","58"):
        assert f'cron: "{minute} * * * *"' in workflow
    assert "python scripts/update_channel_health.py" in workflow
    assert 'json.load(open("VERSION.json"' in workflow
    assert "data/channel-health.json" in workflow


def test_release_gate_derives_version_and_includes_sealed_regressions():
    workflow=read(".github/workflows/release-verification.yml")
    assert 'echo "EXPECTED_VERSION=$VERSION"' in workflow
    assert 'production_readiness.py --version "$EXPECTED_VERSION"' in workflow
    assert "tests/test_sealed_reliability.py" in workflow
    assert "tests/test_channel_health.py" in workflow
