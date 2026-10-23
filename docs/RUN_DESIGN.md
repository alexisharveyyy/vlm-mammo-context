# Run design for Phases 4 and 5

This document fixes how the test-set runs are executed. The analysis plan is
in `PREREGISTRATION.md`; this file covers execution only. The runner is
implemented at the start of Phase 4 to this design.

## Units

One **call** is one model answering one prompt about one case:

    (model, image_kind, condition, paraphrase, answer_format, case_id)

- `model`: `qwen3_vl_8b`, `medgemma_1_5_4b`, `internvl3_5_8b`
  (`configs/models.yaml`).
- `image_kind`: `full`, `roi`, `no_image` or `blank_image` (`blank_full` and
  `blank_roi` for a black image of the size of the full-image or ROI-crop
  master). A blank image is a single value, so it would be refused by the
  mask guard; the runner passes it with an explicit `allow_blank` flag that
  is accepted only for `blank_image` calls and only for an all-zero image.
- `condition`: one of the nine prompt conditions in `prompts/`.
- `paraphrase`: 1, 2 or 3.
- `answer_format`: `forced` (primary) or `plain` (neutral condition only).

## Output layout

    runs/<model>/<image_kind>/<condition>/p<paraphrase>[_plain].jsonl
    runs/<model>/parse_failures.jsonl
    runs/run_log.jsonl

Each JSONL line is one call: the call key, the full `predict()` output
(`raw_text`, `birads`, `malignant`, `confidence`, `p_malignant`,
`class_mass`, `parse`, `meta`), the prompt SHA-256, the image pixel SHA-256,
`commit`, `config_sha256`, `prompt_files_sha256`, a UTC timestamp, and
`reused_from` when the output was reused (see "Identical inputs"). Outputs
only; no images, no pixel data.

## Resumability

- **Append as each call finishes.** Each result is written as one line,
  flushed and `fsync`ed before the next call starts. Nothing is held in
  memory across calls.
- **Skip completed calls on restart.** On start the runner reads every
  existing line, builds the set of completed call keys, and runs only the
  missing calls. A trailing line that is not valid JSON (a write cut off by a
  crash or power loss) is moved to `<file>.partial` and the call is redone.
- **Same code, same config.** A run resumes only if the existing lines carry
  the current `commit`, `config_sha256` and `prompt_files_sha256`. Otherwise
  the runner refuses and names the mismatch. Outputs from two different
  commits are never mixed in one file; a code change mid-run means a new
  run directory and a note in `docs/DEVIATIONS.md`.
- **Pinned and logged.** Every run starts through `scripts/pinned_step.py`,
  which refuses uncommitted code and appends the commit, config hash, command,
  timing and exit code to `runs/run_log.jsonl`. Each resume is a new log line.
- **No sleep.** Every run is wrapped in `caffeinate -dimsu` so macOS does not
  sleep, idle the disk or stop the process while the run is going:

      caffeinate -dimsu uv run python scripts/pinned_step.py \
          --config configs/models.yaml -- \
          uv run --group models python -m models.run --tier T1 --model qwen3_vl_8b

- **Progress commits.** Completed JSONL files are committed at the end of each
  tier (outputs under `runs/` do not block the pinned runner).

## Image-feature caching

Tested on the dev set in Phase 2 (one case, three prompts, both image kinds,
all three models): caching the vision encoder output of an image across
prompts gives **bit-identical** text, `p_malignant` and `class_mass`, and
saves 18 to 21% per call for Qwen3-VL, 45 to 48% for MedGemma 1.5 and 10 to
13% for InternVL3.5. Three repeated uncached calls were also bit-identical
for every model.

The cache wraps the model's `get_image_features` (with `functools.wraps`, so
transformers sees the original signature) and keys it on the SHA-256 of the
pixel tensor and the grid arguments. It holds one image at a time and is
cleared when the image changes. Calls are therefore ordered case by case:
within a tier, all conditions and paraphrases of one case run back to back.

Before each model's first test-set tier, the runner repeats the Phase 2
equivalence check on 5 dev cases. If any output differs, caching is turned
off for that model and the change is recorded in the run log.

## Identical inputs

Greedy decoding was deterministic in Phase 2, so two calls with the same
model, revision, image pixels and prompt give the same output. The runner
keys each call on `sha256(model, revision, sent-image pixel hash or
"no_image", prompt)` and reuses an existing output for a repeated key,
writing the call with `reused_from` set to the original call. This applies
mostly to `no_image` (the neutral and colleague prompts do not depend on the
case) and to `blank_image` for MedGemma (every blank image letterboxes to the
same 896 x 896 black square).

**Determinism audit.** After each tier, 1% of non-reused calls (at least 10)
are rerun with caching off and compared exactly. Any difference stops the run
and is reported.

## Priority order (tiers)

Each tier runs all three models (Qwen3-VL, then MedGemma 1.5, then
InternVL3.5) before the next tier starts. Hours are estimates from the Phase 2
smoke medians, with image-feature caching and identical-input reuse.

| Tier | Phase | Calls per model | Content | Estimated hours (Qwen / MedGemma / InternVL) |
|---|---|---:|---|---|
| T0 | 4 | 3,000 | neutral, forced, full and ROI | 3.1 / 1.5 / 4.3 |
| T0 | 4 | 3,000 | neutral, plain format, full and ROI | 3.1 / 1.5 / 4.3 |
| T0 | 4 | 4,500 | no_image, blank_full and blank_roi x neutral (no_image mostly reused) | 3.6 / 0.0 / 4.7 |
| T1 | 5 | 3,000 | colleague_benign, colleague_malignant, full | 4.3 / 1.3 / 3.5 |
| T2 | 5 | 9,000 | age_42, age_68, history_yes, history_no, combined, irrelevant, full | 12.5 / 3.5 / 10.3 |
| T3 | 5 | 3,000 | colleague_benign, colleague_malignant, ROI | 1.7 / 1.3 / 5.0 |
| T4 | 5 | 9,000 | no_image, blank_full and blank_roi x colleague_benign, colleague_malignant (no_image mostly reused) | 7.2 / 0.0 / 9.4 |

T0 is the Phase 4 baseline; Phase 5 starts at T1 and reuses the T0 neutral
outputs. Total: about 86 hours (Qwen 35, MedGemma 9, InternVL 42). The
neutral full-image tier is also the reference for every Phase 5 contrast, so
it is never rerun.

## Failures

- A call that raises (out of memory, MPS error) is retried once after the
  model is reloaded. If it fails again, the call is written with
  `error` set and no answer, and the run continues. Errors are listed in the
  tier report and count as missing, never as an answer.
- A parse failure is not an error: the call is written normally and also
  appended to `runs/<model>/parse_failures.jsonl` with the raw text.
- Every cell (model, image kind, condition, paraphrase, format) ends as
  complete or as pending with a stated reason.
