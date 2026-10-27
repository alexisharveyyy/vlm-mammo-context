"""Synthetic outputs used to test analysis/."""

import json
import sys

import pytest

from eval import synthetic


def test_writes_every_cell_of_a_tier(tmp_path):
    n = synthetic.generate(tmp_path, ["T1"], ["medgemma_1_5_4b"])
    files = sorted(tmp_path.rglob("*.jsonl"))
    assert n == 2 * 3 * 500 and len(files) == 6
    record = json.loads(files[0].read_text().splitlines()[0])
    assert record["split"] == "test" and record["answer_format"] == "forced"
    for key in ["case_id", "paraphrase", "malignant", "p_malignant", "parse", "error", "raw_text"]:
        assert key in record


def test_is_reproducible(tmp_path):
    synthetic.generate(tmp_path / "a", ["T1"], ["qwen3_vl_8b"])
    synthetic.generate(tmp_path / "b", ["T1"], ["qwen3_vl_8b"])
    for a in (tmp_path / "a").rglob("*.jsonl"):
        assert a.read_bytes() == (tmp_path / "b" / a.relative_to(tmp_path / "a")).read_bytes()


def test_refuses_to_write_into_runs(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["synthetic", "--out", str(synthetic.ROOT / "runs" / "x")])
    with pytest.raises(SystemExit, match="refusing"):
        synthetic.main()


def test_writes_variants_under_robustness(tmp_path):
    n = synthetic.generate(tmp_path, ["T1"], ["medgemma_1_5_4b"], ["position_end", "sampled"])
    # T1 (2 cells) plus position_end (2 cells); sampled runs only Qwen3-VL.
    assert n == (2 + 2) * 3 * 500
    files = sorted((tmp_path / "robustness" / "position_end").rglob("*.jsonl"))
    assert len(files) == 6
    record = json.loads(files[0].read_text().splitlines()[0])
    assert record["variant"] == "position_end"
    assert not (tmp_path / "robustness" / "sampled").exists()
