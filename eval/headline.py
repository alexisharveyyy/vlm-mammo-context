"""Headline chart for the README: malignant-answer rate by prompt and model.

    uv run python -m eval.headline

Reads reports/analysis/cells.csv (written by `Rscript analysis/run_analysis.R
--final`) and writes reports/figures/headline.svg: the malignant-answer rate
on full images, forced format, under `neutral`, `colleague_benign` and
`colleague_malignant` for each model, with the Wilson 95% intervals from the
same table. No number is computed here; the rates and intervals are drawn as
the analysis wrote them. The output is deterministic, so a test can check
that the committed chart matches the committed table.

Colors are the first three slots of a categorical palette validated for
color-vision deficiency in light and dark mode; each condition also has its
own marker shape and every point carries its value, so color is never the
only cue. The SVG switches to dark colors with prefers-color-scheme.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
CELLS = ROOT / "reports" / "analysis" / "cells.csv"
OUT = ROOT / "reports" / "figures" / "headline.svg"

MODELS = [
    ("qwen3_vl_8b", "Qwen3-VL 8B"),
    ("medgemma_1_5_4b", "MedGemma 1.5 4B"),
    ("internvl3_5_8b", "InternVL3.5 8B"),
]
CONDITIONS = [
    ("neutral", "Neutral prompt", "circle"),
    ("colleague_benign", "Colleague says benign", "square"),
    ("colleague_malignant", "Colleague says malignant", "diamond"),
]

WIDTH = 880
LABEL_X = 24
PLOT_X0 = 270
PLOT_X1 = 840
TOP = 132
HEADING = 30
ROW = 36
GAP = 20

STYLE = """
.surface { fill: #fcfcfb; }
.ink { fill: #0b0b0b; }
.ink2 { fill: #52514e; }
.grid { stroke: #e4e3df; stroke-width: 1; }
.axis { stroke: #a3a29c; stroke-width: 1; }
.c1 { fill: #2a78d6; stroke: #2a78d6; }
.c2 { fill: #eb6834; stroke: #eb6834; }
.c3 { fill: #1baf7a; stroke: #1baf7a; }
.ring { stroke: #fcfcfb; stroke-width: 2; }
text { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
@media (prefers-color-scheme: dark) {
  .surface { fill: #1a1a19; }
  .ink { fill: #f0efec; }
  .ink2 { fill: #c3c2b7; }
  .grid { stroke: #33332f; }
  .axis { stroke: #6b6a64; }
  .c1 { fill: #3987e5; stroke: #3987e5; }
  .c2 { fill: #d95926; stroke: #d95926; }
  .c3 { fill: #199e70; stroke: #199e70; }
  .ring { stroke: #1a1a19; }
}
"""


def read_cells(path: Path) -> dict[tuple[str, str], tuple[float, float, float]]:
    """Malignant rate and Wilson interval per (model, condition), full images, forced."""
    wanted = {c for c, _, _ in CONDITIONS}
    out = {}
    with path.open(newline="") as f:
        for r in csv.DictReader(f):
            if (r["image_kind"], r["answer_format"]) != ("full", "forced"):
                continue
            if r["condition"] in wanted:
                out[(r["model"], r["condition"])] = (
                    float(r["malignant_rate"]),
                    float(r["malignant_ci_low"]),
                    float(r["malignant_ci_high"]),
                )
    missing = [(m, c) for m, _ in MODELS for c, _, _ in CONDITIONS if (m, c) not in out]
    if missing:
        raise SystemExit(f"cells.csv lacks {missing}")
    return out


def x_of(rate: float) -> float:
    return PLOT_X0 + rate * (PLOT_X1 - PLOT_X0)


def pct(rate: float) -> str:
    return f"{100 * rate:.1f}%"


def text(x: float, y: float, s: str, cls: str, size: int, bold=False, anchor="start") -> str:
    weight = ' font-weight="600"' if bold else ""
    end = f' text-anchor="{anchor}"' if anchor != "start" else ""
    return (
        f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" font-size="{size}"{weight}{end}>'
        f"{escape(s)}</text>"
    )


def line(x1: float, y1: float, x2: float, y2: float, cls: str, extra="") -> str:
    return f'<line class="{cls}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"{extra}/>'


def marker(shape: str, x: float, y: float, cls: str) -> str:
    c = f'class="{cls} ring"'
    if shape == "circle":
        return f'<circle {c} cx="{x:.1f}" cy="{y:.1f}" r="7.5"/>'
    if shape == "square":
        return f'<rect {c} x="{x - 7:.1f}" y="{y - 7:.1f}" width="14" height="14" rx="2"/>'
    pts = [(x, y - 9), (x + 9, y), (x, y + 9), (x - 9, y)]
    d = " ".join(f"{'M' if i == 0 else 'L'}{px:.1f} {py:.1f}" for i, (px, py) in enumerate(pts))
    return f'<path {c} d="{d} Z"/>'


def render(cells: dict[tuple[str, str], tuple[float, float, float]]) -> str:
    panel = HEADING + ROW * len(CONDITIONS) + GAP
    bottom = TOP + panel * len(MODELS) - GAP
    height = bottom + 92
    title = "Malignant-answer rate on the same 500 mammograms, by prompt"
    desc = "; ".join(
        f"{name}: " + ", ".join(f"{label} {pct(cells[(key, c)][0])}" for c, label, _ in CONDITIONS)
        for key, name in MODELS
    )
    desc += ". Full images, forced format, 1,500 calls per cell, Wilson 95% intervals."
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" '
        f'width="{WIDTH}" height="{height}" role="img" aria-labelledby="t d">',
        f'<title id="t">{escape(title)}</title>',
        f'<desc id="d">{escape(desc)}</desc>',
        f"<style>{STYLE}</style>",
        f'<rect class="surface" width="{WIDTH}" height="{height}" rx="12"/>',
        text(LABEL_X, 40, title, "ink", 24, bold=True),
        text(
            LABEL_X,
            68,
            "Full images, forced answer format, 1,500 calls per cell; bars are 95% intervals",
            "ink2",
            16,
        ),
    ]
    # Legend, one row.
    lx = LABEL_X
    for i, (_, label, shape) in enumerate(CONDITIONS, 1):
        parts.append(marker(shape, lx + 9, 100, f"c{i}"))
        parts.append(text(lx + 24, 106, label, "ink", 16))
        lx += 34 + 9 * len(label) + 28
    # Grid and axis.
    for tick in (0, 0.25, 0.5, 0.75, 1):
        x = x_of(tick)
        parts.append(line(x, TOP - 6, x, bottom, "grid"))
        parts.append(text(x, bottom + 24, f"{int(tick * 100)}%", "ink2", 15, anchor="middle"))
    parts.append(line(PLOT_X0, bottom, PLOT_X1, bottom, "axis"))
    # Panels.
    for p, (key, name) in enumerate(MODELS):
        y0 = TOP + p * panel
        parts.append(text(LABEL_X, y0 + 20, name, "ink", 18, bold=True))
        for i, (cond, label, shape) in enumerate(CONDITIONS, 1):
            rate, lo, hi = cells[(key, cond)]
            y = y0 + HEADING + ROW * (i - 1) + ROW / 2
            tip = f"{name}, {label}: {pct(rate)} (95% interval {pct(lo)} to {pct(hi)})"
            parts.append(f"<g><title>{escape(tip)}</title>")
            parts.append(text(LABEL_X + 12, y + 5, label, "ink2", 16))
            parts.append(line(x_of(lo), y, x_of(hi), y, f"c{i}", ' stroke-width="2"'))
            parts.append(marker(shape, x_of(rate), y, f"c{i}"))
            if rate > 0.8:
                parts.append(text(x_of(lo) - 14, y + 5, pct(rate), "ink", 16, True, "end"))
            else:
                parts.append(text(x_of(hi) + 14, y + 5, pct(rate), "ink", 16, True))
            parts.append("</g>")
    parts.append(
        text(
            LABEL_X,
            bottom + 62,
            "Source: reports/analysis/cells.csv. Chart: uv run python -m eval.headline",
            "ink2",
            14,
        )
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cells", type=Path, default=CELLS)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    args.out.write_text(render(read_cells(args.cells)))
    print(f"wrote {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
