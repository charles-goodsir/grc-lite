// A 25/5 Pomodoro timer in the top bar. The state lives in localStorage (a convenience: the page works without it),
// and the countdown is computed from an end time, so a refresh or a throttled background tab stays correct.
import { $, h } from "./ui.js";

const KEY = "grc-lite-pomodoro";
const LENGTH = { work: 25 * 60, rest: 5 * 60 }; // seconds
const LABEL = { work: "Focus", rest: "Break" };

const read = () => { try { return JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { return {}; } };
const write = (s) => { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* not saved */ } };

function beep() {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    osc.connect(ctx.destination);
    osc.frequency.value = 880;
    osc.start();
    osc.stop(ctx.currentTime + 0.4);
  } catch (e) { /* no sound available */ }
}

const clock = (secs) => `${String(Math.floor(secs / 60)).padStart(2, "0")}:${String(secs % 60).padStart(2, "0")}`;

export function initPomodoro() {
  const host = $("pomodoro");
  const baseTitle = document.title;
  const saved = read();
  // phase, seconds left while paused, and the end time (ms) while running
  const s = {
    phase: saved.phase === "rest" ? "rest" : "work",
    left: Number.isFinite(saved.left) ? saved.left : LENGTH.work,
    endsAt: Number.isFinite(saved.endsAt) ? saved.endsAt : null,
  };
  const face = h("span", { class: "pomo-face", role: "timer", "aria-label": "Pomodoro timer" });
  const go = h("button", { title: "Start or pause the timer" });
  const reset = h("button", { title: "Reset to a fresh 25 minute focus" }, "Reset");
  host.append(face, go, reset);

  const remaining = () => (s.endsAt ? Math.max(0, Math.round((s.endsAt - Date.now()) / 1000)) : s.left);

  function paint() {
    const secs = remaining();
    face.textContent = `${LABEL[s.phase]} ${clock(secs)}`;
    go.textContent = s.endsAt ? "Pause" : "Start";
    document.title = s.endsAt ? `${clock(secs)} ${LABEL[s.phase]} · ${baseTitle}` : baseTitle;
  }
  const store = () => write({ phase: s.phase, left: s.left, endsAt: s.endsAt });

  go.addEventListener("click", () => {
    if (s.endsAt) { s.left = remaining(); s.endsAt = null; } // pause
    else s.endsAt = Date.now() + s.left * 1000;
    store(); paint();
  });
  reset.addEventListener("click", () => {
    s.phase = "work"; s.left = LENGTH.work; s.endsAt = null;
    store(); paint();
  });

  setInterval(() => {
    if (s.endsAt && remaining() === 0) { // phase over: swap and carry straight on
      beep();
      s.phase = s.phase === "work" ? "rest" : "work";
      s.left = LENGTH[s.phase];
      s.endsAt = Date.now() + s.left * 1000;
      store();
    }
    paint();
  }, 1000);
  paint();
}
