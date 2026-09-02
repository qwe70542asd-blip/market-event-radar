from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(path):return (ROOT/path).read_text(encoding='utf-8')
def test_all_app_pages_load_shared_mobile_release_css():
    for name in ('index.html','asset.html','portfolio.html','tw-market.html','institutional.html','news.html','event.html','data-status.html'):
        text=read(name);assert 'assets/v11.4.61-overrides.css?v=11.4.61' in text,name;assert 'assets/shared.js?v=11.4.61' in text,name
def test_phone_quick_navigation_is_single_owner_and_does_not_cover_content():
    css=read('assets/v11.4.61-overrides.css');html=read('index.html')
    assert html.count('class="floating-quick-nav"')==1
    assert '.mobile-global-quick-nav{display:none!important}' in css
    assert 'bottom:calc(62px + env(safe-area-inset-bottom))!important' not in css
    assert 'padding-bottom:calc(82px + env(safe-area-inset-bottom))!important' in css
    assert 'position:fixed!important;left:3px!important' in css
    assert 'position:relative!important' not in css
def test_shared_ui_never_injects_a_second_four_action_bar():
    shared=read('assets/shared.js')
    assert 'if(document.querySelector(".floating-quick-nav")||document.querySelector(".mobile-nav"))return;' in shared
    assert 'floating-quick-nav mobile-global-quick-nav' not in shared
    assert 'shell.appendChild(nav)' not in shared
def test_install_button_only_appears_when_install_is_actionable():
    js=read('assets/pwa-install.js')
    assert 'btn.hidden=!ios' in js
    assert 'beforeinstallprompt' in js and 'btn.hidden=false' in js
    assert 'appinstalled' in js and 'btn.hidden=true' in js

def test_asset_page_has_small_account_quick_read_and_watchlist():
    html=read('asset.html');js=read('assets/asset.js');assert 'id="retailBasicsSection"' in html;assert 'id="toggleWatchlist"' in html;assert 'standardBrokerFeeRate=.001425' in js;assert 'sellTaxRate=isEtf?(isBondEtf?null:.001):.003' in js;assert '近一年價格位置' in js;assert '最新月營收 YoY' in js;assert 'toggleWatchlist' in js
def test_watchlist_is_local_only_and_reused_by_portfolio():
    shared=read('assets/shared.js');portfolio=read('assets/portfolio.js');assert 'marketRadarWatchlistV1' in shared
    for token in ('loadWatchlist','saveWatchlist','toggleWatchlist'):assert token in shared
    assert 'renderWatchlist' in portfolio and 'data-watch-calc' in portfolio and 'data-watch-del' in portfolio
def test_portfolio_has_small_account_cost_tools_and_return_percentages():
    html=read('portfolio.html');js=read('assets/portfolio.js')
    for token in ('id="retailTools"','id="retailToolPrice"','id="retailToolBudget"','id="totalReturn"','報酬率'):assert token in html
    assert 'renderRetailCalculator' in js and 'taxRate=type==="etf"?.001:.003' in js and 'Math.floor(budget/(price*(1+standardBrokerFeeRate)))' in js and 'plPct=' in js
