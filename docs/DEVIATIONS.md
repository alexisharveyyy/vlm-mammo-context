# Deviations from the pre-specified analysis plan

The pre-specified analysis plan is `PREREGISTRATION.md`, frozen at tag
`prereg-v1` before any test-set run (SHA-256
`3ae8ae33638b2eb6353eeb199acaa869d1369d21d95527862e8afd68acde8423`).
Every change to that plan is recorded here before the affected analysis is reported:
the date, what changed, why, and whether any affected test-set result was
already known when the change was made.

## 1. Prompt text for the blank ROI control (2026-10-25)

- **What:** the `blank_roi` control (an all-black image the size of the ROI
  crop) is given the ROI-crop prompt text, and `blank_full` the full-image
  text.
- **Why:** section 4.2 of the plan gives each blank control the same prompt
  text as its image condition, and section 5.2 compares `roi` with
  `blank_roi`. A comment in the frozen `prompts/frame.yaml` says the
  blank-image control uses the full-image frame; it was written before the
  blank control was split into full-size and ROI-size versions, and the
  frozen `models/prompts.py` only handled the full-size name. Using the
  full-image text for `blank_roi` would change the image and the text at
  once and confound the comparison.
- **Results known:** none. Found by the runner's unit tests before any
  test-set call. No frozen file was edited; the rule is in
  `models/prompts.py` (`FRAME_FOR`).

## 2. Definition of "above chance" for the Phase 4 baseline (2026-10-25)

- **What:** a model is labeled above chance when the lower bound of the 95%
  case-bootstrap interval (10,000 resamples, seed 20261026) of the AUROC of
  case-level `p_malignant` exceeds 0.5, on full images, `neutral`, forced
  format. Accuracy of the forced-choice answer is reported next to it but
  does not decide the label.
- **Why:** the plan requires each model to be labeled above chance or not
  (Phase 4) and keeps every model in the study either way, but it does not
  define the label. `p_malignant` is the plan's primary confidence measure;
  on a balanced test set a model that gives nearly the same answer to every
  case has accuracy near 0.5 even if it ranks cases well, so accuracy alone
  would not show whether the model reads the image.
- **Results known:** none. Written before any test-set call. This adds a
  descriptive label; it changes no hypothesis, outcome or test.

## 3. Abstentions counted apart from parse failures in the baseline report (2026-10-27)

- **What:** `eval/baseline.py` counts an answer whose assessment line names
  neither benign nor malignant (for example "Assessment: indeterminate") as
  an abstention, and only output with no readable assessment as a parse
  failure. The first version counted every unparsed answer as both.
- **Why:** section 5 of the plan defines the abstention rate (item 8) and
  the parse failure rate (item 11) as separate outcomes. The change brings
  the report into line with the plan; it does not change the plan. Both
  kinds of answer remain missing in every other metric, as before.
- **Results known:** yes. Made after the tier T0 test-set results were seen,
  when the first report showed identical abstention and parse failure
  rates. It changes no above-chance label, which depends only on the AUROC
  of `p_malignant`.

## 4. Secondary analyses split into a key secondary family and descriptive outcomes (2026-10-27)

- **What:** section 7.1 put every secondary contrast with a p-value into one
  Benjamini-Hochberg family. The secondary analyses are now split in two.
  - **Key secondary family** (Benjamini-Hochberg at q = 0.05), full images
    and forced format unless stated, per model:
    - the paired `p_malignant` shift for each of the four primary contrasts
      (`colleague_malignant` and `colleague_benign` vs `neutral`, `age_68`
      vs `age_42`, `history_yes` vs `history_no`);
    - `irrelevant` vs `neutral` on the primary outcome (the control);
    - the answer-order effect: the malignant rate when malignant is listed
      first minus when benign is, on `neutral`;
    - the abstention rate on `neutral` under the plain format minus the
      forced format;
    - BI-RADS vs assessment consistency: the change in the consistent share
      for each of the four primary contrasts.

    That is 11 tests per model, 33 in all. p-values use the paired case
    bootstrap of section 7. Rate differences are over calls, with cases
    resampled.
  - **Descriptive**, with estimates and 95% intervals but no p-values or
    corrections: the colleague contrasts on ROI crops and their difference
    from full images, AUROC shifts versus `neutral` for `p_malignant` and
    verbal confidence on every image kind, image reliance (accuracy and
    AUROC), and sycophancy for every image kind.
  - Sensitivity and exploratory analyses are unchanged (sections 8 and 9),
    except that the answer-order effect on full images under `neutral`
    moves from exploratory into the key secondary family. Its other cells
    stay exploratory.
- **Why:** the original family would have held about 170 tests, mostly
  descriptive checks (ROI and verbal-confidence versions, image reliance,
  sycophancy by image kind). Correcting them together with the contrasts
  the study is about would dilute those contrasts. The key family keeps the
  pre-specified secondary outcome (the `p_malignant` shift), the control,
  and three per-model properties of the answers.
- **Results known:** decided before any tier T1 to T4 output was read. The
  `p_malignant`, control and consistency tests use T1 and T2 outputs, which
  had not been read. The answer-order and abstention tests use only the
  tier T0 outputs, and their descriptive values were already reported in
  `reports/baseline.md` (Phase 4) when this decision was made. The primary
  family and its Holm correction are unchanged. The bootstrap p-value keeps
  its conservative handling of ties: a resample exactly at 0 counts as the
  other side of 0.

## 5. Phase 4 case-level `p_malignant` averaged over valid answers only (2026-10-27)

- **What:** `eval/baseline.py` now averages case-level `p_malignant` and
  verbal P(malignant) over valid answers only. The first version averaged
  `p_malignant` over every call without a run error, including abstentions
  and parse failures. Valid answers are now also required to be parsed.
  The R analysis uses the same rule.
- **Why:** section 5 of the plan defines case-level values as averages over
  the paraphrases with a valid answer.
- **Results known:** yes. Found after the Phase 4 report, when the R
  analysis was checked against it. The two rules agree on every cell where
  all calls are valid, including the full-image `neutral` cells that decide
  the above-chance labels, so no label can change. On the committed T0
  outputs, only two Qwen3-VL cells change: `roi` (AUROC 0.566 to 0.567) and
  `blank_roi` (AUROC 0.535 to 0.497, Brier 0.253 to 0.274, ECE 0.076 to
  0.161). `reports/baseline.md` is regenerated with the plan's rule when
  the analysis branch is merged after Phase 5.

## 6. Model and setting for the second decoding check (2026-10-27)

- **What:** the Phase 7 check "a second decoding setting for one model"
  (plan section 9) is run on Qwen3-VL, with sampling at temperature 0.7,
  top_p 1.0 and seed 1 set before every call, on full images, forced
  format, for `neutral` and the six conditions of the primary contrasts
  (`configs/robustness.yaml`, variant `sampled`; `docs/ROBUSTNESS.md`, R4).
- **Why:** the plan names the check but not the model or the setting. A
  second seed alone would not change any answer, because the study decodes
  greedily and the determinism audits show identical reruns; the second
  setting therefore samples. Qwen3-VL was chosen because sampling can only
  change answers whose probabilities are not near 0 or 1: on the tier T0
  outputs (full images, `neutral`, forced format), 74% of Qwen3-VL's valid
  answers have `p_malignant` between 0.2 and 0.8, against 29% for
  InternVL3.5 and 0.4% for MedGemma.
- **Results known:** chosen from the tier T0 outputs only, which had been
  reported in `reports/baseline.md`. No tier T1 to T4 output had been read,
  and no Phase 7 run has been made.
