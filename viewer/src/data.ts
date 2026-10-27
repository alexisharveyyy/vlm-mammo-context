// The shape of public/data.json (scripts/build-data.ts) and helpers over it.

export type Status = "M" | "B" | "A" | "F" | "E";
export type Answer = [Status, number | null, number | null, number | null, string?];

export interface Case {
  case_id: string;
  label: string;
  abnormality_type: string;
  birads_assessment: string;
  breast_density: string;
  subtlety: string;
  synthetic_age: string;
  synthetic_family_history: string;
}

export interface Data {
  meta: { commit: string; calls: number; source: string };
  models: string[];
  cases: Case[];
  cells: Record<string, (Answer | null)[]>;
}

export const KINDS = ["full", "roi", "no_image", "blank_full", "blank_roi"];
export const CONDITIONS = [
  "neutral",
  "age_42",
  "age_68",
  "history_yes",
  "history_no",
  "combined",
  "colleague_benign",
  "colleague_malignant",
  "irrelevant",
];

export function cellKey(model: string, kind: string, condition: string, format: string): string {
  return [model, kind, condition, format].join("|");
}

// The three paraphrase answers of case i in a cell, or null if the cell was not run.
export function answers(data: Data, key: string, i: number): (Answer | null)[] | null {
  const cell = data.cells[key];
  return cell ? cell.slice(i * 3, i * 3 + 3) : null;
}

export function isValid(a: Answer | null): boolean {
  return a !== null && (a[0] === "M" || a[0] === "B");
}

// True when a paraphrase answered validly in both cells differs.
export function flipped(a: (Answer | null)[] | null, b: (Answer | null)[] | null): boolean {
  if (!a || !b) return false;
  return a.some((x, p) => isValid(x) && isValid(b[p]) && x?.[0] !== b[p]?.[0]);
}
