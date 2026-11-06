"""Step 7: run_coverage_analysis() combines costs, payouts, totals, gaps and warnings."""
import pytest

from msba_vibathon_2026.coverage import scenario
from msba_vibathon_2026.coverage.config import load_config
from msba_vibathon_2026.coverage.scenario import run_coverage_analysis
from msba_vibathon_2026.coverage.schemas import CoverageResult, HomeInput, PolicyInput, Range, RiskInput

AS_OF = 2026
COMPONENTS = ["rebuild", "code_upgrade", "other_structures", "contents", "living_expenses"]
UNKNOWN = Range(low=None, high=None)
FAIR_POLICY = PolicyInput(document_type="fair_plan", has_dic=False, dwelling_limit=450_000,
                          dwelling_settlement="actual_cash_value", code_upgrade=False, debris_removal=False,
                          contents_limit=0, deductible_all_perils=1_000, last_coverage_update_year=2017,
                          premium_total=6_200)
FAIR_HOME = HomeInput(zip="91001", sq_ft=1_800, contents_value_estimate=100_000)


@pytest.fixture
def rent_4000(monkeypatch):
    seen = []

    def fake(zip_code):
        seen.append(zip_code)
        return 4_000.0

    monkeypatch.setattr(scenario, "monthly_rent", fake)
    return seen


def run(policy=FAIR_POLICY, home=FAIR_HOME, p_destroyed=None):
    return run_coverage_analysis(policy, home, RiskInput(p_destroyed=p_destroyed), as_of_year=AS_OF)


def test_result_validates_against_the_schema(rent_4000):
    result = run()
    assert isinstance(result, CoverageResult)
    assert CoverageResult.model_validate_json(result.model_dump_json()) == result


def test_scope_note_is_present(rent_4000):
    assert run().scope_note == "Total-loss scenario only. Partial damage not modeled."


def test_components_come_in_order(rent_4000):
    assert [c.name for c in run().components] == COMPONENTS


def test_rent_is_looked_up_by_the_home_zip(rent_4000):
    run()
    assert rent_4000 == ["91001"]


def test_components_join_cost_payout_and_shortfall(rent_4000):
    rebuild = run().components[0]
    assert rebuild.cost == Range(low=540_000, high=900_000)
    assert rebuild.payout == Range(low=450_000, high=450_000)
    assert rebuild.shortfall == Range(low=90_000, high=450_000)


def test_component_notes_combine_cost_and_payout_notes(rent_4000):
    other = run().components[2]
    assert any("Assumed" in n for n in other.notes)
    assert any("Coverage A" in n for n in other.notes)


def test_totals_are_filled(rent_4000):
    result = run()
    assert result.deductible == 1_000
    assert result.total_cost == Range(low=902_500, high=1_459_000)
    assert result.total_payout == Range(low=495_000, high=495_000)
    assert result.total_shortfall == Range(low=408_500, high=965_000)


def test_works_without_a_probability(rent_4000):
    result = run()
    assert result.p_destroyed is None
    assert result.expected_shortfall is None


def test_uses_the_probability_when_known(rent_4000):
    result = run(p_destroyed=0.5)
    assert result.p_destroyed == 0.5
    assert result.expected_shortfall == Range(low=204_250, high=482_500)


def test_premium_is_passed_through(rent_4000):
    assert run().premium_total == 6_200


def test_gaps_are_included(rent_4000):
    assert "underinsured" in [g.gap for g in run().gaps]


def test_as_of_year_reaches_the_gap_rules(rent_4000):
    policy = FAIR_POLICY.model_copy(update={"last_coverage_update_year": 2025})
    home = FAIR_HOME
    assert "stale_coverage" not in [g.gap for g in run(policy, home).gaps]
    later = run_coverage_analysis(policy, home, RiskInput(), as_of_year=2028)
    assert "stale_coverage" in [g.gap for g in later.gaps]


def test_as_of_year_is_optional(rent_4000):
    assert "stale_coverage" in [g.gap for g in run_coverage_analysis(FAIR_POLICY, FAIR_HOME, RiskInput()).gaps]


def test_warnings_include_debris_price_surge_and_acv(rent_4000):
    config = load_config()
    warnings = run().warnings
    assert config.debris_removal_note.text in warnings
    assert config.price_surge_note.text in warnings
    assert config.acv_warning.text in warnings


def test_warnings_collect_payout_and_total_warnings(rent_4000):
    policy = FAIR_POLICY.model_copy(update={"has_dic": True, "dic_covers": ["theft"], "deductible_all_perils": None})
    warnings = run(policy).warnings
    assert any("theft" in w for w in warnings)
    assert any("Deductible unknown" in w for w in warnings)


def test_warnings_have_no_duplicates(rent_4000):
    warnings = run().warnings
    assert len(warnings) == len(set(warnings))


def test_assumptions_list_every_config_value_with_its_source(rent_4000):
    config = load_config()
    assumptions = run().assumptions
    for name in type(config).model_fields:
        section = getattr(config, name)
        line = next((a for a in assumptions if a.startswith(f"{name}:")), None)
        assert line is not None, name
        if section.source_url:
            assert section.source_url in line, name
        if section.assumption:
            assert "assumption" in line.lower(), name


def test_assumptions_show_the_values_used(rent_4000):
    assumptions = run().assumptions
    assert any(a.startswith("rebuild_cost_per_sqft: 300 to 500") for a in assumptions)
    assert any(a.startswith("fair_plan_combined_cap: 3000000") for a in assumptions)
    assert any(a.startswith("contents_no_inventory_rule: 0.6 of limit, up to 350000") for a in assumptions)


def test_assumptions_label_code_upgrade_as_an_assumption(rent_4000):
    line = next(a for a in run().assumptions if a.startswith("code_upgrade_recommended_pct_of_dwelling:"))
    assert "assumption" in line.lower()
    assert "not a measured cost" in line


def test_assumptions_keep_the_verify_before_demo_notes(rent_4000):
    assumptions = run().assumptions
    assert any(a.startswith("fair_plan_combined_cap:") and "VERIFY" in a for a in assumptions)
    assert any(a.startswith("acv_warning:") and "VERIFY" in a for a in assumptions)


def test_assumptions_show_the_rent_used(rent_4000):
    assert any("$4,000" in a and "91001" in a and "zillow" in a.lower() for a in run().assumptions)


def test_inputs_are_not_changed(rent_4000):
    policy, home = FAIR_POLICY.model_copy(deep=True), FAIR_HOME.model_copy(deep=True)
    run(policy, home)
    assert policy == FAIR_POLICY and home == FAIR_HOME


def test_missing_rent_does_not_crash(monkeypatch):
    monkeypatch.setattr(scenario, "monthly_rent", lambda zip_code: None)
    result = run()
    assert result.components[4].cost == UNKNOWN
    assert any("living_expenses" in w for w in result.warnings)
    assert any("91001" in a and "no rent data" in a.lower() for a in result.assumptions)


def test_everything_unknown_does_not_crash(monkeypatch):
    monkeypatch.setattr(scenario, "monthly_rent", lambda zip_code: None)
    result = run_coverage_analysis(PolicyInput(), HomeInput(zip="00000"), RiskInput())
    assert result.scope_note
    assert result.total_shortfall == UNKNOWN
    assert result.premium_total is None
    assert [g.gap for g in result.gaps].count("unknown_field") == 4


def test_runs_against_the_real_rent_table():
    result = run_coverage_analysis(FAIR_POLICY, FAIR_HOME, RiskInput())
    assert result.components[4].cost.low is not None


def test_unknown_zip_in_the_real_rent_table_does_not_crash():
    result = run_coverage_analysis(FAIR_POLICY, HomeInput(zip="00000", sq_ft=1_800), RiskInput())
    assert result.components[4].cost == UNKNOWN
