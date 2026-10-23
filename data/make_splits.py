"""Build the patient-level dev and test splits from CBIS-DDSM metadata only.

No pixels are read. Every patient is assigned to exactly one of dev, test or
reserve, so all images, views and sides of a patient stay in one split. Each
dev or test patient contributes one case: one MLO full mammogram.

Rules:
  - eligible image: MLO view, and all abnormalities on it share one binary
    label (benign or malignant)
  - eligible patient: has an eligible image, and all eligible images fall in
    one stratum (abnormality type x label)
  - per stratum, eligible patients are shuffled with a fixed seed; the first
    TEST_PER_STRATUM go to test, the next DEV_PER_STRATUM to dev, the rest to
    reserve
  - each sampled patient's case image is drawn with the same seeded generator

Each case also gets a synthetic age (42 or 68) and a synthetic family history
(present or absent) for the age and history prompt conditions. These are
experimental manipulations, not patient attributes (CBIS-DDSM has no age). The
four combinations are counterbalanced within each split and stratum, using
CONTEXT_SEED.

    python data/make_splits.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path

import cbis
import pandas as pd

SEED = 20261023
VIEW = "MLO"
TEST_PER_STRATUM = 125
DEV_PER_STRATUM = 25
CONTEXT_SEED = 20261024
SYNTHETIC_AGES = [42, 68]
SYNTHETIC_HISTORY = ["absent", "present"]
STRATA = [
    ("calc", "benign"),
    ("calc", "malignant"),
    ("mass", "benign"),
    ("mass", "malignant"),
]

CASE_COLUMNS = [
    "case_id",
    "patient_id",
    "side",
    "view",
    "abnormality_type",
    "label",
    "pathology",
    "birads_assessment",
    "assessments",
    "breast_density",
    "subtlety",
    "n_abnormalities",
    "official_split",
    "series_instance_uid",
    "study_instance_uid",
    "crdc_series_uuid",
    "synthetic_age",
    "synthetic_family_history",
    "roi_crop_available",
    "crop_series_instance_uids",
    "mask_series_instance_uids",
]


def assign(images: pd.DataFrame, seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (patients, cases). patients has one row per patient with its split."""
    eligible = images[
        (images["view"] == VIEW) & images["label"].isin(["benign", "malignant"])
    ].copy()
    eligible["stratum"] = list(zip(eligible["abnormality_type"], eligible["label"], strict=True))

    strata_per_patient = eligible.groupby("patient_id")["stratum"].agg(lambda s: sorted(set(s)))
    patients = pd.DataFrame({"patient_id": sorted(images["patient_id"].unique())})
    patients["split"] = "reserve"
    patients["reason"] = "no_eligible_image"
    patients = patients.set_index("patient_id")
    mixed = strata_per_patient[strata_per_patient.map(len) > 1].index
    patients.loc[mixed, "reason"] = "mixed_strata"

    rng = random.Random(seed)
    chosen = []
    for stratum in STRATA:
        pool = sorted(p for p, s in strata_per_patient.items() if s == [stratum])
        rng.shuffle(pool)
        n_test, n_dev = TEST_PER_STRATUM, DEV_PER_STRATUM
        if len(pool) < n_test + n_dev:
            raise ValueError(f"stratum {stratum} has {len(pool)} patients, need {n_test + n_dev}")
        patients.loc[pool, "reason"] = "not_sampled"
        for split, members in [("test", pool[:n_test]), ("dev", pool[n_test : n_test + n_dev])]:
            for patient in members:
                options = eligible[eligible["patient_id"] == patient].sort_values(
                    ["side", "series_instance_uid"]
                )
                row = options.iloc[rng.randrange(len(options))]
                chosen.append({**row.to_dict(), "split": split})
                patients.loc[patient, ["split", "reason"]] = [split, "sampled"]

    cases = pd.DataFrame(chosen).drop(columns="stratum")
    cases["case_id"] = cases["patient_id"] + "_" + cases["side"] + "_" + cases["view"]
    return patients.reset_index(), cases


def assign_context(cases: pd.DataFrame, seed: int = CONTEXT_SEED) -> pd.DataFrame:
    """Counterbalanced synthetic age and family history within split and stratum."""
    combos = [(age, hist) for age in SYNTHETIC_AGES for hist in SYNTHETIC_HISTORY]
    rng = random.Random(seed)
    cases = cases.sort_values("case_id").copy()
    cases["synthetic_age"] = 0
    cases["synthetic_family_history"] = ""
    for split in ["dev", "test"]:
        for kind, label in STRATA:
            mask = (
                (cases["split"] == split)
                & (cases["abnormality_type"] == kind)
                & (cases["label"] == label)
            )
            n = int(mask.sum())
            order = combos[:]
            rng.shuffle(order)
            values = (order * (n // len(order) + 1))[:n]
            rng.shuffle(values)
            cases.loc[mask, "synthetic_age"] = [age for age, _ in values]
            cases.loc[mask, "synthetic_family_history"] = [hist for _, hist in values]
    return cases


def roi_availability(cases: pd.DataFrame, idc_uids: set[str]) -> pd.Series:
    """True if every abnormality on the case image has crop and mask series in IDC."""

    def available(row) -> bool:
        uids = row.crop_series_instance_uids.split(";") + row.mask_series_instance_uids.split(";")
        return all(u and u in idc_uids for u in uids)

    return cases.apply(available, axis=1)


def split_counts(images: pd.DataFrame, patients: pd.DataFrame, cases: pd.DataFrame) -> dict:
    merged = images.merge(patients[["patient_id", "split"]], on="patient_id")
    counts = {}
    for split in ["dev", "test", "reserve"]:
        m = merged[merged["split"] == split]
        c = cases[cases["split"] == split]
        counts[split] = {
            "patients": int((patients["split"] == split).sum()),
            "full_images": len(m),
            "breasts": int(m[["patient_id", "side"]].drop_duplicates().shape[0]),
            "images_by_view": {k: int(v) for k, v in sorted(m["view"].value_counts().items())},
            "images_by_side": {k: int(v) for k, v in sorted(m["side"].value_counts().items())},
            "cases": len(c),
            "cases_by_stratum": {
                f"{t}/{lab}": int(n)
                for (t, lab), n in sorted(c.groupby(["abnormality_type", "label"]).size().items())
            },
        }
    for split in ["dev", "test"]:
        c = cases[cases["split"] == split]
        counts[split]["synthetic_context"] = {
            f"age {a}, history {h}": int(n)
            for (a, h), n in sorted(
                c.groupby(["synthetic_age", "synthetic_family_history"]).size().items()
            )
        }
        counts[split]["roi_crop_available"] = int(c["roi_crop_available"].sum())
    reasons = patients.loc[patients["split"] == "reserve", "reason"].value_counts()
    counts["reserve_reasons"] = {k: int(v) for k, v in sorted(reasons.items())}
    return counts


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--csv-dir", type=Path, default=Path("data/raw/csv"))
    parser.add_argument("--out", type=Path, default=Path("data/manifests"))
    args = parser.parse_args()

    images = cbis.build_images(cbis.load_rows(args.csv_dir))
    patients, cases = assign(images)

    idc = cbis.idc_series(sorted(cases["series_instance_uid"]))
    idc = idc.rename(columns={"SeriesInstanceUID": "series_instance_uid"})
    if (idc["instanceCount"] != 1).any():
        raise ValueError("expected one instance per full mammogram series")
    cases = cases.merge(idc[["series_instance_uid", "crdc_series_uuid"]], on="series_instance_uid")
    cases["roi_crop_available"] = roi_availability(
        cases, set(cbis.idc_index_table()["SeriesInstanceUID"])
    )
    cases = assign_context(cases)

    overlap = set(cases.loc[cases.split == "dev", "patient_id"]) & set(
        cases.loc[cases.split == "test", "patient_id"]
    )
    if overlap or cases["case_id"].duplicated().any() or patients["patient_id"].duplicated().any():
        raise AssertionError("split integrity check failed")

    args.out.mkdir(parents=True, exist_ok=True)
    for split in ["dev", "test"]:
        part = cases[cases["split"] == split].sort_values("case_id")[CASE_COLUMNS]
        part.to_csv(args.out / f"{split}.csv", index=False, lineterminator="\n")
    patients.sort_values("patient_id").to_csv(
        args.out / "patients.csv", index=False, lineterminator="\n"
    )

    import idc_index
    from idc_index import IDCClient

    summary = {
        "seed": SEED,
        "view": VIEW,
        "test_per_stratum": TEST_PER_STRATUM,
        "dev_per_stratum": DEV_PER_STRATUM,
        "context_seed": CONTEXT_SEED,
        "synthetic_ages": SYNTHETIC_AGES,
        "synthetic_family_history": SYNTHETIC_HISTORY,
        "strata": [f"{t}/{lab}" for t, lab in STRATA],
        "idc_version": IDCClient().get_idc_version(),
        "idc_index_version": idc_index.__version__,
        "source_csv_sha256": {
            name: sha256(args.csv_dir / name) for name in sorted(cbis.CSV_FILES.values())
        },
        "counts": split_counts(images, patients, cases),
    }
    (args.out / "splits.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary["counts"], indent=2))


if __name__ == "__main__":
    main()
