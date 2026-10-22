// CSV parsing and a filterable, sortable table. Cells are text nodes only.
import { h } from "./ui.js";

export function parseCsv(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); field = "";
      rows.push(row); row = [];
    } else field += c;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  return rows.filter((r) => r.some((f) => f !== ""));
}

const ROW_LIMIT = 2000;

export function renderCsv(text, options = {}) {
  const [head, ...body] = parseCsv(text);
  const root = h("div", { class: "data" });
  if (!head) { root.append(h("p", { class: "empty" }, "Empty file.")); return root; }
  const state = { query: "", sortCol: -1, dir: 1, shown: 0 };
  const count = h("span", { class: "count" });
  const wrap = h("div", { class: "scroll" });
  const input = h("input", { type: "search", placeholder: "Filter rows", "aria-label": "Filter rows" });

  function draw() {
    const q = state.query.toLowerCase();
    let rows = body.filter((r) => !q || r.some((f) => f.toLowerCase().includes(q)));
    if (state.sortCol >= 0) {
      const col = state.sortCol;
      rows = [...rows].sort((a, b) => {
        const x = a[col] ?? "", y = b[col] ?? "";
        const nx = parseFloat(x), ny = parseFloat(y);
        return (!isNaN(nx) && !isNaN(ny) ? nx - ny : x.localeCompare(y)) * state.dir;
      });
    }
    state.shown = rows.length;
    count.textContent = `${rows.length} of ${body.length} rows` + (rows.length > ROW_LIMIT ? ` (first ${ROW_LIMIT} shown)` : "");
    const tr = h("tr");
    head.forEach((name, col) => {
      const th = h("th", { tabindex: "0", scope: "col", onclick: () => sortBy(col), onkeydown: (e) => { if (e.key === "Enter") sortBy(col); } }, name);
      if (state.sortCol === col) th.setAttribute("aria-sort", state.dir === 1 ? "ascending" : "descending");
      tr.append(th);
    });
    const tbody = h("tbody");
    for (const r of rows.slice(0, ROW_LIMIT)) tbody.append(h("tr", {}, head.map((_, c) => h("td", {}, r[c] ?? ""))));
    wrap.replaceChildren(h("table", {}, h("thead", {}, tr), tbody));
  }
  function sortBy(col) {
    state.dir = state.sortCol === col ? -state.dir : 1;
    state.sortCol = col;
    draw();
  }
  input.addEventListener("input", () => { state.query = input.value; draw(); });
  const cite = h("button", { title: "Records this filter and the row count as a new evidence entry", onclick: () => options.onCite && options.onCite({ query: state.query.trim(), shown: state.shown, total: body.length }) }, "Cite this view as evidence");
  root.append(h("div", { class: "bar" }, input, count, options.onCite ? cite : ""), wrap);
  draw();
  return root;
}
