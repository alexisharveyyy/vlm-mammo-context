"""Unit tests for scripts/audit.py checks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import audit


def test_message_style():
    assert audit.check_message("Fix split \u2014 again")
    assert not audit.check_message("Fix off-by-one in split")


def test_text_style_and_secrets():
    assert audit.check_text("README.md", "a \u2014 b")
    assert audit.check_text("README.md", "done \U0001f680")
    assert audit.check_text("x.py", "token = 'ghp_" + "a" * 36 + "'")
    assert not audit.check_text("README.md", "plain text, a hyphen - and a colon:")


def test_file_rules():
    assert audit.check_file("data/raw/case.dcm", 10)
    assert audit.check_file("data/png/case.png", 10)
    assert not audit.check_file("reports/figures/flip_rate.png", 10)
    assert audit.check_file("runs/big.jsonl", 6 * 1024 * 1024)
