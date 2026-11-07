"""assess() for the app (contract: docs/inputs_and_contract.md).

- Wildfire analysis: REAL, Atharva's tract exposure index (wildfire.py).
- House analysis (`house_impact`): still a PLACEHOLDER until the house model replaces it.
- Coverage gaps and total-loss scenario: the coverage module (coverage/); gaps.py is the fallback.
- Fix costs and discounts: labelled assumptions below.
"""
from __future__ import annotations

from .coverage.adapter import coverage_for_assess, display_gaps
from .gaps import coverage_gaps, rebuild_estimate
from .wildfire import wildfire_analysis

from . import house as house_model

STUB = house_model.model() is None  # placeholder only if the trained model file is missing
SOURCES = {"wildfire": "real", "house": "placeholder" if STUB else "real"}

# ---- labelled assumptions (cost ranges in USD, assumed premium discount as fraction)
# Sources to replace these: contractor quotes, CDI Safer from Wildfires filings.
MEASURES = {
    "class_a_roof": ("Class A fire-rated roof", 15000, 40000, 0.05, "ROOFCONSTRUCTION", {"Wood", "Other", "Unknown"}),
    "ember_resistant_vents": ("Ember- and fire-resistant vents", 500, 2500, 0.02, "VENTSCREEN",
                              {'Mesh Screen > 1/8"', "Unscreened", "Unknown"}),
    "enclosed_eaves": ("Enclosed eaves", 3000, 12000, 0.02, "EAVES", {"Unenclosed", "Unknown"}),
    "double_pane_or_shutters": ("Double pane windows or added shutters", 8000, 25000, 0.02, "WINDOWPANE",
                                {"Single Pane", "Unknown"}),
    "ember_zone_5ft": ("5-foot ember-resistant zone around the house", 500, 3000, 0.03, "FENCEATTACHEDTOSTRUCTURE",
                       {"Combustible", "Unknown"}),
    "noncombustible_6in_walls": ("Noncombustible 6 inches at the bottom of walls", 500, 2500, 0.01, "EXTERIORSIDING",
                                 {"Wood", "Vinyl", "Other", "Unknown"}),
    "clear_under_decks": ("Clear vegetation and debris from under decks", 100, 500, 0.01, "DECKPORCHELEVATED",
                          {"Wood", "Composite", "Unknown"}),
    "outbuildings_30ft": ("Move sheds and outbuildings 30+ feet away", 500, 5000, 0.01, "UTILITYMISCSTRUCTUREDISTANCE",
                          {"<30'"}),
    "defensible_space": ("Defensible space (trim trees, remove brush)", 500, 5000, 0.03, None, None),
}

WHY = {
    "class_a_roof": "The roof is the largest surface embers land on.",
    "ember_resistant_vents": "Embers enter the attic through vents with coarse or no mesh.",
    "enclosed_eaves": "Open eaves trap heat and embers under the roofline.",
    "double_pane_or_shutters": "Single-pane glass breaks from radiant heat and lets fire inside.",
    "ember_zone_5ft": "Combustibles touching the house (fences, mulch) carry fire to the walls.",
    "noncombustible_6in_walls": "Embers pile up where the wall meets the ground.",
    "clear_under_decks": "Debris under decks ignites and spreads fire to the house.",
    "outbuildings_30ft": "A burning shed near the house acts like a second fire source.",
    "defensible_space": "Cleared vegetation slows the fire and lowers heat reaching the house.",
}

# stub weights: share of house impact each weakness adds (to be replaced by the model)
_WEIGHTS = {"class_a_roof": 0.12, "ember_resistant_vents": 0.10, "enclosed_eaves": 0.08,
            "double_pane_or_shutters": 0.08, "ember_zone_5ft": 0.10, "noncombustible_6in_walls": 0.05,
            "clear_under_decks": 0.04, "outbuildings_30ft": 0.05, "defensible_space": 0.12}


def _rating(x: float, cuts=(0.3, 0.55, 0.75)) -> str:
    return "Low" if x < cuts[0] else "Moderate" if x < cuts[1] else "High" if x < cuts[2] else "Very High"


def missing_measures(home: dict, done: list[str]) -> list[str]:
    out = []
    for mid, (_, _, _, _, field, weak) in MEASURES.items():
        if mid in done:
            continue
        if field is None or home.get(field, "Unknown") in weak:
            out.append(mid)
    return out


def _stub_impact(missing: list[str]) -> float:
    return round(min(0.95, 0.15 + sum(_WEIGHTS[m] for m in missing)), 2)


def house_impact(home: dict, missing: list[str], fixes: list[str] | None = None) -> float:
    """Damage share if fire reaches the house, after applying `fixes` (subset of missing)."""
    fixes = fixes or []
    if STUB:
        return _stub_impact([m for m in missing if m not in fixes])
    return round(house_model.impact_with_fixes(home, fixes), 3)


def assess(inputs: dict, area: dict | None = None) -> dict:
    area = area or {}
    home, ins = inputs.get("home", {}), inputs.get("insurance", {})
    budget = inputs.get("budget") or 0
    premium = ins.get("premium_total") or ins.get("annual_premium") or 0
    sqft = home.get("living_area_sqft")
    rebuild = rebuild_estimate(sqft) or (area.get("zip_home_value") or 0) * 0.6

    wildfire = wildfire_analysis(area)
    missing = missing_measures(home, inputs.get("measures_done", []))
    impact = house_impact(home, missing)

    fixes = []
    for mid in missing:
        name, lo, hi, disc, _, _ = MEASURES[mid]
        after = house_impact(home, missing, [mid])
        avoided = wildfire["p_fire_annual"] * (impact - after) * rebuild
        benefit = premium * disc + avoided
        cost = (lo + hi) / 2
        fixes.append({
            "measure_id": mid, "name": name, "cost_low": lo, "cost_high": hi,
            "impact_after": after, "est_annual_benefit": round(benefit),
            "est_premium_saving": round(premium * disc), "est_avoided_loss": round(avoided),
            "payback_years": round(cost / benefit, 1) if benefit else None,
            "why": WHY[mid],
            "effect_basis": "stub" if STUB else house_model.effect_basis(mid, home),
            "assumptions": ["cost", "discount"] + (["impact (stub)"] if STUB else
                           ["impact (assumed)"] if mid in house_model.ASSUMED else []),
        })
    fixes.sort(key=lambda f: (f["payback_years"] is None, f["payback_years"] or 0))

    plan, spent = [], 0
    for f in fixes:
        if spent + f["cost_low"] <= budget:
            plan.append(f["measure_id"])
            spent += f["cost_low"]
    for f in fixes:
        f["within_budget"] = f["measure_id"] in plan
    after_plan = house_impact(home, missing, plan)
    coverage = coverage_for_assess(inputs, area)

    return {
        "current": {
            "area": area,
            "wildfire": wildfire,
            "house": {"impact": impact, "rating": _rating(impact), "missing": missing, "stub": STUB,
                      "method": None if STUB else "CAL FIRE damage inspections, 2025 Eaton and Palisades fires "
                      "(22,071 homes); logistic regression with fire x ZIP effect"},
            "insurance_gap": display_gaps(coverage, ins) if coverage else coverage_gaps(ins, sqft),
            "coverage": coverage,
        },
        "future": {
            "fixes": fixes,
            "plan_within_budget": plan,
            "plan_cost_low": spent,
            "house_after_plan": {"impact": after_plan, "rating": _rating(after_plan)},
        },
        "caveats": [
            "Wildfire exposure is a relative index for your census tract compared with other LA County tracts, "
            "not a probability or an inspection of your home.",
            "Expected-loss figures use FEMA's annualized wildfire frequency for your tract (National Risk Index).",
            ("House damage scores are placeholders until the house model is plugged in." if STUB else
             "House damage is the chance a home like yours was destroyed when the 2025 Eaton and Palisades fires "
             "reached it (CAL FIRE inspections), not an inspection of your home. Fix effects are associations; "
             "siding and attached-fence changes showed no measurable effect, so no damage reduction is claimed for them."),
            "Fix costs and discounts are assumptions; no public price list exists.",
            "CDI insurance data ends in 2023, before the January 2025 fires.",
        ],
        "stub": STUB,
        "sources": {**SOURCES, "wildfire": "placeholder" if wildfire.get("stub") else "real"},
    }
