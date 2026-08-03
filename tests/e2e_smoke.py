#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, mimetypes, re, sys, time
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
NOW='2026-08-03T11:40:00+08:00'

def assets():
    rows=[]
    for i,sym in enumerate(['00403A','0050','0056','006208','00631L','009816','00981A','2330','2382','3231','2317','2454','2603','6488']):
        row={'id':f'TW:{sym}','symbol':sym,'name':{'2330':'台積電','2382':'廣達','3231':'緯創','2317':'鴻海','2454':'聯發科','2603':'長榮','00403A':'主動統一升級50','0050':'元大台灣50','0056':'元大高股息','006208':'富邦台50','00631L':'元大台灣50正2','009816':'凱基台灣TOP50','00981A':'主動統一台股增長','6488':'環球晶'}[sym], 'market':'TW','exchange':'TPEx' if sym=='6488' else 'TWSE','asset_class':'etf' if sym.startswith('00') else 'stock','currency':'TWD'}
        if sym=='2330':
            row.update({'official_industry':'半導體業','sub_industry':'晶圓代工',
              'metrics':{'eps':42.3,'pe':23.6,'pb':7.1,'dividend_yield':1.7,'roe':31.2,'debt_ratio':22.5,'current_ratio':2.1,'net_margin':39.4},
              'profile':{'full_name':'台灣積體電路製造股份有限公司','issued_shares':25930380458,'paid_in_capital':259303804580,'listing_date':'1994/09/05'},
              'financials':[{'year':2026,'quarter':2,'revenue':900000000000,'operating_income':450000000000,'net_income':350000000000,'eps':13.5,'total_assets':7000000000000,'total_liabilities':1600000000000,'equity':5400000000000}],
              'dividend':{'cash_dividend':6,'stock_dividend':0,'ex_dividend_date':'2026/09/01','announcement_date':'2026/07/15'},
              'analysis_coverage':{'count':8,'missing':[]}})
        if sym=='0056':
            row.update({'etf':{'issuer':'元大投信','manager':'測試經理人','category':'高股息ETF','benchmark':'臺灣高股息指數','strategy':'追蹤高股息指數','inception_date':'2007/12/13','listing_date':'2007/12/26','custodian':'中國信託','distribution':'季配','expense_ratio':'依公開說明書'},'analysis_coverage':{'count':8,'missing':[]}})
        if sym=='6488':
            row.update({'official_industry':'半導體業','sub_industry':'矽晶圓','metrics':{'eps':25.1,'pe':18.2,'pb':3.2,'dividend_yield':2.1},'profile':{'full_name':'環球晶圓股份有限公司','issued_shares':437250000,'paid_in_capital':4372500000,'listing_date':'2011/09/23'}})
        rows.append(row)
    return {'metadata':{'updated_at':NOW},'assets':rows}

def tw_market():
    rows=[]
    for i in range(60):
        sym=str(1000+i)
        pct=(i%20-10)/2
        rows.append({'symbol':sym,'name':f'測試股票{i}','exchange':'TWSE' if i%2==0 else 'TPEx','asset_class':'stock','price':50+i,'previous_close':50+i-pct/100*(50+i),'change_percent':pct,'change':pct/100*(50+i),'volume':1000+i*100})
    # ensure portfolio names too
    rows.extend([
      {'symbol':'2330','name':'台積電','exchange':'TWSE','asset_class':'stock','price':1000,'previous_close':990,'change_percent':1.01,'change':10,'open':995,'high':1010,'low':992,'upper_limit':1085,'lower_limit':895,'volume':100000,
       'bid_prices':[1000,999,998,997,996],'bid_volumes':[15,25,35,45,55],
       'ask_prices':[1001,1002,1003,1004,1005],'ask_volumes':[10,20,30,40,50]},
      {'symbol':'0056','name':'元大高股息','exchange':'TWSE','asset_class':'etf','price':49.89,'previous_close':49.48,'change_percent':.83,'change':.41,'open':49.5,'high':50.1,'low':48.85,'volume':33000},
      {'symbol':'00631L','name':'元大台灣50正2','exchange':'TWSE','asset_class':'etf','price':35,'previous_close':34.5,'change_percent':1.45,'change':.5,'volume':50000},
      {'symbol':'6488','name':'環球晶','exchange':'TPEx','asset_class':'stock','price':390,'previous_close':386,'change_percent':1.04,'change':4,'open':387,'high':394,'low':385,'volume':12000},
      {'symbol':'BAD0','name':'錯誤零價資料','exchange':'TWSE','asset_class':'stock','price':0,'previous_close':100,'change_percent':-100,'change':-100,'volume':999999},
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
        items[f'twse:{s}']={
            'symbol':s,'name':f'股票{s}','market':'twse',
            'foreign_buy':1200000-i*100000,'foreign_sell':200000,'foreign_net':1000000-i*100000,
            'trust_buy':250000,'trust_sell':50000,'trust_net':200000,
            'dealer_buy':20000,'dealer_sell':70000,'dealer_net':-50000,
            'total_net':1150000-i*100000,
            'margin':{'previous_balance':1000+i*10,'buy':100,'sell':80,'cash_repayment':2,'balance':1018+i*10,'limit':5000,'utilization_percent':20.36},
            'short':{'previous_balance':100,'sell':20,'buy':10,'repayment':0,'balance':110,'limit':5000,'utilization_percent':2.2},
            'day_trading':{'eligible':True,'volume':500000,'buy_amount':250000000,'sell_amount':252000000,'volume_ratio_percent':12.5,'amount_ratio_percent':13.2},
            'offset_shares':5,'note':''
        }
    tpex={
        'symbol':'6488','name':'環球晶','market':'tpex',
        'foreign_buy':500000,'foreign_sell':300000,'foreign_net':200000,
        'trust_buy':50000,'trust_sell':10000,'trust_net':40000,
        'dealer_buy':20000,'dealer_sell':15000,'dealer_net':5000,'total_net':245000,
        'margin':{'previous_balance':600,'buy':40,'sell':20,'cash_repayment':0,'balance':620,'limit':3000,'utilization_percent':20.67},
        'short':{'previous_balance':20,'sell':5,'buy':2,'repayment':0,'balance':23,'limit':3000,'utilization_percent':0.77},
        'day_trading':{'eligible':True,'volume':120000,'buy_amount':30000000,'sell_amount':30100000,'volume_ratio_percent':8.1,'amount_ratio_percent':8.4},
        'offset_shares':1,'note':''
    }
    items['tpex:6488']=tpex
    markets={
      'twse':{'institutional':{'foreign_net':4000000,'trust_net':1000000,'dealer_net':-250000,'total_net':4750000},
              'margin':{'previous_balance':5100,'balance':5190,'change':90},
              'short':{'previous_balance':500,'balance':550,'change':50},
              'day_trading':{'volume':500000,'buy_amount':250000000,'sell_amount':252000000,'stock_count':1},'stock_count':5},
      'tpex':{'institutional':{'foreign_net':200000,'trust_net':40000,'dealer_net':5000,'total_net':245000},
              'margin':{'previous_balance':600,'balance':620,'change':20},
              'short':{'previous_balance':20,'balance':23,'change':3},
              'day_trading':{'volume':120000,'buy_amount':30000000,'sell_amount':30100000,'stock_count':1},'stock_count':1}
    }
    snapshot={'date':'20260801','markets':markets,'items':items}
    return {'metadata':{'updated_at':NOW,'trading_date':'20260801','status':'ok'},
            'available_dates':['20260801'],'markets':markets,'items':items,'history':{'20260801':snapshot}}


def asset_audit():
    rows=[]
    checks=[
      {'field':'master.full_name','label':'公司／基金全名','required':True,'available':True,'reason':None,'value':'台灣積體電路製造股份有限公司'},
      {'field':'master.listing_date','label':'上市／上櫃日期','required':True,'available':True,'reason':None,'value':'1994/09/05'},
      {'field':'metrics.eps','label':'EPS','required':True,'available':True,'reason':None,'value':42.3},
      {'field':'metrics.pe','label':'本益比','required':True,'available':True,'reason':None,'value':23.6},
      {'field':'metrics.pb','label':'股價淨值比','required':True,'available':True,'reason':None,'value':7.1},
      {'field':'metrics.roe','label':'ROE','required':True,'available':True,'reason':None,'value':31.2},
      {'field':'metrics.debt_ratio','label':'負債比','required':True,'available':True,'reason':None,'value':22.5},
      {'field':'financials.latest','label':'最近財報','required':True,'available':True,'reason':None,'value':{'year':2026,'quarter':2}},
      {'field':'financials.history','label':'歷季財報','required':True,'available':False,'reason':'quarter_history_incomplete','value':None},
      {'field':'market.quote','label':'最近行情','required':False,'available':True,'reason':None,'value':{'price':1000}},
    ]
    rows.append({'id':'TW:2330','symbol':'2330','name':'台積電','exchange':'TWSE','asset_class':'stock','industry':'半導體業','status':'partial','required_count':9,'available_required_count':8,'coverage_percent':88.89,'missing_required':[{'field':'financials.history','label':'歷季財報','reason':'quarter_history_incomplete'}],'missing_optional':[],'checks':checks})
    rows.append({'id':'TW:0056','symbol':'0056','name':'元大高股息','exchange':'TWSE','asset_class':'etf','industry':'ETF','status':'complete','required_count':8,'available_required_count':8,'coverage_percent':100,'missing_required':[],'missing_optional':[],'checks':[
      {'field':'etf.issuer','label':'ETF 發行公司','required':True,'available':True,'reason':None,'value':'元大投信'},
      {'field':'etf.manager','label':'ETF 基金經理人','required':True,'available':True,'reason':None,'value':'測試經理人'}
    ]})
    field_stats={
      'metrics.eps':{'label':'EPS','applicable':1,'available':1,'missing':0,'not_applicable':1,'coverage_percent':100},
      'financials.history':{'label':'歷季財報','applicable':1,'available':0,'missing':1,'not_applicable':1,'coverage_percent':0},
      'etf.manager':{'label':'ETF 基金經理人','applicable':1,'available':1,'missing':0,'not_applicable':1,'coverage_percent':100}
    }
    return {'metadata':{'version':'v11.2.8','updated_at':NOW,'asset_update_status':'ok','asset_update_message':'fixture'},'summary':{'audited_assets':2,'stock_count':1,'etf_count':1,'complete':1,'partial':1,'unresolved':0,'audit_coverage_percent':100,'field_stats':field_stats,'reason_counts':{'quarter_history_incomplete':1}},'assets':rows,'unresolved_assets':[rows[0]]}

def news():
    items=[{'id':f'n{i}','title':f'財經新聞 {i}','summary':'市場與產業測試內容','source':['鉅亨網','MoneyDJ','Yahoo股市'][i%3],'source_group':'publisher','published_at':NOW,'link':'https://example.org/news','topic':'market','region':'TW','importance_score':40+i} for i in range(12)]
    items.append({'id':'tsmc','title':'台積電（2330）重大訊息公告','summary':'測試個股重大資訊','source':'公開資訊觀測站','source_group':'official-company','published_at':NOW,'link':'https://example.org/tsmc','topic':'material','region':'TW','importance_score':100,'asset_symbols':['2330']})
    sources=[
      {'name':'上市公司重大訊息','group':'official-company','method':'mops_listed','status':'ok','message':'100 筆','item_count':100,'last_checked_at':NOW,'last_success_at':NOW},
      {'name':'臺灣證券交易所新聞','group':'official','method':'twse_news','status':'ok','message':'20 筆','item_count':20,'last_checked_at':NOW,'last_success_at':NOW},
      {'name':'經濟日報','group':'publisher','method':'google','status':'empty','message':'本輪沒有符合新聞','item_count':0,'last_checked_at':NOW,'last_success_at':NOW},
      {'name':'工商時報','group':'publisher','method':'google','status':'warning','message':'暫時失敗','item_count':0,'last_checked_at':NOW,'last_success_at':None},
      {'name':'科技新報','group':'technology','method':'google','status':'scheduled','message':'輪替待檢','item_count':0,'last_checked_at':None,'last_success_at':None}
    ]
    return {'metadata':{'updated_at':NOW,'retention_days':20,'item_count':len(items),'material_item_count':1,'configured_source_count':99,'checked_source_count':45,'healthy_source_count':3,'warning_source_count':1,'active_source_count':4,'discovered_source_count':0,'rotation_bucket':1,'rotation_buckets':4},'sources':sources,'items':items}

PAYLOADS={'assets.json':assets(),'tw-market.json':tw_market(),'events.json':events(),'market-snapshot.json':market(),'tw-chips.json':chips(),'news.json':news(),'asset-audit.json':asset_audit(),
'asset-coverage.json':{'summary':{'total_stocks':1200,'complete':100,'partial_or_basic':1099,'missing':1,'field_counts':{'eps':1000,'pe':1100}},
'metadata':{'updated_at':NOW},'missing_stocks':[{'symbol':'2330','name':'台積電','exchange':'TWSE','industry':'半導體業','missing':['eps','roe']}],'partial_stocks':[]}}

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
        elif 'openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL' in clean:
            route.fulfill(status=200,content_type='application/json',body=json.dumps([{'Code':'2330','PEratio':'23.6','PBratio':'7.1','DividendYield':'1.7','Date':'20260803'}]))
        elif 'openapi.twse.com.tw/v1/opendata/t187ap03_L' in clean:
            route.fulfill(status=200,content_type='application/json',body=json.dumps([{'公司代號':'2330','公司名稱':'台灣積體電路製造股份有限公司','已發行普通股數或TDR原發行股數':'25930380458','實收資本額':'259303804580','上市日期':'1994/09/05'}]))
        elif 'openapi.twse.com.tw/v1/opendata/t187ap47_L' in clean:
            route.fulfill(status=200,content_type='application/json',body=json.dumps([{'基金代號':'0056','基金中文名稱':'元大台灣高股息證券投資信託基金','經理公司名稱':'元大投信','基金經理人':'測試經理人','基金類型':'高股息ETF','標的指數/追蹤指數名稱':'臺灣高股息指數','成立日期':'2007/12/13','上市日期':'2007/12/26','保管機構':'中國信託'}]))
        elif 'www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O' in clean:
            route.fulfill(status=200,content_type='application/json',body=json.dumps([{'公司代號':'6488','公司名稱':'環球晶圓股份有限公司','已發行普通股數':'437250000','實收資本額':'4372500000','上櫃日期':'2011/09/23'}]))
        elif 'www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis' in clean:
            route.fulfill(status=200,content_type='application/json',body=json.dumps([{'SecuritiesCompanyCode':'6488','PERatio':'18.2','PBRatio':'3.2','DividendYield':'2.1','Date':'20260803'}]))
        elif 'mis.twse.com.tw' in clean:
            route.fulfill(status=200,content_type='application/json',body=json.dumps({'msgArray':[{
              'c':'2330','n':'台積電','nf':'台灣積體電路製造股份有限公司','ex':'tse',
              'z':'1000','y':'990','o':'995','h':'1010','l':'992','v':'100000','tv':'200',
              'u':'1085','w':'895','d':'20260803','t':'13:20:00','tlong':'1785744000000',
              'a':'1001_1002_1003_1004_1005_','b':'1000_999_998_997_996_',
              'f':'10_20_30_40_50_','g':'15_25_35_45_55_'
            }]}))
        elif 'www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY' in clean:
            rows=[]
            for i in range(22):
                day=f'115/07/{i+1:02d}'
                close=900+i*2
                rows.append([day,'1,000,000','900,000,000',str(close-1),str(close+3),str(close-3),str(close),'+2','100'])
            route.fulfill(status=200,content_type='application/json',body=json.dumps({
              'stat':'OK','fields':['日期','成交股數','成交金額','開盤價','最高價','最低價','收盤價','漲跌價差','成交筆數'],'data':rows
            }))
        elif 's3.tradingview.com' in clean or 'widgets.tradingview-widget.com' in clean:
            route.fulfill(status=200,content_type='application/javascript',body='document.currentScript?.parentElement?.setAttribute("data-widget-loaded","1");')
        elif 'query1.finance.yahoo.com' in clean or 'query2.finance.yahoo.com' in clean:
            is_daily='interval=1d' in url
            count=260 if is_daily else 60
            base=900 if is_daily else 990
            timestamps=[1780000000+i*(86400 if is_daily else 60) for i in range(count)]
            closes=[base+i*(.4 if is_daily else .15) for i in range(count)]
            chart={'chart':{'result':[{'meta':{'regularMarketPrice':closes[-1],'chartPreviousClose':closes[-2]},
              'timestamp':timestamps,'indicators':{'quote':[{
                'open':[v-1 for v in closes],'high':[v+2 for v in closes],
                'low':[v-2 for v in closes],'close':closes,'volume':[1000+i*10 for i in range(count)]
              }]}}],'error':None}}
            route.fulfill(status=200,content_type='application/json',body=json.dumps(chart))
        elif 'api.coingecko.com' in clean:
            route.fulfill(status=503,body='')
        else:
            route.abort()
    page.route('**/*',route_handler)
    started=time.monotonic()
    page.set_content(inline_html(name),wait_until='domcontentloaded')
    for selector,minimum in assertions:
        page.wait_for_function('(args)=>document.querySelectorAll(args[0]).length>=args[1]',arg=[selector,minimum],timeout=12000)
    if name=="institutional.html":
        page.fill("#stockQueryInput","2330")
        page.click("#stockQueryButton")
        page.wait_for_function('()=>!document.querySelector("#stockQueryResult").hidden && document.querySelectorAll("[data-stock-tab]").length===13',timeout=12000)
        page.click('[data-stock-tab="orderbook"]')
        page.wait_for_function('()=>document.querySelectorAll(".orderbook-table tbody tr").length===5',timeout=12000)
        page.click('[data-stock-tab="technical"]')
        page.wait_for_function('()=>document.querySelectorAll(".technical-card-grid .stock-detail-metric").length>=10',timeout=12000)
        page.click('[data-stock-tab="financials"]')
        page.wait_for_function('()=>document.querySelectorAll(".financial-inline-table tbody tr").length>=1',timeout=12000)
        page.fill('#stockQueryInput','0056')
        page.click('#stockQueryButton')
        page.wait_for_function('()=>document.querySelector("#stockQueryResult").textContent.includes("基金經理人")',timeout=12000)
        page.fill('#stockQueryInput','6488')
        page.click('#stockQueryButton')
        page.click('[data-stock-tab="margin"]')
        page.wait_for_function('()=>document.querySelector("#stockQueryResult").textContent.includes("620 股")',timeout=12000)
    if name=="tw-market.html":
        if 'BAD0' in page.locator('body').inner_text():
            raise AssertionError('invalid NT$0 / -100% quote leaked into rankings')
    if name=="coverage.html":
        page.click('[data-audit-id="TW:2330"]')
        page.wait_for_function('()=>!document.querySelector("#coverageDetail").hidden && document.querySelectorAll(".audit-check-grid .audit-check").length>=8',timeout=12000)
    if name=="news.html":
        page.wait_for_function('()=>document.querySelector("#sourceHealthPanel").hidden===true',timeout=12000)
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
          'institutional.html':[('#institutionalGrid .info-card',4),('#marginGrid .info-card',4),('#stockQueryInput',1)],
          'news.html':[('#newsList .news-card',3)],
          'data-status.html':[('#channelGrid .channel-card',7)],
          'coverage.html':[('#coverageRows tr',1)],
        }
        for name,assertions in tests.items():
            page=browser.new_page()
            results[name]=round(run_page(page,name,assertions),3)
            page.close()
        browser.close()
    print(json.dumps({'status':'PASS','seconds':results,'total_seconds':round(sum(results.values()),3)},ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
