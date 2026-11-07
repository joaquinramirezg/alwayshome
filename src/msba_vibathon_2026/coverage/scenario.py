"""run_coverage_analysis(): the module's one entry point."""
from __future__ import annotations

from .config import Config, ContentsRule, IntRange, IntValue, ShareRange, ShareValue, Sourced, TextNote, load_config
from .costs import compute_costs
from .gaps import find_gaps
from .payout import compute_payouts, compute_totals
from .rent import RENT_SOURCE_URL, monthly_rent
from .schemas import Component, CoverageResult, HomeInput, PolicyInput, RiskInput

SCOPE_NOTE = "Total-loss scenario only. Partial damage not modeled."
# Has a source, but Step 4 uses a coverage recommendation as a cost, so the output labels it.
USED_AS_ASSUMPTION = {"code_upgrade_recommended_pct_of_dwelling"}


def _value_text(section: Sourced) -> str:
    if isinstance(section, (IntRange, ShareRange)):
        return f"{section.low} to {section.high}"
    if isinstance(section, (IntValue, ShareValue)):
        return f"{section.value}"
    if isinstance(section, ContentsRule):
        return f"{section.pct_of_limit} of limit, up to {section.cap}, effective {section.effective}"
    if isinstance(section, TextNote):
        return section.text
    raise TypeError(f"No text format for {type(section).__name__}")


def _assumption_line(name: str, section: Sourced) -> str:
    parts = [f"{name}: {_value_text(section)}."]
    if section.assumption or name in USED_AS_ASSUMPTION:
        parts.append("Assumption.")
    if section.source_url:
        parts.append(f"Source: {section.source_url}.")
    if section.note:
        parts.append(section.note)
    return " ".join(parts)


def _assumptions(config: Config, zip_code: str, rent: float | None) -> list[str]:
    lines = [_assumption_line(name, getattr(config, name)) for name in type(config).model_fields]
    if rent is None:
        lines.append(f"Monthly rent for ZIP {zip_code}: no rent data.")
    else:
        lines.append(f"Monthly rent for ZIP {zip_code}: ${rent:,.0f}. "
                     f"Zillow Observed Rent Index. Source: {RENT_SOURCE_URL}.")
    return lines


def run_coverage_analysis(policy: PolicyInput, home: HomeInput, risk: RiskInput,
                          as_of_year: int | None = None) -> CoverageResult:
    """If a wildfire destroys this home, what does it cost, what does the policy pay, and who pays the rest?

    `as_of_year` sets the year used to judge stale coverage; it defaults to the current year.
    """
    config = load_config()
    rent = monthly_rent(home.zip)
    costs = compute_costs(policy, home, rent)
    payouts = compute_payouts(policy, costs)
    totals = compute_totals(policy, costs, payouts, risk.p_destroyed)
    gaps = find_gaps(policy, home, costs, as_of_year=as_of_year)

    components = [
        Component(name=name, cost=cost.cost, payout=payouts.items[name].payout,
                  shortfall=payouts.items[name].shortfall, notes=cost.notes + payouts.items[name].notes)
        for name, cost in costs.items.items()
    ]
    warnings = [*payouts.warnings, *costs.warnings, config.price_surge_note.text, *totals.warnings]

    return CoverageResult(
        scope_note=SCOPE_NOTE,
        p_destroyed=risk.p_destroyed,
        components=components,
        deductible=totals.deductible,
        total_cost=totals.total_cost,
        total_payout=totals.total_payout,
        total_shortfall=totals.total_shortfall,
        expected_shortfall=totals.expected_shortfall,
        gaps=gaps,
        warnings=warnings,
        premium_total=policy.premium_total,
        assumptions=_assumptions(config, home.zip, rent),
    ).model_copy(deep=True)  # so a caller editing the result cannot change shared values
