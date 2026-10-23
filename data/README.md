# Data card: CBIS-DDSM subset

This repository stores no images, DICOMs or pixel-derived files. It stores the
scripts that download and preprocess the data, case ID manifests, labels taken
from the CBIS-DDSM metadata, and checksums.

## Source

- **Dataset:** Curated Breast Imaging Subset of the Digital Database for
  Screening Mammography (CBIS-DDSM), Version 1, The Cancer Imaging Archive
  (TCIA). DOI [10.7937/K9/TCIA.2016.7O02S9CY](https://doi.org/10.7937/K9/TCIA.2016.7O02S9CY).
- **Images:** downloaded from the NCI Imaging Data Commons (IDC) public
  bucket with `idc-index` (IDC data release v25, `idc-index` 0.13.4; both are
  recorded in `manifests/splits.json`).
- **Metadata:** the four case description CSVs from the TCIA collection page,
  pinned by SHA-256 in `manifests/splits.json`.

## License and required citations

CBIS-DDSM is released under the
[Creative Commons Attribution 3.0 Unported License (CC BY 3.0)](https://creativecommons.org/licenses/by/3.0/).
Use is subject to the
[TCIA Data Usage Policy](https://www.cancerimagingarchive.net/data-usage-policies-and-restrictions/).
Anyone who uses the data, including through this repository, must:

- cite the dataset (required by TCIA whenever the data are used):

  > Sawyer-Lee, R., Gimenez, F., Hoogi, A., & Rubin, D. (2016). Curated Breast
  > Imaging Subset of Digital Database for Screening Mammography (CBIS-DDSM)
  > (Version 1) [Data set]. The Cancer Imaging Archive.
  > https://doi.org/10.7937/K9/TCIA.2016.7O02S9CY

- cite the publication that describes it:

  > Lee, R. S., Gimenez, F., Hoogi, A., Miyake, K. K., Gorovoy, M., & Rubin,
  > D. L. (2017). A curated mammography data set for use in computer-aided
  > detection and diagnosis research. Scientific Data, 4, 170177.
  > https://doi.org/10.1038/sdata.2017.177

- because the images come through IDC, cite IDC:

  > Fedorov, A., Longabaugh, W. J. R., Pot, D., Clunie, D. A., Pieper, S. D.,
  > Gibbs, D. L., et al. (2023). National Cancer Institute Imaging Data
  > Commons: Toward Transparency, Reproducibility, and Scalability in Imaging
  > Artificial Intelligence. RadioGraphics, 43(12).
  > https://doi.org/10.1148/rg.230180

- not attempt to identify or contact any individual in the data.

TCIA also requests a citation of Clark, K. et al. (2013). The Cancer Imaging
Archive (TCIA): Maintaining and Operating a Public Information Repository.
Journal of Digital Imaging, 26(6), 1045-1057.
https://doi.org/10.1007/s10278-013-9622-7

**Changes made (CC BY 3.0 asks that changes be indicated).** The manifests
are derived from the CBIS-DDSM CSVs: abnormality rows are collapsed to one row
per full mammogram, pathology is mapped to a binary label, and a subset of
cases is selected as described below. No images are redistributed.

## Units and labels

- **Patient:** the CSV `patient_id` (for example `P_00001`). CBIS-DDSM gives
  each image a separate DICOM PatientID such as `Mass-Training_P_00001_LEFT_CC`;
  those are not used as patient identifiers here. There are 1,566 patients.
- **Image:** one full mammogram series, which is one view (CC or MLO) of one
  breast. The CSVs list 3,568 abnormalities on 3,103 full images.
- **Case:** one MLO full mammogram of one patient. `case_id` is
  `<patient_id>_<side>_MLO`.
- **Binary label:** `malignant` if the CBIS-DDSM pathology is `MALIGNANT`;
  `benign` if it is `BENIGN` or `BENIGN_WITHOUT_CALLBACK`. Pathology is
  biopsy-confirmed in CBIS-DDSM. The original value is kept in the `pathology`
  column.
- **BI-RADS:** `birads_assessment` is the highest assessment over the
  abnormalities on the image; `assessments` lists all of them. It is a
  secondary label and is not used for stratification.
- **Abnormality type:** `mass` or `calc` (calcification), from the CSV the
  image comes from.

## View choice: MLO only

Each case is a single MLO image, for three reasons:

1. One image per prompt is the only input every candidate model accepts in
   the same way. Some candidates (for example LLaVA-Med) take a single image,
   and multi-image handling differs between the others, which would confound
   the prompt effect being studied.
2. The MLO view images the most breast tissue, including the upper outer
   quadrant and axilla, so it is the single view most likely to show the
   abnormality.
3. More patients have an eligible MLO image than an eligible CC image (1,468
   vs 1,309 patients before the stratum rule below).

## Splits

`make_splits.py` builds the splits from metadata only (no pixels are read),
with seed `20261023`. Every patient is assigned to exactly one of `dev`,
`test` or `reserve`, so all images, views and sides of a patient stay in one
split. The official CBIS-DDSM train/test split is not used (31 patients appear
in both of its parts); it is kept in the `official_split` column for
reference.

1. An image is eligible if it is an MLO view and all abnormalities on it share
   one binary label (17 images have both benign and malignant findings).
2. A patient is eligible if they have an eligible image and all their eligible
   images fall in one stratum (abnormality type x label).
3. Within each of the four strata, eligible patients are shuffled; the first
   125 go to test, the next 25 to dev, the rest to reserve.
4. Each sampled patient's case is drawn from their eligible images with the
   same seeded generator.

| | dev | test | reserve |
|---|---:|---:|---:|
| Patients | 100 | 500 | 966 |
| Full images (all views, all sides) | 190 | 991 | 1,922 |
| Breasts | 104 | 540 | 1,064 |
| Images, CC / MLO | 86 / 104 | 454 / 537 | 920 / 1,002 |
| Images, left / right | 88 / 102 | 507 / 484 | 997 / 925 |
| Cases | 100 | 500 | 0 |

Reserve patients: 788 eligible but not sampled, 80 with eligible images in
more than one stratum, 98 with no eligible image. No patient appears in both
dev and test (`tests/test_manifests.py` checks this on every CI run).

### Class balance

| Cases | calc benign | calc malignant | mass benign | mass malignant |
|---|---:|---:|---:|---:|
| dev | 25 | 25 | 25 | 25 |
| test | 125 | 125 | 125 | 125 |

Test set details: pathology `MALIGNANT` 250, `BENIGN` 197,
`BENIGN_WITHOUT_CALLBACK` 53; left 256, right 244; 36 cases have more than one
abnormality on the image.

BI-RADS assessment by label in the test set:

| | 0 | 2 | 3 | 4 | 5 |
|---|---:|---:|---:|---:|---:|
| benign | 24 | 40 | 50 | 134 | 2 |
| malignant | 9 | 0 | 23 | 133 | 85 |

## Synthetic patient context (experimental manipulation)

CBIS-DDSM has no patient age (the DICOM PatientAge field is empty) and no
family history. The `age` and `history` prompt conditions therefore use
**synthetic values that are experimental manipulations, not real patient
attributes**. They carry no information about the patient or the image and
must never be read as clinical data.

- `synthetic_age`: 42 or 68.
- `synthetic_family_history`: `present` or `absent`.
- The four combinations are counterbalanced within each split and stratum
  (abnormality type x label), assigned with seed `20261024`
  (`context_seed` in `manifests/splits.json`). Cell sizes differ by at most
  one: in the test set each combination has 124 to 126 cases, and age and
  history are each split 125/125 or 126/124 within each label.

The assignment will be restated in the preregistration (Phase 3).

## ROI crops

For each case, `crop_series_instance_uids` and `mask_series_instance_uids`
list the CBIS-DDSM ROI crop and mask series of every abnormality on the image,
and `roi_crop_available` is true when all of them are in the IDC index. All
100 dev and all 500 test cases have ROI crops available. Crops are not
downloaded yet; they may be used as a secondary image condition. In many
series the crop and the mask are two instances of one series, and their order
differs between the mass and calc files, so they have to be told apart by
content (the mask is binary) when they are used.

## Preprocessing

`preprocess.py` writes one full-resolution master PNG per case and applies
the same steps to every image:

1. Read the 16-bit MONOCHROME2 pixels. The DICOMs carry no VOI LUT or window
   tags.
2. Fixed linear window: 0 to 65535 maps to 0 to 255, computed in exact integer
   arithmetic (`(x * 255 + 32767) // 65535`). This keeps the digitized film
   density as it is and involves no per-image choice. A per-image percentile
   window was considered and rejected because it changes the image depending
   on its content.
3. No resizing, flipping, cropping or contrast enhancement. Each model adapter
   (Phase 2) resizes the master to that model's input size, so the resizing
   rule is recorded with the model configuration.

The 600 master PNGs are 1,831 to 4,966 pixels wide and 3,944 to 7,111 pixels
tall (2.3 GB in total; the source DICOMs are about 20 GB).

PNGs are written with fixed settings: zlib level 9, no optimize pass, no
metadata. `manifests/png_sha256.csv` records the SHA-256 of each PNG file and
the SHA-256 of its decoded pixels; the pixel hash does not depend on the PNG
encoder. Pillow, pydicom, numpy, pandas, idc-index and idc-index-data are
pinned to exact versions in `pyproject.toml` and `uv.lock`.

## Reproduce

```sh
uv run python data/download.py metadata   # CSVs, verified against splits.json
uv run python data/make_splits.py         # rewrites the manifests; must not change them
uv run python data/download.py images     # about 20 GB, verified against dicom_checksums.csv
uv run python data/preprocess.py          # PNGs, verified against png_sha256.csv
```

`make_splits.py` reads the IDC index bundled with `idc-index`, so the lockfile
pins the index version.

## Manifests

| File | Content |
|---|---|
| `manifests/dev.csv`, `manifests/test.csv` | one row per case: IDs, labels, BI-RADS, density, subtlety, DICOM UIDs, IDC series UUID, synthetic age and family history, ROI crop and mask series |
| `manifests/patients.csv` | every patient with its split and the reason for reserve |
| `manifests/splits.json` | seed, rules, IDC versions, source CSV SHA-256, counts per split |
| `manifests/dicom_checksums.csv` | per case: IDC object name, size, MD5 from the IDC bucket, SHA-256 |
| `manifests/png_sha256.csv` | per case: PNG width and height, file SHA-256, pixel SHA-256 |

`test.csv` is frozen at the `splits-v1` tag and never changes after it.

## Known issues

- **Dataset age:** DDSM is scanned film from the 1990s, digitized on several
  scanners at several institutions. It does not look like modern digital
  mammography, and results may not transfer to it.
- **Missing demographics:** PatientAge is empty in the DICOM headers and the
  CSVs have no age or history, so the age and history conditions use
  synthetic values (see above).
- **BI-RADS noise:** the CBIS-DDSM paper notes that many BI-RADS assessments
  were probably updated after more information was gathered, so they may not
  reflect a reading of the image alone. 238 abnormalities have assessment 0
  and 3 have assessment 1.
- **Undefined category:** `BENIGN_WITHOUT_CALLBACK` is not defined in the
  dataset paper; it is treated as benign.
- **Out-of-range values:** breast density 0 occurs on 2 rows (valid range 1 to
  4) and subtlety 0 on 2 rows.
- **Duplicate images:** 71 breast and view pairs appear as two series, one
  from the mass CSV and one from the calc CSV. The stratum rule keeps such
  patients out of dev and test when the two series fall in different strata.
- **CSV formatting:** the last file path column ends with a newline inside
  the field, and the density column is spelled `breast_density` in the mass
  files and `breast density` in the calc files. `cbis.py` normalizes both.
- **IDC metadata:** for some Calc-Test series the IDC index has PatientID
  values ending in `.dcm` and swapped SeriesDescription values. Series are
  therefore matched on SeriesInstanceUID only.
- **Removed images:** sources disagree on how many images the curators
  removed (254 on the TCIA page, 339 in the paper).
