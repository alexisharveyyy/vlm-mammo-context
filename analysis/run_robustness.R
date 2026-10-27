# Phase 7 robustness checks (docs/ROBUSTNESS.md).
#
#   Rscript analysis/run_robustness.R [--runs runs] [--robustness runs/robustness]
#       [--variants configs/robustness.yaml] [--manifests data/manifests]
#       [--out reports] [--resamples 10000] [--final]
#
# Run from the repository root. Reads the committed study outputs and the
# variant outputs under <robustness>/<variant>/. Writes <out>/robustness.md
# and <out>/robustness/*.csv. --final stops before anything is computed or
# written unless the commit is known.

args <- commandArgs(trailingOnly = TRUE)
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])))
if (!nzchar(Sys.getenv("RENV_PROJECT"))) {
  Sys.setenv(RENV_PROJECT = here)
  source(file.path(here, "renv", "activate.R"))
}
for (f in c("cli.R", "io.R", "stats.R", "outcomes.R", "report.R", "robustness.R")) {
  source(file.path(here, "R", f))
}

opt <- parse_options(args, list(
  runs = "runs", robustness = "runs/robustness", variants = "configs/robustness.yaml",
  manifests = "data/manifests", out = "reports", resamples = "10000"
))
resamples <- as.integer(opt$resamples)
commit <- current_commit(opt$final)

calls <- read_runs(opt$runs)
r <- robustness(calls, read_cases(opt$manifests), opt$robustness, opt$variants, resamples)

tables <- file.path(opt$out, "robustness")
dir.create(tables, recursive = TRUE, showWarnings = FALSE)
for (name in c("primary", "checks", "agreement", "strict_counts", "sampled_agreement")) {
  utils::write.csv(r[[name]], file.path(tables, paste0(name, ".csv")), row.names = FALSE)
}
meta <- list(
  command = trimws(paste(c("Rscript analysis/run_robustness.R", args), collapse = " ")),
  commit = commit, r_version = as.character(getRversion()), resamples = resamples,
  warning = if (resamples != BOOTSTRAP_RESAMPLES) {
    sprintf("Development run: %d resamples instead of the planned %d.", resamples, BOOTSTRAP_RESAMPLES)
  }
)
writeLines(render_robustness(r, meta), file.path(opt$out, "robustness.md"), sep = "")
cat(sprintf(
  "%d checks (%d pending), %d agreement cells -> %s\n",
  nrow(r$checks), sum(grepl("^pending", r$checks$note)), nrow(r$agreement), opt$out
))
