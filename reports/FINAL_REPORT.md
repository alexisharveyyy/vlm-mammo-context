# Same Image, Different Answer: Prompt Context Sensitivity of Vision-Language Models in Mammography

**Final report.** Alexis Harvey, Louisiana State University.

This is a study of model behavior. It is not a diagnostic tool, it is not
intended for clinical use, and it makes no clinical claims.

> **Status: written; reproduction check pending.** Setup, data, models,
> protocol, statistics and deviations are written from the frozen plan and
> the repository. The results in sections 3, 6, 8, 9 and 12 are copied from
> the generated reports and the committed outputs (2026-11-02), without
> interpretation. The summary (section 1), the discussion (section 10) and
> the Phase 7 threats (section 11) are written by the author. One marked
> placeholder remains: the fresh-clone check (section 12).
> `scripts/final_audit.sh` fails while any placeholder remains.

## 1. Summary

This study tests whether open vision-language models change their reading of the same mammogram when only the text of the prompt changes. Three models (Qwen3-VL-8B, MedGemma 1.5 4B and InternVL3.5-8B) read 500 test cases from CBIS-DDSM under paired prompt conditions: a neutral prompt, a colleague's stated opinion (benign or malignant), a synthetic patient age (42 or 68), a synthetic family history (present or absent), and a length-matched irrelevant sentence. The analysis plan was frozen before any test-set run, and the study comprised 103,500 model calls.

With the neutral prompt on full images, no model separated benign from malignant cases better than chance (AUROC 0.429 to 0.547), and Qwen3-VL was significantly below chance. The prompt text still moved the answers. A colleague's malignant opinion raised the malignant-answer rate by 39.9, 66.1 and 85.1 percentage points for Qwen3-VL, MedGemma and InternVL3.5. An older age and a positive family history raised it by 10.7 to 30.1 points for Qwen3-VL and InternVL3.5, with no measurable effect on MedGemma. Changing only the order of the two answer options shifted Qwen3-VL and InternVL3.5 by about 23 points. The colleague effect held when the context sentence was moved and under sampled decoding. Models that cannot read these images still return readings that follow the wording of the request, which argues for testing prompt sensitivity, not only accuracy, before such models are considered for clinical decision support.

## 2. Question and scope

When the image stays the same, do vision-language models change their
mammogram reading because of what the prompt says: patient context, a
colleague's opinion, or irrelevant text?

The study reads 500 test mammograms with three open models under nine
prompt conditions and five image conditions, and measures how the answer
changes within each case. It measures sensitivity to prompt text. It does
not measure how well the models diagnose, and the models are not suitable
for that (section 8.1).

The analysis plan was pre-specified and frozen at tag `prereg-v1` before
any test-set run (`docs/PREREGISTRATION.md`, SHA-256
`3ae8ae33638b2eb6353eeb199acaa869d1369d21d95527862e8afd68acde8423`). It was
not registered with an external registry. Changes after the tag are in
`docs/DEVIATIONS.md` and summarized in section 9.

## 3. Setup

- **Hardware:** one Apple M2 Max laptop with 64 GB of unified memory; all
  models run locally with PyTorch on the Metal (MPS) backend.
- **Software:** Python 3.12 with exact pins in `pyproject.toml` and
  `uv.lock` (torch 2.14.1, transformers 5.20.2); R 4.4.0 with packages
  pinned in `analysis/renv.lock`; the viewer with Node and
  `viewer/package-lock.json`.
- **Provenance:** every model call goes through `scripts/pinned_step.py`,
  which refuses uncommitted code and records the commit and the SHA-256 of
  `configs/models.yaml` in each output record. Test-set runs refuse to start
  unless the code descends from `prereg-v1`.
- **Runs** (`docs/RUN_DESIGN.md`): resumable and appended call by call;
  image-feature caching, used only after a check on five dev cases showed
  outputs identical with and without it; identical inputs reuse the first
  output; after each tier a 1% sample is rerun uncached and compared
  exactly. Determinism audits (`runs/<model>/determinism_audit.jsonl` and
  `runs/robustness/<variant>/<model>/determinism_audit.jsonl`):

  | Run | Qwen3-VL | MedGemma 1.5 | InternVL3.5 | Mismatches |
  |---|---:|---:|---:|---:|
  | T0 | 68 | 60 | 81 | 0 |
  | T1 | 30 | 30 | 30 | 0 |
  | T2 | 90 | 90 | 90 | 0 |
  | T3 | 30 | 30 | 30 | 0 |
  | T4 | 16 | 10 | 43 | 0 |
  | `position_end` | 30 | 30 | 30 | 0 |
  | `sampled` | 45 | | | 0 |
  | Total | 309 | 250 | 304 | 0 |

  Calls rerun uncached and compared: 728 in tiers T0 to T4 and 135 in the
  variants, 863 in all, with 0 mismatches. The audit samples 1% of the
  calls computed in the run (at least 10); T4 computed few new calls for
  MedGemma and Qwen3-VL because most `no_image` calls reuse identical
  inputs. All 19 cache equivalence checks (15 for the tiers, 4 for the
  variants) found identical outputs.

## 4. Data

- **Source:** CBIS-DDSM, Version 1 (TCIA, CC BY 3.0), images from the NCI
  Imaging Data Commons (data release v25, `idc-index` 0.13.4). See
  `data/README.md` for the data card, citations and the changes made.
- **Unit:** one MLO full mammogram per patient. Labels are biopsy-confirmed
  pathology; `BENIGN_WITHOUT_CALLBACK` counts as benign.
- **Splits** (frozen at tag `splits-v1`; seed 20261023; patient-level): a
  test set of 500 cases, 125 in each stratum (calcification benign,
  calcification malignant, mass benign, mass malignant), and a dev set of
  100 cases from other patients used only for development.
  `data/manifests/test.csv` SHA-256
  `e5d632998a7cf70e347192cce9b7a5c494b5f0842551e99efa8dca4144622ea5`.
- **Images:** DICOMs verified against the IDC MD5 and SHA-256, converted to
  full-resolution 8-bit PNG masters with a recorded pixel SHA-256. ROI
  crops: one abnormality per case (highest BI-RADS assessment, ties by lowest
  abnormality id). No image, DICOM or pixel-derived file is in the
  repository.

## 5. Models

| Key | Checkpoint | Revision | Parameters | License |
|---|---|---|---|---|
| `qwen3_vl_8b` | Qwen/Qwen3-VL-8B-Instruct | `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b` | 8B | Apache-2.0 |
| `medgemma_1_5_4b` | google/medgemma-1.5-4b-it | `91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b` | 4B | Health AI Developer Foundations terms |
| `internvl3_5_8b` | OpenGVLab/InternVL3_5-8B-HF | `741a7d03020411e666c6109218ab71e08151ef86` | 8B | Apache-2.0 |

All run in bfloat16 (not quantized) with greedy decoding, seed 0, at most
128 new tokens and no system prompt. Each model receives the master image
resized by its policy in `configs/models.yaml` (SHA-256
`038826f2fa991918b19161aa335809e37971b29271f977498b3868528db3f62b`).
LLaVA-Med was planned and dropped before the plan was frozen.

## 6. Protocol

- **Prompt conditions** (`prompts/`, frozen at `prereg-v1`): `neutral`;
  `age_42` and `age_68`; `history_yes` and `history_no`; `combined` (the
  case's assigned synthetic age and history); `colleague_benign` and
  `colleague_malignant`; and `irrelevant`, a length-matched sentence with no
  clinical content. Each has three paraphrases. Age and family history are
  synthetic manipulations: every case is read with both values.
- **Image conditions:** `full` (all nine prompts); `roi` (the ROI crop);
  `no_image`; `blank_full` and `blank_roi` (all-black images of the master's
  size). The last four run `neutral`, `colleague_benign` and
  `colleague_malignant`. Blank controls use the prompt text of the image
  they stand in for (`docs/DEVIATIONS.md`, entry 1).
- **Answer format:** forced choice (primary): BI-RADS, benign or malignant,
  and a confidence from 0 to 100, with an instruction to choose even when
  uncertain. A plain format without that instruction runs on `neutral`
  (`full` and `roi`) to measure abstention.
- **Answer order:** counterbalanced within case (seed 20261025): every case
  sees both orders across paraphrases, and the order is the same across
  conditions within a paraphrase.
- **Outputs per call:** the binary answer `y`, `p_malignant` (the
  probability of "malignant" against "benign" at the first token after
  "Assessment:"), its class mass, verbal confidence and BI-RADS. Parse
  failures and abstentions are missing, never guessed.
- **Size:** 34,500 calls per model, 103,500 in all, run in tiers T0 to T4
  (`docs/RUN_DESIGN.md`). Completed calls per tier and model, from the
  committed outputs; abstentions and parse failures under the lenient
  rules, counted apart as in `reports/baseline.md`:

  | Tier | Model | Calls | Errors | Abstentions | Parse failures | Reused |
  |---|---|---:|---:|---:|---:|---:|
  | T0 | Qwen3-VL | 10,500 | 0 | 2,919 | 0 | 3,681 |
  | T0 | MedGemma 1.5 | 10,500 | 0 | 0 | 500 | 4,482 |
  | T0 | InternVL3.5 | 10,500 | 0 | 1,041 | 0 | 2,307 |
  | T1 | each model | 3,000 | 0 | 0 | 0 | 0 |
  | T2 | each model | 9,000 | 0 | 0 | 0 | 0 |
  | T3 | each model | 3,000 | 0 | 0 | 0 | 0 |
  | T4 | Qwen3-VL | 9,000 | 0 | 0 | 0 | 7,362 |
  | T4 | MedGemma 1.5 | 9,000 | 0 | 0 | 504 | 8,964 |
  | T4 | InternVL3.5 | 9,000 | 0 | 0 | 0 | 4,614 |

  All 103,500 calls completed without an error. Reused calls copy the
  output of an identical earlier input. The T0 abstentions are Qwen3-VL
  under the plain format (1,491 on full images, 1,075 on ROI crops), on
  `blank_roi` (347) and on ROI crops in the forced format (6), and
  InternVL3.5 under the plain format (745 full, 296 ROI). The parse failures
  are MedGemma 1.5 on `no_image`: 500 of 1,500 `neutral` calls and 252 of
  1,500 in each colleague condition. The Phase 7 variants added 13,500
  calls with no errors, abstentions or parse failures.

## 7. Statistics

- **Unit:** the case. Paraphrases are averaged within case and condition
  over valid answers (`docs/DEVIATIONS.md`, entry 5).
- **Contrasts:** paired bootstrap over the 500 case IDs, 10,000 resamples,
  seed 20261026, one set of resamples shared by every contrast; 95%
  percentile intervals; two-sided p-values with a resample exactly at 0
  counted on the other side. Rates over calls with Wilson intervals; AUROC
  with pROC.
- **Primary family** (Holm over 12 tests): the malignant-rate shift on full
  images, forced format, for H1 (`colleague_malignant` vs `neutral`), H2
  (`colleague_benign` vs `neutral`), H3 (`age_68` vs `age_42`) and H4
  (`history_yes` vs `history_no`), for each model.
- **Key secondary family** (Benjamini-Hochberg over 33 tests;
  `docs/DEVIATIONS.md`, entry 4): per model on full images, the
  `p_malignant` shift and the BI-RADS consistency shift for the four primary
  contrasts, `irrelevant` vs `neutral`, the answer-order effect on
  `neutral`, and plain minus forced abstention on `neutral`.
- **Descriptive** (estimates and intervals, no tests): ROI contrasts and
  their difference from full images, AUROC shifts, image reliance,
  sycophancy by image kind.
- **Sensitivity:** S1 parse failures counted as flips; S2 the strict parser;
  S3 `p_malignant` without low-mass answers.
- **Robustness (Phase 7, `docs/ROBUSTNESS.md`):** agreement across
  paraphrases and the strict parser for all primary contrasts; the context
  sentence after the task (all models) and sampled decoding (Qwen3-VL) for
  the colleague contrasts only (`docs/DEVIATIONS.md`, entry 7). Read with a
  rule fixed before the results.
- **Exploratory:** plan section 9 and `docs/EXPLORATORY.md`, reported with
  unadjusted intervals and labeled exploratory.
- **Code:** R under `analysis/` produces every number; `eval/crosscheck.py`
  recomputes the point estimates in Python and fails on any difference
  beyond rounding.

## 8. Results

Numbers in this section are copied from the generated reports named in
each subsection (section 12 gives the commands and commits). Estimates are
followed by their 95% interval. "Reference" is the level of the outcome in
the comparison's reference condition, as defined in the reports
(`docs/DEVIATIONS.md`, entry 10). Shifts in percent are differences in the
malignant rate in percentage points. Model keys: Qwen3-VL is
`qwen3_vl_8b`, MedGemma 1.5 is `medgemma_1_5_4b`, InternVL3.5 is
`internvl3_5_8b`.

### 8.1 Baseline: reading the images (Phase 4)

From `reports/baseline.md` (regenerated at the merge with the rule of
deviation 5). Full images, `neutral`, forced format; the above-chance rule
is the lower bound of the 95% interval of the AUROC of case-level
`p_malignant` above 0.5 (deviation 2).

| Model | Label | AUROC `p_malignant` | Accuracy | Malignant rate |
|---|---|---|---|---|
| Qwen3-VL | not above chance | 0.429 (0.379 to 0.479) | 49.3% (46.8 to 51.9) | 12.3% (10.7 to 14.0) |
| MedGemma 1.5 | not above chance | 0.478 (0.428 to 0.529) | 50.2% (47.7 to 52.7) | 0.3% (0.1 to 0.8) |
| InternVL3.5 | not above chance | 0.547 (0.496 to 0.598) | 51.7% (49.1 to 54.2) | 14.9% (13.2 to 16.8) |

No model is above chance. For Qwen3-VL the whole 95% interval of the AUROC
is below 0.5.

**Image reliance** (`reports/analysis.md`, descriptive; `neutral`, forced
format). Difference between the image condition and its control:

| Model | Comparison | Accuracy difference | Reference accuracy | AUROC difference | Reference AUROC |
|---|---|---|---|---|---|
| Qwen3-VL | full vs no_image | -0.7% (-3.1% to 1.8%) | 50.0% | -0.071 (-0.149 to 0.008) | 0.500 |
| Qwen3-VL | full vs blank_full | -0.7% (-4.8% to 3.4%) | 50.0% | -0.035 (-0.094 to 0.022) | 0.464 |
| Qwen3-VL | roi vs blank_roi | -0.1% (-4.3% to 4.1%) | 50.6% | 0.070 (-0.006 to 0.147) | 0.497 |
| MedGemma 1.5 | full vs no_image | 0.2% (-0.1% to 0.7%) | 50.0% | -0.022 (-0.096 to 0.052) | 0.500 |
| MedGemma 1.5 | full vs blank_full | 0.2% (-0.1% to 0.7%) | 50.0% | -0.022 (-0.081 to 0.037) | 0.500 |
| MedGemma 1.5 | roi vs blank_roi | 0.0% (0.0% to 0.0%) | 50.0% | -0.022 (-0.086 to 0.042) | 0.500 |
| InternVL3.5 | full vs no_image | 1.7% (-1.1% to 4.3%) | 50.0% | 0.047 (-0.039 to 0.132) | 0.500 |
| InternVL3.5 | full vs blank_full | 1.9% (-0.0% to 3.8%) | 49.8% | 0.050 (0.009 to 0.092) | 0.497 |
| InternVL3.5 | roi vs blank_roi | -1.0% (-5.1% to 3.1%) | 50.0% | 0.001 (-0.061 to 0.062) | 0.468 |

One of the 18 intervals excludes 0: the AUROC difference of InternVL3.5,
full vs `blank_full`.

**Abstention under the plain format** (`reports/baseline.md`, `neutral`;
rates over calls):

| Model | Image | Abstention rate | Malignant rate (answered) | Accuracy (answered) |
|---|---|---|---|---|
| Qwen3-VL | full | 99.4% (98.9 to 99.7) | 0.0% (0.0 to 29.9) | 22.2% (6.3 to 54.7) |
| Qwen3-VL | roi | 71.7% (69.3 to 73.9) | 0.0% (0.0 to 0.9) | 58.8% (54.1 to 63.4) |
| MedGemma 1.5 | full | 0.0% (0.0 to 0.3) | 0.2% (0.1 to 0.6) | 50.1% (47.5 to 52.6) |
| MedGemma 1.5 | roi | 0.0% (0.0 to 0.3) | 0.0% (0.0 to 0.3) | 50.0% (47.5 to 52.5) |
| InternVL3.5 | full | 49.7% (47.1 to 52.2) | 3.0% (2.0 to 4.5) | 50.9% (47.3 to 54.4) |
| InternVL3.5 | roi | 19.7% (17.8 to 21.8) | 15.4% (13.4 to 17.5) | 48.6% (45.8 to 51.4) |

### 8.2 Primary outcome

From `reports/analysis.md`. Malignant rate shift on full images, forced
format; paired case bootstrap, 500 of 500 cases in every test; Holm over
the 12 tests at familywise alpha 0.05. Figure:
`reports/figures/primary_shift.png`.

| Hypothesis | Model | Contrast | Estimate | Reference malignant rate | p | Holm p |
|---|---|---|---|---|---|---|
| H1 | Qwen3-VL | colleague_malignant vs neutral | 39.9% (37.8% to 42.1%) | 12.3% | <0.001 | p < 0.0025 |
| H2 | Qwen3-VL | colleague_benign vs neutral | -12.3% (-13.9% to -10.7%) | 12.3% | <0.001 | p < 0.0025 |
| H3 | Qwen3-VL | age_68 vs age_42 | 10.7% (8.9% to 12.6%) | 3.7% | <0.001 | p < 0.0025 |
| H4 | Qwen3-VL | history_yes vs history_no | 27.9% (26.2% to 29.6%) | 2.5% | <0.001 | p < 0.0025 |
| H1 | MedGemma 1.5 | colleague_malignant vs neutral | 66.1% (64.1% to 68.1%) | 0.3% | <0.001 | p < 0.0025 |
| H2 | MedGemma 1.5 | colleague_benign vs neutral | -0.3% (-0.8% to 0.0%) | 0.3% | 0.100 | 0.299 |
| H3 | MedGemma 1.5 | age_68 vs age_42 | 0.1% (0.0% to 0.3%) | 0.1% | 0.272 | 0.544 |
| H4 | MedGemma 1.5 | history_yes vs history_no | 0.0% (0.0% to 0.0%) | 0.0% | 1.000 | 1.000 |
| H1 | InternVL3.5 | colleague_malignant vs neutral | 85.1% (83.3% to 86.9%) | 14.9% | <0.001 | p < 0.0025 |
| H2 | InternVL3.5 | colleague_benign vs neutral | -14.9% (-16.7% to -13.1%) | 14.9% | <0.001 | p < 0.0025 |
| H3 | InternVL3.5 | age_68 vs age_42 | 30.1% (28.2% to 31.9%) | 9.5% | <0.001 | p < 0.0025 |
| H4 | InternVL3.5 | history_yes vs history_no | 25.1% (23.8% to 26.5%) | 0.5% | <0.001 | p < 0.0025 |

Nine of the 12 tests have a Holm-adjusted p-value below 0.05: H1 to H4 for
Qwen3-VL and InternVL3.5, and H1 for MedGemma 1.5. MedGemma 1.5's H2, H3
and H4 do not. "p < 0.0025" marks the resolution limit: with 10,000
resamples and the conservative tie rule, the smallest bootstrap p-value is
2/10,001, so the smallest Holm-adjusted p-value over 12 tests is 0.0024
(`docs/DEVIATIONS.md`, entry 10).

### 8.3 Key secondary outcomes

From `reports/analysis.md`. Full images; Benjamini-Hochberg over the 33
tests at q = 0.05 (`docs/DEVIATIONS.md`, entry 4). 29 of the 33 tests have
an adjusted p-value below 0.05. The four that do not are all MedGemma 1.5:
the BI-RADS consistency shift for `colleague_malignant` vs `neutral`, the
`irrelevant` control, the answer order and the abstention difference.

**`p_malignant` shift** (all 12 with p < 0.001 and adjusted p < 0.001;
figure `reports/figures/p_malignant_shift.png`):

| Model | Contrast | Estimate | Reference mean `p_malignant` |
|---|---|---|---|
| Qwen3-VL | colleague_malignant vs neutral | 0.186 (0.169 to 0.203) | 0.311 |
| Qwen3-VL | colleague_benign vs neutral | -0.311 (-0.319 to -0.303) | 0.311 |
| Qwen3-VL | age_68 vs age_42 | 0.125 (0.117 to 0.132) | 0.193 |
| Qwen3-VL | history_yes vs history_no | 0.264 (0.253 to 0.276) | 0.086 |
| MedGemma 1.5 | colleague_malignant vs neutral | 0.649 (0.636 to 0.663) | 0.004 |
| MedGemma 1.5 | colleague_benign vs neutral | -0.004 (-0.007 to -0.002) | 0.004 |
| MedGemma 1.5 | age_68 vs age_42 | 0.001 (0.000 to 0.002) | 0.003 |
| MedGemma 1.5 | history_yes vs history_no | 0.001 (0.001 to 0.002) | 0.001 |
| InternVL3.5 | colleague_malignant vs neutral | 0.825 (0.813 to 0.837) | 0.171 |
| InternVL3.5 | colleague_benign vs neutral | -0.170 (-0.183 to -0.158) | 0.171 |
| InternVL3.5 | age_68 vs age_42 | 0.168 (0.158 to 0.178) | 0.150 |
| InternVL3.5 | history_yes vs history_no | 0.181 (0.175 to 0.187) | 0.039 |

**BI-RADS consistency shift:**

| Model | Contrast | Estimate | Reference consistency rate | p | Adjusted p |
|---|---|---|---|---|---|
| Qwen3-VL | colleague_malignant vs neutral | 78.3% (75.9% to 80.5%) | 4.2% | <0.001 | <0.001 |
| Qwen3-VL | colleague_benign vs neutral | 95.8% (94.5% to 97.0%) | 4.2% | <0.001 | <0.001 |
| Qwen3-VL | age_68 vs age_42 | -11.2% (-12.9% to -9.5%) | 24.0% | <0.001 | <0.001 |
| Qwen3-VL | history_yes vs history_no | -50.2% (-53.1% to -47.3%) | 70.8% | <0.001 | <0.001 |
| MedGemma 1.5 | colleague_malignant vs neutral | -2.1% (-7.3% to 3.3%) | 68.6% | 0.443 | 0.457 |
| MedGemma 1.5 | colleague_benign vs neutral | 31.4% (27.6% to 35.3%) | 68.6% | <0.001 | <0.001 |
| MedGemma 1.5 | age_68 vs age_42 | -10.5% (-12.7% to -8.4%) | 75.3% | <0.001 | <0.001 |
| MedGemma 1.5 | history_yes vs history_no | -5.5% (-6.9% to -4.1%) | 82.7% | <0.001 | <0.001 |
| InternVL3.5 | colleague_malignant vs neutral | 96.0% (94.7% to 97.2%) | 2.3% | <0.001 | <0.001 |
| InternVL3.5 | colleague_benign vs neutral | 54.8% (53.2% to 56.4%) | 2.3% | <0.001 | <0.001 |
| InternVL3.5 | age_68 vs age_42 | 3.5% (2.3% to 4.7%) | 1.9% | <0.001 | <0.001 |
| InternVL3.5 | history_yes vs history_no | 0.7% (0.3% to 1.1%) | 0.4% | <0.001 | <0.001 |

**Control, answer order and abstention:**

| Outcome | Model | Estimate | Reference | p | Adjusted p |
|---|---|---|---|---|---|
| Malignant rate shift, irrelevant vs neutral | Qwen3-VL | -6.7% (-8.4% to -5.1%) | 12.3% | <0.001 | <0.001 |
| Malignant rate shift, irrelevant vs neutral | MedGemma 1.5 | -0.3% (-0.7% to 0.0%) | 0.3% | 0.100 | 0.110 |
| Malignant rate shift, irrelevant vs neutral | InternVL3.5 | -14.1% (-15.8% to -12.5%) | 14.9% | <0.001 | <0.001 |
| Answer order, malignant first minus benign first (`neutral`) | Qwen3-VL | 23.5% (20.3% to 26.9%) | 0.5% | <0.001 | <0.001 |
| Answer order, malignant first minus benign first (`neutral`) | MedGemma 1.5 | -0.4% (-1.1% to 0.0%) | 0.5% | 0.195 | 0.208 |
| Answer order, malignant first minus benign first (`neutral`) | InternVL3.5 | -23.0% (-25.8% to -20.2%) | 26.3% | <0.001 | <0.001 |
| Abstention rate, plain minus forced (`neutral`) | Qwen3-VL | 99.4% (98.9% to 99.8%) | 0.0% | <0.001 | <0.001 |
| Abstention rate, plain minus forced (`neutral`) | MedGemma 1.5 | 0.0% (0.0% to 0.0%) | 0.0% | 1.000 | 1.000 |
| Abstention rate, plain minus forced (`neutral`) | InternVL3.5 | 49.7% (48.1% to 51.2%) | 0.0% | <0.001 | <0.001 |

The reference is the `neutral` malignant rate for the control, the
benign-first malignant rate for the answer order, and the forced-format
abstention rate for abstention.

### 8.4 Descriptive outcomes

From `reports/analysis.md`; estimates and 95% intervals, no tests.

**Sycophancy** (figure `reports/figures/sycophancy.png`): the rate of
answering the colleague's opinion when the colleague is wrong (the opinion
differs from the biopsy label) minus the rate when the colleague is right,
by image kind.

| Model | Image | colleague_benign | Rate when right | colleague_malignant | Rate when right |
|---|---|---|---|---|---|
| Qwen3-VL | full | 0.0% (0.0% to 0.0%) | 100.0% | 0.7% (-2.9% to 4.2%) | 51.9% |
| Qwen3-VL | roi | 0.0% (0.0% to 0.0%) | 100.0% | -2.0% (-7.0% to 2.9%) | 74.7% |
| Qwen3-VL | no_image | 0.0% (0.0% to 0.0%) | 100.0% | 0.0% (-3.0% to 2.9%) | 83.2% |
| Qwen3-VL | blank_full | 0.0% (0.0% to 0.0%) | 100.0% | 0.0% (0.0% to 0.0%) | 100.0% |
| Qwen3-VL | blank_roi | 0.0% (0.0% to 0.0%) | 100.0% | 0.0% (0.0% to 0.0%) | 100.0% |
| MedGemma 1.5 | full | 0.0% (0.0% to 0.0%) | 100.0% | 2.5% (-1.3% to 6.4%) | 65.2% |
| MedGemma 1.5 | roi | 0.0% (0.0% to 0.0%) | 100.0% | -3.9% (-8.3% to 0.6%) | 31.6% |
| MedGemma 1.5 | no_image | 0.0% (0.0% to 0.0%) | 100.0% | 0.0% (0.0% to 0.0%) | 0.0% |
| MedGemma 1.5 | blank_full | 0.0% (0.0% to 0.0%) | 100.0% | 0.0% (-3.0% to 2.9%) | 49.9% |
| MedGemma 1.5 | blank_roi | 0.0% (0.0% to 0.0%) | 100.0% | 0.0% (0.0% to 0.0%) | 33.3% |
| InternVL3.5 | all five | 0.0% (0.0% to 0.0%) | 100.0% | 0.0% (0.0% to 0.0%) | 100.0% |

No interval excludes 0.

**ROI contrasts:** malignant rate shift on ROI crops, and its difference
from the same shift on full images (ROI minus full; reference: the
`neutral` malignant rate on ROI / on full images).

| Model | Contrast | Shift on ROI | Reference | ROI minus full | Reference |
|---|---|---|---|---|---|
| Qwen3-VL | colleague_benign vs neutral | -0.9% (-1.5% to -0.5%) | 0.9% | 11.3% (9.7% to 13.0%) | 0.9% / 12.3% |
| Qwen3-VL | colleague_malignant vs neutral | 72.7% (70.3% to 75.1%) | 0.9% | 32.8% (29.7% to 35.9%) | 0.9% / 12.3% |
| MedGemma 1.5 | colleague_benign vs neutral | 0.0% (0.0% to 0.0%) | 0.0% | 0.3% (0.0% to 0.8%) | 0.0% / 0.3% |
| MedGemma 1.5 | colleague_malignant vs neutral | 29.7% (27.5% to 31.9%) | 0.0% | -36.5% (-39.3% to -33.6%) | 0.0% / 0.3% |
| InternVL3.5 | colleague_benign vs neutral | -62.7% (-65.2% to -60.3%) | 62.7% | -47.9% (-50.7% to -44.9%) | 62.7% / 14.9% |
| InternVL3.5 | colleague_malignant vs neutral | 37.3% (34.8% to 39.7%) | 62.7% | -47.9% (-50.7% to -44.9%) | 62.7% / 14.9% |

**AUROC by condition** (figure `reports/figures/auroc.png`): shift in the
AUROC of `p_malignant` from `neutral`, full images.

| Condition vs neutral | Qwen3-VL | MedGemma 1.5 | InternVL3.5 |
|---|---|---|---|
| Reference AUROC (`neutral`) | 0.429 | 0.478 | 0.547 |
| age_42 | 0.054 (0.004 to 0.104) | -0.004 (-0.014 to 0.006) | 0.004 (-0.012 to 0.020) |
| age_68 | 0.061 (0.011 to 0.111) | 0.002 (-0.005 to 0.009) | -0.002 (-0.017 to 0.013) |
| history_yes | 0.061 (0.021 to 0.102) | -0.005 (-0.013 to 0.004) | 0.009 (-0.006 to 0.025) |
| history_no | 0.087 (0.031 to 0.144) | -0.006 (-0.016 to 0.004) | -0.007 (-0.026 to 0.012) |
| combined | 0.063 (0.003 to 0.125) | -0.007 (-0.025 to 0.011) | -0.016 (-0.067 to 0.037) |
| colleague_benign | 0.036 (-0.019 to 0.092) | 0.001 (-0.039 to 0.042) | -0.025 (-0.069 to 0.020) |
| colleague_malignant | 0.067 (0.005 to 0.131) | -0.002 (-0.032 to 0.027) | -0.021 (-0.062 to 0.020) |
| irrelevant | 0.040 (0.007 to 0.074) | -0.005 (-0.012 to 0.002) | -0.012 (-0.037 to 0.012) |

The AUROC shifts on ROI crops and control images, and the shifts in the
AUROC of verbal confidence, are in `reports/analysis.md`.

**Flip rates:** the share of (case, paraphrase) pairs whose valid answer
differs from the `neutral` answer, full images, forced format, 1,500 pairs
per cell (neutral malignant rate: Qwen3-VL 12.3%, MedGemma 1.5 0.3%,
InternVL3.5 14.9%).

| Condition | Qwen3-VL | MedGemma 1.5 | InternVL3.5 |
|---|---|---|---|
| age_42 | 9.1% (7.7% to 10.6%) | 0.3% (0.1% to 0.7%) | 7.7% (6.4% to 9.1%) |
| age_68 | 10.2% (8.8% to 11.8%) | 0.1% (0.0% to 0.5%) | 24.7% (22.6% to 26.9%) |
| history_yes | 20.7% (18.8% to 22.9%) | 0.3% (0.1% to 0.8%) | 13.9% (12.2% to 15.7%) |
| history_no | 11.1% (9.6% to 12.8%) | 0.3% (0.1% to 0.8%) | 14.3% (12.7% to 16.2%) |
| combined | 17.0% (15.2% to 19.0%) | 0.3% (0.1% to 0.8%) | 15.0% (13.3% to 16.9%) |
| colleague_benign | 12.3% (10.7% to 14.0%) | 0.3% (0.1% to 0.8%) | 14.9% (13.2% to 16.8%) |
| colleague_malignant | 41.7% (39.2% to 44.2%) | 66.1% (63.7% to 68.5%) | 85.1% (83.2% to 86.8%) |
| irrelevant | 11.8% (10.3% to 13.5%) | 0.3% (0.1% to 0.7%) | 14.1% (12.5% to 16.0%) |

Flip rates on ROI crops and control images are in `reports/analysis.md`.

### 8.5 Sensitivity analyses

**S1, parse failures counted as flips** (`reports/analysis.md`, flip
table). No call on full images in the forced format failed to parse, so S1
equals the flip rate in every cell of the primary contrasts. S1 differs
from the flip rate only in three groups of cells: Qwen3-VL on `blank_roi`
(`colleague_benign` 53.5% against 39.5%, `colleague_malignant` 69.6%
against 60.5%) and `roi` (1.3% against 0.9%, 72.7% against 72.6%), and
MedGemma 1.5 on `no_image` (33.3% against 0.0% for both colleague
conditions).

**S2, strict parser** (`reports/robustness.md`, R3): the 12 primary
contrasts from the answers valid under the frozen strict rules, Holm within
these 12.

| Hypothesis | Model | Estimate | Reference malignant rate | p | Holm p | Cases | Reading |
|---|---|---|---|---|---|---|---|
| H1 | Qwen3-VL | 39.9% (37.8% to 42.1%) | 12.3% | <0.001 | p < 0.0025 | 500 | robust |
| H2 | Qwen3-VL | -12.3% (-13.9% to -10.7%) | 12.3% | <0.001 | p < 0.0025 | 500 | robust |
| H3 | Qwen3-VL | 10.7% (8.9% to 12.6%) | 3.7% | <0.001 | p < 0.0025 | 500 | robust |
| H4 | Qwen3-VL | 27.9% (26.2% to 29.6%) | 2.5% | <0.001 | p < 0.0025 | 500 | robust |
| H1 to H4 | MedGemma 1.5 | n/a | n/a | n/a | n/a | 0 | no data |
| H1 | InternVL3.5 | 96.4% (94.8% to 97.9%) | 3.6% | <0.001 | p < 0.0025 | 435 | robust |
| H2 | InternVL3.5 | -3.6% (-5.2% to -2.1%) | 3.6% | <0.001 | p < 0.0025 | 435 | robust |
| H3 | InternVL3.5 | 7.1% (4.2% to 10.3%) | 6.0% | <0.001 | p < 0.0025 | 232 | robust |
| H4 | InternVL3.5 | -0.2% (-0.6% to 0.0%) | 0.4% | 0.752 | 0.752 | 251 | sensitive |

Every Qwen3-VL answer valid under the lenient rules is also valid under the
strict rules. No MedGemma 1.5 answer in these cells is valid under the
strict rules, so S2 has no data for it (`docs/ROBUSTNESS.md`). For
InternVL3.5 the strict rules keep 444 of 1,500 `neutral` answers on full
images; the counts per cell are in `reports/robustness.md`.

**S3, `p_malignant` without low-mass answers** (`reports/analysis.md`): the
`p_malignant` shift with answers of low class mass excluded.

| Model | Contrast | S3 estimate | Reference | Key secondary estimate |
|---|---|---|---|---|
| Qwen3-VL | colleague_malignant vs neutral | 0.186 (0.169 to 0.203) | 0.311 | 0.186 (0.169 to 0.203) |
| Qwen3-VL | colleague_benign vs neutral | -0.311 (-0.319 to -0.303) | 0.311 | -0.311 (-0.319 to -0.303) |
| Qwen3-VL | age_68 vs age_42 | 0.125 (0.117 to 0.132) | 0.193 | 0.125 (0.117 to 0.132) |
| Qwen3-VL | history_yes vs history_no | 0.264 (0.253 to 0.276) | 0.086 | 0.264 (0.253 to 0.276) |
| MedGemma 1.5 | colleague_malignant vs neutral | 0.650 (0.636 to 0.664) | 0.004 | 0.649 (0.636 to 0.663) |
| MedGemma 1.5 | colleague_benign vs neutral | -0.004 (-0.007 to -0.001) | 0.004 | -0.004 (-0.007 to -0.002) |
| MedGemma 1.5 | age_68 vs age_42 | 0.001 (-0.000 to 0.002) | 0.003 | 0.001 (0.000 to 0.002) |
| MedGemma 1.5 | history_yes vs history_no | 0.001 (0.000 to 0.001) | 0.001 | 0.001 (0.001 to 0.002) |
| InternVL3.5 | colleague_malignant vs neutral | 0.825 (0.813 to 0.837) | 0.171 | 0.825 (0.813 to 0.837) |
| InternVL3.5 | colleague_benign vs neutral | -0.170 (-0.183 to -0.158) | 0.171 | -0.170 (-0.183 to -0.158) |
| InternVL3.5 | age_68 vs age_42 | 0.168 (0.158 to 0.178) | 0.150 | 0.168 (0.158 to 0.178) |
| InternVL3.5 | history_yes vs history_no | 0.181 (0.175 to 0.187) | 0.039 | 0.181 (0.175 to 0.187) |

The Qwen3-VL and InternVL3.5 rows are identical to the key secondary
estimates; the MedGemma 1.5 rows differ by at most 0.001.

### 8.6 Robustness (Phase 7)

From `reports/robustness.md`. Reading rule, fixed before the results
(`docs/ROBUSTNESS.md`): robust means the same sign as a significant primary
result and a 95% interval excluding 0; unchanged means an interval
including 0 for a primary result that is not significant; sensitive means
anything else. The variant runs completed with 13,500 calls, no errors, no
abstentions and no parse failures.

**R1, agreement across paraphrases.** Each primary contrast from one
paraphrase at a time (paraphrases 1, 2 and 3):

| Hypothesis | Model | Paraphrase 1 | Paraphrase 2 | Paraphrase 3 | Readings |
|---|---|---|---|---|---|
| H1 | Qwen3-VL | 44.2% (39.6% to 49.0%) | 66.2% (62.2% to 70.4%) | 9.4% (6.6% to 12.2%) | robust, robust, robust |
| H2 | Qwen3-VL | -4.6% (-6.4% to -2.8%) | -27.6% (-31.6% to -23.6%) | -4.6% (-6.6% to -2.8%) | robust, robust, robust |
| H3 | Qwen3-VL | 14.8% (11.8% to 18.0%) | 15.2% (11.8% to 18.6%) | 2.2% (0.8% to 3.6%) | robust, robust, robust |
| H4 | Qwen3-VL | 35.8% (31.6% to 40.0%) | 40.8% (36.4% to 45.2%) | 7.0% (4.8% to 9.2%) | robust, robust, robust |
| H1 | MedGemma 1.5 | 29.6% (25.6% to 33.6%) | 69.6% (65.4% to 73.6%) | 99.2% (98.4% to 99.8%) | robust, robust, robust |
| H2 | MedGemma 1.5 | -0.2% (-0.6% to 0.0%) | -0.2% (-0.6% to 0.0%) | -0.6% (-1.4% to 0.0%) | unchanged, unchanged, unchanged |
| H3 | MedGemma 1.5 | 0.2% (0.0% to 0.6%) | 0.2% (0.0% to 0.6%) | 0.0% (0.0% to 0.0%) | unchanged, unchanged, unchanged |
| H4 | MedGemma 1.5 | 0.0% (0.0% to 0.0%) | 0.0% (0.0% to 0.0%) | 0.0% (0.0% to 0.0%) | unchanged, unchanged, unchanged |
| H1 | InternVL3.5 | 68.8% (64.6% to 72.8%) | 89.8% (87.2% to 92.4%) | 96.8% (95.2% to 98.2%) | robust, robust, robust |
| H2 | InternVL3.5 | -31.2% (-35.4% to -27.2%) | -10.2% (-12.8% to -7.6%) | -3.2% (-4.8% to -1.8%) | robust, robust, robust |
| H3 | InternVL3.5 | 37.2% (33.0% to 41.6%) | 30.4% (26.4% to 34.6%) | 22.6% (19.0% to 26.4%) | robust, robust, robust |
| H4 | InternVL3.5 | 50.6% (46.4% to 55.0%) | 24.8% (21.0% to 28.8%) | 0.0% (0.0% to 0.0%) | robust, robust, sensitive |

35 of the 36 single-paraphrase estimates read robust or unchanged; the
exception is InternVL3.5 H4 from paraphrase 3, 0.0% (0.0% to 0.0%). The
share of cases with three agreeing answers and Fleiss' kappa for every cell
are in `reports/robustness.md`; on full images, `neutral`, forced format,
the share is 66.6% (62.4% to 70.6%) for Qwen3-VL, 99.4% (98.3% to 99.8%)
for MedGemma 1.5 and 62.8% (58.5% to 66.9%) for InternVL3.5.

**R2, context sentence after the task** (`position_end`, all three
models, colleague contrasts):

| Hypothesis | Model | Shift, context at end | Reading | End minus middle |
|---|---|---|---|---|
| H1 | Qwen3-VL | 27.6% (25.8% to 29.4%) | robust | -12.3% (-14.0% to -10.7%) |
| H2 | Qwen3-VL | -12.3% (-13.9% to -10.7%) | robust | 0.0% (0.0% to 0.0%) |
| H1 | MedGemma 1.5 | 68.1% (65.9% to 70.3%) | robust | 1.9% (0.1% to 3.7%) |
| H2 | MedGemma 1.5 | -0.3% (-0.8% to 0.0%) | unchanged | 0.0% (0.0% to 0.0%) |
| H1 | InternVL3.5 | 85.1% (83.3% to 86.9%) | robust | 0.0% (0.0% to 0.0%) |
| H2 | InternVL3.5 | -14.9% (-16.7% to -13.1%) | robust | 0.0% (0.0% to 0.0%) |

The reference malignant rate is the study `neutral` rate (Qwen3-VL 12.3%,
MedGemma 1.5 0.3%, InternVL3.5 14.9%), since `neutral` has no context
sentence.

**R3, strict parser:** see S2 in section 8.5.

**R4, sampled decoding** (Qwen3-VL; temperature 0.7, top_p 1.0, seed 1):

| Hypothesis | Shift, sampled | Reference malignant rate (sampled `neutral`) | Reading | Sampled minus greedy |
|---|---|---|---|---|
| H1 | 19.3% (16.8% to 21.9%) | 44.3% | robust | -20.6% (-23.4% to -17.9%) |
| H2 | -44.3% (-46.5% to -42.1%) | 44.3% | robust | -32.0% (-34.3% to -29.7%) |

The `neutral` malignant rate is 44.3% under sampling and 12.3% under greedy
decoding. Sampled answers equal to the greedy answer, over 1,500 (case,
paraphrase) pairs per condition: `neutral` 68.0% (65.6% to 70.3%),
`colleague_benign` 100.0% (99.7% to 100.0%), `colleague_malignant` 88.6%
(86.9% to 90.1%).

### 8.7 Exploratory analyses

**EXPLORATORY: not tests of the plan's hypotheses.** Unadjusted 95%
intervals, no p-values.

**Plan section 9** (`reports/analysis.md`, "Exploratory"). The combined
condition and the additivity of age and history, full images:

| Model | combined vs neutral | Reference | combined minus (assigned age + assigned history), each vs neutral |
|---|---|---|---|
| Qwen3-VL | 3.5% (1.3% to 5.8%) | 12.3% | 2.9% (0.9% to 4.9%) |
| MedGemma 1.5 | -0.3% (-0.8% to 0.0%) | 0.3% | 0.1% (0.0% to 0.3%) |
| InternVL3.5 | 2.2% (0.2% to 4.2%) | 14.9% | -5.6% (-7.7% to -3.5%) |

Colleague contrasts on the control images (malignant rate shift vs
`neutral` on the same control image; reference: that control's `neutral`
malignant rate):

| Model | Image | colleague_benign | colleague_malignant | Reference |
|---|---|---|---|---|
| Qwen3-VL | no_image | -33.3% (-33.3% to -33.3%) | 49.9% (48.4% to 51.3%) | 33.3% |
| Qwen3-VL | blank_full | -49.9% (-51.3% to -48.4%) | 50.1% (48.7% to 51.6%) | 49.9% |
| Qwen3-VL | blank_roi | -34.0% (-36.6% to -31.3%) | 66.0% (63.4% to 68.7%) | 34.0% |
| MedGemma 1.5 | no_image | 0.0% (0.0% to 0.0%) | 0.0% (0.0% to 0.0%) | 0.0% |
| MedGemma 1.5 | blank_full | 0.0% (0.0% to 0.0%) | 49.9% (48.4% to 51.3%) | 0.0% |
| MedGemma 1.5 | blank_roi | 0.0% (0.0% to 0.0%) | 33.3% (33.3% to 33.3%) | 0.0% |
| InternVL3.5 | no_image | -16.5% (-18.0% to -15.1%) | 83.5% (82.0% to 84.9%) | 16.5% |
| InternVL3.5 | blank_full | -16.6% (-18.1% to -15.1%) | 83.4% (81.9% to 84.9%) | 16.6% |
| InternVL3.5 | blank_roi | -100.0% (-100.0% to -100.0%) | 0.0% (0.0% to 0.0%) | 100.0% |

The primary contrasts by abnormality type, label and BI-RADS assessment,
and the answer-order effect in every cell (malignant rate and mean
`p_malignant`), are in the same section of `reports/analysis.md`.

**Exploratory 2: conditions against `irrelevant`** (`docs/EXPLORATORY.md`,
entry 2; added after the results were known, `docs/DEVIATIONS.md`, entry
9). Malignant rate shift on full images; reference: the `irrelevant`
malignant rate (Qwen3-VL 5.5%, MedGemma 1.5 0.1%, InternVL3.5 0.7%).

| Condition vs irrelevant | Qwen3-VL | MedGemma 1.5 | InternVL3.5 |
|---|---|---|---|
| colleague_malignant | 46.7% (44.7% to 48.7%) | 66.4% (64.5% to 68.3%) | 99.3% (98.6% to 99.8%) |
| colleague_benign | -5.5% (-6.7% to -4.4%) | -0.1% (-0.2% to 0.0%) | -0.7% (-1.4% to -0.2%) |
| age_68 | 8.9% (6.9% to 11.0%) | 0.1% (0.0% to 0.4%) | 38.8% (36.6% to 41.0%) |
| age_42 | -1.8% (-3.1% to -0.5%) | 0.0% (-0.2% to 0.2%) | 8.7% (7.3% to 10.3%) |
| history_yes | 24.8% (23.1% to 26.5%) | -0.1% (-0.2% to 0.0%) | 24.9% (23.6% to 26.3%) |
| history_no | -3.1% (-4.3% to -1.8%) | -0.1% (-0.2% to 0.0%) | -0.2% (-0.5% to 0.1%) |

**Exploratory 1: surface features and Qwen3-VL's answers**
(`reports/exploratory/surface_features.md`; tier T0, Qwen3-VL, full
images, `neutral`, forced format; 2,000 resamples). The AUROC of case-level
`p_malignant` is 0.429 (0.378 to 0.477): 0.410 (0.341 to 0.478) for masses
and 0.446 (0.377 to 0.516) for calcifications. In a least-squares model of
case-level `p_malignant` on 497 cases, the label coefficient is -0.021
(-0.036 to -0.004) alone and -0.016 (-0.031 to -0.000) with the
standardized image and case features. The Spearman correlation with
`p_malignant` is largest in absolute value for breast density, 0.276 (0.191 to 0.357); the
feature AUROCs for the label range from 0.425 (width) to 0.582 (mean
intensity). The full table is in the report.

## 9. Deviations from the frozen plan

From `docs/DEVIATIONS.md`, which gives the reasons and what was known when:

1. **Blank ROI prompt text** (2026-10-25): `blank_roi` uses the ROI-crop
   text and `blank_full` the full-image text. No result known.
2. **Above chance** (2026-10-25): defined as the lower bound of the 95%
   bootstrap interval of the AUROC of `p_malignant` above 0.5 on full
   images, `neutral`, forced format. No result known.
3. **Abstentions and parse failures counted apart** in the baseline report
   (2026-10-27). Made after T0 was seen; changes no label.
4. **Key secondary family and descriptive outcomes** (2026-10-27): the
   secondary analyses split into 33 Benjamini-Hochberg tests and descriptive
   estimates. Decided before any T1 to T4 output was read; the answer-order
   and abstention tests use T0, whose values were already reported.
5. **Case-level `p_malignant` over valid answers only** in the baseline
   (2026-10-27): matches plan section 5; changes no label.
6. **Second decoding setting** (2026-10-27): Qwen3-VL, sampling at
   temperature 0.7, top_p 1.0, seed 1; chosen from T0 only.
7. **Scope of the position and decoding checks** (2026-10-27): the
   colleague contrasts only, decided blind to T1 to T4.

8. **Unattended run procedure from tier T2 on** (2026-10-29): a stall
   watchdog, retries, chaining of tiers, a pinned commit that ignores
   commits of outputs only, a determinism audit per tier and commit, and
   unbuffered logs. Decides when calls run, not what a call computes; the
   T1 outputs existed but no T1 answer was read.
9. **Exploratory comparison against the irrelevant sentence** (2026-11-01):
   the H1 to H4 conditions against `irrelevant` (section 8.7). Added after
   the results were known; exploratory, no p-values.
10. **Reference levels and the p-value floor in the tables** (2026-11-01):
    a reference column with the level of each table's own outcome, and
    Holm-adjusted p-values at the bootstrap's resolution limit printed as
    "p < 0.0025". Made after the results were known; no estimate, interval,
    p-value or test decision changed.

The notes at the end of `docs/DEVIATIONS.md` record that entry 8's remark
about entries 4 to 7 was resolved by the merge in commit `ec9f10a`, and that
the robustness report was regenerated after the Phase 7 runs, when the
primary and secondary results were known, with no change to the analysis
code.

## 10. Discussion

**Readings that follow the text, not the image.** On the neutral prompt, all three models performed at or below chance on full images (AUROC 0.429 to 0.547), and their accuracy with the real image was within 2 points of their accuracy with no image or a blank image. On ROI crops, only Qwen3-VL's AUROC interval lay above 0.5 (0.567, 0.516 to 0.618). Their answers were nonetheless highly responsive to the prompt: the same image received a different reading depending on a single added sentence. Taken together, these results suggest that in this setting the models' answers are determined largely by the text and by fixed response preferences, and very little by the image. The study cannot say what a model would do if it could read the images; it shows that the absence of image skill does not make a model unresponsive to context.

**Authority versus patient details.** The colleague's opinion produced the largest shifts for every model, including MedGemma, which answered benign on 99.7% of full-image calls under the neutral prompt. The models followed the colleague about as often when the colleague was wrong as when the colleague was right: under the malignant opinion, Qwen3-VL agreed on 52.5% of calls when the colleague was wrong and 51.9% when right, MedGemma on 67.7% and 65.2%, and InternVL3.5 on 100% in both cases. MedGemma did not respond to age or family history (shifts of 0.1 and 0.0 points), while Qwen3-VL and InternVL3.5 did (10.7 to 30.1 points). For the two general models, demographic cues and authority cues both moved the answer; for the medical model, only an explicit opinion did. Agreement between the BI-RADS category and the stated assessment rose sharply under the colleague's malignant opinion for Qwen3-VL (+78.3 points) and InternVL3.5 (+96.0 points), but did not change significantly for MedGemma (-2.1 points).

**What the controls show.** The colleague's benign opinion (H2) produced small or null shifts, but this reflects how few malignant answers there were to remove: Qwen3-VL's neutral malignant rate was 12.3% and fell by 12.3 points, InternVL3.5's was 14.9% and fell by 14.9 points, and MedGemma's was 0.3%. H2 therefore says little about whether the models resist a benign suggestion. The length-matched irrelevant sentence was not neutral either: it lowered the malignant rate by 6.7 points for Qwen3-VL and 14.1 points for InternVL3.5. Part of any shift measured against the neutral prompt may therefore come from adding text of any kind. In the exploratory comparison against the irrelevant sentence, the colleague's malignant opinion moved the answers even further (46.7, 66.4 and 99.3 points), while the age and family-history cues gave estimates of similar size to the primary contrasts, carried mainly by the older age and the positive history.

**Formatting matters as much as clinical content.** The order of the answer options moved Qwen3-VL by 23.5 points and InternVL3.5 by 23.0 points in opposite directions, a shift comparable to the age and family-history effects. In the plain answer format, Qwen3-VL abstained on 99.4% of full-image calls (71.7% on ROI crops) and InternVL3.5 on 49.7% (19.7%), so whether these models give an answer at all depends on how the question is posed. The wording of the cue itself mattered as much: across the three paraphrases, the colleague effect ranged from 9.4 to 66.2 points for Qwen3-VL and from 29.6 to 99.2 points for MedGemma, and InternVL3.5's family-history effect ranged from 50.6 to 0.0 points. Clinical content and incidental wording had effects of similar size.

**Decoding choices change the baseline.** Under sampled decoding, Qwen3-VL's neutral malignant rate was 44.3%, against 12.3% under greedy decoding. Greedy answers therefore understate how often this model's output distribution favors a malignant reading. The colleague effect remained clearly positive under sampling (+19.3 points), so the main result does not depend on greedy decoding.

**Implications.** Accuracy alone would describe these models as uninformative. Measured against paired prompts, they are also highly suggestible: a stated opinion, a patient detail, or the order of two words can decide the answer, and the models follow a colleague's opinion whether or not it is correct. Evaluations of vision-language models for clinical use should report sensitivity to prompt content and format alongside accuracy. These findings come from three small open models on one public dataset of digitized film mammograms; larger or newer models, other imaging data, and other prompt designs may behave differently, and this study makes no claim about clinical performance.

## 11. Threats to validity

The full list, with evidence and mitigations, is in `docs/THREATS.md`: no
model reads the images above chance; film mammograms from the 1990s
digitized on several scanners; one public dataset; small models (4B and 8B,
not quantized); synthetic age and family history; label and BI-RADS noise;
image size and brightness associated with the label (a dataset confound);
answer-order sensitivity; and the strict parser's case sensitivity.

- **Paraphrase dependence.** All single-paraphrase estimates read robust or unchanged except one, but their size varies widely: the colleague effect ranges from 9.4 to 66.2 points for Qwen3-VL and from 29.6 to 99.2 points for MedGemma across the three paraphrases. The exception is InternVL3.5's family-history effect (H4), which is 50.6, 24.8 and 0.0 points. Pooled estimates should be read as averages over wordings that can disagree strongly in size, and InternVL3.5's H4 not as a stable effect of family history.
- **Strict parser.** Under the strict parse rules, the colleague effect holds for Qwen3-VL (39.9 points) and InternVL3.5 (96.4 points, on 435 of 500 cases), and InternVL3.5's age effect remains positive (7.1 points, on 232 cases). InternVL3.5's family-history effect falls to -0.2 points (-0.6 to 0.0) on the 251 cases the strict parser can read. The strict parser reads only 9 of MedGemma's answers, none in a primary-contrast cell, so all MedGemma primary results depend on the lenient parser.
- **Position of the context sentence.** Moving the context sentence to the end of the prompt reduced Qwen3-VL's colleague effect from 39.9 to 27.6 points left InternVL3.5's effect exactly unchanged, and raised MedGemma's by 1.9 points (0.1 to 3.7). H1 reads robust for all three models under this check, so its direction does not depend on sentence position, but its size for Qwen3-VL does. Age and history were not tested in this check.
- **Sampled decoding.** Sampling raised Qwen3-VL's neutral malignant rate from 12.3% to 44.3%, and the colleague effect remained positive (+19.3 points). The main results use greedy decoding, so absolute rates describe the model's most likely answer, not its full output distribution. Only Qwen3-VL and the colleague conditions were tested.

## 12. Reproduction

Every result regenerates from committed outputs with one command, run from
the repository root at the commit given. Model outputs come from the
commits recorded in each call; the commit below is the one that produced
the report or table.

| Result | Output | Command | Config | Commit |
|---|---|---|---|---|
| Baseline (8.1) | `reports/baseline.md` | `uv run python -m eval.baseline` | `configs/models.yaml` `038826f2` | `ec9f10a` |
| Primary outcome (8.2) | `reports/analysis.md`, `reports/analysis/contrasts.csv` | `Rscript analysis/run_analysis.R --final` | `analysis/renv.lock` `bc943dd5` | `caa74c3` |
| Key secondary (8.3) | `reports/analysis.md`, `reports/analysis/contrasts.csv` | `Rscript analysis/run_analysis.R --final` | `analysis/renv.lock` `bc943dd5` | `caa74c3` |
| Descriptive (8.4) | `reports/analysis.md`, `reports/analysis/*.csv`, `reports/figures/*.png` | `Rscript analysis/run_analysis.R --final` | `analysis/renv.lock` `bc943dd5` | `caa74c3` |
| Sensitivity S1, S3 (8.5) | `reports/analysis/flips.csv`, `reports/analysis/contrasts.csv` | `Rscript analysis/run_analysis.R --final` | `analysis/renv.lock` `bc943dd5` | `caa74c3` |
| Sensitivity S2 and robustness (8.5, 8.6) | `reports/robustness.md`, `reports/robustness/*.csv` | `Rscript analysis/run_robustness.R --final` | `configs/robustness.yaml` `645174b7` | `caa74c3` |
| Python cross-check | console: 0 mismatches (1,494 numbers without `--robustness`, 1,965 with it) | `uv run python -m eval.crosscheck` and `uv run python -m eval.crosscheck --robustness` | none | `88484b7` |
| Exploratory 1 (8.7) | `reports/exploratory/surface_features.md` | `uv run python -m eval.surface_features` | none | `0963d70` |
| Phase 7 variant runs | `runs/robustness/<variant>/` | `sh scripts/run_variant.sh <variant>` | `configs/models.yaml` `038826f2`, `configs/robustness.yaml` `645174b7` | `8b3baf1` (all 13,500 calls) |
| Model outputs, tiers T0 to T4 | `runs/<model>/` | `sh scripts/run_tier.sh <tier>` | `configs/models.yaml` `038826f2` | `62956ea` (T0), `fb78d02` (T1), `ad88f15` (T2 to T4) |

Full SHA-256 values: `analysis/renv.lock`
`bc943dd5b79bdf8df84739d29e44e856284bc2d31ac94575d6bb750fe311c6f0`;
`configs/robustness.yaml`
`645174b7061984cca85f0ca96c41322aa0dc37109706faac6570464c3f8d7f73`;
`configs/models.yaml` as in section 5. Exploratory 2 (8.7) is part of
`reports/analysis.md` and comes from the same command and commit as the
primary outcome. `reports/robustness.md` and `reports/analysis.md` were
committed in `c6e4af0`.

[[PENDING: fresh-clone check: date, commit and result of rerunning every
command above in a new clone]]

## 13. Data, license and citation

CBIS-DDSM is used under CC BY 3.0 and the TCIA Data Usage Policy; the
required citations are in `data/README.md`. MedGemma is used under the
Health AI Developer Foundations terms. Code is under the MIT License; to
cite this work, see `CITATION.cff`.
