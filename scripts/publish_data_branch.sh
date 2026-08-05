#!/usr/bin/env bash
set -euo pipefail
branch="$1"; shift
label="$1"; shift
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
git worktree add --detach "$tmp" >/dev/null
cd "$tmp"
git checkout --orphan "$branch" 2>/dev/null || git checkout "$branch"
git rm -rf . >/dev/null 2>&1 || true
for src in "$@"; do cp "$OLDPWD/$src" "$(basename "$src")"; done
printf '{"version":"v11.4.12","channel":"%s","label":"%s"}\n' "$branch" "$label" > channel.json
git add .
git -c user.name='market-radar-bot' -c user.email='actions@users.noreply.github.com' commit -m "chore: publish $label" >/dev/null || true
git push origin "HEAD:$branch" --force
