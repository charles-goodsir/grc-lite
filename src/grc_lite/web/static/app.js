import { $, h, api } from "./ui.js";
import { renderMarkdown } from "./md.js";
import { renderCsv } from "./csv.js";
import { KINDS, LABELS, on, problemsTab, recordsTab, reportTab, store } from "./records.js";

// Everything shown from a file is built with DOM text nodes, never innerHTML,
// so a hostile line in a data-room file cannot run script in the page.

// ---- file list and viewer ----

let files = [], current = null, noted = new Set();

function drawFiles() {
  const q = $("filter").value.toLowerCase();
  const list = $("files");
  list.replaceChildren();
  for (const path of files.filter((p) => p.toLowerCase().includes(q))) {
    list.append(h("div", { class: "item" + (path === current ? " on" : ""), role: "option", tabindex: "0", "aria-selected": String(path === current), onclick: () => openFile(path), onkeydown: (e) => { if (e.key === "Enter") openFile(path); } },
      h("span", { class: "dot" + (noted.has(path) ? " has" : ""), title: "Has notes" }), path));
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

// ---- notes tab ----

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

// ---- tabs ----

const TABS = [
  { id: "notes", label: "Notes", render: async () => notesPanel.element() },
  ...KINDS.map((kind) => ({ id: kind, label: LABELS[kind], render: () => recordsTab(kind) })),
  { id: "report", label: "Report", render: reportTab },
  { id: "problems", label: "Problems", render: problemsTab },
];
let activeTab = "notes";

async function showTab(id, focusId) {
  activeTab = id;
  const tab = TABS.find((t) => t.id === id);
  [...$("tabs").children].forEach((b) => b.setAttribute("aria-selected", String(b.dataset.id === id)));
  try {
    $("panel").replaceChildren(...(await tab.render()));
  } catch (e) {
    $("panel").replaceChildren(h("p", { class: "empty pad" }, "Could not load this tab: " + e.message));
  }
  if (focusId) {
    const target = document.getElementById("rec-" + focusId);
    if (target) {
      target.scrollIntoView({ block: "center" });
      target.classList.add("flash");
    }
  }
}

function problemCount() {
  const n = store.problems.length;
  const button = document.querySelector('#tabs button[data-id="problems"]');
  if (button) button.textContent = n ? `Problems (${n})` : "Problems";
}

on({
  problems: problemCount,
  goto: (kind, id) => showTab(kind, id),
  rerender: (focusId) => showTab(activeTab, focusId),
});

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
    const [info, list, index, records] = await Promise.all([api("/api/info"), api("/api/files"), api("/api/notes-index"), api("/api/records")]);
    Object.assign(store, records);
    problemCount();
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
