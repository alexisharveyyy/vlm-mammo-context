"""Download CBIS-DDSM metadata and the dev and test DICOMs, and verify checksums.

    python data/download.py metadata            # four case description CSVs from TCIA
    python data/download.py images              # dev and test full mammograms from IDC
    python data/download.py images --record     # first run only: write dicom_checksums.csv

CSV checksums are verified against data/manifests/splits.json. DICOM checksums
are verified against data/manifests/dicom_checksums.csv: size and MD5 as
published by the IDC Google Cloud bucket, and SHA-256 recorded on first
download. Any mismatch exits non-zero.
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

MANIFESTS = Path("data/manifests")
CHECKSUMS = MANIFESTS / "dicom_checksums.csv"
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


def gcs_object(crdc_series_uuid: str) -> dict:
    with urllib.request.urlopen(GCS_LIST.format(uuid=crdc_series_uuid)) as r:
        items = json.load(r).get("items", [])
    if len(items) != 1:
        raise ValueError(f"expected one object for series {crdc_series_uuid}, got {len(items)}")
    return items[0]


def download_images(root: Path, splits: list[str], record: bool) -> int:
    from idc_index import IDCClient

    cases = load_cases(splits)
    if record:
        objects = [gcs_object(u) for u in cases["crdc_series_uuid"]]
        table = cases[["case_id", "series_instance_uid", "crdc_series_uuid"]].copy()
        table["object"] = [o["name"].split("/", 1)[1] for o in objects]
        table["size"] = [int(o["size"]) for o in objects]
        table["md5_base64"] = [o["md5Hash"] for o in objects]
        table["sha256"] = ""
    else:
        table = pd.read_csv(CHECKSUMS, dtype={"size": int}, keep_default_na=False)
        table = table[table["case_id"].isin(cases["case_id"])]
        if len(table) != len(cases):
            print("dicom_checksums.csv is missing cases; run with --record", file=sys.stderr)
            return 1

    root.mkdir(parents=True, exist_ok=True)
    IDCClient().download_from_selection(
        downloadDir=str(root),
        seriesInstanceUID=list(cases["series_instance_uid"]),
        dirTemplate="%SeriesInstanceUID",
        use_s5cmd_sync=True,
        show_progress_bar=False,
        quiet=True,
    )

    failures = 0
    sha_column = []
    for row in table.itertuples():
        path = root / row.series_instance_uid / row.object
        if not path.is_file():
            print(f"MISSING {row.case_id} {path}")
            failures += 1
            sha_column.append("")
            continue
        md5, sha = digests(path)
        ok = path.stat().st_size == row.size and md5 == row.md5_base64
        if not record:
            ok = ok and sha == row.sha256
        if not ok:
            print(f"BAD {row.case_id} {path}")
            failures += 1
        sha_column.append(sha)

    if record:
        if failures:
            print("not recording checksums: some files failed size or MD5 checks", file=sys.stderr)
        else:
            table["sha256"] = sha_column
            if CHECKSUMS.exists():
                old = pd.read_csv(CHECKSUMS, dtype={"size": int}, keep_default_na=False)
                table = pd.concat([old[~old["case_id"].isin(table["case_id"])], table])
            table.sort_values("case_id").to_csv(CHECKSUMS, index=False, lineterminator="\n")
    print(f"{len(table) - failures}/{len(table)} DICOM files verified")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    meta = sub.add_parser("metadata")
    meta.add_argument("--csv-dir", type=Path, default=Path("data/raw/csv"))
    img = sub.add_parser("images")
    img.add_argument("--root", type=Path, default=Path("data/raw/dicom"))
    img.add_argument("--splits", nargs="+", default=["dev", "test"], choices=["dev", "test"])
    img.add_argument("--record", action="store_true", help="write dicom_checksums.csv")
    args = parser.parse_args()

    if args.command == "metadata":
        return fetch_metadata(args.csv_dir)
    return download_images(args.root, args.splits, args.record)


if __name__ == "__main__":
    sys.exit(main())
