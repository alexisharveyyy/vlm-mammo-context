// Fail if the public build contains or references an image.
//
//   npm run build && npm run check-dist

import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join, resolve } from "node:path";

const DIST = resolve(import.meta.dirname, "..", "dist");
const IMAGE_EXTENSIONS = new Set([
  ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif", ".bmp", ".tif", ".tiff", ".svg", ".ico",
  ".dcm", ".dicom", ".nii", ".gz",
]);
const FORBIDDEN = [/local-images/, /data:image\//, /<img\b/i, /\.png\b/i, /\.dcm\b/i];
const CASE_FIELDS = new Set([
  "case_id", "label", "abnormality_type", "birads_assessment", "breast_density", "subtlety",
  "synthetic_age", "synthetic_family_history",
  // Public DICOM UIDs for the links to the IDC viewer.
  "full_study_uid", "full_series_uid", "roi_study_uid", "roi_series_uid",
]);
const UID = /^[0-9]+(\.[0-9]+)+$/;

const problems: string[] = [];
const files = readdirSync(DIST, { recursive: true, encoding: "utf8" })
  .map((f) => join(DIST, f))
  .filter((f) => statSync(f).isFile());
for (const file of files) {
  if (IMAGE_EXTENSIONS.has(extname(file).toLowerCase())) problems.push(`image file: ${file}`);
  const text = readFileSync(file, "utf8");
  for (const pattern of FORBIDDEN) {
    if (!file.endsWith("data.json") && pattern.test(text)) problems.push(`${file} matches ${pattern}`);
  }
}
const data = JSON.parse(readFileSync(join(DIST, "data.json"), "utf8")) as {
  cases: Record<string, string>[];
};
for (const key of new Set(data.cases.flatMap((c) => Object.keys(c)))) {
  if (!CASE_FIELDS.has(key)) problems.push(`data.json: unexpected case field ${key}`);
  if (key.endsWith("_uid") && !data.cases.every((c) => UID.test(c[key]))) {
    problems.push(`data.json: ${key} is not a DICOM UID in every case`);
  }
}
for (const p of problems) console.error(p);
console.log(`check-dist: ${files.length} files, ${problems.length} problem(s)`);
process.exit(problems.length ? 1 : 0);
