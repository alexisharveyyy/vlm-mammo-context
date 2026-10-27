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
