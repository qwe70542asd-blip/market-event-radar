#!/usr/bin/env bash
set -u

ROOT="${GITHUB_WORKSPACE:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"
mkdir -p /tmp/market-radar-assets-backup data

backup_files=(data/assets.json data/assets-seed.js data/asset-coverage.json data/asset-audit.json data/asset-audit-seed.js data/asset-audit-failures.csv)
for file in "${backup_files[@]}"; do
  if [[ -f "$file" ]]; then
    mkdir -p "/tmp/market-radar-assets-backup/$(dirname "$file")"
    cp "$file" "/tmp/market-radar-assets-backup/$file"
  fi
done

restore_backup() {
  for file in "${backup_files[@]}"; do
    if [[ -f "/tmp/market-radar-assets-backup/$file" ]]; then
      mkdir -p "$(dirname "$file")"
      cp "/tmp/market-radar-assets-backup/$file" "$file"
    fi
  done
}

success=0
last_status=0
attempt_count=0
for attempt in 1 2; do
  attempt_count=$attempt
  echo "Asset update attempt ${attempt}/2 (hard limit 5 minutes)"
  timeout --signal=TERM --kill-after=20s 300s python scripts/update_assets.py
  last_status=$?
  if [[ $last_status -eq 0 ]]; then
    success=1
    break
  fi
  echo "Asset update attempt ${attempt} failed with status ${last_status}; restore previous successful payload and retry."
  restore_backup
  sleep $((attempt * 4))
done

python - "$success" "$last_status" "$attempt_count" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

success = bool(int(sys.argv[1]))
status = int(sys.argv[2])
attempt_count = int(sys.argv[3])
payload = {
    "metadata": {
        "version": "v11.2.8",
        "updated_at": datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "status": "ok" if success else "warning",
        "attempts": attempt_count,
        "last_exit_status": status,
        "message": (
            "Official asset update completed."
            if success else
            "Both bounded attempts failed; previous successful asset payload was retained and the full audit still ran."
        ),
    }
}
Path("data/asset-update-status.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
PY

# A failed upstream refresh is reported rather than erasing previously successful data.
exit 0
