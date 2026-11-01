# Same Image, Different Answer: Prompt Context Sensitivity of Vision-Language Models in Mammography

**Question.** When the image stays the same, do vision-language models change
their mammogram reading because of what the prompt says (patient context, a
colleague's opinion, irrelevant text)?

## Scope

This is a study of model behavior. It is not a diagnostic tool, it is not
intended for clinical use, and it makes no clinical claims. Nothing in this
repository should be used to interpret a real patient's imaging.

What the study measures, and what it does not:

- It measures how much the answer to the same image changes when only the
  prompt text changes. It does not measure how well the models diagnose.
- In the Phase 4 baseline none of the three models reads the images above
  chance, so a context effect here is a shift in answers that carry little
  information about the image.
- Patient age and family history are synthetic: CBIS-DDSM has neither, so
  every case is read with both values of each.
- The images are digitized film mammograms from the 1990s, from one public
  dataset, read by three small open models (4B and 8B parameters).

The full list, with evidence and mitigations, is in
[docs/THREATS.md](docs/THREATS.md).

## Design in brief

- **Data:** CBIS-DDSM from The Cancer Imaging Archive (TCIA), with BI-RADS
  assessments and biopsy-confirmed benign or malignant labels. No images are
  stored in this repository; see `data/README.md`.
- **Models:** three open vision-language models run locally:
  Qwen3-VL-8B-Instruct, MedGemma 1.5 4B (`google/medgemma-1.5-4b-it`) and
  InternVL3.5-8B. Exact checkpoints and revisions are in
  `configs/models.yaml`. LLaVA-Med was a candidate but was dropped because it
  does not run outside its original CUDA-oriented codebase.
- **Model terms:** MedGemma is used under the Health AI Developer Foundations
  terms; this repository contains only model outputs, no weights and no hosted
  model. Qwen3-VL and InternVL3.5 are Apache-2.0.
- **Conditions:** the same image under a neutral prompt and under prompts that
  add patient age, family history, a colleague's benign or malignant opinion,
  or irrelevant text, plus text-only and blank-image controls.
- **Evaluation:** a fixed dev set for prompt and parser development and a test
  set frozen before any model sees it. Every reported number comes from the
  test set and names the command, config and commit that produced it.

## Status

Phase 5 of 8: context conditions on the test set (tiers T1 to T4).

The Phase 4 baseline is in [reports/baseline.md](reports/baseline.md). On full images
with the neutral prompt, none of the three models is above chance by the rule in
docs/DEVIATIONS.md, entry 2. All three stay in the study.

The hypotheses, outcomes and statistical tests are a pre-specified analysis
plan, frozen at tag `prereg-v1` before any test-set run:
`docs/PREREGISTRATION.md`, SHA-256
`3ae8ae33638b2eb6353eeb199acaa869d1369d21d95527862e8afd68acde8423`.
The plan was not registered with an external registry. Changes made after the
tag are logged in `docs/DEVIATIONS.md`; execution follows
`docs/RUN_DESIGN.md`.

## Quickstart

Every reported number regenerates from the committed outputs; no images, no
model weights and no GPU are needed. From the repository root:

```sh
uv sync                                          # Python 3.12, pinned in uv.lock
uv run python -m eval.baseline                   # Phase 4: reports/baseline.md
Rscript -e 'renv::restore(project = "analysis")' # R 4.4.0, pinned in analysis/renv.lock
Rscript analysis/run_analysis.R --final          # Phase 6: reports/analysis.md, figures
Rscript analysis/run_robustness.R --final        # Phase 7: reports/robustness.md
uv run python -m eval.crosscheck --robustness    # recomputes the point estimates in Python
```

The results viewer (outputs only, no images):

```sh
cd viewer && npm ci && npm run data && npm run dev
```

Rerunning the models needs the CBIS-DDSM images (about 30 GB from the NCI
Imaging Data Commons, verified against the committed checksums) and a machine
that can run 8B models:

```sh
uv run python data/download.py metadata && uv run python data/download.py images
uv run python data/preprocess.py
uv run python data/download.py roi && uv run python data/preprocess.py --roi
uv sync --group models
sh scripts/run_tier.sh T0                        # tiers T0 to T4, docs/RUN_DESIGN.md
```

The final report, with a reproduction table that gives the command, config and
commit of every result, is [reports/FINAL_REPORT.md](reports/FINAL_REPORT.md).

## Repository map

| Path | Content |
|---|---|
| `docs/PREREGISTRATION.md` | the pre-specified analysis plan (frozen at `prereg-v1`) |
| `docs/DEVIATIONS.md` | every change to the plan, with date and reason |
| `docs/RUN_DESIGN.md`, `docs/ROBUSTNESS.md` | how the runs and the Phase 7 checks are done |
| `docs/THREATS.md`, `docs/EXPLORATORY.md` | threats to validity; exploratory analyses |
| `data/` | data card, download and preprocessing scripts, manifests and checksums |
| `prompts/`, `configs/` | prompt text (frozen); model and variant settings |
| `models/` | model adapters, prompt rendering, the answer parser and the runner |
| `runs/` | every model output, one JSON line per call |
| `analysis/` | the statistics in R |
| `eval/` | the baseline, the Python cross-check, exploratory analyses, synthetic test data |
| `reports/` | generated reports, tables and figures |
| `viewer/` | the static results viewer |

## Languages

| Language | Role | Status |
|---|---|---|
| Python | data download and preprocessing, model runs and run logging, the Phase 4 baseline, the cross-check of the R numbers, exploratory analyses | in use |
| R | the statistics and figures under `analysis/` (paired case bootstrap, Wilson intervals, AUROC with pROC, Holm and Benjamini-Hochberg) and the Phase 7 robustness checks, reading only the committed run outputs; versions pinned with renv | written and tested on synthetic and tier T0 outputs; runs on the full outputs after Phase 5 |
| TypeScript | the static results viewer under `viewer/` (Vite), outputs only and no images | built against tier T0; published with GitHub Pages once the repository is public |

## Development

```sh
uv sync
sh scripts/check.sh            # lint, format, tests, audit
sh scripts/final_audit.sh      # Phase 8: the whole history
```

## Data license and citation

CBIS-DDSM is released under the
[Creative Commons Attribution 3.0 Unported License (CC BY 3.0)](https://creativecommons.org/licenses/by/3.0/)
and used under the
[TCIA Data Usage Policy](https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/).
No images are redistributed here; the manifests contain case IDs, labels
derived from the CBIS-DDSM metadata, and checksums. If you use this repository,
cite the dataset and its description:

> Sawyer-Lee, R., Gimenez, F., Hoogi, A., & Rubin, D. (2016). Curated Breast
> Imaging Subset of Digital Database for Screening Mammography (CBIS-DDSM)
> (Version 1) [Data set]. The Cancer Imaging Archive.
> https://doi.org/10.7937/K9/TCIA.2016.7O02S9CY

> Lee, R. S., Gimenez, F., Hoogi, A., Miyake, K. K., Gorovoy, M., & Rubin,
> D. L. (2017). A curated mammography data set for use in computer-aided
> detection and diagnosis research. Scientific Data, 4, 170177.
> https://doi.org/10.1038/sdata.2017.177

The images are obtained through the NCI Imaging Data Commons; see
`data/README.md` for the IDC citation, the changes made to the data, and the
full data card.

## License

Code is released under the MIT License (see `LICENSE`). The CBIS-DDSM data is
not redistributed here and remains under CC BY 3.0.
