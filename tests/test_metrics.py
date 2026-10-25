"""Metric implementations against known values."""

import math

import numpy as np
import pytest

from eval import metrics


def test_wilson_known_values():
    lo, hi = metrics.wilson(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-4) and hi == pytest.approx(0.5962, abs=1e-4)
    assert metrics.wilson(0, 10)[0] == 0.0
    assert all(math.isnan(x) for x in metrics.wilson(0, 0))


def test_auroc_perfect_random_and_ties():
    labels = np.array([0, 0, 1, 1], bool)
    assert metrics.auroc(np.array([0.1, 0.2, 0.8, 0.9]), labels) == 1.0
    assert metrics.auroc(np.array([0.9, 0.8, 0.2, 0.1]), labels) == 0.0
    assert metrics.auroc(np.full(4, 0.5), labels) == 0.5
    assert metrics.auroc(np.array([0.1, 0.5, 0.5, 0.9]), labels) == pytest.approx(0.875)


def test_auroc_matches_pairwise_definition():
    rng = np.random.default_rng(1)
    scores = rng.integers(0, 5, 60).astype(float)
    labels = rng.integers(0, 2, 60).astype(bool)
    pos, neg = scores[labels], scores[~labels]
    pairwise = np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg])
    assert metrics.auroc(scores, labels) == pytest.approx(pairwise)


def test_brier_and_ece():
    assert metrics.brier(np.array([1.0, 0.0]), np.array([1, 0])) == 0.0
    assert metrics.brier(np.array([0.5, 0.5]), np.array([1, 0])) == 0.25
    assert metrics.ece(np.array([0.9, 0.9, 0.1, 0.1]), np.array([1, 1, 0, 0])) == pytest.approx(0.1)


def test_bootstrap_ci_is_reproducible():
    data = np.arange(100, dtype=float)
    a = metrics.bootstrap_ci(lambda idx: data[idx].mean(), 100, resamples=500)
    b = metrics.bootstrap_ci(lambda idx: data[idx].mean(), 100, resamples=500)
    assert a == b and a[0] < 49.5 < a[1]


def test_birads_consistency():
    assert metrics.birads_consistency(4, True) == "consistent"
    assert metrics.birads_consistency(2, True) == "inconsistent"
    assert metrics.birads_consistency(3, False) == "consistent"
    assert metrics.birads_consistency(5, False) == "inconsistent"
    assert metrics.birads_consistency(0, False) == "incomplete"
    assert metrics.birads_consistency(None, True) is None
