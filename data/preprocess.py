"""Convert the dev and test DICOMs to full-resolution 8-bit master PNGs.

    python data/preprocess.py            # write PNGs, verify against png_sha256.csv
    python data/preprocess.py --record   # first run only: write png_sha256.csv

Processing, identical for every image:
  1. read the 16-bit MONOCHROME2 pixels (no VOI LUT or window tags exist)
  2. fixed linear window: 0..65535 maps to 0..255, in exact integer arithmetic
     with round-half-up
  3. no resizing, flipping, cropping or per-image contrast adjustment; each
     model adapter resizes the master to its own input size
PNGs are written with fixed settings (zlib level 9, no optimize pass, no
metadata). Two checksums are recorded: SHA-256 of the PNG file and SHA-256 of
the decoded pixels, which does not depend on the PNG encoder.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pydicom
from PIL import Image

MANIFESTS = Path("data/manifests")
CHECKSUMS = MANIFESTS / "png_sha256.csv"
PNG_OPTIONS = {"format": "PNG", "compress_level": 9, "optimize": False}


def window(pixels: np.ndarray) -> np.ndarray:
    """16-bit pixels to 8-bit: round(x * 255 / 65535), exact."""
    if pixels.dtype != np.uint16:
        raise ValueError(f"expected uint16 pixels, got {pixels.dtype}")
    x = pixels.astype(np.uint32)
    return ((x * 255 + 32767) // 65535).astype(np.uint8)


def read_pixels(path: Path) -> np.ndarray:
    ds = pydicom.dcmread(path)
    if ds.PhotometricInterpretation != "MONOCHROME2":
        raise ValueError(f"{path}: unexpected {ds.PhotometricInterpretation}")
    return ds.pixel_array


def pixel_sha256(array: np.ndarray) -> str:
    header = f"{array.dtype.str}{array.shape}".encode()
    return hashlib.sha256(header + np.ascontiguousarray(array).tobytes()).hexdigest()


def write_png(array: np.ndarray, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(array).save(path, **PNG_OPTIONS)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dicom-root", type=Path, default=Path("data/raw/dicom"))
    parser.add_argument("--out", type=Path, default=Path("data/png"))
    parser.add_argument("--record", action="store_true", help="write png_sha256.csv")
    args = parser.parse_args()

    sources = pd.read_csv(MANIFESTS / "dicom_checksums.csv", dtype=str).sort_values("case_id")
    expected = {}
    if not args.record:
        table = pd.read_csv(CHECKSUMS, dtype=str)
        expected = {r.case_id: (r.sha256, r.pixel_sha256) for r in table.itertuples()}

    rows, failures = [], 0
    for src in sources.itertuples():
        array = window(read_pixels(args.dicom_root / src.series_instance_uid / src.object))
        sha = write_png(array, args.out / f"{src.case_id}.png")
        pix = pixel_sha256(array)
        rows.append(
            {
                "case_id": src.case_id,
                "width": array.shape[1],
                "height": array.shape[0],
                "sha256": sha,
                "pixel_sha256": pix,
            }
        )
        if not args.record and expected.get(src.case_id) != (sha, pix):
            print(f"BAD {src.case_id}")
            failures += 1

    if args.record:
        pd.DataFrame(rows).to_csv(CHECKSUMS, index=False, lineterminator="\n")
    print(f"{len(rows) - failures}/{len(rows)} PNGs {'recorded' if args.record else 'verified'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
