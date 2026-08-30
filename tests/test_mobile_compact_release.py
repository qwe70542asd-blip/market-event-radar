from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(path): return (ROOT/path).read_text(encoding="utf-8")

def test_empty_portfolio_collapses_six_metric_cards():
    js=read("assets/home.js");css=read("assets/v11.4.58-overrides.css")
    assert 'classList.toggle("portfolio-empty",rows.length===0)' in js
    assert '.portfolio-summary.portfolio-empty .portfolio-summary-grid{display:none}' in css

def test_mobile_calendar_uses_single_filter_bottom_sheet():
    html=read("index.html");css=read("assets/v11.4.58-overrides.css");js=read("assets/home.js")
    assert '<summary><span>篩選</span>' in html
    assert 'id="calendarClearFilters"' in html and 'id="calendarApplyFilters"' in html
    assert 'grid-template-areas:"search filter" "summary summary"' in css
    assert '.calendar-filter-details-body{position:fixed!important' in css
    assert 'calendarFilterDetails.open=false' in js

def test_mobile_calendar_badges_are_readable_and_yellow_is_high_contrast():
    css=read("assets/v11.4.58-overrides.css")
    for token in ('font-size:12px!important','width:11px!important','min-height:23px!important','background:#ffd25f!important'):
        assert token in css

def test_phone_floating_rail_is_disabled():
    css=read("assets/v11.4.58-overrides.css")
    assert '.home-shell>.floating-quick-nav:not(.mobile-global-quick-nav){display:none!important}' in css
