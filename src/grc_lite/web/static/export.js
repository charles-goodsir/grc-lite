// The Export tab: downloads, importing a notes-tool file, and submitting a level.
import { h, api, download } from "./ui.js";
import { loadRecords, store } from "./records.js";

function note(text, bad = false) {
  return h("div", { class: "note" + (bad ? " bad" : "") }, text);
}

function downloads() {
  const out = h("div", { class: "section" }, h("h3", {}, "Export"), h("p", {}, "Everything you have logged, in the format you need."));
  const message = h("div");
  const get = (name, label) => h("button", { onclick: async () => {
    try { await download("/api/export/" + name, name); message.replaceChildren(note(`Saved ${name}`)); }
    catch (e) { message.replaceChildren(note(`${name}: ${e.message}`, true)); }
  } }, label);
  out.append(
    h("div", { class: "btns" },
      get("submission.md", "Submission (Markdown)"),
      get("report.md", "Report (Markdown)"),
      get("report.html", "Report (printable HTML)"),
      get("records.xlsx", "Excel workbook"),
      get("records.zip", "Backup (ZIP)")),
    h("p", {}, "CSV, one file per tab:"),
    h("div", { class: "btns" }, ["criteria", "evidence", "findings", "requests", "risks"].map((k) => get(k + ".csv", k + ".csv"))),
    message,
  );
  return out;
}

function importer() {
  const out = h("div", { class: "section" }, h("h3", {}, "Import a notes file"), h("p", {}, "Fill an empty assessment from a notes.md downloaded from the notes tool, including your per-file notes. Anything that cannot be mapped is listed, and nothing is guessed."));
  const message = h("div");
  const pick = h("input", { type: "file", accept: ".md,.txt,text/markdown,text/plain", "aria-label": "notes.md file" });
  pick.disabled = store.locked;
  pick.addEventListener("change", async () => {
    const file = pick.files[0];
    if (!file) return;
    try {
      const text = await file.text();
      const done = await api("/api/import-notes", { method: "POST", body: JSON.stringify({ text, name: file.name.replace(/\.[^.]+$/, "") }) });
      await loadRecords();
      const lines = [`Imported ${done.criteria.length} criteria, ${done.evidence.length} evidence, ${done.findings.length} findings, and ${done.notes_imported} file notes.`];
      for (const warning of done.warnings) lines.push("Warning: " + warning);
      message.replaceChildren(...lines.map((l) => note(l, l.startsWith("Warning"))));
    } catch (e) {
      message.replaceChildren(note("Import failed: " + e.message, true));
    }
    pick.value = "";
  });
  out.append(pick, message);
  return out;
}

async function submitting(refresh) {
  const out = h("div", { class: "section" }, h("h3", {}, "Submit this level"));
  const status = await api("/api/submission");
  if (status.submitted) {
    out.append(
      h("p", {}, `Submitted ${status.submitted_at}. Your work is locked.`),
      note(`Send this file to Claude to be reviewed: ${status.file}`),
      note(h("span", {}, "SHA-256: ", h("code", { class: "hash" }, status.sha256))),
      note(status.file_intact && status.matches_records
        ? "The file and your records still match what you submitted."
        : "Warning: the submission file or your records changed after you submitted.", !(status.file_intact && status.matches_records)),
      h("p", {}, "To reopen the level, delete submitted.yaml in the assessment folder. The lock is a commitment to yourself, not a security control."),
    );
    return out;
  }
  const problems = store.problems.length;
  const agree = h("input", { type: "checkbox", id: "agree" });
  const button = h("button", { class: "primary", disabled: "" }, "Submit and lock");
  agree.addEventListener("change", () => { button.disabled = !agree.checked; });
  const message = h("div");
  button.addEventListener("click", async () => {
    try {
      const done = await api("/api/submit", { method: "POST", body: "{}" });
      await loadRecords();
      await refresh();
      return done;
    } catch (e) {
      message.replaceChildren(note("Could not submit: " + e.message, true));
    }
  });
  out.append(
    h("p", {}, "Writes submission.md, records a SHA-256 of it, and locks your work so you cannot change answers after seeing how they are graded. Then send the file to Claude for review."),
    problems ? note(`${problems} problem(s) are still open. You can submit anyway, and the reviewer will see them.`, true) : h("span"),
    h("label", {}, agree, " I understand this locks my work"),
    h("div", { class: "btns pad0" }, button),
    message,
  );
  return out;
}

export async function exportTab(refresh) {
  await loadRecords();
  return [h("div", { class: "scrollpane pad" }, downloads(), importer(), await submitting(refresh))];
}
