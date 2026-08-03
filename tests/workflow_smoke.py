#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, tempfile, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Response:
    def __init__(self,payload=None,content=None,text=None,status_code=200):
        self.payload=payload
        self.content=content if content is not None else (json.dumps(payload,ensure_ascii=False).encode("utf-8") if payload is not None else b"")
        self.text=text if text is not None else self.content.decode("utf-8","ignore")
        self.status_code=status_code
    def raise_for_status(self):
        if self.status_code>=400: raise RuntimeError(f"HTTP {self.status_code}")
    def json(self): return self.payload

class ChipSession:
    def get(self,url,**kwargs):
        if 'T86' in url:
            return Response({
                'stat':'OK',
                'fields':['證券代號','證券名稱','外陸資買進股數(不含外資自營商)','外陸資賣出股數(不含外資自營商)','外陸資買賣超股數(不含外資自營商)','投信買進股數','投信賣出股數','投信買賣超股數','自營商買賣超股數','三大法人買賣超股數'],
                'data':[
                    ['2330','台積電','1200000','200000','1000000','300000','100000','200000','-50000','1150000'],
                    ['2317','鴻海','100000','200000','-100000','80000','30000','50000','10000','-40000']
                ]
            })
        if 'MI_MARGN' in url:
            return Response({
                'stat':'OK',
                'tables':[{
                    'fields':['股票代號','股票名稱','融資買進','融資賣出','融資現金償還','融資前日餘額','融資今日餘額','融資限額','融券賣出','融券買進','融券現券償還','融券前日餘額','融券今日餘額','融券限額','資券互抵'],
                    'data':[
                        ['2330','台積電','100','80','2','1000','1018','5000','20','10','0','100','110','5000','5'],
                        ['2317','鴻海','90','70','1','800','819','4000','15','12','1','80','82','4000','3']
                    ]
                }]
            })
        if 'TWTB4U' in url:
            return Response([{
                '證券代號':'2330','證券名稱':'台積電','現股當沖交易標的註記':'是',
                '當日沖銷交易成交股數':'500000','當日沖銷交易買進成交金額':'250000000',
                '當日沖銷交易賣出成交金額':'252000000'
            }])
        if 'tpex_intraday_trading_statistics' in url:
            return Response([{
                'SecuritiesCompanyCode':'6488','CompanyName':'環球晶','DayTradingEligible':'Y',
                'DayTradingVolume':'120000','DayTradingBuyAmount':'30000000','DayTradingSellAmount':'30100000'
            }])
        if 'tpex_3insti' in url:
            return Response([{
                'Date':'115/08/03','SecuritiesCompanyCode':'6488','CompanyName':'環球晶',
                'ForeignInvestorsBuy':'500000','ForeignInvestorsSell':'300000','ForeignInvestorsDifference':'200000',
                'InvestmentTrustBuy':'50000','InvestmentTrustSell':'10000','InvestmentTrustDifference':'40000',
                'DealerBuy':'20000','DealerSell':'15000','DealerDifference':'5000','TotalDifference':'245000'
            }])
        if 'tpex_mainboard_margin_balance' in url:
            return Response([{
                'Date':'115/08/03','SecuritiesCompanyCode':'6488','CompanyName':'環球晶',
                'PreviousMarginBalance':'600','MarginBuy':'40','MarginSell':'20','CashRepayment':'0','TodayMarginBalance':'620',
                'MarginLimit':'3000','MarginUtilization':'20.67',
                'PreviousShortBalance':'20','ShortSell':'5','ShortBuy':'2','ShortRepayment':'0','TodayShortBalance':'23',
                'ShortLimit':'3000','ShortUtilization':'0.77','OffsetShares':'1'
            }])
        return Response([])

def test_chips(tmp):
    module=load_module('chips_smoke',ROOT/'scripts/update_tw_chips.py')
    module.OUT=tmp/'tw-chips.json';module.SEED=tmp/'tw-chips-seed.js'
    module.requests.Session=lambda:ChipSession()
    module.main()
    payload=json.loads(module.OUT.read_text(encoding='utf-8'))
    assert payload['metadata']['status']=='ok'
    assert len(payload['items'])==3
    assert payload['items']['twse:2330']['margin']['balance']==1018
    assert payload['items']['tpex:6488']['short']['balance']==23
    assert payload['markets']['twse']['margin']['balance']==1837
    assert payload['items']['twse:2330']['day_trading']['volume']==500000
    assert payload['items']['tpex:6488']['day_trading']['volume']==120000
    assert payload['history'][payload['metadata']['trading_date']]



class NewsSession:
    def __init__(self):
        self.headers={}
    def get(self,url,**kwargs):
        if "newsList" in url:
            return Response([{
                "id":"1","title":"證交所重大市場公告","summary":"市場制度調整",
                "date":"2026-08-03T10:00:00+08:00"
            }])
        if "t187ap04_L" in url:
            return Response([{
                "公司代號":"2330","公司簡稱":"台積電","主旨":"公告第二季財務報告",
                "說明":"董事會通過第二季財報","發言日期":"1150803","發言時間":"101500"
            }])
        if "t187ap04_O" in url:
            return Response([{
                "公司代號":"6488","公司簡稱":"環球晶","主旨":"重大訊息說明",
                "說明":"公司營運說明","發言日期":"1150803","發言時間":"102000"
            }])
        if "moneydj" in url.lower() or "listnewarticles" in url:
            html_body = '<html><body><a href="/KMDJ/News/NewsViewer.aspx?a=1">台股重要產業新聞測試</a></body></html>'
            return Response(content=html_body.encode("utf-8"))
        rss = """<?xml version="1.0" encoding="UTF-8"?>
        <rss version="2.0"><channel><title>fixture</title>
        <item><title>台灣財經重大消息測試</title>
        <link>https://example.org/news/1</link>
        <description>財報、股利與市場政策</description>
        <pubDate>Mon, 03 Aug 2026 08:00:00 +0800</pubDate>
        <source>測試媒體</source></item>
        </channel></rss>"""
        return Response(content=rss.encode("utf-8"))

def test_news(tmp):
    module=load_module("news_smoke",ROOT/"scripts/update_news.py")
    module.OUT=tmp/"news.json"
    module.SEED=tmp/"news-seed.js"
    module.REGISTRY=tmp/"news-sources.json"
    module.requests.Session=lambda:NewsSession()
    registry={"sources":[
        {"name":"Yahoo測試","group":"portal","method":"rss","url":"https://example.org/rss","homepage":"https://example.org","priority":5},
        {"name":"MoneyDJ","group":"publisher","method":"moneydj","homepage":"https://www.moneydj.com","priority":5},
        {"name":"臺灣證券交易所新聞","group":"official","method":"twse_news","homepage":"https://www.twse.com.tw","priority":5},
        {"name":"上市公司重大訊息","group":"official-company","method":"mops_listed","homepage":"https://mops.twse.com.tw","priority":5},
        {"name":"上櫃公司重大訊息","group":"official-company","method":"mops_otc","homepage":"https://mops.twse.com.tw","priority":5},
        {"name":"經濟日報","group":"publisher","method":"google","query":"site:money.udn.com 台股 when:7d","homepage":"https://money.udn.com","priority":5},
        {"name":"中央銀行","group":"official","method":"google","query":"site:cbc.gov.tw 利率 when:7d","homepage":"https://www.cbc.gov.tw","priority":5},
        {"name":"廣域測試","group":"broad","method":"google","query":"台股 重大訊息 when:3d","homepage":"https://news.google.com","priority":5,"dynamic_source":True}
    ]}
    module.REGISTRY.write_text(json.dumps(registry,ensure_ascii=False),encoding="utf-8")
    module.OUT.write_text(json.dumps({"items":[],"sources":[]}),encoding="utf-8")
    module.main()
    payload=json.loads(module.OUT.read_text(encoding="utf-8"))
    assert payload["metadata"]["version"]=="v11.2.7"
    assert payload["metadata"]["configured_source_count"]==8
    assert payload["metadata"]["checked_source_count"]==8
    assert payload["metadata"]["material_item_count"]>=2
    assert len(payload["sources"])>=8
    assert len(payload["items"])>=5
    assert all(row.get("link","").startswith("http") for row in payload["items"])
    assert "window.__NEWS_SEED__" in module.SEED.read_text(encoding="utf-8")

def test_events(tmp):
    module=load_module('events_smoke',ROOT/'scripts/update_events.py')
    module.OUT=tmp/'events.json';module.SEED=tmp/'events-seed.js';module.MANUAL=tmp/'manual-events.json'
    start=(module.NOW.replace(hour=9,minute=0,second=0,microsecond=0)).isoformat(timespec='seconds')
    module.OUT.write_text(json.dumps({'sources':[{'name':'fixture'}],'events':[{'id':'fixture','title':'已驗證事件','start':start,'region':'TW'}]},ensure_ascii=False),encoding='utf-8')
    module.MANUAL.write_text('[]',encoding='utf-8')
    module.main()
    payload=json.loads(module.OUT.read_text(encoding='utf-8'))
    assert len(payload['events'])==1
    assert payload['metadata']['updated_at']

def main():
    started=time.monotonic()
    with tempfile.TemporaryDirectory() as directory:
        tmp=Path(directory)
        test_chips(tmp)
        test_news(tmp)
        test_events(tmp)
    elapsed=time.monotonic()-started
    assert elapsed<15,elapsed
    print(json.dumps({'status':'PASS','seconds':round(elapsed,3),'checks':['Taiwan chips official-shape parser','Taiwan news multi-source pipeline','event archive merge']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
