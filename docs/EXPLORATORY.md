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
