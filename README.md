# Same Image, Different Answer: Prompt Context Sensitivity of Vision-Language Models in Mammography

**Question.** When the image stays the same, do vision-language models change
their mammogram reading because of what the prompt says (patient context, a
colleague's opinion, irrelevant text)?

## Scope

This is a study of model behavior. It is not a diagnostic tool, it is not
intended for clinical use, and it makes no clinical claims. Nothing in this
repository should be used to interpret a real patient's imaging.

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

Phase 4 of 8: baseline on the test set.

The hypotheses, outcomes and statistical tests are a pre-specified analysis
plan, frozen at tag `prereg-v1` before any test-set run:
`docs/PREREGISTRATION.md`, SHA-256
`3ae8ae33638b2eb6353eeb199acaa869d1369d21d95527862e8afd68acde8423`.
The plan was not registered with an external registry. Changes made after the
tag are logged in `docs/DEVIATIONS.md`; execution follows
`docs/RUN_DESIGN.md`.

## Languages

| Language | Role | Status |
|---|---|---|
| Python | data download and preprocessing, model runs, run logging, a cross-check of the headline numbers | in use |
| R | statistics and figures under `analysis/` (bootstrap, Wilson intervals, AUROC, multiple-comparison correction), reading only the committed run outputs; versions pinned with renv | planned (Phase 6) |
| TypeScript | static results viewer under `viewer/` (Vite), outputs only and no images | planned (Phase 8) |

## Development

```sh
uv sync
sh scripts/check.sh
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
