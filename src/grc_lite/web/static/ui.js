// Small DOM and fetch helpers. Nothing here ever uses innerHTML.

const token = document.querySelector('meta[name="grc-token"]').content;

export const $ = (id) => document.getElementById(id);

export function h(tag, attrs, ...kids) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const kid of kids.flat()) node.append(kid);
  return node;
}

export async function api(path, options = {}) {
  const method = options.method || "GET";
  const headers = { "X-Grc-Token": token };
  if (method !== "GET") headers["Content-Type"] = "application/json"; // the server only accepts JSON writes
  const res = await fetch(path, { ...options, method, headers });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch (e) { /* no body */ }
    throw new Error(`${res.status} ${detail}`.trim());
  }
  return res.json();
}

export function debounce(fn, ms) {
  let timer = null;
  const wrapped = (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), ms); };
  wrapped.now = (...args) => { clearTimeout(timer); return fn(...args); };
  wrapped.cancel = () => clearTimeout(timer);
  return wrapped;
}

// Download a file the server builds. A plain link cannot send the token, so fetch it and save the blob.
export async function download(path, filename) {
  const res = await fetch(path, { headers: { "X-Grc-Token": token } });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json()).detail || ""; } catch (e) { /* no body */ }
    throw new Error(detail || `download failed (${res.status})`);
  }
  const url = URL.createObjectURL(await res.blob());
  const link = h("a", { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}
