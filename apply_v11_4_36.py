#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NEW_VERSION = "v11.4.36"
OLD_VERSION = "v11.4.36"


def replace_function(text: str, name: str, replacement: str, next_name: str) -> str:
    start = text.find(f"def {name}(")
    if start < 0:
        raise RuntimeError(f"function not found: {name}")
    end = text.find(f"\ndef {next_name}(", start)
    if end < 0:
        raise RuntimeError(f"next function not found after {name}: {next_name}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end + 1:]


def patch_update_events() -> None:
    path = ROOT / "scripts" / "update_events.py"
    text = path.read_text(encoding="utf-8")

    robust_date = r'''def parse_market_date(value: Any) -> date | None:
    """Normalize ROC/Gregorian dates, including non-zero-padded components.

    Examples accepted: 115/08/07, 115/8/7, 1150807, 2026/08/07,
    2026/8/7 and 20260807.  Separated forms are parsed by components first so
    a Gregorian date such as 2026/8/7 is never mistaken for a 3-digit ROC year.
    """
    text = clean(value).replace("年", "/").replace("月", "/").replace("日", "")
    if not text:
        return None

    token_match = re.search(r"(?<!\\d)(\\d{3,4})[./-](\\d{1,2})[./-](\\d{1,2})(?!\\d)", text)
    if token_match:
        year, month, day_value = map(int, token_match.groups())
        if year < 1911:
            year += 1911
        try:
            return date(year, month, day_value)
        except ValueError:
            return None

    compact_match = re.search(r"(?<!\\d)(\\d{7}|\\d{8})(?!\\d)", text)
    if compact_match:
        compact = compact_match.group(1)
        try:
            if len(compact) == 7:
                return date(int(compact[:3]) + 1911, int(compact[3:5]), int(compact[5:7]))
            return date(int(compact[:4]), int(compact[4:6]), int(compact[6:8]))
        except ValueError:
            return None

    try:
        parsed = date_parser.parse(text, fuzzy=True)
        year = parsed.year + 1911 if parsed.year < 1911 else parsed.year
        return date(year, parsed.month, parsed.day)
    except (ValueError, TypeError, OverflowError):
        return None'''
    text = replace_function(text, "parse_market_date", robust_date, "first_market_date")

    tpex_history_parser = r'''def parse_tpex_exdiv_history_payload(payload: Any, source_url: str = TPEX_EXDIV_HISTORY_URL) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for row in payload_dict_rows(payload):
        date_raw = first_value(row, [
            "ExRrightsExDividendDate", "ExRightsExDividendDate", "ExDate", "Date",
            "資料日期", "交易日期", "除權息日期", "除權除息日期", "除權息交易日",
        ]) or semantic_field(row, all_terms=("日期",), any_terms=("除權", "除息", "權息"))
        day = first_market_date(date_raw)
        symbol, name = dividend_company_identity(row)
        if not symbol:
            symbol = first_value(row, ["代號", "Symbol", "股票代號", "證券代號"])
        if not name:
            name = first_value(row, ["名稱", "ShortName", "股票名稱", "證券名稱"])
        if not day or day < ARCHIVE_START or day > NOW.date() or not symbol:
            continue

        kind = first_value(row, [
            "ExRrightsExDividend", "ExRightsExDividend", "Type", "除權息", "權息別",
            "權/息", "權或息", "除權息別",
        ]) or semantic_field(row, any_terms=("權息別", "除權息", "權或息", "exrightsexdividend", "type"))

        cash_raw = first_value(row, [
            "CashDividend", "CashDividendValue", "DividendValue", "息值", "現金股利", "現金股利(元)",
        ]) or semantic_field(row, any_terms=("現金股利", "cashdividend", "息值"), exclude_terms=("股票", "配股"))
        stock_per_thousand = first_value(row, ["每仟股無償配股", "每千股無償配股"])
        stock_raw = first_value(row, [
            "StockDividendRatio", "StockDividendValue", "股票股利", "RightValue", "權值", "無償配股率",
        ]) or semantic_field(row, any_terms=("股票股利", "stockdividend", "無償配股率"))
        stock_ratio = parse_number(stock_raw)
        if stock_ratio is None and stock_per_thousand not in (None, ""):
            shares_per_thousand = parse_number(stock_per_thousand)
            stock_ratio = (shares_per_thousand / 1000.0) if shares_per_thousand is not None else None

        if not kind:
            cash_value = parse_number(cash_raw)
            kind = "除權息" if stock_ratio not in (None, 0) and cash_value not in (None, 0) else "除權" if stock_ratio not in (None, 0) else "除息"
        events.append(make_exdiv_event(
            "TPEX", clean(symbol), clean(name), day, clean(kind), parse_number(cash_raw), stock_ratio,
            "TPEx 上櫃除權除息計算結果表", source_url, "tpex-exdiv-history",
        ))
    return events'''
    text = replace_function(text, "parse_tpex_exdiv_history_payload", tpex_history_parser, "fetch_tpex_exdiv_history")

    tpex_history_fetch = r'''def fetch_tpex_exdiv_history(session: requests.Session) -> SourceResult:
    payload = http_json(session, TPEX_EXDIV_HISTORY_URL)
    rows = payload_dict_rows(payload)
    events = parse_tpex_exdiv_history_payload(payload)
    if not events and rows:
        parsed_days = []
        for row in rows:
            raw = first_value(row, [
                "ExRrightsExDividendDate", "ExRightsExDividendDate", "ExDate", "Date",
                "資料日期", "交易日期", "除權息日期", "除權除息日期", "除權息交易日",
            ]) or semantic_field(row, all_terms=("日期",), any_terms=("除權", "除息", "權息"))
            day = first_market_date(raw)
            if day:
                parsed_days.append(day)
        eligible = [day for day in parsed_days if ARCHIVE_START <= day <= NOW.date()]
        if eligible:
            raise RuntimeError(
                f"TPEx historical ex-dividend returned {len(rows)} rows and {len(eligible)} in-window dates but parser recognized 0 events"
            )
        message = (
            f"official endpoint returned {len(rows)} rows but none fall inside the verified archive window"
            if parsed_days else
            f"official endpoint returned {len(rows)} rows but no recognizable date field"
        )
    else:
        message = f"{len(events)} historical events since 2026-01-01" if events else "official endpoint returned no rows on this run"
    return SourceResult(
        "tpex-exdiv-history", "TPEx historical ex-right/ex-dividend", TPEX_EXDIV_HISTORY_URL,
        ("tpex-exdiv-history",), events, message,
    )'''
    text = replace_function(text, "fetch_tpex_exdiv_history", tpex_history_fetch, "dividend_total")

    text = text.replace(
        'shareholder_raw = first_value(row, ["股東會日期", "ShareholdersMeetingDate"]) or semantic_field(row, all_terms=("股東會",), any_terms=("日期", "date"))',
        'shareholder_raw = first_value(row, ["股東會日期", "ShareholdersMeetingDate"]) or semantic_field(row, all_terms=("股東會",), any_terms=("日期", "date"), exclude_terms=("配盈餘", "待彌補", "金額", "元"))'
    )
    text = text.replace(
        '"董事會決議日", "董事會日期",',
        '"董事會決議日", "董事會日期", "董事會決議通過股利分派日期",'
    )
    text = text.replace(
        'if "股利" not in text or "董事會" not in text or not re.search(r"決議|擬議|通過", text):',
        'if not re.search(r"股利|盈餘分派|盈餘分配|配息|配股", text) or "董事會" not in text or not re.search(r"決議|擬議|通過", text):'
    )

    path.write_text(text, encoding="utf-8")


def patch_tw_chips() -> None:
    path = ROOT / "scripts" / "update_tw_chips.py"
    text = path.read_text(encoding="utf-8")

    parser = r'''def parse_tpex_day_trade_market(rows: list[dict[str, Any]], fallback_date: str | None) -> tuple[dict[str, Any], str | None]:
    """Parse TPEx official market-aggregate day-trading statistics.

    This endpoint is market aggregate data, never per-security data.  Field
    matching intentionally accepts both current Chinese labels and documented
    English aliases, while the selected session must not exceed the verified
    market date.
    """
    candidates: list[tuple[str, dict[str, Any]]] = []
    ceiling = valid_chip_date(fallback_date)

    def market_value(row: dict[str, Any], aliases: tuple[str, ...], *, semantic_any: tuple[str, ...] = (), exclude: tuple[str, ...] = ()) -> tuple[str | None, Any]:
        key, raw = field_pair(row, *aliases)
        if raw is None and semantic_any:
            key, raw = semantic_pair(row, any_terms=semantic_any, exclude_terms=exclude)
        return key, raw

    def market_volume_lots(raw: Any, key: str | None) -> int | float | None:
        parsed = number(raw)
        if parsed is None:
            return None
        label = normalized_key(key or "")
        if any(token in label for token in ("仟股", "千股", "張")):
            return integer_or_float(parsed)
        return integer_or_float(parsed / 1000.0)

    for row in rows:
        explicit = valid_chip_date(row_date(row))
        traded = explicit or (ceiling if len(rows) == 1 else None)
        if not traded or (ceiling and traded > ceiling):
            continue

        volume_key, volume_raw = market_value(
            row,
            ("當日沖銷交易總成交股數", "當日沖銷交易成交股數", "現股當沖成交股數", "TotalIntradayTradingVolume", "IntradayTradingVolume"),
            semantic_any=("當沖成交股數", "沖銷成交股數", "intradaytradingvolume"),
            exclude=("比重", "比例", "ratio"),
        )
        _, buy_raw = market_value(
            row,
            ("當日沖銷交易總買進成交金額", "當日沖銷交易買進成交金額", "現股當沖買進成交金額", "TotalIntradayTradingBuyAmount", "IntradayTradingBuyAmount"),
            semantic_any=("當沖買進成交金額", "沖銷買進成交金額", "intradaytradingbuyamount"),
            exclude=("比重", "比例", "ratio"),
        )
        _, sell_raw = market_value(
            row,
            ("當日沖銷交易總賣出成交金額", "當日沖銷交易賣出成交金額", "現股當沖賣出成交金額", "TotalIntradayTradingSellAmount", "IntradayTradingSellAmount"),
            semantic_any=("當沖賣出成交金額", "沖銷賣出成交金額", "intradaytradingsellamount"),
            exclude=("比重", "比例", "ratio"),
        )
        _, ratio_raw = market_value(
            row,
            ("當日沖銷交易總成交股數占市場比重", "當日沖銷交易成交股數占市場比重", "當沖成交股數占市場比重", "IntradayTradingVolumeRatio", "VolumeRatio"),
            semantic_any=("成交股數占市場比重", "成交股數比重", "volumeratio"),
        )
        _, buy_ratio_raw = market_value(
            row,
            ("當日沖銷交易總買進成交金額占市場比重", "當日沖銷交易買進成交金額占市場比重", "IntradayTradingBuyAmountRatio"),
            semantic_any=("買進成交金額占市場比重", "buyamountratio"),
        )
        _, sell_ratio_raw = market_value(
            row,
            ("當日沖銷交易總賣出成交金額占市場比重", "當日沖銷交易賣出成交金額占市場比重", "IntradayTradingSellAmountRatio"),
            semantic_any=("賣出成交金額占市場比重", "sellamountratio"),
        )

        values = {
            "volume": market_volume_lots(volume_raw, volume_key),
            "buy_amount": number(buy_raw),
            "sell_amount": number(sell_raw),
            "volume_ratio_percent": number(ratio_raw),
            "buy_amount_ratio_percent": number(buy_ratio_raw),
            "sell_amount_ratio_percent": number(sell_ratio_raw),
        }
        values = {key: value for key, value in values.items() if value is not None}
        if values:
            candidates.append((traded, values))

    if not candidates:
        return {}, None
    traded, values = max(candidates, key=lambda item: item[0])
    return values, traded'''
    text = replace_function(text, "parse_tpex_day_trade_market", parser, "parse_institutional")
    text = text.replace(
        '"note": "官方資料優先；第三方只補缺漏。v11.4.36 正確解析民國日期，TPEx 當沖採官方市場彙總口徑，不偽造個股當沖資料。",',
        '"note": "官方資料優先；第三方只補缺漏。v11.4.36 強化 ROC/Gregorian 日期、TPEx 市場彙總當沖欄位與線上 schema gate，不偽造個股當沖資料。",'
    )
    path.write_text(text, encoding="utf-8")


def patch_cloudflare_workflow() -> None:
    path = ROOT / ".github" / "workflows" / "deploy-live-market-worker.yml"
    text = path.read_text(encoding="utf-8")
    old = '''      - name: Cloudflare not configured\n        if: env.CF_API_TOKEN == '' || env.CF_ACCOUNT_ID == '' || env.CF_KV_ID == ''\n        run: echo "Cloudflare secrets are not configured; skipping optional edge-worker deployment. GitHub Actions fallback remains active."'''
    new = '''      - name: Require Cloudflare deployment configuration\n        if: env.CF_API_TOKEN == '' || env.CF_ACCOUNT_ID == '' || env.CF_KV_ID == ''\n        run: |\n          echo "::error::Cloudflare deployment workflow was triggered, but CLOUDFLARE_API_TOKEN / CLOUDFLARE_ACCOUNT_ID / CLOUDFLARE_KV_NAMESPACE_ID is not fully configured."\n          exit 2'''
    if old not in text:
        raise RuntimeError("Cloudflare false-green block not found")
    path.write_text(text.replace(old, new), encoding="utf-8")


def add_live_gate() -> None:
    verifier = ROOT / "scripts" / "verify_v11_4_36_live_sources.py"
    verifier.write_text(r'''#!/usr/bin/env python3
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import requests
import update_events as ev
import update_tw_chips as chips


def fail(message: str) -> None:
    raise SystemExit(f"v11.4.36 live source gate failed: {message}")


def check_exdiv(session: requests.Session) -> None:
    payload = ev.http_json(session, ev.TPEX_EXDIV_HISTORY_URL)
    rows = ev.payload_dict_rows(payload)
    parsed = ev.parse_tpex_exdiv_history_payload(payload)
    eligible = 0
    for row in rows:
        raw = ev.first_value(row, [
            "ExRrightsExDividendDate", "ExRightsExDividendDate", "ExDate", "Date",
            "資料日期", "交易日期", "除權息日期", "除權除息日期", "除權息交易日",
        ]) or ev.semantic_field(row, all_terms=("日期",), any_terms=("除權", "除息", "權息"))
        day = ev.first_market_date(raw)
        if day and ev.ARCHIVE_START <= day <= ev.NOW.date():
            eligible += 1
    if rows and eligible and not parsed:
        fail(f"TPEx ex-dividend rows={len(rows)}, eligible={eligible}, parsed=0")
    print(f"TPEx ex-dividend gate: rows={len(rows)} eligible={eligible} parsed={len(parsed)}")


def check_dividend_plans(session: requests.Session) -> None:
    payload = ev.http_json(session, ev.TPEX_DIVIDEND_PLAN_URL)
    rows = ev.payload_dict_rows(payload)
    parsed = ev.parse_dividend_plans(payload, "TPEX", ev.TPEX_DIVIDEND_PLAN_URL, "tpex-dividend-plan")
    eligible = 0
    for row in rows:
        decision = ev.first_value(row, [
            "董事會決議通過股利分派日", "董事會通過股利分派日", "董事會決議通過股利分派日期",
            "董事會（擬議）股利分派日", "董事會(擬議)股利分派日", "董事會股利分派日",
            "董事會擬議日期", "董事會決議日期", "董事會決議日", "董事會日期",
            "現金股利經董事會決議、增資配股經董事會擬議日期",
            "BoardMeetingDate", "BoardDecisionDate",
        ])
        shareholder = ev.first_value(row, ["股東會日期", "ShareholdersMeetingDate"])
        for raw in (decision, shareholder):
            day = ev.first_market_date(raw)
            if day and ev.ARCHIVE_START <= day <= ev.NOW.date() + timedelta(days=370):
                eligible += 1
                break
    if rows and eligible and not parsed:
        fail(f"TPEx dividend-plan rows={len(rows)}, eligible={eligible}, parsed=0")
    print(f"TPEx dividend-plan gate: rows={len(rows)} eligible={eligible} parsed={len(parsed)}")


def check_day_trade() -> None:
    rows = chips.get_rows(chips.TPEX_DAY_TRADE)
    valid_dates = [chips.valid_chip_date(chips.row_date(row)) for row in rows]
    valid_dates = [value for value in valid_dates if value]
    ceiling = max(valid_dates) if valid_dates else chips.valid_chip_date(chips.NOW.date().isoformat())
    market, traded = chips.parse_tpex_day_trade_market(rows, ceiling)
    if rows and not market:
        fail(f"TPEx day-trading rows={len(rows)} parsed=0")
    if market and (not traded or (ceiling and traded > ceiling)):
        fail(f"TPEx day-trading invalid selected session traded={traded} ceiling={ceiling}")
    print(f"TPEx day-trading gate: rows={len(rows)} date={traded} fields={sorted(market)}")


def main() -> None:
    session = requests.Session()
    session.headers.update(ev.HEADERS)
    check_exdiv(session)
    check_dividend_plans(session)
    check_day_trade()
    print("v11.4.36 live source gate ok")


if __name__ == "__main__":
    main()
''', encoding="utf-8")

    workflow = ROOT / ".github" / "workflows" / "release-verification.yml"
    text = workflow.read_text(encoding="utf-8")
    marker = "      - name: Strict data validation\n"
    block = '''      - name: TPEx v11.4.36 live source contract gate\n        run: python scripts/verify_v11_4_36_live_sources.py\n'''
    if block not in text:
        if marker not in text:
            raise RuntimeError("release verification insertion point not found")
        text = text.replace(marker, block + marker)
    workflow.write_text(text, encoding="utf-8")


def add_contract_tests() -> None:
    test = ROOT / "tests" / "test_v11_4_36_contracts.py"
    test.write_text(r'''from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import update_events as ev
import update_tw_chips as chips


def test_market_date_non_zero_padded_gregorian_and_roc():
    assert ev.parse_market_date("2026/8/7").isoformat() == "2026-08-07"
    assert ev.parse_market_date("115/8/7").isoformat() == "2026-08-07"
    assert ev.parse_market_date("1150807").isoformat() == "2026-08-07"
    assert ev.parse_market_date("20260807").isoformat() == "2026-08-07"


def test_tpex_exdiv_documented_chinese_schema():
    payload = [{
        "除權息日期": "115/8/7",
        "代號": "1234",
        "名稱": "測試公司",
        "權或息": "息",
        "現金股利": "2.5",
        "每仟股無償配股": "0",
    }]
    rows = ev.parse_tpex_exdiv_history_payload(payload, "https://example.test/tpex")
    assert len(rows) == 1
    assert rows[0]["symbol"] == "1234"
    assert rows[0].get("cash_dividend") == 2.5


def test_tpex_dividend_plan_current_schema():
    payload = [{
        "公司代號": "1234",
        "公司名稱": "測試公司",
        "股利年度": "115",
        "期別": "年度",
        "董事會決議通過股利分派日": "115/2/25",
        "股東會日期配盈餘/待彌補虧損(元)": "999999999",
        "股東配發內容-盈餘分配之現金股利(元/股)": "3.0",
        "股東配發內容-盈餘轉增資配股(元/股)": "0.5",
    }]
    rows = ev.parse_dividend_plans(payload, "TPEX", "https://example.test/tpex", "tpex-dividend-plan")
    assert rows
    decision = next(row for row in rows if row["event_type"] == "dividend-decision")
    assert decision["local_date"] == "2026-02-25"
    assert decision.get("cash_dividend") == 3.0


def test_tpex_day_trade_market_aggregate_aliases():
    rows = [{
        "資料日期": "115/08/07",
        "當日沖銷交易成交股數": "1,500,000",
        "當日沖銷交易買進成交金額": "123456789",
        "當日沖銷交易賣出成交金額": "123400000",
        "當日沖銷交易成交股數占市場比重": "18.5",
    }]
    market, traded = chips.parse_tpex_day_trade_market(rows, "2026-08-07")
    assert traded == "2026-08-07"
    assert market["volume"] == 1500
    assert market["buy_amount"] == 123456789
    assert "symbol" not in market
''', encoding="utf-8")


def bump_versions() -> None:
    allowed = {".py", ".js", ".html", ".css", ".yml", ".yaml", ".json", ".md", ".txt", ".sh"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or path.suffix.lower() not in allowed:
            continue
        if path.name == "V11.4.36-release-audit.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        changed = text.replace("v11.4.36", "v11.4.36").replace("11.4.36", "11.4.36").replace("v11-4-36", "v11-4-36")
        if changed != text:
            path.write_text(changed, encoding="utf-8")

    version_path = ROOT / "VERSION.json"
    data = json.loads(version_path.read_text(encoding="utf-8"))
    data["version"] = NEW_VERSION
    data["baseline_version"] = "11.4.36"
    data["name"] = "tpex-live-contracts-cloudflare-release-gate"
    version_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cleanup_audio() -> None:
    for suffix in ("*.m4a", "*.mp3", "*.wav"):
        for path in ROOT.rglob(suffix):
            if ".git" not in path.parts:
                path.unlink()


def main() -> None:
    patch_update_events()
    patch_tw_chips()
    patch_cloudflare_workflow()
    add_live_gate()
    add_contract_tests()
    bump_versions()
    cleanup_audio()
    print("Applied Market Event Radar v11.4.36 integration patch.")
    print("Next: python -m compileall -q scripts tests && python -m pytest -q")


if __name__ == "__main__":
    main()
