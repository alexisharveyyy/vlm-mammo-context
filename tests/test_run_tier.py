"""run_tier.sh retries failed models and chains tiers, with stub commands."""

import os
import shutil
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_tier.sh"

CAFFEINATE = """#!/bin/sh
shift
exec "$@"
"""

# Stub for `uv run python scripts/pinned_step.py ...`: records "<tier> <model>" and
# exits with the next code listed in exits/<tier>_<model> (0 once the list is used).
UV = """#!/bin/sh
while [ "$1" != "--tier" ]; do shift; done
tier="$2"; model="$4"
echo "$tier $model" >> calls.txt
plan="exits/${tier}_${model}"
code=0
if [ -s "$plan" ]; then
    code=$(head -n 1 "$plan")
    tail -n +2 "$plan" > "$plan.tmp" && mv "$plan.tmp" "$plan"
fi
exit "$code"
"""


def setup(tmp_path: Path, exits: dict[str, list[int]]) -> Path:
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "scripts" / "run_tier.sh")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "exits").mkdir()
    for name, codes in exits.items():
        (repo / "exits" / name).write_text("".join(f"{c}\n" for c in codes))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in [("caffeinate", CAFFEINATE), ("uv", UV)]:
        (bin_dir / name).write_text(body)
        (bin_dir / name).chmod(0o755)
    return repo


def run_tier(tmp_path: Path, repo: Path, tier: str, **env: str) -> int:
    env = {
        **os.environ,
        "PATH": f"{tmp_path / 'bin'}:{os.environ['PATH']}",
        "MODELS": "a b",
        "RETRY_PAUSE": "0",
        **env,
    }
    return subprocess.run(["sh", "scripts/run_tier.sh", tier], cwd=repo, env=env).returncode


def calls(repo: Path) -> list[str]:
    return (repo / "calls.txt").read_text().splitlines()


def test_runs_every_model_and_chains_to_t4(tmp_path):
    repo = setup(tmp_path, {})
    assert run_tier(tmp_path, repo, "T3") == 0
    assert calls(repo) == ["T3 a", "T3 b", "T4 a", "T4 b"]
    assert "T4 complete" in (repo / "data/logs/T4.status").read_text()


def test_chain_off_runs_one_tier(tmp_path):
    repo = setup(tmp_path, {})
    assert run_tier(tmp_path, repo, "T1", CHAIN="0") == 0
    assert calls(repo) == ["T1 a", "T1 b"]


def test_retries_a_failed_model_then_continues(tmp_path):
    repo = setup(tmp_path, {"T3_a": [4, 1]})
    assert run_tier(tmp_path, repo, "T3") == 0
    assert calls(repo) == ["T3 a", "T3 a", "T3 a", "T3 b", "T4 a", "T4 b"]
    status = (repo / "data/logs/T3.status").read_text()
    assert status.count("retrying: a") == 2


def test_stops_after_two_retries(tmp_path):
    repo = setup(tmp_path, {"T1_a": [4, 4, 4]})
    assert run_tier(tmp_path, repo, "T1") == 4
    assert calls(repo) == ["T1 a"] * 3
    assert "stopping: a exited 4 (attempt 3)" in (repo / "data/logs/T1.status").read_text()


def test_audit_mismatch_is_not_retried(tmp_path):
    repo = setup(tmp_path, {"T2_b": [3]})
    assert run_tier(tmp_path, repo, "T2") == 3
    assert calls(repo) == ["T2 a", "T2 b"]
