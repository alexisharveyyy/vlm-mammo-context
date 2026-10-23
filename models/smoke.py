"""Phase 2 smoke test: each adapter on the smoke cases, full image and ROI crop.

    python scripts/pinned_step.py --config configs/models.yaml -- \\
        uv run --group models python -m models.smoke --model qwen3_vl_8b

Writes, per model:
  runs/smoke/<model>.jsonl                  one line per (case, image kind)
  runs/smoke/<model>_parse_failures.jsonl   every parse failure with raw text
  runs/smoke/<model>_summary.json           failure rate, timing, versions
Refuses any case that is not in the dev manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

from models import base, images, parse

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--smoke-config", type=Path, default=ROOT / "configs" / "smoke.yaml")
    ap.add_argument("--out", type=Path, default=ROOT / "runs" / "smoke")
    ap.add_argument("--answer-format", choices=sorted(parse.FORMATS), default="plain")
    args = ap.parse_args()

    smoke = yaml.safe_load(args.smoke_config.read_text())
    dev = set(pd.read_csv(ROOT / "data" / "manifests" / "dev.csv", dtype=str)["case_id"])
    if smoke["split"] != "dev" or not set(smoke["cases"]) <= dev:
        print("smoke cases must all be dev cases", file=sys.stderr)
        return 2

    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / f"{args.model}.jsonl"
    fail_path = args.out / f"{args.model}_parse_failures.jsonl"
    for path in (out_path, fail_path):
        path.unlink(missing_ok=True)

    t0 = time.perf_counter()
    adapter = base.load_adapter(args.model)
    load_seconds = time.perf_counter() - t0

    provenance = {
        "commit": os.environ.get("PINNED_COMMIT"),
        "config_sha256": os.environ.get("PINNED_CONFIG_SHA256"),
        "smoke_config_sha256": hashlib.sha256(args.smoke_config.read_bytes()).hexdigest(),
    }
    records = []
    for case_id in smoke["cases"]:
        for kind in smoke["image_kinds"]:
            prompt = f"{smoke['prompts'][kind]}\n\n{parse.FORMATS[args.answer_format]}"
            out = adapter.predict(images.load_case_image(case_id, kind), prompt)
            record = {
                "model": args.model,
                "case_id": case_id,
                "image_kind": kind,
                "prompt_id": f"smoke_neutral_{kind}_{args.answer_format}",
                **out,
                **provenance,
            }
            records.append(record)
            with out_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            if not out["parse"]["ok"]:
                parse.log_failure(
                    fail_path,
                    {"model": args.model, "case_id": case_id, "image_kind": kind},
                    parse.parse(out["raw_text"]),
                    out["raw_text"],
                )
            print(
                f"{case_id} {kind}: {out['meta']['seconds']:.1f}s "
                f"parse_ok={out['parse']['ok']} p_mal={out['p_malignant']}"
            )

    import torch
    import transformers

    summary = {"model": args.model, "answer_format": args.answer_format, **provenance}
    for kind in [None, *smoke["image_kinds"]]:
        rows = [r for r in records if kind is None or r["image_kind"] == kind]
        fails = sum(not r["parse"]["ok"] for r in rows)
        key = kind or "all"
        summary[key] = {
            "calls": len(rows),
            "parse_failures": fails,
            "parse_failure_rate": fails / len(rows),
            "median_seconds": statistics.median(r["meta"]["seconds"] for r in rows),
            "max_seconds": max(r["meta"]["seconds"] for r in rows),
            "median_output_tokens": statistics.median(r["meta"]["output_tokens"] for r in rows),
            "token_probability_available": sum(r["p_malignant"] is not None for r in rows),
        }
    summary["load_seconds"] = round(load_seconds, 1)
    summary["versions"] = {
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "python": platform.python_version(),
        "macos": platform.mac_ver()[0],
    }
    (args.out / f"{args.model}_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
