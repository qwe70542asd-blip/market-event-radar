#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, mimetypes, re, sys, time
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
NOW='2026-08-03T11:40:00+08:00'

def assets():
    rows=[]
    for i,sym in enumerate(['00403A','0050','006208','00631L','009816','00981A','2330','2382','3231','2317','2454','2603']):
        rows.append({'id':f'TW:{sym}','symbol':sym,'name':{'2330':'台積電','2382':'廣達','3231':'緯創','2317':'鴻海','2454':'聯發科','2603':'長榮','00403A':'主動統一升級50','0050':'元大台灣50','006208':'富邦台50','00631L':'元大台灣50正2','009816':'凱基台灣TOP50','00981A':'主動統一台股增長'}[sym], 'market':'TW','exchange':'TWSE','asset_class':'etf' if sym.startswith('00') else 'stock','currency':'TWD'})
    return {'metadata':{'updated_at':NOW},'assets':rows}

def tw_market():
    rows=[]
    for i in range(60):
        sym=str(1000+i)
        pct=(i%20-10)/2
        rows.append({'symbol':sym,'name':f'測試股票{i}','exchange':'TWSE' if i%2==0 else 'TPEx','asset_class':'stock','price':50+i,'previous_close':50+i-pct/100*(50+i),'change_percent':pct,'change':pct/100*(50+i),'volume':1000+i*100})
    # ensure portfolio names too
    rows.extend([
      {'symbol':'2330','name':'台積電','exchange':'TWSE','asset_class':'stock','price':1000,'previous_close':990,'change_percent':1.01,'change':10,'volume':100000},
      {'symbol':'00631L','name':'元大台灣50正2','exchange':'TWSE','asset_class':'etf','price':35,'previous_close':34.5,'change_percent':1.45,'change':.5,'volume':50000},
    ])
    return {'metadata':{'updated_at':NOW,'trading_date':'20260803'},'items':rows}

def events():
    return {'metadata':{'updated_at':NOW,'timezone':'Asia/Taipei'},'events':[{'id':f'e{i}','title':f'市場事件 {i}','start':f'2026-08-{3+i:02d}T09:00:00+08:00','region':'TW','event_group':'earnings','impact':'high' if i%2==0 else 'medium','description':'測試事件'} for i in range(10)]}

def market():
    symbols=[('^TWII','台灣加權指數',43120,'TWD'),('^TWOII','台灣櫃買指數',310,'TWD'),('^GSPC','S&P 500',7490,'USD'),('^IXIC','NASDAQ',25374,'USD'),('^SOX','費城半導體',11311,'USD'),('AAPL','Apple',308.9,'USD')]
    return {'metadata':{'updated_at':NOW},'items':[{'symbol':s,'name':n,'price':p,'previous_close':p*.99,'change_percent':1.01,'currency':c} for s,n,p,c in symbols]}

def chips():
    items={}
    for i,s in enumerate(['2330','2317','2382','3231','2454']):
        items[s]={'symbol':s,'name':f'股票{s}','market':'twse','foreign_net':1000000-i*100000,'trust_net':200000+i*10000,'dealer_net':-50000,'total_net':1150000-i*90000}
    section={'institutional':{'foreign_net':5000000,'trust_net':1000000,'dealer_net':-250000,'total_net':5750000},'day_trading':{'ratio_percent':22.5,'trade_value':50000000000},'margin':{'balance_shares':3000000000},'short':{'balance_shares':120000000}}
    return {'metadata':{'updated_at':NOW,'trading_date':'20260801'},'markets':{'twse':section,'tpex':section},'items':items}

def news():
    return {'metadata':{'updated_at':NOW,'retention_days':20},'items':[{'id':f'n{i}','title':f'財經新聞 {i}','source':['鉅亨網','MoneyDJ','Yahoo股市'][i%3],'published_at':NOW,'link':'https://example.org/news'} for i in range(12)]}

PAYLOADS={'assets.json':assets(),'tw-market.json':tw_market(),'events.json':events(),'market-snapshot.json':market(),'tw-chips.json':chips(),'news.json':news(),'asset-coverage.json':{'summary':{'total_stocks':1200},'metadata':{'updated_at':NOW}}}

PRELUDE='''<script>
const __ls={"market-radar-portfolio-v11-1":JSON.stringify([{id:"p1",asset_id:"TW:2330",symbol:"2330",name:"台積電",market:"TW",exchange:"TWSE",asset_class:"stock",shares:10,avg_cost:900,currency:"TWD"}])};
Object.defineProperty(window,"localStorage",{value:{getItem:k=>Object.prototype.hasOwnProperty.call(__ls,k)?__ls[k]:null,setItem:(k,v)=>__ls[k]=String(v),removeItem:k=>delete __ls[k],clear:()=>Object.keys(__ls).forEach(k=>delete __ls[k]),key:i=>Object.keys(__ls)[i]||null,get length(){return Object.keys(__ls).length}}});
class MockWebSocket {constructor(url){this.url=url;this.readyState=0;this.handlers={};setTimeout(()=>{this.readyState=1;this.emit("open",{});["BTC","ETH","BNB","SOL","XRP"].forEach((s,i)=>this.emit("message",{data:JSON.stringify({data:{s:s+"USDT",c:String(60000/(i+1)),o:String(59000/(i+1)),h:String(61000/(i+1)),l:String(58000/(i+1)),v:"1000",q:"50000000",E:Date.now()}})}))},20)}addEventListener(k,f){(this.handlers[k]??=[]).push(f)}emit(k,e){(this.handlers[k]||[]).forEach(f=>f(e))}close(){this.readyState=3;this.emit("close",{})}};
MockWebSocket.OPEN=1;window.WebSocket=MockWebSocket;
</script>'''

def inline_html(name):
    html=(ROOT/name).read_text(encoding='utf-8').replace('<head>',f'<head><base href="https://example.com/">{PRELUDE}')
    for tag,href in re.findall(r'(<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"[^>]*>)',html):
        file=ROOT/href.split('?')[0]
        html=html.replace(tag,f'<style>{file.read_text(encoding="utf-8")}</style>',1)
    for src in re.findall(r'<script[^>]+src="([^"]+)"[^>]*></script>',html):
        file=ROOT/src.split('?')[0]
        html=html.replace(f'<script src="{src}"></script>',f'<script>{file.read_text(encoding="utf-8")}</script>',1)
    return html

def run_page(page,name,assertions):
    errors=[]
    page.on('pageerror',lambda exc:errors.append(str(exc)))
    def route_handler(route):
        url=route.request.url
        clean=url.split('?',1)[0]
        filename=clean.rsplit('/',1)[-1]
        if filename in PAYLOADS:
            route.fulfill(status=200,content_type='application/json',body=json.dumps(PAYLOADS[filename],ensure_ascii=False))
        elif clean.startswith('https://example.com/data/'):
            file=ROOT/'data'/filename
            route.fulfill(status=200,content_type='application/json',body=file.read_bytes() if file.exists() else b'{}')
        elif 'mis.twse.com.tw' in clean:
            route.fulfill(status=200,content_type='application/json',body=json.dumps({'msgArray':[]}))
        elif 'query1.finance.yahoo.com' in clean or 'query2.finance.yahoo.com' in clean:
            route.fulfill(status=503,body='')
        elif 'api.coingecko.com' in clean:
            route.fulfill(status=503,body='')
        else:
            route.abort()
    page.route('**/*',route_handler)
    started=time.monotonic()
    page.set_content(inline_html(name),wait_until='domcontentloaded')
    for selector,minimum in assertions:
        page.wait_for_function('(args)=>document.querySelectorAll(args[0]).length>=args[1]',arg=[selector,minimum],timeout=12000)
    elapsed=time.monotonic()-started
    if errors: raise AssertionError(f'{name} page errors: {errors}')
    if elapsed>15: raise AssertionError(f'{name} exceeded 15 seconds: {elapsed:.2f}')
    return elapsed

def main():
    results={}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-web-security'])
        tests={
          'index.html':[('#calendarGrid .calendar-day',35),('#marketList .market-row',4),('#cryptoList .crypto-row',5),('#portfolioStrip .quote-card',1),('#homeNews .news-card',3)],
          'tw-market.html':[('#gainers tr',3),('#losers tr',3),('#twHoldings tr',1)],
          'institutional.html':[('#institutionalGrid .info-card',4),('#marginGrid .info-card',4),('#flowRows tr',3)],
          'news.html':[('#newsList .news-card',3)],
          'data-status.html':[('#channelGrid .channel-card',7)],
        }
        for name,assertions in tests.items():
            page=browser.new_page()
            results[name]=round(run_page(page,name,assertions),3)
            page.close()
        browser.close()
    print(json.dumps({'status':'PASS','seconds':results,'total_seconds':round(sum(results.values()),3)},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
