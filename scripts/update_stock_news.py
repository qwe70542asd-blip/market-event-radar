#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher

from common import DATA, NOW, read_json
from news_pipeline import (
    VERSION,
    asset_aliases,
    asset_profiles,
    clean_text,
    infer_symbols,
    parse_datetime,
    readable_chinese,
    keep_in_archive,
    archive_priority,
    ARCHIVE_START,
)

PRIORITY = {
    "cna": 100,
    "wealth": 96,
    "moneydj": 92,
    "cnyes": 90,
    "udn": 88,
    "ltn": 86,
    "yahoo": 84,
    "technews": 82,
    "ctee": 80,
    "asia-risk": 78,
}
STOP = set("台股 公司 今日 最新 表示 指出 宣布 公布 市場 今年 去年 可能 相關 產業 股票 新聞 再創 投資 財經".split())


def words(title: object) -> list[str]:
    values = re.findall(r"[0-9A-Za-z]+|[\u3400-\u9fff]{2,}", clean_text(title).lower())
    return [value for value in values if value not in STOP]


def similar(left: dict, right: dict) -> bool:
    if set(left.get("symbols") or []) != set(right.get("symbols") or []):
        return False
    left_words, right_words = words(left.get("title")), words(right.get("title"))
    left_text, right_text = "".join(left_words), "".join(right_words)
    if not left_text or not right_text:
        return False
    shared = len(set(left_words) & set(right_words))
    return SequenceMatcher(None, left_text, right_text).ratio() >= 0.68 or shared >= 3


def quality(item: dict) -> float:
    return (
        PRIORITY.get(str(item.get("source_id") or ""), 50)
        + (20 if item.get("image_url") else 0)
        + min(len(clean_text(item.get("summary"))), 250) / 25
    )


def main() -> None:
    config = read_json(DATA / "news-channels.json", {"media": []})
    profiles = asset_profiles()
    aliases = asset_aliases()
    candidates: list[dict] = []
    sources: list[dict] = []

    for channel in config.get("media", []):
        payload = read_json(DATA / channel["file"], {"metadata": {}, "items": []})
        matched = 0
        for original in payload.get("items", []):
            title = clean_text(original.get("title"))
            summary = clean_text(original.get("ai_summary") or original.get("summary"))
            published = parse_datetime(original.get("published_at"))
            candidate_for_archive={**original,"title":title,"summary":summary or title,"ai_summary":summary or title}
            if not published or not keep_in_archive(candidate_for_archive,published) or not readable_chinese(title, summary):
                continue
            # Re-run symbol inference against the full current master.  Do not
            # trust a sparse upstream seed's symbol list: it can both miss the
            # headline company and preserve numeric false positives.
            symbols = [symbol for symbol in infer_symbols(f"{title} {summary}", aliases) if symbol in profiles]
            symbols = list(dict.fromkeys(symbols))
            if not symbols:
                continue
            matched += 1
            candidates.append(
                {
                    **original,
                    "title": title,
                    "summary": summary or title,
                    "ai_summary": summary or title,
                    "symbols": symbols,
                    "companies": [profiles[symbol] for symbol in symbols],
                    "affected_markets": symbols[:5],
                    "why_it_matters": f"此資訊主要影響{'、'.join(symbols[:3])}，仍需配合正式數據與市場預期判斷。",
                    "is_stock_news": True,
                    "scope": "stock",
                    "company_announcement": False,
                    "language": "zh-Hant",
                }
            )
        sources.append(
            {
                "id": channel["id"],
                "name": channel["name"],
                "status": payload.get("metadata", {}).get("status", "waiting"),
                "matched": matched,
                "total": len(payload.get("items", [])),
            }
        )

    unique: dict[str, dict] = {}
    for item in candidates:
        key = str(item.get("url") or item.get("id") or f"{item.get('source_id')}|{item.get('title')}")
        if key not in unique or quality(item) > quality(unique[key]):
            unique[key] = item
    candidates = sorted(unique.values(), key=lambda row: str(row.get("published_at") or ""), reverse=True)
    groups: list[list[dict]] = []
    for item in candidates:
        target = next((group for group in groups if similar(item, group[0])), None)
        if target is None:
            groups.append([item])
        else:
            target.append(item)

    output: list[dict] = []
    for group in groups:
        ranked = sorted(group, key=quality, reverse=True)
        primary = dict(ranked[0])
        primary["other_reports"] = [
            {
                "source": item.get("source"),
                "source_id": item.get("source_id"),
                "title": item.get("title"),
                "url": item.get("url"),
                "published_at": item.get("published_at"),
            }
            for item in ranked[1:6]
        ]
        primary["report_count"] = len(ranked)
        primary["verification_status"] = "multi-source" if len(ranked) > 1 else "primary-media" if primary.get("source_id") == "cna" else "reference"
        primary["verification_sources"] = [item.get("source") for item in ranked if item.get("source")]
        output.append(primary)

    output.sort(key=lambda row: (str(row.get("published_at") or ""), archive_priority(row,parse_datetime(row.get("published_at")) or ARCHIVE_START)), reverse=True)
    output = output[:600]
    old = read_json(DATA / "stock-news.json", {"items": []})
    fallback = False
    if not output and old.get("items"):
        output = [row for row in old["items"] if (lambda dt: bool(dt and keep_in_archive(row, dt)))(parse_datetime(row.get("published_at") or row.get("date")))]
        output.sort(key=lambda row: str(row.get("published_at") or row.get("date") or ""), reverse=True)
        fallback = bool(output)

    payload = {
        "metadata": {
            "version": VERSION,
            "updated_at": NOW.isoformat(timespec="seconds"),
            "status": "ok" if output and not fallback else "fallback" if output else "warning",
            "item_count": len(output),
            "source_count": len(sources),
            "used_archive_fallback": fallback,
            "archive_start": ARCHIVE_START.date().isoformat(),
            "sort_order": "published_at_desc",
            "note": "繁體中文媒體個股新聞；近期完整保留，較舊資料只保留高重要度內容，2026-01-01 前自動刪除。",
        },
        "sources": sources,
        "items": output,
    }
    (DATA / "stock-news.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (DATA / "stock-news-seed.js").write_text(
        "window.__STOCK_NEWS_SEED__="
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )
    print(payload["metadata"])


if __name__ == "__main__":
    main()
