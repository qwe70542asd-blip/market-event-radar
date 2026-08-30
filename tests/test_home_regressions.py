from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(path): return (ROOT/path).read_text(encoding="utf-8")

def test_calendar_is_homepage_primary_surface_and_market_precedes_portfolio():
    html=read("index.html")
    assert html.index('id="calendarPanel"') < html.index('id="todayMarketBrief"')
    assert html.index('id="calendarPanel"') < html.index('id="marketStateSummary"')
    assert html.index('id="marketStateSummary"') < html.index('id="portfolioSummary"')
    assert html.index('id="latestNews"') > html.index('id="dateAlertPanel"')

def test_calendar_advanced_filters_are_collapsed_by_default():
    html=read("index.html");css=read("assets/v11.4.57-overrides.css")
    assert '<details class="calendar-filter-details" id="calendarFilterDetails">' in html
    assert 'id="calendarActiveFilterText"' in html
    assert '<details class="calendar-filter-details" id="calendarFilterDetails" open' not in html
    assert '.calendar-filter-details>summary' in css

def test_phone_quick_nav_is_single_fixed_left_rail_not_content_row():
    html=read("index.html");shared=read("assets/shared.js");css=read("assets/v11.4.57-overrides.css")
    assert html.count('class="floating-quick-nav"') == 1
    assert 'position:fixed!important;left:3px!important' in css
    assert 'top:50%!important;transform:translateY(-50%)!important' in css
    assert 'nav.innerHTML=' not in shared.split('function installGlobalMobileQuickNav(){',1)[1].split('function syncMobileNavCurrent',1)[0]

def test_reference_ahead_can_show_verified_partial_live_taiex():
    js=read("assets/stale-market-guard.js")
    assert 'function applyPartialMarket()' in js
    assert 'state.partialLive=!!(state.marketStale&&state.referenceAhead&&referenceChange!=null)' in js
    assert 'setText("marketTone",`${tone} ${partialChange(referenceChange)}`' in js
    assert '全市場廣度、成交動能與法人資料仍等待' in js

def test_major_information_has_nonblank_verified_fallback_candidates():
    home=read("assets/home.js")
    assert 'const fallbackEvents=' in home
    assert 'const fallbackNews=' in home
    assert '_featureLabel:"近期事件"' in home
    assert '_featureLabel:"最近可用"' in home
    assert 'for(const item of candidates)' in home
