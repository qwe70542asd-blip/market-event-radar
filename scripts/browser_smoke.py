#!/usr/bin/env python3
"""Real-browser release smoke for the homepage runtime.

The test intentionally blocks external HTTPS requests so the bundled seeds are
exercised. A JavaScript ReferenceError must fail the release even when HTTP and
syntax-only checks are green.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765").rstrip("/")


def main() -> int:
    errors: list[str] = []
    with sync_playwright() as pw:
        system_chromium = Path("/usr/bin/chromium") if os.environ.get("MARKET_RADAR_SYSTEM_CHROMIUM") == "1" else None
        browser = pw.chromium.launch(
            headless=True,
            executable_path=str(system_chromium) if system_chromium and system_chromium.exists() else None,
        )
        page = browser.new_page()
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        # Force deterministic local-seed fallback and avoid depending on GitHub,
        # CDNs or the optional edge worker during release verification.
        page.route("https://**/*", lambda route: route.abort())
        page.goto(f"{BASE}/index.html", wait_until="domcontentloaded", timeout=20_000)
        page.wait_for_function(
            "document.querySelectorAll('#calendarGrid > *').length === 42",
            timeout=15_000,
        )
        title = page.locator("#calendarTitle").inner_text().strip()
        cells = page.locator("#calendarGrid > *").count()
        page.locator('[data-calendar-mode="dividend"]').click()
        page.locator('[data-calendar-mode="market"]').click()
        if title in {"", "—"}:
            errors.append("calendar title did not initialize")
        if cells != 42:
            errors.append(f"calendar cell count {cells} != 42")
        browser.close()
    if errors:
        raise SystemExit("browser smoke failed: " + " | ".join(errors))
    print("browser smoke ok: homepage initialized with 42 calendar cells and no pageerror")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
