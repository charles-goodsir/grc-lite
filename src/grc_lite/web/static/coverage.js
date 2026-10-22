// The Coverage tab: where the assessment is thin.
import { h, api } from "./ui.js";

export async function coverageTab(nav) {
  const c = await api("/api/coverage");
  const link = (kind, id) => h("button", { class: "idlink", onclick: () => nav.openRecord(kind, id) }, id);
  const section = (title, why, ids, kind) => h("div", { class: "section" },
    h("h3", {}, `${title} (${ids.length})`),
    h("p", {}, why),
    ids.length ? h("div", { class: "btns" }, ids.map((id) => link(kind, id))) : h("p", { class: "ok" }, "None. Nothing to fix here."));

  const waiting = c.outstanding_requests;
  const matrix = c.matrix;
  const linked = new Set(matrix.links.map(([a, b]) => `${a}|${b}`));
  const grid = h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, ""), matrix.evidence.map((e) => h("th", {}, e)))),
    h("tbody", {}, matrix.criteria.map((id) => h("tr", {}, h("th", {}, id), matrix.evidence.map((e) => h("td", { class: "cell" }, linked.has(`${id}|${e}`) ? "●" : ""))))));

  return [h("div", { class: "scrollpane pad" },
    section("Rules with no evidence", "A rule you have not backed with any evidence yet.", c.criteria_without_evidence, "criteria"),
    section("Rules not tested", "Result is still 'not tested'.", c.not_tested, "criteria"),
    section("Gaps with no finding", "A rule marked gap that no live finding covers. Dropped findings do not count.", c.gaps_without_finding, "criteria"),
    section("Selected findings on weaker evidence", "Selected, but the evidence strength is weak, medium or not set.", c.weak_selected, "findings"),
    section("Findings still undecided", "Candidates you have not selected or dropped.", c.undecided, "findings"),
    section("Evidence nothing uses", "Evidence not linked to any rule or request.", c.evidence_unlinked, "evidence"),
    h("div", { class: "section" },
      h("h3", {}, `Requests still waiting (${waiting.length})`),
      h("p", {}, "Asked for, not received yet."),
      waiting.length ? waiting.map((r) => h("div", { class: "problem link", tabindex: "0", onclick: () => nav.openRecord("requests", r.id) },
        h("strong", {}, r.id), ` ${r.what} (asked ${r.asked}${r.days != null ? `, ${r.days} days ago` : ""})`)) : h("p", { class: "ok" }, "None. Nothing to fix here.")),
    matrix.criteria.length && matrix.evidence.length ? h("div", { class: "section" }, h("h3", {}, "Rules and the evidence behind them"), h("div", { class: "scroll" }, grid)) : "",
  )];
}
