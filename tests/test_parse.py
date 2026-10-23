"""Parser behavior on hand-written model outputs."""

import json

import pytest

from models import parse

CLEAN = "BI-RADS: 4\nAssessment: malignant\nConfidence: 70"


def test_strict_accepts_exact_format():
    p = parse.parse(CLEAN, "strict")
    assert p.ok and (p.birads, p.malignant, p.confidence) == (4, True, 70.0)
    p = parse.parse("  BI-RADS: 2\n Assessment: benign \nConfidence: 95\n", "strict")
    assert p.ok and (p.birads, p.malignant, p.confidence) == (2, False, 95.0)


@pytest.mark.parametrize(
    "text",
    [
        "**BI-RADS:** 4\nAssessment: malignant\nConfidence: 70",
        "BI-RADS: 4\nAssessment: Malignant\nConfidence: 70",
        "BI-RADS: 4\nAssessment: malignant\nConfidence: 70%",
        "Here is my answer.\nBI-RADS: 4\nAssessment: malignant\nConfidence: 70",
        "BI-RADS: 7\nAssessment: malignant\nConfidence: 70",
        "BI-RADS: 4\nAssessment: malignant\nConfidence: 170",
    ],
)
def test_strict_rejects_anything_else(text):
    assert not parse.parse(text, "strict").ok


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (CLEAN, (4, True, 70.0)),
        ("**BI-RADS:** 5\n**Assessment:** Malignant\n**Confidence:** 90%", (5, True, 90.0)),
        ("BIRADS category 3\nAssessment - benign\nConfidence = 60", (3, False, 60.0)),
        (
            "The image shows a well-circumscribed mass.\n\nBI-RADS: 2\n"
            "Assessment: benign (likely fibroadenoma)\nConfidence: 85",
            (2, False, 85.0),
        ),
        ("BI-RADS: 0\nAssessment: benign\nConfidence: 12.5", (0, False, 12.5)),
    ],
)
def test_lenient_reads_common_variations(text, expected):
    p = parse.parse(text)
    assert p.ok, p.errors
    assert (p.birads, p.malignant, p.confidence) == expected


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ("Assessment: malignant\nConfidence: 70", "birads_missing"),
        ("BI-RADS: 9\nAssessment: malignant\nConfidence: 70", "birads_range"),
        ("BI-RADS: 4\nConfidence: 70", "assessment_missing"),
        ("BI-RADS: 4\nAssessment: benign or malignant\nConfidence: 70", "assessment_ambiguous"),
        ("BI-RADS: 4\nAssessment: suspicious\nConfidence: 70", "assessment_unreadable"),
        ("BI-RADS: 4\nAssessment: malignant", "confidence_missing"),
        ("BI-RADS: 4\nAssessment: malignant\nConfidence: 250", "confidence_range"),
        ("I cannot provide a medical diagnosis.", "birads_missing"),
    ],
)
def test_lenient_failures_are_named_not_guessed(text, error):
    p = parse.parse(text)
    assert not p.ok and error in p.errors


def test_partial_parse_keeps_good_fields():
    p = parse.parse("BI-RADS: 3\nAssessment: unclear\nConfidence: 40")
    assert p.birads == 3 and p.malignant is None and p.confidence == 40.0


def test_log_failure_keeps_raw_text(tmp_path):
    log = tmp_path / "failures.jsonl"
    text = "I cannot provide a medical diagnosis."
    parse.log_failure(log, {"case_id": "P_1", "model": "m"}, parse.parse(text), text)
    entry = json.loads(log.read_text())
    assert entry["raw_text"] == text and entry["case_id"] == "P_1"
    assert "birads_missing" in entry["errors"]


def test_unknown_rules():
    with pytest.raises(ValueError):
        parse.parse(CLEAN, "loose")
