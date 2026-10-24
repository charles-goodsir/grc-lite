// Page layout: draggable panel widths, hiding the side panels, reading mode and the theme toggle.
// Saved choices live in localStorage as a convenience; the page works without it.
import { $ } from "./ui.js";

const KEY = "grc-layout";
const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; } };
const save = (patch) => { try { localStorage.setItem(KEY, JSON.stringify({ ...read(), ...patch })); } catch (e) { /* not saved */ } };
const clamp = (n, lo, hi) => Math.min(hi, Math.max(lo, n));

const THEMES = ["system", "light", "dark"];

function applyTheme(theme) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  $("theme").textContent = "Theme: " + theme;
}

function splitter(handle, cssVar, key, width) {
  const root = document.documentElement;
  const set = (px) => { root.style.setProperty(cssVar, px + "px"); };
  const limits = key === "side" ? [160, 520] : [300, 760];
  handle.addEventListener("pointerdown", (event) => {
    handle.setPointerCapture(event.pointerId);
    handle.classList.add("drag");
    const move = (e) => set(clamp(width(e.clientX), ...limits));
    const stop = (e) => {
      handle.classList.remove("drag");
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", stop);
      save({ [key]: clamp(width(e.clientX), ...limits) });
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", stop);
  });
  handle.addEventListener("keydown", (e) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    const current = parseFloat(getComputedStyle(root).getPropertyValue(cssVar)) || (key === "side" ? 260 : 420);
    const grow = (e.key === "ArrowRight") === (key === "side"); // dragging right widens the left panel, narrows the right
    const next = clamp(current + (grow ? 24 : -24), ...limits);
    set(next);
    save({ [key]: next });
  });
}

export function initLayout() {
  const saved = read();
  const root = document.documentElement;
  if (saved.side) root.style.setProperty("--side", saved.side + "px");
  if (saved.right) root.style.setProperty("--right", saved.right + "px");
  splitter($("split1"), "--side", "side", (x) => x);
  splitter($("split2"), "--right", "right", (x) => window.innerWidth - x);

  const body = document.body;
  const side = $("toggle-side");
  if (saved.hideSide) { body.classList.add("no-side"); side.setAttribute("aria-pressed", "false"); }
  side.addEventListener("click", () => {
    const hidden = body.classList.toggle("no-side");
    side.setAttribute("aria-pressed", String(!hidden));
    save({ hideSide: hidden });
  });
  const reading = $("reading");
  reading.addEventListener("click", () => {
    const on = body.classList.toggle("reading");
    reading.setAttribute("aria-pressed", String(on));
    reading.textContent = on ? "Leave reading mode" : "Reading mode";
  });
  addEventListener("keydown", (e) => { if (e.key === "Escape" && body.classList.contains("reading")) reading.click(); });

  let theme = THEMES.includes(saved.theme) ? saved.theme : "system";
  applyTheme(theme);
  $("theme").addEventListener("click", () => {
    theme = THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length];
    applyTheme(theme);
    save({ theme });
  });
}
