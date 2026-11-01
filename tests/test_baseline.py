"""Abstention versus parse failure in the baseline report."""

from eval.baseline import is_abstention


def test_assessment_naming_neither_class_is_an_abstention():
    assert is_abstention("BI-RADS: 0\nAssessment: indeterminate\nConfidence: 50", False)
    assert is_abstention("BI-RADS: 0\n**Assessment:** None\nConfidence: 0", False)


def test_parsed_or_unreadable_output_is_not_an_abstention():
    assert not is_abstention("BI-RADS: 2\nAssessment: benign\nConfidence: 80", True)
    assert not is_abstention("I cannot interpret medical images.", False)
    assert not is_abstention("Assessment:\nConfidence: 50", False)
    assert not is_abstention(None, False)


def test_case_level_p_malignant_uses_valid_answers_only():
    import pandas as pd

    from eval.baseline import summarize

    def call(case, paraphrase, malignant, p, text):
        return {
            "case_id": case,
            "paraphrase": paraphrase,
            "malignant": malignant,
            "confidence": 80.0 if malignant is not None else 50.0,
            "birads": 4 if malignant else 2,
            "p_malignant": p,
            "class_mass": 0.9,
            "error": None,
            "raw_text": text,
            "reused_from": None,
            "commit": "c",
            "config_sha256": "h",
            "parse_ok": malignant is not None,
        }

    abstained = "BI-RADS: 0\nAssessment: indeterminate\nConfidence: 50"
    df = pd.DataFrame(
        [
            call("A", 1, True, 0.9, "BI-RADS: 4\nAssessment: malignant\nConfidence: 80"),
            call("A", 2, None, 0.1, abstained),
            call("B", 1, False, 0.6, "BI-RADS: 2\nAssessment: benign\nConfidence: 80"),
        ]
    )
    labels = pd.Series({"A": "malignant", "B": "benign"})
    offsets = pd.Series({"A": "0", "B": "1"})
    out = summarize(df, labels, offsets)
    # Averaging over every call would give case A 0.5 (< 0.6) and an AUROC of 0.
    assert out["auroc"] == 1.0
    assert out["abstentions"] == 1 and out["parse_failures"] == 0
