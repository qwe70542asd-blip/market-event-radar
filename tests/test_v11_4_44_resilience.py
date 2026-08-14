from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(path): return (ROOT/path).read_text(encoding='utf-8')

def test_home_has_independent_late_arrival_rerenders():
    home=read('assets/home.js')
    assert 'function renderTaiwanStatus()' in home
    assert 'twLivePromise.then' in home and 'renderTaiwanStatus()' in home
    assert 'chipsLivePromise.then' in home
    assert 'stockNewsLivePromise.then' in home
    assert 'newsStream.done.then' in home
    assert 'eventLivePromise.then' in home
    assert 'withBootTimeout' not in home

def test_home_taiwan_freshness_uses_taiwan_channel_only():
    home=read('assets/home.js')
    assert 'const quoteAgeMinutes=()=>{const stamp=Date.parse(tw.metadata?.updated_at||0)' in home
    assert 'snapshot.metadata?.updated_at,...(snapshot.items||[]).map(row=>row.market_at)' not in home
    assert 'parts.push(`行情 ${formatTime(twStamp)}`)' in home
    assert 'parts.push(`籌碼 ${formatTime(chipsStamp)}`)' in home

def test_home_high_impact_corporate_events_are_featured():
    home=read('assets/home.js')
    assert 'eventGroup(event)==="company"&&event.impact==="high"' in home

def test_news_loader_is_progressive_and_partial_success_safe():
    shared=read('assets/shared.js')
    news=read('assets/news.js')
    assert 'function startNewsChannels(options={})' in shared
    assert 'Promise.allSettled(promises)' in shared
    assert 'resolved_channel_count' in shared
    assert 'startNewsChannels({onUpdate' in news
    assert '已完成的新聞來源會先顯示' in news

def test_loader_uses_hedged_mirrors_and_indexeddb_last_good():
    shared=read('assets/shared.js')
    assert 'index*850' in shared
    assert 'indexedDB.open(LAST_GOOD_DB,1)' in shared
    assert 'await readLastGood(name)' in shared
    assert 'void rememberLastGood(name,payload)' in shared
    assert 'await new Promise(resolve=>setTimeout(resolve,0))' in shared
    assert 'setTimeout(async()=>{if(settled)return;' in shared

def test_service_worker_normalizes_cache_busting_query():
    sw=read('service-worker.js')
    assert 'u.searchParams.delete("t")' in sw
    assert 'u.searchParams.delete("_")' in sw
    assert 'cache.match(key,{ignoreSearch:true})' in sw

def test_other_pages_no_longer_bind_optional_sources_at_boot():
    tw=read('assets/tw-market.js'); inst=read('assets/institutional.js'); event=read('assets/event.js'); portfolio=read('assets/portfolio.js'); status=read('assets/data-status.js')
    assert 'Promise.all([loadData("tw-market.json"' not in tw
    assert 'loadStockBasics().then' in tw
    assert 'Promise.all([' not in inst.split('\n',12)[0:12].__str__()
    assert 'loadData("yahoo-details.json",yahooPayload).then' in inst
    assert '事件資料同步中' in event and 'startNewsChannels({onUpdate' in event
    assert 'loadData("assets.json",assets).then' in portfolio
    assert 'Promise.allSettled(jobs)' in status

def test_browser_smoke_exercises_delayed_live_rerender():
    smoke=read('scripts/browser_smoke.py')
    for token in ('await wait(5200)','breadthSummary','foreignDirection','台積電 AI 伺服器財報重大進展','測試公司 Q2 財報申報截止','delayed live rerender'):
        assert token in smoke
