#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:?branch required}"
shift

if ! git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
  echo "${BRANCH}: branch not created yet; using main-branch seed files"
  exit 0
fi

git fetch --depth=1 origin "$BRANCH"
for pair in "$@"; do
  source_name="${pair%%:*}"
  destination="${pair#*:}"
  if git cat-file -e "FETCH_HEAD:${source_name}" 2>/dev/null; then
    mkdir -p "$(dirname "$destination")"
    git show "FETCH_HEAD:${source_name}" > "$destination"
    echo "${BRANCH}: restored ${source_name} -> ${destination}"
  fi
done
