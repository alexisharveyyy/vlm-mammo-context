# Phase 7 robustness checks (docs/ROBUSTNESS.md): R1 agreement across
# paraphrases, R2 position of the context sentence, R3 strict parser
# (sensitivity 2), R4 a second decoding setting. All are descriptive except
# R3, which repeats the primary tests with Holm within its own 12.

# The study's frozen strict rules (models/parse.py STRICT, parse_strict): the
# whole output is exactly these three lines, lowercase class word.
STRICT <- "\\A\\s*BI-RADS: ([0-6])\\s*\\n\\s*Assessment: (benign|malignant)\\s*\\n\\s*Confidence: (\\d{1,3})\\s*\\z"

strict_parse <- function(text) {
  out <- data.frame(ok = rep(FALSE, length(text)), malignant = NA)
  hit <- !is.na(text) & grepl(STRICT, text, perl = TRUE)
  if (any(hit)) {
    m <- regmatches(text[hit], regexec(STRICT, text[hit], perl = TRUE))
    conf <- as.integer(vapply(m, `[`, "", 4))
    ok <- conf <= 100
    out$ok[hit] <- ok
    out$malignant[hit] <- ifelse(ok, vapply(m, `[`, "", 3) == "malignant", NA)
  }
  out
}

# The calls with validity and answers under the strict rules (sensitivity 2).
strict_calls <- function(calls) {
  sp <- strict_parse(calls$raw_text)
  calls$valid <- !calls$errored & sp$ok
  calls$y <- ifelse(calls$valid, as.integer(sp$malignant), NA_integer_)
  calls$verbal <- ifelse(calls$valid, calls$verbal, NA_real_)
  calls
}

# Variant calls with the variant in the condition name ("colleague_benign@end").
read_variant <- function(robustness_dir, name, suffix) {
  dir <- file.path(robustness_dir, name)
  if (!dir.exists(dir)) {
    return(NULL)
  }
  calls <- read_runs(dir)
  if (is.null(calls) || nrow(calls) == 0) {
    return(NULL)
  }
  calls$condition <- paste0(calls$condition, "@", suffix)
  calls
}

load_variants <- function(path) yaml::read_yaml(path)$variants

primary_rows <- function(s, family = "primary", outcome = "malignant rate shift") {
  rows <- do.call(rbind, lapply(MODELS, function(m) {
    do.call(rbind, lapply(seq_len(nrow(HYPOTHESES)), function(h) {
      x <- paired_shift(s, family, outcome, m, "full", HYPOTHESES$condition[h], HYPOTHESES$reference[h])
      x$hypothesis <- HYPOTHESES$hypothesis[h]
      x
    }))
  }))
  sel <- !is.na(rows$p)
  rows$p_adjusted <- NA_real_
  rows$p_adjusted[sel] <- stats::p.adjust(rows$p[sel], "holm")
  rows
}

# R1: per cell, unanimity among cases with three valid answers, and Fleiss'
# kappa for the three paraphrases as raters.
fleiss_kappa <- function(y) {
  n <- ncol(y)
  pos <- rowSums(y)
  counts <- cbind(n - pos, pos)
  p_j <- colSums(counts) / (nrow(y) * n)
  p_i <- (rowSums(counts^2) - n) / (n * (n - 1))
  pe <- sum(p_j^2)
  if (nrow(y) == 0 || pe == 1) {
    return(NA_real_)
  }
  (mean(p_i) - pe) / (1 - pe)
}

agreement_table <- function(s) {
  do.call(rbind, lapply(sort(names(s$rows)), function(key) {
    cl <- cell(s, key)
    parts <- strsplit(key, "|", fixed = TRUE)[[1]]
    full <- rowSums(cl$valid) == 3
    y <- cl$y[full, , drop = FALSE]
    unanimous <- sum(rowSums(y) %in% c(0, 3))
    ci <- wilson(unanimous, nrow(y))
    data.frame(
      model = parts[1], image_kind = parts[2], condition = parts[3], answer_format = parts[4],
      cases_all_valid = nrow(y), unanimous = unanimous,
      unanimous_rate = if (nrow(y)) unanimous / nrow(y) else NA_real_,
      ci_low = ci[1], ci_high = ci[2], fleiss_kappa = fleiss_kappa(y),
      stringsAsFactors = FALSE
    )
  }))
}

# R1: each primary contrast from one paraphrase at a time.
paraphrase_rows <- function(s) {
  rows <- list()
  for (m in MODELS) {
    for (h in seq_len(nrow(HYPOTHESES))) {
      cond <- HYPOTHESES$condition[h]
      ref <- HYPOTHESES$reference[h]
      ka <- cell_key(m, "full", cond)
      kb <- cell_key(m, "full", ref)
      for (p in 1:3) {
        outcome <- paste0("malignant rate shift, paraphrase ", p, " only")
        contrast <- paste(cond, "vs", ref)
        missing <- c(ka, kb)[!c(complete(s, ka), complete(s, kb))]
        x <- if (length(missing)) {
          pending_row("robustness", outcome, m, "full", contrast, missing)
        } else {
          d <- cell(s, ka)$y[, p] - cell(s, kb)$y[, p]
          result_row("robustness", outcome, m, "full", contrast, mean(d, na.rm = TRUE),
            boot_mean(s$counts, d),
            n_cases = sum(!is.na(d)), test = FALSE,
            reference = mean(cell(s, kb)$y[!is.na(d), p])
          )
        }
        x$hypothesis <- HYPOTHESES$hypothesis[h]
        x$check <- "R1"
        rows[[length(rows) + 1]] <- x
      }
    }
  }
  do.call(rbind, rows)
}

# R2 and R4: the primary contrasts in a variant, and their difference from the
# study (variant minus study). Conditions in the variant carry "@suffix";
# reference conditions the variant did not rerun come from the study. Only
# hypotheses whose condition the variant reran are included (H1 and H2 in the
# scope of configs/robustness.yaml).
variant_rows <- function(s, variant, suffix, check, label, models) {
  rows <- list()
  rerun <- variant$conditions
  name <- function(cond) if (cond %in% rerun) paste0(cond, "@", suffix) else cond
  for (m in MODELS) {
    if (!m %in% models) next
    for (h in seq_len(nrow(HYPOTHESES))) {
      cond <- HYPOTHESES$condition[h]
      ref <- HYPOTHESES$reference[h]
      if (!cond %in% rerun) next
      contrast <- paste(cond, "vs", ref)
      keys <- c(
        cell_key(m, "full", name(cond)), cell_key(m, "full", name(ref)),
        cell_key(m, "full", cond), cell_key(m, "full", ref)
      )
      missing <- keys[!vapply(keys, function(k) complete(s, k), logical(1))]
      if (length(missing)) {
        a <- pending_row("robustness", paste0("malignant rate shift, ", label), m, "full", contrast, missing)
        b <- pending_row("robustness", paste0("shift difference, ", label, " minus study"), m, "full", contrast, missing)
      } else {
        d_var <- case_value(s, keys[1]) - case_value(s, keys[2])
        d_std <- case_value(s, keys[3]) - case_value(s, keys[4])
        ref_var <- mean(case_value(s, keys[2])[!is.na(d_var)])
        ref_std <- mean(case_value(s, keys[4])[!is.na(d_std)])
        a <- result_row("robustness", paste0("malignant rate shift, ", label), m, "full", contrast,
          mean(d_var, na.rm = TRUE), boot_mean(s$counts, d_var),
          n_cases = sum(!is.na(d_var)), test = FALSE, reference = ref_var
        )
        # Reference rates of the variant and of the study.
        b <- result_row("robustness", paste0("shift difference, ", label, " minus study"), m, "full",
          contrast, mean(d_var, na.rm = TRUE) - mean(d_std, na.rm = TRUE),
          boot_mean(s$counts, d_var) - boot_mean(s$counts, d_std),
          n_cases = min(sum(!is.na(d_var)), sum(!is.na(d_std))), test = FALSE,
          reference = ref_var, reference_2 = ref_std
        )
      }
      for (x in list(a, b)) {
        x$hypothesis <- HYPOTHESES$hypothesis[h]
        x$check <- check
        rows[[length(rows) + 1]] <- x
      }
    }
  }
  if (length(rows)) do.call(rbind, rows)
}

# R4: share of (case, paraphrase) pairs whose variant answer equals the study answer.
answer_agreement <- function(s, variant, suffix, models) {
  do.call(rbind, lapply(intersect(MODELS, models), function(m) {
    do.call(rbind, lapply(variant$conditions, function(cond) {
      ka <- cell_key(m, "full", paste0(cond, "@", suffix))
      kb <- cell_key(m, "full", cond)
      if (!complete(s, ka) || !complete(s, kb)) {
        return(data.frame(
          model = m, condition = cond, pairs = NA_integer_, same = NA_integer_,
          rate = NA_real_, ci_low = NA_real_, ci_high = NA_real_, note = "pending",
          stringsAsFactors = FALSE
        ))
      }
      a <- cell(s, ka)
      b <- cell(s, kb)
      both <- a$valid & b$valid
      same <- sum(both & a$y == b$y, na.rm = TRUE)
      ci <- wilson(same, sum(both))
      data.frame(
        model = m, condition = cond, pairs = sum(both), same = same,
        rate = same / sum(both), ci_low = ci[1], ci_high = ci[2], note = "",
        stringsAsFactors = FALSE
      )
    }))
  }))
}

# R3 counts: valid answers per cell under the lenient and the strict rules.
strict_counts <- function(lenient, strict) {
  keys <- sort(names(lenient$rows))
  do.call(rbind, lapply(keys, function(key) {
    parts <- strsplit(key, "|", fixed = TRUE)[[1]]
    data.frame(
      model = parts[1], image_kind = parts[2], condition = parts[3], answer_format = parts[4],
      calls = sum(cell(lenient, key)$present),
      valid_lenient = sum(cell(lenient, key)$valid), valid_strict = sum(cell(strict, key)$valid),
      stringsAsFactors = FALSE
    )
  }))
}

# The reading rule of docs/ROBUSTNESS.md, applied to one check estimate.
reading <- function(primary, check) {
  if (is.na(primary$estimate) || grepl("^pending", check$note)) {
    return("pending")
  }
  # Runs complete but no case has valid answers in both conditions (for
  # example MedGemma under the strict parser, docs/ROBUSTNESS.md R3).
  if (is.na(check$estimate)) {
    return("no data")
  }
  covers0 <- check$ci_low <= 0 && check$ci_high >= 0
  if (isTRUE(primary$p_adjusted < 0.05)) {
    if (sign(check$estimate) == sign(primary$estimate) && !covers0) "robust" else "sensitive"
  } else {
    if (covers0) "unchanged" else "sensitive"
  }
}

with_reading <- function(rows, primary) {
  rows$reading <- vapply(seq_len(nrow(rows)), function(i) {
    if (grepl("difference", rows$outcome[i])) {
      return("")
    }
    p <- primary[primary$model == rows$model[i] & primary$hypothesis == rows$hypothesis[i], ]
    reading(p, rows[i, ])
  }, "")
  rows
}

robustness <- function(calls, cases, robustness_dir, variants_path, resamples) {
  variants <- load_variants(variants_path)
  extra <- list(
    read_variant(robustness_dir, "position_end", "end"),
    read_variant(robustness_dir, "sampled", "sampled")
  )
  s <- study(do.call(rbind, c(list(calls), extra)), cases, resamples)
  primary <- primary_rows(s)
  s2 <- study(strict_calls(calls), cases, resamples)
  r3 <- primary_rows(s2, "sensitivity", "malignant rate shift, strict parser (S2)")
  r3$check <- "R3"
  r1 <- paraphrase_rows(s)
  r2 <- variant_rows(s, variants$position_end, "end", "R2", "context at end",
    variants$position_end$models)
  r4 <- variant_rows(s, variants$sampled, "sampled", "R4", "sampled decoding",
    variants$sampled$models)
  columns <- c(
    "check", "family", "outcome", "model", "image_kind", "contrast", "hypothesis",
    "estimate", "ci_low", "ci_high", "p", "p_adjusted", "n_cases", "note",
    "reference", "reference_2"
  )
  checks <- do.call(rbind, lapply(Filter(Negate(is.null), list(r1, r2, r3, r4)), function(x) {
    if (!"p_adjusted" %in% names(x)) x$p_adjusted <- NA_real_
    x[, columns]
  }))
  checks <- with_reading(checks, primary)
  main_only <- s$calls[!grepl("@", s$calls$condition), ]
  list(
    primary = primary,
    checks = checks,
    agreement = agreement_table(study(main_only, cases, 1)),
    strict_counts = strict_counts(study(calls, cases, 1), study(strict_calls(calls), cases, 1)),
    sampled_agreement = answer_agreement(s, variants$sampled, "sampled", variants$sampled$models),
    variants = variants
  )
}
