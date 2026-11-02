#!/bin/sh
# Phase 8 final audit over the whole history, before the repository is made
# public. Exits 1 on any finding.
#
#   sh scripts/final_audit.sh              # also checks GitHub (needs gh)
#   sh scripts/final_audit.sh --offline    # git history only
#
# Checks every commit and tag on every ref, and every file version ever
# committed:
#   1. AI attribution and assistant or vendor names in commit and tag
#      messages, file contents and file names;
#   2. every author, committer and tagger is the expected identity
#      (EXPECTED_IDENTITY, default "Alexis Harvey <alexis@harveyfamilia.com>");
#   3. images outside reports/figures/, DICOM and other medical image files;
#   4. files over 5 MB;
#   5. secrets (the patterns of scripts/audit.py);
#   6. em dashes and emojis;
#   7. result placeholders left in reports/FINAL_REPORT.md;
#   8. with gh: the same text checks on pull requests, issues, comments and
#      releases.
# Prints every finding and a count per check.
set -u
here="$(cd "$(dirname "$0")" && pwd)"
cd "$(git rev-parse --show-toplevel)" || exit 2
exec python3 - "$here" "$@" <<'PY'
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import PurePosixPath

sys.path.insert(0, sys.argv[1])
import audit  # noqa: E402  (scripts/audit.py: shared patterns)

OFFLINE = "--offline" in sys.argv[2:]
IDENTITY = __import__("os").environ.get(
    "EXPECTED_IDENTITY", "Alexis Harvey <alexis@harveyfamilia.com>"
)
# Built from pieces so this script does not match itself.
NAMES = re.compile("|".join(["cl" + "aude", "anthr" + "opic"]), re.IGNORECASE)
ATTRIBUTION = re.compile(
    "|".join([r"\bco-authored-by\b", r"\bgenerated with\b", "noreply@" + "anthr" + "opic"]),
    re.IGNORECASE,
)
PLACEHOLDER = "[[" + "PENDING"
# Documented exception to the names check: three historical lines of
# runs/run_log.jsonl (dev check, 2026-10-29, commit 1cfd31e) record an
# `--out` path under the macOS per-user temporary folder, and that folder's
# name contains one of the vendor names. It is a folder name, not
# attribution. The current run_log.jsonl writes the path as $TMPDIR; the
# history keeps the lines as committed. Only these exact lines (SHA-256 of
# the line without its newline) in that file are exempt.
NAMES_EXEMPT_FILE = "runs/run_log.jsonl"
NAMES_EXEMPT_LINES = {
    "1908fbefdad6c93ddc9aa4cb283c63861b44623c1135bdf59c384e9f9f806c9f",
    "738842679bbb7e7b9e64673185eae9510a3e4739f8975d3e8b52c6a8e895cfc8",
    "06ea6b6d0cd34bfaa79489df43bdc8e81d761b87e769eed982c7f7b2abe18ad3",
}
problems = Counter()
exempted = Counter()


def report(check, message):
    problems[check] += 1
    print(f"[{check}] {message}")


def git(*args, text=True):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=text).stdout


def check_text(check_where, text, path=None):
    if ATTRIBUTION.search(text):
        report("attribution", f"{check_where}: attribution line")
    lines = text.splitlines()
    for m in NAMES.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        if path == NAMES_EXEMPT_FILE:
            digest = hashlib.sha256(lines[line - 1].encode("utf-8")).hexdigest()
            if digest in NAMES_EXEMPT_LINES:
                exempted[f"{path}:{line}"] += 1
                continue
        report("names", f"{check_where}:{line}: mentions {m.group(0)!r}")
    for lineno, line in enumerate(text.splitlines(), 1):
        if audit.EM_DASH in line:
            report("em dash", f"{check_where}:{lineno}")
        if audit.EMOJI.search(line):
            report("emoji", f"{check_where}:{lineno}")
        for pattern in audit.SECRETS:
            if pattern.search(line):
                report("secrets", f"{check_where}:{lineno}: {pattern.pattern}")


# Commits: messages and identities.
for line in git("log", "--all", "--format=%H%x00%an <%ae>%x00%cn <%ce>").splitlines():
    sha, author, committer = line.split("\0")
    for role, who in (("author", author), ("committer", committer)):
        if who != IDENTITY:
            report("identity", f"commit {sha[:10]}: {role} {who}")
    check_text(f"commit {sha[:10]} message", git("log", "-1", "--format=%B", sha))

# Tags: messages and taggers of annotated tags.
for line in git(
    "for-each-ref", "refs/tags", "--format=%(refname:short)%00%(objecttype)%00%(taggername) %(taggeremail)"
).splitlines():
    tag, kind, tagger = line.split("\0")
    if kind == "tag":
        if tagger.strip() != IDENTITY:
            report("identity", f"tag {tag}: tagger {tagger}")
        check_text(f"tag {tag} message", git("tag", "-l", "--format=%(contents)", tag))

# Every file version in history, once per blob.
seen = {}
for line in git("rev-list", "--all", "--objects").splitlines():
    sha, _, path = line.partition(" ")
    if path:
        seen.setdefault(sha, set()).add(path)
batch = subprocess.run(
    ["git", "cat-file", "--batch-check=%(objectname) %(objecttype) %(objectsize)"],
    input="\n".join(seen), capture_output=True, text=True, check=True,
).stdout.splitlines()
blobs = {}
for line in batch:
    sha, kind, size = line.split()
    if kind == "blob":
        blobs[sha] = int(size)
paths = sorted({p for sha in blobs for p in seen[sha]})
for path in paths:
    if NAMES.search(path):
        report("names", f"file name {path}")
    suffix = "".join(PurePosixPath(path).suffixes[-2:]).lower()
    ext = PurePosixPath(path).suffix.lower()
    if ext in audit.MEDICAL_EXTENSIONS or suffix == ".nii.gz":
        report("medical images", path)
    if ext in audit.IMAGE_EXTENSIONS and not path.startswith(audit.IMAGE_ALLOWED_PREFIX):
        report("images", f"{path} (outside {audit.IMAGE_ALLOWED_PREFIX})")
for sha, size in sorted(blobs.items()):
    where = sorted(seen[sha])[0]
    if size > audit.MAX_BYTES:
        report("large files", f"{where} ({sha[:10]}): {size} bytes")
    data = git("cat-file", "blob", sha, text=False)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        continue
    for path in sorted(seen[sha]):
        if path == NAMES_EXEMPT_FILE:
            where = path
    check_text(f"{where} ({sha[:10]})", text, path=where)

# Placeholders left in the final report at HEAD.
try:
    report_text = git("show", "HEAD:reports/FINAL_REPORT.md")
except subprocess.CalledProcessError:
    report_text = ""
for lineno, line in enumerate(report_text.splitlines(), 1):
    if PLACEHOLDER in line:
        report("placeholders", f"reports/FINAL_REPORT.md:{lineno}")

# GitHub: pull requests, issues, comments and releases.
if OFFLINE:
    print("GitHub checks skipped (--offline)")
else:
    def gh(*args):
        out = subprocess.run(["gh", *args], capture_output=True, text=True)
        if out.returncode:
            report("github", f"gh {' '.join(args[:2])} failed: {out.stderr.strip()[:200]}")
            return []
        return json.loads(out.stdout or "[]")

    for kind in ("pr", "issue"):
        for item in gh(kind, "list", "--state", "all", "--limit", "1000", "--json", "number,title,body,comments"):
            where = f"{kind} #{item['number']}"
            check_text(f"{where} title", item.get("title") or "")
            check_text(f"{where} body", item.get("body") or "")
            for c in item.get("comments") or []:
                check_text(f"{where} comment", c.get("body") or "")
    for rel in gh("release", "list", "--limit", "1000", "--json", "tagName"):
        body = gh("release", "view", rel["tagName"], "--json", "name,body")
        check_text(f"release {rel['tagName']}", f"{body.get('name', '')}\n{body.get('body', '')}")

print()
checks = [
    "attribution", "names", "identity", "medical images", "images", "large files",
    "secrets", "em dash", "emoji", "placeholders", "github",
]
for check in checks:
    print(f"{check:15} {problems[check]}")
print(f"{'names exempt':15} {sum(exempted.values())} (documented run_log.jsonl lines)")
total = sum(problems.values())
print(f"final audit: {len(blobs)} file versions, {total} finding(s)")
sys.exit(1 if total else 0)
PY
