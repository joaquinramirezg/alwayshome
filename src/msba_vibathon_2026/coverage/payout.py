"""What the policy pays, shortfalls and totals. Pure functions.

Each component has two payout cases that differ only when an input is unknown:
shortfall.low = max(0, cost.low - high case), shortfall.high = max(0, cost.high - low case).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import load_config
from .costs import UNKNOWN, CostBreakdown
from .schemas import PolicyInput, Range


@dataclass
class PayoutItem:
    payout: Range
    shortfall: Range
    notes: list[str] = field(default_factory=list)


@dataclass
class PayoutBreakdown:
    items: dict[str, PayoutItem]
    warnings: list[str]


@dataclass
class Totals:
    deductible: float | None
    total_cost: Range
    total_payout: Range
    total_shortfall: Range
    expected_shortfall: Range | None
    warnings: list[str]


def _is_known(r: Range) -> bool:
    return r.low is not None and r.high is not None


def _shortfall(cost: Range, case_low: float | None, case_high: float | None) -> Range:
    if not _is_known(cost):
        return UNKNOWN
    return Range(low=round(max(0, cost.low - case_high), 2), high=round(max(0, cost.high - case_low), 2))


def _fixed(cost: Range, amount: float, notes: list[str] | None = None) -> PayoutItem:
    """A known amount: both payout cases are the same."""
    return PayoutItem(Range(low=amount, high=amount), _shortfall(cost, amount, amount), notes or [])


def _unknown(cost: Range, note: str) -> PayoutItem:
    """An unknown amount: the low shortfall assumes fully covered, the high assumes nothing is paid."""
    if not _is_known(cost):
        return PayoutItem(UNKNOWN, UNKNOWN, [note])
    return PayoutItem(Range(low=0, high=cost.high), _shortfall(cost, 0, cost.high), [note])


def _is_fair_plan(policy: PolicyInput) -> bool:
    return policy.document_type == "fair_plan"


def _rebuild(policy: PolicyInput, cost: Range) -> PayoutItem:
    notes = []
    if policy.guaranteed_replacement is None:
        notes.append("Guaranteed replacement not stated: treated as not included.")
    if policy.dwelling_settlement == "actual_cash_value":
        notes.append("Computed as if the policy paid replacement cost. With actual cash value, "
                     "the real shortfall may be higher than the high figure shown.")
    elif policy.dwelling_settlement in ("unknown", None):
        notes.append("Dwelling settlement type unknown: treated as replacement cost.")

    if policy.guaranteed_replacement:
        if not _is_known(cost):
            return PayoutItem(UNKNOWN, UNKNOWN, notes)
        return PayoutItem(cost, Range(low=0, high=0), notes)
    if policy.dwelling_limit is None:
        item = _unknown(cost, "Dwelling limit unknown: the low shortfall assumes the rebuild is fully covered.")
        item.notes = notes + item.notes
        return item

    if policy.extended_replacement_pct is None:
        notes.append("Extended replacement not stated: treated as none.")
    cap = round(policy.dwelling_limit * (1 + (policy.extended_replacement_pct or 0)), 2)
    if not _is_known(cost):
        return _fixed(cost, cap, notes)
    return PayoutItem(Range(low=min(cost.low, cap), high=min(cost.high, cap)), _shortfall(cost, cap, cap), notes)


def _code_upgrade(policy: PolicyInput, cost: Range) -> PayoutItem:
    if policy.code_upgrade_amount is not None:
        return _fixed(cost, policy.code_upgrade_amount)
    if policy.code_upgrade is False:
        return _fixed(cost, 0)
    return _unknown(cost, "Code upgrade amount unknown: the low shortfall assumes it is fully covered.")


def _other_structures(policy: PolicyInput, cost: Range) -> PayoutItem:
    limit = policy.other_structures_limit
    if limit is not None and limit > 0:
        return _fixed(cost, limit)
    if _is_fair_plan(policy):
        if policy.dwelling_limit is None:
            return _unknown(cost, "Other structures payout unknown: no Coverage B or dwelling limit.")
        share = load_config().fair_plan_other_structures_pct_of_dwelling
        return _fixed(cost, round(policy.dwelling_limit * share.value, 2),
                      [f"{share.note} This may come out of the Coverage A limit rather than add to it, "
                       "which would raise the shortfall."])
    if limit is None:
        return _unknown(cost, "Other structures limit unknown: the low shortfall assumes it is fully covered.")
    return _fixed(cost, limit)


def _contents(policy: PolicyInput, cost: Range) -> PayoutItem:
    limit = policy.contents_limit
    if limit is None:
        return _unknown(cost, "Contents limit unknown: the low shortfall assumes it is fully covered.")
    return _fixed(cost, limit, [load_config().contents_no_inventory_rule.note] if limit > 0 else [])


def _living_expenses(policy: PolicyInput, cost: Range) -> PayoutItem:
    limit = policy.loss_of_use_limit
    if limit is not None:
        return _fixed(cost, limit)
    if _is_fair_plan(policy):
        return _fixed(cost, 0, ["No loss of use limit on the FAIR Plan page: treated as $0."])
    return _unknown(cost, "Loss of use limit unknown: the low shortfall assumes it is fully covered.")


def compute_payouts(policy: PolicyInput, costs: CostBreakdown) -> PayoutBreakdown:
    warnings = []
    if policy.dwelling_settlement == "actual_cash_value":
        warnings.append(load_config().acv_warning.text)
    if policy.contents_settlement == "actual_cash_value":
        warnings.append("Your contents coverage pays actual cash value (depreciated value), "
                        "so the contents payout could be lower than shown.")
    if policy.has_dic:
        covers = ", ".join(policy.dic_covers) if policy.dic_covers else "nothing listed"
        warnings.append(f"Your supplemental (DIC) policy is not counted in these dollar amounts. It covers: {covers}.")

    return PayoutBreakdown(
        items={
            "rebuild": _rebuild(policy, costs.items["rebuild"].cost),
            "code_upgrade": _code_upgrade(policy, costs.items["code_upgrade"].cost),
            "other_structures": _other_structures(policy, costs.items["other_structures"].cost),
            "contents": _contents(policy, costs.items["contents"].cost),
            "living_expenses": _living_expenses(policy, costs.items["living_expenses"].cost),
        },
        warnings=warnings,
    )


def _sum(ranges: list[Range], extra: float = 0) -> Range:
    if not ranges:
        return UNKNOWN
    return Range(low=round(sum(r.low for r in ranges) + extra, 2), high=round(sum(r.high for r in ranges) + extra, 2))


def compute_totals(policy: PolicyInput, costs: CostBreakdown, payouts: PayoutBreakdown,
                   p_destroyed: float | None) -> Totals:
    """Sum the components with a known cost and add the deductible once to the shortfall."""
    warnings = []
    deductible = policy.deductible_wildfire if policy.deductible_wildfire is not None else policy.deductible_all_perils
    if deductible is None:
        warnings.append("Deductible unknown: counted as $0 in the total shortfall.")

    known = [name for name, item in costs.items.items() if _is_known(item.cost)]
    excluded = [name for name in costs.items if name not in known]
    if excluded:
        warnings.append(f"Totals leave out components with unknown cost, so they are minimums: {', '.join(excluded)}.")

    # Each payout is capped at its cost here, because a limit above the loss is not money paid.
    capped = [Range(low=min(payouts.items[name].payout.low, costs.items[name].cost.low),
                    high=min(payouts.items[name].payout.high, costs.items[name].cost.high)) for name in known]
    total_shortfall = _sum([payouts.items[name].shortfall for name in known], extra=deductible or 0)
    expected = None
    if p_destroyed is not None and _is_known(total_shortfall):
        expected = Range(low=round(p_destroyed * total_shortfall.low, 2), high=round(p_destroyed * total_shortfall.high, 2))

    return Totals(
        deductible=deductible,
        total_cost=_sum([costs.items[name].cost for name in known]),
        total_payout=_sum(capped),
        total_shortfall=total_shortfall,
        expected_shortfall=expected,
        warnings=warnings,
    )
