#!/usr/bin/env bash
set -euo pipefail
branch="$1"; shift
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
if ! git fetch origin "$branch:$branch" --force >/dev/null 2>&1; then exit 0; fi
for pair in "$@"; do src="${pair%%:*}"; dst="${pair#*:}"; mkdir -p "$(dirname "$dst")"; git show "$branch:$src" > "$dst" 2>/dev/null || true; done
