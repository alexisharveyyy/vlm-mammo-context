# Phase 7 robustness design

Phase 7 asks whether the findings are artifacts of one prompt wording, one
prompt layout, one parser or one decoding setting. The analysis plan
(`docs/PREREGISTRATION.md`, tag `prereg-v1`) names these checks in section 8
(sensitivity 2) and section 9 (agreement across paraphrases; position of the
context sentence; a second decoding setting for one model; the strict
parser). This document fixes how each is run and analyzed. It was written on
2026-10-27, while Phase 5 was running and before any tier T1 to T4 output
was read; it was developed on synthetic outputs and the tier T0 outputs only.

Every check here is a robustness check. None adds a confirmatory test, and
none changes the primary or key secondary families. Sensitivity 2 repeats
the primary tests under the strict parser, with Holm within its own 12
tests, and is reported as a sensitivity analysis.

## Checks

### R1. Agreement across paraphrases (no new runs)

Every cell has three paraphrases of the same prompt.

- **Per cell:** among cases with three valid answers, the share whose three
  answers agree (Wilson 95% interval), and Fleiss' kappa for the three
  paraphrases as raters of the binary answer.
- **Per primary contrast** (H1 to H4, each model): the malignant rate shift
  computed from each paraphrase alone, with case-bootstrap 95% intervals,
  and whether the three paraphrase estimates share the sign of the pooled
  estimate.

### R2. Position of the context sentence (new runs: `position_end`)

The study prompt is `<intro> [<context>] <task>`. The variant moves the
context sentence after the task: `<intro> <task> <context>`. The frozen
prompt text in `prompts/` is unchanged; only its order differs
(`models/prompts.py`, `position="end"`).

- **Runs:** the six context conditions of the primary contrasts
  (`colleague_benign`, `colleague_malignant`, `age_42`, `age_68`,
  `history_yes`, `history_no`), full images, forced format, three
  paraphrases, all 500 test cases, all three models. `neutral` has no
  context sentence, so its prompt is identical in both positions and the
  study's `neutral` outputs are the reference.
- **Analysis:** for each model and primary contrast, the shift with the
  context at the end, and its difference from the study shift (end minus
  middle), each with paired case-bootstrap 95% intervals.

### R3. Strict parser (sensitivity 2; no new runs)

The primary analysis repeated with `models.parse.parse_strict`, as frozen at
`prereg-v1`: an answer is valid only if the whole output is exactly
`BI-RADS: <0-6>` / `Assessment: benign|malignant` / `Confidence: <0-100>`,
lowercase class word, nothing else. The 12 primary contrasts are recomputed
from the strictly valid answers, with bootstrap p-values and Holm within
these 12. Reported with the number of answers per cell that are valid under
the lenient but not the strict rules.

The strict rules are case-sensitive, and they stay as frozen. Most of
MedGemma's answers and many of InternVL's write "Benign" or "Malignant"
with a capital letter, which only the lenient rules accept. Coverage on the
tier T0 outputs (valid answers under the lenient rules that are also valid
under the strict rules; `models.parse.parse_strict`):

| Model | All T0 cells | Full image, `neutral`, forced |
|---|---|---|
| Qwen3-VL | 7,581 of 7,581 (100%) | 1,500 of 1,500 (100%) |
| MedGemma 1.5 | 1 of 10,000 (0.01%) | 0 of 1,500 (0%) |
| InternVL3.5 | 3,977 of 9,459 (42.0%) | 444 of 1,500 (29.6%) |

So sensitivity 2 cannot be computed for MedGemma (no case has a strictly
valid answer in the reference cell; its rows are reported as having no
data), and for InternVL it rests on a minority of the answers. The
reference cell is the same in every primary contrast's `neutral` arm, so
these shares bound the data available to S2. This is also listed in
`docs/THREATS.md`.

### R4. Second decoding setting for one model (new runs: `sampled`)

The study decodes greedily with seed 0. Under greedy decoding the seed has no
effect (the determinism audits show identical reruns), so a second seed
alone would reproduce the study outputs. The second setting therefore
samples: temperature 0.7, top_p 1.0, seed 1 set before every call
(`configs/robustness.yaml`). `p_malignant` is read from the raw logits at the
first token after "Assessment:", as in the study.

- **Model:** Qwen3-VL, chosen on the tier T0 outputs only (full images,
  `neutral`): 74% of its valid greedy answers have `p_malignant` between 0.2
  and 0.8, against 29% for InternVL and 0.4% for MedGemma, so sampling has
  the most room to change its answers (`docs/DEVIATIONS.md`, entry 6).
- **Runs:** `neutral` and the six context conditions, full images, forced
  format, three paraphrases, all 500 test cases.
- **Analysis:** for each primary contrast, the shift under sampling and its
  difference from the greedy shift (sampled minus greedy), with paired
  case-bootstrap 95% intervals; and per condition, the share of (case,
  paraphrase) pairs whose sampled answer equals the greedy answer (Wilson
  interval).

## Reading rule

Fixed now, before the results: a primary result that is significant in the
primary analysis is described as robust to a check when the check's estimate
has the same sign and its 95% interval excludes 0. A primary result that is
not significant is described as unchanged by a check when the check's 95%
interval includes 0. Anything else is reported as sensitivity to that check.
This is a description, not a test.

## Cost and order

Estimated from the tier T0 outputs: the mean generation time per call on
full images in the forced format (Qwen3-VL 5.11 s, MedGemma 1.71 s,
InternVL3.5 4.28 s) times the T0 ratio of wall-clock time to generation
time (1.04, 1.06 and 1.03). Context prompts are a sentence longer than
`neutral`, and sampling may change the answer length, so these are
estimates.

| Run | Calls | Qwen3-VL | MedGemma | InternVL3.5 | Total |
|---|---:|---:|---:|---:|---:|
| `position_end` as designed: six conditions of the primary contrasts | 9,000 per model | 13.3 h | 4.5 h | 11.0 h | 28.8 h |
| `position_end` limited to `colleague_benign` and `colleague_malignant` (`neutral` is unchanged by position) | 3,000 per model | 4.4 h | 1.5 h | 3.7 h | 9.6 h |
| `sampled`: `neutral` and the six conditions, Qwen3-VL | 10,500 | 15.5 h | | | 15.5 h |

No variant runs until Phase 5 is complete. They run with
`sh scripts/run_variant.sh <variant>`, `position_end` first, each after a
dev dry run on three cases, as the tiers did.

## Outputs

`Rscript analysis/run_robustness.R --final` reads `runs/` and
`runs/robustness/<variant>/` and writes `reports/robustness.md` and the
tables in `reports/robustness/`. A check whose runs are incomplete is listed
as pending. `uv run python -m eval.crosscheck --robustness` recomputes its
point estimates in Python.
