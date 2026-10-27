# Analysis (R)

The Phase 6 statistics: the tests and outcomes pre-specified in
`docs/PREREGISTRATION.md` (frozen at tag `prereg-v1`), with any changes in
`docs/DEVIATIONS.md`. R reads only the committed run outputs
(`runs/<model>/<image_kind>/<condition>/p<k>[_plain].jsonl`) and the
manifests; Python runs the models.

## Run

From the repository root, with R 4.4.0:

    Rscript -e 'renv::restore(project = "analysis")'     # once
    Rscript analysis/run_analysis.R                      # writes reports/
    uv run python -m eval.crosscheck                     # must report 0 mismatches

`run_analysis.R` writes `reports/analysis.md`, the tables in
`reports/analysis/` (`contrasts.csv`, `cells.csv`, `flips.csv`,
`sycophancy.csv`) and the figures in `reports/figures/`. A full run takes
about 80 seconds. A contrast whose cells are incomplete is listed as pending,
never estimated.

## Tests

    uv run python -m eval.synthetic --out /tmp/synthetic_runs
    SYNTHETIC_RUNS=/tmp/synthetic_runs Rscript analysis/tests/testthat.R

The tests check the statistics against known values and pROC, the abstention
and answer-order rules against the Python code, the committed tier T0 outputs
against `reports/baseline.json`, and that the analysis recovers the effects
planted in synthetic outputs (`eval/synthetic.py`). Synthetic outputs are
never written to `runs/`.

## Files

| File | Content |
|---|---|
| `R/io.R` | reading the run outputs and manifests; abstention rule; answer order |
| `R/stats.R` | Wilson intervals, AUROC, Brier, ECE, BI-RADS consistency, the paired case bootstrap and its p-value |
| `R/outcomes.R` | case-level values, every contrast with its family, Holm and Benjamini-Hochberg |
| `R/report.R` | the Markdown report and figures |
| `run_analysis.R` | command line entry |
| `renv.lock` | pinned R and package versions |

## Implementation notes

These follow the plan; they record choices the plan leaves to the code.

- **Case-level values** average over the paraphrases with a valid answer
  (plan 5), for `y`, `p_malignant` and verbal P(malignant), as in
  `eval/baseline.py` since deviation 5.
- **Bootstrap:** one set of 10,000 resamples of the 500 test cases (seed
  20261026, Mersenne-Twister with rejection sampling, drawn resample by
  resample) is shared by every contrast. In each resample a contrast uses the
  drawn cases with valid values in both conditions. Intervals are 2.5th and
  97.5th percentiles (linear interpolation). In the p-value, a resample
  exactly at 0 counts as the other side of 0 (conservative), and an
  observed 0 gives p = 1.
- **AUROC:** point estimates with pROC (`direction = "<"`). Bootstrap
  replicates use the same Mann-Whitney statistic computed with resample
  weights, which equals pROC on the expanded resample (tested).
- **Rates** (malignant rate, accuracy, flip rate, sycophancy, consistency,
  abstention) are over calls with Wilson intervals. For a rate difference
  (consistency, abstention, answer order, sycophancy, image reliance
  accuracy), cases are resampled and the rate recomputed over their calls.
- **Families** (`docs/DEVIATIONS.md`, entry 4): primary (12 tests, Holm);
  key secondary (33 tests, Benjamini-Hochberg: per model on full images,
  the `p_malignant` shift and the BI-RADS consistency shift for the four
  primary contrasts, the `irrelevant` control, the answer-order effect on
  `neutral`, and plain minus forced abstention on `neutral`); descriptive
  (estimates and intervals only: ROI contrasts, AUROC shifts, image
  reliance, sycophancy). Each row of `contrasts.csv` names its family and
  adjustment.
- **Sensitivity 1** (failures as flips) is in `flips.csv`; sensitivity 3
  (low mass excluded) in `contrasts.csv`. Sensitivity 2 (strict parser) is
  Phase 7.
- **Exploratory** rows (plan 9) have intervals but no p-values.
