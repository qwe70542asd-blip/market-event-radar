#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import json, sys, time

from playwright.sync_api import sync_playwright
import e2e_smoke as smoke

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"validation-screenshots"
OUT.mkdir(exist_ok=True)


def install_routes(page):
    def route_handler(route):
        url=route.request.url
        clean=url.split("?",1)[0]
        filename=clean.rsplit("/",1)[-1]
        if filename in smoke.PAYLOADS:
            route.fulfill(status=200,content_type="application/json",
                          body=json.dumps(smoke.PAYLOADS[filename],ensure_ascii=False))
        elif clean.startswith("https://example.com/data/"):
            file=ROOT/"data"/filename
            route.fulfill(status=200,content_type="application/json",
                          body=file.read_bytes() if file.exists() else b"{}")
        elif "openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL" in clean:
            route.fulfill(status=200,content_type="application/json",body=json.dumps([{"Code":"2330","PEratio":"23.6","PBratio":"7.1","DividendYield":"1.7"}]))
        elif "openapi.twse.com.tw/v1/opendata/t187ap03_L" in clean:
            route.fulfill(status=200,content_type="application/json",body=json.dumps([{"公司代號":"2330","公司名稱":"台灣積體電路製造股份有限公司","已發行普通股數":"25930380458","實收資本額":"259303804580"}]))
        elif "mis.twse.com.tw" in clean:
            route.fulfill(status=200,content_type="application/json",body=json.dumps({"msgArray":[{
              "c":"2330","n":"台積電","nf":"台灣積體電路製造股份有限公司","ex":"tse",
              "z":"1000","y":"990","o":"995","h":"1010","l":"992","v":"100000","tv":"200",
              "u":"1085","w":"895","d":"20260803","t":"13:20:00","tlong":"1785744000000",
              "a":"1001_1002_1003_1004_1005_","b":"1000_999_998_997_996_",
              "f":"10_20_30_40_50_","g":"15_25_35_45_55_"
            }]}))
        elif "www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY" in clean:
            rows=[]
            for i in range(22):
                close=900+i*2
                rows.append([f"115/07/{i+1:02d}","1,000,000","900,000,000",
                             str(close-1),str(close+3),str(close-3),str(close),"+2","100"])
            route.fulfill(status=200,content_type="application/json",body=json.dumps({
              "stat":"OK","fields":["日期","成交股數","成交金額","開盤價","最高價","最低價","收盤價","漲跌價差","成交筆數"],
              "data":rows
            }))
        elif "query1.finance.yahoo.com" in clean or "query2.finance.yahoo.com" in clean:
            is_daily="interval=1d" in url
            count=260 if is_daily else 60
            base=900 if is_daily else 990
            timestamps=[1780000000+i*(86400 if is_daily else 60) for i in range(count)]
            closes=[base+i*(.4 if is_daily else .15) for i in range(count)]
            route.fulfill(status=200,content_type="application/json",body=json.dumps({"chart":{"result":[{
              "meta":{"regularMarketPrice":closes[-1],"chartPreviousClose":closes[-2]},
              "timestamp":timestamps,"indicators":{"quote":[{
                "open":[v-1 for v in closes],"high":[v+2 for v in closes],
                "low":[v-2 for v in closes],"close":closes,
                "volume":[1000+i*10 for i in range(count)]
              }]}
            }],"error":None}}))
        elif "s3.tradingview.com" in clean or "widgets.tradingview-widget.com" in clean:
            route.fulfill(status=200,content_type="application/javascript",
                          body='document.currentScript?.parentElement?.setAttribute("data-widget-loaded","1");')
        elif "api.coingecko.com" in clean:
            route.fulfill(status=503,body="")
        else:
            route.abort()
    page.route("**/*",route_handler)


def load(page,name):
    install_routes(page)
    page.set_content(smoke.inline_html(name),wait_until="domcontentloaded")


def px(page,selector):
    return float(page.eval_on_selector(selector,"el=>parseFloat(getComputedStyle(el).fontSize)"))


def require(condition,message):
    if not condition:
        raise AssertionError(message)


def main():
    started=time.monotonic()
    results={}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path="/usr/bin/chromium",
                                  args=["--no-sandbox","--disable-web-security"])
        context=browser.new_context(viewport={"width":1366,"height":768},device_scale_factor=1)

        page=context.new_page()
        load(page,"tw-market.html")
        page.wait_for_function('()=>document.querySelectorAll("#gainers tr").length>=3')
        rank_name=px(page,"#gainers td:nth-child(2) strong")
        rank_price=px(page,"#gainers td:nth-child(3)>strong")
        rank_pct=px(page,"#gainers td:nth-child(4)>strong")
        require(rank_name>=18,f"rank name font {rank_name}px")
        require(rank_price>=20,f"rank price font {rank_price}px")
        require(rank_pct>=18,f"rank percent font {rank_pct}px")
        page.screenshot(path=str(OUT/"tw-market-readable.png"),full_page=True)
        results["tw-market"]={"name_px":rank_name,"price_px":rank_price,"percent_px":rank_pct}
        page.close()

        page=context.new_page()
        load(page,"index.html")
        page.wait_for_function('()=>document.querySelectorAll("#calendarGrid .event-dot span").length>=3')
        event_font=px(page,"#calendarGrid .event-dot span")
        day_font=px(page,"#calendarGrid .day-head strong")
        weekday_font=px(page,".calendar-weekdays")
        require(event_font>=14,f"calendar event font {event_font}px")
        require(day_font>=21,f"calendar day font {day_font}px")
        require(weekday_font>=14,f"calendar weekday font {weekday_font}px")
        page.locator(".calendar-card").screenshot(path=str(OUT/"calendar-readable.png"))
        page.click('[data-day="2026-08-03"]')
        page.wait_for_function('()=>document.querySelectorAll("#dayDialogBody .day-event").length>=1')
        decoration=page.eval_on_selector("#dayDialogBody .day-event strong","el=>getComputedStyle(el).textDecorationLine")
        require(decoration=="none",f"day event underline remains: {decoration}")
        results["calendar"]={"event_px":event_font,"day_px":day_font,"weekday_px":weekday_font,"event_text_decoration":decoration}
        page.close()

        page=context.new_page()
        load(page,"institutional.html")
        page.fill("#stockQueryInput","2330")
        page.click("#stockQueryButton")
        page.wait_for_function('()=>document.querySelectorAll("[data-stock-tab]").length===13')
        page.click('[data-stock-tab="technical"]')
        page.wait_for_function('()=>document.querySelectorAll(".technical-card-grid .stock-detail-metric").length>=10')
        metric_label=px(page,".technical-card-grid .stock-detail-metric span")
        metric_value=px(page,".technical-card-grid .stock-detail-metric strong")
        require(metric_label>=14,f"technical label font {metric_label}px")
        require(metric_value>=21,f"technical value font {metric_value}px")
        page.locator("#stockQueryResult").screenshot(path=str(OUT/"stock-technical-readable.png"))
        results["stock-technical"]={"label_px":metric_label,"value_px":metric_value}
        page.close()

        page=context.new_page()
        load(page,"news.html")
        page.wait_for_function('()=>document.querySelectorAll("#newsList .news-card").length>=3 && document.querySelector("#sourceHealthPanel").hidden===true')
        news_title=px(page,"#newsList .news-card h3")
        news_summary=px(page,"#newsList .news-card p")
        require(news_title>=18,f"news title font {news_title}px")
        require(news_summary>=12,f"news summary font {news_summary}px")
        page.screenshot(path=str(OUT/"news-readable.png"),full_page=True)
        results["news"]={"title_px":news_title,"summary_px":news_summary}
        page.close()

        page=context.new_page()
        load(page,"coverage.html")
        page.wait_for_function('()=>document.querySelectorAll("#coverageRows tr").length>=1')
        audit_code=px(page,"#coverageRows td:first-child strong")
        audit_pct=px(page,"#coverageRows .audit-status")
        require(audit_code>=13,f"audit code font {audit_code}px")
        require(audit_pct>=13,f"audit percent font {audit_pct}px")
        page.screenshot(path=str(OUT/"full-audit-readable.png"),full_page=True)
        results["full-audit"]={"code_px":audit_code,"percent_px":audit_pct}
        page.close()

        context.close()
        browser.close()

    elapsed=time.monotonic()-started
    require(elapsed<60,f"visual test took {elapsed:.2f}s")
    print(json.dumps({"status":"PASS","seconds":round(elapsed,3),"results":results},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
