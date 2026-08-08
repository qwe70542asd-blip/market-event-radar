from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts'
if str(SCRIPTS) not in sys.path: sys.path.insert(0,str(SCRIPTS))

import news_pipeline
import update_company_disclosures


class NewsIntegrityTests(unittest.TestCase):
    def test_roc_disclosure_time_is_not_now_fallback(self):
        value=update_company_disclosures.publication_datetime('1150806','70004')
        self.assertEqual(value,'2026-08-06T07:00:04+08:00')

    def test_invalid_disclosure_time_fails_closed(self):
        self.assertIsNone(update_company_disclosures.publication_datetime('bad','70004'))

    def test_legacy_now_fallback_is_removed_on_version_migration(self):
        metadata={'version':'v11.4.30','updated_at':'2026-08-08T09:03:26+08:00'}
        poisoned={'published_at':'2026-08-08T09:03:26+08:00'}
        real={'published_at':'2026-08-07T00:00:00+08:00'}
        self.assertTrue(news_pipeline.legacy_now_fallback(poisoned,metadata))
        self.assertFalse(news_pipeline.legacy_now_fallback(real,metadata))

    def test_undated_news_is_rejected(self):
        item=news_pipeline.normalize_item(
            title='中央銀行公布重要市場資訊',
            url='https://example.com/news/1',
            source_id='test',source_name='測試',summary='這是一則足夠長度且可閱讀的繁體中文市場資訊摘要。',
            published_at=None,aliases={},forced_scope='market'
        )
        self.assertIsNone(item)

    def test_numeric_market_counts_do_not_become_stock_codes(self):
        aliases={'台積電':'2330','群創':'3481','測試公司甲':'1250','測試公司乙':'1270'}
        text='群創飆高，台積電領1270家同樂，終場指數上漲1250點。'
        found=news_pipeline.infer_symbols(text,aliases)
        self.assertIn('3481',found)
        self.assertIn('2330',found)
        self.assertNotIn('1250',found)
        self.assertNotIn('1270',found)


    def test_headline_starting_with_market_points_is_not_a_stock_code(self):
        aliases={'測試公司甲':'1250'}
        found=news_pipeline.infer_symbols('1250點大漲，台股全面反攻',aliases)
        self.assertNotIn('1250',found)

    def test_full_stock_master_keeps_etf_authority(self):
        stock_items={str(1000+i):{'symbol':str(1000+i),'market':'TW','asset_class':'stock'} for i in range(500)}
        assets=[{'symbol':'00981A','market':'TW','asset_class':'etf','name':'主動統一台股增長'}]
        def fake_read(path,default):
            return {'items':stock_items} if path.name=='stock-basics.json' else {'assets':assets}
        with patch.object(news_pipeline,'read_json',side_effect=fake_read):
            rows=news_pipeline._stock_master_rows()
        symbols={row.get('symbol') for row in rows}
        self.assertIn('00981A',symbols)
        self.assertEqual(len(rows),501)

    def test_company_extra_symbol_rebuilds_company_profile(self):
        item=news_pipeline.normalize_item(
            title='4953 緯致 公告重要事項',
            url='https://example.com/news/4953',
            source_id='company-disclosures',
            source_name='官方',
            summary='公司公告正式資訊內容，並提供足夠長度的繁體中文摘要。',
            published_at='2026-08-08T07:00:04+08:00',
            aliases={},
            profiles={'4953':{'symbol':'4953','name':'緯致','industry':'資訊服務業','asset_class':'stock'}},
            forced_scope='company',
            extra={'symbols':['4953']},
        )
        self.assertEqual(item['affected_markets'],['4953'])
        self.assertEqual(item['companies'][0]['name'],'緯致')

    def test_explicit_numeric_stock_code_is_allowed(self):
        aliases={'群創':'3481'}
        self.assertIn('3481',news_pipeline.infer_symbols('股票代號 3481 群創今日公告',aliases))


if __name__=='__main__': unittest.main()
