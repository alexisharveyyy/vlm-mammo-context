"""pinned_step refuses dirty trees and logs commit and config hash."""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pinned_step.py"


def git(repo: Path, *args: str) -> None:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


def make_repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q")
    (tmp_path / "config.yaml").write_text("seed: 0\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", "init")
    return tmp_path


def run(repo: Path, *cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--config", "config.yaml", "--", *cmd],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_logs_clean_run(tmp_path):
    repo = make_repo(tmp_path)
    result = run(repo, sys.executable, "-c", "import os; print(os.environ['PINNED_COMMIT'])")
    assert result.returncode == 0
    record = json.loads((repo / "runs" / "run_log.jsonl").read_text().splitlines()[-1])
    assert record["commit"] == result.stdout.strip()
    assert len(record["config_sha256"]) == 64
    assert record["returncode"] == 0


def test_second_run_ignores_run_log(tmp_path):
    repo = make_repo(tmp_path)
    assert run(repo, sys.executable, "-c", "pass").returncode == 0
    assert run(repo, sys.executable, "-c", "pass").returncode == 0


def test_refuses_dirty_tree(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "config.yaml").write_text("seed: 1\n")
    result = run(repo, sys.executable, "-c", "pass")
    assert result.returncode == 2
    assert "config.yaml" in result.stderr


def test_refuses_untracked_code(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "new_module.py").write_text("x = 1\n")
    assert run(repo, sys.executable, "-c", "pass").returncode == 2
