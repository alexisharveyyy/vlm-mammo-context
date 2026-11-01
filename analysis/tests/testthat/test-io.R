test_that("abstention rule matches eval/baseline.py", {
  expect_true(is_abstention("BI-RADS: 0\nAssessment: indeterminate\nConfidence: 50", FALSE))
  expect_true(is_abstention("BI-RADS: 0\n**Assessment:** None\nConfidence: 0", FALSE))
  expect_false(is_abstention("BI-RADS: 2\nAssessment: benign\nConfidence: 80", TRUE))
  expect_false(is_abstention("I cannot interpret medical images.", FALSE))
  expect_false(is_abstention("Assessment:\nConfidence: 50", FALSE))
  expect_false(is_abstention(NA_character_, FALSE))
})

test_that("answer order matches models/prompts.py", {
  expect_equal(first_listed(0, 1), "benign")
  expect_equal(first_listed(0, 2), "malignant")
  expect_equal(first_listed(1, 1), "malignant")
  expect_equal(first_listed(c(0, 1), 3), c("benign", "malignant"))
})

test_that("test cases load in manifest order with answer-order offsets", {
  cases <- read_cases(file.path(Sys.getenv("REPO_ROOT"), "data", "manifests"))
  expect_equal(nrow(cases), 500)
  expect_false(anyNA(cases$answer_order_offset))
  expect_equal(sum(cases$truth), 250)
})
