"""Assign each case an answer-order offset, counterbalanced within split and stratum.

    python data/make_answer_order.py

The answer instruction names the two classes in one of two orders. For
paraphrase p (1, 2, 3) of a case with offset o, the order is
"benign or malignant" when (o + p) is odd and "malignant or benign" when it
is even. So every case sees both orders across its paraphrases, and within
each paraphrase half the cases of each split and stratum get each order.

Writes data/manifests/answer_order.csv. test.csv is not changed.
"""

from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

ANSWER_ORDER_SEED = 20261025
MANIFESTS = Path("data/manifests")


def assign_offsets(cases: pd.DataFrame, seed: int = ANSWER_ORDER_SEED) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for _stratum, group in cases.groupby(["split", "abnormality_type", "label"], sort=True):
        ids = sorted(group["case_id"])
        offsets = [i % 2 for i in range(len(ids))]
        rng.shuffle(offsets)
        rows += [
            {"case_id": c, "answer_order_offset": o} for c, o in zip(ids, offsets, strict=True)
        ]
    return pd.DataFrame(rows).sort_values("case_id")


def main() -> None:
    cases = pd.concat(
        [pd.read_csv(MANIFESTS / f"{s}.csv", dtype=str).assign(split=s) for s in ["dev", "test"]]
    )
    out = assign_offsets(cases)
    out.to_csv(MANIFESTS / "answer_order.csv", index=False, lineterminator="\n")
    merged = out.merge(cases[["case_id", "split", "label"]], on="case_id")
    print(merged.groupby(["split", "label", "answer_order_offset"]).size().to_string())


if __name__ == "__main__":
    main()
