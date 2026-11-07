"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "@/lib/api";
import type { Area, Extraction, Health, Inputs, Insurance, Result, Scenario } from "@/lib/types";
import { Badge, Button, Card, Choice, ErrorNote, Gauge, Note, NumberField, Spinner, Stat, money, pct } from "./ui";

// ---------------------------------------------------------------- questions (CAL FIRE inspection options)
const UNKNOWN = "Unknown";
const HOME_QUESTIONS: { field: string; label: string; help: string; options: string[]; labels?: Record<string, string> }[] = [
  { field: "ROOFCONSTRUCTION", label: "Roof material", help: "Tile, metal, concrete and most asphalt shingles are fire-rated. Wood shakes are not.",
    options: ["Asphalt", "Tile", "Metal", "Concrete", "Wood", "Other"] },
  { field: "EAVES", label: "Eaves (roof overhang)", help: "Enclosed: the underside is covered by a flat board. Unenclosed: you can see the rafters.",
    options: ["Enclosed", "Unenclosed", "No Eaves"], labels: { "No Eaves": "No overhang" } },
  { field: "VENTSCREEN", label: "Attic and crawlspace vents", help: "Fine mesh has holes 1/8 inch or smaller, about the width of a pencil lead.",
    options: ['Mesh Screen <= 1/8"', 'Mesh Screen > 1/8"', "Unscreened", "No Vents"],
    labels: { 'Mesh Screen <= 1/8"': "Fine mesh (1/8\" or less)", 'Mesh Screen > 1/8"': "Coarse mesh", Unscreened: "No screen", "No Vents": "No vents" } },
  { field: "EXTERIORSIDING", label: "Exterior walls", help: "What covers the outside walls.",
    options: ["Stucco/Brick/Cement", "Wood", "Vinyl", "Metal", "Other"], labels: { "Stucco/Brick/Cement": "Stucco, brick or cement" } },
  { field: "WINDOWPANE", label: "Windows", help: "Double-pane windows have two layers of glass with a gap between them.",
    options: ["Multi Pane", "Single Pane"], labels: { "Multi Pane": "Double pane or more", "Single Pane": "Single pane" } },
  { field: "DECKPORCHELEVATED", label: "Raised deck", help: "A deck or porch above the ground.",
    options: ["No Deck/Porch", "Wood", "Composite", "Masonry/Concrete"], labels: { "No Deck/Porch": "None", "Masonry/Concrete": "Masonry or concrete" } },
  { field: "FENCEATTACHEDTOSTRUCTURE", label: "Fence touching the house", help: "A wooden fence attached to the wall can carry fire to the house.",
    options: ["No Fence", "Combustible", "Non Combustible"], labels: { "No Fence": "None", Combustible: "Wood or vinyl", "Non Combustible": "Metal or masonry" } },
  { field: "UTILITYMISCSTRUCTUREDISTANCE", label: "Sheds or outbuildings", help: "Distance from the house to the nearest shed, garage or outbuilding.",
    options: ["Not Applicable", "<30'", "30-50'", ">50'"], labels: { "Not Applicable": "None", "<30'": "Under 30 ft", "30-50'": "30 to 50 ft", ">50'": "Over 50 ft" } },
];
const EXTRA_MEASURES: Record<string, string> = {
  defensible_space: "Defensible space done (trees trimmed, brush cleared)",
  ember_zone_5ft: "First 5 feet around the house free of anything that burns",
  noncombustible_6in_walls: "Bottom 6 inches of walls are noncombustible",
  clear_under_decks: "Nothing stored or growing under decks",
};
const INS_TYPES = { fair: "FAIR Plan only", fair_dic: "FAIR Plan + DIC policy", private: "Private homeowners" } as const;
type InsType = keyof typeof INS_TYPES;
const INS_DOCS: Record<InsType, string[]> = { fair: ["fair_plan"], fair_dic: ["fair_plan", "dic"], private: ["homeowners"] };
const SAMPLE_POLICIES: Record<string, string[]> = {
  "FAIR Plan + DIC (Altadena)": ["fair_plan_altadena.pdf", "dic_altadena.pdf"],
  "FAIR Plan only (Altadena)": ["fair_plan_altadena.pdf"],
  "FAIR Plan, scanned copy": ["fair_plan_scanned.pdf"],
  "Private, underinsured (Palisades)": ["homeowners_palisades_underinsured.pdf"],
  "Private, two pages (Altadena)": ["homeowners_two_page.pdf"],
  "Private, well covered (Wilshire)": ["homeowners_well_covered.pdf"],
  "Not a policy: non-renewal letter": ["nonrenewal_letter.pdf"],
};
const DEMO_ADDRESSES = [
  "1000 E Mariposa St, Altadena, CA 91001",
  "1200 Chautauqua Blvd, Pacific Palisades, CA 90272",
  "3200 Wilshire Blvd, Los Angeles, CA 90010",
];
const STEPS = ["Location", "Your home", "Insurance", "Your situation", "Your plan"];

type InsForm = Omit<Insurance, "documents" | "has_dic">;
const EMPTY_INS: InsForm = {
  dwelling_limit: null, dwelling_settlement: null, extended_replacement_pct: null, premium_total: null,
  liability_limit: null, loss_of_use_limit: null, code_upgrade: false, debris_removal: false,
};

const sevTone = { high: "red", medium: "amber", low: "stone" } as const;

export default function Wizard() {
  const [step, setStep] = useState(0);
  const [health, setHealth] = useState<Health | null>(null);
  const [scenarios, setScenarios] = useState<Record<string, Scenario>>({});
  const [apiDown, setApiDown] = useState(false);

  const [address, setAddress] = useState("");
  const [area, setArea] = useState<Area | null>(null);
  const [areaState, setAreaState] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null });

  const [home, setHome] = useState<Record<string, string | null>>({});
  const [yearBuilt, setYearBuilt] = useState<number | null>(null);
  const [sqft, setSqft] = useState<number | null>(null);
  const [stories, setStories] = useState<number | null>(null);
  const [done, setDone] = useState<string[]>([]);

  const [insType, setInsType] = useState<InsType | null>(null);
  const [ins, setIns] = useState<InsForm>(EMPTY_INS);
  const [extraction, setExtraction] = useState<Extraction | null>(null);
  const [extractState, setExtractState] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null });

  const [budget, setBudget] = useState(10000);
  const [result, setResult] = useState<Result | null>(null);
  const [assessState, setAssessState] = useState<{ loading: boolean; error: string | null }>({ loading: false, error: null });
  const [report, setReport] = useState<{ markdown: string; source: string } | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setApiDown(true));
    api.samples().then((s) => {
      setScenarios(s.homeowners);
      // Demo deep link: /?demo=altadena_fair_only&step=4 fills a sample homeowner and opens that step.
      const q = new URLSearchParams(window.location.search);
      const id = q.get("demo");
      if (id && s.homeowners[id]) {
        fillSample(s.homeowners[id]);
        const n = Number(q.get("step"));
        if (n >= 1 && n <= 5) setStep(n - 1);
      }
    }).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------------------------------------------------------------- actions
  async function lookUp(addr: string) {
    if (!addr.trim()) return;
    setAreaState({ loading: true, error: null });
    setArea(null);
    try {
      setArea(await api.area(addr));
      setAreaState({ loading: false, error: null });
    } catch (e) {
      setAreaState({ loading: false, error: (e as Error).message });
    }
  }

  function fillSample(s: Scenario) {
    setAddress(s.address);
    lookUp(s.address);
    const h: Record<string, string | null> = {};
    HOME_QUESTIONS.forEach((q) => (h[q.field] = (s.home[q.field] as string) ?? null));
    setHome(h);
    setYearBuilt((s.home.year_built as number) ?? null);
    setSqft((s.home.living_area_sqft as number) ?? null);
    setStories((s.home.stories as number) ?? null);
    setDone(s.measures_done);
    const { type, ...rest } = s.insurance;
    setInsType(type === INS_TYPES.fair_dic ? "fair_dic" : type === INS_TYPES.private ? "private" : "fair");
    setIns(rest);
    setBudget(s.budget);
    setExtraction(null);
    setResult(null);
    setReport(null);
  }

  function applyExtraction(x: Extraction) {
    const m = x.merged as Record<string, unknown>;
    const docs = (m.documents as string[]) ?? [];
    if (docs.includes("fair_plan")) setInsType(m.has_dic ? "fair_dic" : "fair");
    else if (docs.some((d) => d === "homeowners" || d === "dwelling_fire")) setInsType("private");
    const covered = (v: unknown) => (v && typeof v === "object" ? Boolean((v as { covered?: boolean }).covered) : Boolean(v));
    setIns((prev) => ({
      ...prev,
      dwelling_limit: (m.dwelling_limit as number) ?? prev.dwelling_limit,
      dwelling_settlement: (m.dwelling_settlement as InsForm["dwelling_settlement"]) ?? prev.dwelling_settlement,
      extended_replacement_pct: (m.extended_replacement_pct as number) ?? prev.extended_replacement_pct,
      premium_total: (m.premium_total as number) ?? prev.premium_total,
      liability_limit: (m.liability_limit as number) ?? prev.liability_limit,
      loss_of_use_limit: (m.loss_of_use_limit as number) ?? prev.loss_of_use_limit,
      code_upgrade: m.code_upgrade != null ? covered(m.code_upgrade) : prev.code_upgrade,
      debris_removal: m.debris_removal != null ? covered(m.debris_removal) : prev.debris_removal,
    }));
  }

  async function readPolicies(run: () => Promise<Extraction>) {
    setExtractState({ loading: true, error: null });
    try {
      const x = await run();
      setExtraction(x);
      applyExtraction(x);
      setExtractState({ loading: false, error: null });
    } catch (e) {
      setExtractState({ loading: false, error: (e as Error).message });
    }
  }

  const inputs: Inputs | null = useMemo(() => {
    if (!insType) return null;
    return {
      address,
      home: { ...home, year_built: yearBuilt, living_area_sqft: sqft, stories },
      measures_done: done,
      insurance: {
        ...ins,
        documents: INS_DOCS[insType],
        has_dic: insType === "fair_dic",
        extended_replacement_pct: ins.extended_replacement_pct ?? 0,
        liability_limit: ins.liability_limit ?? 0,
        loss_of_use_limit: ins.loss_of_use_limit ?? 0,
        dwelling_settlement: ins.dwelling_settlement ?? "unknown",
      },
      budget,
    };
  }, [address, home, yearBuilt, sqft, stories, done, ins, insType, budget]);

  const missing = {
    0: !area ? ["your address"] : [],
    1: [
      ...HOME_QUESTIONS.filter((q) => !home[q.field]).map((q) => q.label.toLowerCase()),
      ...(sqft ? [] : ["living area"]),
    ],
    2: [
      ...(insType ? [] : ["current coverage"]),
      ...(ins.dwelling_limit ? [] : ["dwelling limit"]),
      ...(ins.dwelling_settlement ? [] : ["how the dwelling is paid"]),
      ...(ins.premium_total ? [] : ["annual premium"]),
    ],
  } as Record<number, string[]>;

  // re-run the plan when the budget changes on the plan screen
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  async function runAssess(inp: Inputs) {
    if (!area) return;
    setAssessState({ loading: true, error: null });
    try {
      setResult(await api.assess(inp, area));
      setReport(null);
      setAssessState({ loading: false, error: null });
    } catch (e) {
      setAssessState({ loading: false, error: (e as Error).message });
    }
  }
  useEffect(() => {
    if (step < 3 || !inputs) return;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => runAssess(inputs), 250);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, inputs, area]);

  function next() {
    setStep((s) => Math.min(4, s + 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  // ---------------------------------------------------------------- render
  const wf = area?.wildfire;
  return (
    <div className="min-h-screen bg-sand">
      <header className="sticky top-0 z-20 border-b border-stone-200/80 bg-white/85 backdrop-blur">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <button type="button" onClick={() => setStep(0)} className="flex items-center gap-3 text-left" aria-label="AlwaysHome, back to start">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/brand/alwayshome-mark.svg" alt="" width={45} height={36} className="h-9 w-auto" />
            <div>
              <div className="font-display text-xl font-semibold leading-none text-ink">Always<span className="text-brand-600">Home</span></div>
              <div className="mt-1 text-xs text-stone-500">From the FAIR Plan back to private insurance</div>
            </div>
          </button>
          {Object.keys(scenarios).length > 0 && (
            <label className="flex items-center gap-2 text-sm text-stone-600">
              <Badge>Demo</Badge>
              <select className="rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-sm" defaultValue=""
                onChange={(e) => e.target.value && scenarios[e.target.value] && fillSample(scenarios[e.target.value])}>
                <option value="">Fill with a sample homeowner…</option>
                {Object.entries(scenarios).map(([id, s]) => <option key={id} value={id}>{s.title}</option>)}
              </select>
            </label>
          )}
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        {apiDown && <div className="mb-6"><ErrorNote>The AlwaysHome API is not reachable. Start it with <code>uv run uvicorn api.main:app --port 8000</code>.</ErrorNote></div>}

        {step === 0 && !area && (
          <section className="relative mb-10 overflow-hidden rounded-3xl bg-ink px-6 py-10 text-white sm:px-10 sm:py-14">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/brand/alwayshome-mark-on-dark.svg" alt="" aria-hidden className="pointer-events-none absolute -right-24 -top-6 w-64 opacity-[0.12] sm:w-80" />
            <div className="relative max-w-2xl">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1 text-xs text-white/80">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-500" /> For California homeowners on the FAIR Plan
              </div>
              <h1 className="font-display text-4xl font-semibold leading-tight sm:text-5xl">
                Get your home back to <span className="text-brand-400">private insurance.</span>
              </h1>
              <p className="mt-4 text-lg text-white/75">
                See your real wildfire exposure, what your policy would actually pay, and the fire-safety fixes that give you the most for your money.
              </p>
            </div>
            <dl className="relative mt-8 grid max-w-3xl grid-cols-1 gap-4 sm:grid-cols-3">
              {[
                ["+29.1%", "FAIR Plan rate increase on October 15"],
                ["41%", "of homes in the riskiest ZIP codes are on the FAIR Plan"],
                ["+84%", "average California premiums since 2020"],
              ].map(([v, l]) => (
                <div key={v} className="rounded-2xl border border-white/10 bg-white/5 p-4">
                  <dt className="font-display text-3xl font-semibold text-brand-400">{v}</dt>
                  <dd className="mt-1 text-sm text-white/70">{l}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}

        <ol className="mb-8 grid grid-cols-2 gap-2 sm:grid-cols-5">
          {STEPS.map((s, i) => (
            <li key={s}>
              <button type="button" onClick={() => setStep(i)}
                className={`w-full rounded-xl px-3 py-2 text-left text-sm ${
                  i === step ? "bg-brand-600 text-white" : i < step ? "bg-brand-100 text-brand-900" : "bg-white text-stone-500 border border-stone-200"
                }`}>
                <span className="block text-xs opacity-80">Step {i + 1}</span>
                <span className="font-semibold">{s}</span>
              </button>
            </li>
          ))}
        </ol>

        {/* ---------------- step 1: location */}
        {step === 0 && (
          <Card>
            <h1 className="text-2xl font-bold text-stone-900">Where is your home?</h1>
            <p className="mt-1 text-stone-600">We look up your wildfire exposure, fire history and the local insurance market. Los Angeles County only for now.</p>
            <form className="mt-5 flex flex-col gap-3 sm:flex-row" onSubmit={(e) => { e.preventDefault(); lookUp(address); }}>
              <input value={address} onChange={(e) => setAddress(e.target.value)} placeholder="Street address, city, ZIP"
                className="flex-1 rounded-xl border border-stone-300 px-4 py-3 text-stone-900 outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100" />
              <Button type="submit" disabled={!address.trim() || areaState.loading}>Look up</Button>
            </form>
            <div className="mt-2 flex flex-wrap gap-2 text-xs text-stone-500">
              Try:
              {DEMO_ADDRESSES.map((a) => (
                <button key={a} type="button" className="underline hover:text-stone-800" onClick={() => { setAddress(a); lookUp(a); }}>{a.split(",")[1].trim()}</button>
              ))}
            </div>

            <div className="mt-6">
              {areaState.loading && <Spinner label="Looking up your area…" />}
              {areaState.error && <ErrorNote>We could not find that address ({areaState.error}). Check the spelling, or try a nearby address.</ErrorNote>}
              {area && (
                <div className="grid gap-6 md:grid-cols-[220px_1fr]">
                  <div className="flex flex-col items-center rounded-xl bg-brand-50 p-4 text-center">
                    <div className="text-xs font-medium uppercase tracking-wide text-brand-800">Wildfire exposure</div>
                    <Gauge value={wf?.score ?? null} label="Wildfire exposure score" />
                    <div className="text-lg font-semibold text-stone-900">{wf?.rating}</div>
                    <div className="mt-1 text-xs text-stone-600">Your neighborhood compared with the rest of LA County</div>
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Stat label="Mapped fire hazard zone" value={area.hazard_class ?? "Outside mapped zones"} />
                    <Stat label="Homes on the FAIR Plan (ZIP, 2022)" value={pct(area.fair_plan_share, 1)} />
                    <Stat label="Area burned since 1950" value={wf?.components.burned_footprint_pct != null ? `${Math.round(wf.components.burned_footprint_pct)}%` : "n/a"}
                      sub={wf?.components.last_fire_year ? `Last fire: ${wf.components.last_fire_year}` : "No fire on record"} />
                    <Stat label="Typical home value (ZIP)" value={money(area.zip_home_value)} />
                    {!area.hazard_class && (wf?.score ?? 0) > 0 && (
                      <div className="sm:col-span-2"><Note>Your home is outside the mapped hazard zones, but your neighborhood is exposed. Most homes destroyed in the 2025 Eaton Fire were outside any zone.</Note></div>
                    )}
                    <p className="text-xs text-stone-500 sm:col-span-2">Matched {area.geocode?.matched_address}. The exposure score is relative to other LA County neighborhoods, not a probability or an inspection.</p>
                  </div>
                </div>
              )}
            </div>
            <div className="mt-6 flex justify-end"><Button onClick={next} disabled={!area}>Continue</Button></div>
          </Card>
        )}

        {/* ---------------- step 2: home */}
        {step === 1 && (
          <Card>
            <h1 className="text-2xl font-bold text-stone-900">Tell us about your home</h1>
            <p className="mt-1 text-stone-600">These are the features fire inspectors check. Not sure? Choose &ldquo;I don&rsquo;t know&rdquo;.</p>
            <div className="mt-6 grid gap-6 md:grid-cols-2">
              {HOME_QUESTIONS.map((q) => (
                <div key={q.field}>
                  <div className="font-medium text-stone-900">{q.label}</div>
                  <div className="mb-2 text-xs text-stone-500">{q.help}</div>
                  <Choice options={[...q.options, UNKNOWN]} value={home[q.field] ?? null}
                    labels={{ ...(q.labels ?? {}), [UNKNOWN]: "I don't know" }}
                    onChange={(v) => setHome((h) => ({ ...h, [q.field]: v }))} />
                </div>
              ))}
            </div>
            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              <NumberField label="Year built" value={yearBuilt} onChange={setYearBuilt} placeholder="e.g. 1965" />
              <NumberField label="Living area (sq ft)" value={sqft} onChange={setSqft} placeholder="e.g. 1800" hint="Used to estimate the cost to rebuild" />
              <NumberField label="Stories" value={stories} onChange={setStories} placeholder="e.g. 1" />
            </div>
            <div className="mt-8">
              <div className="font-medium text-stone-900">Already done any of these?</div>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {Object.entries(EXTRA_MEASURES).map(([k, label]) => (
                  <label key={k} className="flex items-center gap-3 rounded-xl border border-stone-200 p-3 text-sm text-stone-800">
                    <input type="checkbox" className="h-4 w-4 accent-brand-600" checked={done.includes(k)}
                      onChange={(e) => setDone((d) => (e.target.checked ? [...d, k] : d.filter((x) => x !== k)))} />
                    {label}
                  </label>
                ))}
              </div>
            </div>
            <StepFooter missing={missing[1]} onBack={() => setStep(0)} onNext={next} />
          </Card>
        )}

        {/* ---------------- step 3: insurance */}
        {step === 2 && (
          <div className="space-y-6">
            <Card>
              <h1 className="text-2xl font-bold text-stone-900">Your insurance</h1>
              <p className="mt-1 text-stone-600">Upload your declarations page and our AI fills in the form, showing the exact line it read for every value. Or type the numbers yourself.</p>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center ${health?.ai_enabled ? "border-brand-300 bg-brand-50/50 hover:bg-brand-50" : "border-stone-200 bg-stone-50 opacity-60"}`}>
                  <span className="text-3xl">📄</span>
                  <span className="mt-2 font-medium text-stone-900">Upload policy PDFs</span>
                  <span className="text-xs text-stone-500">FAIR Plan, plus your DIC policy if you have one. Max 2 files. Not stored.</span>
                  {!health?.ai_enabled && <span className="mt-2 text-xs text-red-700">AI reading is off on this server</span>}
                  <input type="file" accept="application/pdf" multiple className="hidden" disabled={!health?.ai_enabled}
                    onChange={(e) => { const f = Array.from(e.target.files ?? []).slice(0, 2); if (f.length) readPolicies(() => api.extract(f)); }} />
                </label>
                <div className="rounded-xl border border-stone-200 p-6">
                  <div className="font-medium text-stone-900">Or try a sample policy</div>
                  <div className="mb-3 text-xs text-stone-500">Fictional declarations pages, read by the AI ahead of time.</div>
                  <select className="w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm" defaultValue=""
                    onChange={(e) => e.target.value && readPolicies(() => api.samplePolicies(SAMPLE_POLICIES[e.target.value]))}>
                    <option value="">Choose a sample…</option>
                    {Object.keys(SAMPLE_POLICIES).map((k) => <option key={k}>{k}</option>)}
                  </select>
                </div>
              </div>
              <div className="mt-4">
                {extractState.loading && <Spinner label="Reading your policy… this takes about 15 seconds" />}
                {extractState.error && <ErrorNote>{extractState.error}. You can enter the numbers by hand below.</ErrorNote>}
              </div>
              {extraction && <ExtractionReview extraction={extraction} />}
            </Card>

            <Card>
              <h2 className="text-lg font-semibold text-stone-900">{extraction ? "Check the values we found" : "Enter your coverage"}</h2>
              <p className="text-sm text-stone-600">Find these on your declarations page. Leave optional amounts empty if your policy doesn&rsquo;t include them.</p>
              <div className="mt-4">
                <div className="mb-2 text-sm font-medium text-stone-800">Current coverage</div>
                <Choice options={Object.keys(INS_TYPES) as InsType[]} value={insType} labels={INS_TYPES} onChange={setInsType} />
              </div>
              <div className="mt-5 grid gap-4 sm:grid-cols-3">
                <NumberField label="Dwelling limit" prefix="$" value={ins.dwelling_limit} placeholder="650000" hint="Coverage A"
                  onChange={(v) => setIns({ ...ins, dwelling_limit: v })} />
                <NumberField label="Total annual premium" prefix="$" value={ins.premium_total} placeholder="6200" hint="All policies together"
                  onChange={(v) => setIns({ ...ins, premium_total: v })} />
                <NumberField label="Extended replacement (%)" value={ins.extended_replacement_pct} placeholder="optional, e.g. 25"
                  onChange={(v) => setIns({ ...ins, extended_replacement_pct: v })} />
                <NumberField label="Personal liability" prefix="$" value={ins.liability_limit} placeholder="optional" hint="Coverage E"
                  onChange={(v) => setIns({ ...ins, liability_limit: v })} />
                <NumberField label="Loss of use" prefix="$" value={ins.loss_of_use_limit} placeholder="optional" hint="Coverage D"
                  onChange={(v) => setIns({ ...ins, loss_of_use_limit: v })} />
              </div>
              <div className="mt-5">
                <div className="mb-2 text-sm font-medium text-stone-800">How is the dwelling paid after a loss?</div>
                <Choice options={["replacement_cost", "actual_cash_value", "unknown"] as const} value={ins.dwelling_settlement}
                  labels={{ replacement_cost: "Replacement cost", actual_cash_value: "Actual cash value", unknown: "Not sure" }}
                  onChange={(v) => setIns({ ...ins, dwelling_settlement: v })} />
              </div>
              <div className="mt-5 flex flex-wrap gap-6 text-sm text-stone-800">
                <label className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={ins.code_upgrade}
                  onChange={(e) => setIns({ ...ins, code_upgrade: e.target.checked })} />Building code upgrade coverage</label>
                <label className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={ins.debris_removal}
                  onChange={(e) => setIns({ ...ins, debris_removal: e.target.checked })} />Debris removal coverage</label>
              </div>
              <StepFooter missing={missing[2]} onBack={() => setStep(1)} onNext={next} nextLabel="See my situation" />
            </Card>
          </div>
        )}

        {/* ---------------- step 4: situation, step 5: plan */}
        {step >= 3 && (
          <PlanView
            section={step === 3 ? "situation" : "plan"}
            onNext={next} onBack={() => setStep(step - 1)}
            missing={[...missing[0], ...missing[1], ...missing[2]]}
            result={result} assessState={assessState} budget={budget} setBudget={setBudget}
            report={report} reportLoading={reportLoading} aiEnabled={!!health?.ai_enabled}
            onReport={async () => {
              if (!result) return;
              setReportLoading(true);
              try { setReport(await api.report(address, result, !!health?.ai_enabled)); } finally { setReportLoading(false); }
            }}
            onEdit={setStep}
          />
        )}
      </main>
      <footer className="mt-8 border-t border-stone-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-8 text-sm text-stone-500 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/brand/alwayshome-monogram.svg" alt="" width={14} height={28} className="h-7 w-auto" />
            <span><span className="font-display font-semibold text-ink">AlwaysHome</span> · UCLA Anderson MSBA Vibathon 2026</span>
          </div>
          <p className="max-w-md text-xs">
            Data: CAL FIRE hazard zones, fire perimeters and 2025 damage inspections, FEMA National Risk Index, California Department of Insurance.
            Not insurance advice. Fix costs and discounts are estimates.
          </p>
        </div>
      </footer>
    </div>
  );
}

function StepFooter({ missing, onBack, onNext, nextLabel = "Continue" }: { missing: string[]; onBack: () => void; onNext: () => void; nextLabel?: string }) {
  return (
    <div className="mt-8 flex flex-col-reverse items-stretch gap-3 sm:flex-row sm:items-center sm:justify-between">
      <Button variant="secondary" onClick={onBack}>Back</Button>
      <div className="flex flex-col items-end gap-2">
        {missing.length > 0 && <span className="text-xs text-stone-500">Still needed: {missing.join(", ")}</span>}
        <Button onClick={onNext} disabled={missing.length > 0}>{nextLabel}</Button>
      </div>
    </div>
  );
}

function fmtValue(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return v >= 1000 ? `$${v.toLocaleString("en-US")}` : String(v);
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (Array.isArray(v)) return v.map((x) => (typeof x === "string" ? x : `${x.name} ${x.amount ?? ""}`)).join("; ");
  if (typeof v === "object") {
    const o = v as Record<string, unknown>;
    if ("covered" in o) return o.covered ? `Covered${o.pct ? ` (${o.pct}%)` : ""}` : "Not covered";
    if ("pct" in o || "amount" in o) return [o.pct ? `${o.pct}%` : "", o.amount ? `$${Number(o.amount).toLocaleString("en-US")}` : ""].filter(Boolean).join(" / ");
  }
  return String(v).replaceAll("_", " ");
}

function ExtractionReview({ extraction }: { extraction: Extraction }) {
  return (
    <div className="mt-6 space-y-6">
      {extraction.documents.map((d) => (
        <div key={d.file}>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="font-semibold text-stone-900">{d.file}</span>
            <Badge tone="orange">{fmtValue(d.fields.find((f) => f.field === "document_type")?.value)}</Badge>
            {d.source === "cache" && <Badge>pre-read sample</Badge>}
            {!d.text_layer && <Badge tone="amber">scanned: compare values with the document</Badge>}
          </div>
          <div className="overflow-x-auto rounded-xl border border-stone-200">
            <table className="w-full text-left text-sm">
              <thead className="bg-stone-50 text-xs uppercase text-stone-500">
                <tr><th className="px-3 py-2">Field</th><th className="px-3 py-2">Value</th><th className="px-3 py-2">Where we found it</th><th className="px-3 py-2">Check</th></tr>
              </thead>
              <tbody>
                {d.fields.filter((f) => f.value !== null || f.must_have).map((f) => (
                  <tr key={f.field} className="border-t border-stone-100">
                    <td className="px-3 py-2 text-stone-700">{f.label}{f.must_have && <span className="text-brand-600"> *</span>}</td>
                    <td className="px-3 py-2 font-medium text-stone-900">{fmtValue(f.value)}</td>
                    <td className="px-3 py-2 text-stone-600">{f.source_text ? <><q className="italic">{f.source_text}</q> <span className="text-xs text-stone-400">p.{f.page}</span></> : <span className="text-stone-400">not on the page</span>}</td>
                    <td className="px-3 py-2">
                      {f.verified === true && <Badge tone="green">quote found</Badge>}
                      {f.verified === false && <Badge tone="amber">check this</Badge>}
                      {f.flag && <Badge tone="red">{f.flag}</Badge>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}

const COMPONENT_LABELS: Record<string, string> = {
  rebuild: "Rebuild the house",
  code_upgrade: "Build to today's fire code",
  other_structures: "Garage, fences, sheds",
  contents: "Belongings",
  living_expenses: "Rent while you rebuild",
  debris_removal: "Clear the burned lot",
};
const range = (r: { low: number; high: number }) =>
  Math.round(r.low) === Math.round(r.high) ? money(r.low) : `${money(r.low)}–${money(r.high)}`;

function LossScenario({ c }: { c: NonNullable<Result["current"]["coverage"]> }) {
  const short = c.total_shortfall.high > 0;
  return (
    <Card>
      <h2 className="text-lg font-semibold text-stone-900">If your home burned down tomorrow</h2>
      <p className="text-sm text-stone-600">What rebuilding would cost, what your policy would pay, and what you would pay yourself.</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Stat label="Total cost" value={range(c.total_cost)} />
        <Stat label="Insurance pays" value={range(c.total_payout)} />
        <div className={`rounded-xl p-4 ${short ? "bg-red-50" : "bg-emerald-50"}`}>
          <div className={`text-xs font-medium uppercase tracking-wide ${short ? "text-red-700" : "text-emerald-700"}`}>You pay out of pocket</div>
          <div className={`mt-1 text-2xl font-semibold ${short ? "text-red-800" : "text-emerald-800"}`}>{range(c.total_shortfall)}</div>
        </div>
      </div>
      <div className="mt-4 overflow-x-auto rounded-xl border border-stone-200">
        <table className="w-full text-left text-sm">
          <thead className="bg-stone-50 text-xs uppercase text-stone-500">
            <tr><th className="px-3 py-2">Cost</th><th className="px-3 py-2">Estimate</th><th className="px-3 py-2">Policy pays</th><th className="px-3 py-2">Your share</th></tr>
          </thead>
          <tbody>
            {c.components.map((p) => (
              <tr key={p.name} className="border-t border-stone-100">
                <td className="px-3 py-2 text-stone-800">{COMPONENT_LABELS[p.name] ?? p.name.replaceAll("_", " ")}</td>
                <td className="px-3 py-2">{range(p.cost)}</td>
                <td className="px-3 py-2">{range(p.payout)}</td>
                <td className={`px-3 py-2 font-medium ${p.shortfall.high > 0 ? "text-red-700" : "text-emerald-700"}`}>{range(p.shortfall)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-stone-500">{c.scope_note} Ranges reflect uncertain rebuild costs; see assumptions below.</p>
    </Card>
  );
}

function PlanView({
  section, onNext, onBack, missing, result, assessState, budget, setBudget, report, reportLoading, aiEnabled, onReport, onEdit,
}: {
  section: "situation" | "plan"; onNext: () => void; onBack: () => void;
  missing: string[]; result: Result | null; assessState: { loading: boolean; error: string | null };
  budget: number; setBudget: (b: number) => void; report: { markdown: string; source: string } | null;
  reportLoading: boolean; aiEnabled: boolean; onReport: () => void; onEdit: (step: number) => void;
}) {
  if (missing.length) {
    return <Card><ErrorNote>Please complete the earlier steps first. Still needed: {missing.join(", ")}.</ErrorNote>
      <div className="mt-4"><Button variant="secondary" onClick={() => onEdit(0)}>Go to step 1</Button></div></Card>;
  }
  if (assessState.error) return <Card><ErrorNote>{assessState.error}</ErrorNote></Card>;
  if (!result) return <Card><Spinner label="Building your plan…" /></Card>;
  const { current: cur, future: fut } = result;
  const drop = cur.house.impact - fut.house_after_plan.impact;
  const pts = (x: number) => `${Math.round(x * 100)} points`;

  function download() {
    if (!report) return;
    const url = URL.createObjectURL(new Blob([report.markdown], { type: "text/markdown" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "alwayshome_plan.md" });
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      {result.sources.house === "placeholder" && (
        <Note>Prototype: the house damage estimate is a placeholder until our house model is plugged in. The wildfire exposure score uses real data.</Note>
      )}
      {section === "situation" && <>
      <Card>
        <h1 className="text-2xl font-bold text-stone-900">Your situation today</h1>
        <p className="mt-1 text-stone-600">How exposed your area is, how likely your home is to survive a fire, and what your insurance would really pay.</p>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <div className="flex flex-col items-center rounded-xl bg-brand-50 p-4 text-center">
            <div className="text-xs font-medium uppercase tracking-wide text-brand-800">Wildfire exposure</div>
            <Gauge value={cur.wildfire.score} label="Wildfire exposure" />
            <div className="font-semibold text-stone-900">{cur.wildfire.rating}</div>
          </div>
          <Stat label="Chance of losing the house if fire reaches it" value={pct(cur.house.impact)} sub={cur.house.rating}>
            <div className="mt-1 text-xs text-stone-500">Homes like yours in the 2025 Eaton and Palisades fires (22,071 CAL FIRE inspections)</div>
          </Stat>
        </div>
      </Card>

      {cur.coverage && <LossScenario c={cur.coverage} />}

      <Card>
        <h2 className="text-lg font-semibold text-stone-900">Gaps in your coverage</h2>
        {cur.insurance_gap.length === 0 ? <p className="mt-2 text-sm text-emerald-700">No major gaps found.</p> : (
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {cur.insurance_gap.map((g) => (
              <div key={g.gap} className="rounded-xl border border-stone-200 p-4">
                <div className="flex items-start justify-between gap-2"><span className="font-medium text-stone-900">{g.gap}</span><Badge tone={sevTone[g.severity]}>{g.severity}</Badge></div>
                <p className="mt-1 text-sm text-stone-600">{g.why}</p>
              </div>
            ))}
          </div>
        )}
      </Card>
      <div className="flex justify-between">
        <Button variant="secondary" onClick={onBack}>Back</Button>
        <Button onClick={onNext}>See my plan</Button>
      </div>
      </>}

      {section === "plan" && <>
      <Card>
        <h1 className="text-2xl font-bold text-stone-900">Your plan</h1>
        <p className="mt-1 text-stone-600">The fire-safety fixes that lower your risk the most for the money, within your budget.</p>
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          <Stat label="Chance of losing the house today" value={pct(cur.house.impact)} sub={cur.house.rating} />
          <Stat label="After the fixes in your plan" value={pct(fut.house_after_plan.impact)}
            sub={drop > 0 ? <span className="font-medium text-emerald-700">▼ {pts(drop)} lower</span> : "No change"} />
        </div>
      </Card>

      <Card>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-stone-900">Fixes, best value first</h2>
            <p className="text-sm text-stone-600">{fut.plan_within_budget.length} fixes fit your budget, from {money(fut.plan_cost_low)}.</p>
          </div>
          <label className="w-full max-w-xs text-sm text-stone-700">
            Budget: <span className="font-semibold text-stone-900">{money(budget)}</span>
            <input type="range" min={0} max={60000} step={1000} value={budget} onChange={(e) => setBudget(Number(e.target.value))}
              className="mt-1 w-full accent-brand-600" />
          </label>
        </div>
        {assessState.loading && <div className="mt-2"><Spinner label="Updating…" /></div>}
        {fut.fixes.length === 0 ? <p className="mt-4 text-emerald-700">Your home already meets every measure we check.</p> : (
          <ol className="mt-4 space-y-3">
            {fut.fixes.map((f, i) => (
              <li key={f.measure_id} className={`rounded-xl border p-4 ${f.within_budget ? "border-brand-300 bg-brand-50/40" : "border-stone-200"}`}>
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="flex items-start gap-3">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-stone-900 text-sm font-semibold text-white">{i + 1}</span>
                    <div>
                      <div className="font-semibold text-stone-900">{f.name}</div>
                      <div className="text-sm text-stone-600">{f.why}</div>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {f.effect_basis === "data" && <Badge tone="orange">backed by 2025 fire data</Badge>}
                    {f.effect_basis === "assumed" && <Badge>effect assumed</Badge>}
                    {f.effect_basis === "no_measured_effect" && <Badge>no measured effect; discount only</Badge>}
                    {f.within_budget ? <Badge tone="green">in your plan</Badge> : <Badge>later</Badge>}
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <div><div className="text-xs text-stone-500">Cost (estimate)</div><div className="font-medium">{money(f.cost_low)}–{money(f.cost_high)}</div></div>
                  <div><div className="text-xs text-stone-500">Back per year</div><div className="font-medium">{money(f.est_annual_benefit)}</div></div>
                  <div><div className="text-xs text-stone-500">Pays back in</div><div className="font-medium">{f.payback_years != null ? `${f.payback_years} yrs` : "n/a"}</div></div>
                  <div><div className="text-xs text-stone-500">Loss chance after</div><div className="font-medium">{pct(f.impact_after)}</div></div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold text-stone-900">Your report</h2>
          <div className="flex flex-wrap gap-2">
            <Button onClick={onReport} disabled={reportLoading}>{report ? "Generate again" : "Generate report"}</Button>
            {report && <Button variant="secondary" onClick={download}>Download</Button>}
          </div>
        </div>
        {!report && !reportLoading && <p className="mt-2 text-sm text-stone-600">A plain-language summary of your situation and plan{aiEnabled ? ", written by AI from your numbers" : ""}, ready to download or share with a broker.</p>}
        {reportLoading && <div className="mt-3"><Spinner label={aiEnabled ? "Writing your report… about 20 seconds" : "Writing your report…"} /></div>}
        {report && (
          <article className="report mt-4 rounded-xl bg-stone-50 p-5 text-stone-800">
            <p className="mb-2 text-xs text-stone-500">{report.source === "ai" ? "Written by AI from your plan's numbers; every figure comes from the analysis above" : "Standard report"}</p>
            <ReactMarkdown>{report.markdown}</ReactMarkdown>
          </article>
        )}
      </Card>

      <details className="rounded-2xl border border-stone-200 bg-white p-5 text-sm text-stone-600">
        <summary className="cursor-pointer font-medium text-stone-800">Assumptions and limits</summary>
        <ul className="mt-2 list-disc space-y-1 pl-5">{result.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
      </details>
      <div><Button variant="secondary" onClick={onBack}>Back</Button></div>
      </>}
    </div>
  );
}
