# Threats to validity

A working list, started on 2026-10-27 during Phase 5 from what was known by
then: the frozen plan, the data, the models and the tier T0 baseline. No tier
T1 to T4 result had been read. Entries 1 to 8 and the other known limits are
as written then. Entries 9 to 12 were added on 2026-11-02 from the Phase 7
results (`reports/robustness.md`), after the primary and secondary results
were known; they state the results and do not interpret them. The list is
summarized in the final report.

Each entry says what the threat is, the evidence for it, what it does to the
conclusions, and what the study does about it.

## 1. No model reads the images above chance

- **Evidence:** in the Phase 4 baseline (`reports/baseline.md`), no model's
  AUROC of `p_malignant` on full images is above chance by the rule in
  `docs/DEVIATIONS.md`, entry 2. Qwen3-VL is significantly below chance
  (AUROC 0.429, 95% interval 0.379 to 0.479). The answers barely depend on
  the image: MedGemma answers benign on 99.7% of full-image calls, and the
  malignant rates on blank and no-image controls are of the same order as on
  real images.
- **Consequence:** a context effect here is a shift in answers that carry
  little information about the image. It shows how much the prompt moves
  these models, not how much it moves a reader who sees the lesion. The
  effects may be larger or smaller for models that read mammograms well.
- **Mitigation:** all models stay in the study as planned; the image
  controls (`no_image`, `blank_full`, `blank_roi`) are reported next to every
  context effect, so a shift can be compared with what the same text does
  without an image. Exploratory analysis 1 (`docs/EXPLORATORY.md`) looks at
  which surface features drive Qwen3-VL's below-chance answers.

## 2. Dataset age, film and scanners

- **Evidence:** CBIS-DDSM is a curated subset of DDSM: film mammograms from
  the 1990s, digitized on several scanners at several institutions
  (`data/README.md`, known issues). Current screening uses digital
  mammography and tomosynthesis.
- **Consequence:** the images differ from those the models are most likely
  to meet in current practice (contrast, noise, resolution, scanner
  artifacts). Effects may not transfer to digital mammograms.
- **Mitigation:** none within the study. Stated as a limit of scope.

## 3. One public dataset

- **Evidence:** every case comes from CBIS-DDSM, one population and one
  curation.
- **Consequence:** results may not generalize to other populations, sites or
  case mixes. The dataset is public and widely used, so the models may have
  seen its images or descriptions during training.
- **Mitigation:** the within-case design compares each image with itself, so
  memorization would have to depend on the prompt condition to bias a
  contrast. Not testable here; stated as a limit.

## 4. Small models

- **Evidence:** the three models have 4B (MedGemma 1.5) and 8B (Qwen3-VL,
  InternVL3.5) parameters. They run locally in bfloat16; none is quantized.
- **Consequence:** larger open models and proprietary models may read the
  images better (threat 1) and may respond to context differently.
- **Mitigation:** none within the study; the model list is fixed in the
  frozen plan. Stated as a limit.

## 5. Synthetic age and family history

- **Evidence:** CBIS-DDSM has no age or family history. Both are
  experimental manipulations (`docs/PREREGISTRATION.md`, 4.1): every case is
  read with both values of each, and the `combined` condition uses values
  assigned at random.
- **Consequence:** the age and history effects measure how the models react
  to the words, not how real patient characteristics relate to findings.
  The assigned values are unrelated to the image, so for some cases the
  sentence is implausible for the image.
- **Mitigation:** the paired design makes each contrast within-case, and the
  `irrelevant` control measures the effect of adding any sentence.

## 6. Label and BI-RADS noise

- **Evidence:** labels are biopsy pathology, with `BENIGN_WITHOUT_CALLBACK`
  (a category the dataset paper does not define) counted as benign. The
  CBIS-DDSM paper notes that many BI-RADS assessments were probably updated
  after more information was gathered, so they may not reflect a reading of
  the image alone; 238 abnormalities have assessment 0 (`data/README.md`,
  known issues).
- **Consequence:** label errors bias accuracy, AUROC and the sycophancy
  split (colleague right or wrong) toward no effect. The CBIS-DDSM BI-RADS
  assessment is used only in an exploratory stratification; the BI-RADS
  consistency outcome compares the model's own BI-RADS with its own answer
  and does not depend on the label.
- **Mitigation:** none beyond the dataset's curation. Stated as a limit.

## 7. Image size and brightness go with the label (dataset confound)

- **Evidence:** in exploratory analysis 1 (`reports/exploratory/surface_features.md`;
  tier T0 cases only; exploratory, not part of the frozen plan), surface
  properties of the 500 test images are associated with the biopsy label on
  their own. As a score for malignancy, image height has an AUROC of 0.580
  (95% interval 0.529 to 0.630) and mean intensity 0.582 (0.533 to 0.630);
  the breast area fraction, mean and spread are between 0.566 and 0.577,
  and image width goes the other way (0.425, 0.375 to 0.479). These
  properties come from the film, digitizer and site rather than the lesion.
- **Consequence:** a model can look better or worse than chance through
  acquisition properties instead of the lesion. For Qwen3-VL, height,
  brightness and breast area fraction all correlate negatively with
  `p_malignant` (Spearman about -0.15) while going with malignancy, the
  direction of its below-chance AUROC; adding the surface features to a
  regression moves the label coefficient only from -0.021 to -0.016, so
  they explain a small part of it. Accuracy and AUROC in this dataset are
  therefore not clean measures of reading the lesion.
- **Mitigation:** the context effects compare each image with itself, so a
  property of the image is held fixed within every contrast and cannot by
  itself create a context effect; it can only change how large the room for
  a shift is. The association is reported as exploratory and was found on
  T0 only.

## 8. Answer-order sensitivity

- **Evidence:** in the Phase 4 baseline, the order in which the two options
  are listed changes the answers a lot. On full images under `neutral`,
  Qwen3-VL answers malignant 24.1% of the time when malignant is listed
  first and 0.5% when benign is; InternVL3.5 shows the reverse (3.3% and
  26.3%). MedGemma shows no clear effect.
- **Consequence:** answer order is as large a prompt effect as any the study
  measures, and it may interact with the context conditions.
- **Mitigation:** order is counterbalanced within case (every case sees both
  orders across paraphrases, and the order is the same across conditions),
  so contrasts are not confounded with it. The order effect on `neutral` is
  a key secondary test (`docs/DEVIATIONS.md`, entry 4), and its other cells
  are reported as exploratory.

## Added in Phase 7

Readings follow the rule fixed in `docs/ROBUSTNESS.md` before the results:
robust means the same sign as a significant primary result and a 95%
interval excluding 0; unchanged means an interval including 0 for a primary
result that is not significant; sensitive means anything else.

## 9. Dependence on the paraphrase (R1)

- **Evidence:** each primary contrast computed from one paraphrase at a
  time gives estimates that differ between paraphrases. For Qwen3-VL, H1 is
  44.2% (39.6% to 49.0%), 66.2% (62.2% to 70.4%) and 9.4% (6.6% to 12.2%)
  from paraphrases 1, 2 and 3. Of the 36 single-paraphrase estimates, 35 read
  robust or unchanged. The exception is InternVL3.5's H4
  (`history_yes` vs `history_no`) from paraphrase 3: 0.0% (0.0% to 0.0%)
  against 50.6% (46.4% to 55.0%) and 24.8% (21.0% to 28.8%) from paraphrases
  1 and 2, read sensitive. On full images under `neutral`, the share of
  cases whose three answers agree is 66.6% for Qwen3-VL, 99.4% for MedGemma
  1.5 and 62.8% for InternVL3.5.
- **Where reported:** `reports/robustness.md`, R1; final report, section
  8.6.

## 10. Strict parser (R3, sensitivity 2)

- **Evidence:** under the frozen strict rules, Qwen3-VL's four primary
  contrasts are identical to the primary results (every lenient answer is
  also strictly valid) and read robust. MedGemma 1.5 has no strictly valid
  answer in these cells, so its four contrasts have no data. InternVL3.5's
  H1, H2 and H3 read robust, on 435, 435 and 232 of 500 cases. Its H4 is
  -0.2% (-0.6% to 0.0%), Holm p 0.752, on 251 of 500 cases, against 25.1%
  (23.8% to 26.5%) in the primary analysis, and reads sensitive.
- **Where reported:** `reports/robustness.md`, R3; final report, section
  8.5.

## 11. Position of the context sentence (R2)

- **Evidence:** with the context sentence after the task, the colleague
  contrasts read robust for all three models, except MedGemma 1.5's H2,
  which reads unchanged (as in the primary analysis). The difference from
  the study (end minus middle) is -12.3% (-14.0% to -10.7%) for Qwen3-VL's
  H1, 1.9% (0.1% to 3.7%) for MedGemma 1.5's H1, and 0.0% (0.0% to 0.0%)
  for the other four contrasts. The age and history contrasts were not run
  in this position (`docs/DEVIATIONS.md`, entry 7).
- **Where reported:** `reports/robustness.md`, R2; final report, section
  8.6.

## 12. Decoding setting (R4)

- **Evidence:** with sampled decoding (Qwen3-VL only; temperature 0.7,
  top_p 1.0, seed 1), H1 is 19.3% (16.8% to 21.9%) and H2 is -44.3% (-46.5%
  to -42.1%); both read robust. The `neutral` malignant rate is 44.3% under
  sampling and 12.3% under greedy decoding. The differences from greedy
  (sampled minus greedy) are -20.6% (-23.4% to -17.9%) for H1 and -32.0%
  (-34.3% to -29.7%) for H2. Sampled answers equal the greedy answer in
  68.0% of (case, paraphrase) pairs under `neutral`, 100.0% under
  `colleague_benign` and 88.6% under `colleague_malignant`. The other two
  models and the age and history contrasts were not run with sampling.
- **Where reported:** `reports/robustness.md`, R4; final report, section
  8.6.

## Other known limits

- **Strict parser:** the frozen strict rules, kept unchanged, require a
  lowercase class word. On tier T0 they accept 100% of Qwen3-VL's valid
  answers, 0.01% of MedGemma's (1 of 10,000; none in the full-image
  `neutral` cell) and 42.0% of InternVL3.5's (29.6% in that cell). So
  sensitivity 2 cannot be computed for MedGemma and rests on a minority of
  InternVL3.5's answers (`docs/ROBUSTNESS.md`, R3).
- **Abstention:** under the plain format Qwen3-VL abstains on 99.4% of
  full-image calls; the forced format is primary for this reason, and
  forced answers may not reflect what the model would say unprompted.
- **Image resolution:** each model sees the master image downsampled to its
  input size (`configs/models.yaml`: at most about one million pixels for
  Qwen3-VL, 896 px on the long side for MedGemma and InternVL3.5 before
  their own tiling), which may lose fine calcifications.
- **One view, one decoding setting:** one MLO image per patient, and greedy
  decoding; Phase 7 adds one sampled setting for one model (Qwen3-VL).
- **Robustness scope:** the position and decoding checks cover only the
  colleague contrasts; the age and history contrasts are not checked for
  either (`docs/DEVIATIONS.md`, entry 7; `docs/EXPLORATORY.md`).
