"""Checks for the model-app contract (docs/inputs_and_contract.md).

`validate_inputs` and `validate_output` return a list of problems (empty = valid).
The app shows them in its debug panel, and the tests run them on every scenario, so
when the real model replaces assess_stub.py any shape mismatch shows up immediately.
"""
from __future__ import annotations

HOME_OPTIONS = {
    "ROOFCONSTRUCTION": {"Wood", "Asphalt", "Concrete", "Tile", "Metal", "Other", "Unknown"},
    "EAVES": {"Enclosed", "Unenclosed", "No Eaves", "Unknown"},
    "VENTSCREEN": {'Mesh Screen <= 1/8"', 'Mesh Screen > 1/8"', "Unscreened", "No Vents", "Unknown"},
    "EXTERIORSIDING": {"Metal", "Stucco/Brick/Cement", "Vinyl", "Wood", "Other", "Unknown"},
    "WINDOWPANE": {"Single Pane", "Multi Pane", "No Windows", "Unknown"},
    "DECKPORCHELEVATED": {"Composite", "Wood", "Masonry/Concrete", "No Deck/Porch", "Unknown"},
    "FENCEATTACHEDTOSTRUCTURE": {"Combustible", "Non Combustible", "No Fence", "Unknown"},
    "UTILITYMISCSTRUCTUREDISTANCE": {"<30'", "30-50'", ">50'", "Not Applicable", "Unknown"},
}
MEASURE_IDS = {
    "class_a_roof", "ember_zone_5ft", "noncombustible_6in_walls", "ember_resistant_vents",
    "double_pane_or_shutters", "enclosed_eaves", "clear_under_decks", "outbuildings_30ft",
    "defensible_space", "firewise_usa", "fire_risk_reduction_community",
}
FIX_KEYS = {"measure_id", "name", "cost_low", "cost_high", "impact_after", "est_annual_benefit",
            "payback_years", "within_budget", "why", "assumptions"}


def _num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _prob(x) -> bool:
    return _num(x) and 0 <= x <= 1


def validate_inputs(inputs: dict) -> list[str]:
    errs = []
    for key in ("address", "home", "measures_done", "insurance", "budget"):
        if key not in inputs:
            errs.append(f"inputs.{key} missing")
    for field, allowed in HOME_OPTIONS.items():
        v = inputs.get("home", {}).get(field)
        if v not in allowed:
            errs.append(f"inputs.home.{field}={v!r} not one of the DINS options")
    for m in inputs.get("measures_done", []):
        if m not in MEASURE_IDS:
            errs.append(f"inputs.measures_done has unknown measure {m!r}")
    if not _num(inputs.get("budget")) or inputs.get("budget", 0) < 0:
        errs.append("inputs.budget must be a number >= 0")
    return errs


def validate_output(out: dict) -> list[str]:
    errs = []
    cur, fut = out.get("current", {}), out.get("future", {})
    wf, house = cur.get("wildfire", {}), cur.get("house", {})
    if not _prob(wf.get("p_fire_annual")):
        errs.append("current.wildfire.p_fire_annual must be a probability 0-1")
    if not isinstance(wf.get("rating"), str):
        errs.append("current.wildfire.rating must be text")
    if not _prob(house.get("impact")):
        errs.append("current.house.impact must be 0-1")
    if not isinstance(house.get("rating"), str):
        errs.append("current.house.rating must be text")
    for g in cur.get("insurance_gap", []):
        if g.get("severity") not in ("high", "medium", "low") or not g.get("gap"):
            errs.append(f"bad insurance_gap entry {g!r}")
    fixes = fut.get("fixes")
    if not isinstance(fixes, list):
        errs.append("future.fixes must be a list")
        fixes = []
    for f in fixes:
        missing = FIX_KEYS - f.keys()
        if missing:
            errs.append(f"fix {f.get('measure_id')!r} missing {sorted(missing)}")
        if f.get("measure_id") not in MEASURE_IDS:
            errs.append(f"fix has unknown measure_id {f.get('measure_id')!r}")
        if _num(f.get("cost_low")) and _num(f.get("cost_high")) and f["cost_low"] > f["cost_high"]:
            errs.append(f"fix {f['measure_id']}: cost_low > cost_high")
        if "impact_after" in f and not _prob(f["impact_after"]):
            errs.append(f"fix {f.get('measure_id')}: impact_after must be 0-1")
        if _prob(f.get("impact_after")) and _prob(house.get("impact")) and f["impact_after"] > house["impact"] + 1e-9:
            errs.append(f"fix {f['measure_id']}: impact_after higher than current impact")
    plan = fut.get("plan_within_budget", [])
    if not set(plan) <= {f.get("measure_id") for f in fixes}:
        errs.append("future.plan_within_budget lists a fix not in future.fixes")
    if not _prob(fut.get("house_after_plan", {}).get("impact")):
        errs.append("future.house_after_plan.impact must be 0-1")
    if not isinstance(out.get("caveats"), list):
        errs.append("caveats must be a list")
    return errs
