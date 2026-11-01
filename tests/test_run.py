"""The resumable runner, with a fake adapter and synthetic images."""

import json
import time

import numpy as np
import pandas as pd
import pytest
from PIL import Image

from models import base, run

PROV = {"commit": "a" * 40, "config_sha256": "b" * 64, "prompt_files_sha256": "c" * 64}


class FakeAdapter(base.Adapter):
    def __init__(self, noisy=False):
        super().__init__(
            "fake",
            {
                "repo_id": "fake/m",
                "revision": "r" * 40,
                "resize": {"type": "long_side", "size": 32},
            },
        )
        self.calls, self.noisy = 0, noisy

    def load(self):
        pass

    def generate(self, image, prompt):
        self.calls += 1
        seed = len(prompt) + (0 if image is None else int(np.asarray(image).sum()))
        if self.noisy:
            seed += self.calls
        label = "malignant" if seed % 2 else "benign"
        text = f"BI-RADS: {seed % 6}\nAssessment: {label}\nConfidence: {seed % 100}"
        return base.Generation(text, [], None, 0.0)

    def decode(self, token_ids):
        return ""

    def class_token_ids(self):
        return {"benign": {0}, "malignant": {1}}


CASES = pd.DataFrame(
    {
        "case_id": ["A", "B", "C"],
        "synthetic_age": ["42", "68", "42"],
        "synthetic_family_history": ["absent", "present", "present"],
        "answer_order_offset": ["0", "1", "0"],
    }
)


def loader(case_id, kind):
    if kind == "no_image":
        return None
    if kind.startswith("blank_"):
        return Image.new("L", (30, 60), 0)
    rng = np.random.default_rng(ord(case_id) + len(kind))
    return Image.fromarray(rng.integers(0, 256, (60, 30), dtype=np.uint8))


def make(tmp_path, adapter=None, prov=PROV):
    return run.Runner(
        adapter or FakeAdapter(), CASES, tmp_path, prov, loader, "dev", log=lambda m: None
    )


def lines(tmp_path):
    return [
        json.loads(x)
        for p in sorted(tmp_path.glob("fake/*/*/*.jsonl"))
        for x in p.read_text().splitlines()
    ]


def test_t0_writes_every_call_and_reuses_identical_inputs(tmp_path):
    runner = make(tmp_path)
    calls = run.calls_for("T0", "fake", ["A", "B", "C"])
    assert len(calls) == 3 * 7 * 3
    runner.run(calls)
    records = lines(tmp_path)
    assert len(records) == len(calls) and len({r["call_key"] for r in records}) == len(calls)
    no_image = [r for r in records if r["image_kind"] == "no_image"]
    # neutral no_image prompts depend only on the answer order, so case C (same
    # offset as A) reuses A's outputs; B (other offset) gets new calls.
    reused = {r["case_id"] for r in no_image if r["reused_from"]}
    assert reused == {"C"}
    assert runner.adapter.calls == len(calls) - sum(bool(r["reused_from"]) for r in records)
    blank = [r for r in records if r["image_kind"] == "blank_full"]
    assert all(r["sent_pixel_sha256"] == blank[0]["sent_pixel_sha256"] for r in blank)
    assert (tmp_path / "fake/full/neutral/p1.jsonl").exists()
    assert (tmp_path / "fake/full/neutral/p1_plain.jsonl").exists()


def test_resume_skips_completed_calls(tmp_path):
    calls = run.calls_for("T1", "fake", ["A", "B"])
    make(tmp_path).run(calls[:5])
    second = FakeAdapter()
    make(tmp_path, second).run(calls)
    assert second.calls == len(calls) - 5
    assert len(lines(tmp_path)) == len(calls)


def test_cut_off_line_is_set_aside_and_redone(tmp_path):
    calls = run.calls_for("T1", "fake", ["A"])
    make(tmp_path).run(calls)
    path = calls[-1].path(tmp_path)
    content = path.read_text().splitlines()
    path.write_text("\n".join(content[:-1]) + "\n" + content[-1][: len(content[-1]) // 2])
    redo = FakeAdapter()
    make(tmp_path, redo).run(calls)
    assert redo.calls == 1
    assert path.with_suffix(".jsonl.partial").exists()
    assert len(lines(tmp_path)) == len(calls)


def test_refuses_to_resume_with_other_commit(tmp_path):
    calls = run.calls_for("T1", "fake", ["A"])
    make(tmp_path).run(calls[:2])
    with pytest.raises(SystemExit, match="refusing to resume"):
        make(tmp_path, prov={**PROV, "commit": "d" * 40}).run(calls)


def test_calls_are_case_major():
    calls = run.calls_for("T0", "fake", ["A", "B"])
    first_b = next(i for i, c in enumerate(calls) if c.case_id == "B")
    assert all(c.case_id == "A" for c in calls[:first_b])
    assert all(c.case_id == "B" for c in calls[first_b:])


def test_audit_detects_nondeterminism(tmp_path):
    calls = run.calls_for("T1", "fake", ["A", "B"])
    runner = make(tmp_path)
    computed = runner.run(calls)
    assert runner.audit(computed, "T1")
    noisy = make(tmp_path, FakeAdapter(noisy=True))
    assert not noisy.audit(computed, "T1")
    audit = (tmp_path / "fake/determinism_audit.jsonl").read_text().splitlines()
    assert len(audit) == 2 and json.loads(audit[1])["mismatches"]


def test_tiers_match_the_run_design():
    assert {k for k, _, _ in run.TIERS["T3"]} == {"roi"}
    assert len(run.TIERS["T2"]) == 6 and len(run.TIERS["T4"]) == 6
    assert ("roi", "neutral", "plain") in run.TIERS["T0"]


def test_computed_calls_match_an_uninterrupted_run(tmp_path):
    calls = run.calls_for("T4", "fake", ["A", "B", "C"])
    runner = make(tmp_path)
    computed = runner.run(calls)
    assert runner.computed_calls(calls) == computed


def test_computed_calls_cover_a_restarted_run(tmp_path):
    calls = run.calls_for("T1", "fake", ["A", "B"])
    first = make(tmp_path).run(calls[:5])
    runner = make(tmp_path)
    second = runner.run(calls)
    assert runner.computed_calls(calls) == first + second


def test_audit_runs_once_per_tier_and_commit(tmp_path):
    calls = run.calls_for("T1", "fake", ["A"])
    runner = make(tmp_path)
    assert not runner.audited("T1")
    assert runner.audit(runner.run(calls), "T1")
    assert runner.audited("T1") and not runner.audited("T2")
    assert not make(tmp_path, prov={**PROV, "commit": "d" * 40}).audited("T1")


def test_watchdog_exits_when_no_call_finishes():
    exits, messages = [], []
    dog = run.Watchdog(0.05, log=messages.append, exit=exits.append, poll_s=0.01).start()
    dog.thread.join(timeout=2)
    assert exits == [run.STALL_EXIT]
    assert "no model call finished" in messages[-1]


def test_watchdog_stays_quiet_while_calls_finish():
    exits = []
    dog = run.Watchdog(0.2, log=lambda m: None, exit=exits.append, poll_s=0.01).start()
    adapter = run.with_heartbeat(FakeAdapter(), dog.beat)
    sent = adapter.prepare(loader("A", "full"))
    for _ in range(30):
        adapter.predict_prepared(sent, "prompt", None)
        time.sleep(0.02)
    dog.stop()
    dog.thread.join(timeout=2)
    assert exits == []


def test_variants_are_full_image_forced_cells_of_study_conditions():
    for name in ("position_end", "sampled"):
        variant = run.load_variant(name)
        cells = run.variant_cells(variant)
        assert {k for k, _, _ in cells} == {"full"} and {f for _, _, f in cells} == {"forced"}
        assert set(variant["models"]) <= {"qwen3_vl_8b", "medgemma_1_5_4b", "internvl3_5_8b"}
        assert all(c in run.prompts.CONDITIONS for _, c, _ in cells)
    # neutral prompts do not depend on the position, so position_end reuses the study's.
    assert "neutral" not in run.load_variant("position_end")["conditions"]
    assert run.load_variant("sampled")["decoding"]["do_sample"] is True
    with pytest.raises(SystemExit, match="unknown variant"):
        run.load_variant("nope")


def test_variant_runs_record_the_variant_and_move_the_context(tmp_path):
    variant = run.load_variant("position_end")
    prov = PROV | {"variant": "position_end", "variant_sha256": run.variant_sha256(variant)}
    runner = run.Runner(
        FakeAdapter(), CASES, tmp_path, prov, loader, "dev", log=lambda m: None, position="end"
    )
    calls = run.calls_for_cells(run.variant_cells(variant), "fake", ["A", "B"])
    assert len(calls) == 2 * 2 * 3
    runner.run(calls)
    records = lines(tmp_path)
    assert len(records) == len(calls)
    assert all(r["variant"] == "position_end" for r in records)
    call = calls[0]
    assert (
        runner.prompt_for(call)
        .split("\n\n")[0]
        .endswith(
            run.prompts.context_sentence(call.condition, call.paraphrase, CASES.iloc[0].to_dict())
        )
    )
    # Resuming under a changed variant block is refused.
    changed = run.Runner(
        FakeAdapter(),
        CASES,
        tmp_path,
        prov | {"variant_sha256": "d" * 64},
        loader,
        "dev",
        log=lambda m: None,
    )
    with pytest.raises(SystemExit, match="variant_sha256"):
        changed.run(calls)


def test_variant_inputs_are_never_reused_from_the_study(tmp_path):
    variant = run.load_variant("sampled")
    study = make(tmp_path)
    sampled = run.Runner(
        FakeAdapter(),
        CASES,
        tmp_path,
        PROV | {"variant": "sampled", "variant_sha256": run.variant_sha256(variant)},
        loader,
        "dev",
        log=lambda m: None,
    )
    assert study.input_key("x", "prompt") != sampled.input_key("x", "prompt")
