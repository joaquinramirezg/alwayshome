"""The homeowner's plan as a short, plain-language report (Markdown).

`template_report` is deterministic and always works. `ai_report` asks Claude to rewrite
it more readably; it may only reword, never add numbers. It falls back to the template
when there is no API key or the call fails, so the demo never breaks.
"""
from __future__ import annotations

import os

MODEL = "claude-opus-5-5"

AI_SYSTEM = """You rewrite a homeowner's fire-safety and insurance plan so it is clear and encouraging to read.
Rules: keep every number, dollar amount and percentage exactly as given; do not add any new number, insurer name,
discount or claim; keep the caveats; plain English, short paragraphs, Markdown headings and bullets; under 350 words."""


def _money(x) -> str:
    return "n/a" if x is None else f"${x:,.0f}"


def _wildfire_line(wf: dict) -> str:
    if wf.get("score") is not None:
        return (f"- Wildfire exposure of your area: **{wf['score']:.0f} out of 100** ({wf['rating']}), "
                f"compared with other LA County neighborhoods.")
    return f"- Wildfire exposure of your area: **{wf['rating']}** (based on the fire hazard zone only)."


def _range(r: dict) -> str:
    if r["low"] is None:
        return "n/a"
    return _money(r["low"]) if r["low"] == r["high"] else f"{_money(r['low'])} to {_money(r['high'])}"


def _coverage_lines(cov: dict | None) -> list[str]:
    if not cov:
        return []
    prefix = "at least " if any(w.startswith("Totals leave out") for w in cov["warnings"]) else ""
    return ["", "## If your home is destroyed",
            f"- Cost to recover: **{prefix}{_range(cov['total_cost'])}**",
            f"- Your policy pays: **{prefix}{_range(cov['total_payout'])}**",
            f"- You would pay: **{prefix}{_range(cov['total_shortfall'])}**",
            f"- {cov['scope_note']} These are estimates, not a quote or a claim outcome."]


def template_report(address: str, result: dict) -> str:
    cur, fut = result["current"], result["future"]
    plan_ids = set(fut["plan_within_budget"])
    plan = [f for f in fut["fixes"] if f["measure_id"] in plan_ids]
    later = [f for f in fut["fixes"] if f["measure_id"] not in plan_ids]
    lines = [
        f"# Your AlwaysON plan: {address}",
        "",
        "## Where you are today",
        _wildfire_line(cur["wildfire"]),
        f"- If a fire reaches your house, expected damage: **{cur['house']['impact']:.0%}** ({cur['house']['rating']}).",
    ]
    if cur["insurance_gap"]:
        lines += ["", "## Gaps in your coverage"]
        lines += [f"- **{g['gap']}** ({g['severity']}): {g['why']}" for g in cur["insurance_gap"]]
    lines += _coverage_lines(cur.get("coverage"))
    lines += ["", "## Do these first (within your budget)"]
    if plan:
        lines += [f"{i}. **{f['name']}**: {_money(f['cost_low'])} to {_money(f['cost_high'])}, "
                  f"about {_money(f['est_annual_benefit'])} a year back"
                  f"{f' (pays back in about {f['payback_years']} years)' if f['payback_years'] else ''}. {f['why']}"
                  for i, f in enumerate(plan, 1)]
        lines.append(f"\nAfter these, expected damage drops to **{fut['house_after_plan']['impact']:.0%}** "
                     f"({fut['house_after_plan']['rating']}).")
    else:
        lines.append("- Nothing fits the current budget; see the list below.")
    if later:
        lines += ["", "## Later, when budget allows"]
        lines += [f"- {f['name']}: {_money(f['cost_low'])} to {_money(f['cost_high'])}" for f in later]
    lines += ["", "## Next steps",
              "1. Get two quotes for the first fix on the list.",
              "2. Keep receipts and photos: insurers ask for proof of the work.",
              "3. Ask a broker which private insurers write in your ZIP once the work is done, and which Safer from Wildfires discounts apply.",
              "", "## Please note"]
    lines += [f"- {c}" for c in result["caveats"]]
    return "\n".join(lines)


def ai_report(address: str, result: dict) -> tuple[str, str]:
    """Return (markdown, source) where source is "ai" or "template"."""
    base = template_report(address, result)
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return base, "template"
    try:
        import anthropic

        r = anthropic.Anthropic().messages.create(
            model=MODEL,
            max_tokens=4000,
            system=AI_SYSTEM,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": base}],
        )
        if r.stop_reason in ("refusal", "max_tokens"):
            return base, "template"
        text = "".join(b.text for b in r.content if b.type == "text").strip()
        return (text, "ai") if text else (base, "template")
    except Exception:
        return base, "template"
