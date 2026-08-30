#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from typing import Any

from common import DATA, NOW, VERSION, read_json, write_payload

# This file is intentionally a compact metadata index.  The browser health page
# reads this single payload instead of downloading every multi-megabyte channel.
SPECS: list[tuple[str, str, int]] = [
    ("assets.json", "標的與財報", 36 * 3600),
    ("asset-audit.json", "標的稽核", 36 * 3600),
    ("tw-market.json", "台股行情", 3 * 3600),
    ("tw-chips.json", "法人籌碼", 72 * 3600),
    ("market-snapshot.json", "全球行情", 20 * 60),
    ("market-kline.json", "全球 K 線", 2 * 3600),
    ("events.json", "事件月曆", 12 * 3600),
    ("monthly-revenue.json", "月營收歷史", 18 * 3600),
    ("dividend-history.json", "股利歷史", 18 * 3600),
    ("stock-basics.json", "公司基本資料", 36 * 3600),
    ("secondary-reference.json", "股票網站參考行情", 36 * 3600),
    ("yahoo-details.json", "Yahoo 詳細資料補充", 96 * 3600),
    ("etf-details.json", "ETF 多來源資料補充", 72 * 3600),
    ("stock-news.json", "個股媒體新聞", 3 * 3600),
    ("news-cna.json", "中央社", 3 * 3600),
    ("news-moneydj.json", "MoneyDJ", 3 * 3600),
    ("news-cnyes.json", "鉅亨網", 3 * 3600),
    ("news-udn.json", "經濟日報", 3 * 3600),
    ("news-ltn.json", "自由財經", 3 * 3600),
    ("news-wealth.json", "財富自由", 3 * 3600),
    ("news-yahoo.json", "Yahoo股市", 3 * 3600),
    ("news-technews.json", "科技新報／財經新報", 3 * 3600),
    ("news-ctee.json", "工商時報", 3 * 3600),
    ("news-asia-risk.json", "亞洲總體風險", 3 * 3600),
    ("official-market-notices.json", "官方市場公告", 12 * 3600),
    ("company-disclosures.json", "個股重大訊息", 12 * 3600),
    ("data-verification.json", "資料交叉驗證", 3 * 3600),
]

BAD = {"failed", "error", "unavailable", "circuit-open"}
PARTIAL = {"warning", "partial", "fallback", "degraded"}
PENDING = {"loading", "waiting", "pending", "seed", "seeded", "unknown", ""}


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=NOW.tzinfo)
        return parsed.astimezone(NOW.tzinfo)
    except Exception:
        return None


def cardinality(payload: dict[str, Any]) -> int:
    items = payload.get("items")
    if isinstance(items, (list, dict)):
        return len(items)
    assets = payload.get("assets")
    if isinstance(assets, list):
        return len(assets)
    events = payload.get("events")
    if isinstance(events, list):
        return len(events)
    return 0


def nested_statuses(payload: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for source in payload.get("sources") or []:
        if isinstance(source, dict):
            status = str(source.get("status") or "").strip().lower()
            if status:
                result.append(status)
    return result


def item_staleness(payload: dict[str, Any], max_age_seconds: int) -> tuple[int, int, list[str]]:
    items = payload.get("items")
    if not isinstance(items, dict) or len(items) > 5000:
        return 0, 0, []
    cutoff = NOW.timestamp() - max_age_seconds
    checked = stale = 0
    samples: list[str] = []
    for key, row in items.items():
        if not isinstance(row, dict):
            continue
        stamp = parse_time(row.get("updated_at") or row.get("source_updated_at"))
        if stamp is None:
            continue
        checked += 1
        if stamp.timestamp() < cutoff:
            stale += 1
            if len(samples) < 5:
                samples.append(str(key))
    return checked, stale, samples


def chip_date_mismatch(payload: dict[str, Any]) -> list[str]:
    metadata = payload.get("metadata") or {}
    trading = str(metadata.get("trading_date") or "")
    if not trading:
        return []
    mismatches: list[str] = []
    for market_name, market in (payload.get("markets") or {}).items():
        if not isinstance(market, dict):
            continue
        for field in ("institutional_date", "institutional_amount_date", "day_trading_date"):
            value = str(market.get(field) or "")
            if value and value != trading:
                mismatches.append(f"{market_name}.{field}={value}")
    return mismatches[:8]


def classify(file: str, payload: dict[str, Any], max_age_seconds: int) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload, dict) else {}
    metadata = metadata if isinstance(metadata, dict) else {}
    updated = parse_time(metadata.get("updated_at"))
    age_seconds = max(0, int((NOW - updated).total_seconds())) if updated else None
    stale = updated is None or age_seconds > max_age_seconds
    raw = str(metadata.get("status") or "").strip().lower()
    reasons: list[str] = []
    if not payload:
        status = "unavailable"
        reasons.append("channel file missing")
    elif raw in BAD:
        status = "failed"
        reasons.append(raw)
    elif raw in PENDING:
        status = "pending"
        reasons.append(raw or "missing status")
    elif raw == "stale" or stale:
        status = "stale"
        reasons.append("updated_at exceeded max age" if stale else "source marked stale")
    elif raw in PARTIAL:
        status = "degraded" if raw == "degraded" else "partial"
        reasons.append(raw)
    else:
        status = "fresh"

    child = nested_statuses(payload)
    bad_children = [value for value in child if value in BAD | PARTIAL | {"stale"}]
    if bad_children and status == "fresh":
        status = "partial"
        reasons.append(f"nested sources: {', '.join(sorted(set(bad_children)))}")

    if file == "dividend-history.json" and str(metadata.get("mops_status") or "") == "circuit-open":
        status = "degraded"
        reasons.append("MOPS circuit-open")

    if file == "tw-chips.json":
        mismatch = chip_date_mismatch(payload)
        if mismatch:
            if status == "fresh":
                status = "partial"
            reasons.append("mixed component dates")
        else:
            mismatch = []
    else:
        mismatch = []

    checked, stale_items, samples = (0, 0, [])
    if file in {"etf-details.json", "yahoo-details.json"}:
        checked, stale_items, samples = item_staleness(payload, max_age_seconds)
        if stale_items:
            ratio = stale_items / checked if checked else 0
            if status == "fresh":
                status = "degraded" if ratio >= 0.2 else "partial"
            reasons.append(f"stale items {stale_items}/{checked}")

    errors = payload.get("errors") if isinstance(payload, dict) else None
    error_count = len(errors) if isinstance(errors, list) else 0
    if error_count and status == "fresh":
        status = "partial"
        reasons.append(f"errors={error_count}")

    return {
        "file": file,
        "status": status,
        "source_status": raw or None,
        "version": metadata.get("version"),
        "updated_at": metadata.get("updated_at"),
        "age_seconds": age_seconds,
        "max_age_seconds": max_age_seconds,
        "stale": stale,
        "item_count": cardinality(payload),
        "error_count": error_count,
        "nested_degraded_count": len(bad_children),
        "item_timestamp_checked": checked,
        "stale_item_count": stale_items,
        "stale_item_samples": samples,
        "date_mismatch_samples": mismatch,
        "reasons": reasons[:6],
    }


def main() -> None:
    channels: list[dict[str, Any]] = []
    for file, label, max_age_seconds in SPECS:
        payload = read_json(DATA / file, {})
        row = classify(file, payload, max_age_seconds)
        row["label"] = label
        channels.append(row)

    counts = {key: 0 for key in ("fresh", "partial", "degraded", "stale", "pending", "failed", "unavailable")}
    for row in channels:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    bad_count = sum(counts.get(key, 0) for key in ("partial", "degraded", "stale", "failed", "unavailable"))
    overall = "fresh" if bad_count == 0 and counts.get("pending", 0) == 0 else "degraded" if counts.get("failed", 0) or counts.get("unavailable", 0) else "partial"
    verification = read_json(DATA / "data-verification.json", {})
    verification_meta = verification.get("metadata") if isinstance(verification, dict) else {}
    verification_meta = verification_meta if isinstance(verification_meta, dict) else {}
    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": overall,
            "channel_count": len(channels),
            "counts": counts,
            "bad_count": bad_count,
            "payload_mode": "metadata-only",
            "retention_note": "Health page consumes this compact index and never downloads every full historical channel.",
            "verification_summary": {
                "status": verification_meta.get("status"),
                "updated_at": verification_meta.get("updated_at"),
                "trust_counts": verification_meta.get("trust_counts") or verification_meta.get("counts") or {},
                "completeness_counts": verification_meta.get("completeness_counts") or {},
                "average_field_coverage_percent": verification_meta.get("average_field_coverage_percent"),
                "conflict_ratio_percent": verification_meta.get("conflict_ratio_percent"),
                "partial_ratio_percent": verification_meta.get("partial_ratio_percent"),
            },
        },
        "channels": channels,
    }
    write_payload("channel-health.json", "__CHANNEL_HEALTH_SEED__", payload)
    print(payload["metadata"])


if __name__ == "__main__":
    main()
