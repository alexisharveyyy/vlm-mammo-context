# vlm-mammo-context

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
- **Models:** open vision-language models (candidates: Qwen2-VL, LLaVA-Med,
  MedGemma, InternVL).
- **Conditions:** the same image under a neutral prompt and under prompts that
  add patient age, family history, a colleague's benign or malignant opinion,
  or irrelevant text, plus text-only and blank-image controls.
- **Evaluation:** a fixed dev set for prompt and parser development and a test
  set frozen before any model sees it. Every reported number comes from the
  test set and names the command, config and commit that produced it.

## Status

Phase 0 of 8: repository and guardrails. No results yet.

## Development

```sh
uv sync
sh scripts/check.sh
```

## License

Code is released under the MIT License (see `LICENSE`). The CBIS-DDSM data is
not redistributed here and remains under its own terms.
