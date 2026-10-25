"""Resumable study runner (docs/RUN_DESIGN.md).

    caffeinate -dimsu uv run python scripts/pinned_step.py --config configs/models.yaml -- \\
        uv run --group models python -m models.run --tier T0 --model qwen3_vl_8b

Each call (model, image kind, condition, paraphrase, answer format, case) is
appended to runs/<model>/<image_kind>/<condition>/p<k>[_plain].jsonl as soon
as it finishes, and skipped on restart. Calls are ordered case by case so the
image-feature cache hits. Identical inputs (same model, revision, config,
commit, sent pixels and prompt) reuse the first output. After the tier, a
sample of calls is rerun uncached and compared exactly. Test-set runs refuse
to start unless the code descends from the prereg-v1 tag.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from models import images, parse, prompts

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = ROOT / "data" / "manifests"

COLLEAGUE = ["colleague_benign", "colleague_malignant"]
TIERS: dict[str, list[tuple[str, str, str]]] = {
    "T0": [
        ("full", "neutral", "forced"),
        ("roi", "neutral", "forced"),
        ("full", "neutral", "plain"),
        ("roi", "neutral", "plain"),
        ("no_image", "neutral", "forced"),
        ("blank_full", "neutral", "forced"),
        ("blank_roi", "neutral", "forced"),
    ],
    "T1": [("full", c, "forced") for c in COLLEAGUE],
    "T2": [
        ("full", c, "forced")
        for c in ["age_42", "age_68", "history_yes", "history_no", "combined", "irrelevant"]
    ],
    "T3": [("roi", c, "forced") for c in COLLEAGUE],
    "T4": [(k, c, "forced") for k in ["no_image", "blank_full", "blank_roi"] for c in COLLEAGUE],
}
OUTPUT_FIELDS = [
    "raw_text",
    "birads",
    "malignant",
    "confidence",
    "p_malignant",
    "class_mass",
    "parse",
    "meta",
]
COMPARED = ["raw_text", "p_malignant", "class_mass"]


@dataclass(frozen=True)
class Call:
    model: str
    image_kind: str
    condition: str
    paraphrase: int
    answer_format: str
    case_id: str

    @property
    def key(self) -> str:
        return "|".join(
            str(v)
            for v in (
                self.model,
                self.image_kind,
                self.condition,
                self.paraphrase,
                self.answer_format,
                self.case_id,
            )
        )

    def path(self, root: Path) -> Path:
        suffix = "_plain" if self.answer_format == "plain" else ""
        return (
            root
            / self.model
            / self.image_kind
            / self.condition
            / f"p{self.paraphrase}{suffix}.jsonl"
        )


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def prompt_files_sha256() -> str:
    h = hashlib.sha256()
    for path in sorted((ROOT / "prompts").glob("*.yaml")):
        h.update(path.name.encode() + b"\x00" + path.read_bytes() + b"\x00")
    return h.hexdigest()


def image_sha256(image: Image.Image | None) -> str:
    return "no_image" if image is None else images.pixel_sha256(np.asarray(image))


def append_line(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def read_records(path: Path) -> list[dict]:
    """Records of a JSONL file. A cut-off last line is moved to <file>.partial."""
    if not path.exists():
        return []
    raw = path.read_bytes()
    lines = raw.split(b"\n")
    records, keep = [], []
    for i, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
            keep.append(line)
        except json.JSONDecodeError:
            if i < len(lines) - 1 and any(x.strip() for x in lines[i + 1 :]):
                raise ValueError(f"{path}: corrupt line {i + 1} that is not the last") from None
            with path.with_suffix(path.suffix + ".partial").open("ab") as f:
                f.write(line + b"\n")
            path.write_bytes(b"".join(x + b"\n" for x in keep))
    return records


def existing_state(root: Path, model: str) -> tuple[dict[str, dict], dict[str, dict]]:
    """(records by call key, reusable records by input key) for a model."""
    done, by_input = {}, {}
    model_dir = root / model
    if not model_dir.exists():
        return done, by_input
    for path in sorted(model_dir.glob("*/*/*.jsonl")):
        for record in read_records(path):
            done[record["call_key"]] = record
            if record.get("error") is None and record.get("reused_from") is None:
                by_input.setdefault(record["input_key"], record)
    return done, by_input


def calls_for(tier: str, model: str, case_ids: list[str]) -> list[Call]:
    """All calls of a tier in run order: case, then image kind, then prompt."""
    cells = TIERS[tier]
    kinds = list(dict.fromkeys(kind for kind, _, _ in cells))
    out = []
    for case_id in case_ids:
        for kind in kinds:
            for k, condition, fmt in cells:
                if k == kind:
                    for p in prompts.PARAPHRASES:
                        out.append(Call(model, kind, condition, p, fmt, case_id))
    return out


class Runner:
    def __init__(
        self,
        adapter,
        cases: pd.DataFrame,
        out_root: Path,
        provenance: dict,
        load_image: Callable[[str, str], Image.Image | None],
        split: str,
        log: Callable[[str], None] = print,
    ):
        self.adapter = adapter
        self.cases = cases.set_index("case_id", drop=False)
        self.root = out_root
        self.prov = provenance
        self.load_image = load_image
        self.split = split
        self.log = log
        self.failures_path = out_root / adapter.key / "parse_failures.jsonl"

    def input_key(self, sent_sha: str, prompt: str) -> str:
        cfg = self.adapter.cfg
        parts = [
            self.adapter.key,
            cfg["revision"],
            self.prov["config_sha256"],
            self.prov["commit"],
            sent_sha,
            prompt,
        ]
        return sha256_text(json.dumps(parts))

    def prompt_for(self, call: Call) -> str:
        return prompts.render(
            call.condition,
            call.paraphrase,
            call.image_kind,
            self.cases.loc[call.case_id].to_dict(),
            call.answer_format,
        )

    def predict_with_retry(self, sent, prompt, input_size) -> tuple[dict | None, str | None]:
        for attempt in (1, 2):
            try:
                return self.adapter.predict_prepared(sent, prompt, input_size), None
            except Exception as exc:  # any backend failure is recorded, never raised
                self.log(f"call failed (attempt {attempt}): {exc!r}")
                if attempt == 1:
                    self.adapter.reload()
                else:
                    return None, repr(exc)
        return None, "unreachable"

    def run(self, calls: list[Call]) -> list[Call]:
        done, by_input = existing_state(self.root, self.adapter.key)
        for call in calls:
            record = done.get(call.key)
            if record is not None:
                for field in ("commit", "config_sha256", "prompt_files_sha256"):
                    if record.get(field) != self.prov[field]:
                        raise SystemExit(
                            f"refusing to resume: {call.key} was written with {field}="
                            f"{record.get(field)}, current is {self.prov[field]}"
                        )
        todo = [c for c in calls if c.key not in done]
        self.log(f"{self.adapter.key}: {len(calls) - len(todo)} done, {len(todo)} to run")
        computed, start, current = [], time.monotonic(), None
        for n, call in enumerate(todo, 1):
            if current != (call.case_id, call.image_kind):
                current = (call.case_id, call.image_kind)
                image = self.load_image(call.case_id, call.image_kind)
                sent = self.adapter.prepare(image, allow_blank=call.image_kind.startswith("blank"))
                input_size = None if image is None else image.size
                master_sha, sent_sha = image_sha256(image), image_sha256(sent)
            prompt = self.prompt_for(call)
            ikey = self.input_key(sent_sha, prompt)
            reused = by_input.get(ikey)
            if reused is not None:
                outputs, error, reused_from = (
                    {f: reused[f] for f in OUTPUT_FIELDS},
                    None,
                    reused["call_key"],
                )
            else:
                outputs, error = self.predict_with_retry(sent, prompt, input_size)
                outputs = outputs or {f: None for f in OUTPUT_FIELDS}
                reused_from = None
            record = {
                "call_key": call.key,
                "split": self.split,
                "model": call.model,
                "image_kind": call.image_kind,
                "condition": call.condition,
                "paraphrase": call.paraphrase,
                "answer_format": call.answer_format,
                "case_id": call.case_id,
                **outputs,
                "error": error,
                "reused_from": reused_from,
                "prompt_sha256": sha256_text(prompt),
                "image_pixel_sha256": master_sha,
                "sent_pixel_sha256": sent_sha,
                "input_key": ikey,
                **self.prov,
                "written_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            }
            append_line(call.path(self.root), record)
            if error is None and reused_from is None:
                by_input[ikey] = record
                computed.append(call)
            if error is None and not outputs["parse"]["ok"]:
                parse.log_failure(
                    self.failures_path,
                    {"call_key": call.key},
                    parse.parse(outputs["raw_text"]),
                    outputs["raw_text"],
                )
            if n % 25 == 0 or n == len(todo):
                rate = (time.monotonic() - start) / n
                self.log(
                    f"{self.adapter.key}: {n}/{len(todo)} "
                    f"({rate:.2f} s/call, about {rate * (len(todo) - n) / 3600:.1f} h left)"
                )
        return computed

    def audit(self, computed: list[Call], tier: str, seed: int = 0) -> bool:
        """Rerun a sample uncached and compare exactly. True if all identical."""
        if not computed:
            return True
        n = min(len(computed), max(10, len(computed) // 100))
        sample = sorted(random.Random(seed).sample(computed, n), key=lambda c: c.key)
        done, _ = existing_state(self.root, self.adapter.key)
        self.adapter.set_feature_cache(False)
        mismatches = []
        for call in sample:
            image = self.load_image(call.case_id, call.image_kind)
            sent = self.adapter.prepare(image, allow_blank=call.image_kind.startswith("blank"))
            out = self.adapter.predict_prepared(
                sent, self.prompt_for(call), None if image is None else image.size
            )
            if any(out[f] != done[call.key][f] for f in COMPARED):
                mismatches.append(call.key)
        result = {
            "tier": tier,
            "sampled": n,
            "computed": len(computed),
            "mismatches": mismatches,
            **self.prov,
            "written_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        append_line(self.root / self.adapter.key / "determinism_audit.jsonl", result)
        self.log(f"determinism audit: {n} calls, {len(mismatches)} mismatches")
        return not mismatches


def cache_check(adapter, load_image, case_rows: list[dict]) -> bool:
    """Phase 2 equivalence check: cached and uncached outputs must be identical."""
    tests = []
    for row in case_rows:
        sent = adapter.prepare(load_image(row["case_id"], "full"))
        for condition in ["neutral", *COLLEAGUE]:
            tests.append((sent, prompts.render(condition, 1, "full", row)))
    adapter.set_feature_cache(False)
    plain = [adapter.predict_prepared(s, p, None) for s, p in tests]
    adapter.set_feature_cache(True)
    cached = [adapter.predict_prepared(s, p, None) for s, p in tests]
    return all(a[f] == b[f] for a, b in zip(plain, cached, strict=True) for f in COMPARED)


def default_loader(sizes: dict[str, dict[str, tuple[int, int]]]):
    def load(case_id: str, kind: str) -> Image.Image | None:
        if kind == "no_image":
            return None
        if kind.startswith("blank_"):
            w, h = sizes[kind.removeprefix("blank_")][case_id]
            return Image.new("L", (w, h), 0)
        return images.load_case_image(case_id, kind)

    return load


def master_sizes() -> dict[str, dict[str, tuple[int, int]]]:
    out = {}
    for kind, name in [("full", "png_sha256.csv"), ("roi", "roi_checksums.csv")]:
        t = pd.read_csv(MANIFESTS / name, dtype={"width": int, "height": int})
        out[kind] = {r.case_id: (r.width, r.height) for r in t.itertuples()}
    return out


def load_cases(split: str) -> pd.DataFrame:
    cases = pd.read_csv(MANIFESTS / f"{split}.csv", dtype=str)
    order = pd.read_csv(MANIFESTS / "answer_order.csv", dtype=str)
    merged = cases.merge(order, on="case_id", validate="one_to_one")
    if len(merged) != len(cases):
        raise ValueError("answer_order.csv does not cover every case")
    return merged.sort_values("case_id").reset_index(drop=True)


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tier", required=True, choices=sorted(TIERS))
    ap.add_argument("--model", required=True)
    ap.add_argument("--split", default="test", choices=["test", "dev"])
    ap.add_argument("--limit", type=int, help="first N cases (dev only)")
    ap.add_argument("--out", type=Path, help="default runs/ for test, runs/dev/ for dev")
    ap.add_argument("--no-cache", action="store_true", help="disable image-feature caching")
    args = ap.parse_args(argv)

    if args.split == "test":
        if args.limit:
            ap.error("--limit is for the dev split only")
        if git("merge-base", "--is-ancestor", "prereg-v1", "HEAD").returncode != 0:
            print("test-set runs require HEAD to descend from prereg-v1", file=sys.stderr)
            return 2
    commit = os.environ.get("PINNED_COMMIT")
    if not commit:
        print("run through scripts/pinned_step.py (PINNED_COMMIT is not set)", file=sys.stderr)
        return 2
    if sys.platform == "darwin":
        subprocess.Popen(["caffeinate", "-dimsu", "-w", str(os.getpid())])

    from models import base

    provenance = {
        "commit": commit,
        "config_sha256": os.environ["PINNED_CONFIG_SHA256"],
        "prompt_files_sha256": prompt_files_sha256(),
    }
    cases = load_cases(args.split)
    if args.limit:
        cases = cases.head(args.limit)
    out_root = args.out or (ROOT / "runs" if args.split == "test" else ROOT / "runs" / "dev")
    loader = default_loader(master_sizes())
    adapter = base.load_adapter(args.model)

    use_cache = not args.no_cache
    if use_cache:
        dev_rows = load_cases("dev").head(5).to_dict("records")
        use_cache = cache_check(adapter, loader, dev_rows)
        append_line(
            out_root / args.model / "cache_checks.jsonl",
            {
                "identical": use_cache,
                "dev_cases": [r["case_id"] for r in dev_rows],
                **provenance,
                "written_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            },
        )
        print(f"image-feature cache {'on' if use_cache else 'OFF: outputs differed'}")
    adapter.set_feature_cache(use_cache)

    runner = Runner(adapter, cases, out_root, provenance, loader, args.split)
    computed = runner.run(calls_for(args.tier, args.model, list(cases["case_id"])))
    ok = runner.audit(computed, args.tier)
    return 0 if ok else 3


if __name__ == "__main__":
    sys.exit(main())
