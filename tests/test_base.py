"""Model-independent parts of the adapter interface."""

import math

import numpy as np
import pytest
from PIL import Image

from models import base

# A toy tokenizer: one token per word piece below.
VOCAB = ["BI-RADS: 4", "\n", "Assessment:", " malignant", " benign", "\nConfidence: 70", "x"]


def decode(ids):
    return "".join(VOCAB[i] for i in ids)


def logprobs(p_mal, p_ben):
    p = np.full(len(VOCAB), 1e-12)
    p[3], p[4] = p_mal, p_ben
    p[6] = max(1e-12, 1 - p_mal - p_ben)  # the rest of the mass goes to another token
    return np.log(p / p.sum())


CLASS_IDS = {"benign": {4}, "malignant": {3}}


def test_class_probability_at_answer_slot():
    ids = [0, 1, 2, 3, 5]
    steps = [logprobs(0.5, 0.5)] * 3 + [logprobs(0.6, 0.2)] + [logprobs(0.5, 0.5)]
    out = base.class_probability(ids, decode, steps, CLASS_IDS)
    assert out["step"] == 3
    assert math.isclose(out["p_malignant"], 0.75, rel_tol=1e-6)
    assert math.isclose(out["class_mass"], 0.8, rel_tol=1e-3)


def test_class_probability_missing_slot_or_logits():
    assert base.class_probability([0, 1, 6], decode, [logprobs(0.5, 0.5)] * 3, CLASS_IDS) is None
    assert base.class_probability([0, 1, 2, 3], decode, None, CLASS_IDS) is None
    shared = {"benign": {3}, "malignant": {3}}
    assert base.class_probability([0, 2, 3], decode, [logprobs(0.5, 0.5)] * 3, shared) is None


class FakeAdapter(base.Adapter):
    def load(self):
        pass

    def generate(self, image, prompt):
        self.seen = image
        ids = [0, 1, 2, 3, 5]
        return base.Generation(decode(ids), ids, [logprobs(0.9, 0.1)] * 5, 0.01)

    def decode(self, token_ids):
        return decode(token_ids)

    def class_token_ids(self):
        return CLASS_IDS


CFG = {"repo_id": "fake/model", "revision": "0" * 40, "resize": {"type": "long_side", "size": 64}}


def test_predict_contract():
    rng = np.random.default_rng(0)
    image = Image.fromarray(rng.integers(0, 256, (200, 100), dtype=np.uint8))
    adapter = FakeAdapter("fake", CFG)
    out = adapter.predict(image, "prompt")
    assert set(out) >= {"raw_text", "birads", "malignant", "confidence", "p_malignant"}
    assert (out["birads"], out["malignant"], out["confidence"]) == (4, True, 70.0)
    assert math.isclose(out["p_malignant"], 0.9, rel_tol=1e-6)
    assert out["meta"]["sent_size"] == [32, 64] and adapter.seen.mode == "RGB"


def test_predict_refuses_masks():
    mask = np.zeros((50, 50), dtype=np.uint8)
    mask[10:20, 10:20] = 255
    with pytest.raises(ValueError, match="mask"):
        FakeAdapter("fake", CFG).predict(Image.fromarray(mask), "prompt")


def test_blank_allowed_only_when_requested_and_all_zero():
    blank = Image.fromarray(np.zeros((40, 30), dtype=np.uint8))
    with pytest.raises(ValueError, match="mask"):
        base.check_not_mask(blank)
    base.check_not_mask(blank, allow_blank=True)
    mask = np.zeros((40, 30), dtype=np.uint8)
    mask[5:10, 5:10] = 255
    with pytest.raises(ValueError, match="mask"):
        base.check_not_mask(Image.fromarray(mask), allow_blank=True)


def test_text_only_predict():
    adapter = FakeAdapter("fake", CFG)
    out = adapter.predict(None, "prompt")
    assert adapter.seen is None
    assert out["meta"]["input_size"] is None and out["meta"]["sent_size"] is None
