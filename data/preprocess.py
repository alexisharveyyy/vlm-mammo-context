"""Convert the dev and test DICOMs to full-resolution 8-bit master PNGs.

    python data/preprocess.py            # write PNGs, verify against png_sha256.csv
    python data/preprocess.py --record   # first run only: write png_sha256.csv
    python data/preprocess.py --roi      # ROI crops, verify against roi_checksums.csv

Processing, identical for every image:
  1. read the 16-bit MONOCHROME2 pixels (no VOI LUT or window tags exist)
  2. fixed linear window: 0..65535 maps to 0..255, in exact integer arithmetic
     with round-half-up
  3. no resizing, flipping, cropping or per-image contrast adjustment; each
     model adapter resizes the master to its own input size
PNGs are written with fixed settings (zlib level 9, no optimize pass, no
metadata). Two checksums are recorded: SHA-256 of the PNG file and SHA-256 of
the decoded pixels, which does not depend on the PNG encoder.

With --roi, the crop of each case's selected abnormality is identified by
content (the mask is the binary image; see roi.py) and converted with the
same settings. roi_checksums.csv records which object is the crop and the
mask, whether the CSV had them the other way round, and the PNG checksums.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import cbis
import numpy as np
import pandas as pd
import pydicom
import roi
from PIL import Image

MANIFESTS = Path("data/manifests")
CHECKSUMS = MANIFESTS / "png_sha256.csv"
ROI_CHECKSUMS = MANIFESTS / "roi_checksums.csv"
DEFAULTS = {  # (dicom root, PNG folder) for full images and for --roi
    False: (Path("data/raw/dicom"), Path("data/png")),
    True: (Path("data/raw/roi"), Path("data/png_roi")),
}
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


def csv_order_swapped(case: pd.DataFrame, mask: str) -> str:
    """Whether the CSV paths name the mask series as the crop series.

    Only defined when crop and mask are separate series. In a shared series
    both instances have InstanceNumber 1 and IDC names files by UUID, so the
    CSV file names (000000, 000001) cannot be mapped to an instance.
    """
    first = case.iloc[0]
    if first.crop_series_instance_uid == first.mask_series_instance_uid:
        return "undetermined"
    series_of = dict(zip(case["object"], case["series_instance_uid"], strict=True))
    return "yes" if series_of[mask] == first.crop_series_instance_uid else "no"


def convert_roi(root: Path, out: Path, record: bool) -> int:
    objects = pd.read_csv(MANIFESTS / "roi_dicom_checksums.csv", dtype=str)
    expected = {}
    if not record:
        table = pd.read_csv(ROI_CHECKSUMS, dtype=str)
        expected = {r.case_id: (r.sha256, r.pixel_sha256) for r in table.itertuples()}

    index = cbis.idc_index_table()
    description = dict(zip(index["SeriesInstanceUID"], index["SeriesDescription"], strict=True))

    rows, failures = [], 0
    for case_id, case in objects.groupby("case_id", sort=True):
        paths = [root / r.series_instance_uid / r.object for r in case.itertuples()]
        crop_path, mask_path = roi.identify(paths)
        array = window(read_pixels(crop_path))
        sha = write_png(array, out / f"{case_id}.png")
        pix = pixel_sha256(array)
        first = case.iloc[0]
        rows.append(
            {
                "case_id": case_id,
                "abnormality_id": first.abnormality_id,
                "n_abnormalities": first.n_abnormalities,
                "shared_series": first.crop_series_instance_uid == first.mask_series_instance_uid,
                "crop_series_instance_uid": crop_path.parent.name,
                "crop_object": crop_path.name,
                "mask_series_instance_uid": mask_path.parent.name,
                "mask_object": mask_path.name,
                "csv_order_swapped": csv_order_swapped(case, mask_path.name),
                "idc_crop_series_description": description[crop_path.parent.name],
                "idc_mask_series_description": description[mask_path.parent.name],
                "width": array.shape[1],
                "height": array.shape[0],
                "sha256": sha,
                "pixel_sha256": pix,
            }
        )
        if not record and expected.get(case_id) != (sha, pix):
            print(f"BAD {case_id}")
            failures += 1

    if record:
        pd.DataFrame(rows).to_csv(ROI_CHECKSUMS, index=False, lineterminator="\n")
    print(f"{len(rows) - failures}/{len(rows)} ROI PNGs {'recorded' if record else 'verified'}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dicom-root", type=Path, help="default depends on --roi")
    parser.add_argument("--out", type=Path, help="default depends on --roi")
    parser.add_argument("--record", action="store_true", help="write the checksum manifest")
    parser.add_argument("--roi", action="store_true", help="convert ROI crops instead")
    args = parser.parse_args()

    default_root, default_out = DEFAULTS[args.roi]
    args.dicom_root = args.dicom_root or default_root
    args.out = args.out or default_out
    if args.roi:
        return convert_roi(args.dicom_root, args.out, args.record)

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
