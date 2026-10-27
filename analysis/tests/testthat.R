# Rscript analysis/tests/testthat.R (from the repository root or analysis/)
here <- dirname(normalizePath(sub("^--file=", "", grep("^--file=", commandArgs(), value = TRUE)[1])))
analysis <- dirname(here)
if (!nzchar(Sys.getenv("RENV_PROJECT"))) {
  Sys.setenv(RENV_PROJECT = analysis)
  source(file.path(analysis, "renv", "activate.R"))
}
for (f in c("io.R", "stats.R", "outcomes.R", "report.R")) source(file.path(analysis, "R", f))
Sys.setenv(REPO_ROOT = dirname(analysis))
result <- testthat::test_dir(file.path(here, "testthat"), reporter = "summary", stop_on_failure = TRUE)
