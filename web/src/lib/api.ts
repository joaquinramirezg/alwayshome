import type { Area, Extraction, Health, Inputs, Result, Scenario } from "./types";

// Slow AI calls (10-60 s) go straight to the API so a hosting proxy timeout can't cut them off.
// Set NEXT_PUBLIC_DIRECT_API_URL (e.g. https://alwayson-api.onrender.com) on Vercel; empty = same origin.
const DIRECT = (process.env.NEXT_PUBLIC_DIRECT_API_URL ?? "").replace(/\/$/, "");

async function call<T>(path: string, init?: RequestInit, direct = false): Promise<T> {
  const res = await fetch((direct ? DIRECT : "") + path, init);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {}
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => call<Health>("/api/health"),
  samples: () => call<{ homeowners: Record<string, Scenario>; policies: string[] }>("/api/samples"),
  area: (address: string) => call<Area>(`/api/area?address=${encodeURIComponent(address)}`),
  assess: (inputs: Inputs, area: Area) => call<Result>("/api/assess", json({ inputs, area })),
  samplePolicies: (names: string[]) =>
    call<Extraction>(`/api/policy/samples?${names.map((n) => `names=${encodeURIComponent(n)}`).join("&")}`),
  extract: (files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return call<Extraction>("/api/policy/extract", { method: "POST", body: form }, true);
  },
  report: (address: string, result: Result, ai: boolean) =>
    call<{ markdown: string; source: string }>("/api/report", json({ address, result, ai }), ai),
};
