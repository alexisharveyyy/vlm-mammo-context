# Phase 7 robustness checks (docs/ROBUSTNESS.md).
root <- Sys.getenv("REPO_ROOT")
runs <- Sys.getenv("SYNTHETIC_RUNS")
variants_path <- file.path(root, "configs", "robustness.yaml")

test_that("strict rules match models/parse.py parse_strict", {
  x <- strict_parse(c(
    "BI-RADS: 4\nAssessment: malignant\nConfidence: 80",
    "BI-RADS: 2\nAssessment: benign\nConfidence: 100\n",
    "BI-RADS: 2\nAssessment: Benign\nConfidence: 90",
    "BI-RADS: 2\nAssessment: probably benign\nConfidence: 90",
    "BI-RADS: 2\nAssessment: benign\nConfidence: 101",
    "BI-RADS: 7\nAssessment: benign\nConfidence: 50",
    "Sure. BI-RADS: 2\nAssessment: benign\nConfidence: 50",
    NA
  ))
  expect_equal(x$ok, c(TRUE, TRUE, FALSE, FALSE, FALSE, FALSE, FALSE, FALSE))
  expect_equal(x$malignant[1:2], c(TRUE, FALSE))
})

test_that("Fleiss' kappa matches a hand-computed value", {
  y <- rbind(c(1, 1, 1), c(0, 0, 0), c(1, 1, 0), c(0, 0, 1))
  expect_equal(fleiss_kappa(y), 1 / 3)
  expect_equal(fleiss_kappa(rbind(c(1, 1, 1), c(0, 0, 0))), 1)
  expect_true(is.na(fleiss_kappa(rbind(c(1, 1, 1), c(1, 1, 1)))))
})

test_that("strict counts on the committed T0 outputs match the Python parser", {
  calls <- read_runs(file.path(root, "runs"))
  calls <- calls[calls$condition == "neutral", ]
  cases <- read_cases(file.path(root, "data", "manifests"))
  counts <- strict_counts(study(calls, cases, 1), study(strict_calls(calls), cases, 1))
  by_model <- aggregate(cbind(valid_lenient, valid_strict) ~ model, counts, sum)
  # Counted with models.parse.parse_strict on the same outputs (docs/ROBUSTNESS.md, R3).
  expected <- data.frame(
    model = c("internvl3_5_8b", "medgemma_1_5_4b", "qwen3_vl_8b"),
    valid_lenient = c(9459, 10000, 7581), valid_strict = c(3977, 1, 7581)
  )
  expect_equal(by_model[order(by_model$model), ], expected, ignore_attr = TRUE)
})

test_that("the checks recover the planted variant effects", {
  skip_if(!nzchar(runs), "SYNTHETIC_RUNS not set")
  r <- robustness(read_runs(runs), read_cases(file.path(root, "data", "manifests")),
    file.path(runs, "robustness"), variants_path, resamples = 200
  )
  ch <- r$checks
  # R2 and R4 cover only the colleague contrasts (H1, H2) that the variants rerun.
  expect_equal(as.vector(table(ch$check)[c("R1", "R2", "R3", "R4")]), c(36, 12, 12, 4))
  expect_true(all(ch$hypothesis[ch$check %in% c("R2", "R4")] %in% c("H1", "H2")))
  expect_false(any(grepl("^pending", ch$note)))
  # position_end scales the context effects by 1.25.
  diff <- ch[ch$check == "R2" & grepl("difference", ch$outcome), ]
  expect_true(all(diff$estimate[diff$hypothesis == "H1"] > 0))
  expect_true(all(diff$estimate[diff$hypothesis == "H2"] < 0))
  # sampled runs only for the models in configs/robustness.yaml.
  expect_equal(unique(ch$model[ch$check == "R4"]), r$variants$sampled$models)
  expect_true(all(r$sampled_agreement$rate < 1 & r$sampled_agreement$rate > 0.5))
  # The strict parser drops the capitalized answers (20% planted).
  s2 <- ch[ch$check == "R3", ]
  expect_true(all(s2$n_cases <= 500) && all(s2$estimate * r$primary$estimate > 0))
  expect_equal(s2$p_adjusted, stats::p.adjust(s2$p, "holm"))
  expect_true(all(r$strict_counts$valid_strict < r$strict_counts$valid_lenient))
  # One-paraphrase estimates keep the sign of the colleague effects.
  r1 <- ch[ch$check == "R1" & ch$hypothesis %in% c("H1", "H2"), ]
  expect_true(all(sign(r1$estimate) == ifelse(r1$hypothesis == "H1", 1, -1)))
  expect_true(all(r$agreement$fleiss_kappa <= 1, na.rm = TRUE))
  expect_true(all(ch$reading[!grepl("difference", ch$outcome)] %in% c("robust", "unchanged", "sensitive")))
})

test_that("checks without their runs are pending, not errors", {
  skip_if(!nzchar(runs), "SYNTHETIC_RUNS not set")
  calls <- read_runs(runs)
  calls <- calls[calls$condition %in% c("neutral", "colleague_malignant"), ]
  r <- robustness(calls, read_cases(file.path(root, "data", "manifests")),
    file.path(tempdir(), "no_variants"), variants_path, resamples = 10
  )
  ch <- r$checks
  expect_true(all(grepl("^pending", ch$note[ch$check %in% c("R2", "R4")])))
  expect_true(all(ch$reading[ch$check %in% c("R2", "R4") & !grepl("difference", ch$outcome)] == "pending"))
  expect_true(all(r$sampled_agreement$note == "pending"))
})

test_that("readings follow the rule in docs/ROBUSTNESS.md", {
  sig <- data.frame(estimate = 0.2, p_adjusted = 0.01)
  ns <- data.frame(estimate = 0.01, p_adjusted = 0.4)
  row <- function(est, lo, hi, note = "") data.frame(estimate = est, ci_low = lo, ci_high = hi, note = note)
  expect_equal(reading(sig, row(0.15, 0.05, 0.25)), "robust")
  expect_equal(reading(sig, row(0.15, -0.01, 0.25)), "sensitive")
  expect_equal(reading(sig, row(-0.1, -0.2, -0.05)), "sensitive")
  expect_equal(reading(ns, row(0.02, -0.03, 0.07)), "unchanged")
  expect_equal(reading(ns, row(0.1, 0.05, 0.15)), "sensitive")
  expect_equal(reading(sig, row(NA, NA, NA, "0 of 500 cases")), "no data")
  expect_equal(reading(sig, row(NA, NA, NA, "pending: x incomplete")), "pending")
})
