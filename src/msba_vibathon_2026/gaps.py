"""Coverage gap rules. Plain rules, no model: each gap says what is missing and why it matters."""
from __future__ import annotations

# Labelled assumption: LA rebuild cost per square foot after the 2025 fires.
REBUILD_COST_PER_SQFT = 450


def rebuild_estimate(living_area_sqft: float | None) -> float | None:
    return living_area_sqft * REBUILD_COST_PER_SQFT if living_area_sqft else None


def coverage_gaps(ins: dict, living_area_sqft: float | None = None) -> list[dict]:
    """ins: flat insurance dict (from merge_policies or the manual form)."""
    gaps: list[dict] = []

    def add(gap, severity, why):
        gaps.append({"gap": gap, "severity": severity, "why": why})

    docs = ins.get("documents") or [ins.get("document_type")]
    on_fair = "fair_plan" in docs
    has_dic = ins.get("has_dic", False)

    if on_fair and not has_dic:
        add("FAIR Plan only, no supplemental (DIC) policy", "high",
            "The FAIR Plan covers fire, not theft, water damage or personal liability.")
    if ins.get("liability_limit") in (None, 0) and not has_dic:
        add("No personal liability coverage", "high", "Injuries on your property are not covered.")
    if ins.get("loss_of_use_limit") in (None, 0):
        add("No loss-of-use coverage", "medium",
            "Hotel and rent while the home is rebuilt are not paid. After the 2025 fires this often ran 1 to 3 years.")

    rebuild = rebuild_estimate(living_area_sqft)
    dwelling = ins.get("dwelling_limit")
    ext = ins.get("extended_replacement_pct") or 0
    if rebuild and dwelling:
        effective = dwelling * (1 + ext / 100)
        if effective < 0.9 * rebuild:
            add(f"Underinsured by about ${rebuild - effective:,.0f}", "high",
                f"Dwelling limit ${dwelling:,.0f}{f' + {ext:g}% extended' if ext else ''} vs. an estimated "
                f"${rebuild:,.0f} to rebuild ({living_area_sqft:,.0f} sq ft x ${REBUILD_COST_PER_SQFT}/sq ft, assumption).")

    if ins.get("dwelling_settlement") == "actual_cash_value":
        add("Dwelling paid at actual cash value", "high",
            "A claim pays the depreciated value, not the cost to rebuild.")
    if not ext and ins.get("dwelling_settlement") != "actual_cash_value":
        add("No extended replacement cost", "medium",
            "Construction costs spike after big fires; extended replacement adds 25 to 50% headroom.")

    code = ins.get("code_upgrade")
    if not (code.get("covered") if isinstance(code, dict) else code):
        add("No building code upgrade coverage", "medium",
            "Rebuilding to current fire code (Chapter 7A) costs more than the old house.")
    debris = ins.get("debris_removal")
    if not (debris.get("covered") if isinstance(debris, dict) else debris):
        add("Debris removal not shown", "low", "Clearing a burned lot can cost tens of thousands of dollars.")

    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(gaps, key=lambda g: order[g["severity"]])
