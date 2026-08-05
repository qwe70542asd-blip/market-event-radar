#!/usr/bin/env python3
from common import *
# The public endpoints differ by market and trading day. This updater preserves the last good payload
# and provides a stable schema; add official parsers here without ever replacing valid data with zeros.
def main():
 old=read_json(DATA/"tw-chips.json",{"markets":{},"items":{},"history":{},"available_dates":[]})
 old["metadata"]={**old.get("metadata",{}),"version":"v11.4.7","updated_at":NOW.isoformat(timespec="seconds"),"trading_date":old.get("metadata",{}).get("trading_date"),"source":"TWSE／TPEx official after-hours data","note":"保留最後成功資料；缺值不以 0 代替。"}
 write_payload("tw-chips.json","__TW_CHIPS_SEED__",old)
if __name__=="__main__":main()
