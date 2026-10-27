"""Synthetic run outputs with planted effects, for developing and testing analysis/.

    uv run python -m eval.synthetic --out /tmp/synthetic_runs [--tiers T0 T1 ...]

Writes <out>/<model>/<image_kind>/<condition>/p<k>[_plain].jsonl with the
fields of a real run record that the analysis reads, for the test-set case IDs
and every cell of the requested tiers (models.run.TIERS). Nothing here is a
result: the answers come from a fixed logistic model with the effects in
EFFECTS, so tests can check that the analysis recovers them. Never write this
into runs/.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from models.prompts import answer_order
from models.run import TIERS

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["qwen3_vl_8b", "medgemma_1_5_4b", "internvl3_5_8b"]
SEED = 1
COMMIT = "0" * 40
CONFIG = "1" * 64

# Logit shifts by condition. combined adds the case's assigned age and history.
EFFECTS = {
    "neutral": 0.0,
    "colleague_malignant": 1.2,
    "colleague_benign": -1.2,
    "age_42": -0.15,
    "age_68": 0.15,
    "history_yes": 0.25,
    "history_no": -0.25,
    "irrelevant": 0.0,
}
MODEL_BIAS = {"qwen3_vl_8b": -0.5, "medgemma_1_5_4b": -2.0, "internvl3_5_8b": -1.0}
MODEL_SCALE = {"qwen3_vl_8b": 1.0, "medgemma_1_5_4b": 0.5, "internvl3_5_8b": 1.0}
SIGNAL = {"full": 0.6, "roi": 1.0, "no_image": 0.0, "blank_full": 0.0, "blank_roi": 0.0}
MALIGNANT_FIRST = 0.3
PARSE_FAILURE, FORCED_ABSTENTION, PLAIN_ABSTENTION, ERROR = 0.015, 0.005, 0.3, 0.002


def effect(condition: str, case: pd.Series) -> float:
    if condition != "combined":
        return EFFECTS[condition]
    history = "history_yes" if case["synthetic_family_history"] == "present" else "history_no"
    return EFFECTS[f"age_{int(case['synthetic_age'])}"] + EFFECTS[history]


def record(model, kind, condition, paraphrase, answer_format, case_id, rng, logit) -> dict:
    base = {
        "call_key": "|".join(
            str(v) for v in (model, kind, condition, paraphrase, answer_format, case_id)
        ),
        "split": "test",
        "model": model,
        "image_kind": kind,
        "condition": condition,
        "paraphrase": paraphrase,
        "answer_format": answer_format,
        "case_id": case_id,
        "error": None,
        "reused_from": None,
        "commit": COMMIT,
        "config_sha256": CONFIG,
    }
    empty = {
        "raw_text": None,
        "birads": None,
        "malignant": None,
        "confidence": None,
        "p_malignant": None,
        "class_mass": None,
        "parse": None,
    }
    u = rng.random()
    if u < ERROR:
        return base | empty | {"error": "RuntimeError: synthetic"}
    p = 1 / (1 + math.exp(-logit))
    mass = float(rng.uniform(0.3, 1.0))
    if u < ERROR + PARSE_FAILURE:
        text = "I cannot interpret medical images."
        parsed = {"birads": None, "malignant": None, "confidence": None}
        return (
            base
            | empty
            | {
                "raw_text": text,
                "parse": parsed | {"rules": "lenient", "errors": ["format"], "ok": False},
            }
        )
    abstain = PLAIN_ABSTENTION if answer_format == "plain" else FORCED_ABSTENTION
    if rng.random() < abstain:
        text = "BI-RADS: 0\nAssessment: indeterminate\nConfidence: 50"
        parsed = {"birads": 0, "malignant": None, "confidence": 50.0}
        return (
            base
            | empty
            | parsed
            | {
                "raw_text": text,
                "p_malignant": p,
                "class_mass": mass,
                "parse": parsed
                | {"rules": "lenient", "errors": ["assessment_unreadable"], "ok": False},
            }
        )
    malignant = p > 0.5
    confidence = float(min(100, max(50, round(100 * max(p, 1 - p) + rng.normal(0, 5)))))
    birads = int(rng.choice([4, 5, 0]) if malignant else rng.choice([1, 2, 3, 4, 0]))
    word = "malignant" if malignant else "benign"
    parsed = {"birads": birads, "malignant": malignant, "confidence": confidence}
    return (
        base
        | parsed
        | {
            "raw_text": f"BI-RADS: {birads}\nAssessment: {word}\nConfidence: {int(confidence)}",
            "p_malignant": p,
            "class_mass": mass,
            "parse": parsed | {"rules": "strict", "errors": [], "ok": True},
        }
    )


def generate(out: Path, tiers: list[str], models: list[str] = MODELS) -> int:
    cases = pd.read_csv(ROOT / "data" / "manifests" / "test.csv", dtype=str)
    offsets = pd.read_csv(ROOT / "data" / "manifests" / "answer_order.csv", dtype=str).set_index(
        "case_id"
    )["answer_order_offset"]
    cells = [cell for tier in tiers for cell in TIERS[tier]]
    rng = np.random.default_rng(SEED)
    n = 0
    for model in models:
        # Case and paraphrase effects are shared across conditions, so contrasts are paired.
        case_effect = {(k, c): rng.normal(0, 0.8) for k in SIGNAL for c in cases["case_id"]}
        para_effect = {
            (k, c, p): rng.normal(0, 0.3)
            for k in SIGNAL
            for c in cases["case_id"]
            for p in (1, 2, 3)
        }
        for kind, condition, answer_format in cells:
            for paraphrase in (1, 2, 3):
                lines = []
                for case in cases.itertuples(index=False):
                    row = pd.Series(case._asdict())
                    truth = 1.0 if row["label"] == "malignant" else -1.0
                    first = answer_order(int(offsets[row["case_id"]]), paraphrase)[0]
                    logit = (
                        MODEL_BIAS[model]
                        + SIGNAL[kind] * truth
                        + MODEL_SCALE[model] * effect(condition, row)
                        + (MALIGNANT_FIRST if first == "malignant" else 0.0)
                        + case_effect[(kind, row["case_id"])]
                        + para_effect[(kind, row["case_id"], paraphrase)]
                        + rng.normal(0, 0.2)
                    )
                    lines.append(
                        record(
                            model,
                            kind,
                            condition,
                            paraphrase,
                            answer_format,
                            row["case_id"],
                            rng,
                            logit,
                        )
                    )
                suffix = "_plain" if answer_format == "plain" else ""
                path = out / model / kind / condition / f"p{paraphrase}{suffix}.jsonl"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("".join(json.dumps(r) + "\n" for r in lines))
                n += len(lines)
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--tiers", nargs="+", default=list(TIERS))
    ap.add_argument("--models", nargs="+", default=MODELS)
    args = ap.parse_args()
    out = args.out.resolve()
    if (ROOT / "runs").resolve() in (out, *out.parents):
        raise SystemExit("refusing to write synthetic outputs into runs/")
    print(f"wrote {generate(args.out, args.tiers, args.models)} synthetic calls to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
