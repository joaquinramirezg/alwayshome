"""Coverage gap rules. Each rule returns a Gap or None; add new ones to GAP_RULES."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from .config import load_config
from .costs import CostBreakdown
from .schemas import Gap, HomeInput, PolicyInput


@dataclass
class GapContext:
    policy: PolicyInput
    home: HomeInput
    costs: CostBreakdown
    as_of_year: int

    @property
    def is_fair_plan(self) -> bool:
        return self.policy.document_type == "fair_plan"


def _usd(value: float) -> str:
    return f"${value:,.0f}"


def _coverage_per_sqft(ctx: GapContext) -> float | None:
    if ctx.policy.dwelling_limit is None or not ctx.home.sq_ft:
        return None
    return ctx.policy.dwelling_limit / ctx.home.sq_ft


def _rebuild_evidence(per_sqft: float) -> str:
    rate = load_config().rebuild_cost_per_sqft
    return f"Coverage {_usd(per_sqft)}/sq ft; rebuild estimates {_usd(rate.low)} to {_usd(rate.high)}+/sq ft."


def underinsured(ctx: GapContext) -> Gap | None:
    per_sqft = _coverage_per_sqft(ctx)
    rate = load_config().rebuild_cost_per_sqft
    if per_sqft is None or per_sqft >= rate.low:
        return None
    return Gap(gap="underinsured", severity="high", evidence=_rebuild_evidence(per_sqft),
               action="Ask your insurer to update your dwelling limit to current rebuild costs.",
               source_url=rate.source_url)


def possibly_underinsured(ctx: GapContext) -> Gap | None:
    per_sqft = _coverage_per_sqft(ctx)
    rate = load_config().rebuild_cost_per_sqft
    if per_sqft is None or not rate.low <= per_sqft < rate.high:
        return None
    return Gap(gap="possibly_underinsured", severity="medium", evidence=_rebuild_evidence(per_sqft),
               action="Your coverage may not cover a full rebuild at today's costs.", source_url=rate.source_url)


def stale_coverage(ctx: GapContext) -> Gap | None:
    threshold = load_config().stale_coverage_years
    reasons = []
    last = ctx.policy.last_coverage_update_year
    if last is not None and ctx.as_of_year - last >= threshold.value:
        reasons.append(f"Coverage last updated in {last}, {ctx.as_of_year - last} years ago "
                       f"(flagged at {threshold.value} years).")
    if ctx.home.renovated_since_update:
        reasons.append("Home renovated since the last coverage update.")
    if not reasons:
        return None
    return Gap(gap="stale_coverage", severity="medium", evidence=" ".join(reasons),
               action="Ask your insurer to review your coverage amount.", source_url=threshold.source_url)


def fair_no_dic(ctx: GapContext) -> Gap | None:
    if not ctx.is_fair_plan or ctx.policy.has_dic is not False:
        return None
    return Gap(gap="fair_no_dic", severity="high", evidence="FAIR Plan policy with no supplemental (DIC) policy.",
               action="The FAIR Plan doesn't cover water damage, theft or liability. "
                      "A supplemental (DIC) policy fills those gaps.",
               source_url=None)


def actual_cash_value(ctx: GapContext) -> Gap | None:
    if ctx.policy.dwelling_settlement != "actual_cash_value":
        return None
    return Gap(gap="actual_cash_value", severity="high", evidence="Dwelling settlement is actual cash value.",
               action="Ask about replacement cost coverage.", source_url=load_config().acv_warning.source_url)


def low_extended_replacement(ctx: GapContext) -> Gap | None:
    minimum = load_config().extended_replacement_recommended_min_pct
    pct = ctx.policy.extended_replacement_pct
    if ctx.policy.guaranteed_replacement or (pct or 0) >= minimum.value:
        return None
    current = "none listed" if pct is None else f"{pct:.0%}"
    return Gap(gap="low_extended_replacement", severity="medium",
               evidence=f"Extended replacement: {current}; advised at least {minimum.value:.0%}.",
               action="California experts advise 25% to 50% extended replacement cost.",
               source_url=minimum.source_url)


def no_code_upgrade(ctx: GapContext) -> Gap | None:
    share = load_config().code_upgrade_recommended_pct_of_dwelling
    action = "Code upgrades after a fire can reach six figures."
    policy = ctx.policy
    if policy.code_upgrade is False:
        return Gap(gap="no_code_upgrade", severity="high", evidence="No code upgrade coverage on this policy.",
                   action=action, source_url=share.source_url)
    if policy.code_upgrade_amount is None or policy.dwelling_limit is None:
        return None
    recommended = policy.dwelling_limit * share.low
    if policy.code_upgrade_amount >= recommended:
        return None
    return Gap(gap="no_code_upgrade", severity="medium",
               evidence=f"Code upgrade coverage {_usd(policy.code_upgrade_amount)}; "
                        f"{share.low:.0%} of your dwelling limit is {_usd(recommended)}.",
               action=action, source_url=share.source_url)


def no_debris_removal(ctx: GapContext) -> Gap | None:
    if ctx.policy.debris_removal is not False:
        return None
    note = load_config().debris_removal_note
    return Gap(gap="no_debris_removal", severity="medium", evidence="No debris removal coverage on this policy.",
               action=note.text, source_url=note.source_url)


def no_living_expenses(ctx: GapContext) -> Gap | None:
    limit = ctx.policy.loss_of_use_limit
    if not ctx.is_fair_plan or limit not in (0, None):
        return None
    cost = ctx.costs.items["living_expenses"].cost
    evidence = "Loss of use limit: " + ("$0." if limit == 0 else "not on the page.")
    if cost.low is not None and cost.high is not None:
        evidence += f" Estimated living expenses: {_usd(cost.low)} to {_usd(cost.high)}."
    return Gap(gap="no_living_expenses", severity="high", evidence=evidence,
               action="If your home is destroyed, you'd pay rent yourself during rebuilding.",
               source_url=load_config().living_expense_months.source_url)


def no_contents(ctx: GapContext) -> Gap | None:
    if ctx.policy.contents_limit != 0:
        return None
    return Gap(gap="no_contents", severity="high", evidence="Contents limit: $0.",
               action="Your belongings aren't covered.", source_url=None)


def above_fair_cap(ctx: GapContext) -> Gap | None:
    cap = load_config().fair_plan_combined_cap
    rebuild_high = ctx.costs.items["rebuild"].cost.high
    if not ctx.is_fair_plan or rebuild_high is None:
        return None
    needed = rebuild_high + (ctx.costs.items["contents"].cost.high or 0)
    if needed <= cap.value:
        return None
    return Gap(gap="above_fair_cap", severity="high",
               evidence=f"Rebuild plus contents up to {_usd(needed)}; FAIR Plan combined limit {_usd(cap.value)}.",
               action="Your needs may exceed the FAIR Plan's combined limit.", source_url=cap.source_url)


def renewal_risk(ctx: GapContext) -> Gap | None:
    if ctx.policy.nonrenewal_notice is not True:
        return None
    return Gap(gap="renewal_risk", severity="medium", evidence="Your policy has a non-renewal notice.",
               action="Prioritize fire-safety fixes before your renewal date.", source_url=None)


def _unknown_field(field: str, label: str, skip_on_fair_plan: bool = False) -> Callable[[GapContext], Gap | None]:
    """One rule per field, so each unknown field gets its own gap."""

    def rule(ctx: GapContext) -> Gap | None:
        if getattr(ctx.policy, field) is not None or (skip_on_fair_plan and ctx.is_fair_plan):
            return None
        return Gap(gap="unknown_field", severity="info", evidence=f"Not found on your policy: {label} ({field}).",
                   action=f"Check your declarations page for {label}.", source_url=None)

    return rule


GAP_RULES: list[Callable[[GapContext], Gap | None]] = [
    underinsured,
    possibly_underinsured,
    stale_coverage,
    fair_no_dic,
    actual_cash_value,
    low_extended_replacement,
    no_code_upgrade,
    no_debris_removal,
    no_living_expenses,
    no_contents,
    above_fair_cap,
    renewal_risk,
    _unknown_field("dwelling_limit", "your dwelling limit"),
    _unknown_field("dwelling_settlement", "how the dwelling is settled"),
    _unknown_field("code_upgrade", "code upgrade coverage"),
    # On a FAIR Plan a missing limit is treated as $0, and no_living_expenses already covers it.
    _unknown_field("loss_of_use_limit", "your loss of use limit", skip_on_fair_plan=True),
]


def find_gaps(policy: PolicyInput, home: HomeInput, costs: CostBreakdown, as_of_year: int | None = None) -> list[Gap]:
    """Run every rule. `as_of_year` defaults to the current year."""
    ctx = GapContext(policy, home, costs, as_of_year if as_of_year is not None else date.today().year)
    return [gap for rule in GAP_RULES if (gap := rule(ctx)) is not None]
