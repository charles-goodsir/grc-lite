// The Check tab: the pre-submit checklist, reminders from your own mistake log, and the finding coach.
import { h } from "./ui.js";
import { loadCoach, loadRecords, store } from "./records.js";

const ICON = { ok: "✓", fix: "✗", warn: "!" };
const KIND_BY_PREFIX = { "C": "criteria", "E": "evidence", "F": "findings", "R": "requests", "K": "risks" };

function ids(nav, list) {
  return h("div", { class: "btns" }, list.map((id) => {
    const kind = KIND_BY_PREFIX[id[0]];
    return /^[A-Z]-\d+$/.test(id) && kind ? h("button", { class: "idlink", onclick: () => nav.openRecord(kind, id) }, id) : h("span", { class: "chip" }, id);
  }));
}

function remembered(key) {
  try { return localStorage.getItem(key) === "1"; } catch (e) { return false; }
}
function remember(key, on) {
  try { localStorage.setItem(key, on ? "1" : "0"); } catch (e) { /* a convenience only */ }
}

export async function checkTab(nav) {
  await loadRecords();
  await loadCoach();
  const c = store.coach;
  const box = h("div", { class: "scrollpane pad" });
  const bad = c.checks.filter((x) => x.status !== "ok").length;
  box.append(h("div", { class: "section" },
    h("h3", {}, bad ? `Before you submit: ${bad} to look at` : "Before you submit: all clear"),
    h("p", {}, "These catch incomplete or inconsistent work. They cannot tell whether a conclusion is right."),
    ...c.checks.map((x) => h("div", { class: "check " + x.status },
      h("span", { class: "mark", "aria-label": x.status }, ICON[x.status]),
      h("div", {}, h("strong", {}, x.label), h("div", { class: "detail" }, x.detail), x.ids.length && x.status !== "ok" ? ids(nav, x.ids) : "")))));

  if (c.reminders.length) {
    box.append(h("div", { class: "section" },
      h("h3", {}, "From your own mistakes"),
      h("p", {}, "Mistakes you have tagged in earlier gradings, most frequent first. Tick each once you have checked it."),
      ...c.reminders.map((r) => {
        const key = `grc-check:${r.tag}`;
        const tick = h("input", { type: "checkbox", id: "rem-" + r.tag.replace(/\W/g, "-") });
        tick.checked = remembered(key);
        tick.addEventListener("change", () => remember(key, tick.checked));
        return h("label", { class: "reminder" }, tick, h("span", {}, h("strong", {}, `${r.tag} (${r.count}x): `), r.reminder));
      })));
  }

  const entries = Object.entries(c.findings);
  box.append(h("div", { class: "section" },
    h("h3", {}, "Finding coach"),
    entries.length ? "" : h("p", { class: "ok" }, "No suggestions on any finding."),
    ...entries.map(([id, issues]) => h("div", { class: "coachfinding" },
      h("button", { class: "idlink", onclick: () => nav.openRecord("findings", id) }, id),
      ...issues.map((i) => h("div", { class: "issue " + i.level }, h("span", { class: "chip" }, i.level === "fix" ? "fix" : "tip"), " " + i.message))))));
  return [box];
}
