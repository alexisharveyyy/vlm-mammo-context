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
  sec <- con[con$family == "secondary" & !is.na(con$p), ]
  expect_equal(sec$p_adjusted, stats::p.adjust(sec$p, "BH"))
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
