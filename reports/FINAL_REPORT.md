# Same Image, Different Answer: Prompt Context Sensitivity of Vision-Language Models in Mammography

**Final report.** Alexis Harvey, Louisiana State University.

This is a study of model behavior. It is not a diagnostic tool, it is not
intended for clinical use, and it makes no clinical claims.

> **Status: skeleton.** Setup, data, models, protocol, statistics and
> deviations are written from the frozen plan and the repository. Every
> result is a marked placeholder, `[[PENDING: ...]]`, to be filled from the
> final analysis run after Phase 5 and Phase 7. `scripts/final_audit.sh`
> fails while any placeholder remains.

## 1. Summary

[[PENDING: three to five sentences with the headline findings, filled from
reports/analysis.md and reports/robustness.md after the final run]]

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
  exactly. [[PENDING: determinism audit totals for tiers T0 to T4 and the
  Phase 7 variants]]

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
  (`docs/RUN_DESIGN.md`). [[PENDING: completed calls, errors and parse
  failures per tier and model]]

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

### 8.1 Baseline: reading the images (Phase 4)

[[PENDING: above-chance label, AUROC and accuracy per model on full images,
neutral, forced format, from reports/baseline.md regenerated at merge with
the rule of deviation 5]]

[[PENDING: image reliance: full vs no_image and blank_full, roi vs
blank_roi]]

[[PENDING: abstention under the plain format]]

### 8.2 Primary outcome

[[PENDING: table of the 12 primary tests (estimate, 95% interval, p, Holm
p) from reports/analysis.md, and figure reports/figures/primary_shift.png]]

### 8.3 Key secondary outcomes

[[PENDING: p_malignant shifts, BI-RADS consistency shifts, irrelevant
control, answer order, abstention, with Benjamini-Hochberg p-values]]

### 8.4 Descriptive outcomes

[[PENDING: sycophancy by image kind (reports/figures/sycophancy.png), ROI
contrasts, AUROC by condition (reports/figures/auroc.png), flip rates]]

### 8.5 Sensitivity analyses

[[PENDING: S1, S2 and S3 against the primary results]]

### 8.6 Robustness (Phase 7)

[[PENDING: R1 to R4 with their readings, from reports/robustness.md]]

### 8.7 Exploratory analyses

[[PENDING: plan section 9 analyses from reports/analysis.md, and
reports/exploratory/surface_features.md, each labeled exploratory]]

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

[[PENDING: any later deviation entries]]

## 10. Threats to validity

The full list, with evidence and mitigations, is in `docs/THREATS.md`: no
model reads the images above chance; film mammograms from the 1990s
digitized on several scanners; one public dataset; small models (4B and 8B,
not quantized); synthetic age and family history; label and BI-RADS noise;
image size and brightness associated with the label (a dataset confound);
answer-order sensitivity; and the strict parser's case sensitivity.

[[PENDING: threats added in Phase 7 and how the results bear on each]]

## 11. Reproduction

Every result regenerates from committed outputs with one command, run from
the repository root at the commit given. Model outputs come from the
commits recorded in each call; the commit below is the one that produced
the report or table.

| Result | Output | Command | Config | Commit |
|---|---|---|---|---|
| Baseline (8.1) | `reports/baseline.md` | `uv run python -m eval.baseline` | `configs/models.yaml` `038826f2` | [[PENDING: commit]] |
| Primary outcome (8.2) | `reports/analysis.md`, `reports/analysis/contrasts.csv` | `Rscript analysis/run_analysis.R --final` | `analysis/renv.lock` [[PENDING: SHA-256]] | [[PENDING: commit]] |
| Key secondary (8.3) | `reports/analysis.md`, `reports/analysis/contrasts.csv` | `Rscript analysis/run_analysis.R --final` | `analysis/renv.lock` [[PENDING: SHA-256]] | [[PENDING: commit]] |
| Descriptive (8.4) | `reports/analysis.md`, `reports/analysis/*.csv`, `reports/figures/*.png` | `Rscript analysis/run_analysis.R --final` | `analysis/renv.lock` [[PENDING: SHA-256]] | [[PENDING: commit]] |
| Sensitivity S1, S3 (8.5) | `reports/analysis/flips.csv`, `reports/analysis/contrasts.csv` | `Rscript analysis/run_analysis.R --final` | `analysis/renv.lock` [[PENDING: SHA-256]] | [[PENDING: commit]] |
| Sensitivity S2 and robustness (8.5, 8.6) | `reports/robustness.md`, `reports/robustness/*.csv` | `Rscript analysis/run_robustness.R --final` | `configs/robustness.yaml` [[PENDING: SHA-256]] | [[PENDING: commit]] |
| Python cross-check | console: 0 mismatches | `uv run python -m eval.crosscheck --robustness` | none | [[PENDING: commit]] |
| Exploratory 1 (8.7) | `reports/exploratory/surface_features.md` | `uv run python -m eval.surface_features` | none | [[PENDING: commit]] |
| Phase 7 variant runs | `runs/robustness/<variant>/` | `sh scripts/run_variant.sh <variant>` | `configs/models.yaml`, `configs/robustness.yaml` [[PENDING: SHA-256]] | [[PENDING: commits recorded in the outputs]] |
| Model outputs, tiers T0 to T4 | `runs/<model>/` | `sh scripts/run_tier.sh <tier>` | `configs/models.yaml` `038826f2` | [[PENDING: commits recorded in the outputs]] |

[[PENDING: fresh-clone check: date, commit and result of rerunning every
command above in a new clone]]

## 12. Data, license and citation

CBIS-DDSM is used under CC BY 3.0 and the TCIA Data Usage Policy; the
required citations are in `data/README.md`. MedGemma is used under the
Health AI Developer Foundations terms. Code is under the MIT License; to
cite this work, see `CITATION.cff`.
