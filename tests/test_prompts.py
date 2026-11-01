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


def test_blank_roi_uses_roi_text():
    assert prompts.render("colleague_benign", 2, "blank_roi", CASE) == prompts.render(
        "colleague_benign", 2, "roi", CASE
    )


def test_controls_use_full_image_text():
    for control in ("no_image", "blank_image", "blank_full"):
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


@pytest.mark.parametrize("condition", prompts.CONDITIONS)
def test_end_position_moves_only_the_context_sentence(condition):
    for p in prompts.PARAPHRASES:
        middle = prompts.render(condition, p, "full", CASE).split("\n\n")
        end = prompts.render(condition, p, "full", CASE, position="end").split("\n\n")
        context = prompts.context_sentence(condition, p, CASE)
        assert end[1] == middle[1]
        if not context:
            assert end == middle
        else:
            assert end[0].endswith(" " + context)
            assert end[0].replace(" " + context, "") == middle[0].replace(" " + context, "")
    with pytest.raises(ValueError, match="position"):
        prompts.render(condition, 1, "full", CASE, position="start")


def test_default_rendering_matches_the_committed_t0_prompts():
    """Every committed T0 call was made with the prompt the default renders."""
    import hashlib
    import json

    runs = MANIFESTS.parents[1] / "runs"
    cases = pd.read_csv(MANIFESTS / "test.csv", dtype=str).merge(
        pd.read_csv(MANIFESTS / "answer_order.csv", dtype=str), on="case_id"
    )
    rows = cases.set_index("case_id").to_dict("index")
    checked = 0
    for path in sorted(runs.glob("*/*/neutral/p*.jsonl")):
        if path.parts[-4] in ("dev", "smoke", "smoke_forced"):
            continue
        for line in path.read_text().splitlines()[:50]:
            r = json.loads(line)
            text = prompts.render(
                r["condition"],
                r["paraphrase"],
                r["image_kind"],
                rows[r["case_id"]],
                r["answer_format"],
            )
            assert hashlib.sha256(text.encode()).hexdigest() == r["prompt_sha256"], r["call_key"]
            checked += 1
    assert checked >= 50 or not runs.exists()
