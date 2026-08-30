from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT/path).read_text(encoding="utf-8")


def test_home_has_market_heat_risk_and_sector_momentum_cards():
    html=read("index.html"); js=read("assets/home.js")
    for token in ("marketHeatScore","marketHeatFill","todayRiskLabel","sectorMomentum","今日產業動能","市場上漲熱度"):
        assert token in html
    for token in ("renderMarketInsights","riskPoints","official_industry","median(values)","sector-momentum-row"):
        assert token in js


def test_calendar_uses_dot_count_markers_instead_of_mobile_bars():
    html=read("index.html");js=read("assets/home.js");css=read("assets/v11.4.58-overrides.css")
    for token in ("calendar-legend","legend-dot major","legend-dot macro","legend-dot company","legend-dot dividend"):
        assert token in html
    for token in ('calendarMarker("major"','calendarMarker("macro"','calendarMarker("company"','calendarMarker("dividend"',"calendar-markers"):
        assert token in js
    assert '.calendar-day>.event-pill{display:none!important}' in css
    assert '.calendar-marker i' in css


def test_mobile_calendar_keeps_instruction_visible_and_opens_as_bottom_sheet():
    css=read("assets/v11.4.58-overrides.css")
    assert '.calendar-meta span:last-child{display:block!important' in css
    assert 'inset:auto 0 0 0!important' in css
    assert 'border-radius:20px 20px 0 0!important' in css
    assert 'height:min(78dvh,760px)!important' in css


def test_new_dashboard_refreshes_when_market_or_asset_channels_upgrade():
    js=read("assets/home.js")
    assert 'assets=fresh;rebuildAssets();renderPortfolioSummary();renderMarketInsights()' in js
    assert 'tw=fresh;rebuildQuotes();renderMarketList();renderTaiwanStatus();renderPortfolioSummary();renderTodayBrief()' in js
    assert 'chips=fresh;renderTaiwanStatus();renderTodayBrief()' in js


def test_old_mobile_duplicate_nav_injection_cannot_return():
    shared=read("assets/shared.js");css=read("assets/v11.4.58-overrides.css")
    assert 'nav.innerHTML=' not in shared.split('function installGlobalMobileQuickNav(){',1)[1].split('function syncMobileNavCurrent',1)[0]
    assert 'shell.appendChild(nav)' not in shared
    assert 'mobile-global-quick-nav{display:grid' not in css


def test_pages_do_not_duplicate_ids_or_asset_references():
    import re
    for path in ROOT.glob("*.html"):
        text=path.read_text(encoding="utf-8")
        ids=re.findall(r'\bid="([^"]+)"',text)
        assert len(ids)==len(set(ids)),f"duplicate id in {path.name}"
        refs=re.findall(r'<(?:script|link)\b[^>]+(?:src|href)="([^"]+)"',text)
        local=[ref for ref in refs if not ref.startswith(("http://","https://","#"))]
        assert len(local)==len(set(local)),f"duplicate script/style reference in {path.name}"
