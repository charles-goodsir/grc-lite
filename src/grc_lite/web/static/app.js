import { $, h, api } from "./ui.js";
import { renderMarkdown } from "./md.js";
import { renderCsv } from "./csv.js";
import { searchTab } from "./search.js";
import { checkTab } from "./check.js";
import { coverageTab } from "./coverage.js";
import { exportTab } from "./export.js";
import { gradingTab } from "./grading.js";
import { initLayout } from "./layout.js";
import { progressTab } from "./progress.js";
import { drawStepper } from "./stepper.js";
import { KINDS, LABELS, loadCoach, on, problemsTab, recordsTab, reportTab, store } from "./records.js";

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

const today = () => new Date().toLocaleDateString("sv-SE"); // local date as YYYY-MM-DD

async function addEvidence(fields) {
  if (store.locked) { alert("This level is submitted and locked."); return; }
  try {
    const made = await api("/api/records/evidence", { method: "POST", body: JSON.stringify({ fields }) });
    store.problems = made.problems;
    store.evidence.push(made.record);
    problemCount();
    await showTab("evidence", made.record.id);
  } catch (e) {
    alert("Could not add the evidence: " + e.message);
  }
}

function selectedText() {
  const sel = getSelection();
  if (!sel || sel.isCollapsed || !$("view").contains(sel.anchorNode)) return "";
  return sel.toString().trim().slice(0, 1000);
}

function viewToolbar(path, kind) {
  const button = h("button", { disabled: "", onmousedown: (e) => e.preventDefault(), onclick: () => {
    const text = selectedText();
    if (text) addEvidence({ date: today(), source: path, type: kind === "csv" ? "system" : "document", shows: `"${text}"` });
  } }, "Add selected text as evidence");
  const update = () => { button.disabled = !selectedText() || store.locked; };
  document.addEventListener("selectionchange", update);
  return h("div", { class: "viewbar" }, button, h("span", { class: "count" }, "Select text in the file, then add it as an evidence entry."));
}

async function openFile(path) {
  await notesPanel.flush();
  current = path;
  drawFiles();
  const view = $("view");
  try {
    const file = await api("/api/file?path=" + encodeURIComponent(path));
    const content = file.kind === "md" ? renderMarkdown(file.text)
      : file.kind === "csv" ? renderCsv(file.text, { onCite: ({ query, shown, total }) => addEvidence({
        date: today(), source: path, type: "system",
        shows: query ? `${shown} of ${total} rows in ${path} contain "${query}".` : `${total} rows in ${path}.`,
        reliability: "Counted in the study app from the file as given." }) })
      : h("pre", { class: "plain" }, file.text);
    view.replaceChildren(viewToolbar(path, file.kind), content);
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
      refreshStepper();
    } catch (e) {
      status.className = "status bad";
      status.textContent = "NOT SAVED. Check the terminal where grc serve is running.";
    }
  }
  box.addEventListener("input", () => { dirty = true; status.textContent = "Typing..."; clearTimeout(timer); timer = setTimeout(save, 500); });
  return {
    setLocked(locked) { box.readOnly = locked; },
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
  { id: "search", label: "Search", render: async () => searchTab(nav) },
  { id: "coverage", label: "Coverage", render: () => coverageTab(nav) },
  { id: "check", label: "Check", render: () => checkTab(nav) },
  { id: "report", label: "Report", render: reportTab },
  { id: "export", label: "Export", render: () => exportTab(() => showTab("export")) },
  { id: "grading", label: "Grading", render: () => gradingTab(nav) },
  { id: "progress", label: "Progress", render: progressTab },
  { id: "problems", label: "Problems", render: problemsTab },
];
const GROUPS = [
  ["Work", ["notes", "criteria", "evidence", "findings", "requests", "risks"]],
  ["Review", ["check", "problems", "coverage", "report"]],
  ["Find", ["search"]],
  ["Finish", ["export", "grading", "progress"]],
];
let activeTab = "notes";
const nav = {
  refreshFiles: async () => {
    const [list, index] = await Promise.all([api("/api/files"), api("/api/notes-index")]);
    files = list.files;
    noted = new Set(index.paths);
    drawFiles();
  },
  rerender: () => showTab(activeTab),
  openFile: (path) => openFile(path),
  openNotes: async (path) => { await openFile(path); await showTab("notes"); },
  openRecord: (kind, id) => showTab(kind, id),
};

const groupOf = (id) => GROUPS.find(([, ids]) => ids.includes(id))[0];
const lastInGroup = {};

function showGroup(name) {
  document.querySelectorAll("#groups button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.group === name)));
  document.querySelectorAll("#tabs button").forEach((b) => { b.hidden = groupOf(b.dataset.id) !== name; });
}

async function showTab(id, focusId) {
  activeTab = id;
  lastInGroup[groupOf(id)] = id;
  showGroup(groupOf(id));
  const tab = TABS.find((t) => t.id === id);
  document.querySelectorAll("#tabs button").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.id === id)));
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

const scopePath = () => files.find((p) => /(^|\/)01-scope\.md$/i.test(p));
function refreshStepper() {
  drawStepper({ scopeNoted: noted.has(scopePath()) }, {
    openScope: () => { const path = scopePath(); if (path) openFile(path); },
    openRecord: (kind) => showTab(kind),
  });
}

function reviewBadge() {
  const badge = document.querySelector('#groups [data-badge="Review"]');
  if (!badge) return;
  const checks = store.criteria.length ? store.coach.checks.filter((x) => x.status !== "ok").length : 0;
  const n = store.problems.length + checks;
  badge.textContent = String(n);
  badge.hidden = !n;
}

function problemCount() {
  const n = store.problems.length;
  const button = document.querySelector('#tabs button[data-id="problems"]');
  if (button) button.textContent = n ? `Problems (${n})` : "Problems";
  reviewBadge();
  refreshStepper();
}

function updateLock() {
  const bar = $("lockbar");
  bar.hidden = !store.locked;
  bar.textContent = store.locked ? "Submitted and locked. Editing is off; reading and export still work." : "";
  notesPanel.setLocked(store.locked);
  refreshStepper();
}

function checkCount() {
  // nothing to check until the first rule exists, so an empty level does not show a count
  const n = store.criteria.length ? store.coach.checks.filter((x) => x.status !== "ok").length : 0;
  const button = document.querySelector('#tabs button[data-id="check"]');
  if (button) button.textContent = n ? `Check (${n})` : "Check";
  reviewBadge();
  refreshStepper();
}

on({
  coach: checkCount,
  problems: problemCount,
  locked: updateLock,
  goto: (kind, id) => showTab(kind, id),
  rerender: (focusId) => showTab(activeTab, focusId),
});

// ---- start ----

async function start() {
  for (const [group, ids] of GROUPS) {
    $("groups").append(h("button", { "data-group": group, "aria-pressed": "false", onclick: () => showTab(lastInGroup[group] || ids[0]) },
      group, h("span", { class: "badge", "data-badge": group, hidden: "" })));
    for (const id of ids) {
      const tab = TABS.find((t) => t.id === id);
      $("tabs").append(h("button", { role: "tab", "data-id": tab.id, onclick: () => showTab(tab.id) }, tab.label));
    }
  }
  initLayout();
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
    await loadCoach().catch(() => {}); // so the stepper does not tick "Write findings" before the coach has looked
    problemCount();
    updateLock();
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
