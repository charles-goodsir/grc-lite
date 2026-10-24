// The level stepper: the playbook's steps, ticked from what you have logged.
import { $, h } from "./ui.js";
import { store } from "./records.js";

export function drawStepper(state, nav) {
  const c = store.criteria;
  const tested = c.some((x) => (x.result || "not tested") !== "not tested") && store.evidence.length > 0;
  const needRequests = c.some((x) => x.result === "can't test");
  const coachFix = store.coach.checks.find((x) => x.key === "coach")?.status === "fix";
  const selected = store.findings.filter((f) => f.status === "selected").length;
  const steps = [
    { label: "Read the scope", done: state.scopeNoted || c.length > 0, tip: "Ticks once you have a note on the scope file or have started the rules.", go: () => nav.openScope() },
    { label: "Pull out the rules", done: c.length > 0, tip: "Add the testable rules from the client's own documents.", go: () => nav.openRecord("criteria") },
    { label: "Test them", done: tested, tip: "Log evidence and give each rule a result.", go: () => nav.openRecord("evidence") },
    { label: "Log what's missing", done: tested && (!needRequests || store.requests.length > 0), tip: "Ask for anything you could not test, and log the request.", go: () => nav.openRecord("requests") },
    { label: "Write findings", done: selected > 0 && !coachFix, tip: "Select findings, fill them in, and clear the coach's fixes.", go: () => nav.openRecord("findings") },
    { label: "Submit and review", done: store.locked, tip: "Run the Check tab, then submit and lock.", go: () => nav.openRecord("export") },
  ];
  const now = steps.findIndex((s) => !s.done);
  $("stepper").replaceChildren(...steps.map((s, i) => h("button", {
    class: (s.done ? "done " : "") + (i === now ? "now" : ""), "data-tip": `${s.label}: ${s.tip}`, onclick: s.go,
    "aria-label": `${i + 1}. ${s.label}${s.done ? " (done)" : i === now ? " (current step)" : ""}`, "aria-current": i === now ? "step" : "false",
  }, h("span", { class: "num" }, s.done ? "✓" : String(i + 1)), h("span", { class: "lab" }, s.label))));
}
