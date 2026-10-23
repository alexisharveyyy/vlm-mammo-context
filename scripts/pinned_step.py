"""Run an experiment step pinned to a clean commit and a hashed config.

Refuses to start if tracked or untracked (non-ignored) files differ from HEAD,
except for paths under the output prefixes. Appends one JSON line per run to
runs/run_log.jsonl with the commit, config hash, command, timing and exit code.
The child process sees PINNED_COMMIT and PINNED_CONFIG_SHA256 in its environment.

    python scripts/pinned_step.py --config configs/models.yaml -- python -m eval.run ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

OUTPUT_PREFIXES = ("runs/",)
LOG_PATH = Path("runs/run_log.jsonl")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def dirty_paths(output_prefixes: tuple[str, ...] = OUTPUT_PREFIXES) -> list[str]:
    """Paths that differ from HEAD, ignoring experiment outputs."""
    paths = []
    for line in git("status", "--porcelain", "--untracked-files=all").splitlines():
        path = line[3:].split(" -> ")[-1].strip('"')
        if not path.startswith(output_prefixes):
            paths.append(path)
    return paths


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", type=Path, required=True, help="config file to hash")
    parser.add_argument("--log", type=Path, default=LOG_PATH, help="run log (JSON lines)")
    parser.add_argument("command", nargs=argparse.REMAINDER, help="command after --")
    args = parser.parse_args(argv)

    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("no command given; pass it after --")
    if not args.config.is_file():
        parser.error(f"config not found: {args.config}")

    dirty = dirty_paths()
    if dirty:
        print("pinned_step: refusing to run with uncommitted changes:", file=sys.stderr)
        for path in dirty:
            print(f"  {path}", file=sys.stderr)
        return 2

    commit = git("rev-parse", "HEAD").strip()
    config_hash = sha256_file(args.config)
    env = {**os.environ, "PINNED_COMMIT": commit, "PINNED_CONFIG_SHA256": config_hash}

    started = datetime.now(UTC)
    t0 = time.monotonic()
    returncode = subprocess.run(command, env=env).returncode
    elapsed = time.monotonic() - t0

    record = {
        "started_utc": started.isoformat(timespec="seconds"),
        "elapsed_s": round(elapsed, 3),
        "commit": commit,
        "config": str(args.config),
        "config_sha256": config_hash,
        "command": command,
        "returncode": returncode,
    }
    args.log.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    return returncode


if __name__ == "__main__":
    sys.exit(main())
