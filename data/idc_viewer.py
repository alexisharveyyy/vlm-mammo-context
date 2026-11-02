"""Record the IDC viewer identifiers of every test case's full image and ROI crop.

    uv run python data/idc_viewer.py

Writes data/manifests/idc_viewer.csv: per test case, the StudyInstanceUID and
SeriesInstanceUID of the full mammogram (from data/manifests/test.csv) and of
the ROI crop series the study used (from data/manifests/roi_checksums.csv),
with the crop's StudyInstanceUID looked up in the idc-index metadata. The
results viewer links each case to these series in the NCI Imaging Data
Commons viewer. Reads metadata only; no image is downloaded.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

MANIFESTS = Path("data/manifests")
OUT = MANIFESTS / "idc_viewer.csv"
FIELDS = ["case_id", "full_study_uid", "full_series_uid", "roi_study_uid", "roi_series_uid"]


def read(name: str) -> list[dict[str, str]]:
    with (MANIFESTS / name).open(newline="") as f:
        return list(csv.DictReader(f))


def main() -> int:
    from idc_index import IDCClient

    cases = read("test.csv")
    crops = {r["case_id"]: r["crop_series_instance_uid"] for r in read("roi_checksums.csv")}
    index = IDCClient().index
    study_of = dict(zip(index["SeriesInstanceUID"], index["StudyInstanceUID"], strict=True))
    rows = []
    for c in cases:
        full, crop = c["series_instance_uid"], crops[c["case_id"]]
        if study_of.get(full) != c["study_instance_uid"] or crop not in study_of:
            print(f"{c['case_id']}: series not found in idc-index", file=sys.stderr)
            return 1
        rows.append([c["case_id"], c["study_instance_uid"], full, study_of[crop], crop])
    with OUT.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(FIELDS)
        writer.writerows(rows)
    print(f"{len(rows)} cases -> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
