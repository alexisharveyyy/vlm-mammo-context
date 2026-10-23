"""ROI crop selection and crop/mask identification for dev and test cases.

One abnormality per case: all abnormalities on a case image share its binary
label (and, in this data, its pathology), so the label comes from each of
them. The rule picks the one with the highest BI-RADS assessment, which is the
case's birads_assessment, and breaks ties by the lowest abnormality id.

Crop and mask are told apart by pixel content, never by series or instance
order: the mask is the image whose pixels take at most two values.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pydicom


def select_abnormalities(cases: pd.DataFrame, rows: pd.DataFrame) -> pd.DataFrame:
    """One abnormality row per case, with its crop and mask series."""
    rows = rows.copy()
    rows["abnormality_number"] = rows["abnormality_id"].astype(int)
    merged = cases[["case_id", "series_instance_uid", "label", "birads_assessment"]].merge(
        rows, on="series_instance_uid", suffixes=("", "_row")
    )
    if (merged["label"] != merged["label_row"]).any():
        raise ValueError("an abnormality disagrees with its case label")
    chosen = (
        merged.sort_values(
            ["case_id", "assessment", "abnormality_number"], ascending=[True, False, True]
        )
        .groupby("case_id", sort=True)
        .head(1)
    )
    if (chosen["assessment"] != chosen["birads_assessment"].astype(int)).any():
        raise ValueError("selected abnormality does not carry the case BI-RADS")
    counts = merged.groupby("case_id").size().rename("n_abnormalities")
    out = chosen.set_index("case_id").join(counts).reset_index()
    out["csv_crop_file"] = out["cropped_image_file_path"].str.split("/").str[-1]
    out["csv_mask_file"] = out["ROI_mask_file_path"].str.split("/").str[-1]
    return out[
        [
            "case_id",
            "abnormality_number",
            "n_abnormalities",
            "assessment",
            "pathology",
            "crop_series_instance_uid",
            "mask_series_instance_uid",
            "csv_crop_file",
            "csv_mask_file",
        ]
    ].rename(columns={"abnormality_number": "abnormality_id"})


def is_binary(pixels: np.ndarray) -> bool:
    return np.unique(pixels).size <= 2


def identify(paths: list[Path]) -> tuple[Path, Path]:
    """(crop, mask) among the candidate DICOM files of one abnormality."""
    binary = [p for p in paths if is_binary(pydicom.dcmread(p).pixel_array)]
    other = [p for p in paths if p not in binary]
    if len(binary) != 1 or len(other) != 1:
        raise ValueError(f"expected one mask and one crop, got {len(binary)} and {len(other)}")
    return other[0], binary[0]
