import "./style.css";
import { type Answer, type Case, CONDITIONS, type Data, KINDS, answers, cellKey, flipped } from "./data";

const PAGE_SIZE = 50;
// The value of the "all" option of every filter.
const ALL = "";
const FORMATS = ["forced", "plain"];
const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;

const controls = {
  model: $<HTMLSelectElement>("model"),
  kind: $<HTMLSelectElement>("kind"),
  condition: $<HTMLSelectElement>("condition"),
  format: $<HTMLSelectElement>("format"),
  label: $<HTMLSelectElement>("label"),
  type: $<HTMLSelectElement>("type"),
  flipped: $<HTMLInputElement>("flipped"),
  search: $<HTMLInputElement>("search"),
};
let page = 0;
let selected: number | null = null;

function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  text = "",
  className = "",
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

// Options "all" followed by the values.
function fillSelect(select: HTMLSelectElement, values: string[]): void {
  select.replaceChildren(
    ...[ALL, ...values].map((v) => Object.assign(el("option", v === ALL ? "all" : v), { value: v })),
  );
}

function marks(list: (Answer | null)[] | null): HTMLElement {
  const span = el("span", "", "marks");
  for (const a of list ?? [null, null, null]) {
    const mark = el("span", a ? a[0] : ".", `ans ${a ? a[0] : "none"}`);
    if (a) {
      const p = a[1] === null ? "n/a" : a[1].toFixed(3);
      mark.title = `p_malignant ${p}, BI-RADS ${a[2] ?? "n/a"}, confidence ${a[3] ?? "n/a"}${a[4] ? `\n${a[4]}` : ""}`;
    }
    span.append(mark);
  }
  return span;
}

function context(c: Case): string {
  return `age ${c.synthetic_age}, history ${c.synthetic_family_history}`;
}

// Cells that were run and match the model, image, condition and format filters,
// in the order of the filter options.
function matchingKeys(data: Data): string[] {
  const order = [data.models, KINDS, CONDITIONS, FORMATS];
  const wanted = [controls.model, controls.kind, controls.condition, controls.format].map((c) => c.value);
  return Object.keys(data.cells)
    .map((key) => key.split("|"))
    .filter((parts) => parts.every((v, j) => wanted[j] === ALL || wanted[j] === v))
    .sort((a, b) => {
      for (let j = 0; j < 4; j++) {
        const d = order[j].indexOf(a[j]) - order[j].indexOf(b[j]);
        if (d) return d;
      }
      return 0;
    })
    .map((parts) => parts.join("|"));
}

function neutralOf(key: string): string {
  const [model, kind, , format] = key.split("|");
  return cellKey(model, kind, "neutral", format);
}

// Matching cells of case i whose answers differ from neutral in a paraphrase.
function flippedCells(data: Data, keys: string[], i: number): number {
  return keys.filter(
    (key) => !key.includes("|neutral|") && flipped(answers(data, key, i), answers(data, neutralOf(key), i)),
  ).length;
}

function counts(data: Data, keys: string[], rows: number[]): Record<string, number> {
  const out: Record<string, number> = { M: 0, B: 0, A: 0, F: 0, E: 0 };
  for (const key of keys) for (const i of rows) for (const a of answers(data, key, i) ?? []) if (a) out[a[0]] += 1;
  return out;
}

function matching(data: Data, keys: string[]): number[] {
  const query = controls.search.value.trim().toUpperCase();
  const out: number[] = [];
  data.cases.forEach((c, i) => {
    if (controls.label.value && c.label !== controls.label.value) return;
    if (controls.type.value && c.abnormality_type !== controls.type.value) return;
    if (query && !c.case_id.includes(query)) return;
    if (controls.flipped.checked && !flippedCells(data, keys, i)) return;
    out.push(i);
  });
  return out;
}

function renderSummary(data: Data, keys: string[], rows: number[]): void {
  const n = counts(data, keys, rows);
  const valid = n.M + n.B;
  const scope = keys.length === 1 ? "this cell" : `${keys.length} cells`;
  $("summary").replaceChildren(
    el("strong", `${rows.length} of ${data.cases.length} cases`),
    el(
      "span",
      keys.length
        ? ` | ${scope}: ${valid} valid answers, malignant ${valid ? ((100 * n.M) / valid).toFixed(1) : "n/a"}%, ` +
            `${n.A} abstained, ${n.F} parse failures, ${n.E} errors`
        : " | no cell that was run matches these filters",
    ),
  );
}

// One matching cell: the three paraphrase marks under neutral and under the
// cell. Several: per case, malignant answers / valid answers over the matching
// cells, and matching cells that flip against neutral / matching non-neutral cells.
function rowCells(data: Data, keys: string[], i: number): [HTMLElement, HTMLElement] {
  const a = el("td");
  const b = el("td");
  if (keys.length === 1) {
    a.append(marks(answers(data, neutralOf(keys[0]), i)));
    b.append(marks(answers(data, keys[0], i)));
    return [a, b];
  }
  const n = counts(data, keys, [i]);
  const valid = n.M + n.B;
  a.textContent = valid ? `${n.M} / ${valid}` : "none valid";
  a.title = `${n.A} abstained, ${n.F} parse failures, ${n.E} errors`;
  const contexts = keys.filter((key) => !key.includes("|neutral|")).length;
  b.textContent = contexts ? `${flippedCells(data, keys, i)} / ${contexts}` : "n/a";
  return [a, b];
}

function renderRows(data: Data): void {
  const keys = matchingKeys(data);
  const rows = matching(data, keys);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  page = Math.min(page, pages - 1);
  const single = keys.length === 1;
  $("head-a").textContent = single ? "Neutral" : "Malignant / valid";
  $("head-b").textContent = single ? keys[0].split("|")[2] : "Cells flipped";
  const body = $("rows");
  body.replaceChildren(
    ...rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map((i) => {
      const c = data.cases[i];
      const tr = el("tr");
      if (i === selected) tr.className = "selected";
      tr.tabIndex = 0;
      const open = () => {
        selected = i;
        renderDetail(data);
        renderRows(data);
      };
      tr.addEventListener("click", open);
      tr.addEventListener("keydown", (e) => {
        if (e.key === "Enter") open();
      });
      const [first, second] = rowCells(data, keys, i);
      tr.append(
        el("td", c.case_id, "mono"),
        el("td", c.label, `label ${c.label}`),
        el("td", c.abnormality_type),
        el("td", context(c)),
        first,
        second,
      );
      return tr;
    }),
  );
  $("page").textContent = `Page ${page + 1} of ${pages}`;
  $<HTMLButtonElement>("prev").disabled = page === 0;
  $<HTMLButtonElement>("next").disabled = page >= pages - 1;
  renderSummary(data, keys, rows);
}

function renderDetail(data: Data): void {
  const detail = $("detail");
  if (selected === null) return;
  const c = data.cases[selected];
  const head = el("div", "", "detail-head");
  head.append(
    el("h2", c.case_id),
    el(
      "p",
      `Biopsy label ${c.label}; ${c.abnormality_type}; CBIS-DDSM BI-RADS ${c.birads_assessment}; ` +
        `density ${c.breast_density}; subtlety ${c.subtlety}. Synthetic context: ${context(c)}.`,
    ),
  );
  const parts: HTMLElement[] = [head];
  if (import.meta.env.DEV && import.meta.env.VITE_LOCAL_IMAGES === "1") {
    const figure = el("div", "", "local");
    for (const k of ["full", "roi"]) {
      const img = el("img");
      img.alt = `${k} image of ${c.case_id} (local only)`;
      img.src = `/local-images/${k}/${c.case_id}.png`;
      figure.append(img);
    }
    parts.push(figure);
  }
  const formats = controls.format.value === ALL ? FORMATS : [controls.format.value];
  const sections = formats.flatMap((format) => KINDS.map((kind) => [format, kind] as const));
  for (const [format, kind] of sections) {
    const conditions = CONDITIONS.filter((cond) =>
      data.models.some((m) => data.cells[cellKey(m, kind, cond, format)]),
    );
    if (!conditions.length) continue;
    const table = el("table", "", "grid");
    const header = el("tr");
    const title = format === "forced" ? kind : `${kind} (${format})`;
    header.append(el("th", title), ...data.models.map((m) => el("th", m)));
    table.append(header);
    for (const cond of conditions) {
      const tr = el("tr");
      tr.append(el("th", cond));
      for (const m of data.models) {
        const td = el("td");
        const list = answers(data, cellKey(m, kind, cond, format), selected);
        td.append(marks(list));
        if (cond !== "neutral" && flipped(list, answers(data, cellKey(m, kind, "neutral", format), selected))) {
          td.className = "flip";
          td.title = "differs from neutral in at least one paraphrase";
        }
        tr.append(td);
      }
      table.append(tr);
    }
    parts.push(table);
  }
  detail.replaceChildren(...parts);
}

class MissingData extends Error {}

// A missing data.json comes back as the dev server's HTML page or a 404.
async function loadData(): Promise<Data> {
  const response = await fetch("./data.json");
  const text = response.ok ? await response.text() : "";
  if (!text || text.trimStart().startsWith("<")) throw new MissingData();
  return JSON.parse(text) as Data;
}

function showError(e: unknown): void {
  const box = el("div", "", "notice");
  if (e instanceof MissingData) {
    const command = el("code", "npm run data");
    box.append(
      el("strong", "The data file is missing. "),
      "data.json is generated from the committed run outputs and not stored in the repository. From the ",
      el("code", "viewer/"),
      " folder run ",
      command,
      " and reload the page (",
      el("code", "npm run dev"),
      " and ",
      el("code", "npm run build"),
      " run it first).",
    );
  } else {
    box.append(el("strong", "Could not read data.json. "), String(e));
  }
  $("summary").replaceChildren(box);
}

async function main(): Promise<void> {
  const data = await loadData();
  $("meta").textContent =
    `${data.meta.calls.toLocaleString()} model calls from ${data.meta.source}, commit ${data.meta.commit.slice(0, 7)}.`;
  fillSelect(controls.model, data.models);
  const present = (i: number) => (k: string) => Object.keys(data.cells).some((key) => key.split("|")[i] === k);
  fillSelect(controls.kind, KINDS.filter(present(1)));
  fillSelect(controls.condition, CONDITIONS.filter(present(2)));
  fillSelect(controls.format, FORMATS.filter(present(3)));
  // "Answer flipped" needs a matching cell other than neutral.
  const updateFlipped = () => {
    controls.flipped.disabled = matchingKeys(data).every((key) => key.includes("|neutral|"));
  };
  for (const control of Object.values(controls)) {
    control.addEventListener("input", () => {
      updateFlipped();
      page = 0;
      renderRows(data);
      renderDetail(data);
    });
  }
  updateFlipped();
  $("prev").addEventListener("click", () => {
    page -= 1;
    renderRows(data);
  });
  $("next").addEventListener("click", () => {
    page += 1;
    renderRows(data);
  });
  renderRows(data);
}

main().catch(showError);
