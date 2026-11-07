"use client";

import { useSyncExternalStore } from "react";

type Mode = "light" | "dark";

function read(): Mode {
  return document.documentElement.classList.contains("dark") ? "dark" : "light";
}
function subscribe(cb: () => void) {
  const obs = new MutationObserver(cb);
  obs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => obs.disconnect();
}

/** Light / dark switch. The initial theme (saved choice, else the system setting) is set before paint in layout.tsx. */
export default function ThemeToggle() {
  const mode = useSyncExternalStore(subscribe, read, () => "light" as Mode);
  function toggle() {
    const next: Mode = mode === "dark" ? "light" : "dark";
    document.documentElement.classList.toggle("dark", next === "dark");
    try { localStorage.setItem("alwayshome-theme", next); } catch {}
  }
  return (
    <button type="button" onClick={toggle} aria-label={`Switch to ${mode === "dark" ? "light" : "dark"} mode`}
      className="flex h-9 w-9 items-center justify-center rounded-lg border border-stone-200 bg-surface text-stone-700 hover:bg-stone-50">
      {mode === "dark" ? (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
      ) : (
        <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
      )}
    </button>
  );
}
