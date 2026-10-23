"""Load master PNGs and resize them for a model.

Only the full image or the ROI crop of a case can be loaded; ROI masks are
never converted to PNG and load_case_image refuses any binary image, so a
mask cannot reach a model. Every load checks the pixel SHA-256 against the
committed manifest.

Resize policies (configs/models.yaml, key `resize`):
  max_pixels  scale down, keeping the aspect ratio, until width * height is at
              most max_pixels; then round each side down to a multiple of
              `multiple_of`. Never upscales except to reach `min_side`.
  letterbox   scale so the long side is `size`, keeping the aspect ratio, and
              pad to size x size with black (the image background is black).
  long_side   scale so the long side is `size`, keeping the aspect ratio.
Resampling is Lanczos on the 8-bit master. The result is converted to RGB by
copying the gray channel, since every model expects three channels.
"""

from __future__ import annotations

import hashlib
import math
from functools import cache
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "full": (ROOT / "data" / "png", ROOT / "data" / "manifests" / "png_sha256.csv"),
    "roi": (ROOT / "data" / "png_roi", ROOT / "data" / "manifests" / "roi_checksums.csv"),
}


@cache
def expected_pixels(kind: str) -> dict[str, str]:
    table = pd.read_csv(SOURCES[kind][1], dtype=str)
    return dict(zip(table["case_id"], table["pixel_sha256"], strict=True))


def pixel_sha256(array: np.ndarray) -> str:
    header = f"{array.dtype.str}{array.shape}".encode()
    return hashlib.sha256(header + np.ascontiguousarray(array).tobytes()).hexdigest()


def load_case_image(case_id: str, kind: str = "full", verify: bool = True) -> Image.Image:
    """The 8-bit grayscale master of a case: kind is "full" or "roi"."""
    if kind not in SOURCES:
        raise ValueError(f"kind must be one of {sorted(SOURCES)}, not {kind!r}")
    path = SOURCES[kind][0] / f"{case_id}.png"
    with Image.open(path) as im:
        im.load()
        image = im.copy()
    array = np.asarray(image)
    if image.mode != "L":
        raise ValueError(f"{path}: expected an 8-bit grayscale PNG, got {image.mode}")
    if np.unique(array).size <= 2:
        raise ValueError(f"{path}: binary image (looks like a mask); refusing to load")
    if verify and pixel_sha256(array) != expected_pixels(kind)[case_id]:
        raise ValueError(f"{path}: pixel checksum does not match the manifest")
    return image


def _scaled(image: Image.Image, width: int, height: int) -> Image.Image:
    if (width, height) == image.size:
        return image.copy()
    return image.resize((width, height), Image.Resampling.LANCZOS)


def resize(image: Image.Image, policy: dict) -> Image.Image:
    """Resize a grayscale master according to a policy, return RGB."""
    w, h = image.size
    kind = policy["type"]
    if kind == "max_pixels":
        m = policy.get("multiple_of", 1)
        scale = min(1.0, math.sqrt(policy["max_pixels"] / (w * h)))
        nw, nh = (max(m, int(w * scale) // m * m), max(m, int(h * scale) // m * m))
        min_side = policy.get("min_side", 0)
        if min(nw, nh) < min_side:
            up = min_side / min(nw, nh)
            nw, nh = math.ceil(nw * up / m) * m, math.ceil(nh * up / m) * m
        out = _scaled(image, nw, nh)
    elif kind in ("letterbox", "long_side"):
        size = policy["size"]
        scale = size / max(w, h)
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        out = _scaled(image, nw, nh)
        if kind == "letterbox":
            canvas = Image.new("L", (size, size), 0)
            canvas.paste(out, ((size - nw) // 2, (size - nh) // 2))
            out = canvas
    else:
        raise ValueError(f"unknown resize policy {kind!r}")
    return out.convert("RGB")
