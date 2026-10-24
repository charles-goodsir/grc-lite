// The Progress tab: every level's status and score, and which kinds of mistake keep coming back.
import { h, api } from "./ui.js";

function bar(value, max, label) {
  const pct = max ? Math.round((value / max) * 100) : 0;
  const fill = h("div", { class: "bar-fill" });
  fill.style.width = pct + "%"; // set through the DOM: the page's CSP does not allow a style attribute
  return h("div", { class: "bar-track", role: "img", "aria-label": label }, fill);
}

const SVG = "http://www.w3.org/2000/svg";
function svg(tag, attrs, text) {
  const node = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs || {})) node.setAttribute(k, v);
  if (text) node.textContent = text;
  return node;
}

// planted gaps caught, as a percentage, for each graded level in order
function trend(levels) {
  const graded = levels.filter((l) => l.status === "graded" && l.planted.total);
  if (graded.length < 2) return h("p", { class: "empty" }, "Grade two or more levels to see a trend.");
  const w = 300, hgt = 110, left = 28, top = 8, bottom = 22;
  const x = (i) => left + (i * (w - left - 10)) / (graded.length - 1);
  const y = (pct) => top + ((100 - pct) * (hgt - top - bottom)) / 100;
  const chart = svg("svg", { viewBox: `0 0 ${w} ${hgt}`, class: "trend", role: "img", "aria-label": "Planted gaps caught per graded level" });
  for (const pct of [0, 50, 100]) {
    chart.append(svg("line", { x1: left, x2: w - 10, y1: y(pct), y2: y(pct), class: "axis" }), svg("text", { x: 2, y: y(pct) + 3 }, pct + "%"));
  }
  const points = graded.map((l, i) => [x(i), y(Math.round((l.planted.caught / l.planted.total) * 100))]);
  chart.append(svg("polyline", { points: points.map((p) => p.join(",")).join(" "), class: "line" }));
  graded.forEach((l, i) => {
    const pct = Math.round((l.planted.caught / l.planted.total) * 100);
    const dot = svg("circle", { cx: points[i][0], cy: points[i][1], r: 3, class: "dot" });
    dot.append(svg("title", {}, `${l.name}: ${pct}% (${l.planted.caught} of ${l.planted.total})`));
    chart.append(dot, svg("text", { x: points[i][0] - 6, y: hgt - 8 }, l.name.slice(0, 2)));
  });
  return chart;
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
    h("div", { class: "section" }, h("h3", {}, "Caught per graded level"), trend(levels)),
    h("div", { class: "section" }, h("h3", {}, "Mistakes by tag, across levels"), ...tags),
    h("p", { class: "empty" }, "Reads only each level's saved grading. Other levels' data rooms and answer keys are never opened."))];
}
