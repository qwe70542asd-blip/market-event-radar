#!/usr/bin/env python3
"""Refresh Taiwan closing quotes and online historical market turnover.

The updater validates the restored archive before reuse and backfills every calendar month from the official TWSE/TPEx network sources.
Local JSON is only a last-known-good cache. Turnover averages are published only from complete market totals, so a missing TPEx component can no longer silently bias volume momentum.
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

import requests

from common import DATA, NOW, read_json, write_payload, VERSION

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarketEventRadar/11.4.57)"}
TWSE_QUOTES = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
TPEX_QUOTES = "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
TWSE_FUNDS = "https://openapi.twse.com.tw/v1/opendata/t187ap47_L"
TPEX_FUNDS = "https://www.tpex.org.tw/openapi/v1/tpex_opfund_latest"
TWSE_HISTORY_OPENAPI = "https://openapi.twse.com.tw/v1/exchangeReport/FMTQIK"
TWSE_HISTORY_MONTH = "https://www.twse.com.tw/rwd/zh/afterTrading/FMTQIK"
TPEX_HISTORY_OPENAPI = "https://www.tpex.org.tw/openapi/v1/tpex_daily_trading_index"
TPEX_HISTORY_MONTH = "https://www.tpex.org.tw/www/zh-tw/afterTrading/tradingIndex"
HISTORY_START = date(2026, 1, 1)


def number(value: Any) -> float | None:
    text = str(value or "").replace(",", "").replace("元", "").strip()
    if not text or text in {"-", "--", "N/A", "null", "None"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def first(row: dict, names: tuple[str, ...]) -> str:
    for name in names:
        value = str(row.get(name) or "").strip()
        if value:
            return value
    return ""


def parse_market_date(value: Any) -> str | None:
    text = str(value or "").strip().replace("年", "/").replace("月", "/").replace("日", "")
    digits = re.sub(r"\D", "", text)
    try:
        if len(digits) == 7:
            year, month, day = int(digits[:3]) + 1911, int(digits[3:5]), int(digits[5:7])
        elif len(digits) >= 8:
            year, month, day = int(digits[:4]), int(digits[4:6]), int(digits[6:8])
        else:
            parts = [int(x) for x in re.findall(r"\d+", text)[:3]]
            if len(parts) != 3:
                return None
            year, month, day = parts
            if year < 1911:
                year += 1911
        parsed = date(year, month, day)
        return parsed.isoformat()
    except (ValueError, TypeError):
        return None


def valid_session_date(value: Any) -> str | None:
    """Return a verified-shaped weekday date, rejecting legacy weekend/future pollution."""
    day = parse_market_date(value)
    if not day:
        return None
    parsed = date.fromisoformat(day)
    if parsed < HISTORY_START or parsed > NOW.date() or parsed.weekday() >= 5:
        return None
    return day


def official_etf_codes(session: requests.Session, old_rows: list[dict]) -> tuple[set[str], list[str]]:
    """Load ETF symbols per exchange with the merged official asset master as fail-closed fallback."""
    warnings: list[str] = []
    master_assets = read_json(DATA / "assets.json", {"assets": []}).get("assets") or []
    master_by_exchange: dict[str, set[str]] = {"TWSE": set(), "TPEX": set()}
    for asset in master_assets:
        if not isinstance(asset, dict) or str(asset.get("asset_class") or "").lower() != "etf":
            continue
        exchange = str(asset.get("exchange") or "").upper()
        code = str(asset.get("symbol") or "").upper().strip()
        if exchange in master_by_exchange and code:
            master_by_exchange[exchange].add(code)
    codes: set[str] = set().union(*master_by_exchange.values())
    sources = [
        (TWSE_FUNDS, ("基金代號", "證券代號", "Code", "SecuritiesCode", "FundCode", "SecurityCode", "StockCode", "基金證券代號"), "TWSE"),
        (TPEX_FUNDS, ("SecuritiesCompanyCode", "SecuritiesCode", "Code", "FundCode", "SecurityCode", "StockCode", "證券代號", "基金代號"), "TPEx"),
    ]
    for url, keys, label in sources:
        source_codes: set[str] = set()
        try:
            response = session.get(url, headers=HEADERS, timeout=20)
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list):
                raise RuntimeError("unexpected response")
            for row in rows:
                if not isinstance(row, dict):
                    continue
                code = first(row, keys)
                if code:
                    source_codes.add(re.sub(r"[^0-9A-Za-z]", "", code).upper())
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{label} ETF list: {exc}")
        exchange_key = label.upper()
        if not source_codes:
            source_codes.update(master_by_exchange.get(exchange_key, set()))
            if source_codes:
                warnings.append(f"{label} ETF endpoint returned no recognized code; reused {len(source_codes)} official asset-master ETF symbols")
            else:
                source_codes.update(
                    str(row.get("symbol") or "").upper()
                    for row in old_rows
                    if str(row.get("exchange") or "").upper() == exchange_key
                    and row.get("asset_class") == "etf"
                    and str(row.get("symbol") or "").strip()
                )
                if source_codes:
                    warnings.append(f"{label} ETF endpoint returned no recognized code; reused {len(source_codes)} last-known-good ETF symbols")
                else:
                    warnings.append(f"{label} ETF endpoint returned no recognized code and no verified fallback ETF symbols were available")
        codes.update(source_codes)
    return {code for code in codes if code}, warnings


def asset_class(symbol: str, etf_codes: set[str]) -> str:
    code = symbol.upper()
    if code in etf_codes:
        return "etf"
    if re.fullmatch(r"\d{4}", code):
        return "stock"
    return "other"


def fetch_quotes(session: requests.Session, url: str, exchange: str, etf_codes: set[str]) -> list[dict]:
    response = session.get(url, headers=HEADERS, timeout=25)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        raise RuntimeError("unexpected quote response")
    output = []
    for row in payload:
        symbol = first(row, ("Code", "SecuritiesCompanyCode", "SecuritiesCode", "股票代號"))
        name = first(row, ("Name", "CompanyName", "SecuritiesCompanyName", "股票名稱"))
        price = number(first(row, ("ClosingPrice", "Close", "ClosePrice", "收盤價")))
        change = number(first(row, ("Change", "ChangeAmount", "漲跌價差")))
        if not symbol or price is None:
            continue
        previous = price - change if change is not None else None
        output.append({
            "symbol": symbol,
            "name": name,
            "exchange": exchange,
            "asset_class": asset_class(symbol, etf_codes),
            "price": price,
            "previous_close": previous,
            "change": change,
            "change_percent": change / previous * 100 if change is not None and previous not in (None, 0) else None,
            "open": number(first(row, ("OpeningPrice", "Open", "開盤價"))),
            "high": number(first(row, ("HighestPrice", "High", "最高價"))),
            "low": number(first(row, ("LowestPrice", "Low", "最低價"))),
            "volume": number(first(row, ("TradeVolume", "TradingShares", "TradingVolume", "成交股數"))),
            "trade_value": number(first(row, ("TradeValue", "TransactionAmount", "成交金額"))),
            "source_date": parse_market_date(first(row, ("Date", "日期", "資料日期", "TradeDate", "TradingDate"))),
            "quote_date": None,
            "quote_time": "",
            "status": "latest-close",
        })
    return output


def rows_and_fields(payload: Any) -> tuple[list[Any], list[str]]:
    if isinstance(payload, list):
        return payload, []
    if not isinstance(payload, dict):
        return [], []
    rows = payload.get("data") or payload.get("items") or payload.get("aaData") or payload.get("results") or payload.get("tables") or []
    raw_fields = payload.get("fields") or payload.get("columns") or payload.get("columnNames") or []
    if isinstance(rows, list) and rows and isinstance(rows[0], dict) and ("data" in rows[0] or "items" in rows[0]):
        table = rows[0]
        rows = table.get("data") or table.get("items") or []
        raw_fields = table.get("fields") or table.get("columns") or raw_fields
    fields: list[str] = []
    for field in raw_fields if isinstance(raw_fields, list) else []:
        if isinstance(field, dict):
            fields.append(str(field.get("name") or field.get("title") or field.get("field") or field.get("key") or ""))
        else:
            fields.append(str(field))
    return rows if isinstance(rows, list) else [], fields


def normalized_field(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u3400-\u9fff]+", "", str(value or "").strip().lower())


def field_value(row: dict[str, Any], aliases: tuple[str, ...]) -> tuple[Any, str]:
    wanted = {normalized_field(alias) for alias in aliases}
    for key, value in row.items():
        if normalized_field(key) in wanted and str(value or "").strip():
            return value, str(key)
    for key, value in row.items():
        norm = normalized_field(key)
        if any(alias and alias in norm for alias in wanted) and str(value or "").strip():
            return value, str(key)
    return None, ""


def history_records(payload: Any, component: str, source: str) -> list[dict[str, Any]]:
    raw_rows, fields = rows_and_fields(payload)
    output: list[dict[str, Any]] = []
    for raw in raw_rows:
        if isinstance(raw, (list, tuple)):
            row = {str(fields[index]): value for index, value in enumerate(raw) if index < len(fields)} if fields else {}
            if not row and len(raw) >= 3:
                row = {"Date": raw[0], "TradeValue": raw[2]}
        elif isinstance(raw, dict):
            row = raw
        else:
            continue
        date_raw, _ = field_value(row, (
            "Date", "日期", "資料日期", "TradeDate", "TradingDate", "成交日期", "年月日", "交易日期",
        ))
        if not str(date_raw or "").strip():
            for key, value in row.items():
                norm = normalized_field(key)
                if ("date" in norm or "日期" in norm or "年月日" in norm) and str(value or "").strip():
                    date_raw = value; break
        amount_raw, amount_key = field_value(row, (
            "TradeValue", "成交金額", "成交金額(元)", "成交金額（元）", "Amount", "TradingValue",
            "成交值", "TotalAmount", "TransactionAmount", "TradeAmount", "TotalTradeValue",
            "TransactionValue", "TotalTransactionAmount", "TradingAmount", "交易金額", "金額", "金額(元)", "金額（元）",
        ))
        if number(amount_raw) is None:
            candidates = []
            for key, value in row.items():
                norm = normalized_field(key)
                if any(term in norm for term in ("amount", "value", "金額", "成交值", "交易值")) and not any(term in norm for term in ("index", "指數", "volume", "數量", "股數", "筆數", "change", "漲跌")):
                    parsed = number(value)
                    if parsed is not None and parsed > 0:
                        candidates.append((parsed, str(key), value))
            if candidates:
                _, amount_key, amount_raw = max(candidates, key=lambda item: item[0])
        day = valid_session_date(parse_market_date(date_raw))
        value = number(amount_raw)
        key_norm = normalized_field(amount_key)
        if value is not None and ("千元" in amount_key or "仟元" in amount_key or "thousand" in key_norm):
            value *= 1000
        if not day or value is None or value <= 0:
            continue
        output.append({"date": day, component: value, "sources": [source]})
    return output


def fetch_json(session: requests.Session, url: str, *, params: dict[str, Any] | None = None) -> Any:
    response = session.get(url, params=params, headers=HEADERS, timeout=25)
    response.raise_for_status()
    return response.json()


def online_history(session: requests.Session) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    for url, component, label in (
        (TWSE_HISTORY_OPENAPI, "twse_trade_value", "TWSE OpenAPI FMTQIK"),
        (TPEX_HISTORY_OPENAPI, "tpex_trade_value", "TPEx OpenAPI daily trading index"),
    ):
        try:
            parsed = history_records(fetch_json(session, url), component, label)
            rows.extend(parsed)
            if not parsed:
                warnings.append(f"{label}: no recognized historical rows")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{label}: {exc}")

    # The monthly official endpoints are the archive backfill path. v11.4.32
    # stopped requesting later months once a *global* row count crossed 40,
    # which allowed entire months (notably May/July) to remain missing forever.
    # A full backfill runs at most once per day, so querying every month is both
    # bounded and much safer than a count-based shortcut.
    year, month = HISTORY_START.year, HISTORY_START.month
    while (year, month) <= (NOW.year, NOW.month):
        try:
            payload = fetch_json(session, TWSE_HISTORY_MONTH, params={"response": "json", "date": f"{year:04d}{month:02d}01"})
            parsed = history_records(payload, "twse_trade_value", "TWSE official monthly FMTQIK")
            rows.extend(parsed)
            if not parsed:
                warnings.append(f"TWSE monthly {year:04d}-{month:02d}: no recognized historical rows")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"TWSE monthly {year:04d}-{month:02d}: {exc}")
        try:
            payload = fetch_json(session, TPEX_HISTORY_MONTH, params={"date": f"{year:04d}/{month:02d}/01", "id": "", "response": "json"})
            parsed = history_records(payload, "tpex_trade_value", "TPEx official monthly daily-indices")
            rows.extend(parsed)
            if not parsed:
                warnings.append(f"TPEx monthly {year:04d}-{month:02d}: no recognized historical rows")
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"TPEx monthly {year:04d}-{month:02d}: {exc}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return rows, warnings


def merge_history(old_rows: list[dict], online_rows: list[dict], current_total: float | None, current_date: str | None = None) -> list[dict]:
    by_date: dict[str, dict[str, Any]] = {}
    for raw in [*old_rows, *online_rows]:
        day = valid_session_date(raw.get("date"))
        if not day:
            continue
        row = by_date.setdefault(day, {"date": day, "sources": []})
        for key in ("twse_trade_value", "tpex_trade_value"):
            value = number(raw.get(key))
            if value is not None and value > 0:
                row[key] = value
        # Older files may only have a total. Preserve an explicit v11.4.46
        # completeness flag, but never infer completeness from a source label:
        # v11.4.32 could say "TWSE/TPEx quote sum" while its stored total had
        # already been overwritten by the lone TWSE component.
        old_total = number(raw.get("trade_value"))
        if old_total is not None and old_total > 0:
            row["legacy_trade_value"] = old_total
            old_coverage = str(raw.get("total_coverage") or "")
            row["legacy_complete_total"] = raw.get("complete_total") is True and old_coverage in {
                "twse+tpex-components", "twse+tpex-quote-sum", "legacy-total-complete"
            }
        for source in raw.get("sources") or ([raw.get("source")] if raw.get("source") else []):
            if source and source not in row["sources"]:
                row["sources"].append(source)
    # Never fabricate a weekend/holiday turnover row.  The quote endpoints are
    # latest-close feeds, so their aggregate belongs to the verified trading
    # date from the official turnover history (or an explicit source date).
    current_date = valid_session_date(current_date)
    if current_date and current_total is not None and current_total > 0:
        row = by_date.setdefault(current_date, {"date": current_date, "sources": []})
        row["live_quote_sum"] = current_total
        if "TWSE/TPEx official latest-close quote sum" not in row["sources"]:
            row["sources"].append("TWSE/TPEx official latest-close quote sum")
    output = []
    for day, row in by_date.items():
        twse = number(row.get("twse_trade_value"))
        tpex = number(row.get("tpex_trade_value"))
        quote_total = number(row.get("live_quote_sum"))
        legacy_total = number(row.get("legacy_trade_value"))
        source_text = " + ".join(row.get("sources") or ["official online history"])
        if twse not in (None, 0) and tpex not in (None, 0):
            total, coverage, complete_total = twse + tpex, "twse+tpex-components", True
        elif quote_total not in (None, 0):
            # Latest-close quote sum includes ranked TWSE and TPEx securities and
            # is more complete than a lone TWSE component.
            total, coverage, complete_total = quote_total, "twse+tpex-quote-sum", True
        elif legacy_total not in (None, 0):
            total = legacy_total
            complete_total = row.get("legacy_complete_total") is True
            coverage = "legacy-total-complete" if complete_total else "legacy-total-unverified"
        elif twse not in (None, 0) or tpex not in (None, 0):
            total = twse if twse not in (None, 0) else tpex
            coverage, complete_total = "partial-single-market", False
        else:
            total, coverage, complete_total = None, "missing", False
        if total is None or total <= 0:
            continue
        output.append({
            "date": day,
            "trade_value": total,
            "twse_trade_value": twse,
            "tpex_trade_value": tpex,
            "total_coverage": coverage,
            "complete_total": complete_total,
            "source": source_text,
            "sources": row.get("sources") or [],
            "updated_at": NOW.isoformat(timespec="seconds"),
        })
    return sorted(output, key=lambda item: item["date"], reverse=True)


def trim_history_to_trading_date(rows: list[dict], trading_date: str | None) -> list[dict]:
    verified = valid_session_date(trading_date)
    if not verified:
        return [row for row in rows if valid_session_date(row.get("date"))]
    return [
        row for row in rows
        if (day := valid_session_date(row.get("date"))) and day <= verified
    ]


def average(values: list[float], sessions: int) -> float | None:
    selected = values[:sessions]
    return sum(selected) / sessions if len(selected) == sessions else None


def recent_history_complete(rows: list[dict], trading_date: str | None, sessions: int, max_calendar_days: int) -> bool:
    """Require enough complete totals and a recent time span, not just row count."""
    end = valid_session_date(trading_date)
    if not end:
        return False
    dates = [
        date.fromisoformat(str(row.get("date")))
        for row in rows
        if row.get("complete_total") is True and valid_session_date(row.get("date")) and str(row.get("date")) <= end
    ]
    dates = sorted(set(dates), reverse=True)
    if len(dates) < sessions:
        return False
    return (date.fromisoformat(end) - dates[sessions - 1]).days <= max_calendar_days


def exchange_row_counts(rows: list[dict]) -> dict[str, int]:
    counts = {"TWSE": 0, "TPEx": 0}
    for row in rows:
        exchange = str(row.get("exchange") or "")
        if exchange in counts and row.get("asset_class") in {"stock", "etf"}:
            counts[exchange] += 1
    return counts


def coherent_quote_date(rows: list[dict], old_trading_date: str | None) -> tuple[str | None, str, list[str]]:
    """Return a session date only when exchange dates do not contradict each other.

    Some official latest-close feeds omit a date.  A single observed exchange date
    may still anchor the snapshot, but a cross-exchange mismatch or regression
    must never relabel mixed/stale prices as a newer session.
    """
    notes: list[str] = []
    by_exchange: dict[str, set[str]] = {"TWSE": set(), "TPEx": set()}
    for row in rows:
        exchange = str(row.get("exchange") or "")
        day = valid_session_date(row.get("source_date"))
        if exchange in by_exchange and day:
            by_exchange[exchange].add(day)
    latest = {exchange: max(days) for exchange, days in by_exchange.items() if days}
    if len(latest) == 2 and len(set(latest.values())) != 1:
        notes.append(f"Quote session mismatch: TWSE={latest.get('TWSE')} TPEx={latest.get('TPEx')}")
        return None, "conflict", notes
    observed = max(latest.values(), default=None)
    if observed and old_trading_date and observed < old_trading_date:
        notes.append(f"Quote session regressed from {old_trading_date} to {observed}")
        return None, "regressed", notes
    if observed:
        return observed, "official-quote-date", notes
    return None, "undated", notes


def main() -> None:
    old = read_json(DATA / "tw-market.json", {"items": []})
    old_rows = old.get("items") or []
    old_trading_date = valid_session_date((old.get("metadata") or {}).get("trading_date"))
    session = requests.Session()
    etf_codes, warnings = official_etf_codes(session, old_rows)

    fetched_by_exchange: dict[str, list[dict]] = {}
    for url, exchange in ((TWSE_QUOTES, "TWSE"), (TPEX_QUOTES, "TPEx")):
        try:
            fetched_by_exchange[exchange] = fetch_quotes(session, url, exchange, etf_codes)
        except Exception as exc:  # noqa: BLE001
            fetched_by_exchange[exchange] = []
            warnings.append(f"{exchange} quotes: {exc}")

    # A single exchange can easily exceed the old global 100-row threshold.
    # Replacing the market with that partial snapshot silently deleted the other
    # exchange.  v11.4.46 requires both exchanges before replacing last-known-good.
    fresh_rows = [row for exchange in ("TWSE", "TPEx") for row in fetched_by_exchange.get(exchange, [])]
    fresh_counts = exchange_row_counts(fresh_rows)
    min_exchange_rows = 100
    fresh_complete = all(fresh_counts.get(exchange, 0) >= min_exchange_rows for exchange in ("TWSE", "TPEx"))
    fresh_quote_date, quote_date_basis, quote_notes = coherent_quote_date(fresh_rows, old_trading_date)
    warnings.extend(quote_notes)

    use_last_known_good = (not fresh_complete or quote_date_basis in {"conflict", "regressed"}) and bool(old_rows)
    if use_last_known_good:
        rows = [{**row, "asset_class": asset_class(str(row.get("symbol") or ""), etf_codes)} for row in old_rows]
        quote_snapshot_status = "last-known-good"
        quote_date_basis = "last-known-good"
        if not fresh_complete:
            warnings.append(
                "Incomplete cross-exchange quote refresh; retained the complete last-known-good snapshot "
                f"(fresh TWSE={fresh_counts.get('TWSE', 0)}, TPEx={fresh_counts.get('TPEx', 0)})"
            )
        quote_trading_date = old_trading_date
    else:
        rows = fresh_rows
        quote_snapshot_status = "fresh-complete" if fresh_complete else "fresh-incomplete-no-fallback"
        quote_trading_date = fresh_quote_date
        if not fresh_complete:
            warnings.append("No complete last-known-good quote snapshot was available; current output is explicitly marked incomplete")

    ranked_rows = [row for row in rows if row.get("asset_class") in {"stock", "etf"}]
    up = sum((number(row.get("change_percent")) or 0) > 0 for row in ranked_rows)
    down = sum((number(row.get("change_percent")) or 0) < 0 for row in ranked_rows)
    current_quote_total = sum(number(row.get("trade_value")) or 0 for row in ranked_rows) or None

    history_path = DATA / "market-volume-history.json"
    history = read_json(history_path, {"metadata": {}, "items": []})
    raw_old_history_rows = history.get("items") or []
    old_history_rows = [row for row in raw_old_history_rows if valid_session_date(row.get("date"))]
    legacy_history_polluted = len(old_history_rows) != len(raw_old_history_rows)
    history_meta = history.get("metadata") or {}
    history_checked_today = str(history_meta.get("last_full_backfill_date") or "") == NOW.date().isoformat()
    history_current_version = str(history_meta.get("version") or "") == VERSION
    enough_history = len(old_history_rows) >= 20
    if history_checked_today and history_current_version and enough_history and not legacy_history_polluted and old_trading_date:
        fetched_history, history_warnings = [], []
    else:
        fetched_history, history_warnings = online_history(session)
    if legacy_history_polluted:
        history_warnings.insert(0, "Removed legacy weekend/future turnover rows before selecting the trading session")
    warnings.extend(history_warnings)

    fetched_dates = [day for row in fetched_history if (day := valid_session_date(row.get("date")))]
    retained_dates = [day for row in old_history_rows if (day := valid_session_date(row.get("date")))]
    history_end = max([*fetched_dates, *retained_dates], default=None)

    # If both quote feeds are complete but neither exposes a date, official
    # turnover history is allowed to identify the latest close.  Crucially this
    # is separate from history retention; a partial/stale quote refresh never
    # drags trading_date backwards or causes newer history rows to be deleted.
    if not quote_trading_date and quote_snapshot_status.startswith("fresh"):
        quote_trading_date = max([day for day in (history_end, old_trading_date) if day], default=None)
        if quote_trading_date:
            quote_date_basis = "official-history-inference"
    trading_date = quote_trading_date or old_trading_date
    if not trading_date:
        warnings.append("Unable to verify latest Taiwan quote session; retained rows without a fabricated date")

    # Never relabel a last-known-good snapshot as a newer turnover-history date.
    for row in rows:
        row.pop("source_date", None)
        row["quote_date"] = trading_date
        row["quote_time"] = ""
        row["status"] = "latest-close" if quote_snapshot_status == "fresh-complete" else quote_snapshot_status

    # Turnover history has its own verified end date.  It may legitimately be
    # newer than a retained quote snapshot while one exchange endpoint is stale.
    history_rows = merge_history(old_history_rows, fetched_history, current_quote_total, trading_date)
    history_end = max(
        [day for item in history_rows if (day := valid_session_date(item.get("date")))],
        default=history_end,
    )
    previous_values = [
        number(item.get("trade_value"))
        for item in history_rows
        if item.get("date") != trading_date
        and (not trading_date or str(item.get("date")) < trading_date)
        and item.get("complete_total") is True
    ]
    previous_values = [value for value in previous_values if value is not None and value > 0]
    latest_row = next((item for item in history_rows if item.get("date") == trading_date), None)
    total_trade_value = number(latest_row.get("trade_value")) if latest_row and latest_row.get("complete_total") is True else current_quote_total
    history_complete_5d = recent_history_complete(history_rows, trading_date, 6, 20)
    history_complete_20d = recent_history_complete(history_rows, trading_date, 21, 45)
    history_complete_60d = recent_history_complete(history_rows, trading_date, 61, 110)
    average_5d = average(previous_values, 5) if history_complete_5d else None
    average_20d = average(previous_values, 20) if history_complete_20d else None
    average_60d = average(previous_values, 60) if history_complete_60d else None
    volume_ratio_20d = total_trade_value / average_20d if total_trade_value not in (None, 0) and average_20d not in (None, 0) else None

    volume_payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "history_start": HISTORY_START.isoformat(),
            "history_end": history_end,
            "quote_trading_date": trading_date,
            "retention_policy": "2026-01-01 through latest verified turnover-history session",
            "source_policy": "direct-online-official backfill at most once per day; restored rows are session-validated before reuse",
            "migration": "v11.4.46 separates quote-session freshness from turnover-history freshness and rejects partial cross-exchange snapshots",
            "last_full_backfill_date": NOW.date().isoformat() if fetched_history else history_meta.get("last_full_backfill_date"),
            "session_count": len(history_rows),
            "warnings": history_warnings,
        },
        "items": history_rows,
    }
    write_payload("market-volume-history.json", "__MARKET_VOLUME_HISTORY_SEED__", volume_payload)

    final_counts = exchange_row_counts(rows)
    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "trading_date": trading_date,
            "market_status": quote_snapshot_status,
            "quote_snapshot_status": quote_snapshot_status,
            "quote_date_basis": quote_date_basis,
            "quote_snapshot_complete": all(final_counts.get(exchange, 0) >= min_exchange_rows for exchange in ("TWSE", "TPEx")),
            "quote_exchange_counts": final_counts,
            "history_end": history_end,
            "source": "TWSE/TPEx official online open data",
            "warnings": warnings,
            "etf_count": sum(row.get("asset_class") == "etf" for row in rows),
            "excluded_product_count": sum(row.get("asset_class") == "other" for row in rows),
            "etf_classifier": "official-fund-whitelist-with-conservative-last-known-good-fallback",
            "total_trade_value": total_trade_value,
            "average_5d_trade_value": average_5d,
            "average_20d_trade_value": average_20d,
            "average_60d_trade_value": average_60d,
            "volume_ratio_20d": volume_ratio_20d,
            "volume_history_sessions": len(previous_values),
            "volume_history_start": HISTORY_START.isoformat(),
            "volume_history_source": "official-online-last-verified-session",
            "volume_history_complete": history_complete_20d,
            "volume_history_complete_5d": history_complete_5d,
            "volume_history_complete_20d": history_complete_20d,
            "volume_history_complete_60d": history_complete_60d,
        },
        "breadth": {"up": up, "down": down, "flat": len(ranked_rows) - up - down},
        "items": rows,
    }
    write_payload("tw-market.json", "__TW_MARKET_SEED__", payload)


if __name__ == "__main__":
    main()
