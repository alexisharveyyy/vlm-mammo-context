"""Download CBIS-DDSM metadata and the dev and test DICOMs, and verify checksums.

    python data/download.py metadata            # four case description CSVs from TCIA
    python data/download.py images              # dev and test full mammograms from IDC
    python data/download.py images --record     # first run only: write dicom_checksums.csv
    python data/download.py roi                 # ROI crop and mask series from IDC
    python data/download.py roi --record        # first run only: write roi_dicom_checksums.csv

CSV checksums are verified against data/manifests/splits.json. DICOM checksums
are verified against data/manifests/dicom_checksums.csv: size and MD5 as
published by the IDC Google Cloud bucket, and SHA-256 recorded on first
download. ROI series are verified the same way against
data/manifests/roi_dicom_checksums.csv. Any mismatch exits non-zero.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import cbis
import pandas as pd
import roi

MANIFESTS = Path("data/manifests")
CHECKSUMS = MANIFESTS / "dicom_checksums.csv"
ROI_CHECKSUMS = MANIFESTS / "roi_dicom_checksums.csv"
GCS_LIST = (
    "https://storage.googleapis.com/storage/v1/b/idc-open-data/o"
    "?prefix={uuid}/&fields=items(name,size,md5Hash)"
)


def digests(path: Path) -> tuple[str, str]:
    """(base64 MD5, hex SHA-256) of a file."""
    md5, sha = hashlib.md5(), hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            md5.update(chunk)
            sha.update(chunk)
    return base64.b64encode(md5.digest()).decode(), sha.hexdigest()


def fetch_metadata(csv_dir: Path) -> int:
    expected = json.loads((MANIFESTS / "splits.json").read_text())["source_csv_sha256"]
    csv_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    for name in sorted(cbis.CSV_FILES.values()):
        path = csv_dir / name
        if not path.exists():
            urllib.request.urlretrieve(cbis.CSV_BASE_URL + name, path)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        ok = actual == expected[name]
        failures += not ok
        print(f"{'ok ' if ok else 'BAD'} {name} {actual}")
    return 1 if failures else 0


def load_cases(splits: list[str]) -> pd.DataFrame:
    frames = [pd.read_csv(MANIFESTS / f"{s}.csv", dtype=str) for s in splits]
    return pd.concat(frames, ignore_index=True).sort_values("case_id")


def gcs_objects(crdc_series_uuid: str) -> list[dict]:
    with urllib.request.urlopen(GCS_LIST.format(uuid=crdc_series_uuid)) as r:
        items = json.load(r).get("items", [])
    if not items:
        raise ValueError(f"no objects for series {crdc_series_uuid}")
    return sorted(items, key=lambda o: o["name"])


def add_objects(table: pd.DataFrame) -> pd.DataFrame:
    """One row per bucket object of each row's series, with size and MD5."""
    out = []
    for row in table.to_dict("records"):
        for obj in gcs_objects(row["crdc_series_uuid"]):
            out.append(
                {
                    **row,
                    "object": obj["name"].split("/", 1)[1],
                    "size": int(obj["size"]),
                    "md5_base64": obj["md5Hash"],
                    "sha256": "",
                }
            )
    return pd.DataFrame(out)


def idc_download(root: Path, series_uids: list[str]) -> None:
    from idc_index import IDCClient

    root.mkdir(parents=True, exist_ok=True)
    IDCClient().download_from_selection(
        downloadDir=str(root),
        seriesInstanceUID=sorted(set(series_uids)),
        dirTemplate="%SeriesInstanceUID",
        use_s5cmd_sync=True,
        show_progress_bar=False,
        quiet=True,
    )


def verify(table: pd.DataFrame, root: Path, record: bool) -> tuple[int, list[str]]:
    """Check size and MD5 (and SHA-256 unless recording). Returns (failures, sha256s)."""
    failures, shas = 0, []
    for row in table.itertuples():
        path = root / row.series_instance_uid / row.object
        if not path.is_file():
            print(f"MISSING {row.case_id} {path}")
            failures += 1
            shas.append("")
            continue
        md5, sha = digests(path)
        ok = path.stat().st_size == row.size and md5 == row.md5_base64
        if not record:
            ok = ok and sha == row.sha256
        if not ok:
            print(f"BAD {row.case_id} {path}")
            failures += 1
        shas.append(sha)
    return failures, shas


def read_checksums(path: Path, cases: pd.DataFrame) -> pd.DataFrame | None:
    table = pd.read_csv(path, dtype=str, keep_default_na=False)
    table["size"] = table["size"].astype(int)
    table = table[table["case_id"].isin(cases["case_id"])]
    if set(table["case_id"]) != set(cases["case_id"]):
        print(f"{path.name} is missing cases; run with --record", file=sys.stderr)
        return None
    return table


def save_checksums(table: pd.DataFrame, shas: list[str], path: Path, key: list[str]) -> None:
    table = table.copy()
    table["sha256"] = shas
    if path.exists():
        old = pd.read_csv(path, dtype=str, keep_default_na=False)
        old = old[~old["case_id"].isin(table["case_id"])]
        table = pd.concat([old, table.astype(str)])
    table.sort_values(key).to_csv(path, index=False, lineterminator="\n")


def fetch_and_verify(table: pd.DataFrame, root: Path, record: bool, path: Path, key) -> int:
    idc_download(root, list(table["series_instance_uid"]))
    failures, shas = verify(table, root, record)
    if record and failures:
        print("not recording checksums: some files failed size or MD5 checks", file=sys.stderr)
    elif record:
        save_checksums(table, shas, path, key)
    print(f"{len(table) - failures}/{len(table)} DICOM files verified")
    return 1 if failures else 0


def download_images(root: Path, splits: list[str], record: bool) -> int:
    cases = load_cases(splits)
    if record:
        table = add_objects(cases[["case_id", "series_instance_uid", "crdc_series_uuid"]])
        if table.groupby("case_id").size().max() != 1:
            raise ValueError("expected one object per full mammogram series")
    else:
        table = read_checksums(CHECKSUMS, cases)
        if table is None:
            return 1
    return fetch_and_verify(table, root, record, CHECKSUMS, ["case_id"])


def download_roi(root: Path, splits: list[str], record: bool, csv_dir: Path) -> int:
    """ROI crop and mask series of the selected abnormality of each case."""
    cases = load_cases(splits)
    if record:
        selected = roi.select_abnormalities(cases, cbis.load_rows(csv_dir))
        series = selected.melt(
            id_vars=[c for c in selected.columns if not c.endswith("_series_instance_uid")],
            value_vars=["crop_series_instance_uid", "mask_series_instance_uid"],
            value_name="series_instance_uid",
        )
        series = series.drop(columns="variable").drop_duplicates(["case_id", "series_instance_uid"])
        series = series.merge(
            selected[["case_id", "crop_series_instance_uid", "mask_series_instance_uid"]],
            on="case_id",
        )
        idc = cbis.idc_series(sorted(set(series["series_instance_uid"])))
        uuids = dict(zip(idc["SeriesInstanceUID"], idc["crdc_series_uuid"], strict=True))
        series["crdc_series_uuid"] = series["series_instance_uid"].map(uuids)
        table = add_objects(series.sort_values(["case_id", "series_instance_uid"]))
        per_case = table.groupby("case_id").size()
        if (per_case != 2).any():
            raise ValueError(f"expected two ROI objects per case: {per_case[per_case != 2]}")
    else:
        table = read_checksums(ROI_CHECKSUMS, cases)
        if table is None:
            return 1
    return fetch_and_verify(table, root, record, ROI_CHECKSUMS, ["case_id", "object"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    meta = sub.add_parser("metadata")
    meta.add_argument("--csv-dir", type=Path, default=Path("data/raw/csv"))
    img = sub.add_parser("images")
    img.add_argument("--root", type=Path, default=Path("data/raw/dicom"))
    img.add_argument("--splits", nargs="+", default=["dev", "test"], choices=["dev", "test"])
    img.add_argument("--record", action="store_true", help="write dicom_checksums.csv")
    rois = sub.add_parser("roi")
    rois.add_argument("--root", type=Path, default=Path("data/raw/roi"))
    rois.add_argument("--splits", nargs="+", default=["dev", "test"], choices=["dev", "test"])
    rois.add_argument("--csv-dir", type=Path, default=Path("data/raw/csv"))
    rois.add_argument("--record", action="store_true", help="write roi_dicom_checksums.csv")
    args = parser.parse_args()

    if args.command == "metadata":
        return fetch_metadata(args.csv_dir)
    if args.command == "roi":
        return download_roi(args.root, args.splits, args.record, args.csv_dir)
    return download_images(args.root, args.splits, args.record)


if __name__ == "__main__":
    sys.exit(main())
