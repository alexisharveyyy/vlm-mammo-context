"""Render study prompts from the files in prompts/.

    render("colleague_malignant", paraphrase=2, image_kind="full", case=row)

`case` is a row of dev.csv or test.csv merged with answer_order.csv; only the
synthetic context columns and the answer-order offset are read. The true
label is never used. Controls use the text of the image condition they stand
in for (FRAME_FOR).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"
CONDITIONS = [
    "neutral",
    "age_42",
    "age_68",
    "history_yes",
    "history_no",
    "combined",
    "colleague_benign",
    "colleague_malignant",
    "irrelevant",
]
PARAPHRASES = (1, 2, 3)
ANSWER_FORMATS = ("forced", "plain")
# Controls use the text of the image condition they stand in for: no_image and
# blank_full the full-image frame, blank_roi the ROI frame. "blank_image" is
# the full-size blank image as first named in prompts/frame.yaml.
FRAME_FOR = {"no_image": "full", "blank_image": "full", "blank_full": "full", "blank_roi": "roi"}


@cache
def _load(name: str) -> dict:
    return yaml.safe_load((PROMPTS / f"{name}.yaml").read_text())


def answer_order(offset: int, paraphrase: int) -> tuple[str, str]:
    """("benign", "malignant") when offset + paraphrase is odd, else reversed."""
    if (offset + paraphrase) % 2 == 1:
        return ("benign", "malignant")
    return ("malignant", "benign")


def context_sentence(condition: str, paraphrase: int, case: dict) -> str:
    template = _load(condition)["context"][paraphrase]
    if condition != "combined":
        return template
    age = int(case["synthetic_age"])
    history = {"present": "history_yes", "absent": "history_no"}[case["synthetic_family_history"]]
    return template.format(
        age_sentence=_load(f"age_{age}")["context"][paraphrase],
        history_sentence=_load(history)["context"][paraphrase],
    )


def render(
    condition: str,
    paraphrase: int,
    image_kind: str,
    case: dict,
    answer_format: str = "forced",
) -> str:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}")
    frame = _load("frame")[FRAME_FOR.get(image_kind, image_kind)][paraphrase]
    context = context_sentence(condition, paraphrase, case)
    body = " ".join(part for part in (frame["intro"], context, frame["task"]) if part)
    first, second = answer_order(int(case["answer_order_offset"]), paraphrase)
    fmt = _load("answer_format")[answer_format].format(first=first, second=second)
    return f"{body}\n\n{fmt}"
