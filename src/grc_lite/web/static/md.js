// A small Markdown renderer. It builds DOM nodes with text only, so file content cannot inject HTML.
import { h } from "./ui.js";

function inline(parent, text) {
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*|\[[^\]]+\]\([^)]*\))/g;
  let last = 0;
  for (const m of text.matchAll(pattern)) {
    if (m.index > last) parent.append(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) parent.append(h("strong", {}, tok.slice(2, -2)));
    else if (tok.startsWith("`")) parent.append(h("code", {}, tok.slice(1, -1)));
    else if (tok.startsWith("[")) parent.append(tok.slice(1, tok.indexOf("]"))); // links show their text only
    else parent.append(h("em", {}, tok.slice(1, -1)));
    last = m.index + tok.length;
  }
  if (last < text.length) parent.append(text.slice(last));
}

function cells(line) {
  const parts = line.trim().replace(/^\||\|$/g, "").split(/(?<!\\)\|/);
  return parts.map((c) => c.trim().replace(/\\\|/g, "|"));
}

export function renderMarkdown(text) {
  const root = h("div", { class: "md" });
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (/^```/.test(line)) {
      const code = [];
      i++;
      while (i < lines.length && !/^```/.test(lines[i])) code.push(lines[i++]);
      i++;
      root.append(h("pre", {}, h("code", {}, code.join("\n"))));
    } else if (/^#{1,6}\s/.test(line)) {
      const node = h("h" + line.match(/^#+/)[0].length);
      inline(node, line.replace(/^#+\s*/, ""));
      root.append(node);
      i++;
    } else if (/^\s*\|/.test(line) && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1] || "")) {
      const table = h("table");
      const head = h("tr");
      for (const c of cells(line)) { const th = h("th"); inline(th, c); head.append(th); }
      table.append(h("thead", {}, head));
      i += 2;
      const body = h("tbody");
      while (i < lines.length && /^\s*\|/.test(lines[i])) {
        const row = h("tr");
        for (const c of cells(lines[i])) { const td = h("td"); inline(td, c); row.append(td); }
        body.append(row);
        i++;
      }
      table.append(body);
      root.append(h("div", { class: "scroll" }, table));
    } else if (/^\s*([-*]|\d+\.)\s+/.test(line)) {
      const list = h(/^\s*\d/.test(line) ? "ol" : "ul");
      while (i < lines.length && /^\s*([-*]|\d+\.)\s+/.test(lines[i])) {
        const item = h("li");
        inline(item, lines[i].replace(/^\s*([-*]|\d+\.)\s+/, ""));
        list.append(item);
        i++;
      }
      root.append(list);
    } else if (/^>\s?/.test(line)) {
      const quote = h("blockquote");
      const parts = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) parts.push(lines[i++].replace(/^>\s?/, ""));
      inline(quote, parts.join(" "));
      root.append(quote);
    } else if (/^(-{3,}|\*{3,})\s*$/.test(line)) {
      root.append(h("hr"));
      i++;
    } else if (line.trim() === "") {
      i++;
    } else {
      const para = h("p");
      const parts = [];
      while (i < lines.length && lines[i].trim() !== "" && !/^(#{1,6}\s|```|>|\s*([-*]|\d+\.)\s+|\s*\|)/.test(lines[i])) {
        parts.push(lines[i++]);
      }
      if (!parts.length) parts.push(lines[i++]);
      inline(para, parts.join(" "));
      root.append(para);
    }
  }
  return root;
}
