"""Connects the coverage module to assess(): converts the app's inputs and formats the gaps."""
from __future__ import annotations

import logging

from ..gaps import coverage_gaps
from .scenario import run_coverage_analysis
from .schemas import Gap, HomeInput, PolicyInput, RiskInput

logger = logging.getLogger(__name__)

# Gap id -> the title the homeowner sees. The evidence and action become the explanation.
GAP_TITLES = {
    "underinsured": "Underinsured for today's rebuild costs",
    "possibly_underinsured": "Coverage may not pay for a full rebuild",
    "stale_coverage": "Coverage may be out of date",
    "fair_no_dic": "FAIR Plan only, no supplemental (DIC) policy",
    "actual_cash_value": "Dwelling paid at actual cash value",
    "low_extended_replacement": "No or low extended replacement cost",
    "no_code_upgrade": "No or low building code upgrade coverage",
    "no_debris_removal": "Debris removal not covered",
    "no_living_expenses": "No loss-of-use coverage",
    "no_contents": "No contents coverage",
    "above_fair_cap": "Your needs may exceed the FAIR Plan limit",
    "renewal_risk": "Non-renewal notice",
    "unknown_field": "Check your declarations page",
}
SEVERITY = {"high": "high", "medium": "medium", "info": "low"}  # the contract's words
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _covered(value) -> bool | None:
    """The extractor gives {covered, limit, pct}; the form gives a boolean."""
    return value.get("covered") if isinstance(value, dict) else value


def _code_upgrade_amount(ins: dict) -> float | None:
    if ins.get("code_upgrade_amount") is not None:
        return ins["code_upgrade_amount"]
    code = ins.get("code_upgrade")
    if not isinstance(code, dict):
        return None
    if code.get("limit") is not None:
        return code["limit"]
    if code.get("pct") is not None and ins.get("dwelling_limit") is not None:
        return code["pct"] / 100 * ins["dwelling_limit"]
    return None


def _wildfire_deductible(ins: dict) -> float | None:
    value = ins.get("deductible_wildfire")
    if not isinstance(value, dict):
        return value
    if value.get("amount") is not None:
        return value["amount"]
    if value.get("pct") is not None and ins.get("dwelling_limit") is not None:
        return value["pct"] / 100 * ins["dwelling_limit"]
    return None


def _document_type(ins: dict) -> str | None:
    documents = ins.get("documents") or []
    if "fair_plan" in documents:
        return "fair_plan"
    known = [d for d in documents if d and d != "dic"] or [d for d in documents if d]
    return known[0] if known else ins.get("document_type")


def to_policy_input(ins: dict) -> PolicyInput:
    """App or extractor insurance dict -> PolicyInput. Percentages here are whole numbers (25 for 25%)."""
    extended = ins.get("extended_replacement_pct")
    deductible = ins.get("deductible_all_perils")
    return PolicyInput(
        document_type=_document_type(ins),
        has_dic=ins.get("has_dic"),
        dic_covers=ins.get("dic_covers") or [],
        premium_total=ins.get("premium_total") if ins.get("premium_total") is not None else ins.get("annual_premium"),
        dwelling_limit=ins.get("dwelling_limit"),
        other_structures_limit=ins.get("other_structures_limit"),
        contents_limit=ins.get("contents_limit"),
        loss_of_use_limit=ins.get("loss_of_use_limit"),
        dwelling_settlement=ins.get("dwelling_settlement"),
        extended_replacement_pct=None if extended is None else extended / 100,
        guaranteed_replacement=ins.get("guaranteed_replacement"),
        contents_settlement=ins.get("contents_settlement"),
        code_upgrade=_covered(ins.get("code_upgrade")),
        code_upgrade_amount=_code_upgrade_amount(ins),
        debris_removal=_covered(ins.get("debris_removal")),
        deductible_all_perils=deductible if deductible is not None else ins.get("deductible"),
        deductible_wildfire=_wildfire_deductible(ins),
        last_coverage_update_year=ins.get("last_coverage_update_year"),
        nonrenewal_notice=ins.get("nonrenewal_notice"),
    )


def to_home_input(home: dict, area: dict) -> HomeInput:
    return HomeInput(
        zip=(area.get("geocode") or {}).get("zip") or "",
        sq_ft=home.get("living_area_sqft"),
        stories=home.get("stories"),
        year_built=home.get("year_built"),
        contents_value_estimate=home.get("contents_value_estimate"),
        other_structures_estimate=home.get("other_structures_estimate"),
        renovated_since_update=home.get("renovated_since_update"),
    )


def coverage_for_assess(inputs: dict, area: dict) -> dict | None:
    """The contract's `current.coverage` block, or None so the plan still finishes if this step fails.

    p_destroyed stays None until a real house model exists: FEMA's frequency times a placeholder
    damage score would look like a probability without being one.
    """
    try:
        return run_coverage_analysis(to_policy_input(inputs.get("insurance", {})),
                                     to_home_input(inputs.get("home", {}), area),
                                     RiskInput(p_destroyed=None)).model_dump()
    except Exception:
        logger.exception("Coverage analysis failed; falling back to the basic gap rules")
        return None


def _display_gap(gap: Gap | dict) -> dict:
    g = Gap.model_validate(gap)
    return {"gap": GAP_TITLES.get(g.gap, g.gap), "severity": SEVERITY[g.severity], "why": f"{g.evidence} {g.action}"}


def display_gaps(coverage: dict, ins: dict) -> list[dict]:
    """The module's gaps in the contract's shape, plus the liability rule the module doesn't cover."""
    gaps = [_display_gap(g) for g in coverage["gaps"]]
    gaps += [g for g in coverage_gaps(ins) if "liability" in g["gap"].lower()]
    return sorted(gaps, key=lambda g: SEVERITY_ORDER[g["severity"]])
