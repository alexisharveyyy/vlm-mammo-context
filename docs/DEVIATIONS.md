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
