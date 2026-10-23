#!/bin/sh
# Lint, tests and the repository audit. Must pass before every push.
set -eu

cd "$(git rev-parse --show-toplevel)"

echo "== ruff check"
uv run ruff check .
echo "== ruff format --check"
uv run ruff format --check .
echo "== pytest"
uv run pytest -q
echo "== audit"
uv run python scripts/audit.py
echo "check.sh: all passed"
