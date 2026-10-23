"""Split rules on a synthetic image table."""

import make_splits
import pandas as pd
import pytest


def image(patient, side, view, kind, label, uid):
    return {
        "series_instance_uid": uid,
        "patient_id": patient,
        "side": side,
        "view": view,
        "study_instance_uid": f"s-{uid}",
        "abnormality_type": kind,
        "label": label,
        "pathology": label.upper(),
        "birads_assessment": 4,
        "assessments": "4",
        "breast_density": "2",
        "subtlety": "3",
        "n_abnormalities": 1,
        "official_split": "train",
    }


@pytest.fixture
def images(monkeypatch):
    monkeypatch.setattr(make_splits, "TEST_PER_STRATUM", 3)
    monkeypatch.setattr(make_splits, "DEV_PER_STRATUM", 1)
    rows, uid = [], 0
    for kind, label in make_splits.STRATA:
        for i in range(6):
            patient = f"P_{kind}_{label}_{i}"
            for side in ["LEFT", "RIGHT"]:
                for view in ["CC", "MLO"]:
                    uid += 1
                    rows.append(image(patient, side, view, kind, label, str(uid)))
    rows.append(image("P_mixed", "LEFT", "MLO", "mass", "benign", "m1"))
    rows.append(image("P_mixed", "RIGHT", "MLO", "calc", "malignant", "m2"))
    rows.append(image("P_cc_only", "LEFT", "CC", "mass", "benign", "c1"))
    rows.append(image("P_two_labels", "LEFT", "MLO", "mass", "benign;malignant", "t1"))
    return pd.DataFrame(rows)


def test_every_patient_in_exactly_one_split(images):
    patients, cases = make_splits.assign(images)
    assert patients["patient_id"].is_unique
    assert set(patients["patient_id"]) == set(images["patient_id"])
    dev = set(cases.loc[cases.split == "dev", "patient_id"])
    test = set(cases.loc[cases.split == "test", "patient_id"])
    assert not dev & test
    split_of = dict(zip(patients.patient_id, patients.split, strict=True))
    for row in cases.itertuples():
        assert split_of[row.patient_id] == row.split


def test_balanced_mlo_one_case_per_patient(images):
    _, cases = make_splits.assign(images)
    assert (cases["view"] == "MLO").all()
    assert cases["patient_id"].is_unique
    counts = cases.groupby(["split", "abnormality_type", "label"]).size()
    assert (counts.xs("test") == 3).all() and (counts.xs("dev") == 1).all()


def test_excluded_patients_go_to_reserve(images):
    patients, _ = make_splits.assign(images)
    reason = dict(zip(patients.patient_id, patients.reason, strict=True))
    assert reason["P_mixed"] == "mixed_strata"
    assert reason["P_cc_only"] == "no_eligible_image"
    assert reason["P_two_labels"] == "no_eligible_image"


def test_deterministic(images):
    a = make_splits.assign(images)[1]
    b = make_splits.assign(images)[1]
    pd.testing.assert_frame_equal(a, b)
    c = make_splits.assign(images, seed=1)[1]
    assert set(a["case_id"]) != set(c["case_id"])
