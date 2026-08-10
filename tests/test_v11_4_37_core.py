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
