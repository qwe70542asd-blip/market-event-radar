from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_publisher_parses_version_without_nested_shell_quoting():
    text=(ROOT/'scripts/publish_data_branch.sh').read_text(encoding='utf-8')
    assert 'python - "$repo_root/VERSION.json"' in text
    assert 'json.loads(path.read_text' in text
    assert 'snapshot_history' in text and 'git switch --orphan' in text
def test_publisher_requires_token_and_uses_temp_worktree():
    text=(ROOT/'scripts/publish_data_branch.sh').read_text(encoding='utf-8')
    assert 'GH_TOKEN is required' in text and 'git worktree add --detach' in text
