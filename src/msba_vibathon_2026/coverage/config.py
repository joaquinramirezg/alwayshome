"""Load and validate config.yaml, the only home of the module's numbers and sources."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

CONFIG_PATH = Path(__file__).with_name("config.yaml")


class Sourced(BaseModel):
    """A config entry: it must cite a source or be marked as an assumption."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_url: str | None = None
    assumption: bool = False
    note: str | None = None

    @model_validator(mode="after")
    def has_source_or_assumption(self):
        if not self.source_url and not self.assumption:
            raise ValueError("needs a source_url or assumption: true")
        return self


class IntRange(Sourced):
    low: int
    high: int

    @model_validator(mode="after")
    def low_not_above_high(self):
        if self.low > self.high:
            raise ValueError("low is above high")
        return self


class ShareRange(Sourced):
    low: float
    high: float

    @model_validator(mode="after")
    def low_not_above_high(self):
        if self.low > self.high:
            raise ValueError("low is above high")
        return self


class IntValue(Sourced):
    value: int


class ShareValue(Sourced):
    value: float


class TextNote(Sourced):
    text: str


class ContentsRule(Sourced):
    pct_of_limit: float
    cap: int
    effective: str


class Config(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    rebuild_cost_per_sqft: IntRange
    price_surge_note: TextNote
    code_upgrade_recommended_pct_of_dwelling: ShareRange
    other_structures_cost_pct_of_rebuild: ShareValue
    fair_plan_other_structures_pct_of_dwelling: ShareValue
    living_expense_months: IntRange
    fair_plan_combined_cap: IntValue
    extended_replacement_recommended_min_pct: ShareValue
    stale_coverage_years: IntValue
    contents_no_inventory_rule: ContentsRule
    debris_removal_note: TextNote
    acv_warning: TextNote


@lru_cache(maxsize=1)
def load_config() -> Config:
    """Read config.yaml once. Raises pydantic.ValidationError if it is incomplete or invalid."""
    return Config.model_validate(yaml.safe_load(CONFIG_PATH.read_text()))
