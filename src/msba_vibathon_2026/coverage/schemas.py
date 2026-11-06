"""Input and output models. On inputs, None means unknown."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Settlement = Literal["actual_cash_value", "replacement_cost", "unknown"]


# --------------------------------------------------------------------- inputs
class PolicyInput(BaseModel):
    document_type: Literal["fair_plan", "dic", "homeowners", "dwelling_fire", "other"] | None = None
    has_dic: bool | None = None                      # supplemental policy present (FAIR Plan only)
    dic_covers: list[str] = []
    premium_total: float | None = None               # all policies combined, per year
    dwelling_limit: float | None = None              # Coverage A
    other_structures_limit: float | None = None      # Coverage B; None = not on page; 0 = explicitly not covered
    contents_limit: float | None = None              # Coverage C
    loss_of_use_limit: float | None = None           # Coverage D (ALE or fair rental value)
    dwelling_settlement: Settlement | None = None
    # A fraction: 0.25 for 25%. The extraction spec returns 25, so callers must convert it.
    extended_replacement_pct: float | None = Field(default=None, le=1)
    guaranteed_replacement: bool | None = None
    contents_settlement: Settlement | None = None
    code_upgrade: bool | None = None
    code_upgrade_amount: float | None = None
    debris_removal: bool | None = None
    deductible_all_perils: float | None = None
    deductible_wildfire: float | None = None
    last_coverage_update_year: int | None = None
    nonrenewal_notice: bool | None = None


class HomeInput(BaseModel):
    zip: str
    sq_ft: float | None = None
    stories: int | None = None
    year_built: int | None = None
    contents_value_estimate: float | None = None
    other_structures_estimate: float | None = None
    renovated_since_update: bool | None = None


class RiskInput(BaseModel):
    p_destroyed: float | None = None                 # from the risk model; placeholder until it exists


# -------------------------------------------------------------------- outputs
class Range(BaseModel):
    low: float | None
    high: float | None


class Component(BaseModel):
    name: Literal["rebuild", "code_upgrade", "other_structures", "contents", "living_expenses"]
    cost: Range
    payout: Range
    shortfall: Range
    notes: list[str] = []


class Gap(BaseModel):
    gap: str
    severity: Literal["high", "medium", "info"]
    evidence: str          # plain language, includes the numbers
    action: str            # what to ask or check, never a product recommendation
    source_url: str | None


class CoverageResult(BaseModel):
    scope_note: str                          # "Total-loss scenario only. Partial damage not modeled."
    p_destroyed: float | None
    components: list[Component]
    deductible: float | None
    total_cost: Range
    total_payout: Range
    total_shortfall: Range                   # includes deductible
    expected_shortfall: Range | None         # p_destroyed x total_shortfall; secondary display
    gaps: list[Gap]
    warnings: list[str]                      # ACV, debris note, price surge, etc.
    premium_total: float | None              # passed through for the optimizer
    assumptions: list[str]                   # every config value used, with its source
