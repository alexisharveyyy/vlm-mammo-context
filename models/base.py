"""One interface for every model: predict(image, prompt) -> answer dict.

    adapter = load_adapter("qwen2_vl_7b")            # from configs/models.yaml
    out = adapter.predict(load_case_image(case_id, "full"), prompt)

predict() resizes the master with the model's policy, generates greedily with
a fixed seed, parses the answer and, when the backend exposes per-step
logits, reads the probability of "malignant" vs "benign" at the position
where the answer word starts. The returned dict:

    raw_text      the generated text, unmodified
    birads        int 0..6 or None
    malignant     True, False or None
    confidence    0..100 or None (the model's stated confidence)
    p_malignant   P(malignant) / (P(malignant) + P(benign)) for the first
                  token of the answer word, or None
    class_mass    P(malignant) + P(benign) at that position, or None
    parse         parser output: rules, errors, ok
    meta          model, revision, image size sent, tokens, seconds
"""

from __future__ import annotations

import math
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

from models import images, parse

CONFIG = Path(__file__).resolve().parents[1] / "configs" / "models.yaml"
ANSWER_SLOT = re.compile(r"assessment\s*[:=\-]\s*$", re.IGNORECASE)
CLASS_WORDS = {
    "benign": ["benign", " benign", "Benign", " Benign"],
    "malignant": ["malignant", " malignant", "Malignant", " Malignant"],
}


@dataclass
class Generation:
    text: str
    token_ids: list[int]
    # log-probabilities over the vocabulary at each generated step, or None
    step_logprobs: Sequence[np.ndarray] | None
    seconds: float


def class_probability(
    token_ids: list[int],
    decode: Callable[[list[int]], str],
    step_logprobs: Sequence[np.ndarray] | None,
    class_ids: dict[str, set[int]],
) -> dict | None:
    """P(malignant) vs P(benign) at the first token after "Assessment:"."""
    if step_logprobs is None or class_ids["benign"] & class_ids["malignant"]:
        return None
    for step in range(len(token_ids)):
        if ANSWER_SLOT.search(decode(token_ids[:step])):
            logp = step_logprobs[step]
            mass = {
                k: float(sum(math.exp(logp[i]) for i in sorted(ids)))
                for k, ids in class_ids.items()
            }
            total = mass["benign"] + mass["malignant"]
            if total == 0:
                return None
            return {"p_malignant": mass["malignant"] / total, "class_mass": total, "step": step}
    return None


def check_not_mask(image: Image.Image) -> None:
    if np.unique(np.asarray(image.convert("L"))).size <= 2:
        raise ValueError("binary image: masks are never shown to a model")


class Adapter(ABC):
    def __init__(self, key: str, cfg: dict):
        self.key = key
        self.cfg = cfg

    @abstractmethod
    def load(self) -> None: ...

    @abstractmethod
    def generate(self, image: Image.Image, prompt: str) -> Generation: ...

    @abstractmethod
    def decode(self, token_ids: list[int]) -> str: ...

    @abstractmethod
    def class_token_ids(self) -> dict[str, set[int]]: ...

    def predict(self, image: Image.Image, prompt: str) -> dict:
        check_not_mask(image)
        sent = images.resize(image, self.cfg["resize"])
        gen = self.generate(sent, prompt)
        parsed = parse.parse(gen.text)
        probs = class_probability(
            gen.token_ids, self.decode, gen.step_logprobs, self.class_token_ids()
        )
        return {
            "raw_text": gen.text,
            "birads": parsed.birads,
            "malignant": parsed.malignant,
            "confidence": parsed.confidence,
            "p_malignant": probs["p_malignant"] if probs else None,
            "class_mass": probs["class_mass"] if probs else None,
            "parse": parse.as_dict(parsed),
            "meta": {
                "model": self.key,
                "repo_id": self.cfg["repo_id"],
                "revision": self.cfg["revision"],
                "input_size": list(image.size),
                "sent_size": list(sent.size),
                "output_tokens": len(gen.token_ids),
                "seconds": round(gen.seconds, 3),
            },
        }


class TransformersAdapter(Adapter):
    """Hugging Face transformers image-text-to-text models on MPS or CPU."""

    def load(self) -> None:
        import torch
        from transformers import AutoModelForImageTextToText, AutoProcessor

        self.torch = torch
        self.device = self.cfg.get("device", "mps")
        dtype = getattr(torch, self.cfg.get("dtype", "bfloat16"))
        kwargs = {"revision": self.cfg["revision"], **self.cfg.get("load_kwargs", {})}
        self.processor = AutoProcessor.from_pretrained(
            self.cfg["repo_id"], **kwargs, **self.cfg.get("processor_kwargs", {})
        )
        self.model = AutoModelForImageTextToText.from_pretrained(
            self.cfg["repo_id"], dtype=dtype, **kwargs
        ).to(self.device)
        self.model.eval()
        self.tokenizer = self.processor.tokenizer

    def messages(self, prompt: str) -> list[dict]:
        return [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]

    def generate(self, image: Image.Image, prompt: str) -> Generation:
        torch = self.torch
        text = self.processor.apply_chat_template(
            self.messages(prompt), add_generation_prompt=True, tokenize=False
        )
        inputs = self.processor(text=[text], images=[image], return_tensors="pt").to(self.device)
        if "pixel_values" in inputs:
            inputs["pixel_values"] = inputs["pixel_values"].to(self.model.dtype)
        torch.manual_seed(self.cfg["decoding"]["seed"])
        start = time.perf_counter()
        with torch.inference_mode():
            out = self.model.generate(
                **inputs,
                do_sample=False,
                max_new_tokens=self.cfg["decoding"]["max_new_tokens"],
                output_logits=True,
                return_dict_in_generate=True,
                pad_token_id=self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
            )
        if self.device == "mps":
            torch.mps.synchronize()
        seconds = time.perf_counter() - start
        new = out.sequences[0, inputs["input_ids"].shape[1] :].tolist()
        eos = set(self._eos_ids())
        while new and new[-1] in eos:
            new.pop()
        logprobs = [
            torch.log_softmax(step[0].float(), dim=-1).cpu().numpy()
            for step in out.logits[: len(new)]
        ]
        return Generation(self.decode(new), new, logprobs, seconds)

    def _eos_ids(self) -> list[int]:
        eos = self.model.generation_config.eos_token_id
        return eos if isinstance(eos, list) else [eos]

    def decode(self, token_ids: list[int]) -> str:
        return self.tokenizer.decode(token_ids, skip_special_tokens=True)

    def class_token_ids(self) -> dict[str, set[int]]:
        return {
            label: {self.tokenizer.encode(w, add_special_tokens=False)[0] for w in words}
            for label, words in CLASS_WORDS.items()
        }


ADAPTERS: dict[str, type[Adapter]] = {"transformers": TransformersAdapter}


def load_config(path: Path = CONFIG) -> dict:
    return yaml.safe_load(path.read_text())


def load_adapter(key: str, path: Path = CONFIG) -> Adapter:
    cfg = load_config(path)["models"][key]
    adapter = ADAPTERS[cfg["backend"]](key, cfg)
    adapter.load()
    return adapter
