// The Criteria, Evidence, Findings, Requests and Risks tabs, plus Report and Problems.
// Records are drafts: every edit is saved to the YAML files, and what is still missing is
// reported by the server's validator rather than blocked here.
import { h, api, debounce } from "./ui.js";
import { renderMarkdown } from "./md.js";

export const store = { grading: { graded: false, grading: null, tags: [], revealed: false }, locked: false, meta: { name: "", scale: 3, slots: 8, counters: {} }, criteria: [], evidence: [], findings: [], requests: [], risks: [], problems: [] };

let listeners = { problems: () => {}, goto: () => {}, rerender: () => {}, locked: () => {} };
export const on = (handlers) => { listeners = { ...listeners, ...handlers }; };

export async function loadRecords() {
  Object.assign(store, await api("/api/records"));
  store.grading = await api("/api/grading");
  listeners.problems();
  listeners.locked();
}

// ---- save status shared by the tabs ----

let statusEl = null;
function setStatus(text, bad = false) {
  if (!statusEl) return;
  statusEl.className = "status" + (bad ? " bad" : "");
  statusEl.textContent = text;
}

// ---- rating, same bands as the Python report ----

const BANDS = { 3: [[7, "High"], [4, "Medium"], [1, "Low"]], 5: [[20, "Critical"], [13, "High"], [6, "Medium"], [1, "Low"]] };
function rate(likelihood, impact) {
  const l = Number(likelihood), i = Number(impact);
  if (!l || !i) return null;
  const n = l * i;
  return { n, band: BANDS[store.meta.scale].find(([floor]) => n >= floor)[1] };
}

// ---- what each form asks for ----

const RESULTS = ["not tested", "meets", "gap", "can't test"];
const FORMS = {
  criteria: {
    label: "Criteria", add: "+ Add rule",
    fields: [
      ["source", "Source (file, section or rule number)", "text"],
      ["rule", "Rule (quote it)", "area"],
      ["evidence_needed", "Evidence needed (what would prove it?)", "area"],
      ["evidence", "Evidence received", "refs:evidence"],
      ["result", "Result", { select: RESULTS }],
    ],
    badge: (r) => `${r.result || "not tested"}`,
    tone: (r) => ({ meets: "meets", gap: "gap", "can't test": "cant" })[r.result] || "",
    summary: () => `${store.criteria.length} rules: ` + RESULTS.map((o) => `${store.criteria.filter((r) => (r.result || "not tested") === o).length} ${o}`).join(", "),
  },
  evidence: {
    label: "Evidence", add: "+ Add evidence",
    fields: [
      ["date", "Date", "date"],
      ["source", "Source (file or person)", "text"],
      ["type", "Type", { select: ["", "system", "document", "observation", "interview"] }],
      ["shows", "What it shows (facts, numbers)", "area"],
      ["reliability", "Reliability note", "area"],
    ],
    badge: (r) => r.type || "",
    tone: () => "",
    summary: () => `${store.evidence.length} items logged`,
  },
  findings: {
    label: "Findings", add: "+ Add candidate", rerenderOn: "status",
    fields: [
      ["title", "Title (one issue only)", "text"],
      ["status", "Status", { select: ["candidate", "selected", "dropped"] }],
      ["strength", "Evidence strength (strong = counts, several files, rule quoted)", { select: ["", "strong", "medium", "weak"] }],
      ["strength_reason", "Why that strength", "area"],
      ["criteria", "Criteria", "refs:criteria"],
      ["condition", "Condition (what the evidence shows: counts and evidence IDs)", "area"],
      ["cause", "Cause (why it happened, optional)", "area"],
      ["consequence", "Consequence (why it matters)", "area"],
      ["action", "Action (one fix)", "area"],
      ["owner", "Owner (role)", "text"],
      ["due", "Due", "date"],
      ["likelihood", "Likelihood", "score"],
      ["likelihood_reason", "Why that likelihood (one sentence)", "text"],
      ["impact", "Impact", "score"],
      ["impact_reason", "Why that impact (one sentence)", "text"],
      ["control_ref", "Control reference (optional)", "text"],
    ],
    core: ["title", "status", "strength", "strength_reason"],
    badge: (r) => {
      if (r.status === "dropped") return "dropped";
      if (r.status !== "selected") return `candidate${r.strength ? " · " + r.strength : ""}`;
      const x = rate(r.likelihood, r.impact);
      return `selected · ${x ? `${x.n} ${x.band}` : "unrated"}`;
    },
    tone: (r) => {
      if (r.status === "dropped") return "dropped";
      if (r.status !== "selected") return "";
      const x = rate(r.likelihood, r.impact);
      return x ? { Critical: "gap", High: "gap", Medium: "cant", Low: "meets" }[x.band] : "sel";
    },
    summary: () => {
      const n = (s) => store.findings.filter((r) => r.status === s).length;
      const over = n("selected") > store.meta.slots;
      return `${n("candidate")} candidates · ${n("selected")} selected of ${store.meta.slots} slots${over ? " (OVER)" : ""}`;
    },
  },
  requests: {
    label: "Requests", add: "+ Add request",
    fields: [
      ["asked", "Date asked", "date"],
      ["what", "What I asked for", "area"],
      ["asked_who", "Asked who", "text"],
      ["received", "Date received (leave empty while outstanding)", "date"],
      ["evidence", "Evidence it became", "ref:evidence"],
      ["notes", "Notes", "area"],
    ],
    badge: (r) => (r.received ? "received" : "outstanding"),
    tone: (r) => (r.received ? "meets" : "cant"),
    summary: () => `${store.requests.length} requests, ${store.requests.filter((r) => !r.received).length} outstanding`,
  },
  risks: {
    label: "Risks", add: "+ Add risk",
    fields: [
      ["title", "Risk", "text"],
      ["description", "Description", "area"],
      ["owner", "Owner (role)", "text"],
      ["likelihood", "Likelihood", "score"],
      ["likelihood_reason", "Why that likelihood (one sentence)", "text"],
      ["impact", "Impact", "score"],
      ["impact_reason", "Why that impact (one sentence)", "text"],
      ["treatment", "Treatment", { select: ["", "mitigate", "accept", "transfer", "avoid"] }],
      ["status", "Status", { select: ["open", "accepted", "closed"] }],
      ["findings", "Findings", "refs:findings"],
      ["criteria", "Criteria", "refs:criteria"],
    ],
    badge: (r) => {
      const x = rate(r.likelihood, r.impact);
      return `${x ? `${x.n} ${x.band}` : "unrated"} · ${r.treatment || "no treatment"}`;
    },
    tone: (r) => {
      const x = rate(r.likelihood, r.impact);
      return x ? { Critical: "gap", High: "gap", Medium: "cant", Low: "meets" }[x.band] : "sel";
    },
    summary: () => `${store.risks.length} risks`,
  },
};

// Short reminders from the playbook, shown when you press the ? beside a field.
const TIPS = {
  "criteria.source": "Where the rule comes from: the client's own policy, with the file and rule number.",
  "criteria.rule": "Quote the rule as written, so anyone can check it.",
  "criteria.evidence_needed": "What would prove this rule is followed, or not? If it is not in the data room, ask for it and log a request.",
  "criteria.result": "meets, gap or can't test. If evidence is missing, say can't test and log a request.",
  "evidence.shows": "Facts only: what it shows, with numbers. Opinions belong in your findings.",
  "evidence.reliability": "How far can you trust it? For example: exported by the client, not independently verified.",
  "findings.title": "One issue only.",
  "findings.strength": "Strong means counts, several files, and the rule quoted.",
  "findings.criteria": "Criteria: what should be happening (a policy rule, a standard control, a law).",
  "findings.condition": "What the evidence shows, with numbers and the evidence ID.",
  "findings.cause": "Why it happened: no process, no owner, no automation. Optional.",
  "findings.consequence": "Why it matters, in one or two sentences.",
  "findings.action": "The fix, with an owner and a date. One fix.",
  "findings.likelihood": "Rating = likelihood x impact. Scale 1-3: 7-9 High, 4-6 Medium, 1-3 Low. Scale 1-5: 20-25 Critical, 13-19 High, 6-12 Medium, 1-5 Low.",
  "findings.impact": "Rating = likelihood x impact. Scale 1-3: 7-9 High, 4-6 Medium, 1-3 Low. Scale 1-5: 20-25 Critical, 13-19 High, 6-12 Medium, 1-5 Low.",
  "findings.control_ref": "A control number such as an Annex A reference, if the level asks for one. Optional.",
  "requests.received": "Leave empty while you are still waiting. The report lists outstanding requests.",
  "risks.treatment": "Mitigate, accept, transfer or avoid.",
};

// "criteria: Field required" reads better as "criteria is empty"
const friendly = (message) => message.replace(/^(\w+): Field required$/, "$1 is empty").replace(/^Value error, /, "");

// what the grader wrote about a record, once a grading has been imported
const SHEETS = { criteria: ["Criteria"], evidence: ["Evidence"], findings: ["Candidates", "Findings"] };
function graderNotes(kind, id) {
  const notes = store.grading.grading?.notes || [];
  return notes.filter((n) => n.id === id && (SHEETS[kind] || []).includes(n.sheet));
}

function missingFor(id) {
  return store.problems.filter((p) => p.id === id).map((p) => friendly(p.message));
}

function grow(el) {
  if (el.tagName !== "TEXTAREA") return;
  el.style.height = "auto";
  if (el.scrollHeight) el.style.height = el.scrollHeight + "px";
}

function optionLabel(kind, record) {
  const text = record.title || record.source || record.what || record.rule || "";
  return `${record.id} ${text}`.slice(0, 60);
}

// ---- one editable field ----

function control(kind, record, [key, label, type], state, changed) {
  const wrap = h("div", { class: "field" }, h("label", {}, label));
  const tip = TIPS[`${kind}.${key}`];
  if (tip) {
    const note = h("div", { class: "tip", hidden: "" }, tip);
    wrap.append(h("button", { type: "button", class: "tipbtn", "aria-label": "Help for " + label, title: "Help", onclick: () => { note.hidden = !note.hidden; } }, "?"), note);
  }
  const set = (value) => { state[key] = value; changed(key); };
  let input;
  if (typeof type === "object") {
    input = h("select", {}, type.select.map((o) => h("option", { value: o }, o || "–")));
    input.value = state[key] ?? type.select[0];
    input.addEventListener("change", () => set(input.value));
  } else if (type === "score") {
    const options = ["", ...Array.from({ length: store.meta.scale }, (_, i) => String(i + 1))];
    input = h("select", {}, options.map((o) => h("option", { value: o }, o || "–")));
    input.value = state[key] ? String(state[key]) : "";
    input.addEventListener("change", () => set(input.value));
  } else if (type.startsWith("refs:")) {
    const target = type.slice(5);
    input = h("div", { class: "refs" });
    const chosen = new Set(state[key] || []);
    if (!store[target].length) input.append(h("span", { class: "empty" }, `No ${target} yet.`));
    for (const other of store[target]) {
      const box = h("input", { type: "checkbox" });
      box.checked = chosen.has(other.id);
      box.addEventListener("change", () => {
        box.checked ? chosen.add(other.id) : chosen.delete(other.id);
        set([...chosen].sort());
      });
      input.append(h("label", { class: "ref" }, box, optionLabel(target, other)));
    }
    for (const id of chosen) { // keep a reference to something deleted visible, so it can be fixed
      if (!store[target].some((o) => o.id === id)) input.append(h("span", { class: "ref gone" }, `${id} (not found)`));
    }
  } else if (type.startsWith("ref:")) {
    const target = type.slice(4);
    input = h("select", {}, [h("option", { value: "" }, "–"), ...store[target].map((o) => h("option", { value: o.id }, optionLabel(target, o)))]);
    input.value = state[key] || "";
    input.addEventListener("change", () => set(input.value));
  } else {
    input = h(type === "area" ? "textarea" : "input", type === "date" ? { type: "text", placeholder: "YYYY-MM-DD" } : type === "text" ? { type: "text" } : {});
    input.value = state[key] ?? "";
    input.addEventListener("input", () => { set(input.value); grow(input); });
  }
  const id = `f-${record.id}-${key}`;
  if (input.tagName === "DIV") { // a group of checkboxes: name the group by its label
    input.setAttribute("role", "group");
    input.setAttribute("aria-label", label);
  } else {
    input.id = id;
    wrap.firstChild.setAttribute("for", id); // clicking the label focuses the field, and screen readers name it
  }
  if (store.locked) {
    if (input.tagName === "DIV") input.querySelectorAll("input").forEach((box) => { box.disabled = true; });
    else input.disabled = true;
  }
  wrap.append(input);
  return wrap;
}

// ---- one record card ----

function card(kind, record) {
  const form = FORMS[kind];
  const state = { ...record };
  const badge = h("span", { class: "badge-line" });
  const missing = h("div", { class: "missing" });
  const del = h("button", { class: "danger", onclick: () => remove() }, "Delete");
  del.hidden = store.locked;
  const graded = graderNotes(kind, record.id).map((n) =>
    h("div", { class: "grader" }, h("strong", {}, `Grader${n.key_rating ? " (key: " + n.key_rating + ")" : ""}: `), n.note));
  const root = h("div", { class: "card", id: `rec-${record.id}` }, h("h4", {}, badge, del), missing, ...graded);

  function refresh() {
    root.className = "card " + form.tone(state);
    badge.textContent = `${record.id}${form.badge(state) ? "  ·  " + form.badge(state) : ""}`;
    const m = missingFor(record.id);
    missing.textContent = m.length ? "To fix: " + m.join("; ") : "";
  }

  const save = debounce(async () => {
    const fields = Object.fromEntries(Object.entries(state).filter(([k]) => k !== "id"));
    setStatus("Saving...");
    try {
      const result = await api(`/api/records/${kind}/${record.id}`, { method: "PUT", body: JSON.stringify({ fields }) });
      store.problems = result.problems;
      const at = store[kind].findIndex((r) => r.id === record.id);
      if (at >= 0) store[kind][at] = { id: record.id, ...state };
      listeners.problems();
      refresh();
      setStatus("Saved");
    } catch (e) {
      setStatus("NOT SAVED: " + e.message, true);
    }
  }, 450);

  function changed(key) {
    refresh();
    save();
    if (form.rerenderOn === key) save.now().then(() => listeners.rerender());
  }

  async function remove() {
    if (!confirm(`Delete ${record.id}? Its number will not be reused.`)) return;
    save.cancel();
    try {
      const result = await api(`/api/records/${kind}/${record.id}`, { method: "DELETE" });
      store.problems = result.problems;
      store[kind] = store[kind].filter((r) => r.id !== record.id);
      listeners.problems();
      listeners.rerender();
    } catch (e) {
      setStatus("NOT DELETED: " + e.message, true);
    }
  }

  for (const field of form.fields) {
    if (form.core && state.status !== "selected" && !form.core.includes(field[0])) continue;
    const row = control(kind, record, field, state, changed);
    root.append(row);
    const input = row.querySelector("textarea");
    if (input) requestAnimationFrame(() => grow(input));
  }
  refresh();
  return root;
}

// ---- a records tab ----

export async function recordsTab(kind) {
  await loadRecords();
  const form = FORMS[kind];
  const summary = h("div", { class: "summary" });
  const add = h("button", { onclick: async () => {
    try {
      const made = await api(`/api/records/${kind}`, { method: "POST", body: JSON.stringify({ fields: kind === "findings" ? { status: "candidate" } : {} }) });
      store.problems = made.problems;
      store[kind].push(made.record);
      listeners.problems();
      listeners.rerender(made.record.id);
    } catch (e) {
      setStatus("NOT ADDED: " + e.message, true);
    }
  } }, form.add);
  add.disabled = store.locked;
  const top = h("div", { class: "top" }, h("div", { class: "row" }, summary, add));

  let filter = "all";
  if (kind === "findings" || kind === "risks") top.append(scaleRow(kind === "findings" ? (v) => { filter = v; drawCards(); } : null));
  const list = h("div", { class: "cards" });
  function drawCards() {
    list.replaceChildren();
    for (const record of store[kind]) {
      if (kind === "findings" && filter !== "all" && record.status !== filter) continue;
      list.append(card(kind, record));
    }
    if (!store[kind].length) list.append(h("p", { class: "empty pad" }, `No ${form.label.toLowerCase()} yet. Use the button above to add one.`));
    summary.textContent = form.summary();
  }
  drawCards();
  statusEl = h("div", { class: "status" }, "Changes save as you type.");
  return [h("div", { class: "scrollpane" }, top, list), statusEl];
}

function scaleRow(onFilter) {
  const scale = h("select", { "aria-label": "Risk scale" }, [h("option", { value: "3" }, "Scale 1-3"), h("option", { value: "5" }, "Scale 1-5")]);
  scale.value = String(store.meta.scale);
  const slots = h("input", { type: "number", min: "1", max: "50", "aria-label": "Slots", value: String(store.meta.slots) });
  scale.disabled = slots.disabled = store.locked;
  const apply = async () => {
    try {
      Object.assign(store, await api("/api/meta", { method: "PUT", body: JSON.stringify({ name: store.meta.name, scale: Number(scale.value), slots: Number(slots.value) || 8 }) }));
      listeners.problems();
      listeners.rerender();
    } catch (e) {
      setStatus("NOT SAVED: " + e.message, true);
    }
  };
  scale.addEventListener("change", apply);
  slots.addEventListener("change", apply);
  const row = h("div", { class: "row" }, scale, h("label", {}, "Slots ", slots));
  if (onFilter) {
    const f = h("select", { "aria-label": "Filter findings" }, ["all", "candidate", "selected", "dropped"].map((o) => h("option", { value: o }, o === "all" ? "Show all" : o)));
    f.addEventListener("change", () => onFilter(f.value));
    row.append(f);
  }
  return row;
}

// ---- problems and report ----

export async function problemsTab() {
  await loadRecords();
  const box = h("div", { class: "scrollpane pad" });
  if (!store.problems.length) {
    box.append(h("p", {}, "No problems. Everything logged passes the same checks as grc validate."));
  } else {
    box.append(h("p", { class: "summary" }, `${store.problems.length} to fix. Click one to go to it.`));
    for (const problem of store.problems) {
      const kind = problem.file.replace(/\.yaml$/, "");
      const link = FORMS[kind] && problem.id;
      const row = h("div", { class: "problem" }, h("strong", {}, problem.id || problem.file || "Assessment"), " " + friendly(problem.message));
      if (link) {
        row.classList.add("link");
        row.tabIndex = 0;
        const go = () => listeners.goto(kind, problem.id);
        row.addEventListener("click", go);
        row.addEventListener("keydown", (e) => { if (e.key === "Enter") go(); });
      }
      box.append(row);
    }
  }
  statusEl = null;
  return [box];
}

export async function reportTab() {
  await loadRecords();
  const out = h("div", { class: "pad" });
  const name = h("input", { type: "text", value: store.meta.name, "aria-label": "Assessment name", maxlength: "200" });
  const rename = debounce(async () => {
    try {
      Object.assign(store, await api("/api/meta", { method: "PUT", body: JSON.stringify({ name: name.value, scale: store.meta.scale, slots: store.meta.slots }) }));
      setStatus("Saved");
    } catch (e) {
      setStatus("NOT SAVED: " + e.message, true);
    }
  }, 600);
  name.disabled = store.locked;
  name.addEventListener("input", rename);
  const result = await api("/api/report");
  let copy = null;
  if (result.markdown) {
    out.append(renderMarkdown(result.markdown));
    copy = h("button", { onclick: async () => {
      try { await navigator.clipboard.writeText(result.markdown); setStatus("Markdown copied"); }
      catch (e) { setStatus("Copy was blocked by the browser", true); }
    } }, "Copy Markdown");
  } else if (result.problems.length) {
    out.append(h("p", {}, `The report is held back until ${result.problems.length} problem(s) are fixed. See the Problems tab.`));
  } else {
    out.append(h("p", { class: "empty" }, "Nothing to report yet. Add criteria, evidence and findings."));
  }
  statusEl = h("div", { class: "status" }, "Report title saves as you type.");
  const top = h("div", { class: "top" }, h("div", { class: "row" }, h("label", {}, "Title ", name), copy || ""));
  return [h("div", { class: "scrollpane" }, top, out), statusEl];
}

export const KINDS = Object.keys(FORMS);
export const LABELS = Object.fromEntries(KINDS.map((k) => [k, FORMS[k].label]));
