"use client";

import type { ReactNode } from "react";

/** Executive money format: $380, $5.6K, $255K, $1.5M (rounded to readable steps). */
export const money = (x: number | null | undefined) => {
  if (x === null || x === undefined || Number.isNaN(x)) return "n/a";
  const sign = x < 0 ? "-" : "";
  const v = Math.abs(x);
  if (v < 1_000) return `${sign}$${Math.round(v / 10) * 10}`;
  if (v < 10_000) return `${sign}$${(Math.round(v / 100) / 10).toFixed(1).replace(/\.0$/, "")}K`;
  if (v < 100_000) return `${sign}$${Math.round(v / 1_000)}K`;
  if (Math.round(v / 5_000) * 5 < 1_000) return `${sign}$${Math.round(v / 5_000) * 5}K`;
  return `${sign}$${(Math.round(v / 100_000) / 10).toFixed(1).replace(/\.0$/, "")}M`;
};
/** Round every "$123,456" inside a sentence to the same executive format. */
export const roundMoneyText = (t: string) =>
  t.replace(/\$\d{1,3}(?:,\d{3})+(?:\.\d+)?|\$\d{4,}(?:\.\d+)?/g, (m) => money(Number(m.replace(/[$,]/g, ""))));

export const pct = (x: number | null | undefined, digits = 0) =>
  x === null || x === undefined ? "n/a" : `${(x * 100).toFixed(digits)}%`;

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-stone-200 bg-surface p-6 shadow-sm ${className}`}>{children}</div>;
}

export function Badge({ children, tone = "stone" }: { children: ReactNode; tone?: "stone" | "red" | "amber" | "green" | "orange" }) {
  const tones = {
    stone: "bg-stone-100 text-stone-700",
    red: "bg-red-100 text-red-800",
    amber: "bg-amber-100 text-amber-800",
    green: "bg-emerald-100 text-emerald-800",
    orange: "bg-brand-100 text-brand-800",
  };
  return <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${tones[tone]}`}>{children}</span>;
}

export function Button({
  children, onClick, variant = "primary", disabled, type = "button",
}: {
  children: ReactNode; onClick?: () => void; variant?: "primary" | "secondary" | "ghost"; disabled?: boolean; type?: "button" | "submit";
}) {
  const styles = {
    primary: "bg-brand-600 text-white hover:bg-brand-700 disabled:bg-stone-300",
    secondary: "border border-stone-300 bg-surface text-stone-800 hover:bg-stone-50 disabled:text-stone-400",
    ghost: "text-stone-600 hover:text-stone-900",
  };
  return (
    <button type={type} onClick={onClick} disabled={disabled}
      className={`rounded-xl px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed ${styles[variant]}`}>
      {children}
    </button>
  );
}

export function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 text-sm text-stone-600">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-brand-600 border-t-transparent" />
      {label}
    </div>
  );
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">{children}</div>;
}

export function Note({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">{children}</div>;
}

export function Stat({ label, value, sub, children }: { label: string; value: ReactNode; sub?: ReactNode; children?: ReactNode }) {
  return (
    <div className="rounded-xl bg-stone-50 p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-stone-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-stone-900">{value}</div>
      {sub && <div className="mt-0.5 text-sm text-stone-600">{sub}</div>}
      {children}
    </div>
  );
}

/** Semicircle gauge for 0-100 scores. */
export function Gauge({ value, max = 100, label, color = "#D2602A" }: { value: number | null; max?: number; label: string; color?: string }) {
  const v = value === null ? 0 : Math.max(0, Math.min(max, value));
  const angle = Math.PI * (1 - v / max);
  const x = 60 + 50 * Math.cos(angle);
  const y = 60 - 50 * Math.sin(angle);
  const large = 0;
  return (
    <svg viewBox="0 0 120 70" className="w-full max-w-[180px]" role="img" aria-label={label}>
      <path d="M10 60 A50 50 0 0 1 110 60" fill="none" stroke="var(--gauge-track)" strokeWidth="10" strokeLinecap="round" />
      {value !== null && v > 0 && (
        <path d={`M10 60 A50 50 0 ${large} 1 ${x.toFixed(2)} ${y.toFixed(2)}`} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round" />
      )}
      <text x="60" y="56" textAnchor="middle" className="fill-stone-900" style={{ fontSize: 20, fontWeight: 700 }}>
        {value === null ? "n/a" : Math.round(v)}
      </text>
      <text x="60" y="68" textAnchor="middle" className="fill-stone-500" style={{ fontSize: 7 }}>
        out of {max}
      </text>
    </svg>
  );
}

export function NumberField({
  label, value, onChange, placeholder, hint, prefix,
}: {
  label: string; value: number | null; onChange: (v: number | null) => void; placeholder?: string; hint?: string; prefix?: string;
}) {
  return (
    <label className="block">
      <span className="text-sm font-medium text-stone-800">{label}</span>
      <div className="mt-1 flex items-center rounded-xl border border-stone-300 bg-surface focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-100">
        {prefix && <span className="pl-3 text-stone-500">{prefix}</span>}
        <input
          type="number" inputMode="numeric" min={0}
          className="w-full rounded-xl bg-transparent px-3 py-2.5 text-stone-900 outline-none"
          value={value ?? ""} placeholder={placeholder}
          onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
        />
      </div>
      {hint && <span className="mt-1 block text-xs text-stone-500">{hint}</span>}
    </label>
  );
}

export function Choice<T extends string>({
  options, value, onChange, labels,
}: {
  options: readonly T[]; value: T | null; onChange: (v: T) => void; labels?: Partial<Record<T, string>>;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {options.map((o) => (
        <button key={o} type="button" onClick={() => onChange(o)}
          className={`rounded-xl border px-3 py-2 text-sm transition ${
            value === o ? "border-brand-600 bg-brand-50 font-semibold text-brand-800" : "border-stone-300 bg-surface text-stone-700 hover:border-stone-400"
          }`}>
          {labels?.[o] ?? o}
        </button>
      ))}
    </div>
  );
}
