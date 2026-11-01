# Exploratory analyses

Analyses we may add later. Every item here is exploratory: it is not part of
the pre-specified analysis plan frozen at tag `prereg-v1`
(`docs/PREREGISTRATION.md`), it is not counted in the primary or secondary
test families, and any result from it is reported as exploratory. Each entry
gives the date it was added and what was known when it was added.

## 1. Surface features and Qwen3-VL's below-chance answers (added 2026-10-27)

- **Status:** exploratory, not part of the frozen plan. Done on 2026-10-27
  with tier T0 only: `uv run python -m eval.surface_features` writes
  `reports/exploratory/surface_features.md` (aggregates only; the per-case
  pixel features stay in `data/` and are not committed).
- **Question:** which surface image features predict Qwen3-VL's
  below-chance answers on full images (`neutral`, forced format)? Candidate
  features include brightness, image size, and mass versus calcification.
- **Known when added:** the Phase 4 baseline (`reports/baseline.md`), in
  which Qwen3-VL's AUROC of `p_malignant` is significantly below 0.5.

## Note: age and history are not covered by the position and decoding checks

- **Status:** a limit of the Phase 7 scope, recorded on 2026-10-27, blind to
  tiers T1 to T4 (`docs/DEVIATIONS.md`, entry 7). Not an analysis.
- **What:** the position check (context sentence after the task) and the
  second decoding setting (sampling) rerun only the colleague conditions.
  The age and history contrasts (H3 and H4) are checked for agreement across
  paraphrases and under the strict parser, which use the existing outputs,
  but whether they depend on where the sentence sits or on greedy decoding
  is not tested.
- **Why:** run time. The two checks cost about 16 hours for the colleague
  contrasts and about 44 hours for all four primary contrasts. The colleague
  contrasts were kept because their sentence states an answer outright, so
  they are the most direct test of a prompt shifting the reading.
- **If added later:** rerun `age_42`, `age_68`, `history_yes` and
  `history_no` in both variants (about 19 hours for the position check on
  three models and 9 hours for the decoding check on Qwen3-VL), reported as
  exploratory.
