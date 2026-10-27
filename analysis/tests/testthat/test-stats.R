test_that("wilson matches known values", {
  ci <- wilson(50, 100)
  expect_equal(ci, c(0.4038, 0.5962), tolerance = 1e-4)
  expect_equal(wilson(0, 10)[1], 0)
  expect_true(all(is.na(wilson(0, 0))))
})

test_that("auroc matches pROC and the pairwise definition", {
  set.seed(1)
  s <- sample(0:4, 60, replace = TRUE) + 0
  y <- sample(c(TRUE, FALSE), 60, replace = TRUE)
  pairwise <- mean(outer(s[y], s[!y], ">") + 0.5 * outer(s[y], s[!y], "=="))
  expect_equal(auroc(s, y), pairwise)
  expect_equal(auroc_proc(s, y), pairwise)
  expect_equal(auroc(c(0.1, 0.5, 0.5, 0.9), c(FALSE, FALSE, TRUE, TRUE)), 0.875)
  expect_true(is.na(auroc(c(1, 2), c(TRUE, TRUE))))
})

test_that("bootstrap helpers equal the plain statistic under unit weights", {
  set.seed(2)
  n <- 40
  s <- runif(n)
  y <- rep(c(TRUE, FALSE), n / 2)
  x <- ifelse(runif(n) < 0.1, NA, rnorm(n))
  k <- rpois(n, 2)
  m <- k + rpois(n, 2) + 1
  w <- matrix(1L, 2, n)
  expect_equal(boot_auroc(w, s, y), rep(auroc(s, y), 2))
  expect_equal(boot_mean(w, x), rep(mean(x, na.rm = TRUE), 2))
  expect_equal(boot_ratio(w, k, m), rep(sum(k) / sum(m), 2))
})

test_that("weighted bootstrap AUROC equals AUROC of the expanded resample", {
  set.seed(3)
  n <- 30
  s <- round(runif(n), 1)
  y <- rep(c(TRUE, FALSE), n / 2)
  counts <- bootstrap_counts(n, resamples = 5, seed = 7)
  for (b in 1:5) {
    idx <- rep(seq_len(n), counts[b, ])
    expect_equal(boot_auroc(counts, s, y)[b], auroc(s[idx], y[idx]))
  }
})

test_that("bootstrap counts are reproducible resamples of n cases", {
  a <- bootstrap_counts(50, resamples = 20)
  expect_identical(a, bootstrap_counts(50, resamples = 20))
  expect_true(all(rowSums(a) == 50))
  expect_false(identical(a, bootstrap_counts(50, resamples = 20, seed = 1)))
})

test_that("bootstrap p-value follows the plan's rule", {
  expect_equal(bootstrap_p(0.1, c(rep(0.2, 98), -0.1, 0)), 2 * 3 / 101)
  expect_equal(bootstrap_p(-0.1, rep(-0.2, 100)), 2 / 101)
  expect_equal(bootstrap_p(0, c(1, -1)), 1)
  expect_equal(bootstrap_p(0.1, rep(-1, 10)), 1)
})

test_that("percentile interval uses linear interpolation", {
  expect_equal(percentile_ci(0:100), c(2.5, 97.5))
})

test_that("calibration and BI-RADS consistency", {
  expect_equal(brier(c(1, 0), c(TRUE, FALSE)), 0)
  expect_equal(brier(c(0.5, 0.5), c(TRUE, FALSE)), 0.25)
  expect_equal(ece(c(0.9, 0.9, 0.1, 0.1), c(TRUE, TRUE, FALSE, FALSE)), 0.1)
  expect_equal(
    birads_consistency(c(4, 2, 3, 5, 0, NA), c(TRUE, TRUE, FALSE, FALSE, FALSE, TRUE)),
    c("consistent", "inconsistent", "consistent", "inconsistent", "incomplete", NA)
  )
})
