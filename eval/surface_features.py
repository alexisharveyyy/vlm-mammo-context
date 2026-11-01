"""Exploratory analysis 1 (docs/EXPLORATORY.md): surface features and Qwen3-VL's answers.

    uv run python -m eval.surface_features [--images data/png]

EXPLORATORY. Not part of the pre-specified analysis plan frozen at prereg-v1.

Reads only tier T0 outputs: Qwen3-VL, full images, neutral prompt, forced
format (runs/qwen3_vl_8b/full/neutral/p1-p3.jsonl). Asks which surface
features of the image and case go with the model's case-level p_malignant,
whose AUROC is below chance (reports/baseline.md). Features: image width,
height and megapixels (from data/manifests/png_sha256.csv); mean intensity
over the image and over the breast region, the breast area fraction and the
breast intensity spread (from the local PNG masters); abnormality type,
breast density, subtlety and side (from the manifest).

Per-case features are derived from pixels, so they are cached under data/
(never committed) and only aggregate statistics are written to
reports/exploratory/surface_features.md and .json. Intervals use a case
bootstrap (2,000 resamples, seed 20261026) and are unadjusted.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from eval import metrics

ROOT = Path(__file__).resolve().parents[1]
MODEL = "qwen3_vl_8b"
RESAMPLES = 2000
# Pixels at or above this 8-bit level count as breast; the film background is near 0.
BREAST_LEVEL = 16
FEATURES = [
    "width",
    "height",
    "megapixels",
    "mean_intensity",
    "breast_fraction",
    "breast_mean",
    "breast_sd",
    "is_mass",
    "breast_density",
    "subtlety",
    "is_left",
]
LABEL = "EXPLORATORY: not part of the pre-specified analysis plan"


def image_features(path: Path) -> dict:
    a = np.asarray(Image.open(path).convert("L"), dtype=np.float64)
    breast = a[a >= BREAST_LEVEL]
    return {
        "mean_intensity": a.mean() / 255,
        "breast_fraction": breast.size / a.size,
        "breast_mean": breast.mean() / 255 if breast.size else np.nan,
        "breast_sd": breast.std() / 255 if breast.size else np.nan,
    }


def load_features(images: Path, cache: Path, cases: pd.DataFrame) -> pd.DataFrame:
    """Per-case features, from the cache when it covers every case."""
    if cache.exists():
        cached = pd.read_csv(cache, dtype={"case_id": str})
        if set(cases["case_id"]) <= set(cached["case_id"]):
            return cached.set_index("case_id").loc[cases["case_id"]].reset_index()
    rows = [{"case_id": c} | image_features(images / f"{c}.png") for c in cases["case_id"]]
    out = pd.DataFrame(rows)
    cache.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(cache, index=False)
    return out


def load_answers(runs: Path) -> pd.DataFrame:
    """Case-level y and p_malignant over valid answers (plan section 5)."""
    rows = []
    for p in (1, 2, 3):
        for line in (runs / MODEL / "full" / "neutral" / f"p{p}.jsonl").read_text().splitlines():
            r = json.loads(line)
            assert r["condition"] == "neutral" and r["answer_format"] == "forced"
            if r["split"] != "test" or r["error"] or not (r["parse"] and r["parse"]["ok"]):
                continue
            rows.append(
                {"case_id": r["case_id"], "y": float(r["malignant"]), "p": r["p_malignant"]}
            )
    return pd.DataFrame(rows).groupby("case_id").mean()


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    ok = ~(np.isnan(x) | np.isnan(y))
    rx, ry = pd.Series(x[ok]).rank().to_numpy(), pd.Series(y[ok]).rank().to_numpy()
    if rx.std() == 0 or ry.std() == 0:
        return np.nan
    return float(np.corrcoef(rx, ry)[0, 1])


def standardized_ols(df: pd.DataFrame, columns: list[str]) -> np.ndarray:
    """Coefficients of p on the label and standardized columns (intercept dropped)."""
    x = df[columns].to_numpy(dtype=float)
    sd = x.std(axis=0)
    x = (x - x.mean(axis=0)) / np.where(sd == 0, 1, sd)
    design = np.column_stack([np.ones(len(df)), df["truth"].to_numpy(dtype=float), x])
    coef, *_ = np.linalg.lstsq(design, df["p"].to_numpy(), rcond=None)
    return coef[1:]


def bootstrap(stat, n: int) -> np.ndarray:
    rng = np.random.default_rng(metrics.BOOTSTRAP_SEED)
    return np.array([stat(rng.integers(0, n, n)) for _ in range(RESAMPLES)])


def ci(values: np.ndarray) -> tuple[float, float]:
    v = values[np.isfinite(values)] if values.ndim == 1 else values
    return float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def analyze(df: pd.DataFrame) -> dict:
    n = len(df)
    truth = df["truth"].to_numpy()
    p = df["p"].to_numpy()
    out = {
        "cases": n,
        "auroc": metrics.auroc(p, truth),
        "auroc_ci": ci(bootstrap(lambda i: metrics.auroc(p[i], truth[i]), n)),
        "auroc_by_type": {},
        "features": {},
    }
    for kind in ("mass", "calc"):
        sel = (df["abnormality_type"] == kind).to_numpy()
        ps, ts = p[sel], truth[sel]
        out["auroc_by_type"][kind] = {
            "cases": int(sel.sum()),
            "auroc": metrics.auroc(ps, ts),
            "auroc_ci": ci(
                bootstrap(lambda i, ps=ps, ts=ts: metrics.auroc(ps[i], ts[i]), int(sel.sum()))
            ),
        }
    for f in FEATURES:
        ok = df[f].notna().to_numpy()
        x, px, tx = df[f].to_numpy(dtype=float)[ok], p[ok], truth[ok]
        m = int(ok.sum())
        out["features"][f] = {
            "cases": m,
            "spearman_with_p": spearman(x, px),
            "spearman_ci": ci(bootstrap(lambda i, x=x, px=px: spearman(x[i], px[i]), m)),
            "auroc_for_label": metrics.auroc(x, tx),
            "auroc_for_label_ci": ci(
                bootstrap(lambda i, x=x, tx=tx: metrics.auroc(x[i], tx[i]), m)
            ),
        }
    continuous = [f for f in FEATURES if df[f].nunique() > 1]
    # The regression uses cases with every feature present.
    df = df.dropna(subset=continuous).reset_index(drop=True)
    n = len(df)
    alone = standardized_ols(df, [])[0]
    adjusted = standardized_ols(df, continuous)
    boot_alone = bootstrap(lambda i: standardized_ols(df.iloc[i], [])[0], n)
    boot_adjusted = bootstrap(lambda i: standardized_ols(df.iloc[i], continuous), n)
    out["regression"] = {
        "cases": n,
        "label_alone": alone,
        "label_alone_ci": ci(boot_alone),
        "label_adjusted": adjusted[0],
        "label_adjusted_ci": ci(boot_adjusted[:, 0]),
        "coefficients": {
            f: {"estimate": adjusted[k + 1], "ci": ci(boot_adjusted[:, k + 1])}
            for k, f in enumerate(continuous)
        },
    }
    return out


def fmt(x: float, d: int = 3) -> str:
    return "n/a" if x is None or not np.isfinite(x) else f"{x:.{d}f}"


def fmt_ci(x: float, lo_hi) -> str:
    return f"{fmt(x)} ({fmt(lo_hi[0])} to {fmt(lo_hi[1])})"


def render(res: dict, meta: dict) -> str:
    lines = [
        "# Exploratory analysis 1: surface features and Qwen3-VL's answers",
        "",
        f"**{LABEL}** (`docs/EXPLORATORY.md`, entry 1). No result here is a test of the",
        "plan's hypotheses. Intervals are unadjusted 95% case-bootstrap percentile intervals",
        f"({RESAMPLES:,} resamples, seed {metrics.BOOTSTRAP_SEED}).",
        "",
        f"Generated by `{meta['command']}` at commit `{meta['commit']}`. Input: tier T0 only,",
        f"Qwen3-VL, full images, `neutral`, forced format; {res['cases']} cases with a valid",
        "answer. Case-level `p_malignant` averages the valid paraphrases. Per-case features",
        "come from the local PNG masters and are not committed; this report holds",
        "aggregates only.",
        "",
        "## Discrimination",
        "",
        f"AUROC of case-level `p_malignant`: {fmt_ci(res['auroc'], res['auroc_ci'])}.",
        "",
        "| Abnormality | Cases | AUROC |",
        "|---|---:|---|",
    ]
    for kind, r in res["auroc_by_type"].items():
        lines.append(f"| {kind} | {r['cases']} | {fmt_ci(r['auroc'], r['auroc_ci'])} |")
    lines += [
        "",
        "## Features",
        "",
        "Spearman correlation of each feature with case-level `p_malignant`, and the AUROC",
        "of the feature itself for the biopsy label (0.5 = unrelated to the label).",
        "",
        "| Feature | Cases | Spearman with p_malignant | AUROC of feature for label |",
        "|---|---:|---|---|",
    ]
    for f, r in res["features"].items():
        lines.append(
            f"| {f} | {r['cases']} | {fmt_ci(r['spearman_with_p'], r['spearman_ci'])} | "
            f"{fmt_ci(r['auroc_for_label'], r['auroc_for_label_ci'])} |"
        )
    reg = res["regression"]
    lines += [
        "",
        "## Label effect with and without the features",
        "",
        "Least squares of case-level `p_malignant` on the label (malignant = 1) and the",
        f"standardized features, on the {reg['cases']} cases with every feature present.",
        "A negative label coefficient is the below-chance pattern;",
        "if it moves toward 0 when the features are added, the features account for part",
        "of it.",
        "",
        f"- Label coefficient alone: {fmt_ci(reg['label_alone'], reg['label_alone_ci'])}",
        "- Label coefficient with the features: "
        + fmt_ci(reg["label_adjusted"], reg["label_adjusted_ci"]),
        "",
        "| Feature (standardized) | Coefficient |",
        "|---|---|",
    ]
    for f, r in reg["coefficients"].items():
        lines.append(f"| {f} | {fmt_ci(r['estimate'], r['ci'])} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--images", type=Path, default=ROOT / "data" / "png")
    ap.add_argument("--runs", type=Path, default=ROOT / "runs")
    ap.add_argument(
        "--cache", type=Path, default=ROOT / "data" / "derived" / "surface_features.csv"
    )
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "exploratory")
    args = ap.parse_args()

    manifests = ROOT / "data" / "manifests"
    cases = pd.read_csv(manifests / "test.csv", dtype=str)
    sizes = pd.read_csv(manifests / "png_sha256.csv", dtype={"case_id": str})
    df = (
        cases.merge(sizes[["case_id", "width", "height"]], on="case_id")
        .merge(load_features(args.images, args.cache, cases), on="case_id")
        .merge(load_answers(args.runs), left_on="case_id", right_index=True)
    )
    df["truth"] = (df["label"] == "malignant").astype(float)
    df["megapixels"] = df["width"] * df["height"] / 1e6
    df["is_mass"] = (df["abnormality_type"] == "mass").astype(float)
    df["is_left"] = (df["side"] == "LEFT").astype(float)
    for c in ("breast_density", "subtlety"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    res = analyze(df)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    meta = {"command": "uv run python -m eval.surface_features", "commit": commit}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "surface_features.md").write_text(render(res, meta))
    (args.out / "surface_features.json").write_text(
        json.dumps({"label": LABEL, **meta, "results": res}, indent=2, default=float) + "\n"
    )
    print(f"{LABEL}: {res['cases']} cases -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
