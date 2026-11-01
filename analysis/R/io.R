# Read the committed run outputs and the test-set manifests.
#
# Only the fields the analysis needs are kept. Records outside the test split
# are dropped. Nothing here changes a value: parse results are taken as
# recorded by models/parse.py (lenient rules).

MODELS <- c("qwen3_vl_8b", "medgemma_1_5_4b", "internvl3_5_8b")
KINDS <- c("full", "roi", "no_image", "blank_full", "blank_roi")
CONDITIONS <- c(
  "neutral", "age_42", "age_68", "history_yes", "history_no", "combined",
  "colleague_benign", "colleague_malignant", "irrelevant"
)

field <- function(df, name, cast) {
  if (name %in% names(df)) cast(df[[name]]) else cast(rep(NA, nrow(df)))
}

read_run_file <- function(path) {
  df <- jsonlite::stream_in(file(path), verbose = FALSE, simplifyVector = TRUE)
  if (nrow(df) == 0) {
    return(NULL)
  }
  parse_ok <- if (is.data.frame(df$parse) && "ok" %in% names(df$parse)) {
    as.logical(df$parse$ok)
  } else {
    rep(NA, nrow(df))
  }
  data.frame(
    split = field(df, "split", as.character),
    model = field(df, "model", as.character),
    image_kind = field(df, "image_kind", as.character),
    condition = field(df, "condition", as.character),
    paraphrase = field(df, "paraphrase", as.integer),
    answer_format = field(df, "answer_format", as.character),
    case_id = field(df, "case_id", as.character),
    raw_text = field(df, "raw_text", as.character),
    malignant = field(df, "malignant", as.logical),
    confidence = field(df, "confidence", as.numeric),
    birads = field(df, "birads", as.integer),
    p_malignant = field(df, "p_malignant", as.numeric),
    class_mass = field(df, "class_mass", as.numeric),
    error = field(df, "error", as.character),
    parse_ok = !is.na(parse_ok) & parse_ok,
    stringsAsFactors = FALSE
  )
}

# All call records under runs_dir/<model>/<kind>/<condition>/p<k>[_plain].jsonl.
read_runs <- function(runs_dir, models = MODELS) {
  paths <- unlist(lapply(models, function(m) {
    Sys.glob(file.path(runs_dir, m, "*", "*", "p[123]*.jsonl"))
  }))
  calls <- do.call(rbind, lapply(paths, read_run_file))
  calls <- calls[calls$split == "test", ]
  calls$errored <- !is.na(calls$error)
  calls$abstained <- mapply(is_abstention, calls$raw_text, calls$parse_ok)
  calls$valid <- !calls$errored & calls$parse_ok & !is.na(calls$malignant)
  calls$y <- ifelse(calls$valid, as.integer(calls$malignant), NA_integer_)
  calls$verbal <- ifelse(
    calls$valid & !is.na(calls$confidence),
    ifelse(calls$malignant, calls$confidence / 100, 1 - calls$confidence / 100),
    NA_real_
  )
  rownames(calls) <- NULL
  calls
}

# Unparsed, with an assessment line that names neither class (plan 5.2 item 8).
# The same rule as is_abstention in eval/baseline.py.
is_abstention <- function(text, parse_ok) {
  if (isTRUE(parse_ok) || is.na(text)) {
    return(FALSE)
  }
  text <- gsub("[*_`#]", "", text)
  m <- regmatches(text, regexec("(?i)\\bassessment[ \t]*[:=-][ \t]*([^\n]*)", text, perl = TRUE))[[1]]
  if (length(m) < 2) {
    return(FALSE)
  }
  value <- trimws(m[2])
  nzchar(value) && !grepl("(?i)\\b(benign|malignant)\\b", value, perl = TRUE)
}

# Test cases in manifest order, with the answer-order offset.
read_cases <- function(manifests_dir) {
  cases <- utils::read.csv(file.path(manifests_dir, "test.csv"), colClasses = "character")
  offsets <- utils::read.csv(file.path(manifests_dir, "answer_order.csv"), colClasses = "character")
  cases$answer_order_offset <- as.integer(offsets$answer_order_offset[
    match(cases$case_id, offsets$case_id)
  ])
  cases$truth <- cases$label == "malignant"
  cases
}

# The option listed first in paraphrase p (models/prompts.py answer_order).
first_listed <- function(offset, paraphrase) {
  ifelse((offset + paraphrase) %% 2 == 1, "benign", "malignant")
}
