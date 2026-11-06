"""Step 3: input and output models match the plan, and unknown inputs are allowed."""
import pytest
from pydantic import ValidationError

from msba_vibathon_2026.coverage.schemas import (Component, CoverageResult, Gap, HomeInput, PolicyInput, Range,
                                                 RiskInput)

POLICY_FIELDS = {
    "document_type", "has_dic", "dic_covers", "premium_total", "dwelling_limit", "other_structures_limit",
    "contents_limit", "loss_of_use_limit", "dwelling_settlement", "extended_replacement_pct",
    "guaranteed_replacement", "contents_settlement", "code_upgrade", "code_upgrade_amount", "debris_removal",
    "deductible_all_perils", "deductible_wildfire", "last_coverage_update_year", "nonrenewal_notice",
}
HOME_FIELDS = {"zip", "sq_ft", "stories", "year_built", "contents_value_estimate", "other_structures_estimate",
               "renovated_since_update"}
RESULT_FIELDS = {"scope_note", "p_destroyed", "components", "deductible", "total_cost", "total_payout",
                 "total_shortfall", "expected_shortfall", "gaps", "warnings", "premium_total", "assumptions"}


def make_range() -> Range:
    return Range(low=1.0, high=2.0)


def make_component(name="rebuild") -> Component:
    return Component(name=name, cost=make_range(), payout=make_range(), shortfall=make_range())


def make_gap(severity="high") -> Gap:
    return Gap(gap="underinsured", severity=severity, evidence="Coverage $250/sq ft", action="Ask", source_url=None)


# ---------------------------------------------------------------- field names
def test_field_names_match_the_plan():
    assert set(PolicyInput.model_fields) == POLICY_FIELDS
    assert set(HomeInput.model_fields) == HOME_FIELDS
    assert set(RiskInput.model_fields) == {"p_destroyed"}
    assert set(Range.model_fields) == {"low", "high"}
    assert set(Component.model_fields) == {"name", "cost", "payout", "shortfall", "notes"}
    assert set(Gap.model_fields) == {"gap", "severity", "evidence", "action", "source_url"}
    assert set(CoverageResult.model_fields) == RESULT_FIELDS


# --------------------------------------------------------------------- inputs
def test_policy_can_be_entirely_unknown():
    policy = PolicyInput()
    assert all(getattr(policy, f) is None for f in POLICY_FIELDS - {"dic_covers"})
    assert policy.dic_covers == []


def test_home_needs_only_a_zip():
    home = HomeInput(zip="91001")
    assert home.zip == "91001"
    assert all(getattr(home, f) is None for f in HOME_FIELDS - {"zip"})


def test_home_without_a_zip_is_rejected():
    with pytest.raises(ValidationError):
        HomeInput()


def test_risk_can_be_unknown():
    assert RiskInput().p_destroyed is None
    assert RiskInput(p_destroyed=0.3).p_destroyed == 0.3


def test_zero_stays_distinct_from_unknown():
    policy = PolicyInput(other_structures_limit=0, contents_limit=0)
    assert policy.other_structures_limit == 0
    assert policy.contents_limit == 0
    assert policy.loss_of_use_limit is None


def test_dic_covers_lists_are_not_shared():
    first = PolicyInput()
    first.dic_covers.append("theft")
    assert PolicyInput().dic_covers == []


@pytest.mark.parametrize("field, value", [
    ("document_type", "renters"),
    ("dwelling_settlement", "market_value"),
    ("contents_settlement", "market_value"),
    ("dwelling_limit", "a lot"),
])
def test_invalid_policy_values_are_rejected(field, value):
    with pytest.raises(ValidationError):
        PolicyInput(**{field: value})


@pytest.mark.parametrize("value", ["fair_plan", "dic", "homeowners", "dwelling_fire", "other"])
def test_every_document_type_is_accepted(value):
    assert PolicyInput(document_type=value).document_type == value


@pytest.mark.parametrize("value", ["actual_cash_value", "replacement_cost", "unknown"])
def test_every_settlement_type_is_accepted(value):
    policy = PolicyInput(dwelling_settlement=value, contents_settlement=value)
    assert policy.dwelling_settlement == policy.contents_settlement == value


@pytest.mark.parametrize("value", [0, 0.25, 0.5, 1])
def test_extended_replacement_accepts_fractions(value):
    assert PolicyInput(extended_replacement_pct=value).extended_replacement_pct == value


@pytest.mark.parametrize("value", [1.01, 25, 50])
def test_extended_replacement_rejects_whole_percent_values(value):
    with pytest.raises(ValidationError):
        PolicyInput(extended_replacement_pct=value)


def test_extra_extraction_fields_are_ignored():
    policy = PolicyInput(dwelling_limit=450_000, insurer_name="Example", liability_limit=100_000)
    assert policy.dwelling_limit == 450_000
    assert not hasattr(policy, "insurer_name")


# -------------------------------------------------------------------- outputs
def test_range_bounds_can_be_unknown():
    assert Range(low=None, high=None).low is None


@pytest.mark.parametrize("name", ["rebuild", "code_upgrade", "other_structures", "contents", "living_expenses"])
def test_every_component_name_is_accepted(name):
    assert make_component(name).name == name


def test_unknown_component_name_is_rejected():
    with pytest.raises(ValidationError):
        make_component("debris_removal")


def test_component_notes_default_to_empty():
    assert make_component().notes == []


@pytest.mark.parametrize("severity", ["high", "medium", "info"])
def test_every_gap_severity_is_accepted(severity):
    assert make_gap(severity).severity == severity


def test_unknown_gap_severity_is_rejected():
    with pytest.raises(ValidationError):
        make_gap("low")


def test_result_round_trips_through_json():
    result = CoverageResult(
        scope_note="Total-loss scenario only. Partial damage not modeled.", p_destroyed=None,
        components=[make_component()], deductible=None, total_cost=make_range(), total_payout=make_range(),
        total_shortfall=make_range(), expected_shortfall=None, gaps=[make_gap()], warnings=["w"],
        premium_total=None, assumptions=["a"],
    )
    assert CoverageResult.model_validate_json(result.model_dump_json()) == result


def test_result_without_a_scope_note_is_rejected():
    with pytest.raises(ValidationError):
        CoverageResult(
            p_destroyed=None, components=[], deductible=None, total_cost=make_range(), total_payout=make_range(),
            total_shortfall=make_range(), expected_shortfall=None, gaps=[], warnings=[], premium_total=None,
            assumptions=[],
        )
