# Command line options and the commit check shared by the entry scripts.

# Options as --name value pairs over defaults, plus the --final switch.
parse_options <- function(args, defaults) {
  opt <- defaults
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
  opt$final <- final
  opt
}

# The checked-out commit, or "unknown". With final = TRUE an unknown commit stops the run.
current_commit <- function(final = FALSE) {
  commit <- suppressWarnings(tryCatch(
    system2("git", c("rev-parse", "HEAD"), stdout = TRUE, stderr = FALSE),
    error = function(e) character()
  ))
  commit <- if (length(commit) == 1 && grepl("^[0-9a-f]{40}$", commit)) commit else "unknown"
  if (final && commit == "unknown") {
    stop("--final: the commit is unknown (is git installed, and is this a git checkout?)", call. = FALSE)
  }
  commit
}
