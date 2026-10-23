"""Parse a model answer into BI-RADS, benign/malignant and confidence.

Every prompt asks for exactly this format:

    BI-RADS: <0-6>
    Assessment: <benign or malignant>
    Confidence: <0-100>

Two rule sets:
  strict   the three labelled lines, in order, nothing else but whitespace
  lenient  each labelled field found anywhere in the text (first match wins),
           tolerating case, markdown emphasis, "BIRADS", "category", a "%"
           sign and surrounding prose

The lenient rules are the default; strict is used for the Phase 7 parser
sensitivity analysis. A field that cannot be read is None and is named in
`errors`. Nothing is guessed: an assessment that names both classes, or a
number out of range, is a failure.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

FORMAT_INSTRUCTION = (
    "Answer in exactly this format and nothing else:\n"
    "BI-RADS: <a number from 0 to 6>\n"
    "Assessment: <benign or malignant>\n"
    "Confidence: <a number from 0 to 100>"
)

STRICT = re.compile(
    r"\A\s*BI-RADS: ([0-6])\s*\n\s*Assessment: (benign|malignant)\s*\n"
    r"\s*Confidence: (\d{1,3})\s*\Z"
)

# Markdown emphasis and similar decoration are removed before lenient matching.
DECORATION = re.compile(r"[*_`#]")
BIRADS = re.compile(r"\bBI-?RADS\b\s*(?:assessment|category)?\s*[:=\-]?\s*(\d+)", re.IGNORECASE)
ASSESSMENT = re.compile(r"\bassessment\s*[:=\-]\s*([^\n]*)", re.IGNORECASE)
CLASS_WORD = re.compile(r"\b(benign|malignant)\b", re.IGNORECASE)
CONFIDENCE = re.compile(r"\bconfidence\s*[:=\-]?\s*(\d+(?:\.\d+)?)\s*%?", re.IGNORECASE)


@dataclass
class Parsed:
    birads: int | None = None
    malignant: bool | None = None
    confidence: float | None = None
    rules: str = "lenient"
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def parse_strict(text: str) -> Parsed:
    m = STRICT.match(text)
    if not m:
        return Parsed(rules="strict", errors=["format"])
    confidence = int(m.group(3))
    if confidence > 100:
        return Parsed(rules="strict", errors=["confidence_range"])
    return Parsed(int(m.group(1)), m.group(2) == "malignant", float(confidence), "strict")


def parse_lenient(text: str) -> Parsed:
    clean = DECORATION.sub("", text)
    out = Parsed(rules="lenient")

    m = BIRADS.search(clean)
    if not m:
        out.errors.append("birads_missing")
    elif not 0 <= int(m.group(1)) <= 6:
        out.errors.append("birads_range")
    else:
        out.birads = int(m.group(1))

    m = ASSESSMENT.search(clean)
    words = {w.lower() for w in CLASS_WORD.findall(m.group(1))} if m else set()
    if not m:
        out.errors.append("assessment_missing")
    elif len(words) != 1:
        out.errors.append("assessment_ambiguous" if words else "assessment_unreadable")
    else:
        out.malignant = words == {"malignant"}

    m = CONFIDENCE.search(clean)
    if not m:
        out.errors.append("confidence_missing")
    elif not 0 <= float(m.group(1)) <= 100:
        out.errors.append("confidence_range")
    else:
        out.confidence = float(m.group(1))
    return out


def parse(text: str, rules: str = "lenient") -> Parsed:
    if rules == "strict":
        return parse_strict(text)
    if rules == "lenient":
        return parse_lenient(text)
    raise ValueError(f"unknown rules: {rules}")


def log_failure(path: Path, record: dict, parsed: Parsed, raw_text: str) -> None:
    """Append one parse failure, with the raw text, to a JSON lines file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {**record, "rules": parsed.rules, "errors": parsed.errors, "raw_text": raw_text}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def as_dict(parsed: Parsed) -> dict:
    return {**asdict(parsed), "ok": parsed.ok}
