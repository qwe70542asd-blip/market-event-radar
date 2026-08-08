#!/usr/bin/env python3
"""Remove an accidentally nested copy of the repository from ./scripts.

Only paths that can never be legitimate updater code are touched.  Use --check
in CI to fail closed without deleting anything.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
NESTED_DIRS = [".github", "assets", "data", "docs", "tests", "scripts", "edge"]
MIRRORED_FILES = [
    ".gitignore", ".nojekyll", "404.html", "asset.html", "data-status.html",
    "event.html", "index.html", "institutional.html", "news.html", "portfolio.html",
    "tw-market.html", "README.md", "GITHUB-DESKTOP-UPDATE.txt", "VALIDATION.json",
    "VALIDATION.txt", "VERSION.json", "manifest.webmanifest", "service-worker.js",
    "requirements.txt", "CLEAN-REPO.cmd",
]


def offenders() -> list[Path]:
    values = [SCRIPTS / name for name in NESTED_DIRS + MIRRORED_FILES]
    return [path for path in values if path.exists()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report nested copies and exit non-zero")
    args = parser.parse_args()
    found = offenders()
    if not found:
        print("repository layout clean")
        return 0
    if args.check:
        print("nested repository copy detected:")
        for path in found:
            print(" -", path.relative_to(ROOT))
        return 2
    for path in found:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print("removed", path.relative_to(ROOT))
    print("nested repository cleanup complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
