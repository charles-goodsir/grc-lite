// "Next up": one line saying what to do next, worked out from the records you already have.
// The order follows the playbook: rules, then testing them, then findings.
import { $, h } from "./ui.js";
import { store } from "./records.js";

const short = (text, n = 70) => (text.length > n ? text.slice(0, n - 1) + "…" : text);

function suggestion() {
  if (store.locked) return null;
  const rules = store.criteria;
  if (!rules.length) return { text: "Add your first rule. Select a rule in a file and press 'Add selected text as a criterion'." };

  const untested = rules.filter((r) => (r.result || "not tested") === "not tested");
  if (untested.length) {
    const next = untested[0];
    return { text: `${untested.length} of ${rules.length} rules not tested. Next: ${next.id} ${short(next.rule || "")}`, kind: "criteria", id: next.id };
  }

  const covered = new Set(store.findings.filter((f) => f.status !== "dropped").flatMap((f) => f.criteria || []));
  const bare = rules.filter((r) => r.result === "gap" && !covered.has(r.id));
  if (bare.length) return { text: `${bare.length} gap${bare.length > 1 ? "s" : ""} with no finding. Next: ${bare[0].id} ${short(bare[0].rule || "")}`, kind: "criteria", id: bare[0].id };

  const undecided = store.findings.filter((f) => f.status === "candidate");
  if (undecided.length) return { text: `${undecided.length} candidate finding${undecided.length > 1 ? "s" : ""} to select or drop. Next: ${undecided[0].id} ${short(undecided[0].title || "")}`, kind: "findings", id: undecided[0].id };

  if (store.problems.length) return { text: `${store.problems.length} to fix on the Problems tab.`, kind: "problems" };
  return { text: "Nothing obvious left. Run the Check tab, then submit." , kind: "check" };
}

export function drawNextUp(nav) {
  const s = suggestion();
  const box = $("nextup");
  box.hidden = !s;
  if (!s) return;
  const label = h("span", { class: "nu-label" }, "Next up");
  box.replaceChildren(label, s.kind
    ? h("button", { class: "nu-text", onclick: () => nav.openRecord(s.kind, s.id) }, s.text)
    : h("span", { class: "nu-text" }, s.text));
}
