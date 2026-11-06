"""Cost of a total loss, by component. Pure functions: rent is passed in."""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import load_config
from .schemas import HomeInput, PolicyInput, Range

UNKNOWN = Range(low=None, high=None)


@dataclass
class CostItem:
    cost: Range
    notes: list[str] = field(default_factory=list)


@dataclass
class CostBreakdown:
    items: dict[str, CostItem]
    warnings: list[str]


def _times(value: float, low: float, high: float) -> Range:
    """value x (low, high), rounded to cents to remove float noise."""
    return Range(low=round(value * low, 2), high=round(value * high, 2))


def _same(value: float) -> Range:
    return Range(low=value, high=value)


def _rebuild(home: HomeInput) -> CostItem:
    rate = load_config().rebuild_cost_per_sqft
    if home.sq_ft is None:
        return CostItem(UNKNOWN, ["Rebuild cost unknown: square footage not provided."])
    return CostItem(_times(home.sq_ft, rate.low, rate.high))


def _code_upgrade(policy: PolicyInput) -> CostItem:
    share = load_config().code_upgrade_recommended_pct_of_dwelling
    if policy.dwelling_limit is None:
        return CostItem(UNKNOWN, ["Code upgrade cost unknown: dwelling limit not provided."])
    return CostItem(_times(policy.dwelling_limit, share.low, share.high),
                    [f"Assumption: {share.low:.0%} to {share.high:.0%} of the dwelling limit. "
                     "This is an expert recommendation, not a measured cost."])


def _other_structures(home: HomeInput, rebuild: Range) -> CostItem:
    if home.other_structures_estimate is not None:
        return CostItem(_same(home.other_structures_estimate))
    if rebuild.low is None or rebuild.high is None:
        return CostItem(UNKNOWN, ["Other structures cost unknown: no estimate and no rebuild cost."])
    share = load_config().other_structures_cost_pct_of_rebuild.value
    return CostItem(_times(1, rebuild.low * share, rebuild.high * share),
                    [f"Assumed {share:.0%} of rebuild cost because no estimate was given."])


def _contents(policy: PolicyInput, home: HomeInput) -> CostItem:
    if home.contents_value_estimate is not None:
        return CostItem(_same(home.contents_value_estimate))
    if policy.contents_limit is not None:
        return CostItem(_same(policy.contents_limit), ["Contents value assumed equal to your limit."])
    return CostItem(UNKNOWN, ["Contents cost unknown: no estimate and no contents limit."])


def _living_expenses(rent: float | None) -> CostItem:
    months = load_config().living_expense_months
    if rent is None:
        return CostItem(UNKNOWN, ["Living expenses unknown: no rent data for ZIP."])
    return CostItem(_times(rent, months.low, months.high))


def compute_costs(policy: PolicyInput, home: HomeInput, rent: float | None) -> CostBreakdown:
    """Cost of each component. `rent` is the monthly rent for the ZIP, or None."""
    rebuild = _rebuild(home)
    return CostBreakdown(
        items={
            "rebuild": rebuild,
            "code_upgrade": _code_upgrade(policy),
            "other_structures": _other_structures(home, rebuild.cost),
            "contents": _contents(policy, home),
            "living_expenses": _living_expenses(rent),
        },
        warnings=[load_config().debris_removal_note.text],
    )
