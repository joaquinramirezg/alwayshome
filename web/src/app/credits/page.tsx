import type { Metadata } from "next";
import Link from "next/link";
import ThemeToggle from "@/components/theme-toggle";

export const metadata: Metadata = {
  title: "Credits",
  description: "The team, data and tools behind AlwaysHome.",
};

const TEAM = [
  {
    name: "David Ewenczyk",
    email: "david.ewenczyk.2027@anderson.ucla.edu",
    role: "Co-founder & Chief Data Officer",
    work: "Architect of the data engine and the coverage model. Turned scattered state, federal and insurance data into one validated pipeline for Los Angeles County, and built the total-loss model that shows homeowners what their policy would pay, and what it wouldn't.",
  },
  {
    name: "Joaquin Ramirez",
    email: "joaquin.elias.ramirez.gutierrez.2027@anderson.ucla.edu",
    role: "Co-founder & Chief Product Officer",
    work: "Leads product and AI. Built the homeowner experience end to end: the AI policy reader that quotes the exact line behind every number, the house-damage model trained on 22,000 homes from the 2025 fires, and the platform it all runs on.",
  },
  {
    name: "Atharva Uplap",
    email: "atharva.uplap.2027@anderson.ucla.edu",
    role: "Co-founder & Chief Risk Officer",
    work: "Leads wildfire risk science. Built the neighborhood wildfire exposure index from state hazard maps, 75 years of fire history and FEMA loss data, and the insurance gap and recommendations engine powering our next release.",
  },
];

const DATA = [
  ["CAL FIRE / Office of the State Fire Marshal", "Fire Hazard Severity Zones (SRA 2024, LRA 2025)"],
  ["CAL FIRE", "Historical fire perimeters since 1950; damage inspections (DINS) of the 2025 Eaton and Palisades fires"],
  ["FEMA", "National Risk Index: wildfire frequency and expected annual loss by census tract"],
  ["California Department of Insurance", "New, renewed and non-renewed policies by ZIP (2015 to 2023); FAIR Plan share by ZIP (2022); Safer from Wildfires measures"],
  ["USDA Forest Service", "Wildfire Risk to Communities"],
  ["US Census Bureau", "Geocoder, American Community Survey, ZIP and tract crosswalks (with HUD)"],
  ["Zillow Research", "Home values by ZIP"],
];

const TOOLS = ["Claude API (Anthropic)", "Next.js and React on Vercel", "FastAPI and Python on Render", "GeoPandas, pandas, scikit-learn", "Streamlit (internal test bench)"];

export default function Credits() {
  return (
    <div className="min-h-screen bg-sand">
      <header className="border-b border-stone-200/80 bg-surface">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-3" aria-label="AlwaysHome home">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/brand/alwayshome-mark.svg" alt="" width={45} height={36} className="h-9 w-auto dark:hidden" />
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/brand/alwayshome-mark-on-dark.svg" alt="" width={45} height={36} className="hidden h-9 w-auto dark:block" />
            <span className="font-display text-xl font-semibold text-ink">Always<span className="text-brand-600">Home</span></span>
          </Link>
          <div className="flex items-center gap-3">
            <Link href="/" className="text-sm font-medium text-stone-600 hover:text-brand-600">Back to the app</Link>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl px-4 py-12 sm:px-6 lg:px-8">
        <p className="text-sm font-medium uppercase tracking-wide text-brand-600">Founding team</p>
        <h1 className="mt-2 font-display text-4xl font-semibold text-ink sm:text-5xl">The team behind AlwaysHome</h1>
        <p className="mt-4 max-w-3xl text-lg text-stone-600">
          Built in one day for the UCLA Anderson MSBA Vibathon 2026, theme 04 &ldquo;Uninsurable&rdquo;: helping California homeowners
          on the FAIR Plan find their way back to affordable private insurance.
        </p>

        <section className="mt-10 grid gap-6 md:grid-cols-3">
          {TEAM.map((p) => (
            <article key={p.name} className="rounded-2xl border border-stone-200 bg-surface p-6 shadow-sm">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-brand-100 font-display text-lg font-semibold text-brand-800">
                {p.name.split(" ").map((w) => w[0]).join("")}
              </div>
              <h2 className="mt-4 font-display text-2xl font-semibold text-ink">{p.name}</h2>
              <p className="mt-1 text-sm font-semibold text-brand-600">{p.role}</p>
              <p className="mt-3 text-sm text-stone-600">{p.work}</p>
              <a href={`mailto:${p.email}`} className="mt-4 block break-all text-sm text-stone-700 underline decoration-stone-300 hover:text-brand-600">
                {p.email}
              </a>
              <p className="mt-1 text-xs text-stone-500">MSBA Class of 2027, UCLA Anderson</p>
            </article>
          ))}
        </section>

        <section className="mt-12 grid gap-6 lg:grid-cols-3">
          <div className="rounded-2xl border border-stone-200 bg-surface p-6 lg:col-span-2">
            <h2 className="font-display text-2xl font-semibold text-ink">Data</h2>
            <dl className="mt-4 divide-y divide-stone-200">
              {DATA.map(([who, what]) => (
                <div key={who + what} className="grid gap-1 py-3 sm:grid-cols-3">
                  <dt className="font-medium text-stone-800">{who}</dt>
                  <dd className="text-sm text-stone-600 sm:col-span-2">{what}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className="rounded-2xl border border-stone-200 bg-surface p-6">
            <h2 className="font-display text-2xl font-semibold text-ink">Built with</h2>
            <ul className="mt-4 space-y-2 text-sm text-stone-700">
              {TOOLS.map((t) => <li key={t} className="flex gap-2"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600" />{t}</li>)}
            </ul>
            <p className="mt-6 text-xs text-stone-500">
              Prototype for education. Not insurance advice. Fix costs and discounts are estimates; scores describe areas and homes like
              yours, not an inspection of your property.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
