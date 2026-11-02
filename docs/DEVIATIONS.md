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

## 7. Scope of the Phase 7 position and decoding checks (2026-10-27)

- **What:** the two Phase 7 checks that need new model runs cover only the
  colleague contrasts on full images, forced format:
  - position of the context sentence (variant `position_end`):
    `colleague_benign` and `colleague_malignant`, all three models; the
    study's `neutral` outputs are the reference, since `neutral` has no
    context sentence;
  - second decoding setting (variant `sampled`): Qwen3-VL at temperature
    0.7, top_p 1.0, seed 1, on `neutral`, `colleague_benign` and
    `colleague_malignant`.

  This narrows entry 6, which listed all six context conditions of the
  primary contrasts for the decoding check. The age and history contrasts
  (H3, H4) are checked by agreement across paraphrases and the strict
  parser, which need no new runs, but not by these two checks.
- **Why:** the plan names the checks without a scope. The narrowed scope
  costs about 16 hours of runs instead of about 44, and keeps the contrasts
  where a prompt sentence states an answer outright.
- **Results known:** decided by the study owner on 2026-10-27, blind to
  tiers T1 to T4: no T1 to T4 output had been read, and no Phase 7 run had
  been made. The runs start only after Phase 5 is complete.

## 8. Unattended run procedure from tier T2 on (2026-10-29)

Entries 4 to 7 concern the analysis and are added to this file when the
analysis is merged after Phase 5.

- **What:** from tier T2 on, the runs fixed in `docs/RUN_DESIGN.md` (frozen
  with the plan at `prereg-v1`) change in five ways: a watchdog exits a
  model's run with code 4 if no model call finishes for 15 minutes;
  `scripts/run_tier.sh` retries a model that exits non-zero up to 2 times
  (never after a determinism audit mismatch) and starts the next tier when a
  tier finishes; the pinned commit is the latest commit that changed
  anything outside `runs/`, so committing outputs does not change it; the
  determinism audit samples every call of the tier computed at the current
  commit and runs once per tier and commit; and logs are unbuffered.
- **Why:** MedGemma's T1 run took 44.5 hours instead of about 1.5. The Mac's
  lid was closed while it ran on battery at 21:02 UTC on 2026-10-27, and
  `caffeinate` cannot prevent that sleep. From 21:30 UTC the system slept and
  ran only during its maintenance wakes (about every 18 minutes, a few calls
  each), until it was woken at 16:33 UTC on 2026-10-29. No call failed and
  no output was lost: all 3,000 calls were written once, without errors, and
  the determinism audit found 0 mismatches in 30 calls. Because the progress
  lines were buffered, the log showed nothing during that time, and the next
  model waited for a person to notice. The changes let the tiers run
  unattended and make a stall visible and bounded.
- **Effect on results:** none intended or expected. The changes decide when
  calls run, not what a call computes: prompts, images, models, decoding and
  the fields written are unchanged, and the cache equivalence check and the
  determinism audit still run for every model. Before T2 started, the new
  runner reran the tier T0 calls of 3 dev cases for each model: all 189
  outputs were identical to the earlier dev outputs, and every cache
  equivalence check and determinism audit passed (`docs/RUN_DESIGN.md`). Sleep itself is not prevented; the Mac must stay on
  AC power with the lid open.
- **Results known:** the T0 results and the T1 outputs existed. The T1 files
  were read only for call keys, timestamps and error fields to find the
  cause; no T1 answer was read. No analysis result depends on the change.

## 9. Exploratory comparison against the irrelevant sentence (2026-11-01)

- **What:** an exploratory analysis was added: the conditions of H1 to H4
  (`colleague_malignant`, `colleague_benign`, `age_68`, `age_42`,
  `history_yes`, `history_no`) each against `irrelevant` instead of their
  plan reference, on full images, with the same paired case bootstrap,
  estimates and 95% intervals only (`docs/EXPLORATORY.md`, entry 2).
- **Why:** requested by the study owner after reading the results, to see
  the context effects against a reference that also has an extra sentence.
- **Effect on results:** none on the primary, key secondary, descriptive or
  sensitivity analyses. The new rows are in the exploratory family, have no
  p-values and are not corrected for multiplicity.
- **Results known:** yes. Added after the Phase 6 results were seen (tag
  `analysis-v1`, reports at commit `684397b`).

## 10. Reference rates and the p-value floor in the results tables (2026-11-01)

- **What:** two changes to how the reports present results, with no change
  to any estimate, interval, p-value or test decision.
  - Every table of shifts in `reports/analysis.md` and `reports/robustness.md`
    has a reference column: the level of that table's own outcome in the
    comparison. That is the malignant rate for malignant rate shifts, mean
    `p_malignant` for `p_malignant` shifts, the consistency rate for
    BI-RADS consistency shifts and the AUROC for AUROC shifts (likewise
    accuracy, abstention rate, the rate when the colleague is right for
    sycophancy, and the benign-first value for the answer order). For
    paired shifts it is the reference condition's case-level value over the
    same cases. The flip table has the neutral malignant rate. The tables in
    `reports/analysis/contrasts.csv` and `reports/robustness/checks.csv`
    have the columns `reference` and `reference_2`. A first version on the
    same day showed the malignant rate in every table; at the owner's
    request the tables of other outcomes now show their own level.
  - Holm-adjusted p-values at the resolution limit of the bootstrap are
    printed as "p < 0.0025" instead of "0.002", with a note: with 10,000
    resamples and the conservative tie rule the smallest bootstrap p-value
    is 2/10,001, so the smallest Holm-adjusted p-value over 12 tests is
    0.0024. The stored values in the CSV tables are unchanged.
- **Why:** requested by the study owner after reading the results, so that
  floor and ceiling effects are visible next to each shift, and so that a
  p-value at the floor is not read as an exact value.
- **Effect on results:** none. The Python cross-check also recomputes the
  reference level of every paired shift and of the BI-RADS consistency and
  abstention tests.
- **Results known:** yes. Made after the Phase 6 results were seen (tag
  `analysis-v1`).

## Notes

- **Entry 8 and entries 4 to 7 (2026-11-01):** entry 8 says that entries 4
  to 7 are added to this file when the analysis is merged after Phase 5.
  That is resolved: the merge of the analysis into main (commit `ec9f10a`)
  added them, and the entries are now in order. Entry 8 itself is unchanged.
