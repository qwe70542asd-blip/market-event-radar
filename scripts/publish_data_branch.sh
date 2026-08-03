#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:?branch required}"
CHANNEL="${2:?channel name required}"
shift 2
FILES=("$@")

if [[ ${#FILES[@]} -eq 0 ]]; then
  echo "No files supplied for ${BRANCH}"
  exit 1
fi

REMOTE="https://x-access-token:${GH_TOKEN:?GH_TOKEN required}@github.com/${GITHUB_REPOSITORY:?GITHUB_REPOSITORY required}.git"
WORK="/tmp/market-radar-${BRANCH}"

for attempt in 1 2 3 4; do
  rm -rf "$WORK"
  mkdir -p "$WORK"
  cd "$WORK"
  git init -q
  git config user.name "market-event-radar-bot"
  git config user.email "actions@users.noreply.github.com"
  git remote add origin "$REMOTE"

  if timeout 45s git ls-remote --exit-code --heads origin "$BRANCH" >/dev/null 2>&1; then
    timeout 90s git fetch --depth=1 origin "$BRANCH"
    git checkout -q -B "$BRANCH" FETCH_HEAD
  else
    git checkout -q --orphan "$BRANCH"
  fi

  copied=()
  for source in "${FILES[@]}"; do
    source_path="${GITHUB_WORKSPACE}/${source}"
    if [[ ! -f "$source_path" ]]; then
      echo "Missing publish file: $source"
      exit 1
    fi
    destination="$(basename "$source")"
    cp "$source_path" "$destination"
    copied+=("$destination")
  done

  python - "$BRANCH" "$CHANNEL" "${copied[@]}" <<'PY'
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

branch, channel, *files = sys.argv[1:]
entries = []
payload_times = []
for name in files:
    path = Path(name)
    data = path.read_bytes()
    row = {
        "name": name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    if name.endswith(".json"):
        try:
            payload = json.loads(data.decode("utf-8"))
            metadata = payload.get("metadata") or {}
            row["records"] = max(
                [len(payload.get(key) or []) for key in ("assets","events","items","announcements","daily","financials")]
                + [int((payload.get("summary") or {}).get("total_stocks") or 0)]
            )
            row["payload_updated_at"] = metadata.get("updated_at") or payload.get("updated_at")
            if row["payload_updated_at"]:
                payload_times.append(row["payload_updated_at"])
        except Exception:
            row["records"] = None
    entries.append(row)

manifest = {
    "version": "v11.2.8",
    "channel": channel,
    "branch": branch,
    "published_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "payload_updated_at": max(payload_times) if payload_times else None,
    "repository": os.environ.get("GITHUB_REPOSITORY"),
    "workflow": os.environ.get("GITHUB_WORKFLOW"),
    "run_id": os.environ.get("GITHUB_RUN_ID"),
    "run_number": os.environ.get("GITHUB_RUN_NUMBER"),
    "commit_sha": os.environ.get("GITHUB_SHA"),
    "files": entries,
}
Path("channel.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

  git add "${copied[@]}" channel.json
  if git diff --cached --quiet; then
    echo "${BRANCH}: no data changes"
    exit 0
  fi

  git commit -q -m "chore: refresh ${CHANNEL} v11.2.8"
  if timeout 90s git push origin "HEAD:${BRANCH}"; then
    echo "${BRANCH}: publish complete"
    exit 0
  fi

  echo "${BRANCH}: push conflict, retry ${attempt}/4"
  sleep $((attempt * 5))
done

echo "${BRANCH}: unable to publish after retries"
exit 1
