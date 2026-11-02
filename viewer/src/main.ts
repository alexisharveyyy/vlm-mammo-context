import "./style.css";
import headline from "../../reports/figures/headline.svg?raw";
import {
  type Answer,
  type Case,
  CONDITIONS,
  type Data,
  KIND_NAMES,
  KINDS,
  MODEL_NAMES,
  answers,
  cellKey,
  flipped,
  idcViewerUrl,
} from "./data";

const PAGE_SIZE = 50;
// The value of the "all" option of every filter.
const ALL = "";
const FORMATS = ["forced", "plain"];
const LEGEND: [string, string][] = [
  ["M", "malignant"],
  ["B", "benign"],
  ["A", "abstained"],
  ["F", "parse failure"],
  ["E", "run error"],
  ["none", "not run"],
];
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

const fmt = (n: number) => n.toLocaleString("en-US");

// Options "all" followed by the values, with an optional display name.
function fillSelect(select: HTMLSelectElement, values: string[], names: Record<string, string> = {}): void {
  select.replaceChildren(
    ...[ALL, ...values].map((v) =>
      Object.assign(el("option", v === ALL ? "all" : (names[v] ?? v)), { value: v }),
    ),
  );
}

function mark(status: string): HTMLElement {
  return el("span", status === "none" ? "." : status, `ans ${status}`);
}

function marks(list: (Answer | null)[] | null): HTMLElement {
  const span = el("span", "", "marks");
  for (const a of list ?? [null, null, null]) {
    const m = mark(a ? a[0] : "none");
    if (a) {
      const p = a[1] === null ? "n/a" : a[1].toFixed(3);
      m.title = `p_malignant ${p}, BI-RADS ${a[2] ?? "n/a"}, confidence ${a[3] ?? "n/a"}${a[4] ? `\n${a[4]}` : ""}`;
    } else {
      m.title = "not run";
    }
    span.append(m);
  }
  return span;
}

function legend(): HTMLElement {
  const box = el("div", "", "legend");
  box.setAttribute("aria-label", "Legend");
  for (const [status, name] of LEGEND) {
    const item = el("span", "", "item");
    item.append(mark(status), name);
    box.append(item);
  }
  box.append(el("span", "Three marks per cell, one per paraphrase."));
  return box;
}

function pill(label: string): HTMLElement {
  return el("span", label, `pill ${label}`);
}

function context(c: Case): string {
  return `${c.synthetic_age}, ${c.synthetic_family_history}`;
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
  $("count").textContent = `${fmt(rows.length)} of ${fmt(data.cases.length)} cases`;
  if (!keys.length) {
    $("tally").textContent = "No cell that was run matches these filters.";
    return;
  }
  const n = counts(data, keys, rows);
  const valid = n.M + n.B;
  const rate = valid ? `${((100 * n.M) / valid).toFixed(1)}% malignant` : "no valid answers";
  const scope = keys.length === 1 ? "1 matching cell" : `${keys.length} matching cells`;
  $("tally").textContent =
    `${scope}: ${fmt(valid)} valid answers (${rate}), ${fmt(n.A)} abstained, ` +
    `${fmt(n.F)} parse failures, ${fmt(n.E)} errors`;
}

// One matching cell: the three paraphrase marks under neutral and under the
// cell. Several: per case, malignant answers of valid answers over the matching
// cells, and matching cells that flip against neutral of matching non-neutral cells.
function rowCells(data: Data, keys: string[], i: number): [HTMLElement, HTMLElement] {
  const a = el("td", "", "num");
  const b = el("td", "", "num");
  if (keys.length === 1) {
    a.append(marks(answers(data, neutralOf(keys[0]), i)));
    b.append(marks(answers(data, keys[0], i)));
    return [a, b];
  }
  const n = counts(data, keys, [i]);
  const valid = n.M + n.B;
  a.textContent = valid ? `${n.M} of ${valid}` : "none valid";
  a.title = `${n.M} malignant of ${valid} valid answers; ${n.A} abstained, ${n.F} parse failures, ${n.E} errors`;
  const contexts = keys.filter((key) => !key.includes("|neutral|")).length;
  b.textContent = contexts ? `${flippedCells(data, keys, i)} of ${contexts}` : "n/a";
  return [a, b];
}

function select(data: Data, i: number): void {
  selected = i;
  renderDetail(data);
  renderRows(data);
  if (window.matchMedia("(max-width: 1099px)").matches) {
    $("detail").scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function renderRows(data: Data): void {
  const keys = matchingKeys(data);
  const rows = matching(data, keys);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  page = Math.min(page, pages - 1);
  const single = keys.length === 1;
  $("head-a").textContent = single ? "Neutral" : "Malignant answers";
  $("head-b").textContent = single ? keys[0].split("|")[2] : "Cells flipped";
  const focused = document.activeElement instanceof HTMLTableRowElement ? document.activeElement.dataset.i : undefined;
  const body = $("rows");
  body.replaceChildren(
    ...rows.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE).map((i) => {
      const c = data.cases[i];
      const tr = el("tr");
      tr.dataset.i = String(i);
      tr.tabIndex = 0;
      tr.setAttribute("aria-selected", String(i === selected));
      tr.setAttribute("aria-label", `${c.case_id}, ${c.label}, ${c.abnormality_type}`);
      tr.addEventListener("click", () => select(data, i));
      tr.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          select(data, i);
        } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          const next = e.key === "ArrowDown" ? tr.nextElementSibling : tr.previousElementSibling;
          if (next instanceof HTMLElement) next.focus();
        }
      });
      const label = el("td");
      label.append(pill(c.label));
      const [first, second] = rowCells(data, keys, i);
      tr.append(
        el("td", c.case_id, "mono"),
        label,
        el("td", c.abnormality_type === "calc" ? "calcification" : c.abnormality_type),
        el("td", context(c)),
        first,
        second,
      );
      return tr;
    }),
  );
  // Re-rendering replaces the rows; keep the keyboard focus on the same case.
  if (focused !== undefined) body.querySelector<HTMLElement>(`tr[data-i="${focused}"]`)?.focus();
  $("page").textContent = `Page ${page + 1} of ${pages}`;
  $<HTMLButtonElement>("prev").disabled = page === 0;
  $<HTMLButtonElement>("next").disabled = page >= pages - 1;
  renderSummary(data, keys, rows);
}

function idcLink(text: string, study: string, series: string): HTMLAnchorElement {
  const a = el("a", text, "button");
  a.href = idcViewerUrl(study, series);
  a.target = "_blank";
  a.rel = "noopener noreferrer";
  return a;
}

function renderDetail(data: Data): void {
  const detail = $("detail");
  if (selected === null) return;
  const c = data.cases[selected];
  const title = el("div", "", "title-row");
  title.append(el("h2", c.case_id), pill(c.label));
  const chips = el("ul", "", "chips");
  chips.setAttribute("aria-label", "Case details");
  for (const text of [
    c.abnormality_type === "calc" ? "calcification" : c.abnormality_type,
    `CBIS-DDSM BI-RADS ${c.birads_assessment}`,
    `density ${c.breast_density}`,
    `subtlety ${c.subtlety}`,
    `synthetic age ${c.synthetic_age}`,
    `synthetic history ${c.synthetic_family_history}`,
  ]) {
    chips.append(el("li", text));
  }
  const actions = el("div", "", "actions");
  actions.append(
    idcLink("View full image in IDC", c.full_study_uid, c.full_series_uid),
    idcLink("View ROI crop in IDC", c.roi_study_uid, c.roi_series_uid),
  );
  const note = el(
    "p",
    "Opens the NCI Imaging Data Commons viewer in a new tab. Images are shown by IDC, not hosted on this site. " +
      "Some ROI series also contain the ROI mask.",
    "muted small",
  );
  const parts: HTMLElement[] = [title, chips, actions, note];
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
  parts.push(legend());
  const formats = controls.format.value === ALL ? FORMATS : [controls.format.value];
  const sections = formats.flatMap((format) => KINDS.map((kind) => [format, kind] as const));
  for (const [format, kind] of sections) {
    const conditions = CONDITIONS.filter((cond) =>
      data.models.some((m) => data.cells[cellKey(m, kind, cond, format)]),
    );
    if (!conditions.length) continue;
    const name = KIND_NAMES[kind] ?? kind;
    parts.push(el("h3", format === "forced" ? name : `${name}, ${format} format`, "grid-title"));
    const table = el("table", "", "grid");
    const head = el("tr");
    head.append(el("th", "Condition"), ...data.models.map((m) => el("th", MODEL_NAMES[m] ?? m)));
    for (const th of head.children) th.setAttribute("scope", "col");
    const thead = el("thead");
    thead.append(head);
    const tbody = el("tbody");
    for (const cond of conditions) {
      const tr = el("tr");
      const th = el("th", cond);
      th.scope = "row";
      tr.append(th);
      let any = false;
      for (const m of data.models) {
        const td = el("td");
        const list = answers(data, cellKey(m, kind, cond, format), selected);
        td.append(marks(list));
        if (cond !== "neutral" && flipped(list, answers(data, cellKey(m, kind, "neutral", format), selected))) {
          td.className = "flip";
          td.title = "differs from neutral in at least one paraphrase";
          any = true;
        }
        tr.append(td);
      }
      if (any) tr.className = "flip-row";
      tbody.append(tr);
    }
    table.append(thead, tbody);
    const wrap = el("div", "", "grid-wrap");
    wrap.append(table);
    parts.push(wrap);
  }
  detail.replaceChildren(...parts);
}

// The headline chart, in a shadow root so its own styles stay inside it.
function renderChart(): void {
  const host = $("chart");
  const root = host.attachShadow({ mode: "open" });
  // Below 600 px the chart scrolls sideways instead of shrinking its text.
  root.innerHTML = `<style>:host{display:block;overflow-x:auto}svg{display:block;width:100%;min-width:600px;height:auto}</style>${headline}`;
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
  const box = el("p", "", "notice");
  if (e instanceof MissingData) {
    box.append(
      el("strong", "The data file is missing. "),
      "data.json is generated from the committed run outputs and not stored in the repository. From the ",
      el("code", "viewer/"),
      " folder run ",
      el("code", "npm run data"),
      " and reload the page (",
      el("code", "npm run dev"),
      " and ",
      el("code", "npm run build"),
      " run it first).",
    );
  } else {
    box.append(el("strong", "Could not read data.json. "), String(e));
  }
  $("count").replaceChildren(box);
}

function resetFilters(): void {
  for (const c of [controls.model, controls.kind, controls.condition, controls.format, controls.label, controls.type]) {
    c.value = ALL;
  }
  controls.search.value = "";
  controls.flipped.checked = false;
}

async function main(): Promise<void> {
  renderChart();
  const data = await loadData();
  const total = counts(data, Object.keys(data.cells), data.cases.map((_, i) => i));
  $("stat-cases").textContent = fmt(data.cases.length);
  $("stat-models").textContent = fmt(data.models.length);
  $("stat-calls").textContent = fmt(data.meta.calls);
  $("stat-errors").textContent = fmt(total.E);
  fillSelect(controls.model, data.models, MODEL_NAMES);
  const present = (i: number) => (k: string) => Object.keys(data.cells).some((key) => key.split("|")[i] === k);
  fillSelect(controls.kind, KINDS.filter(present(1)), KIND_NAMES);
  fillSelect(controls.condition, CONDITIONS.filter(present(2)));
  fillSelect(controls.format, FORMATS.filter(present(3)));
  // "Answer flipped" needs a matching cell other than neutral.
  const updateFlipped = () => {
    controls.flipped.disabled = matchingKeys(data).every((key) => key.includes("|neutral|"));
    if (controls.flipped.disabled) controls.flipped.checked = false;
  };
  const refresh = () => {
    updateFlipped();
    page = 0;
    renderRows(data);
    renderDetail(data);
  };
  for (const control of Object.values(controls)) control.addEventListener("input", refresh);
  $("reset").addEventListener("click", () => {
    resetFilters();
    refresh();
  });
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
