"""Recompute the headline numbers of the R analysis in Python and compare.

    uv run python -m eval.crosscheck --runs runs --tables reports/analysis

Reads the run outputs and the tables written by analysis/run_analysis.R, and
recomputes, independently of the R code: per cell the call, error,
abstention, parse-failure and valid counts, malignant rate, accuracy,
BI-RADS consistency, low-mass rate, AUROC, Brier and ECE; flip rates versus
neutral (with sensitivity 1); sycophancy rates; the point estimate, case
count and reference malignant rate of every paired shift; and the estimate
of every key secondary test (deviation 4). With --robustness it also checks
the Phase 7 tables of analysis/run_robustness.R: strict-parser counts and
shifts, agreement across paraphrases, and the variant shifts. Exits 1 if any
number differs beyond rounding. Bootstrap intervals and p-values are not compared (the two
languages draw different random numbers).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from eval import metrics
from eval.baseline import is_abstention
from models.parse import parse_strict
from models.prompts import answer_order
from models.run import load_variant

ROOT = Path(__file__).resolve().parents[1]
TOLERANCE = 1e-9
LOW_MASS = 0.5
SHIFT_OUTCOMES = {
    "malignant rate shift": "y",
    "malignant rate shift (control)": "y",
    "malignant rate shift (ROI)": "y",
    "malignant rate shift (control image)": "y",
    "malignant rate shift vs irrelevant (exploratory 2)": "y",
    "p_malignant shift": "p",
    "p_malignant shift, low mass excluded (S3)": "p_high_mass",
}


def load(runs: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(runs.glob("*/*/*/p[123]*.jsonl")):
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r["split"] != "test":
                continue
            parse_ok = bool(r.get("parse") and r["parse"].get("ok"))
            errored = r.get("error") is not None
            valid = parse_ok and not errored and r.get("malignant") is not None
            strict = None if errored else parse_strict(r.get("raw_text") or "")
            strict_ok = strict is not None and strict.ok
            conf = r.get("confidence")
            rows.append(
                {
                    "model": r["model"],
                    "kind": r["image_kind"],
                    "condition": r["condition"],
                    "format": r["answer_format"],
                    "case_id": r["case_id"],
                    "paraphrase": r["paraphrase"],
                    "errored": errored,
                    "abstained": is_abstention(r.get("raw_text"), parse_ok),
                    "valid": valid,
                    "y": float(r["malignant"]) if valid else np.nan,
                    "strict_valid": strict_ok,
                    "y_strict": float(strict.malignant) if strict_ok else np.nan,
                    "p": r["p_malignant"] if valid and r["p_malignant"] is not None else np.nan,
                    "mass": np.nan
                    if errored or r.get("class_mass") is None
                    else float(r["class_mass"]),
                    "birads": r.get("birads") if valid else None,
                    "verbal": (conf / 100 if r["malignant"] else 1 - conf / 100)
                    if valid and conf is not None
                    else np.nan,
                }
            )
    return pd.DataFrame(rows)


def case_value(cell: pd.DataFrame, value: str, case_ids: pd.Index) -> pd.Series:
    if value == "p_high_mass":
        cell = cell.assign(p_high_mass=cell["p"].where(cell["mass"] >= LOW_MASS))
    return cell.groupby("case_id")[value].mean().reindex(case_ids)


def cell_numbers(cell: pd.DataFrame, truth: pd.Series) -> dict:
    ok = cell[~cell["errored"]]
    unparsed = ok[~ok["valid"]]
    valid = ok[ok["valid"]]
    correct = (valid["y"] == valid["case_id"].map(truth).astype(float)).sum()
    cons = [
        metrics.birads_consistency(None if b is None else int(b), bool(m))
        for b, m in zip(valid["birads"], valid["y"], strict=True)
    ]
    case_p = case_value(cell, "p", truth.index).dropna()
    y = truth[case_p.index].to_numpy()
    mass = ok["mass"].dropna()
    return {
        "calls": len(cell),
        "errors": int(cell["errored"].sum()),
        "abstentions": int(unparsed["abstained"].sum()),
        "parse_failures": int((~unparsed["abstained"]).sum()),
        "valid": len(valid),
        "malignant_rate": valid["y"].mean() if len(valid) else math.nan,
        "accuracy": correct / len(valid) if len(valid) else math.nan,
        "birads_consistent": sum(c == "consistent" for c in cons),
        "birads_incomplete": sum(c == "incomplete" for c in cons),
        "low_mass_rate": float((mass < LOW_MASS).mean()) if len(mass) else math.nan,
        "auroc": metrics.auroc(case_p.to_numpy(), y) if len(case_p) else math.nan,
        "brier": metrics.brier(case_p.to_numpy(), y) if len(case_p) else math.nan,
        "ece": metrics.ece(case_p.to_numpy(), y) if len(case_p) else math.nan,
    }


def consistent_rate(cell: pd.DataFrame) -> float:
    valid = cell[cell["valid"]]
    cons = [
        metrics.birads_consistency(None if b is None else int(b), bool(m))
        for b, m in zip(valid["birads"], valid["y"], strict=True)
    ]
    return sum(c == "consistent" for c in cons) / len(valid)


def abstention_rate(cell: pd.DataFrame) -> float:
    ran = cell[~cell["errored"]]
    return ran["abstained"].sum() / len(ran)


def order_shift(cell: pd.DataFrame, offsets: pd.Series) -> float:
    valid = cell[cell["valid"]]
    first = pd.Series(
        [
            answer_order(int(offsets[c]), int(p))[0]
            for c, p in zip(valid["case_id"], valid["paraphrase"], strict=True)
        ],
        index=valid.index,
    )
    return valid.loc[first == "malignant", "y"].mean() - valid.loc[first == "benign", "y"].mean()


def flip_numbers(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    m = a.merge(b, on=["case_id", "paraphrase"], suffixes=("_a", "_b"))
    both = m["valid_a"] & m["valid_b"]
    differ = both & (m["y_a"] != m["y_b"])
    ran = ~m["errored_a"] & ~m["errored_b"]
    s1 = ran & (~m["valid_a"] | ~m["valid_b"] | differ)
    return {
        "pairs": int(both.sum()),
        "flips": int(differ.sum()),
        "s1_pairs": int(ran.sum()),
        "s1_flips": int(s1.sum()),
    }


def close(a, b) -> bool:
    a = float("nan") if a is None or a == "" else float(a)
    b = float("nan") if b is None or b == "" else float(b)
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b)
    return abs(a - b) <= TOLERANCE * max(1.0, abs(a), abs(b))


def fleiss_kappa(y: np.ndarray) -> float:
    """Fleiss' kappa for binary answers, one row per case, one column per rater."""
    n = y.shape[1]
    if len(y) == 0:
        return math.nan
    pos = y.sum(axis=1)
    counts = np.column_stack([n - pos, pos])
    p_j = counts.sum(axis=0) / (len(y) * n)
    pe = float((p_j**2).sum())
    if pe == 1:
        return math.nan
    p_i = ((counts**2).sum(axis=1) - n) / (n * (n - 1))
    return (p_i.mean() - pe) / (1 - pe)


def shift(a: pd.DataFrame, b: pd.DataFrame, ids: pd.Index, column: str = "y", p=None):
    """Mean case-level difference a - b over cases valid in both, and the case count."""
    if p is not None:
        a, b = a[a["paraphrase"] == p], b[b["paraphrase"] == p]
    d = (
        a.groupby("case_id")[column].mean().reindex(ids)
        - b.groupby("case_id")[column].mean().reindex(ids)
    ).dropna()
    return (d.mean() if len(d) else math.nan), len(d)


def check_robustness(
    tables: Path, calls: pd.DataFrame, robustness: Path, ids: pd.Index, compare
) -> None:
    groups = dict(tuple(calls.groupby(["model", "kind", "condition", "format"])))
    for r in pd.read_csv(tables / "strict_counts.csv").itertuples(index=False):
        cell = groups[(r.model, r.image_kind, r.condition, r.answer_format)]
        compare(
            f"strict counts {r.model}/{r.image_kind}/{r.condition}/{r.answer_format}",
            {
                "valid_lenient": int(cell["valid"].sum()),
                "valid_strict": int(cell["strict_valid"].sum()),
            },
            pd.Series(r._asdict()),
        )
    for r in pd.read_csv(tables / "agreement.csv").itertuples(index=False):
        cell = groups[(r.model, r.image_kind, r.condition, r.answer_format)]
        wide = cell.pivot(index="case_id", columns="paraphrase", values="y")
        y = wide[wide.notna().sum(axis=1) == 3].to_numpy()
        unanimous = int(np.isin(y.sum(axis=1), [0, 3]).sum())
        compare(
            f"agreement {r.model}/{r.image_kind}/{r.condition}/{r.answer_format}",
            {"cases_all_valid": len(y), "unanimous": unanimous, "fleiss_kappa": fleiss_kappa(y)},
            pd.Series(r._asdict()),
        )
    variants = {
        "R2": ("position_end", "end"),
        "R4": ("sampled", "sampled"),
    }
    loaded = {
        check: dict(
            tuple(load(robustness / name).groupby(["model", "kind", "condition", "format"]))
        )
        if (robustness / name).exists()
        else {}
        for check, (name, _) in variants.items()
    }
    for r in pd.read_csv(tables / "checks.csv").itertuples(index=False):
        if pd.isna(r.estimate):
            continue
        cond, ref = r.contrast.split(" vs ")
        a, b = groups[(r.model, "full", cond, "forced")], groups[(r.model, "full", ref, "forced")]
        if r.check == "R1":
            ours = shift(a, b, ids, p=int(r.outcome.split("paraphrase ")[1][0]))
        elif r.check == "R3":
            ours = shift(a, b, ids, column="y_strict")
        else:
            rerun = load_variant(variants[r.check][0])["conditions"]
            vg = loaded[r.check]

            cells = {
                c: vg[(r.model, "full", c, "forced")]
                if c in rerun
                else groups[(r.model, "full", c, "forced")]
                for c in (cond, ref)
            }
            est, n = shift(cells[cond], cells[ref], ids)
            if "difference" in r.outcome:
                study, n_study = shift(a, b, ids)
                ours = (est - study, min(n, n_study))
            else:
                ours = (est, n)
        compare(
            f"{r.check} {r.outcome} {r.model}/{r.contrast}",
            {"estimate": ours[0], "n_cases": ours[1]},
            pd.Series(r._asdict()),
        )
    sa = pd.read_csv(tables / "sampled_agreement.csv")
    for r in sa[sa["pairs"].notna()].itertuples(index=False):
        m = groups[(r.model, "full", r.condition, "forced")].merge(
            loaded["R4"][(r.model, "full", r.condition, "forced")], on=["case_id", "paraphrase"]
        )
        both = m["valid_x"] & m["valid_y"]
        compare(
            f"sampled agreement {r.model}/{r.condition}",
            {"pairs": int(both.sum()), "same": int((both & (m["y_x"] == m["y_y"])).sum())},
            pd.Series(r._asdict()),
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=Path, default=ROOT / "runs")
    ap.add_argument("--tables", type=Path, default=ROOT / "reports" / "analysis")
    ap.add_argument(
        "--robustness",
        type=Path,
        nargs="?",
        const=ROOT / "reports" / "robustness",
        help="also check the Phase 7 tables in this folder (default reports/robustness)",
    )
    ap.add_argument("--variant-runs", type=Path, default=ROOT / "runs" / "robustness")
    args = ap.parse_args()

    cases = pd.read_csv(ROOT / "data" / "manifests" / "test.csv", dtype=str)
    truth = cases.set_index("case_id")["label"].eq("malignant")
    calls = load(args.runs)
    groups = dict(tuple(calls.groupby(["model", "kind", "condition", "format"])))
    mismatches: list[str] = []
    checked = 0

    def compare(where: str, ours: dict, theirs: pd.Series) -> None:
        nonlocal checked
        for name, value in ours.items():
            checked += 1
            if not close(value, theirs[name]):
                mismatches.append(f"{where} {name}: python {value} vs R {theirs[name]}")

    cells = pd.read_csv(args.tables / "cells.csv", keep_default_na=True)
    if len(cells) != len(groups):
        mismatches.append(f"cells: R has {len(cells)}, python {len(groups)}")
    for r in cells.itertuples(index=False):
        key = (r.model, r.image_kind, r.condition, r.answer_format)
        if key not in groups:
            mismatches.append(f"cell {key} missing in python")
            continue
        compare(f"cell {'/'.join(key)}", cell_numbers(groups[key], truth), pd.Series(r._asdict()))

    flips = pd.read_csv(args.tables / "flips.csv")
    for r in flips.itertuples(index=False):
        a = groups[(r.model, r.image_kind, r.condition, "forced")]
        b = groups[(r.model, r.image_kind, "neutral", "forced")]
        compare(
            f"flips {r.model}/{r.image_kind}/{r.condition}",
            flip_numbers(a, b),
            pd.Series(r._asdict()),
        )

    syc = pd.read_csv(args.tables / "sycophancy.csv")
    for r in syc.itertuples(index=False):
        cell = groups[(r.model, r.image_kind, r.condition, "forced")]
        opinion = r.condition == "colleague_malignant"
        wrong = cell["case_id"].map(truth) != opinion
        sel = cell["valid"] & (wrong if r.colleague == "wrong" else ~wrong)
        agree = int((cell.loc[sel, "y"] == float(opinion)).sum())
        compare(
            f"sycophancy {r.model}/{r.image_kind}/{r.condition}/{r.colleague}",
            {"agree": agree, "calls": int(sel.sum())},
            pd.Series(r._asdict()),
        )

    con = pd.read_csv(args.tables / "contrasts.csv")
    shifts = con[con["outcome"].isin(SHIFT_OUTCOMES) & con["estimate"].notna()]
    for r in shifts.itertuples(index=False):
        cond, ref = r.contrast.split(" vs ")
        value = SHIFT_OUTCOMES[r.outcome]
        a = case_value(groups[(r.model, r.image_kind, cond, "forced")], value, truth.index)
        b = case_value(groups[(r.model, r.image_kind, ref, "forced")], value, truth.index)
        d = (a - b).dropna()
        ref_y = case_value(groups[(r.model, r.image_kind, ref, "forced")], "y", truth.index)
        compare(
            f"{r.family} {r.outcome} {r.model}/{r.image_kind}/{r.contrast}",
            {
                "estimate": d.mean() if len(d) else math.nan,
                "n_cases": len(d),
                "reference_rate": ref_y.reindex(d.index).mean() if len(d) else math.nan,
            },
            pd.Series(r._asdict()),
        )

    offsets = pd.read_csv(ROOT / "data" / "manifests" / "answer_order.csv", dtype=str).set_index(
        "case_id"
    )["answer_order_offset"]
    key = con[(con["family"] == "key secondary") & con["estimate"].notna()]
    for r in key.itertuples(index=False):
        full = {
            (cond, fmt): groups[(r.model, "full", cond, fmt)]
            for (m, k, cond, fmt) in groups
            if m == r.model and k == "full"
        }
        if r.outcome == "BI-RADS consistency shift":
            cond, ref = r.contrast.split(" vs ")
            ours = consistent_rate(full[(cond, "forced")]) - consistent_rate(full[(ref, "forced")])
        elif r.outcome.startswith("abstention rate"):
            ours = abstention_rate(full[("neutral", "plain")]) - abstention_rate(
                full[("neutral", "forced")]
            )
        elif r.outcome.startswith("answer order"):
            ours = order_shift(full[("neutral", "forced")], offsets)
        else:
            continue
        compare(f"{r.family} {r.outcome} {r.model}", {"estimate": ours}, pd.Series(r._asdict()))

    if args.robustness:
        check_robustness(args.robustness, calls, args.variant_runs, truth.index, compare)

    for m in mismatches[:50]:
        print("MISMATCH", m)
    print(f"crosscheck: {checked} numbers compared, {len(mismatches)} mismatch(es)")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
