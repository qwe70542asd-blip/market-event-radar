#!/usr/bin/env python3
"""Fail if more than one workflow can publish the same live-* branch."""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def publisher_branches(text: str) -> set[str]:
    branches = set(re.findall(r"publish_data_branch\.sh\s+(live-[a-z0-9-]+)", text))
    branches.update(re.findall(r"branch:\s*(live-[a-z0-9-]+)", text))
    return branches


def main() -> int:
    publishers: dict[str, list[str]] = defaultdict(list)
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for branch in publisher_branches(text):
            publishers[branch].append(path.name)
    conflicts = {branch: names for branch, names in publishers.items() if len(names) > 1}
    if conflicts:
        print("duplicate live-branch publishers detected:")
        for branch, names in sorted(conflicts.items()):
            print(f" - {branch}: {', '.join(names)}")
        return 2
    print(f"workflow publisher audit ok: {len(publishers)} live branches, one writer each")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
