"""Exploratory analysis 1: features, inputs and the exploratory label."""

import json

import numpy as np
import pandas as pd
from PIL import Image

from eval import surface_features as sf


def test_image_features_on_a_known_image(tmp_path):
    a = np.zeros((10, 10), dtype=np.uint8)
    a[:, :4] = 255  # 40% breast at full intensity, rest background
    Image.fromarray(a).save(tmp_path / "X.png")
    f = sf.image_features(tmp_path / "X.png")
    assert f["breast_fraction"] == 0.4
    assert f["breast_mean"] == 1.0 and f["breast_sd"] == 0.0
    assert abs(f["mean_intensity"] - 0.4) < 1e-12


def test_reads_only_t0_neutral_forced_valid_answers(tmp_path):
    cell = tmp_path / sf.MODEL / "full" / "neutral"
    cell.mkdir(parents=True)
    for p in (1, 2, 3):
        rows = [
            {
                "split": "test",
                "condition": "neutral",
                "answer_format": "forced",
                "case_id": "A",
                "error": None,
                "parse": {"ok": True},
                "malignant": p == 1,
                "p_malignant": 0.1 * p,
            },
            {
                "split": "test",
                "condition": "neutral",
                "answer_format": "forced",
                "case_id": "B",
                "error": None,
                "parse": {"ok": p != 3},
                "malignant": False,
                "p_malignant": 0.9,
            },
        ]
        (cell / f"p{p}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    out = sf.load_answers(tmp_path)
    assert abs(out.loc["A", "p"] - 0.2) < 1e-12 and abs(out.loc["A", "y"] - 1 / 3) < 1e-12
    assert out.loc["B", "p"] == 0.9


def test_report_is_labeled_exploratory_and_has_no_case_ids():
    rng = np.random.default_rng(0)
    n = 40
    df = pd.DataFrame({f: rng.normal(size=n) for f in sf.FEATURES})
    df["truth"] = np.tile([0.0, 1.0], n // 2)
    df["p"] = rng.uniform(size=n)
    df["abnormality_type"] = np.repeat(["mass", "calc"], n // 2)
    df["case_id"] = [f"P_{i:05d}_LEFT_MLO" for i in range(n)]
    sf.RESAMPLES = 50
    res = sf.analyze(df)
    text = sf.render(res, {"command": "c", "commit": "x"})
    assert sf.LABEL in text and "EXPLORATORY" in text
    assert "P_0" not in text and "P_0" not in json.dumps(res, default=float)
    assert set(res["features"]) == set(sf.FEATURES)
