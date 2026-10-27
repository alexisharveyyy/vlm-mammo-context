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
