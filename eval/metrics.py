"""Metrics shared by the baseline and analysis scripts (Python side).

The Phase 6 statistics are written in R; these functions are the Python
implementations used for the Phase 4 baseline and for the R cross-check.
"""

from __future__ import annotations

import math

import numpy as np

BOOTSTRAP_SEED = 20261026
BOOTSTRAP_RESAMPLES = 10_000


def wilson(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson score 95% interval for a proportion."""
    if n == 0:
        return (math.nan, math.nan)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def auroc(scores: np.ndarray, labels: np.ndarray) -> float:
    """Area under the ROC curve (Mann-Whitney, ties count one half)."""
    scores, labels = np.asarray(scores, float), np.asarray(labels, bool)
    pos, neg = scores[labels], scores[~labels]
    if len(pos) == 0 or len(neg) == 0:
        return math.nan
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order))
    values = np.concatenate([pos, neg])[order]
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[i]:
            j += 1
        ranks[order[i : j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def brier(probs: np.ndarray, labels: np.ndarray) -> float:
    return float(np.mean((np.asarray(probs, float) - np.asarray(labels, float)) ** 2))


def ece(probs: np.ndarray, labels: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error with equal-width bins on [0, 1]."""
    probs, labels = np.asarray(probs, float), np.asarray(labels, float)
    idx = np.minimum((probs * bins).astype(int), bins - 1)
    total = 0.0
    for b in range(bins):
        mask = idx == b
        if mask.any():
            total += mask.mean() * abs(probs[mask].mean() - labels[mask].mean())
    return float(total)


def bootstrap_ci(
    statistic,
    n: int,
    resamples: int = BOOTSTRAP_RESAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    """Percentile 95% interval of statistic(indices) over case resamples."""
    rng = np.random.default_rng(seed)
    values = np.array([statistic(rng.integers(0, n, n)) for _ in range(resamples)])
    values = values[~np.isnan(values)]
    return (float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5)))


def birads_consistency(birads: int | None, malignant: bool | None) -> str | None:
    """consistent, inconsistent or incomplete (BI-RADS 0); None if unparsed."""
    if birads is None or malignant is None:
        return None
    if birads == 0:
        return "incomplete"
    if malignant:
        return "consistent" if birads in (4, 5, 6) else "inconsistent"
    return "consistent" if birads in (1, 2, 3) else "inconsistent"
