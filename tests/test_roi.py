"""ROI abnormality selection and crop/mask identification."""

import numpy as np
import pandas as pd
import pytest
import roi
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid


def abnormality(uid, number, assessment, label="malignant"):
    return {
        "series_instance_uid": uid,
        "abnormality_id": str(number),
        "assessment": assessment,
        "label": label,
        "pathology": label.upper(),
        "crop_series_instance_uid": f"crop-{uid}-{number}",
        "mask_series_instance_uid": f"crop-{uid}-{number}",
        "cropped_image_file_path": f"x/y/crop-{uid}-{number}/000000.dcm",
        "ROI_mask_file_path": f"x/y/crop-{uid}-{number}/000001.dcm",
    }


def case(case_id, uid, birads, label="malignant"):
    return {
        "case_id": case_id,
        "series_instance_uid": uid,
        "label": label,
        "birads_assessment": str(birads),
    }


def test_selects_highest_birads_then_lowest_id():
    cases = pd.DataFrame([case("A", "a", 5), case("B", "b", 4), case("C", "c", 3)])
    rows = pd.DataFrame(
        [
            abnormality("a", 1, 4),
            abnormality("a", 2, 5),
            abnormality("b", 3, 4),
            abnormality("b", 2, 4),
            abnormality("c", 1, 3),
        ]
    )
    chosen = roi.select_abnormalities(cases, rows).set_index("case_id")
    assert chosen.loc["A", "abnormality_id"] == 2
    assert chosen.loc["B", "abnormality_id"] == 2
    assert chosen.loc["C", "abnormality_id"] == 1
    assert chosen["n_abnormalities"].to_dict() == {"A": 2, "B": 2, "C": 1}


def test_rejects_label_mismatch():
    cases = pd.DataFrame([case("A", "a", 4)])
    rows = pd.DataFrame([abnormality("a", 1, 4, label="benign")])
    with pytest.raises(ValueError):
        roi.select_abnormalities(cases, rows)


def write_dicom(path, pixels):
    ds = Dataset()
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.SOPInstanceUID = generate_uid()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.set_pixel_data(pixels, "MONOCHROME2", pixels.dtype.itemsize * 8)
    ds.save_as(path, enforce_file_format=True)
    return path


def test_identifies_mask_by_content_regardless_of_order(tmp_path):
    rng = np.random.default_rng(0)
    crop = write_dicom(tmp_path / "a.dcm", rng.integers(0, 65536, (40, 30), dtype=np.uint16))
    mask_pixels = np.zeros((80, 60), dtype=np.uint8)
    mask_pixels[10:30, 10:20] = 255
    mask = write_dicom(tmp_path / "b.dcm", mask_pixels)
    assert roi.identify([crop, mask]) == (crop, mask)
    assert roi.identify([mask, crop]) == (crop, mask)


def test_identify_rejects_two_masks(tmp_path):
    mask = np.zeros((8, 8), dtype=np.uint8)
    a = write_dicom(tmp_path / "a.dcm", mask)
    b = write_dicom(tmp_path / "b.dcm", mask)
    with pytest.raises(ValueError):
        roi.identify([a, b])
