"""Phase 4 baseline report from the committed test-set outputs.

    uv run python -m eval.baseline

Reads runs/<model>/<image_kind>/neutral/*.jsonl (tier T0) and writes
reports/baseline.md and reports/baseline.json. Nothing is run.

Per model and image kind (neutral prompt): parse failures, errors, malignant
answer rate, accuracy and BI-RADS consistency over calls with Wilson 95%
intervals (calls of one case are not independent, so these intervals are
somewhat narrow); AUROC of case-level p_malignant and verbal P(malignant),
Brier score and ECE, with case-bootstrap 95% intervals; the low-mass rate;
and the abstention rate. An abstention is an answer whose assessment line is
neither benign nor malignant (docs/PREREGISTRATION.md, section 5, item 8); a
parse failure that is not an abstention has no readable assessment. Both are
missing in every other metric. The above-chance label follows
docs/DEVIATIONS.md, entry 2.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

from eval import metrics
from models.parse import CLASS_WORD, DECORATION
from models.prompts import answer_order

ROOT = Path(__file__).resolve().parents[1]
MODELS = ["qwen3_vl_8b", "medgemma_1_5_4b", "internvl3_5_8b"]
KINDS = ["full", "no_image", "blank_full", "roi", "blank_roi"]
LOW_MASS = 0.5
# The assessment on its own line (models.parse.ASSESSMENT may run on to the next).
ASSESSMENT_LINE = re.compile(r"\bassessment[ \t]*[:=\-][ \t]*([^\n]*)", re.IGNORECASE)


def load(model: str, split: str = "test") -> pd.DataFrame:
    rows = []
    runs = ROOT / "runs" if split == "test" else ROOT / "runs" / "dev"
    for path in sorted((runs / model).glob("*/neutral/*.jsonl")):
        for line in path.read_text().splitlines():
            r = json.loads(line)
            if r["split"] != split:
                continue
            rows.append(
                {
                    k: r[k]
                    for k in [
                        "case_id",
                        "image_kind",
                        "paraphrase",
                        "answer_format",
                        "malignant",
                        "confidence",
                        "birads",
                        "p_malignant",
                        "class_mass",
                        "error",
                        "raw_text",
                        "reused_from",
                        "commit",
                        "config_sha256",
                    ]
                }
                | {"parse_ok": bool(r["parse"] and r["parse"]["ok"])}
            )
    return pd.DataFrame(rows)


def is_abstention(text: str, parse_ok: bool) -> bool:
    """Unparsed, with an assessment line that names neither class."""
    if parse_ok or text is None:
        return False
    m = ASSESSMENT_LINE.search(DECORATION.sub("", text))
    return bool(m and m.group(1).strip() and not CLASS_WORD.search(m.group(1)))


def verbal_p(row) -> float:
    if row.malignant is None or pd.isna(row.confidence):
        return np.nan
    return row.confidence / 100 if row.malignant else 1 - row.confidence / 100


def summarize(df: pd.DataFrame, labels: pd.Series, offsets: pd.Series) -> dict:
    out = {
        "calls": len(df),
        "errors": int(df["error"].notna().sum()),
        "reused": int(df["reused_from"].notna().sum()),
    }
    ok = df[df["error"].isna()]
    abstained = [is_abstention(t, p) for t, p in zip(ok["raw_text"], ok["parse_ok"], strict=True)]
    out["abstentions"] = int(sum(abstained))
    out["abstention_rate"] = out["abstentions"] / max(len(ok), 1)
    out["abstention_ci"] = metrics.wilson(out["abstentions"], len(ok))
    out["parse_failures"] = int((~ok["parse_ok"]).sum()) - out["abstentions"]
    out["parse_failure_rate"] = out["parse_failures"] / max(len(ok), 1)
    out["parse_failure_ci"] = metrics.wilson(out["parse_failures"], len(ok))
    answered = ok[ok["malignant"].notna()].copy()
    answered["truth"] = answered["case_id"].map(labels).eq("malignant")
    n = len(answered)
    mal = int(answered["malignant"].astype(bool).sum())
    correct = int((answered["malignant"].astype(bool) == answered["truth"]).sum())
    out["answered"] = n
    out["malignant_rate"] = mal / n if n else np.nan
    out["malignant_rate_ci"] = metrics.wilson(mal, n)
    out["accuracy"] = correct / n if n else np.nan
    out["accuracy_ci"] = metrics.wilson(correct, n)
    cons = [
        metrics.birads_consistency(None if pd.isna(b) else int(b), bool(m))
        for b, m in zip(answered["birads"], answered["malignant"], strict=True)
    ]
    counts = pd.Series([c for c in cons if c]).value_counts()
    for key in ["consistent", "inconsistent", "incomplete"]:
        out[f"birads_{key}"] = int(counts.get(key, 0))
    first = [
        answer_order(int(offsets[c]), int(p))[0]
        for c, p in zip(answered["case_id"], answered["paraphrase"], strict=True)
    ]
    for listed in ["malignant", "benign"]:
        sel = answered["malignant"].astype(bool)[[f == listed for f in first]]
        k = int(sel.sum())
        out[f"{listed}_first_calls"] = len(sel)
        out[f"{listed}_first_malignant_rate"] = k / len(sel) if len(sel) else np.nan
        out[f"{listed}_first_malignant_ci"] = metrics.wilson(k, len(sel))
    out["birads_consistent_rate"] = out["birads_consistent"] / n if n else np.nan
    out["birads_consistent_ci"] = metrics.wilson(out["birads_consistent"], n)
    mass = ok["class_mass"].dropna()
    out["low_mass_rate"] = float((mass < LOW_MASS).mean()) if len(mass) else np.nan

    ok = ok.assign(verbal=[verbal_p(r) for r in ok.itertuples()])
    case = ok.groupby("case_id").agg(p=("p_malignant", "mean"), v=("verbal", "mean"))
    case["truth"] = case.index.to_series().map(labels).eq("malignant").to_numpy()
    for name, col in [("auroc", "p"), ("auroc_verbal", "v")]:
        c = case.dropna(subset=[col])
        s, y = c[col].to_numpy(), c["truth"].to_numpy()
        out[name] = metrics.auroc(s, y)
        out[f"{name}_ci"] = (
            metrics.bootstrap_ci(lambda i, s=s, y=y: metrics.auroc(s[i], y[i]), len(c))
            if len(c)
            else (np.nan, np.nan)
        )
        out[f"{name}_cases"] = len(c)
    c = case.dropna(subset=["p"])
    p, y = c["p"].to_numpy(), c["truth"].to_numpy()
    out["brier"] = metrics.brier(p, y) if len(c) else np.nan
    out["ece"] = metrics.ece(p, y) if len(c) else np.nan
    out["commits"] = sorted(df["commit"].unique())
    out["config_sha256"] = sorted(df["config_sha256"].unique())
    return out


def fmt(x, ci=None, pct=True) -> str:
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    s = f"{100 * x:.1f}%" if pct else f"{x:.3f}"
    if ci is not None and not any(np.isnan(v) for v in ci):
        s += (
            f" ({100 * ci[0]:.1f} to {100 * ci[1]:.1f})"
            if pct
            else f" ({ci[0]:.3f} to {ci[1]:.3f})"
        )
    return s


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=ROOT / "reports")
    ap.add_argument(
        "--split",
        default="test",
        choices=["test", "dev"],
        help="dev only checks the script on dev outputs; reports use test",
    )
    args = ap.parse_args()

    test = pd.read_csv(ROOT / "data" / "manifests" / f"{args.split}.csv", dtype=str)
    labels = test.set_index("case_id")["label"]
    offsets = pd.read_csv(ROOT / "data" / "manifests" / "answer_order.csv", dtype=str).set_index(
        "case_id"
    )["answer_order_offset"]
    results, pending = {}, []
    for model in MODELS:
        df = load(model, args.split)
        for kind in KINDS:
            for answer_format in ["forced", "plain"]:
                part = (
                    df[(df.get("image_kind") == kind) & (df.get("answer_format") == answer_format)]
                    if len(df)
                    else df
                )
                expected = (
                    3 * len(test) if (answer_format == "forced" or kind in ("full", "roi")) else 0
                )
                if expected == 0:
                    continue
                key = f"{model}/{kind}/{answer_format}"
                if len(part) < expected:
                    pending.append(f"{key}: {len(part)} of {expected} calls")
                    if len(part) == 0:
                        continue
                results[key] = summarize(part, labels, offsets)
                results[key]["complete"] = len(part) >= expected

    labels_out = {}
    for model in MODELS:
        r = results.get(f"{model}/full/forced")
        if r is None or not r["complete"]:
            labels_out[model] = "pending"
        else:
            labels_out[model] = "above chance" if r["auroc_ci"][0] > 0.5 else "not above chance"
    below = [
        m
        for m in MODELS
        if labels_out[m] != "pending" and results[f"{m}/full/forced"]["auroc_ci"][1] < 0.5
    ]

    args.out.mkdir(parents=True, exist_ok=True)
    command = "uv run python -m eval.baseline" + ("" if args.split == "test" else " --split dev")
    payload = {
        "split": args.split,
        "generated_from_commit": git_head(),
        "command": command,
        "results": results,
        "above_chance": labels_out,
        "below_chance": below,
        "pending": pending,
    }
    (args.out / "baseline.json").write_text(json.dumps(payload, indent=2, default=float) + "\n")
    (args.out / "baseline.md").write_text(render(payload))
    print(json.dumps({"above_chance": labels_out, "pending": pending}, indent=2))
    return 0


def summary(payload: dict) -> list[str]:
    """Plain statements of the results; causes are not examined here."""
    res, labels = payload["results"], payload["above_chance"]
    if any(v == "pending" for v in labels.values()):
        return ["Pending: not every model has complete full-image neutral outputs."]
    above = [m for m, v in labels.items() if v == "above chance"]
    lines = [
        "- No model is above chance."
        if not above
        else f"- Above chance: {', '.join(above)}. Not above chance: "
        + ", ".join(m for m in labels if m not in above)
        + "."
    ]
    for m in payload["below_chance"]:
        r = res[f"{m}/full/forced"]
        lines.append(
            f"- {m} is significantly below chance: AUROC of `p_malignant` "
            f"{fmt(r['auroc'], r['auroc_ci'], False)}, so the whole 95% interval is below 0.5."
        )
    large, small = [], []
    for m in labels:
        r = res[f"{m}/full/forced"]
        mf, bf = r["malignant_first_malignant_ci"], r["benign_first_malignant_ci"]
        text = (
            f"{m} {fmt(r['malignant_first_malignant_rate'])} when malignant is listed first "
            f"and {fmt(r['benign_first_malignant_rate'])} when benign is listed first"
        )
        (large if mf[0] > bf[1] or bf[0] > mf[1] else small).append(text)
    if large:
        lines.append(
            "- The answer-order effect is large (the two orders' 95% intervals do not "
            "overlap). Malignant rate on full images: " + "; ".join(large) + "."
        )
    if small:
        lines.append("- No clear answer-order effect on full images: " + "; ".join(small) + ".")
    lines.append("- Causes are not examined in this report.")
    return lines


def render(payload: dict) -> str:
    res = payload["results"]
    out = [
        f"# Phase 4 baseline ({payload['split']} set, neutral prompt)",
        "",
        "This is a study of model behavior, not a diagnostic tool.",
        "",
        f"Generated by `{payload['command']}` at commit `{payload['generated_from_commit']}`. "
        "Rows give the commit and config SHA-256 that produced the model outputs. "
        "Abstentions (an assessment that is neither benign nor malignant) and parse "
        "failures (no readable assessment) are counted separately and are missing in "
        "the other metrics. "
        "Rates are over calls (3 paraphrases per case) with Wilson 95% intervals; "
        "AUROC, Brier and ECE use case-level means with case-bootstrap 95% intervals "
        "(10,000 resamples, seed 20261026).",
        "",
    ]
    out += ["## Summary", "", *summary(payload), ""]
    out += [
        "## Above chance",
        "",
        "Rule (docs/DEVIATIONS.md, entry 2): lower bound of the 95% interval of the AUROC "
        "of case-level `p_malignant` above 0.5, full image, neutral, forced format.",
        "",
        "| Model | Label | AUROC (95% CI) | Accuracy (95% CI) |",
        "|---|---|---|---|",
    ]
    for model, label in payload["above_chance"].items():
        r = res.get(f"{model}/full/forced", {})
        out.append(
            f"| {model} | {label} | {fmt(r.get('auroc'), r.get('auroc_ci'), False)} | "
            f"{fmt(r.get('accuracy'), r.get('accuracy_ci'))} |"
        )
    out += [
        "",
        "## Forced format by image kind",
        "",
        "| Model | Image | Calls | Abstentions | Parse failures | Errors | Malignant rate | "
        "Accuracy | "
        "AUROC p_malignant | AUROC verbal | Brier | ECE | BI-RADS consistent | "
        "BI-RADS 0 | Low mass | Outputs from |",
        "|---|---|---:|---|---|---:|---|---|---|---|---|---|---|---:|---|---|",
    ]
    for key, r in res.items():
        model, kind, answer_format = key.split("/")
        if answer_format != "forced":
            continue
        commits = ",".join(c[:7] for c in r["commits"])
        configs = ",".join(c[:8] for c in r["config_sha256"])
        cells = [
            model,
            kind,
            str(r["calls"]),
            fmt(r["abstention_rate"], r["abstention_ci"]),
            fmt(r["parse_failure_rate"], r["parse_failure_ci"]),
            str(r["errors"]),
            fmt(r["malignant_rate"], r["malignant_rate_ci"]),
            fmt(r["accuracy"], r["accuracy_ci"]),
            fmt(r["auroc"], r["auroc_ci"], False),
            fmt(r["auroc_verbal"], r["auroc_verbal_ci"], False),
            fmt(r["brier"], pct=False),
            fmt(r["ece"], pct=False),
            fmt(r["birads_consistent_rate"], r["birads_consistent_ci"]),
            str(r["birads_incomplete"]),
            fmt(r["low_mass_rate"]),
            f"`{commits}` / `{configs}`",
        ]
        out.append("| " + " | ".join(cells) + " |")
    out += [
        "",
        "## Plain format (abstention), neutral",
        "",
        "| Model | Image | Calls | Abstention rate | Parse failures | Malignant rate | Accuracy |",
        "|---|---|---:|---|---|---|---|",
    ]
    for key, r in res.items():
        model, kind, answer_format = key.split("/")
        if answer_format == "plain":
            cells = [
                model,
                kind,
                str(r["calls"]),
                fmt(r["abstention_rate"], r["abstention_ci"]),
                fmt(r["parse_failure_rate"], r["parse_failure_ci"]),
                fmt(r["malignant_rate"], r["malignant_rate_ci"]),
                fmt(r["accuracy"], r["accuracy_ci"]),
            ]
            out.append("| " + " | ".join(cells) + " |")
    out += [
        "",
        "## Answer order, forced format, neutral",
        "",
        "Malignant rate over answered calls by the option listed first in the prompt "
        "(docs/PREREGISTRATION.md, section 4, answer order). Descriptive only; the "
        "answer-order analysis is a Phase 6 secondary analysis.",
        "",
        "| Model | Image | Malignant listed first | Benign listed first | Difference |",
        "|---|---|---|---|---:|",
    ]
    for key, r in res.items():
        model, kind, answer_format = key.split("/")
        if answer_format == "forced":
            diff = r["malignant_first_malignant_rate"] - r["benign_first_malignant_rate"]
            cells = [
                model,
                kind,
                fmt(r["malignant_first_malignant_rate"], r["malignant_first_malignant_ci"]),
                fmt(r["benign_first_malignant_rate"], r["benign_first_malignant_ci"]),
                "n/a" if np.isnan(diff) else f"{100 * diff:+.1f} points",
            ]
            out.append("| " + " | ".join(cells) + " |")
    out += ["", "## Pending", ""]
    out += [f"- {p}" for p in payload["pending"]] or ["None."]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
