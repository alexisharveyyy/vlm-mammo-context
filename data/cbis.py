"""Shared CBIS-DDSM metadata: source CSVs and the per-image table.

The four case description CSVs list one row per abnormality. Several rows can
point to the same full mammogram series, so build_images() collapses them to
one row per full-image series (one view of one breast of one patient).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CSV_BASE_URL = "https://www.cancerimagingarchive.net/wp-content/uploads/"
CSV_FILES = {
    ("mass", "train"): "mass_case_description_train_set.csv",
    ("mass", "test"): "mass_case_description_test_set.csv",
    ("calc", "train"): "calc_case_description_train_set.csv",
    ("calc", "test"): "calc_case_description_test_set.csv",
}

# BENIGN_WITHOUT_CALLBACK is benign for the binary label; the original value
# is kept in the manifests.
BINARY_LABEL = {
    "MALIGNANT": "malignant",
    "BENIGN": "benign",
    "BENIGN_WITHOUT_CALLBACK": "benign",
}


def load_rows(csv_dir: Path) -> pd.DataFrame:
    """All abnormality rows from the four CSVs with normalized columns."""
    frames = []
    for (kind, split), name in sorted(CSV_FILES.items()):
        df = pd.read_csv(csv_dir / name, dtype=str)
        # Column names differ between files ("breast_density" vs "breast density").
        df.columns = [c.strip().replace(" ", "_") for c in df.columns]
        df = df.apply(lambda col: col.str.strip())
        df["abnormality_type"] = kind
        df["official_split"] = split
        frames.append(df)
    rows = pd.concat(frames, ignore_index=True)
    # image file path: <DICOM PatientID>/<StudyInstanceUID>/<SeriesInstanceUID>/<file>.dcm
    parts = rows["image_file_path"].str.split("/")
    rows["study_instance_uid"] = parts.str[1]
    rows["series_instance_uid"] = parts.str[2]
    # ROI crop and mask series. They are often the same two-instance series,
    # with the crop/mask order inconsistent between files, so both are kept.
    rows["crop_series_instance_uid"] = rows["cropped_image_file_path"].str.split("/").str[2]
    rows["mask_series_instance_uid"] = rows["ROI_mask_file_path"].str.split("/").str[2]
    rows["label"] = rows["pathology"].map(BINARY_LABEL)
    if rows["label"].isna().any():
        bad = sorted(rows.loc[rows["label"].isna(), "pathology"].unique())
        raise ValueError(f"unknown pathology values: {bad}")
    rows["assessment"] = rows["assessment"].astype(int)
    return rows


def _join(values: pd.Series) -> str:
    return ";".join(sorted(set(values)))


def build_images(rows: pd.DataFrame) -> pd.DataFrame:
    """One row per full mammogram series."""
    images = (
        rows.groupby("series_instance_uid", sort=True)
        .agg(
            patient_id=("patient_id", "first"),
            side=("left_or_right_breast", "first"),
            view=("image_view", "first"),
            study_instance_uid=("study_instance_uid", "first"),
            abnormality_type=("abnormality_type", _join),
            label=("label", _join),
            pathology=("pathology", _join),
            birads_assessment=("assessment", "max"),
            assessments=("assessment", lambda s: ";".join(str(v) for v in sorted(s))),
            breast_density=("breast_density", _join),
            subtlety=("subtlety", _join),
            n_abnormalities=("abnormality_id", "size"),
            official_split=("official_split", _join),
            crop_series_instance_uids=("crop_series_instance_uid", _join),
            mask_series_instance_uids=("mask_series_instance_uid", _join),
        )
        .reset_index()
    )
    for col in ["patient_id", "left_or_right_breast", "image_view", "study_instance_uid"]:
        n = rows.groupby("series_instance_uid")[col].nunique()
        if (n > 1).any():
            raise ValueError(f"series with inconsistent {col}: {list(n[n > 1].index)[:5]}")
    return images


def idc_index_table() -> pd.DataFrame:
    """CBIS-DDSM rows of the IDC index bundled with idc-index."""
    from idc_index import IDCClient

    index = IDCClient().index
    return index[index["collection_id"] == "cbis_ddsm"]


def idc_series(series_uids: list[str]) -> pd.DataFrame:
    """IDC index rows (crdc_series_uuid, size) for the given SeriesInstanceUIDs."""
    index = idc_index_table()
    sel = index[index["SeriesInstanceUID"].isin(series_uids)]
    missing = set(series_uids) - set(sel["SeriesInstanceUID"])
    if missing:
        raise ValueError(f"{len(missing)} series not in the IDC index, e.g. {sorted(missing)[:3]}")
    return sel[["SeriesInstanceUID", "crdc_series_uuid", "instanceCount", "series_size_MB"]]
