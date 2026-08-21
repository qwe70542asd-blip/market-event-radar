from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(path): return (ROOT/path).read_text(encoding='utf-8')

def test_v11448_one_by_four_quick_navigation_and_priority_strip():
    html=read('index.html');css=read('assets/v11.4.48-overrides.css')
    assert 'today-market-brief' in html
    assert 'grid-template-columns:96px' in css
    assert 'grid-auto-rows:58px' in css
    assert html.count('class="quick-tile') == 4

def test_v11448_major_information_has_fixed_desktop_geometry():
    css=read('assets/v11.4.48-overrides.css')
    for token in ('height:510px','grid-template-rows:345px 165px','height:345px','max-height:510px'):
        assert token in css

def test_v11448_day_dialog_keeps_close_control_visible_and_has_escape_backdrop_close():
    css=read('assets/v11.4.48-overrides.css');home=read('assets/home.js')
    for token in ('height:min(88dvh,900px)','grid-template-rows:auto minmax(0,1fr)','overflow:auto','scrollbar-gutter:stable'):
        assert token in css
    for token in ('event.target===dialog','event.key==="Escape"','event.preventDefault();closeDayDialog()'):
        assert token in home

def test_v11448_major_news_covers_market_structure_and_multiple_industries():
    home=read('assets/home.js')
    for token in ('MARKET_STRUCTURE_RE','零股','撮合','交易制度','AI_SECTOR_RE','FINANCE_RE','SHIPPING_RE','ENERGY_RE','BIOTECH_RE','REAL_ESTATE_RE','DEFENSE_RE','ROBOTICS_RE'):
        assert token in home
    assert 'selectDiverseNews' in home
    assert 'used>=2&&item._majorScore<88' in home

def test_v11448_corroborated_explicit_news_dates_can_join_calendar_without_single_source_guessing():
    home=read('assets/home.js')
    for token in ('explicitNewsDate','NEWS_EVENT_ACTION_RE','derivedNewsEvents','reported-corroborated','single-media dates remain news, not confirmed calendar facts'):
        assert token in home
    assert 'reports>0||["cna","official-notices"].includes(sourceId)' in home

def test_v11448_large_company_day_is_progressively_disclosed():
    home=read('assets/home.js')
    assert 'groups.company.slice(0,36)' in home
    assert 'show-all-company-events' in home
    assert '顯示全部 ${groups.company.length} 筆公司資訊' in home
