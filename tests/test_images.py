"""Resize policies and the mask guard."""

import numpy as np
import pytest
from PIL import Image

from models import images


def gray(w, h, seed=0):
    rng = np.random.default_rng(seed)
    return Image.fromarray(rng.integers(0, 256, (h, w), dtype=np.uint8))


def test_max_pixels_keeps_aspect_and_multiple():
    out = images.resize(
        gray(3000, 5000), {"type": "max_pixels", "max_pixels": 1_000_000, "multiple_of": 28}
    )
    w, h = out.size
    assert w * h <= 1_000_000 and w % 28 == 0 and h % 28 == 0
    assert abs(w / h - 0.6) < 0.02 and out.mode == "RGB"


def test_max_pixels_never_upscales_but_honors_min_side():
    small = gray(100, 300)
    out = images.resize(small, {"type": "max_pixels", "max_pixels": 10**7, "multiple_of": 28})
    assert out.size == (84, 280)
    out = images.resize(
        small, {"type": "max_pixels", "max_pixels": 10**7, "multiple_of": 28, "min_side": 224}
    )
    assert min(out.size) >= 224 and out.size[0] % 28 == 0


def test_letterbox_pads_to_square_without_distortion():
    out = images.resize(gray(2000, 4000), {"type": "letterbox", "size": 896})
    assert out.size == (896, 896)
    arr = np.asarray(out)[:, :, 0]
    assert arr[:, :200].max() == 0 and arr[:, -200:].max() == 0
    assert arr[:, 300:600].max() > 0


def test_long_side():
    assert images.resize(gray(1000, 4000), {"type": "long_side", "size": 448}).size == (112, 448)


def test_grayscale_copied_to_three_channels():
    out = np.asarray(images.resize(gray(50, 50), {"type": "long_side", "size": 50}))
    assert (out[:, :, 0] == out[:, :, 1]).all() and (out[:, :, 1] == out[:, :, 2]).all()


def test_unknown_policy():
    with pytest.raises(ValueError):
        images.resize(gray(10, 10), {"type": "crop"})


def test_refuses_binary_images(tmp_path, monkeypatch):
    mask = np.zeros((20, 20), dtype=np.uint8)
    mask[5:10, 5:10] = 255
    Image.fromarray(mask).save(tmp_path / "X.png")
    monkeypatch.setitem(images.SOURCES, "roi", (tmp_path, tmp_path / "unused.csv"))
    with pytest.raises(ValueError, match="mask"):
        images.load_case_image("X", "roi", verify=False)


def test_rejects_unknown_kind():
    with pytest.raises(ValueError):
        images.load_case_image("P_00001_LEFT_MLO", "mask")
