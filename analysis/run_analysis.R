# Phase 6 analysis: the pre-specified tests and outcomes in docs/PREREGISTRATION.md.
#
#   Rscript analysis/run_analysis.R [--runs runs] [--manifests data/manifests]
#       [--out reports] [--resamples 10000] [--final]
#
# Run from the repository root. Reads only the committed run outputs and the
# manifests. Writes <out>/analysis.md, <out>/analysis/*.csv and
# <out>/figures/*.png.
#
# --final is for the reported analysis: it stops before anything is computed
# or written unless the commit of the code and outputs is known.

args <- commandArgs(trailingOnly = TRUE)
opt <- list(runs = "runs", manifests = "data/manifests", out = "reports", resamples = "10000")
final <- FALSE
i <- 1
while (i <= length(args)) {
  if (args[i] == "--final") {
    final <- TRUE
    i <- i + 1
    next
  }
  name <- sub("^--", "", args[i])
  if (!name %in% names(opt) || i == length(args)) stop("unknown or incomplete option ", args[i])
  opt[[name]] <- args[i + 1]
  i <- i + 2
}
resamples <- as.integer(opt$resamples)

commit <- suppressWarnings(tryCatch(
  system2("git", c("rev-parse", "HEAD"), stdout = TRUE, stderr = FALSE),
  error = function(e) character()
))
commit <- if (length(commit) == 1 && grepl("^[0-9a-f]{40}$", commit)) commit else "unknown"
if (final && commit == "unknown") {
  stop("--final: the commit is unknown (is git installed, and is this a git checkout?)", call. = FALSE)
}

here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])))
# Use the package versions pinned in analysis/renv.lock from any directory.
if (!nzchar(Sys.getenv("RENV_PROJECT"))) {
  Sys.setenv(RENV_PROJECT = here)
  source(file.path(here, "renv", "activate.R"))
}
for (f in c("io.R", "stats.R", "outcomes.R", "report.R")) source(file.path(here, "R", f))

calls <- read_runs(opt$runs)
cases <- read_cases(opt$manifests)
s <- study(calls, cases, resamples)

con <- contrasts(s)
cells <- cell_table(s)
flips <- flip_table(s)
syc <- sycophancy_rates(s)

tables <- file.path(opt$out, "analysis")
dir.create(tables, recursive = TRUE, showWarnings = FALSE)
utils::write.csv(con, file.path(tables, "contrasts.csv"), row.names = FALSE)
utils::write.csv(cells, file.path(tables, "cells.csv"), row.names = FALSE)
utils::write.csv(flips, file.path(tables, "flips.csv"), row.names = FALSE)
utils::write.csv(syc, file.path(tables, "sycophancy.csv"), row.names = FALSE)
figures <- write_figures(con, cells, syc, file.path(opt$out, "figures"))

command <- paste(c("Rscript analysis/run_analysis.R", args), collapse = " ")
meta <- list(
  command = trimws(command), commit = commit, r_version = as.character(getRversion()),
  resamples = resamples, calls = nrow(calls), runs = opt$runs,
  warning = if (resamples != BOOTSTRAP_RESAMPLES) {
    sprintf("Development run: %d resamples instead of the planned %d.", resamples, BOOTSTRAP_RESAMPLES)
  }
)
writeLines(render_report(con, cells, flips, syc, meta), file.path(opt$out, "analysis.md"), sep = "")
cat(sprintf(
  "%d calls, %d contrasts (%d pending), %d cells, %d figures -> %s\n",
  nrow(calls), nrow(con), sum(grepl("^pending", con$note)), nrow(cells), length(figures), opt$out
))
