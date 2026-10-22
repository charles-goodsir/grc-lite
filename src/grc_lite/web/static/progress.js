// The Progress tab: every level's status and score, and which kinds of mistake keep coming back.
import { h, api } from "./ui.js";

function bar(value, max, label) {
  const pct = max ? Math.round((value / max) * 100) : 0;
  return h("div", { class: "bar-track", role: "img", "aria-label": label }, h("div", { class: "bar-fill", style: `width:${pct}%` }));
}

export async function progressTab() {
  const { levels, totals } = await api("/api/progress");
  const pct = totals.planted ? Math.round((totals.caught / totals.planted) * 100) : 0;
  const topTag = Object.keys(totals.mistakes)[0];

  const rows = levels.map((lv) => {
    const p = lv.planted;
    return h("tr", { class: lv.current ? "here" : "" },
      h("td", {}, lv.name, lv.current ? h("span", { class: "chip" }, "this level") : ""),
      h("td", {}, h("span", { class: "status-badge " + lv.status.replace(" ", "-") }, lv.status), lv.error ? h("div", { class: "empty" }, lv.error) : ""),
      h("td", {}, p ? `${p.caught} of ${p.total}` : "-"),
      h("td", {}, p ? String(p.rated_off) : "-"),
      h("td", { class: "barcell" }, p ? bar(p.caught, p.total, `${p.caught} of ${p.total} caught`) : ""));
  });
  const table = h("div", { class: "scroll" }, h("table", {},
    h("thead", {}, h("tr", {}, ["Level", "Status", "Caught", "Rated off", ""].map((x) => h("th", {}, x)))),
    h("tbody", {}, rows)));

  const entries = Object.entries(totals.mistakes);
  const max = entries.length ? entries[0][1] : 0;
  const tags = entries.length
    ? entries.map(([tag, n]) => h("div", { class: "tagrow" }, h("span", { class: "tagname" }, tag), bar(n, max, `${n} mistakes tagged ${tag}`), h("span", { class: "count" }, String(n))))
    : [h("p", { class: "empty" }, "No graded levels yet. Mistakes appear here once a grading is imported.")];

  return [h("div", { class: "scrollpane pad" },
    h("div", { class: "stats" },
      h("div", { class: "stat" }, h("div", { class: "num" }, String(totals.graded)), h("div", { class: "lab" }, "levels graded")),
      h("div", { class: "stat" }, h("div", { class: "num" }, totals.planted ? `${pct}%` : "-"), h("div", { class: "lab" }, totals.planted ? `${totals.caught} of ${totals.planted} planted gaps caught` : "no graded levels")),
      h("div", { class: "stat" }, h("div", { class: "num small" }, topTag || "-"), h("div", { class: "lab" }, "most common mistake"))),
    h("div", { class: "section" }, h("h3", {}, "Levels"), table),
    h("div", { class: "section" }, h("h3", {}, "Mistakes by tag, across levels"), ...tags),
    h("p", { class: "empty" }, "Reads only each level's saved grading. Other levels' data rooms and answer keys are never opened."))];
}
