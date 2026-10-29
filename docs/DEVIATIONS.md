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
