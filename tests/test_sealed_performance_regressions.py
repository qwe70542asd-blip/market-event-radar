from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(path): return (ROOT/path).read_text(encoding="utf-8")

def test_unknown_numeric_industry_codes_never_render_as_labels():
    home=read("assets/home.js"); asset=read("assets/asset.js"); leaders=read("assets/dynamic-leaders.js")
    assert 'validHomeIndustryLabel' in home
    assert 'Numeric taxonomy values such as 91' in home
    assert '其他／未分類' in asset
    assert 'return"其他"' in leaders
    assert 'industry=validHomeIndustryLabel' in home

def test_asset_page_uses_bounded_seed_bootstrap_only():
    html=read("asset.html")
    for required in ("data/tw-market-seed.js", "data/events-seed.js", "data/stock-news-seed.js", "assets/asset.js"):
        assert required in html
    for forbidden in ("data/assets-seed.js", "data/tw-chips-seed.js", "data/yahoo-details-seed.js", "data/etf-details-seed.js", "data/stock-basics-seed.js", "data/monthly-revenue-seed.js", "data/dividend-history-seed.js", "data/data-verification-seed.js"):
        assert forbidden not in html

def test_service_worker_does_not_prefetch_optional_data_storm():
    sw=read("service-worker.js")
    install=sw.split('self.addEventListener("install"',1)[1].split('self.addEventListener("activate"',1)[0]
    assert 'Promise.allSettled(OPTIONAL_STATIC' not in install
    optional=sw.split('const OPTIONAL_STATIC=',1)[1].split(';',1)[0]
    assert 'data/news-cna-seed.js' not in optional
    assert 'data/yahoo-details-seed.js' not in optional

def test_service_worker_upgrade_forces_one_clean_reload():
    reg=read("assets/sw-register.js")
    assert 'controllerchange' in reg
    assert 'sessionStorage.getItem(RELOAD_KEY)' in reg
    assert 'location.reload()' in reg
    assert 'service-worker.js?v=' in reg

def test_home_news_refresh_is_concurrency_bounded():
    shared=read("assets/shared.js"); home=read("assets/home.js")
    assert 'const concurrency=' in shared
    assert 'Array.from({length:Math.min(concurrency,NEWS_FILES.length)}' in shared
    assert 'startNewsChannels({concurrency:2' in home
