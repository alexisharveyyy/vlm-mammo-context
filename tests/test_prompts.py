"""Study prompts: structure, pairing, counterbalancing and no label leakage."""

import re
from itertools import product
from pathlib import Path

import pandas as pd
import pytest

from models import parse, prompts

MANIFESTS = Path(__file__).resolve().parents[1] / "data" / "manifests"
CASE = {"synthetic_age": "68", "synthetic_family_history": "present", "answer_order_offset": "0"}
ALL = list(product(prompts.CONDITIONS, prompts.PARAPHRASES, ["full", "roi"], ["forced", "plain"]))


@pytest.mark.parametrize(("condition", "p", "kind", "fmt"), ALL)
def test_every_prompt_renders_and_parses_as_expected(condition, p, kind, fmt):
    text = prompts.render(condition, p, kind, CASE, fmt)
    _body, answer = text.split("\n\n")
    assert answer.startswith("Answer in exactly this format")
    assert ("You must choose" in answer) == (fmt == "forced")
    assert "\u2014" not in text and "{" not in text
    # The format block itself must not parse as an answer.
    assert not parse.parse(answer).ok


def test_neutral_is_frame_only_and_context_is_inserted_between():
    neutral = prompts.render("neutral", 1, "full", CASE).split("\n\n")[0]
    colleague = prompts.render("colleague_benign", 1, "full", CASE).split("\n\n")[0]
    intro, task = neutral.split(". ", 1)
    assert colleague.startswith(intro + ". A colleague") and colleague.endswith(task)


@pytest.mark.parametrize("p", prompts.PARAPHRASES)
def test_pairs_differ_only_in_the_manipulated_words(p):
    pairs = [
        ("age_42", "age_68", "42", "68"),
        ("colleague_benign", "colleague_malignant", "benign", "malignant"),
        ("history_yes", "history_no", None, None),
    ]
    for a, b, wa, wb in pairs:
        ta = prompts.render(a, p, "full", CASE).split("\n\n")[0]
        tb = prompts.render(b, p, "full", CASE).split("\n\n")[0]
        assert ta != tb
        if wa:
            assert ta.replace(wa, wb) == tb


@pytest.mark.parametrize("p", prompts.PARAPHRASES)
def test_irrelevant_length_matches_colleague(p):
    lengths = [
        len(prompts.context_sentence(c, p, CASE))
        for c in ("colleague_benign", "colleague_malignant")
    ]
    irrelevant = len(prompts.context_sentence("irrelevant", p, CASE))
    assert min(lengths) <= irrelevant <= max(lengths)


def test_irrelevant_has_no_clinical_words():
    words = re.compile(r"benign|malignan|cancer|breast|patient|radiolog|mammo", re.I)
    for p in prompts.PARAPHRASES:
        assert not words.search(prompts.context_sentence("irrelevant", p, CASE))


def test_combined_uses_assigned_values():
    young = {**CASE, "synthetic_age": "42", "synthetic_family_history": "absent"}
    for p in prompts.PARAPHRASES:
        assert prompts.context_sentence("combined", p, young) == (
            prompts.context_sentence("age_42", p, young)
            + " "
            + prompts.context_sentence("history_no", p, young)
        )


def test_answer_order_alternates_and_is_counterbalanced():
    assert [prompts.answer_order(0, p)[0] for p in prompts.PARAPHRASES] == [
        "benign",
        "malignant",
        "benign",
    ]
    assert [prompts.answer_order(1, p)[0] for p in prompts.PARAPHRASES] == [
        "malignant",
        "benign",
        "malignant",
    ]
    text = prompts.render("neutral", 2, "full", CASE)
    assert "Assessment: <malignant or benign>" in text
    assert "You must choose malignant or benign" in text


def test_controls_use_full_image_text():
    for control in ("no_image", "blank_image"):
        assert prompts.render("neutral", 1, control, CASE) == prompts.render(
            "neutral", 1, "full", CASE
        )


def test_unknown_condition():
    with pytest.raises(ValueError):
        prompts.render("colleague_unsure", 1, "full", CASE)


def test_answer_order_manifest_counterbalanced():
    order = pd.read_csv(MANIFESTS / "answer_order.csv", dtype=str)
    for split in ["dev", "test"]:
        cases = pd.read_csv(MANIFESTS / f"{split}.csv", dtype=str).merge(order, on="case_id")
        assert len(cases) == len(pd.read_csv(MANIFESTS / f"{split}.csv"))
        counts = cases.groupby(["abnormality_type", "label", "answer_order_offset"]).size()
        assert len(counts) == 8 and counts.max() - counts.min() <= 1
