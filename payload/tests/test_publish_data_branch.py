from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "publish_data_branch.sh"

def run(*args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args), cwd=cwd, env=env, text=True, capture_output=True, check=False
    )

@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None, reason="bash/git unavailable")
def test_publisher_syntax():
    result = run("bash", "-n", str(SCRIPT), cwd=ROOT)
    assert result.returncode == 0, result.stderr

@pytest.mark.skipif(shutil.which("bash") is None or shutil.which("git") is None, reason="bash/git unavailable")
def test_publisher_creates_history_free_branch(tmp_path: Path):
    repo = tmp_path / "repo"
    remote = tmp_path / "remote.git"
    repo.mkdir()

    assert run("git", "init", "-b", "main", cwd=repo).returncode == 0
    run("git", "config", "user.name", "test", cwd=repo)
    run("git", "config", "user.email", "test@example.invalid", cwd=repo)

    (repo / "VERSION.json").write_text(
        json.dumps({"version": "v11.4.53"}), encoding="utf-8"
    )
    (repo / "sample.json").write_text('{"ok":true}\n', encoding="utf-8")
    scripts = repo / "scripts"
    scripts.mkdir()
    shutil.copy2(SCRIPT, scripts / SCRIPT.name)

    run("git", "add", ".", cwd=repo)
    assert run("git", "commit", "-m", "seed", cwd=repo).returncode == 0
    assert run("git", "init", "--bare", str(remote), cwd=repo).returncode == 0
    assert run("git", "remote", "add", "origin", str(remote), cwd=repo).returncode == 0

    env = os.environ.copy()
    env.update({"GH_TOKEN": "unit-test-token", "GITHUB_RUN_ID": "53", "GITHUB_RUN_ATTEMPT": "1"})
    result = run(
        "bash", "scripts/publish_data_branch.sh",
        "live-test", "live-test", "sample.json",
        cwd=repo, env=env,
    )
    assert result.returncode == 0, result.stderr

    channel = run("git", f"--git-dir={remote}", "show", "live-test:channel.json", cwd=repo)
    assert channel.returncode == 0, channel.stderr
    payload = json.loads(channel.stdout)
    assert payload["version"] == "v11.4.53"
    assert payload["snapshot_history"] == "orphan"

    count = run("git", f"--git-dir={remote}", "rev-list", "--count", "live-test", cwd=repo)
    assert count.returncode == 0
    assert count.stdout.strip() == "1"
