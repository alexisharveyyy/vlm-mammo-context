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

The assignment is restated in the pre-specified analysis plan
(`docs/PREREGISTRATION.md`, frozen at tag `prereg-v1` before any test-set run).

## ROI crops

`crop_series_instance_uids` and `mask_series_instance_uids` in `dev.csv` and
`test.csv` list the CBIS-DDSM ROI crop and mask series of every abnormality on
the case image; `roi_crop_available` is true for all 100 dev and all 500 test
cases. `download.py roi` fetches the crop and mask series of one selected
abnormality per case (1,200 DICOM objects, about 10 GB), verified by size and
the IDC bucket MD5, and `preprocess.py --roi` converts the crops. They may be
used as a secondary image condition.

**One abnormality per case.** 39 cases have more than one abnormality on the
image (3 dev, 36 test). All abnormalities on a case image share the case's
binary label (this is an eligibility rule of the splits), and in this data
they also share its pathology, so the label comes from each of them. The rule
uses the abnormality with the highest BI-RADS assessment, which is the case's
`birads_assessment`, and breaks ties by the lowest CBIS-DDSM abnormality id.
The assessments differ in 3 test cases; in 2 of them
(`P_00284_LEFT_MLO`, `P_00969_LEFT_MLO`) the rule selects abnormality 2.

**Crop or mask is decided by content.** The mask is the image whose pixels
take at most two values (masks are 8-bit with values 0 and 255; crops are
16-bit). Series and instance order are never used.

**Swapped series.** In 579 cases (94 dev, 485 test) the crop and the mask are
two instances of one series. Both instances have InstanceNumber 1 and IDC
names files by UUID, so the CSV file names (`000000`, `000001`) cannot be
mapped to an instance; whether the CSV order is swapped is undetermined
there. The CSVs use a fixed convention by file type (the calc files name the
crop `000001`, the mass files `000000`). IDC gives such a series a single
description ("cropped images" or "ROI mask images") that does not tell the
two apart. In the other 21 cases (6 dev, 15 test) the crop and mask are
separate series: the CSV names the mask series as the crop in 1 case
(`P_00474_LEFT_MLO`, test), and IDC's series descriptions match the content
in all 21.

The crops are converted with the same fixed settings as the full images
(16-bit to 8-bit integer window, no resizing, same PNG options). Crops are 81
to 2,853 pixels wide and 81 to 3,817 pixels tall.
`manifests/roi_dicom_checksums.csv` records the selected abnormality and every
DICOM object (size, MD5, SHA-256); `manifests/roi_checksums.csv` records which
object is the crop and which the mask, `csv_order_swapped`
(`yes`, `no` or `undetermined`), the IDC series descriptions, and the PNG file
and pixel SHA-256. The crops are frozen with the `prereg-v1` tag, not with
`splits-v1`.

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
uv run python data/download.py roi        # ROI crops and masks, about 10 GB
uv run python data/preprocess.py --roi    # crop PNGs, verified against roi_checksums.csv
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
| `manifests/roi_dicom_checksums.csv` | per case: selected abnormality, its crop and mask DICOM objects with size, MD5, SHA-256 |
| `manifests/roi_checksums.csv` | per case: crop and mask object, swap status, IDC descriptions, crop PNG size and SHA-256s |
| `manifests/idc_viewer.csv` | per test case: study and series UIDs of the full image and of the ROI crop series, for links to the IDC viewer (`data/idc_viewer.py`, idc-index metadata only) |

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
