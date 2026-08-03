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
    def __init__(self,payload): self.payload=payload
    def raise_for_status(self): return None
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
    assert payload['history'][payload['metadata']['trading_date']]


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
        test_events(tmp)
    elapsed=time.monotonic()-started
    assert elapsed<15,elapsed
    print(json.dumps({'status':'PASS','seconds':round(elapsed,3),'checks':['Taiwan chips official-shape parser','event archive merge']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
