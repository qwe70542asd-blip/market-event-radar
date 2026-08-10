#!/usr/bin/env python3
"""Progressively enrich Taiwan ETF details from independent sources.

Precedence inside this channel:
1. TWSE ETF e添富 / issuer official links
2. MoneyDJ structured ETF pages
3. HiStock active ETF observation page
4. Yahoo ETF top holdings / reference hints (merged by frontend coverage)

The channel is reference-only when no official field is available. It never
replaces an official value already embedded in assets.json on the frontend.
"""
from __future__ import annotations

import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from common import DATA, NOW, read_json, write_payload

VERSION = "v11.4.39"
BATCH = 24
PRIORITY_SYMBOLS = ["00981A", "00403A", "00631L", "006208", "0050", "0056", "00878", "00919", "2330", "2317", "2454"]
TIMEOUT = 24
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5",
}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def number(value: Any) -> float | None:
    text = clean(value).replace(",", "").replace("%", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def date_text(value: Any) -> str | None:
    text = clean(value)
    m = re.search(r"(20\d{2})[/-](\d{1,2})[/-](\d{1,2})", text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"(\d{2,3})[/-](\d{1,2})[/-](\d{1,2})", text)
    if m:
        return f"{int(m.group(1))+1911}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def fetch(url: str) -> tuple[str, BeautifulSoup]:
    response = SESSION.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding or "utf-8"
    return response.url, BeautifulSoup(response.text, "lxml")


def table_rows(soup: BeautifulSoup) -> list[list[str]]:
    rows: list[list[str]] = []
    for tr in soup.select("tr"):
        cells = [clean(cell.get_text(" ", strip=True)) for cell in tr.select("th,td")]
        if cells:
            rows.append(cells)
    return rows


def pair_map(soup: BeautifulSoup) -> dict[str, str]:
    out: dict[str, str] = {}
    for row in table_rows(soup):
        if len(row) == 2 and len(row[0]) <= 24:
            out[row[0].strip("：:")] = row[1]
        elif len(row) >= 4:
            for index in range(0, len(row) - 1, 2):
                key = row[index].strip("：:")
                if key and len(key) <= 24:
                    out[key] = row[index + 1]
    return out


def pick(pairs: dict[str, str], *labels: str) -> str | None:
    for label in labels:
        for key, value in pairs.items():
            if label in key and clean(value):
                return clean(value)
    return None


def parse_twse(symbol: str) -> dict[str, Any]:
    url = f"https://www.twse.com.tw/zh/ETFortune/etfInfo/{symbol}"
    final_url, soup = fetch(url)
    text = clean(soup.get_text(" ", strip=True))
    result: dict[str, Any] = {
        "source": "TWSE ETF e添富",
        "source_url": final_url,
        "source_level": "official",
    }
    headings = [clean(node.get_text(" ", strip=True)) for node in soup.find_all(["h1", "h2", "h3"])]
    heading_text = next((value for value in headings if "基金" in value and len(value) >= 8), None)
    if heading_text:
        result["formal_name"] = heading_text
    pairs = pair_map(soup)
    patterns = {
        "short_name": r"證券簡稱\s+(.+?)\s+證券類別",
        "category": r"證券類別\s+(.+?)\s+發行公司",
        "issuer": r"發行公司\s+(.+?)\s+基金經理人",
        "manager": r"基金經理人\s+(.+?)\s+(?:標的指數|追蹤指數)",
        # Active ETFs put「投資策略」immediately after 標的指數.  The old
        # boundary only stopped at「主題/因子」and swallowed the entire strategy.
        "benchmark": r"(?:標的指數|追蹤指數)\s+(.+?)\s+(?:投資策略|主題/因子|基金特色|資產規模|受益人次)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if match:
            result[key] = clean(match.group(1))
    structured = {
        "short_name": pick(pairs, "證券簡稱", "基金簡稱"),
        "category": pick(pairs, "證券類別", "基金類型"),
        "issuer": pick(pairs, "發行公司", "投信公司", "基金公司"),
        "manager": pick(pairs, "基金經理人", "經理人"),
        "benchmark": pick(pairs, "標的指數", "追蹤指數"),
    }
    for key, value in structured.items():
        if value and not result.get(key):
            result[key] = clean(value)
    if result.get("benchmark"):
        benchmark = re.split(r"\s+(?=投資策略|主題/因子|基金特色|資產規模|受益人次)", clean(result["benchmark"]), maxsplit=1)[0]
        result["benchmark"] = "不適用" if benchmark in {"無", "不適用", "N/A", "NA", "-", "—"} else benchmark
    aum = re.search(r"資產規模(?:\(億元\))?\s*([\d,.]+)\s*億元", text)
    if aum:
        result["aum"] = number(aum.group(1))
        result["aum_unit"] = "億元"
    beneficiaries = re.search(r"受益人次(?:\(萬人\))?\s*([\d,.]+)\s*萬人", text)
    if beneficiaries:
        value = number(beneficiaries.group(1))
        result["beneficiary_count"] = int(value * 10000) if value is not None else None
    distributions = []
    for row in table_rows(soup):
        if len(row) < 2:
            continue
        payment = date_text(row[0])
        amount = number(row[1])
        if payment and amount is not None and 0 <= amount < 100:
            distributions.append({
                "payment_date": payment,
                "amount": amount,
                "cash": amount,
                "source": "TWSE ETF e添富",
                "url": final_url,
            })
    if distributions:
        unique = {(row["payment_date"], row["amount"]): row for row in distributions}
        result["distributions"] = sorted(unique.values(), key=lambda row: row["payment_date"], reverse=True)[:30]
    return {key: value for key, value in result.items() if value not in (None, "", [])}


def moneydj_url(symbol: str, page: str) -> str:
    return f"https://www.moneydj.com/ETF/X/Basic/{page}.xdjhtm?etfid={symbol}.TW"


def parse_moneydj_basic(symbol: str) -> dict[str, Any]:
    final_url, soup = fetch(moneydj_url(symbol, "Basic0004"))
    pairs = pair_map(soup)
    official_link = None
    for anchor in soup.select("a[href]"):
        text = clean(anchor.get_text(" ", strip=True))
        href = urljoin(final_url, anchor.get("href"))
        if "官方網站" in text or ("ETF/Fund" in href or "product" in href.lower()):
            official_link = href
            break
    result = {
        "source": "MoneyDJ ETF 基本資料",
        "source_url": final_url,
        "source_level": "reference",
        "formal_name": pick(pairs, "ETF名稱", "基金名稱"),
        "issuer": pick(pairs, "基金公司", "發行公司", "投信公司"),
        "manager": pick(pairs, "基金經理人", "經理人"),
        "inception_date": date_text(pick(pairs, "成立日期", "基金成立日")),
        "listing_date": date_text(pick(pairs, "上市日期", "掛牌日期")),
        "benchmark": pick(pairs, "追蹤指數", "標的指數"),
        "category": pick(pairs, "基金類型", "ETF類型", "投資類型"),
        "region": pick(pairs, "投資區域", "區域"),
        "currency": pick(pairs, "計價幣別", "幣別"),
        "management_fee": pick(pairs, "經理費", "管理費"),
        "custody_fee": pick(pairs, "保管費"),
        "strategy": pick(pairs, "投資策略"),
        "official_url": official_link,
    }
    return {key: value for key, value in result.items() if value not in (None, "", [])}


def parse_moneydj_holdings(symbol: str) -> dict[str, Any]:
    final_url, soup = fetch(moneydj_url(symbol, "Basic0007"))
    rows = table_rows(soup)
    holdings: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    mode = None
    for row in rows:
        joined = " ".join(row)
        if "個股名稱" in joined and "投資比例" in joined:
            mode = "holdings"
            continue
        if "產業" in joined and "比例" in joined and "個股名稱" not in joined:
            mode = "allocation"
            continue
        if mode == "holdings" and len(row) >= 2:
            match = re.search(r"(.+?)\((\d{4,6}[A-Z]?)\.(?:TW|TWO)\)", row[0], re.I)
            if not match:
                continue
            weight = number(row[1])
            shares = number(row[2]) if len(row) >= 3 else None
            holdings.append({
                "name": clean(match.group(1)).rstrip("*"),
                "symbol": match.group(2).upper(),
                "weight": weight,
                "shares": shares,
                "source": "MoneyDJ ETF 持股",
                "url": final_url,
            })
        elif mode == "allocation" and len(row) >= 2:
            weight = number(row[-1])
            if weight is None or not clean(row[0]) or "現金" in row[0]:
                continue
            allocations.append({"name": clean(row[0]), "weight": weight, "source": "MoneyDJ ETF 持股"})
    page_text = clean(soup.get_text(" ", strip=True))
    dates = re.findall(r"資料日期[:：]?\s*(20\d{2}[/-]\d{1,2}[/-]\d{1,2})", page_text)
    result = {
        "source": "MoneyDJ ETF 持股",
        "source_url": final_url,
        "source_level": "reference",
        "holdings": holdings[:100],
        "allocations": allocations[:30],
        "holdings_date": date_text(dates[-1]) if dates else None,
    }
    return {key: value for key, value in result.items() if value not in (None, "", [])}


def parse_moneydj_nav(symbol: str) -> dict[str, Any]:
    final_url, soup = fetch(moneydj_url(symbol, "Basic0003"))
    result: dict[str, Any] = {"source": "MoneyDJ ETF 淨值", "source_url": final_url, "source_level": "reference"}
    for row in table_rows(soup):
        if not row:
            continue
        label = row[0]
        if label.startswith("市價") and len(row) >= 2:
            result["market_price"] = number(row[1])
            result["price_date"] = date_text(label)
        elif label.startswith("淨值") and len(row) >= 2:
            result["nav"] = number(row[1])
            result["nav_date"] = date_text(label)
    if result.get("market_price") not in (None, 0) and result.get("nav") is not None:
        result["premium_discount"] = (result["market_price"] - result["nav"]) / result["nav"] * 100 if result["nav"] else None
    return {key: value for key, value in result.items() if value not in (None, "", [])}


def parse_moneydj_distributions(symbol: str) -> dict[str, Any]:
    final_url, soup = fetch(moneydj_url(symbol, "Basic0005"))
    distributions = []
    for table in soup.select("table"):
        rows = []
        for tr in table.select("tr"):
            cells = [clean(cell.get_text(" ", strip=True)) for cell in tr.select("th,td")]
            if cells:
                rows.append(cells)
        if not rows:
            continue
        header_index = next((index for index, row in enumerate(rows) if any("配息" in cell or "除息" in cell or "發放" in cell for cell in row)), None)
        if header_index is None:
            continue
        headers = rows[header_index]
        ex_index = next((index for index, cell in enumerate(headers) if "除息" in cell), None)
        payment_index = next((index for index, cell in enumerate(headers) if "發放" in cell), None)
        amount_index = next((index for index, cell in enumerate(headers) if ("每單位" in cell or "配息金額" in cell or cell.strip() == "配息") and "率" not in cell), None)
        for row in rows[header_index + 1:]:
            if not any(date_text(cell) for cell in row):
                continue
            ex_date = date_text(row[ex_index]) if ex_index is not None and ex_index < len(row) else next((date_text(cell) for cell in row if date_text(cell)), None)
            payment_date = date_text(row[payment_index]) if payment_index is not None and payment_index < len(row) else None
            amount = number(row[amount_index]) if amount_index is not None and amount_index < len(row) else None
            if amount is None:
                candidates = [number(cell) for cell in row]
                candidates = [value for value in candidates if value is not None and 0 < value <= 5]
                amount = min(candidates) if candidates else None
            if not ex_date or amount is None:
                continue
            distributions.append({
                "ex_date": ex_date,
                "payment_date": payment_date,
                "amount": amount,
                "cash": amount,
                "source": "MoneyDJ ETF 配息",
                "url": final_url,
            })
    unique = {(row.get("ex_date"), row.get("payment_date"), row.get("amount")): row for row in distributions}
    return {
        "source": "MoneyDJ ETF 配息",
        "source_url": final_url,
        "source_level": "reference",
        "distributions": sorted(unique.values(), key=lambda row: row.get("ex_date") or "", reverse=True)[:40],
    }


def histock_master() -> dict[str, dict[str, Any]]:
    url = "https://histock.tw/stock/active-etf.aspx"
    try:
        final_url, soup = fetch(url)
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for row in table_rows(soup):
        code_index = next((index for index, cell in enumerate(row) if re.fullmatch(r"\d{4,6}[A-Z]?", cell.replace(" ", ""), re.I)), None)
        if code_index is None or len(row) < code_index + 4:
            continue
        symbol = row[code_index].replace(" ", "").upper()
        out[symbol] = {
            "source": "HiStock 主動式 ETF 觀測站",
            "source_url": final_url,
            "source_level": "reference",
            "formal_name": row[code_index + 1] if len(row) > code_index + 1 else None,
            "issuer": row[code_index + 2] if len(row) > code_index + 2 else None,
            "aum": number(row[code_index + 3]) if len(row) > code_index + 3 else None,
            "aum_unit": "億元",
            "listing_date": next((date_text(cell) for cell in reversed(row) if date_text(cell)), None),
        }
    return out


def merge_sources(records: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"sources": [], "field_sources": {}, "verification": {}}
    priority = {"official": 3, "reference": 1}
    selected_priority: dict[str, int] = {}
    list_fields = {"holdings", "allocations", "distributions"}
    metadata_fields = {"source", "source_url", "source_level"}
    for record in records:
        if not record:
            continue
        source = {key: record.get(key) for key in ("source", "source_url", "source_level") if record.get(key)}
        if source and source not in result["sources"]:
            result["sources"].append(source)
        level = str(record.get("source_level") or "reference")
        rank = priority.get(level, 1)
        for key, value in record.items():
            if key in metadata_fields or value in (None, "", []):
                continue
            if key in list_fields:
                if not result.get(key) or rank > selected_priority.get(key, -1):
                    result[key] = value
                    selected_priority[key] = rank
                    result["field_sources"][key] = record.get("source")
                continue
            if rank > selected_priority.get(key, -1) or key not in result:
                result[key] = value
                selected_priority[key] = rank
                result["field_sources"][key] = record.get("source")
    for key, source_name in result["field_sources"].items():
        matches = []
        for record in records:
            if record.get(key) not in (None, "", []):
                matches.append((record.get("source_level") or "reference", record.get(key), record.get("source")))
        if any(level == "official" for level, _value, _source in matches):
            status = "official"
        elif len(matches) >= 2 and len({json.dumps(value, ensure_ascii=False, sort_keys=True) for _level, value, _source in matches}) == 1:
            status = "multi_source"
        else:
            status = "reference"
        result["verification"][key] = {"status": status, "source": source_name, "matches": len(matches)}
    return result


def parse_one(asset: dict[str, Any], histock: dict[str, dict[str, Any]]) -> tuple[str, dict[str, Any] | None, str | None]:
    symbol = str(asset.get("symbol") or "").upper()
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    jobs = [parse_twse, parse_moneydj_basic, parse_moneydj_holdings, parse_moneydj_nav, parse_moneydj_distributions]
    for job in jobs:
        try:
            records.append(job(symbol))
        except Exception as exc:
            errors.append(f"{job.__name__}: {exc}")
        time.sleep(random.uniform(0.08, 0.25))
    if histock.get(symbol):
        records.append(histock[symbol])
    merged = merge_sources(records)
    if len(merged) <= 3:
        return symbol, None, "; ".join(errors) or "all ETF sources empty"
    merged.update({
        "symbol": symbol,
        "updated_at": NOW.isoformat(timespec="seconds"),
        "status": "ok" if not errors else "partial",
        "errors": errors[:10],
    })
    return symbol, merged, None



def derive_allocations_from_holdings(row: dict[str, Any], sector_by_symbol: dict[str, str]) -> None:
    if row.get("allocations") or not row.get("holdings"):
        return
    totals: dict[str, float] = {}
    for holding in row.get("holdings") or []:
        symbol = str(holding.get("symbol") or "").upper()
        sector = clean(holding.get("sector") or holding.get("industry") or sector_by_symbol.get(symbol))
        weight = number(holding.get("weight"))
        if not sector or weight is None:
            continue
        totals[sector] = totals.get(sector, 0.0) + weight
    if not totals:
        return
    row["allocations"] = [{"name": name, "weight": weight, "source": "持股×官方產業分類計算"} for name, weight in sorted(totals.items(), key=lambda item: item[1], reverse=True)]
    row.setdefault("field_sources", {})["allocations"] = "持股×官方產業分類計算"
    row.setdefault("verification", {})["allocations"] = {"status": "calculated", "source": "持股×官方產業分類計算", "matches": 1}


def main() -> None:
    assets = read_json(DATA / "assets.json", {"assets": []}).get("assets", [])
    sector_by_symbol = {str(asset.get("symbol") or "").upper(): clean(asset.get("official_industry") or asset.get("sub_industry") or asset.get("industry")) for asset in assets if asset.get("asset_class") == "stock"}
    old = read_json(DATA / "etf-details.json", {"items": {}, "state": {}})
    items = dict(old.get("items") or {})
    state = dict(old.get("state") or {})
    candidates = [asset for asset in assets if asset.get("market") == "TW" and asset.get("asset_class") == "etf" and asset.get("symbol")]
    priority = {symbol: index for index, symbol in enumerate(PRIORITY_SYMBOLS)}
    candidates.sort(key=lambda row: (priority.get(str(row.get("symbol")).upper(), 9999), str(row.get("symbol"))))
    cursor = int(state.get("cursor") or 0)
    cursor = cursor if cursor < len(candidates) else 0
    rolling = candidates[cursor:cursor + BATCH]
    if len(rolling) < BATCH:
        rolling += candidates[:BATCH - len(rolling)]
    missing_priority = [asset for asset in candidates if str(asset.get("symbol")).upper() in priority and str(asset.get("symbol")).upper() not in items]
    batch, seen = [], set()
    for asset in missing_priority + rolling:
        symbol = str(asset.get("symbol")).upper()
        if symbol in seen:
            continue
        batch.append(asset); seen.add(symbol)
        if len(batch) >= BATCH:
            break
    histock = histock_master()
    success = 0
    errors = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(parse_one, asset, histock) for asset in batch]
        for future in as_completed(futures):
            symbol, row, error = future.result()
            if row:
                previous_row = items.get(symbol) or {}
                current_holdings = row.get("holdings") or []
                previous_holdings = previous_row.get("holdings") or []
                current_date = row.get("holdings_date")
                previous_date = previous_row.get("holdings_date")
                if current_holdings and previous_holdings and current_date and previous_date and current_date != previous_date:
                    previous_map = {str(item.get("symbol") or "").upper(): item for item in previous_holdings if item.get("symbol")}
                    for holding in current_holdings:
                        old_holding = previous_map.get(str(holding.get("symbol") or "").upper()) or {}
                        current_shares = number(holding.get("shares"))
                        old_shares = number(old_holding.get("shares"))
                        if current_shares is not None and old_shares is not None:
                            holding["change_shares"] = current_shares - old_shares
                    row["holdings_previous_date"] = previous_date
                    history = list(previous_row.get("holdings_history") or [])
                    history.insert(0, {"date": previous_date, "holdings": previous_holdings})
                    row["holdings_history"] = history[:5]
                elif current_date == previous_date and previous_holdings:
                    old_map = {str(item.get("symbol") or "").upper(): item for item in previous_holdings if item.get("symbol")}
                    for holding in current_holdings:
                        old_holding = old_map.get(str(holding.get("symbol") or "").upper()) or {}
                        if holding.get("change_shares") is None and old_holding.get("change_shares") is not None:
                            holding["change_shares"] = old_holding.get("change_shares")
                items[symbol] = row
                success += 1
            elif error:
                errors.append({"symbol": symbol, "error": error[:400]})
    for row in items.values():
        if isinstance(row, dict):
            derive_allocations_from_holdings(row, sector_by_symbol)
    next_cursor = (cursor + len(batch)) % len(candidates) if candidates else 0
    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": "ok" if success == len(batch) and success else "partial" if success or items else "warning",
            "item_count": len(items),
            "batch_size": len(batch),
            "batch_success": success,
            "note": "Official ETF fields are primary. MoneyDJ、HiStock 與 Yahoo 交叉補齊基金主檔、配息、持股與產業配置；前端同時會整合 ETF 相關參考來源。",
        },
        "state": {"cursor": next_cursor, "last_batch_at": NOW.isoformat(timespec="seconds")},
        "errors": errors[:100],
        "items": items,
    }
    write_payload("etf-details.json", "__ETF_DETAILS_SEED__", payload)
    print(payload["metadata"])


if __name__ == "__main__":
    main()
