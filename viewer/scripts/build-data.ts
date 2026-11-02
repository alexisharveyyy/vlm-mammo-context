// Build public/data.json from the committed run outputs and the test manifest.
//
//   npm run data
//
// Reads runs/<model>/<image_kind>/<condition>/p<k>[_plain].jsonl (test split
// only), data/manifests/test.csv and data/manifests/idc_viewer.csv. Keeps only
// the parsed answer of each call, the case fields listed in CASE_FIELDS, and
// the public DICOM study and series UIDs in IDC_FIELDS, which the viewer uses
// to link each case to the IDC viewer. No image, path or hash is written.

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const ROOT = resolve(import.meta.dirname, "..", "..");
const OUT = resolve(import.meta.dirname, "..", "public", "data.json");
const MODELS = ["qwen3_vl_8b", "medgemma_1_5_4b", "internvl3_5_8b"];
const CASE_FIELDS = [
  "case_id",
  "label",
  "abnormality_type",
  "birads_assessment",
  "breast_density",
  "subtlety",
  "synthetic_age",
  "synthetic_family_history",
];
const IDC_FIELDS = ["full_study_uid", "full_series_uid", "roi_study_uid", "roi_series_uid"];

interface RunRecord {
  split: string;
  model: string;
  image_kind: string;
  condition: string;
  paraphrase: number;
  answer_format: string;
  case_id: string;
  raw_text: string | null;
  birads: number | null;
  malignant: boolean | null;
  confidence: number | null;
  p_malignant: number | null;
  error: string | null;
  parse: { ok: boolean } | null;
}

// Status, p_malignant, BI-RADS, confidence, and the raw text when unparsed.
type Answer = [string, number | null, number | null, number | null, string?];

function readCsv(path: string): Record<string, string>[] {
  const text = readFileSync(path, "utf8");
  if (text.includes('"')) throw new Error(`${path}: quoted CSV fields are not supported`);
  const [header, ...lines] = text.trim().split("\n");
  const names = header.split(",");
  return lines.map((line) => {
    const values = line.split(",");
    return Object.fromEntries(names.map((n, i) => [n, values[i]]));
  });
}

// The rule of is_abstention in eval/baseline.py.
function isAbstention(text: string | null): boolean {
  if (text === null) return false;
  const m = /\bassessment[ \t]*[:=-][ \t]*([^\n]*)/i.exec(text.replace(/[*_`#]/g, ""));
  return m !== null && m[1].trim() !== "" && !/\b(benign|malignant)\b/i.test(m[1]);
}

function answer(r: RunRecord): Answer {
  if (r.error !== null) return ["E", null, null, null];
  const p = r.p_malignant === null ? null : Math.round(r.p_malignant * 1000) / 1000;
  if (r.parse?.ok && r.malignant !== null) {
    return [r.malignant ? "M" : "B", p, r.birads, r.confidence];
  }
  return [isAbstention(r.raw_text) ? "A" : "F", p, r.birads, r.confidence, (r.raw_text ?? "").slice(0, 300)];
}

function runFiles(dir: string): string[] {
  if (!existsSync(dir)) return [];
  return readdirSync(dir, { recursive: true, encoding: "utf8" })
    .filter((f) => /(^|\/)p[123](_plain)?\.jsonl$/.test(f))
    .map((f) => join(dir, f))
    .sort();
}

const cases = readCsv(join(ROOT, "data", "manifests", "test.csv"));
const idc = new Map(readCsv(join(ROOT, "data", "manifests", "idc_viewer.csv")).map((r) => [r.case_id, r]));
const index = new Map(cases.map((c, i) => [c.case_id, i]));
const cells: Record<string, (Answer | null)[]> = {};
let calls = 0;
for (const model of MODELS) {
  for (const path of runFiles(join(ROOT, "runs", model))) {
    for (const line of readFileSync(path, "utf8").split("\n")) {
      if (!line) continue;
      const r = JSON.parse(line) as RunRecord;
      if (r.split !== "test") continue;
      const i = index.get(r.case_id);
      if (i === undefined) throw new Error(`${path}: unknown case ${r.case_id}`);
      const key = [r.model, r.image_kind, r.condition, r.answer_format].join("|");
      cells[key] ??= new Array<Answer | null>(cases.length * 3).fill(null);
      cells[key][i * 3 + r.paraphrase - 1] = answer(r);
      calls += 1;
    }
  }
}

const commit = execFileSync("git", ["rev-parse", "HEAD"], { cwd: ROOT, encoding: "utf8" }).trim();
const data = {
  meta: { commit, calls, source: "runs/ (test split)" },
  models: MODELS,
  cases: cases.map((c) => {
    const links = idc.get(c.case_id);
    if (!links) throw new Error(`idc_viewer.csv: no row for ${c.case_id}`);
    return Object.fromEntries([
      ...CASE_FIELDS.map((f) => [f, c[f]]),
      ...IDC_FIELDS.map((f) => [f, links[f]]),
    ]);
  }),
  cells,
};
mkdirSync(resolve(OUT, ".."), { recursive: true });
writeFileSync(OUT, JSON.stringify(data));
console.log(`${calls} calls in ${Object.keys(cells).length} cells -> ${OUT}`);
