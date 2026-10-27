# Statistics from docs/PREREGISTRATION.md, section 7.
#
# Contrasts use a paired bootstrap over case IDs: one set of resamples (seed
# 20261026) is drawn over all test cases and shared by every contrast, and a
# contrast is recomputed in each resample from the drawn cases that have valid
# values in both conditions.

BOOTSTRAP_SEED <- 20261026L
BOOTSTRAP_RESAMPLES <- 10000L

# Wilson score 95% interval for k successes in n trials.
wilson <- function(k, n, z = stats::qnorm(0.975)) {
  if (n == 0) {
    return(c(NA_real_, NA_real_))
  }
  p <- k / n
  denom <- 1 + z^2 / n
  centre <- (p + z^2 / (2 * n)) / denom
  half <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / denom
  c(max(0, centre - half), min(1, centre + half))
}

# Resample weights: row b counts how often each of the n cases was drawn in
# resample b. Draws are made resample by resample.
bootstrap_counts <- function(n, resamples = BOOTSTRAP_RESAMPLES, seed = BOOTSTRAP_SEED) {
  old <- RNGkind("Mersenne-Twister", "Inversion", "Rejection")
  on.exit(do.call(RNGkind, as.list(old)))
  set.seed(seed)
  idx <- matrix(sample.int(n, n * resamples, replace = TRUE), nrow = resamples, byrow = TRUE)
  counts <- matrix(0L, resamples, n)
  for (b in seq_len(resamples)) counts[b, ] <- tabulate(idx[b, ], nbins = n)
  counts
}

# Percentile interval (numpy's default linear interpolation, R type 7).
percentile_ci <- function(values) {
  values <- values[is.finite(values)]
  if (length(values) == 0) {
    return(c(NA_real_, NA_real_))
  }
  unname(stats::quantile(values, c(0.025, 0.975), type = 7))
}

# Two-sided bootstrap p-value (plan 7):
# min(1, 2 * (1 + #{resamples on the other side of 0 from the observed}) / (B + 1)).
# A resample exactly at 0 counts as the other side; an observed 0 gives p = 1.
bootstrap_p <- function(observed, values) {
  values <- values[is.finite(values)]
  if (!is.finite(observed) || observed == 0 || length(values) == 0) {
    return(if (is.finite(observed)) 1 else NA_real_)
  }
  other <- if (observed > 0) sum(values <= 0) else sum(values >= 0)
  min(1, 2 * (1 + other) / (length(values) + 1))
}

# Weighted mean of x over cases with non-missing x, for every resample.
boot_mean <- function(counts, x) {
  ok <- !is.na(x)
  num <- counts[, ok, drop = FALSE] %*% x[ok]
  den <- counts[, ok, drop = FALSE] %*% rep(1, sum(ok))
  as.vector(num / den)
}

# Ratio of sums (successes over trials) for every resample; rates over calls
# with cases as the resampled unit.
boot_ratio <- function(counts, k, n) {
  as.vector((counts %*% k) / (counts %*% n))
}

# AUROC (Mann-Whitney, ties count one half). Matches pROC with direction "<".
auroc <- function(scores, truth) {
  ok <- !is.na(scores) & !is.na(truth)
  scores <- scores[ok]
  truth <- as.logical(truth[ok])
  n_pos <- sum(truth)
  n_neg <- sum(!truth)
  if (n_pos == 0 || n_neg == 0) {
    return(NA_real_)
  }
  r <- rank(scores)
  (sum(r[truth]) - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)
}

auroc_proc <- function(scores, truth) {
  ok <- !is.na(scores) & !is.na(truth)
  if (length(unique(truth[ok])) < 2) {
    return(NA_real_)
  }
  roc <- pROC::roc(
    response = as.logical(truth[ok]), predictor = scores[ok],
    levels = c(FALSE, TRUE), direction = "<", quiet = TRUE
  )
  as.numeric(pROC::auc(roc))
}

# AUROC in every resample: with weights w, sum_ij w_i w_j [s_i > s_j + ties/2]
# over positive i and negative j, divided by the weighted pair count.
boot_auroc <- function(counts, scores, truth) {
  ok <- !is.na(scores) & !is.na(truth)
  pos <- which(ok & truth)
  neg <- which(ok & !truth)
  if (length(pos) == 0 || length(neg) == 0) {
    return(rep(NA_real_, nrow(counts)))
  }
  a <- outer(scores[pos], scores[neg], ">") + 0.5 * outer(scores[pos], scores[neg], "==")
  wp <- counts[, pos, drop = FALSE]
  wn <- counts[, neg, drop = FALSE]
  num <- rowSums((wp %*% a) * wn)
  den <- rowSums(wp) * rowSums(wn)
  ifelse(den > 0, num / den, NA_real_)
}

brier <- function(p, truth) {
  ok <- !is.na(p)
  mean((p[ok] - as.numeric(truth[ok]))^2)
}

# Expected calibration error, 10 equal-width bins on [0, 1].
ece <- function(p, truth, bins = 10L) {
  ok <- !is.na(p)
  p <- p[ok]
  truth <- as.numeric(truth[ok])
  if (length(p) == 0) {
    return(NA_real_)
  }
  b <- pmin(floor(p * bins), bins - 1)
  total <- 0
  for (k in unique(b)) {
    sel <- b == k
    total <- total + mean(sel) * abs(mean(p[sel]) - mean(truth[sel]))
  }
  total
}

# consistent, inconsistent or incomplete (BI-RADS 0); NA when not parsed.
birads_consistency <- function(birads, malignant) {
  out <- ifelse(
    malignant,
    ifelse(birads %in% 4:6, "consistent", "inconsistent"),
    ifelse(birads %in% 1:3, "consistent", "inconsistent")
  )
  out[!is.na(birads) & birads == 0] <- "incomplete"
  out[is.na(birads) | is.na(malignant)] <- NA_character_
  out
}
