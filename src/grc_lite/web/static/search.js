// The Search tab: files you can see, your notes and your records.
import { h, api } from "./ui.js";

export function searchTab(nav) {
  const input = h("input", { type: "search", placeholder: "Search files, notes and records", "aria-label": "Search", minlength: "2", maxlength: "100" });
  const out = h("div", { class: "pad" }, h("p", { class: "empty" }, "Type at least two characters and press Enter."));

  function group(title, hits, render) {
    if (!hits.length) return [];
    return [h("h3", {}, `${title} (${hits.length})`), ...hits.map(render)];
  }
  const row = (label, snippet, onclick) => h("div", { class: "hit", tabindex: "0", role: "button", onclick, onkeydown: (e) => { if (e.key === "Enter") onclick(); } }, h("strong", {}, label), h("span", { class: "snip" }, snippet));

  async function run() {
    const q = input.value.trim();
    if (q.length < 2) { out.replaceChildren(h("p", { class: "empty" }, "Type at least two characters.")); return; }
    try {
      const { hits, truncated } = await api("/api/search?q=" + encodeURIComponent(q));
      if (!hits.length) { out.replaceChildren(h("p", { class: "empty" }, "No matches.")); return; }
      out.replaceChildren(
        ...group("In files", hits.filter((x) => x.kind === "file"), (x) => row(`${x.path}:${x.line}`, x.snippet, () => nav.openFile(x.path))),
        ...group("In your notes", hits.filter((x) => x.kind === "note"), (x) => row(`${x.path}:${x.line}`, x.snippet, () => nav.openNotes(x.path))),
        ...group("In your records", hits.filter((x) => x.kind === "record"), (x) => row(`${x.id} (${x.field})`, x.snippet, () => nav.openRecord(x.record, x.id))),
        truncated ? h("p", { class: "empty" }, "Showing the first 100 matches. Narrow the search to see the rest.") : "",
      );
    } catch (e) {
      out.replaceChildren(h("p", { class: "empty" }, "Search failed: " + e.message));
    }
  }
  input.addEventListener("keydown", (e) => { if (e.key === "Enter") run(); });
  return [h("div", { class: "scrollpane" }, h("div", { class: "top" }, input), out)];
}
