# Tables, figures and the Markdown report.

fmt_num <- function(x, digits = 3) ifelse(is.na(x), "n/a", formatC(x, format = "f", digits = digits))
fmt_pct <- function(x) ifelse(is.na(x), "n/a", paste0(formatC(100 * x, format = "f", digits = 1), "%"))
fmt_ci <- function(est, lo, hi, pct = FALSE) {
  f <- function(x) ifelse(rep_len(pct, length(x)), fmt_pct(x), fmt_num(x))
  ifelse(is.na(lo), f(est), paste0(f(est), " (", f(lo), " to ", f(hi), ")"))
}
fmt_p <- function(p) {
  ifelse(is.na(p), "n/a", ifelse(p < 0.001, "<0.001", formatC(p, format = "f", digits = 3)))
}

# Smallest Holm-adjusted p over m tests: with the conservative tie rule the
# smallest bootstrap p is 2 / (resamples + 1) (stats.R, bootstrap_p).
holm_floor <- function(resamples, m = 12) m * 2 / (resamples + 1)

# Holm-adjusted p-values at that floor are shown as "p < x", with x the floor
# rounded up to the next 0.0005 (p < 0.0025 for 10,000 resamples).
fmt_holm <- function(p, floor) {
  bound <- formatC(ceiling(floor / 5e-4 - 1e-9) * 5e-4, format = "fg")
  ifelse(!is.na(p) & p <= floor * (1 + 1e-9), paste("p <", bound), fmt_p(p))
}

holm_note <- function(resamples, m = 12) {
  paste0(
    "Holm-adjusted p-values at the resolution limit are shown as ",
    fmt_holm(0, holm_floor(resamples, m)), ": with ",
    formatC(resamples, format = "d", big.mark = ","), " resamples and the conservative tie ",
    "rule, the smallest possible bootstrap p-value is 2/", formatC(resamples + 1, format = "d", big.mark = ","),
    " (", formatC(2 / (resamples + 1), format = "fg", digits = 2), "), so the smallest ",
    "Holm-adjusted p-value over ", m, " tests is ", formatC(holm_floor(resamples, m), format = "fg", digits = 2),
    ". More resamples would be needed to resolve smaller p-values."
  )
}

# Reference malignant rate(s) of a row: "a" or, for two image kinds, "a / b".
fmt_reference <- function(r1, r2) {
  ifelse(is.na(r1), "n/a", ifelse(is.na(r2), fmt_pct(r1), paste(fmt_pct(r1), "/", fmt_pct(r2))))
}

REFERENCE_NOTE <- paste(
  "Reference rate: the malignant rate of the comparison, so floor and ceiling",
  "effects are visible. For paired shifts it is the reference condition's case-level",
  "rate over the same cases (condition rate = reference rate + malignant rate shift);",
  "for other rows it is the reference cell's rate over valid calls, or that of the",
  "single condition the row is about; for rows comparing two image kinds, neutral in",
  "each kind (first / second)."
)

md_table <- function(df) {
  df[] <- lapply(df, as.character)
  header <- paste0("| ", paste(names(df), collapse = " | "), " |")
  rule <- paste0("|", paste(rep("---", ncol(df)), collapse = "|"), "|")
  body <- apply(df, 1, function(r) paste0("| ", paste(r, collapse = " | "), " |"))
  c(header, rule, body)
}

contrast_table <- function(x, pct = TRUE, tests = TRUE, floor = NA_real_) {
  adjusted <- ifelse(x$adjustment == "holm", fmt_holm(x$p_adjusted, floor), fmt_p(x$p_adjusted))
  out <- data.frame(
    Model = x$model, Image = x$image_kind, Contrast = x$contrast,
    Estimate = fmt_ci(x$estimate, x$ci_low, x$ci_high, pct),
    `Reference rate` = fmt_reference(x$reference_rate, x$reference_rate_2),
    p = fmt_p(x$p), `Adjusted p` = adjusted, Cases = ifelse(is.na(x$n_cases), "", x$n_cases),
    Note = x$note, check.names = FALSE
  )
  if (tests) out else out[, setdiff(names(out), c("p", "Adjusted p"))]
}

write_figures <- function(con, cells, syc, fig_dir) {
  dir.create(fig_dir, recursive = TRUE, showWarnings = FALSE)
  written <- character()
  save <- function(plot, name, height) {
    path <- file.path(fig_dir, name)
    ggplot2::ggsave(path, plot, width = 7, height = height, dpi = 120)
    written <<- c(written, path)
  }
  forest <- function(x, xlab) {
    x <- x[!is.na(x$estimate), ]
    if (nrow(x) == 0) {
      return(NULL)
    }
    ggplot2::ggplot(x, ggplot2::aes(x = estimate, y = contrast, colour = model)) +
      ggplot2::geom_vline(xintercept = 0, colour = "grey60") +
      ggplot2::geom_pointrange(ggplot2::aes(xmin = ci_low, xmax = ci_high),
        position = ggplot2::position_dodge(width = 0.6)
      ) +
      ggplot2::labs(x = xlab, y = NULL, colour = "Model") +
      ggplot2::theme_minimal(base_size = 11)
  }
  p <- forest(con[con$family == "primary", ], "Malignant rate shift (95% CI), full image")
  if (!is.null(p)) save(p, "primary_shift.png", 4)
  p <- forest(con[con$outcome == "p_malignant shift", ], "p_malignant shift (95% CI), full image")
  if (!is.null(p)) save(p, "p_malignant_shift.png", 4)
  if (!is.null(syc) && nrow(syc)) {
    p <- ggplot2::ggplot(syc, ggplot2::aes(x = image_kind, y = rate, colour = colleague)) +
      ggplot2::geom_pointrange(ggplot2::aes(ymin = ci_low, ymax = ci_high),
        position = ggplot2::position_dodge(width = 0.5)
      ) +
      ggplot2::facet_grid(condition ~ model) +
      ggplot2::labs(x = NULL, y = "Rate of answering the colleague's opinion (95% CI)", colour = "Colleague") +
      ggplot2::theme_minimal(base_size = 10) +
      ggplot2::theme(axis.text.x = ggplot2::element_text(angle = 45, hjust = 1))
    save(p, "sycophancy.png", 5)
  }
  forced <- cells[cells$answer_format == "forced" & !is.na(cells$auroc), ]
  if (nrow(forced)) {
    p <- ggplot2::ggplot(forced, ggplot2::aes(x = auroc, y = condition, colour = image_kind)) +
      ggplot2::geom_vline(xintercept = 0.5, colour = "grey60") +
      ggplot2::geom_pointrange(ggplot2::aes(xmin = auroc_ci_low, xmax = auroc_ci_high),
        position = ggplot2::position_dodge(width = 0.6)
      ) +
      ggplot2::facet_wrap(~model) +
      ggplot2::labs(x = "AUROC of p_malignant (95% CI)", y = NULL, colour = "Image") +
      ggplot2::theme_minimal(base_size = 10)
    save(p, "auroc.png", 5)
  }
  written
}

render_report <- function(con, cells, flips, syc, meta) {
  out <- c(
    "# Phase 6 analysis (test set)",
    "",
    "This is a study of model behavior, not a diagnostic tool.",
    "",
    paste0(
      "Generated by `", meta$command, "` at commit `", meta$commit, "` with R ",
      meta$r_version, " (packages pinned in `analysis/renv.lock`). ",
      "Analysis plan: `docs/PREREGISTRATION.md` (tag `prereg-v1`); deviations in ",
      "`docs/DEVIATIONS.md`. Paired case bootstrap with ", meta$resamples,
      " resamples, seed ", BOOTSTRAP_SEED, "; rates over calls with Wilson 95% intervals; ",
      "AUROC with pROC. Input: ", meta$calls, " calls from `", meta$runs, "`."
    ),
    "",
    REFERENCE_NOTE,
    ""
  )
  if (!is.null(meta$warning)) out <- c(out, paste("**", meta$warning, "**"), "")
  prim <- con[con$family == "primary", ]
  out <- c(
    out, "## Primary outcome: malignant rate shift (Holm over 12 tests)", "",
    md_table(cbind(Hypothesis = prim$hypothesis,
      contrast_table(prim, floor = holm_floor(meta$resamples)))), "",
    holm_note(meta$resamples), ""
  )
  sec <- con[con$family == "key secondary", ]
  out <- c(out, paste0(
    "Key secondary family: ", sum(!is.na(sec$p)), " tests with p-values, Benjamini-Hochberg ",
    "(docs/DEVIATIONS.md, entry 4)."
  ), "")
  for (o in unique(sec$outcome)) {
    x <- sec[sec$outcome == o, ]
    out <- c(out, paste0("## Key secondary: ", o), "",
      md_table(contrast_table(x, pct = !grepl("AUROC|p_malignant", o))), "")
  }
  desc <- con[con$family == "descriptive", ]
  for (o in unique(desc$outcome)) {
    x <- desc[desc$outcome == o, ]
    out <- c(out, paste0("## Descriptive: ", o, " (estimates and 95% intervals, no tests)"), "",
      md_table(contrast_table(x, pct = !grepl("AUROC|p_malignant", o), tests = FALSE)), "")
  }
  if (!is.null(syc) && nrow(syc)) {
    out <- c(out, "## Sycophancy rates", "", md_table(data.frame(
      Model = syc$model, Image = syc$image_kind, Condition = syc$condition,
      Colleague = syc$colleague, Calls = syc$calls,
      Rate = fmt_ci(syc$rate, syc$ci_low, syc$ci_high, TRUE), check.names = FALSE
    )), "")
  }
  if (!is.null(flips) && nrow(flips)) {
    out <- c(out, "## Flip rate versus neutral", "",
      paste(
        "S1 counts every parse failure as a flip (plan 8, sensitivity 1).",
        "Neutral rate: the malignant rate of the neutral cell over valid calls."
      ), "",
      md_table(data.frame(
        Model = flips$model, Image = flips$image_kind, Condition = flips$condition,
        Pairs = flips$pairs, `Flip rate` = fmt_ci(flips$flip_rate, flips$ci_low, flips$ci_high, TRUE),
        `Neutral rate` = fmt_pct(flips$reference_rate),
        `S1 flip rate` = fmt_ci(flips$s1_flip_rate, flips$s1_ci_low, flips$s1_ci_high, TRUE),
        check.names = FALSE
      )), "")
  }
  out <- c(out, "## Cells", "", md_table(data.frame(
    Model = cells$model, Image = cells$image_kind, Condition = cells$condition,
    Format = cells$answer_format, Calls = cells$calls, Errors = cells$errors,
    Abstentions = fmt_ci(cells$abstention_rate, cells$abstention_ci_low, cells$abstention_ci_high, TRUE),
    `Parse failures` = fmt_ci(cells$parse_failure_rate, cells$parse_failure_ci_low, cells$parse_failure_ci_high, TRUE),
    `Malignant rate` = fmt_ci(cells$malignant_rate, cells$malignant_ci_low, cells$malignant_ci_high, TRUE),
    Accuracy = fmt_ci(cells$accuracy, cells$accuracy_ci_low, cells$accuracy_ci_high, TRUE),
    AUROC = fmt_ci(cells$auroc, cells$auroc_ci_low, cells$auroc_ci_high),
    Brier = fmt_num(cells$brier), ECE = fmt_num(cells$ece),
    `BI-RADS consistent` = fmt_ci(cells$birads_consistent_rate, cells$birads_consistent_ci_low, cells$birads_consistent_ci_high, TRUE),
    `Low mass` = fmt_pct(cells$low_mass_rate), check.names = FALSE
  )), "")
  irr <- con[con$outcome == VS_IRRELEVANT_OUTCOME, ]
  if (nrow(irr)) {
    out <- c(out, "## Exploratory 2: conditions against the irrelevant sentence", "",
      paste(
        "Exploratory, added after the results were known (docs/EXPLORATORY.md, entry 2;",
        "docs/DEVIATIONS.md, entry 9). Each H1 to H4 condition against `irrelevant`",
        "instead of its plan reference; same paired case bootstrap, no multiplicity",
        "correction, estimates and 95% intervals only."
      ), "",
      md_table(contrast_table(irr, tests = FALSE)), "")
  }
  for (fam in c("sensitivity", "exploratory")) {
    x <- con[con$family == fam & !is.na(con$estimate) & con$outcome != VS_IRRELEVANT_OUTCOME, ]
    if (nrow(x)) {
      label <- if (fam == "sensitivity") "Sensitivity analyses (unadjusted)" else "Exploratory (unadjusted, not part of the plan's tests)"
      out <- c(out, paste("##", label), "", md_table(data.frame(
        Outcome = x$outcome, Model = x$model, Image = x$image_kind, Contrast = x$contrast,
        Estimate = fmt_ci(x$estimate, x$ci_low, x$ci_high, !grepl("p_malignant", x$outcome)),
        `Reference rate` = fmt_reference(x$reference_rate, x$reference_rate_2),
        Cases = x$n_cases, check.names = FALSE
      )), "")
    }
  }
  pend <- con[grepl("^pending", con$note), ]
  out <- c(out, "## Pending", "")
  out <- c(out, if (nrow(pend)) paste0("- ", pend$family, ": ", pend$outcome, ", ", pend$model, ", ", pend$image_kind, ", ", pend$contrast, " (", pend$note, ")") else "None.")
  paste0(c(out, ""), collapse = "\n")
}

check_table <- function(x, tests = FALSE, floor = NA_real_) {
  out <- data.frame(
    Model = x$model, Hypothesis = x$hypothesis, Contrast = x$contrast,
    Estimate = fmt_ci(x$estimate, x$ci_low, x$ci_high, TRUE),
    `Reference rate` = fmt_reference(x$reference_rate, x$reference_rate_2),
    p = fmt_p(x$p), `Holm p` = fmt_holm(x$p_adjusted, floor),
    Cases = ifelse(is.na(x$n_cases), "", x$n_cases), Reading = x$reading, Note = x$note,
    check.names = FALSE
  )
  if (tests) out else out[, setdiff(names(out), c("p", "Holm p"))]
}

render_robustness <- function(r, meta) {
  ch <- r$checks
  section <- function(check, outcome_pattern, tests = FALSE) {
    x <- ch[ch$check == check & grepl(outcome_pattern, ch$outcome), ]
    if (nrow(x)) md_table(check_table(x, tests, holm_floor(meta$resamples))) else "None."
  }
  out <- c(
    "# Phase 7 robustness (test set)",
    "",
    "This is a study of model behavior, not a diagnostic tool.",
    "",
    paste0(
      "Generated by `", meta$command, "` at commit `", meta$commit, "` with R ", meta$r_version,
      ". Design: `docs/ROBUSTNESS.md`. Paired case bootstrap with ", meta$resamples,
      " resamples, seed ", BOOTSTRAP_SEED, ". Shifts are malignant-rate shifts on full images, ",
      "forced format. Reading (docs/ROBUSTNESS.md): robust = same sign as a significant primary ",
      "result and 95% interval excluding 0; unchanged = interval including 0 for a primary result ",
      "that is not significant; sensitive = anything else. Only R3 has p-values."
    ),
    "",
    paste(REFERENCE_NOTE, "In the difference rows, the variant's and the study's reference rates."),
    ""
  )
  if (!is.null(meta$warning)) out <- c(out, paste0("**", meta$warning, "**"), "")
  prim <- r$primary
  out <- c(out, "## Primary results (reference)", "", md_table(data.frame(
    Model = prim$model, Hypothesis = prim$hypothesis, Contrast = prim$contrast,
    Estimate = fmt_ci(prim$estimate, prim$ci_low, prim$ci_high, TRUE),
    `Reference rate` = fmt_reference(prim$reference_rate, prim$reference_rate_2),
    `Holm p` = fmt_holm(prim$p_adjusted, holm_floor(meta$resamples)), Note = prim$note,
    check.names = FALSE
  )), "", holm_note(meta$resamples), "")
  ag <- r$agreement
  out <- c(out, "## R1. Agreement across paraphrases", "",
    "Cases with three valid answers whose three answers agree, and Fleiss' kappa.", "",
    md_table(data.frame(
      Model = ag$model, Image = ag$image_kind, Condition = ag$condition, Format = ag$answer_format,
      Cases = ag$cases_all_valid,
      Unanimous = fmt_ci(ag$unanimous_rate, ag$ci_low, ag$ci_high, TRUE),
      Kappa = fmt_num(ag$fleiss_kappa), check.names = FALSE
    )), "",
    "Each primary contrast from one paraphrase at a time:", "",
    section("R1", "paraphrase"), "",
    "## R2. Context sentence after the task", "",
    section("R2", "^malignant rate shift"), "",
    "Difference from the study (end minus middle):", "",
    section("R2", "difference"), "",
    "## R3. Strict parser (sensitivity 2)", "",
    "The primary analysis with the frozen strict rules; Holm within these 12 tests.",
    "Holm-adjusted p-values at the resolution limit are shown as above.", "",
    section("R3", ".", tests = TRUE), "",
    "Valid answers under the lenient and strict rules:", "",
    md_table(data.frame(
      Model = r$strict_counts$model, Image = r$strict_counts$image_kind,
      Condition = r$strict_counts$condition, Format = r$strict_counts$answer_format,
      Calls = r$strict_counts$calls, Lenient = r$strict_counts$valid_lenient,
      Strict = r$strict_counts$valid_strict, check.names = FALSE
    )), "",
    "## R4. Sampled decoding", "",
    paste0("Models: ", paste(r$variants$sampled$models, collapse = ", "), "."), "",
    section("R4", "^malignant rate shift"), "",
    "Difference from the study (sampled minus greedy):", "",
    section("R4", "difference"), "",
    "Answers equal to the greedy answer, per condition:", ""
  )
  sa <- r$sampled_agreement
  out <- c(out, if (!is.null(sa) && nrow(sa)) {
    md_table(data.frame(
      Model = sa$model, Condition = sa$condition, Pairs = ifelse(is.na(sa$pairs), "", sa$pairs),
      Same = fmt_ci(sa$rate, sa$ci_low, sa$ci_high, TRUE), Note = sa$note, check.names = FALSE
    ))
  } else {
    "None."
  }, "")
  pend <- ch[grepl("^pending", ch$note), ]
  out <- c(out, "## Pending", "", if (nrow(pend)) {
    paste0("- ", pend$check, " ", pend$outcome, ", ", pend$model, ", ", pend$contrast)
  } else {
    "None."
  })
  paste0(c(out, ""), collapse = "\n")
}
