"use strict";

// Everything shown from a file is built with textContent / DOM nodes, never innerHTML,
// so a hostile line in a data-room file cannot run script in the page.

const token = document.querySelector('meta[name="grc-token"]').content;
const $ = (id) => document.getElementById(id);

function h(tag, attrs, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const kid of kids.flat()) node.append(kid);
  return node;
}

async function api(path, options = {}) {
  const headers = { "X-Grc-Token": token };
  if (options.body) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { ...options, headers });
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

// ---- markdown (small subset: headings, lists, tables, code, quotes, bold, italic, code) ----

function inline(parent, text) {
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*|\[[^\]]+\]\([^)]*\))/g;
  let last = 0;
  for (const m of text.matchAll(pattern)) {
    if (m.index > last) parent.append(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) parent.append(h("strong", {}, tok.slice(2, -2)));
    else if (tok.startsWith("`")) parent.append(h("code", {}, tok.slice(1, -1)));
    else if (tok.startsWith("[")) parent.append(tok.slice(1, tok.indexOf("]"))); // links show their text only
    else parent.append(h("em", {}, tok.slice(1, -1)));
    last = m.index + tok.length;
  }
  if (last < text.length) parent.append(text.slice(last));
}

function cells(line) {
  return line.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
}

function renderMarkdown(text) {
  const root = h("div", { class: "md" });
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      const code = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
      i++;
      root.append(h("pre", {}, h("code", {}, code.join("\n"))));
    } else if (/^#{1,6}\s/.test(line)) {
      const level = line.match(/^#+/)[0].length;
      const node = h("h" + level);
      inline(node, line.replace(/^#+\s*/, ""));
      root.append(node);
      i++;
    } else if (/^\s*\|/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || "")) {
      const table = h("table");
      const head = h("tr");
      for (const c of cells(line)) { const th = h("th"); inline(th, c); head.append(th); }
      table.append(h("thead", {}, head));
      i += 2;
      const body = h("tbody");
      while (i < lines.length && /^\s*\|/.test(lines[i])) {
        const row = h("tr");
        for (const c of cells(lines[i])) { const td = h("td"); inline(td, c); row.append(td); }
        body.append(row);
        i++;
      }
      table.append(body);
      root.append(table);
    } else if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const list = h(/^\s*\d/.test(line) ? "ol" : "ul");
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        const item = h("li");
        inline(item, lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
        list.append(item);
        i++;
      }
      root.append(list);
    } else if (/^>\s?/.test(line)) {
      const quote = h("blockquote");
      const parts = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) parts.push(lines[i++].replace(/^>\s?/, ""));
      inline(quote, parts.join(" "));
      root.append(quote);
    } else if (/^(-{3,}|\*{3,})\s*$/.test(line)) {
      root.append(h("hr"));
      i++;
    } else if (line.trim() === "") {
      i++;
    } else {
      const para = h("p");
      const parts = [];
      while (i < lines.length && lines[i].trim() !== "" && !/^(#{1,6}\s|```|>|\s*([-*]|\d+\.)\s+|\s*\|)/.test(lines[i])) {
        parts.push(lines[i++]);
      }
      if (!parts.length) parts.push(lines[i++]);
      inline(para, parts.join(" "));
      root.append(para);
    }
  }
  return root;
}

// ---- csv ----

function parseCsv(text) {
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

function renderCsv(text) {
  const [head, ...body] = parseCsv(text);
  const root = h("div", { class: "data" });
  if (!head) { root.append(h("p", { class: "empty" }, "Empty file.")); return root; }
  const state = { query: "", sortCol: -1, dir: 1 };
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
        const cmp = !isNaN(nx) && !isNaN(ny) ? nx - ny : x.localeCompare(y);
        return cmp * state.dir;
      });
    }
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
  root.append(h("div", { class: "bar" }, input, count), wrap);
  draw();
  return root;
}

// ---- file list and viewer ----

let files = [], current = null, noted = new Set();

function drawFiles() {
  const q = $("filter").value.toLowerCase();
  const list = $("files");
  list.replaceChildren();
  for (const path of files.filter((p) => p.toLowerCase().includes(q))) {
    const item = h("div", { class: "item" + (path === current ? " on" : ""), role: "option", tabindex: "0", "aria-selected": String(path === current), onclick: () => openFile(path), onkeydown: (e) => { if (e.key === "Enter") openFile(path); } },
      h("span", { class: "dot" + (noted.has(path) ? " has" : ""), title: "Has notes" }), path);
    list.append(item);
  }
}

async function openFile(path) {
  await notesPanel.flush();
  current = path;
  drawFiles();
  const view = $("view");
  try {
    const file = await api("/api/file?path=" + encodeURIComponent(path));
    if (file.kind === "md") view.replaceChildren(renderMarkdown(file.text));
    else if (file.kind === "csv") view.replaceChildren(renderCsv(file.text));
    else view.replaceChildren(h("pre", { class: "plain" }, file.text));
    view.scrollTop = 0;
  } catch (e) {
    view.replaceChildren(h("p", { class: "empty" }, "Could not open this file."));
  }
  await notesPanel.load(path);
}

function step(delta) {
  if (!files.length) return;
  const at = Math.max(0, files.indexOf(current));
  openFile(files[Math.min(files.length - 1, Math.max(0, at + delta))]);
}

// ---- right-hand tabs ----

const notesPanel = (() => {
  const box = h("textarea", { id: "notes-text", placeholder: "Notes for this file. Saved as you type.", "aria-label": "Notes for this file" });
  const status = h("div", { class: "status" }, "Open a file to take notes.");
  let timer = null, path = null, dirty = false;

  async function save() {
    clearTimeout(timer);
    if (!dirty || !path) return;
    const target = path, text = box.value;
    status.className = "status";
    status.textContent = "Saving...";
    try {
      await api("/api/notes", { method: "PUT", body: JSON.stringify({ path: target, text }) });
      dirty = false;
      status.textContent = "Saved";
      if (text.trim()) noted.add(target); else noted.delete(target);
      drawFiles();
    } catch (e) {
      status.className = "status bad";
      status.textContent = "NOT SAVED. Check the terminal where grc serve is running.";
    }
  }
  box.addEventListener("input", () => { dirty = true; status.textContent = "Typing..."; clearTimeout(timer); timer = setTimeout(save, 500); });
  return {
    element: () => [box, status],
    flush: save,
    async load(next) {
      path = next;
      dirty = false;
      box.value = "";
      status.className = "status";
      status.textContent = "Loading...";
      try {
        box.value = (await api("/api/notes?path=" + encodeURIComponent(next))).text;
        status.textContent = "Saved";
      } catch (e) {
        status.className = "status bad";
        status.textContent = "Could not load notes.";
      }
    },
  };
})();

const TABS = [{ id: "notes", label: "Notes", render: () => notesPanel.element() }];

function showTab(id) {
  const tab = TABS.find((t) => t.id === id);
  [...$("tabs").children].forEach((b) => b.setAttribute("aria-selected", String(b.dataset.id === id)));
  $("panel").replaceChildren(...tab.render());
}

// ---- start ----

async function start() {
  for (const tab of TABS) {
    $("tabs").append(h("button", { role: "tab", "data-id": tab.id, onclick: () => showTab(tab.id) }, tab.label));
  }
  showTab("notes");
  $("filter").addEventListener("input", drawFiles);
  addEventListener("keydown", (e) => {
    if (!e.altKey) return;
    if (e.key === "ArrowDown") { e.preventDefault(); step(1); }
    if (e.key === "ArrowUp") { e.preventDefault(); step(-1); }
  });
  addEventListener("beforeunload", () => { notesPanel.flush(); });
  try {
    const [info, list, index] = await Promise.all([api("/api/info"), api("/api/files"), api("/api/notes-index")]);
    $("level-name").textContent = info.level;
    document.title = info.level + " | grc-lite";
    files = list.files;
    noted = new Set(index.paths);
    drawFiles();
    if (files.length) openFile(files[0]);
    else $("view").replaceChildren(h("p", { class: "empty" }, "No .md, .csv or .txt files found in this folder."));
  } catch (e) {
    $("view").replaceChildren(h("p", { class: "empty" }, "Could not reach the server. Is grc serve still running?"));
  }
}

start();
