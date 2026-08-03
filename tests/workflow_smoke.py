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
            return Response({'stat':'OK','fields':['證券代號','證券名稱','外陸資買賣超股數(不含外資自營商)','投信買賣超股數','自營商買賣超股數','三大法人買賣超股數'],'data':[['2330','台積電','1000000','200000','-50000','1150000'],['2317','鴻海','-100000','50000','10000','-40000']]})
        return Response({'stat':'OK','fields':['項目','買進','賣出','餘額'],'data':[['融資(交易單位)','1','2','3000000'],['融券(交易單位)','1','2','120000']]})

def test_chips(tmp):
    module=load_module('chips_smoke',ROOT/'scripts/update_tw_chips.py')
    module.OUT=tmp/'tw-chips.json';module.SEED=tmp/'tw-chips-seed.js'
    module.requests.Session=lambda:ChipSession()
    module.main()
    payload=json.loads(module.OUT.read_text(encoding='utf-8'))
    assert payload['metadata']['status']=='ok'
    assert len(payload['items'])==2
    assert payload['markets']['twse']['margin']['balance_shares']==3000000

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
