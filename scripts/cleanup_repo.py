#!/usr/bin/env python3
"""Keep the repository layout aligned with the current release.

This script is deliberately version-aware.  It removes stale version-specific
regression suites/verifiers/manifests left behind by overlay updates, redundant
workflow publishers that target the same live branches, and accidental nested
repository copies under ./scripts.

Use --check in CI to fail closed without deleting anything.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
VERSION_INFO = json.loads((ROOT / "VERSION.json").read_text(encoding="utf-8"))
VERSION = str(VERSION_INFO["version"])
VERSION_DOTS = VERSION.removeprefix("v")
VERSION_UNDERSCORE = VERSION_DOTS.replace(".", "_")

NESTED_DIRS = [".github", "assets", "data", "docs", "tests", "scripts", "edge"]
MIRRORED_FILES = [
    ".gitignore", ".nojekyll", "404.html", "asset.html", "data-status.html",
    "event.html", "index.html", "institutional.html", "news.html", "portfolio.html",
    "tw-market.html", "README.md", "GITHUB-DESKTOP-UPDATE.txt", "VALIDATION.json",
    "VALIDATION.txt", "VERSION.json", "manifest.webmanifest", "service-worker.js",
    "requirements.txt", "CLEAN-REPO.cmd",
]

# v11.4.44 has one authoritative writer for every live branch.  These former
# standalone publishers duplicated aggregate workflows and could force-push the
# same branch under a different concurrency group.
REDUNDANT_WORKFLOWS = [
    "update-company-disclosures.yml",
    "update-global-market.yml",
    "update-news-asia-risk.yml",
    "update-news-cna.yml",
    "update-news-cnyes.yml",
    "update-news-ctee.yml",
    "update-news-ltn.yml",
    "update-news-moneydj.yml",
    "update-news-technews.yml",
    "update-news-udn.yml",
    "update-news-wealth.yml",
    "update-news-yahoo.yml",
    "update-official-notices.yml",
    "update-stock-news.yml",
    "update-tw-market.yml",
]


def version_obsolete_paths() -> list[Path]:
    found: list[Path] = []
    current_test_prefix = f"test_v{VERSION_UNDERSCORE}_"
    for path in (ROOT / "tests").glob("test_v*_*.py"):
        if not path.name.startswith(current_test_prefix):
            found.append(path)
    current_verifier = f"verify_v{VERSION_UNDERSCORE}_live_sources.py"
    for path in SCRIPTS.glob("verify_v*_live_sources.py"):
        if path.name != current_verifier:
            found.append(path)
    current_manifest = f"DELETION-MANIFEST-{VERSION}.txt"
    for path in ROOT.glob("DELETION-MANIFEST-v*.txt"):
        if path.name != current_manifest:
            found.append(path)
    found.extend(ROOT.glob("apply_v*.py"))
    found.extend((ROOT / ".github" / "workflows" / name) for name in REDUNDANT_WORKFLOWS)
    return found


def offenders() -> list[Path]:
    values = [SCRIPTS / name for name in NESTED_DIRS + MIRRORED_FILES]
    values.extend(version_obsolete_paths())
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in values:
        if path.exists() and path not in seen:
            seen.add(path)
            unique.append(path)
    return sorted(unique, key=lambda p: str(p.relative_to(ROOT)).lower())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="report stale/conflicting files and exit non-zero")
    args = parser.parse_args()
    found = offenders()
    if not found:
        print(f"repository layout clean for {VERSION}")
        return 0
    if args.check:
        print(f"stale/conflicting repository files detected for {VERSION}:")
        for path in found:
            print(" -", path.relative_to(ROOT))
        return 2
    for path in found:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        print("removed", path.relative_to(ROOT))
    print(f"repository cleanup complete for {VERSION}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
