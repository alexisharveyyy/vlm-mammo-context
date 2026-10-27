import "./style.css";
import { type Answer, type Case, CONDITIONS, type Data, KINDS, answers, cellKey, flipped } from "./data";

const PAGE_SIZE = 50;
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

function fillSelect(select: HTMLSelectElement, values: string[]): void {
  select.replaceChildren(...values.map((v) => Object.assign(el("option", v), { value: v })));
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

function availableFormats(data: Data): string[] {
  const key = cellKey(controls.model.value, controls.kind.value, controls.condition.value, "plain");
  return data.cells[key] ? ["forced", "plain"] : ["forced"];
}

function matching(data: Data): number[] {
  const { model, kind, condition, format } = Object.fromEntries(
    Object.entries(controls).map(([k, v]) => [k, v.value]),
  );
  const key = cellKey(model, kind, condition, format);
  const ref = cellKey(model, kind, "neutral", format);
  const query = controls.search.value.trim().toUpperCase();
  const out: number[] = [];
  data.cases.forEach((c, i) => {
    if (controls.label.value && c.label !== controls.label.value) return;
    if (controls.type.value && c.abnormality_type !== controls.type.value) return;
    if (query && !c.case_id.includes(query)) return;
    if (controls.flipped.checked && !flipped(answers(data, key, i), answers(data, ref, i))) return;
    out.push(i);
  });
  return out;
}

function renderSummary(data: Data, rows: number[]): void {
  const key = cellKey(controls.model.value, controls.kind.value, controls.condition.value, controls.format.value);
  const counts: Record<string, number> = { M: 0, B: 0, A: 0, F: 0, E: 0 };
  for (const i of rows) for (const a of answers(data, key, i) ?? []) if (a) counts[a[0]] += 1;
  const valid = counts.M + counts.B;
  const summary = $("summary");
  summary.replaceChildren(
    el("strong", `${rows.length} of ${data.cases.length} cases`),
    el(
      "span",
      data.cells[key]
        ? ` | this cell: ${valid} valid answers, malignant ${valid ? ((100 * counts.M) / valid).toFixed(1) : "n/a"}%, ` +
            `${counts.A} abstained, ${counts.F} parse failures, ${counts.E} errors`
        : " | this cell has not been run",
    ),
  );
}

function renderRows(data: Data): void {
  const rows = matching(data);
  const pages = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  page = Math.min(page, pages - 1);
  const { model, kind, condition, format } = Object.fromEntries(
    Object.entries(controls).map(([k, v]) => [k, v.value]),
  );
  $("cond-head").textContent = condition;
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
      const neutral = el("td");
      neutral.append(marks(answers(data, cellKey(model, kind, "neutral", format), i)));
      const cond = el("td");
      cond.append(marks(answers(data, cellKey(model, kind, condition, format), i)));
      tr.append(
        el("td", c.case_id, "mono"),
        el("td", c.label, `label ${c.label}`),
        el("td", c.abnormality_type),
        el("td", context(c)),
        neutral,
        cond,
      );
      return tr;
    }),
  );
  $("page").textContent = `Page ${page + 1} of ${pages}`;
  $<HTMLButtonElement>("prev").disabled = page === 0;
  $<HTMLButtonElement>("next").disabled = page >= pages - 1;
  renderSummary(data, rows);
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
  const format = controls.format.value;
  for (const kind of KINDS) {
    const conditions = CONDITIONS.filter((cond) =>
      data.models.some((m) => data.cells[cellKey(m, kind, cond, format)]),
    );
    if (!conditions.length) continue;
    const table = el("table", "", "grid");
    const header = el("tr");
    header.append(el("th", kind), ...data.models.map((m) => el("th", m)));
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

async function main(): Promise<void> {
  const data = (await (await fetch("./data.json")).json()) as Data;
  $("meta").textContent =
    `${data.meta.calls.toLocaleString()} model calls from ${data.meta.source}, commit ${data.meta.commit.slice(0, 7)}.`;
  fillSelect(controls.model, data.models);
  const present = (i: number) => (k: string) => Object.keys(data.cells).some((key) => key.split("|")[i] === k);
  fillSelect(controls.kind, KINDS.filter(present(1)));
  fillSelect(controls.condition, CONDITIONS.filter(present(2)));
  fillSelect(controls.format, availableFormats(data));
  for (const control of Object.values(controls)) {
    control.addEventListener("input", () => {
      if (control !== controls.format) {
        const current = controls.format.value;
        fillSelect(controls.format, availableFormats(data));
        if ([...controls.format.options].some((o) => o.value === current)) controls.format.value = current;
      }
      controls.flipped.disabled = controls.condition.value === "neutral";
      page = 0;
      renderRows(data);
      renderDetail(data);
    });
  }
  controls.flipped.disabled = controls.condition.value === "neutral";
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

main().catch((e: unknown) => {
  $("summary").textContent = `Could not load data.json: ${String(e)}`;
});
