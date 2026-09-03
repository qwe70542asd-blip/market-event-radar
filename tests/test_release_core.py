from pathlib import Path
import importlib.util
import sys

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0,str(SCRIPTS))

import news_pipeline
import update_data_verification
import update_etf_details
import update_stock_basics


def test_canonical_url_dedupes_headline_edits():
    rows=[
        {
            'title':'蘋果庫克投重磅炸彈稱百年一遇暴漲這兩家公司盆滿缽滿',
            'url':'https://example.com/news/5534001?utm_source=x',
            'published_at':news_pipeline.NOW.isoformat(),
            'summary':'這是一段足夠長的中文新聞摘要內容，用來測試同網址改標題後仍然只能保留一筆。',
        },
        {
            'title':'蘋果庫克投重磅炸彈稱百年一遇暴漲這兩家公司繼續盆滿缽滿',
            'url':'https://example.com/news/5534001',
            'published_at':news_pipeline.NOW.isoformat(),
            'summary':'這是一段足夠長的中文新聞摘要內容，用來測試同網址改標題後仍然只能保留一筆。',
        },
    ]
    assert len(news_pipeline.dedupe(rows)) == 1


def test_numeric_money_amount_not_stock_code():
    aliases={'台積電':'2330','大統新創':'1470'}
    found=news_pipeline.infer_symbols('女股神購入1470萬美元的台積電股票',aliases)
    assert '2330' in found
    assert '1470' not in found


def test_ambiguous_media_and_phrase_aliases_are_suppressed():
    assert news_pipeline.infer_symbols('工商時報報導國際油價連三跌',{'時報':'8923'}) == []
    assert news_pipeline.infer_symbols('台糖表示自主進口黃豆產製成品油',{'及成':'3095'}) == []


def test_short_real_company_alias_still_matches():
    found=news_pipeline.infer_symbols('群創飆高，台積電同步走強',{'群創':'3481','台積電':'2330'})
    assert set(found) == {'3481','2330'}


def test_etf_text_fields_are_not_sent_through_numeric_comparator():
    status,values=update_data_verification.text_status_for('不適用','不適用','official')
    assert status == 'multi_source'
    assert values == ['不適用','不適用']
    status,values=update_data_verification.text_status_for(None,'摩根投信','official')
    assert status == 'official'
    assert values == ['摩根投信']
    assert update_data_verification.normalize_benchmark_value('無 投資策略 主動投資台灣股票 主題/因子 AI') == '不適用'


def test_twse_active_etf_benchmark_stops_before_strategy(monkeypatch):
    from bs4 import BeautifulSoup
    html='''<html><body><h2>主動測試基金</h2><div>證券簡稱 主動測試 證券類別 主動式ETF 發行公司 測試投信 基金經理人 王小明 標的指數 無 投資策略 主動投資台灣股票 主題/因子 AI 資產規模 10 億元 受益人次 1 萬人</div></body></html>'''
    soup=BeautifulSoup(html,'lxml')
    monkeypatch.setattr(update_etf_details,'fetch',lambda url:(url,soup))
    row=update_etf_details.parse_twse('00499A')
    assert row.get('benchmark') == '不適用'
    assert '投資策略' not in row.get('benchmark','')


def test_generic_google_news_artwork_is_rejected():
    text=(ROOT/'scripts/update_media_source.py').read_text(encoding='utf-8')
    assert 'google-prefer' in text
    assert 'pic_fb' in text


def test_portfolio_totals_have_fx_guard():
    home=(ROOT/'assets/home.js').read_text(encoding='utf-8')
    portfolio=(ROOT/'assets/portfolio.js').read_text(encoding='utf-8')
    for text in (home,portfolio):
        assert 'TWD=X' in text
        assert 'fxToTwd' in text


def _verification_snapshots():
    keys = update_data_verification.SOURCE_FILES
    return {key: {"updated_at": "2026-08-10T09:00:00+08:00"} for key in keys}


def test_data_verification_isolates_etf_and_stock_optional_channels():
    payloads = {"tw_market": {"metadata": {"trading_date": "2026-08-07"}}}
    snapshots = _verification_snapshots()
    common = dict(
        payloads=payloads,
        quotes={
            "00401A": {"symbol": "00401A", "price": 13.2, "quote_date": "2026-08-07"},
            "2330": {"symbol": "2330", "price": 1800, "quote_date": "2026-08-07"},
        },
        revenue={"2330": [{"period": "2026-07", "revenue": 100, "source": "official", "source_updated_at": "2026-08-10T08:00:00+08:00"}]},
        dividends={},
        secondary={},
        yahoo={},
        etf_details={"00401A": {"benchmark": "不適用", "updated_at": "2026-08-10T08:30:00+08:00"}},
        audit_map={},
        source_snapshots=snapshots,
    )
    etf = {
        "market": "TW", "asset_class": "etf", "exchange": "TWSE", "symbol": "00401A",
        "etf": {"benchmark": "不適用"},
    }
    stock = {
        "market": "TW", "asset_class": "stock", "exchange": "TWSE", "symbol": "2330",
        "monthly_revenue": [{"period": "2026-07", "revenue": 100, "source": "official"}],
    }
    etf_result = update_data_verification.build_asset_verification(etf, **common)
    stock_result = update_data_verification.build_asset_verification(stock, **common)
    assert etf_result and stock_result
    etf_row, _, _ = etf_result
    stock_row, _, _ = stock_result
    assert etf_row["verified_against"]["monthly_revenue"] is None
    assert etf_row["verified_against"]["etf_details"] == "2026-08-10T08:30:00+08:00"
    assert stock_row["verified_against"]["monthly_revenue"] == "2026-08-10T08:00:00+08:00"
    assert stock_row["verified_against"]["etf_details"] is None

import update_assets
import update_dividend_history
import update_tw_chips


def test_two_character_alias_does_not_match_inside_ordinary_phrase():
    text='群創開盤強攻漲停，截至上午9點46分，成交量已達16萬張'
    found=news_pipeline.infer_symbols(text,{'群創':'3481','至上':'8112'})
    assert found == ['3481']


def test_margin_rate_metric_is_earnings_not_central_bank_rate():
    row=news_pipeline.classify('聯茂上半年賺贏去年全年','第二季毛利率與獲利跳增，每股盈餘3.52元',{'聯茂':'6213'},'media')
    assert row['ai_category'] == '企業財報'
    fed=news_pipeline.classify('聯準會宣布升息','政策利率調升一碼',{},None)
    assert fed['ai_category'] == '央行與利率'


def test_twse_parsers_accept_verified_session_fallback_date():
    rows=[{'證券代號':'2330','證券名稱':'台積電','外陸資買賣超股數不含外資自營商':'1000','投信買賣超股數':'-2000','自營商買賣超股數':'500'}]
    items,market,traded=update_tw_chips.parse_institutional(rows,{'2330':{'name':'台積電'}},'https://example.test','2026-08-07')
    assert traded == '2026-08-07'
    assert items['2330']['institutional']['foreign_net'] == 1
    assert market['foreign_net'] == 1


def test_institutional_amount_parsers_keep_official_semantics():
    rows=[
      {'_source_date':'2026-08-07','單位名稱':'自營商(自行買賣)','買進金額':'100','賣出金額':'40','買賣差額':'60'},
      {'_source_date':'2026-08-07','單位名稱':'自營商(避險)','買進金額':'50','賣出金額':'70','買賣差額':'-20'},
      {'_source_date':'2026-08-07','單位名稱':'投信','買進金額':'200','賣出金額':'100','買賣差額':'100'},
      {'_source_date':'2026-08-07','單位名稱':'外資及陸資(不含外資自營商)','買進金額':'500','賣出金額':'800','買賣差額':'-300'},
      {'_source_date':'2026-08-07','單位名稱':'外資自營商','買進金額':'10','賣出金額':'10','買賣差額':'0'},
      {'_source_date':'2026-08-07','單位名稱':'合計','買進金額':'850','賣出金額':'1010','買賣差額':'-160'},
    ]
    values,traded=update_tw_chips.parse_twse_institutional_amounts(rows,'2026-08-07')
    assert traded == '2026-08-07'
    assert values['foreign']['net'] == -300
    assert values['trust']['net'] == 100
    assert values['dealer']['net'] == 40
    assert values['total']['net'] == -160


def test_tpex_issued_shares_derived_only_from_official_capital_and_par_value():
    values=update_assets.official_issued_share_values({'實收資本額':'436,892,550','普通股每股面額':'新台幣10元','特別股':'0'},'TPEx company master')
    assert values['issued_shares'] == 43_689_255
    assert values['issued_shares_status'] == 'calculated_official_fields'
    assert 'paid-in capital / par value' in values['issued_shares_source']
    missing=update_assets.official_issued_share_values({'實收資本額':'1000000','普通股每股面額':'無票面金額'},'TPEx company master')
    assert missing['issued_shares'] is None


def test_verification_normalizes_harmless_etf_text_variants():
    assert update_data_verification.text_status_for('MSCI臺灣指數','MSCI台灣指數','official')[0] == 'multi_source'
    assert update_data_verification.text_status_for('MSCI&#174;臺灣指數','MSCIR臺灣指數','official')[0] == 'multi_source'
    assert update_data_verification.text_status_for('富邦證券投資信託股份有限公司','富邦投信','official')[0] == 'multi_source'
    assert update_data_verification.benchmark_status_for('臺灣證券交易所發行量加權股價報酬指數','臺灣加權股價報酬指數','official')[0] == 'multi_source'


def test_active_etf_no_tracking_index_skips_reference_conflict():
    asset={'market':'TW','asset_class':'etf','symbol':'00403A','name':'主動統一台股增長','etf':{'management_style':'主動式管理','benchmark':'不適用'}}
    field,_=update_data_verification.build_etf_field(asset,'00403A',{'00403A':{'benchmark':'臺灣證券交易所發行量加權股價報酬指數','verification':{'benchmark':{'status':'official'}}}})
    check=field['fields']['benchmark']
    assert check['status'] == 'official'
    assert check['comparison_skipped'] == 'active_etf_no_tracking_index'


def test_reference_dividend_never_overwrites_official_same_period():
    rows=update_dividend_history.merge_dividend_records([], [
      {'period':'2026','cash':2.0,'source':'Yahoo Finance dividend event','source_level':'reference','ex_date':'2026-07-01'},
      {'period':'2026','cash':3.0,'source':'TWSE dividend'},
    ])
    assert rows[0]['cash'] == 3.0
    assert rows[0]['source'] == 'TWSE dividend'
    assert rows[0].get('source_level') != 'reference'


def test_dividend_merge_uses_ex_date_across_different_period_labels():
    rows=update_dividend_history.merge_dividend_records([], [
      {'period':'2026','period_basis':'ex_date_year','cash':2.0,'source':'Yahoo Finance dividend event','source_level':'reference','ex_date':'2026-07-01'},
      {'period':'2025','cash':3.0,'source':'TWSE dividend','ex_date':'2026-07-01'},
    ])
    assert len(rows) == 1
    assert rows[0]['period'] == '2025'
    assert rows[0]['cash'] == 3.0
    assert rows[0].get('period_basis') is None


def test_dividend_merge_preserves_multiple_events_in_same_year():
    rows=update_dividend_history.merge_dividend_records([], [
      {'period':'2026','cash':1.0,'source':'Yahoo Finance dividend event','source_level':'reference','ex_date':'2026-03-01'},
      {'period':'2026','cash':1.5,'source':'Yahoo Finance dividend event','source_level':'reference','ex_date':'2026-09-01'},
    ])
    assert len(rows) == 2
    assert {row['ex_date'] for row in rows} == {'2026-03-01','2026-09-01'}


def test_retained_media_archive_is_reclassified_with_current_rules():
    aliases={'群創':'3481','至上':'8112'}
    profiles={'3481':{'symbol':'3481','name':'群創','asset_class':'stock'},'8112':{'symbol':'8112','name':'至上','asset_class':'stock'}}
    old={'title':'群創開盤強攻漲停','summary':'截至上午9點46分，成交量已達16萬張','symbols':['3481','8112'],'companies':[profiles['3481'],profiles['8112']]}
    row=news_pipeline.refresh_retained_media_item(old,aliases,profiles)
    assert row['symbols'] == ['3481']
    assert [company['symbol'] for company in row['companies']] == ['3481']


def test_company_dates_accept_compact_roc_and_reject_after_listing():
    assert update_stock_basics.normalize_date("0720627") == "1983-06-27"
    assert update_stock_basics.normalize_date("1150809") == "2026-08-09"
    row = update_stock_basics.sanitize_company_dates({
        "listed_date":"2007-12-10",
        "established_date":"2026/08/09",
    })
    assert row["listed_date"] == "2007-12-10"
    assert "established_date" not in row


def test_financial_ratios_with_unknown_period_do_not_create_false_conflict():
    asset = {
        "asset_class":"stock",
        "metrics":{"roe":12.0,"pe":20.0},
        "metric_sources":{"roe":"TWSE balance ci","pe":"TWSE valuation"},
    }
    yahoo = {
        "metrics":{"roe":5.0,"pe":20.1},
        "metrics_meta":{"roe":{"status":"calculated","source":"Yahoo 財報欄位計算","period":"近四季／最新季"},"pe":{"status":"reference","source":"Yahoo Finance"}},
    }
    result = update_data_verification.build_metrics_field(asset, yahoo)
    assert result["fields"]["roe"]["status"] == "official"
    assert result["fields"]["roe"]["comparison_skipped"] == "period_basis_not_proven_equal"
    assert result["fields"]["pe"]["status"] == "multi_source"


def test_asset_page_uses_per_metric_verification_status():
    text=(ROOT/'assets/asset.js').read_text(encoding='utf-8')
    assert 'verification.fields?.metrics?.fields?.[key]?.status' in text


def test_service_worker_non_ok_network_response_can_fall_back_to_cache():
    text=(ROOT/'service-worker.js').read_text(encoding='utf-8')
    assert 'canonicalRequest(request)' in text
    assert 'cache.match(key)' in text
    assert 'ignoreSearch:false' in text


def test_media_health_distinguishes_direct_source_from_history_fallback():
    text=(ROOT/'scripts/update_media_source.py').read_text(encoding='utf-8')
    for token in ('live_source_ok','fallback_ok','health_status="ok" if live_source_ok else "degraded"'):
        assert token in text


def test_dividend_history_has_broad_failure_circuit_breaker():
    text=(ROOT/'scripts/update_dividend_history.py').read_text(encoding='utf-8')
    assert 'mops_circuit_remaining' in text
    assert 'failure_ratio >= .9' in text
    assert 'sample_errors' in text


def test_asset_master_rejects_company_date_after_listing():
    assert update_assets.sane_company_date("2026/08/09", listed_date="2007/12/10", establishment=True) is None
    assert update_assets.sane_company_date("0720627", listed_date="2007/12/10", establishment=True) == "1983/06/27"

def test_dividend_current_row_keeps_tpex_legacy_meeting_and_board_dates():
    parsed=update_dividend_history.current_row({
        '公司代號':'1234','股利年度':'115','期別':'年度',
        '股東配發-盈餘分配之現金股利(元/股)':'2.5',
        '董事會決議通過股利分派日':'1150311',
        '股東會日期配盈餘/待彌補虧損(元)':'1150617',
    },'TPEx dividend')
    assert parsed
    _,row=parsed
    assert row['board_date']=='2026/03/11'
    assert row['shareholder_meeting_date']=='2026/06/17'


def test_company_dates_preserve_pre_2000_gregorian_and_validate_calendar():
    assert update_stock_basics.normalize_date("1950-12-29") == "1950-12-29"
    assert update_stock_basics.normalize_date("1962/2/9") == "1962-02-09"
    assert update_stock_basics.normalize_date("19830627") == "1983-06-27"
    assert update_stock_basics.normalize_date("1983年06月27日") == "1983-06-27"
    assert update_stock_basics.normalize_date("0720627") == "1983-06-27"
    assert update_stock_basics.normalize_date("19830231") is None


def test_company_date_sanity_preserves_old_listing_but_drops_impossible_establishment():
    row = update_stock_basics.sanitize_company_dates({
        "listed_date": "1962-02-09",
        "established_date": "2026-08-09",
    })
    assert row["listed_date"] == "1962-02-09"
    assert "established_date" not in row


def test_market_snapshot_rejects_quote_timestamp_from_different_session():
    import update_market_snapshot
    row = {
        "symbol": "^TWII", "price": 24000, "previous_close": 23900,
        "change": 100, "change_percent": 100 / 23900 * 100,
        "session_date": "2026-08-11", "price_date": "2026-08-11", "ohlc_date": "2026-08-11",
        "market_at_local": "2026-08-12T13:33:00+08:00",
        "open": 23950, "high": 24100, "low": 23900, "close": 24000, "candles": [],
    }
    import pytest
    with pytest.raises(ValueError, match="timestamp/session mismatch"):
        update_market_snapshot.validate_market_row(row)


def test_media_dict_image_cannot_bypass_generic_image_filter():
    text = (ROOT / "scripts/update_media_source.py").read_text(encoding="utf-8")
    assert 'if isinstance(value,dict):return image_value(' in text
    assert 'if isinstance(value,dict):return value.get("url")' not in text


def test_frontend_company_date_parser_matches_backend_for_old_dates():
    import json
    import subprocess
    shared = (ROOT / "assets/shared.js").read_text(encoding="utf-8")
    lines = [line for line in shared.splitlines() if line.startswith("const basicDate=") or line.startswith("const saneBasicDates=")]
    script = "\n".join(lines) + "\nconsole.log(JSON.stringify([basicDate('1950-12-29'),basicDate('19830627'),basicDate('0720627'),basicDate('19830231'),saneBasicDates('2026-08-09','1962-02-09').listed_date,saneBasicDates('2026-08-09','1962-02-09').established_date]));"
    result = subprocess.run(["node", "-e", script], check=True, text=True, capture_output=True)
    values = json.loads(result.stdout)
    assert values == ["1950-12-29", "1983-06-27", "1983-06-27", "", "1962-02-09", ""]


def test_frontend_generic_news_filter_is_in_parity_with_backend_denylist():
    shared = (ROOT / "assets/shared.js").read_text(encoding="utf-8")
    for token in ("google-prefer", "pic_fb", "line-ad"):
        assert token in shared


def test_common_catastrophic_collection_shrink_guard():
    import common
    previous={"items":{str(i):{} for i in range(1000)}}
    current={"items":{str(i):{} for i in range(100)}}
    try:
        common.guard_against_catastrophic_shrink("stock-basics.json",previous,current)
    except RuntimeError as exc:
        assert "Catastrophic dataset shrink blocked" in str(exc)
    else:
        raise AssertionError("catastrophic shrink must be blocked")
    # Ordinary churn remains allowed.
    common.guard_against_catastrophic_shrink("stock-basics.json",previous,{"items":{str(i):{} for i in range(800)}})
