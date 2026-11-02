"""Integrity of the committed split manifests."""

import hashlib
import json
from pathlib import Path

import pandas as pd

MANIFESTS = Path(__file__).resolve().parents[1] / "data" / "manifests"

# test.csv is frozen at tag splits-v1. This hash must never change.
TEST_CSV_SHA256 = "e5d632998a7cf70e347192cce9b7a5c494b5f0842551e99efa8dca4144622ea5"


def read(name):
    return pd.read_csv(MANIFESTS / name, dtype=str)


def test_no_patient_in_both_dev_and_test():
    dev, test = read("dev.csv"), read("test.csv")
    assert not set(dev.patient_id) & set(test.patient_id)


def test_patients_file_agrees_with_cases():
    patients = read("patients.csv")
    assert patients.patient_id.is_unique
    split_of = dict(zip(patients.patient_id, patients.split, strict=True))
    for split in ["dev", "test"]:
        cases = read(f"{split}.csv")
        assert cases.patient_id.is_unique and cases.case_id.is_unique
        assert all(split_of[p] == split for p in cases.patient_id)
        assert (patients.split == split).sum() == len(cases)


def test_sizes_and_balance():
    summary = json.loads((MANIFESTS / "splits.json").read_text())
    for split, per_stratum in [
        ("test", summary["test_per_stratum"]),
        ("dev", summary["dev_per_stratum"]),
    ]:
        cases = read(f"{split}.csv")
        assert len(cases) == 4 * per_stratum
        assert (cases.view == "MLO").all()
        counts = cases.groupby(["abnormality_type", "label"]).size()
        assert len(counts) == 4 and (counts == per_stratum).all()


def test_checksums_cover_every_case():
    cases = set(read("dev.csv").case_id) | set(read("test.csv").case_id)
    for name in ["dicom_checksums.csv", "png_sha256.csv"]:
        table = read(name)
        assert set(table.case_id) == cases
        assert table.sha256.str.fullmatch(r"[0-9a-f]{64}").all()
    pixels = read("png_sha256.csv").pixel_sha256
    assert pixels.str.fullmatch(r"[0-9a-f]{64}").all()


def test_synthetic_context_counterbalanced():
    for split in ["dev", "test"]:
        cases = read(f"{split}.csv")
        assert set(cases.synthetic_age) == {"42", "68"}
        assert set(cases.synthetic_family_history) == {"absent", "present"}
        cells = cases.groupby(
            ["abnormality_type", "label", "synthetic_age", "synthetic_family_history"]
        ).size()
        assert len(cells) == 16 and cells.max() - cells.min() <= 1


def test_roi_crops_recorded():
    for split in ["dev", "test"]:
        cases = read(f"{split}.csv")
        assert set(cases.roi_crop_available) <= {"True", "False"}
        assert cases.crop_series_instance_uids.notna().all()


def test_test_set_frozen():
    digest = hashlib.sha256((MANIFESTS / "test.csv").read_bytes()).hexdigest()
    assert digest == TEST_CSV_SHA256, "test.csv is frozen at splits-v1 and must not change"


def test_roi_checksums_cover_every_case():
    cases = pd.concat([read("dev.csv"), read("test.csv")])
    objects = read("roi_dicom_checksums.csv")
    pngs = read("roi_checksums.csv")
    assert set(objects.case_id) == set(cases.case_id)
    assert (objects.groupby("case_id").size() == 2).all()
    assert objects.md5_base64.str.len().eq(24).all()
    assert pngs.case_id.is_unique and set(pngs.case_id) == set(cases.case_id)
    assert pngs.sha256.str.fullmatch(r"[0-9a-f]{64}").all()
    assert pngs.pixel_sha256.str.fullmatch(r"[0-9a-f]{64}").all()
    assert set(pngs.csv_order_swapped) <= {"yes", "no", "undetermined"}
    assert (pngs.crop_object != pngs.mask_object).all()
    birads = dict(zip(cases.case_id, cases.birads_assessment, strict=True))
    assert all(birads[c] == a for c, a in zip(objects.case_id, objects.assessment, strict=True))


def test_idc_viewer_links_match_the_manifests():
    links, cases = read("idc_viewer.csv"), read("test.csv")
    crops = read("roi_checksums.csv").set_index("case_id").crop_series_instance_uid
    assert list(links.case_id) == list(cases.case_id)
    assert (links.full_study_uid.values == cases.study_instance_uid.values).all()
    assert (links.full_series_uid.values == cases.series_instance_uid.values).all()
    assert (links.roi_series_uid.values == crops[links.case_id].values).all()
    uid = r"[0-9]+(\.[0-9]+)+"
    for column in links.columns[1:]:
        assert links[column].str.fullmatch(uid).all()
