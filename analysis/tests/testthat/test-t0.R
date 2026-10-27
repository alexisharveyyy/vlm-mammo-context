# The committed tier T0 outputs against the Phase 4 report (eval/baseline.py).
root <- Sys.getenv("REPO_ROOT")
baseline_path <- file.path(root, "reports", "baseline.json")

test_that("T0 cells agree with reports/baseline.json", {
  skip_if_not(file.exists(baseline_path))
  # Python writes NaN, which strict JSON does not allow.
  text <- gsub("\\bNaN\\b", "null", paste(readLines(baseline_path), collapse = "\n"))
  base <- jsonlite::fromJSON(text, simplifyVector = FALSE)$results
  calls <- read_runs(file.path(root, "runs"))
  calls <- calls[calls$condition == "neutral", ]
  s <- study(calls, read_cases(file.path(root, "data", "manifests")), resamples = 10)
  for (key in names(base)) {
    parts <- strsplit(key, "/")[[1]]
    b <- base[[key]]
    x <- cell_summary(s, cell_key(parts[1], parts[2], "neutral", parts[3]))
    expect_equal(x$calls, b$calls, info = key)
    expect_equal(x$errors, b$errors, info = key)
    expect_equal(x$abstentions, b$abstentions, info = key)
    expect_equal(x$parse_failures, b$parse_failures, info = key)
    expect_equal(x$accuracy, as.numeric(b$accuracy), tolerance = 1e-12, info = key)
    expect_equal(x$malignant_rate, as.numeric(b$malignant_rate), tolerance = 1e-12, info = key)
    # The baseline averages p_malignant over every call without a run error;
    # the plan (section 5) averages over valid answers. They agree when every
    # call is valid.
    if (x$valid == x$calls) {
      expect_equal(x$auroc, as.numeric(b$auroc), tolerance = 1e-12, info = key)
      expect_equal(x$brier, as.numeric(b$brier), tolerance = 1e-12, info = key)
      expect_equal(x$ece, as.numeric(b$ece), tolerance = 1e-12, info = key)
    }
  }
})
