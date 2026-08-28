#!/usr/bin/env python3
"""HTTP-level release smoke test for the GitHub Pages/App shell.

Run after starting a static server, for example:
  python -m http.server 8765 &
  python scripts/http_smoke.py http://127.0.0.1:8765
"""
from __future__ import annotations

import sys
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765").rstrip("/") + "/"
PAGES = ["index.html", "portfolio.html", "tw-market.html", "asset.html?symbol=2330", "news.html", "institutional.html", "event.html"]
REQUIRED = {
    "index.html": ["v11.4.54", "今日台股狀態", "六大指數互動 K 線與關鍵資訊"],
    "tw-market.html": ["台股四大排行", "搜尋全部股票與 ETF"],
    "news.html": ["財經新聞"],
    "asset.html?symbol=2330": ["標的詳情"],
}


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        value = values.get("src") if tag in {"script", "img"} else values.get("href") if tag == "link" else None
        if value and not value.startswith(("http://", "https://", "data:", "#")):
            self.urls.add(value)


def get(path: str) -> tuple[int, str, str]:
    url = urljoin(BASE, path)
    request = Request(url, headers={"User-Agent": "MarketEventRadarReleaseSmoke/11.4.54"})
    with urlopen(request, timeout=12) as response:
        return response.status, response.headers.get("Content-Type", ""), response.read().decode("utf-8", errors="replace")


def main() -> None:
    assets: set[str] = set()
    for page in PAGES:
        status, content_type, body = get(page)
        assert status == 200, (page, status)
        assert "text/html" in content_type, (page, content_type)
        assert "v11.4.54" in body, page
        for token in REQUIRED.get(page, []):
            assert token in body, (page, token)
        parser = AssetParser(); parser.feed(body); assets.update(parser.urls)
    for raw in sorted(assets):
        parsed = urlparse(raw)
        path = parsed.path.lstrip("./")
        if not path or path.endswith("/"):
            continue
        status, _, _ = get(path)
        assert status == 200, (raw, status)
    expected_seed_markers = {
        "data/market-snapshot-seed.js": "window.__MARKET_SNAPSHOT_SEED__",
        "data/market-kline-seed.js": "window.__MARKET_KLINE_SEED__",
        "data/events-seed.js": "window.__EVENT_SEED__",
        "data/stock-basics-seed.js": "window.__STOCK_BASICS_SEED__",
    }
    for path, marker in expected_seed_markers.items():
        status, _, body = get(path)
        assert status == 200 and marker in body, (path, marker)
    print(f"HTTP smoke passed: {len(PAGES)} pages, {len(assets)} referenced assets")


if __name__ == "__main__":
    main()
