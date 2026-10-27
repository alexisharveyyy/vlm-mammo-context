"""Tolerance of the R and Python cross-check."""

import math

from eval.crosscheck import close


def test_close_allows_rounding_only():
    assert close(0.123456789012345, 0.1234567890123451)
    assert not close(0.4463333, 0.4463343)
    assert close(500, "500")
    assert close(math.nan, "") and close(None, math.nan)
    assert not close(math.nan, 0.0)
