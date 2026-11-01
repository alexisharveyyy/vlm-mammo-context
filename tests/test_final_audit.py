"""scripts/final_audit.sh on throwaway repositories with planted problems."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "final_audit.sh"
ME = ("Alexis Harvey", "alexis@harveyfamilia.com")
# Built from pieces so this file does not trip the audits itself.
NAME = "Cl" + "aude"
EM_DASH = chr(0x2014)


def git(repo, *args, env=None):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


def make_repo(tmp_path, files, message="Add files", who=ME):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    env = os.environ | {
        "GIT_AUTHOR_NAME": who[0],
        "GIT_AUTHOR_EMAIL": who[1],
        "GIT_COMMITTER_NAME": who[0],
        "GIT_COMMITTER_EMAIL": who[1],
    }
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
    git(repo, "add", "-A", env=env)
    git(repo, "commit", "-q", "--no-verify", "-m", message, env=env)
    return repo


def audit(repo):
    out = subprocess.run(["sh", str(SCRIPT), "--offline"], cwd=repo, capture_output=True, text=True)
    counts = {}
    for line in out.stdout.splitlines():
        parts = line.rsplit(None, 1)
        if len(parts) == 2 and parts[1].isdigit():
            counts[parts[0].strip()] = int(parts[1])
    return out.returncode, counts


def test_clean_repository_passes(tmp_path):
    code, counts = audit(make_repo(tmp_path, {"README.md": "Regenerated with the rules.\n"}))
    assert code == 0 and sum(counts.values()) == 0


@pytest.mark.parametrize(
    ("files", "message", "who", "check"),
    [
        ({"a.txt": "x\n"}, "Add x\n\nCo-Authored-By: someone", ME, "attribution"),
        ({"a.txt": f"Written by {NAME}.\n"}, "Add x", ME, "names"),
        ({f"notes/{NAME}.md": "x\n"}, "Add x", ME, "names"),
        ({"a.txt": "x\n"}, "Add x", ("Someone", "s@example.com"), "identity"),
        ({"img/scan.png": b"\x89PNG"}, "Add x", ME, "images"),
        (
            {"reports/figures/plot.png": b"\x89PNG", "raw/a.dcm": b"DICM"},
            "Add x",
            ME,
            "medical images",
        ),
        ({"big.bin": b"\0" * (5 * 1024 * 1024 + 1)}, "Add x", ME, "large files"),
        ({"a.txt": "token " + "gh" + "p_" + "A" * 36 + "\n"}, "Add x", ME, "secrets"),
        ({"a.txt": f"a {EM_DASH} b\n"}, "Add x", ME, "em dash"),
        ({"a.txt": "ok\n"}, "Add x \U0001f600", ME, "emoji"),
        ({"reports/FINAL_REPORT.md": "[[" + "PENDING: result]]\n"}, "Add x", ME, "placeholders"),
    ],
)
def test_each_problem_fails_the_audit(tmp_path, files, message, who, check):
    code, counts = audit(make_repo(tmp_path, files, message, who))
    assert code == 1
    assert counts[check] >= 1


def test_problems_removed_later_are_still_found(tmp_path):
    repo = make_repo(tmp_path, {"a.txt": f"by {NAME}\n"})
    (repo / "a.txt").write_text("clean\n")
    env = os.environ | {
        "GIT_AUTHOR_NAME": ME[0],
        "GIT_AUTHOR_EMAIL": ME[1],
        "GIT_COMMITTER_NAME": ME[0],
        "GIT_COMMITTER_EMAIL": ME[1],
    }
    git(repo, "commit", "-q", "--no-verify", "-am", "Clean up", env=env)
    code, counts = audit(repo)
    assert code == 1 and counts["names"] == 1
