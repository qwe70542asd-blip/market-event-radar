#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PAYLOAD = PACKAGE_ROOT / "payload"

def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(2)

def find_repo() -> Path:
    candidates = [Path.cwd(), PACKAGE_ROOT.parent, PACKAGE_ROOT]
    for candidate in candidates:
        if (candidate / "VERSION.json").exists() and (candidate / "scripts").is_dir():
            return candidate.resolve()
    fail("找不到 market-event-radar 專案根目錄。請把本資料夾解壓到專案根目錄後再執行。")

def patch_text(path: Path, transforms: list[tuple[str, str]]) -> None:
    if not path.exists():
        fail(f"缺少必要檔案：{path.name}")
    text = path.read_text(encoding="utf-8")
    for old, new in transforms:
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")

def run_optional(cmd: list[str], cwd: Path) -> None:
    try:
        result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    except FileNotFoundError:
        print(f"[SKIP] 未安裝 {cmd[0]}")
        return
    if result.returncode:
        print(result.stdout)
        print(result.stderr)
        fail("驗證失敗：" + " ".join(cmd))
    print("[PASS]", " ".join(cmd))

def main() -> int:
    repo = find_repo()
    print("[1/6] 專案：", repo)
    current = json.loads((repo / "VERSION.json").read_text(encoding="utf-8")).get("version")
    if current not in {"v11.4.52", "v11.4.53"}:
        fail(f"這個安裝包以 v11.4.52 為基準；目前偵測到 {current}")

    print("[2/6] 覆蓋 v11.4.53 檔案")
    for src in PAYLOAD.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(PAYLOAD)
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print("  write", rel)

    print("[3/6] 更新首頁與 Service Worker 快取版本")
    index = repo / "index.html"
    patch_text(index, [
        ("v11.4.52", "v11.4.53"),
        ("11.4.52", "11.4.53"),
    ])
    text = index.read_text(encoding="utf-8")
    guard_tag = '<script src="assets/stale-market-guard.js?v=11.4.53"></script>'
    if guard_tag not in text:
        marker = '<script src="assets/home.js?v=11.4.53"></script>'
        if marker not in text:
            fail("index.html 找不到 home.js 載入位置")
        text = text.replace(marker, marker + guard_tag)
        index.write_text(text, encoding="utf-8")

    sw = repo / "service-worker.js"
    patch_text(sw, [
        ("market-event-radar-v11-4-52", "market-event-radar-v11-4-53"),
        ("v11.4.52-overrides.css?v=11.4.52", "v11.4.53-overrides.css?v=11.4.53"),
        ("?v=11.4.52", "?v=11.4.53"),
    ])
    sw_text = sw.read_text(encoding="utf-8")
    if "assets/stale-market-guard.js?v=11.4.53" not in sw_text:
        sw_text = sw_text.replace(
            '"assets/home.js?v=11.4.53",',
            '"assets/home.js?v=11.4.53","assets/stale-market-guard.js?v=11.4.53",'
        )
        sw.write_text(sw_text, encoding="utf-8")

    print("[4/6] 刪除所有舊版本殘留")
    subprocess.run([sys.executable, "scripts/cleanup_repo.py"], cwd=repo, check=True)

    print("[5/6] 語法與 publisher regression")
    run_optional(["bash", "-n", "scripts/publish_data_branch.sh"], repo)
    run_optional(["node", "--check", "assets/stale-market-guard.js"], repo)
    run_optional(["node", "--check", "edge/market-live-worker.js"], repo)
    run_optional([sys.executable, "-m", "pytest", "-q", "tests/test_publish_data_branch.py"], repo)

    print("[6/6] 完成")
    print("v11.4.53 已覆蓋；舊版 manifest / validation / overrides / legacy tests 已清除。")
    print("接著用 GitHub Desktop 查看 Changes，確認後 Commit + Push 即可。")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
