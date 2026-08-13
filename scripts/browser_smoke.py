#!/usr/bin/env python3
"""Real-browser release smoke for startup and delayed-live recovery.

The first pass blocks external HTTPS and verifies the bundled fallback can mount.
The second pass deliberately delays individual live channels beyond the old
homepage boot timeout and verifies mounted cards upgrade when data arrives.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765").rstrip("/")

DELAYED_FETCH_SCRIPT = r"""
(() => {
  const nativeFetch = window.fetch.bind(window);
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const localDay = offset => {
    const d = new Date(Date.now() + offset * 86400000);
    const parts = new Intl.DateTimeFormat('en-CA',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
    const map = Object.fromEntries(parts.map(p => [p.type,p.value]));
    return `${map.year}-${map.month}-${map.day}`;
  };
  const json = value => new Response(JSON.stringify(value),{status:200,headers:{'content-type':'application/json'}});
  window.fetch = async (...args) => {
    const input=args[0], url=String(typeof input==='string'?input:input?.url||'');
    if(url.includes('raw.githubusercontent.com/qwe70542asd-blip/market-event-radar/live-tw-market/tw-market.json')){
      await wait(5200);
      const items=Array.from({length:12},(_,i)=>({symbol:String(2300+i),name:`測試${i}`,exchange:'TWSE',asset_class:'stock',price:100+i,previous_close:99+i,change_percent:1,volume:1000,trade_value:1000000,quote_date:localDay(0),status:'latest-close'}));
      return json({metadata:{version:'v11.4.43',updated_at:new Date().toISOString(),trading_date:localDay(0),market_status:'latest-close',volume_ratio_20d:.94,volume_history_sessions:145,total_trade_value:1000000000000},breadth:{up:1244,down:743,flat:207},items});
    }
    if(url.includes('raw.githubusercontent.com/qwe70542asd-blip/market-event-radar/live-tw-chips/tw-chips.json')){
      await wait(2800);
      return json({metadata:{version:'v11.4.43',updated_at:new Date().toISOString(),trading_date:localDay(0)},markets:{twse:{institutional:{foreign_net:560548.321,trust_net:1000,dealer_net:2000,total_net:563548.321},institutional_date:localDay(0)}},items:{}});
    }
    if(url.includes('raw.githubusercontent.com/qwe70542asd-blip/market-event-radar/live-events/events.json')){
      await wait(3200);
      return json({metadata:{version:'v11.4.43',updated_at:new Date().toISOString()},events:[{id:'delayed-high-company',title:'測試公司 Q2 財報申報截止',start:`${localDay(1)}T09:00:00+08:00`,local_date:localDay(1),category:'taiwan',event_type:'corporate',event_group:'corporate',region:'TW',impact:'high',description:'高影響公司事件應進入首頁重大資訊。'}]});
    }
    if(url.includes('raw.githubusercontent.com/qwe70542asd-blip/market-event-radar/live-news-cna/news-cna.json')){
      await wait(1200);
      return json({metadata:{version:'v11.4.43',source_id:'cna',source_name:'中央社',updated_at:new Date().toISOString(),status:'ok',item_count:1},items:[{id:'delayed-news',source_id:'cna',source:'中央社',title:'台積電 AI 伺服器財報重大進展',url:'https://example.com/delayed-news',canonical_url:'https://example.com/delayed-news',url_valid:true,published_at:new Date().toISOString(),summary:'台積電與 AI 伺服器供應鏈重大財報與資本支出進展。',ai_summary:'台積電與 AI 伺服器供應鏈重大財報與資本支出進展。',impact:'high',importance_score:80,ai_category:'企業財報',topic:'earnings'}]});
    }
    if(/^https:\/\//i.test(url)) throw new TypeError('external blocked by delayed-live smoke');
    return nativeFetch(...args);
  };
})();
"""


def main() -> int:
    errors: list[str] = []
    with sync_playwright() as pw:
        system_chromium = Path("/usr/bin/chromium") if os.environ.get("MARKET_RADAR_SYSTEM_CHROMIUM") == "1" else None
        browser = pw.chromium.launch(headless=True, executable_path=str(system_chromium) if system_chromium and system_chromium.exists() else None)

        # Pass 1: deterministic seed/fallback boot.
        context = browser.new_context(service_workers="block")
        page = context.new_page()
        page.on("pageerror", lambda exc: errors.append(f"seed: {exc}"))
        page.route("https://**/*", lambda route: route.abort())
        page.goto(f"{BASE}/index.html", wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_function("document.querySelectorAll('#calendarGrid > *').length === 42", timeout=15_000)
        title = page.locator("#calendarTitle").inner_text().strip()
        cells = page.locator("#calendarGrid > *").count()
        page.locator('[data-calendar-mode="dividend"]').click()
        page.locator('[data-calendar-mode="market"]').click()
        if title in {"", "—"}: errors.append("seed: calendar title did not initialize")
        if cells != 42: errors.append(f"seed: calendar cell count {cells} != 42")
        context.close()

        # Pass 2: live data arrives later than the historical 4.5s boot race.
        context = browser.new_context(service_workers="block")
        page = context.new_page()
        page.on("pageerror", lambda exc: errors.append(f"delayed: {exc}"))
        page.add_init_script(DELAYED_FETCH_SCRIPT)
        page.goto(f"{BASE}/index.html?delayed-live=1", wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_function("document.querySelector('#breadthSummary')?.textContent.includes('1,244')", timeout=14_000)
        page.wait_for_function("document.querySelector('#foreignDirection')?.textContent === '買超'", timeout=14_000)
        page.wait_for_function("document.querySelector('#homeNews')?.textContent.includes('台積電 AI 伺服器財報重大進展') || document.querySelector('#homeNews')?.textContent.includes('測試公司 Q2 財報申報截止')", timeout=14_000)
        tone=page.locator("#marketTone").inner_text().strip(); breadth=page.locator("#breadthSummary").inner_text().strip(); momentum=page.locator("#volumeMomentum").inner_text().strip(); foot=page.locator("#focusUpdated").inner_text().strip()
        if tone != "偏多": errors.append(f"delayed: market tone stayed {tone!r}")
        if "1,244" not in breadth or "743" not in breadth: errors.append(f"delayed: breadth stayed {breadth!r}")
        if momentum != "量能正常": errors.append(f"delayed: volume momentum stayed {momentum!r}")
        if "行情" not in foot or "籌碼" not in foot: errors.append(f"delayed: status footer did not independently refresh: {foot!r}")
        context.close(); browser.close()

    if errors: raise SystemExit("browser smoke failed: " + " | ".join(errors))
    print("browser smoke ok: seed boot + delayed live rerender + progressive news/event recovery")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
