"""Repository audit: writing style, data files and secrets.

Checks every commit message in history and every file that is tracked or would
be added (untracked but not ignored). Exits non-zero on any finding.

    python scripts/audit.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

EM_DASH = "\u2014"
EMOJI = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff\ufe0f]")

SECRETS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"hf_[A-Za-z0-9]{30,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{30,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

MEDICAL_EXTENSIONS = {".dcm", ".dicom", ".nii", ".gz"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}
# Plots of model outputs are allowed; nothing derived from pixels.
IMAGE_ALLOWED_PREFIX = "reports/figures/"
MAX_BYTES = 5 * 1024 * 1024


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def check_message(message: str) -> list[str]:
    problems = []
    if EM_DASH in message:
        problems.append("em dash")
    if EMOJI.search(message):
        problems.append("emoji")
    return problems


def check_text(path: str, text: str) -> list[str]:
    problems = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if EM_DASH in line:
            problems.append(f"{path}:{lineno}: em dash")
        if EMOJI.search(line):
            problems.append(f"{path}:{lineno}: emoji")
        for pattern in SECRETS:
            if pattern.search(line):
                problems.append(f"{path}:{lineno}: possible secret ({pattern.pattern})")
    return problems


def check_file(path: str, size: int) -> list[str]:
    problems = []
    suffix = Path(path).suffix.lower()
    if suffix in MEDICAL_EXTENSIONS:
        problems.append(f"{path}: medical image file")
    if suffix in IMAGE_EXTENSIONS and not path.startswith(IMAGE_ALLOWED_PREFIX):
        problems.append(f"{path}: image outside {IMAGE_ALLOWED_PREFIX}")
    if size > MAX_BYTES:
        problems.append(f"{path}: {size} bytes, over 5 MB")
    return problems


def audit_history() -> list[str]:
    has_head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], capture_output=True)
    if has_head.returncode:
        return []
    problems = []
    for sha in git("rev-list", "--all").split():
        for p in check_message(git("log", "-1", "--format=%B", sha)):
            problems.append(f"commit {sha[:10]}: {p}")
    return problems


def audit_tree() -> list[str]:
    problems = []
    paths = git("ls-files", "--cached", "--others", "--exclude-standard").splitlines()
    for path in paths:
        file = Path(path)
        if not file.is_file():
            continue
        problems += check_file(path, file.stat().st_size)
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        problems += check_text(path, text)
    return problems


def main() -> int:
    problems = audit_history() + audit_tree()
    for p in problems:
        print(p)
    print(f"audit: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
