// The Grading tab: import the grading file, see the scoreboard, and keep a mistake log.
import { h, api } from "./ui.js";
import { loadRecords, store } from "./records.js";

const OUTCOME = { caught: "Caught", rated_low: "Caught, rated too low", rated_high: "Caught, rated too high", missed: "Missed", other: "Other" };

function table(headers, rows) {
  return h("div", { class: "scroll" }, h("table", {}, h("thead", {}, h("tr", {}, headers.map((x) => h("th", {}, x)))), h("tbody", {}, rows.map((r) => h("tr", {}, r.map((c) => h("td", {}, c)))))));
}

function stat(label, value) {
  return h("div", { class: "stat" }, h("div", { class: "num" }, String(value)), h("div", { class: "lab" }, label));
}

function importer(nav, graded) {
  const message = h("div");
  const pick = h("input", { type: "file", accept: ".md,.txt,text/markdown,text/plain", "aria-label": "Grading file" });
  const send = async (text, name, replace) => api("/api/grading", { method: "POST", body: JSON.stringify({ text, name, replace }) });
  pick.addEventListener("change", async () => {
    const file = pick.files[0];
    if (!file) return;
    const text = await file.text();
    try {
      try {
        await send(text, file.name, false);
      } catch (e) {
        if (!String(e.message).includes("already has a grading") || !confirm("This level already has a grading. Replace it? Tags you set on repeated mistakes are kept.")) throw e;
        await send(text, file.name, true);
      }
      await nav.refreshFiles();
      await nav.rerender();
    } catch (e) {
      message.replaceChildren(h("div", { class: "note bad" }, "Import failed: " + e.message));
    }
    pick.value = "";
  });
  return h("div", { class: "section" },
    h("h3", {}, graded ? "Replace the grading" : "Import the grading"),
    h("p", {}, graded ? "Pick a newer grading file to replace this one." : "After the review, pick the grading file you were sent. Nothing in it is guessed: anything that does not fit is listed."),
    pick, message);
}

export async function gradingTab(nav) {
  await loadRecords();
  const box = h("div", { class: "scrollpane pad" });
  if (!store.locked) {
    box.append(h("div", { class: "section" }, h("h3", {}, "Grading"), h("p", {}, "Submit your level first (Export tab), send the submission for review, then come back here to import the grading.")));
    return [box];
  }
  const state = store.grading;
  if (!state.graded) {
    box.append(importer(nav, false));
    return [box];
  }
  const g = state.grading;
  const caught = g.planted.filter((p) => ["caught", "rated_low", "rated_high"].includes(p.outcome)).length;
  const offRating = g.planted.filter((p) => ["rated_low", "rated_high"].includes(p.outcome)).length;
  box.append(
    h("div", { class: "section" }, h("h3", {}, g.title), h("p", {}, `Imported ${g.imported_at} from ${g.source || "a file"}. The answer key and graded files are now in the file list.`)),
    h("div", { class: "stats" }, stat("planted gaps", g.planted.length), stat("caught", caught), stat("missed", g.planted.length - caught), stat("rated off", offRating)),
    ...(g.warnings.length ? [h("div", { class: "note bad" }, "Not read from the file: " + g.warnings.join("; "))] : []),
    h("div", { class: "section" }, h("h3", {}, "Planted items"),
      table(["#", "Planted gap", "Result", "Yours", "Key", "Finding"],
        g.planted.map((p) => [p.number, p.gap, h("span", { class: "outcome " + p.outcome }, p.result || OUTCOME[p.outcome]), p.your_rating, p.key_rating, p.finding]))),
    ...[["Grading summary", g.summary], ["Done well", g.done_well], ["For next time", g.next_time]].map(([title, rows]) =>
      rows.length ? h("div", { class: "section" }, h("h3", {}, title), table(["Point", "Detail"], rows.map((r) => [r.point, r.detail]))) : ""),
    ...(g.added.length ? [h("div", { class: "section" }, h("h3", {}, "Findings you missed"), h("p", {}, "Written by the grader from the answer key. They are not added to your records."),
      ...g.added.map((a) => h("details", {}, h("summary", {}, `${a.id}: ${a.title}`), h("pre", { class: "plain" }, a.text))))] : []),
  );

  // mistake log: tags are suggestions you can change
  const counts = {};
  for (const m of g.mistakes) counts[m.tag] = (counts[m.tag] || 0) + 1;
  const log = h("div", { class: "section" },
    h("h3", {}, `Mistake log (${g.mistakes.length})`),
    h("p", {}, "Each miss and each \"for next time\" point. Tags marked as suggestions come from simple keyword rules; change any that are wrong."),
    h("div", { class: "btns" }, Object.entries(counts).map(([tag, n]) => h("span", { class: "chip" }, `${tag}: ${n}`))),
  );
  const status = h("div", { class: "status" }, "");
  const rows = g.mistakes.map((m) => {
    const select = h("select", { "aria-label": `Tag for ${m.id}` }, state.tags.map((t) => h("option", { value: t }, t)));
    select.value = m.tag;
    select.addEventListener("change", async () => {
      try { await api(`/api/grading/mistakes/${m.id}`, { method: "PUT", body: JSON.stringify({ tag: select.value }) }); status.textContent = "Saved"; status.className = "status"; }
      catch (e) { status.textContent = "NOT SAVED: " + e.message; status.className = "status bad"; }
    });
    return [m.id, m.source, m.text, select];
  });
  log.append(table(["ID", "Source", "What", "Tag"], rows), status);
  box.append(log, importer(nav, true));
  return [box];
}
