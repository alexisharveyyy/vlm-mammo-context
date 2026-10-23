"""Preprocessing is fixed and deterministic."""

import numpy as np
import preprocess
import pytest
from PIL import Image


def test_window_exact_integer_mapping():
    pixels = np.array([[0, 128, 129, 257, 32767, 65535]], dtype=np.uint16)
    assert preprocess.window(pixels).tolist() == [[0, 0, 1, 1, 127, 255]]


def test_window_rejects_other_dtypes():
    with pytest.raises(ValueError):
        preprocess.window(np.zeros((2, 2), dtype=np.int32))


def test_full_resolution_and_bytes_deterministic(tmp_path):
    rng = np.random.default_rng(0)
    array = preprocess.window(rng.integers(0, 65536, size=(1500, 900), dtype=np.uint16))
    a = preprocess.write_png(array, tmp_path / "a.png")
    b = preprocess.write_png(array, tmp_path / "b.png")
    assert a == b
    with Image.open(tmp_path / "a.png") as im:
        assert im.size == (900, 1500) and im.mode == "L"
        assert preprocess.pixel_sha256(np.asarray(im)) == preprocess.pixel_sha256(array)
