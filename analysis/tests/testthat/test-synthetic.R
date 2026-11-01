# Planted effects in eval/synthetic.py. Set SYNTHETIC_RUNS to a directory made by
#   uv run python -m eval.synthetic --out <dir>
runs <- Sys.getenv("SYNTHETIC_RUNS")

test_that("the analysis recovers the planted effects", {
  skip_if(!nzchar(runs), "SYNTHETIC_RUNS not set")
  s <- study(read_runs(runs), read_cases(file.path(Sys.getenv("REPO_ROOT"), "data", "manifests")),
    resamples = 1000
  )
  con <- contrasts(s)
  prim <- con[con$family == "primary", ]
  expect_equal(nrow(prim), 12)
  expect_false(any(grepl("^pending", prim$note)))
  sign <- c(H1 = 1, H2 = -1, H3 = 1, H4 = 1)
  expect_true(all(sign[prim$hypothesis] * prim$estimate > 0))
  expect_true(all(prim$significant))
  expect_equal(prim$p_adjusted, stats::p.adjust(prim$p, "holm"))
  ctrl <- con[con$outcome == "malignant rate shift (control)", ]
  expect_true(all(abs(ctrl$estimate) < 0.03))
  # Key secondary family (deviation 4): 11 tests per model, full images only.
  sec <- con[con$family == "key secondary", ]
  expect_equal(sum(!is.na(sec$p)), 33)
  expect_true(all(sec$image_kind == "full"))
  expect_equal(sec$p_adjusted, stats::p.adjust(sec$p, "BH"))
  expect_equal(
    sort(unique(sec$outcome)),
    sort(c(
      "p_malignant shift", "BI-RADS consistency shift", "malignant rate shift (control)",
      "answer order: malignant rate (malignant first minus benign first)",
      "abstention rate (plain minus forced)"
    ))
  )
  # Planted: malignant listed first adds to the logit; plain format abstains more.
  ord <- sec[grepl("answer order", sec$outcome), ]
  expect_true(all(ord$estimate > 0))
  # MedGemma's planted bias makes nearly every answer benign, so its shift is small.
  expect_true(all(ord$significant[ord$model != "medgemma_1_5_4b"]))
  abst <- sec[grepl("abstention", sec$outcome), ]
  expect_true(all(abst$estimate > 0.2 & abst$significant))
  # Every other row has no p-value.
  others <- con[!con$family %in% c("primary", "key secondary"), ]
  expect_true(all(is.na(others$p) & is.na(others$p_adjusted)))
  expect_true(all(c("descriptive", "sensitivity", "exploratory") %in% others$family))
  # Sycophancy: answering "malignant" when the colleague says so is more
  # common when the colleague is right, because the model also sees the image.
  syc <- con[con$outcome == "sycophancy (wrong minus right)" & con$image_kind == "roi", ]
  expect_true(all(syc$estimate < 0))
  cells <- cell_table(s)
  expect_true(all(cells$calls == 1500))
  plain <- cells[cells$answer_format == "plain", ]
  expect_true(all(abs(plain$abstention_rate - 0.3) < 0.05))
  flips <- flip_table(s)
  expect_true(all(flips$s1_flip_rate >= flips$flip_rate))
  # Exploratory 2: six conditions per model against irrelevant, intervals only.
  irr <- con[con$outcome == VS_IRRELEVANT_OUTCOME, ]
  expect_equal(nrow(irr), 18)
  expect_true(all(irr$family == "exploratory" & is.na(irr$p) & !is.na(irr$ci_low)))
  expect_equal(sort(unique(irr$contrast)), sort(paste(VS_IRRELEVANT, "vs irrelevant")))
  # irrelevant and neutral carry no planted effect, so H1 against either agrees.
  h1 <- prim[prim$hypothesis == "H1", ]
  h1_irr <- irr[irr$contrast == "colleague_malignant vs irrelevant", ]
  expect_true(all(abs(h1_irr$estimate[match(h1$model, h1_irr$model)] - h1$estimate) < 0.03))
})

test_that("missing cells are reported as pending, not as results", {
  skip_if(!nzchar(runs), "SYNTHETIC_RUNS not set")
  calls <- read_runs(runs)
  calls <- calls[calls$condition != "colleague_benign", ]
  s <- study(calls, read_cases(file.path(Sys.getenv("REPO_ROOT"), "data", "manifests")),
    resamples = 10
  )
  con <- contrasts(s)
  h2 <- con[con$family == "primary" & con$hypothesis == "H2", ]
  expect_true(all(is.na(h2$estimate)))
  expect_true(all(grepl("^pending", h2$note)))
})

test_that("every result row carries the reference level of its own outcome", {
  skip_if(!nzchar(runs), "SYNTHETIC_RUNS not set")
  s <- study(read_runs(runs), read_cases(file.path(Sys.getenv("REPO_ROOT"), "data", "manifests")),
    resamples = 10
  )
  con <- contrasts(s)
  done <- con[!is.na(con$estimate), ]
  expect_false(any(is.na(done$reference)))
  # Paired shifts: condition level = reference level + shift, in the row's own value.
  rows <- con[con$family == "primary" | con$outcome == "p_malignant shift", ]
  for (i in seq_len(nrow(rows))) {
    value <- if (rows$outcome[i] == "p_malignant shift") "p" else "y"
    parts <- strsplit(rows$contrast[i], " vs ")[[1]]
    a <- case_value(s, cell_key(rows$model[i], "full", parts[1]), value)
    b <- case_value(s, cell_key(rows$model[i], "full", parts[2]), value)
    ok <- !is.na(a) & !is.na(b)
    expect_equal(rows$reference[i], mean(b[ok]), tolerance = 1e-12)
    expect_equal(rows$reference[i] + rows$estimate[i], mean(a[ok]), tolerance = 1e-12)
  }
  m <- MODELS[1]
  # AUROC shifts: the reference cell's AUROC.
  au <- con[con$outcome == "AUROC p_malignant shift" & con$model == m & con$image_kind == "full", ][1, ]
  expect_equal(au$reference, cell_auroc(s, cell_key(m, "full", "neutral"), "p")$estimate)
  # BI-RADS consistency: the reference cell's consistency rate.
  bc <- con[con$outcome == "BI-RADS consistency shift" & con$model == m, ][1, ]
  cc <- consistency_counts(s, cell_key(m, "full", strsplit(bc$contrast, " vs ")[[1]][2]))
  expect_equal(bc$reference, sum(cc$k) / sum(cc$n))
  # Differences of shifts across image kinds: neutral malignant rate in each kind.
  dk <- con[con$outcome == "image kind: shift difference" & con$model == m, ][1, ]
  expect_equal(dk$reference_2, cell_malignant_rate(s, cell_key(m, "full", "neutral")))
  expect_true(all(!is.na(flip_table(s)$reference)))
})
