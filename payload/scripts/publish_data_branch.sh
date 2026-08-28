#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "usage: $0 <branch> <label> <source> [source ...]" >&2
  exit 2
fi

branch="$1"; shift
label="$1"; shift
repo_root="$PWD"
tmp="$(mktemp -d)"
rmdir "$tmp"

cleanup() {
  git -C "$repo_root" worktree remove --force "$tmp" >/dev/null 2>&1 || true
  rm -rf "$tmp"
}
trap cleanup EXIT

git worktree add --detach "$tmp" >/dev/null
cd "$tmp"

tmp_branch="__publish_${branch//[^A-Za-z0-9]/_}_${GITHUB_RUN_ID:-$$}_${GITHUB_RUN_ATTEMPT:-0}"
git switch --orphan "$tmp_branch" >/dev/null 2>&1
git rm -rf . >/dev/null 2>&1 || true

for src in "$@"; do
  test -f "$repo_root/$src" || { echo "missing publish source: $src" >&2; exit 2; }
  cp "$repo_root/$src" "$(basename "$src")"
done

version="$(
  python - "$repo_root/VERSION.json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
value = json.loads(path.read_text(encoding="utf-8")).get("version")
if not isinstance(value, str) or not value.startswith("v"):
    raise SystemExit("VERSION.json does not contain a valid version")
print(value)
PY
)"

printf '{"version":"%s","channel":"%s","label":"%s","snapshot_history":"orphan"}\n' \
  "$version" "$branch" "$label" > channel.json

git add .
git -c user.name='market-radar-bot' \
    -c user.email='actions@users.noreply.github.com' \
    commit -m "chore: publish $label snapshot" >/dev/null

test -n "${GH_TOKEN:-}" || { echo "GH_TOKEN is required for publication" >&2; exit 2; }
auth="$(printf 'x-access-token:%s' "$GH_TOKEN" | base64 | tr -d '\n')"
git -c http.https://github.com/.extraheader="AUTHORIZATION: basic $auth" \
  push origin "HEAD:refs/heads/$branch" --force
unset auth
