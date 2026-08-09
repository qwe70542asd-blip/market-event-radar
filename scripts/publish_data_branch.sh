#!/usr/bin/env bash
set -euo pipefail
branch="$1"; shift
label="$1"; shift
repo_root="$PWD"
tmp="$(mktemp -d)"
rmdir "$tmp"
trap 'git -C "$repo_root" worktree remove --force "$tmp" >/dev/null 2>&1 || true; rm -rf "$tmp"' EXIT

git worktree add --detach "$tmp" >/dev/null
cd "$tmp"
# Always publish a history-free snapshot.  restore_data_branch.sh creates local
# refs for live-* branches; using the destination name with checkout --orphan
# therefore fell back to the existing branch in v11.4.30 and accumulated a new
# multi-megabyte commit every refresh.
tmp_branch="__publish_${branch//[^A-Za-z0-9]/_}_${GITHUB_RUN_ID:-$$}_${GITHUB_RUN_ATTEMPT:-0}"
git switch --orphan "$tmp_branch" >/dev/null 2>&1
git rm -rf . >/dev/null 2>&1 || true
for src in "$@"; do
  test -f "$repo_root/$src" || { echo "missing publish source: $src" >&2; exit 2; }
  cp "$repo_root/$src" "$(basename "$src")"
done
printf '{"version":"v11.4.33","channel":"%s","label":"%s","snapshot_history":"orphan"}\n' "$branch" "$label" > channel.json
git add .
git -c user.name='market-radar-bot' -c user.email='actions@users.noreply.github.com' commit -m "chore: publish $label snapshot" >/dev/null
git push origin "HEAD:refs/heads/$branch" --force
