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
    assert rebuild.payout == Range(low=405_000, high=450_000)
    assert rebuild.shortfall == Range(low=90_000, high=495_000)


def test_component_notes_combine_cost_and_payout_notes(rent_4000):
    other = run().components[2]
    assert any("Assumed" in n for n in other.notes)
    assert any("Coverage A" in n for n in other.notes)


def test_totals_are_filled(rent_4000):
    result = run()
    assert result.deductible == 1_000
    assert result.total_cost == Range(low=902_500, high=1_459_000)
    assert result.total_payout == Range(low=450_000, high=495_000)
    assert result.total_shortfall == Range(low=408_500, high=1_010_000)


def test_works_without_a_probability(rent_4000):
    result = run()
    assert result.p_destroyed is None
    assert result.expected_shortfall is None


def test_uses_the_probability_when_known(rent_4000):
    result = run(p_destroyed=0.5)
    assert result.p_destroyed == 0.5
    assert result.expected_shortfall == Range(low=204_250, high=505_000)


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


# ------------------------------------------------- Step 8: hand-calculated cases
CASE_1_POLICY = dict(document_type="fair_plan", has_dic=False, dwelling_limit=450_000,
                     dwelling_settlement="actual_cash_value", code_upgrade=False, debris_removal=False,
                     contents_limit=0, deductible_all_perils=1_000, last_coverage_update_year=2017)
CASE_1_HOME = dict(zip="91001", sq_ft=1_800, contents_value_estimate=100_000)
CASE_2_POLICY = dict(document_type="homeowners", dwelling_limit=1_100_000, dwelling_settlement="replacement_cost",
                     extended_replacement_pct=0.50, code_upgrade=True, code_upgrade_amount=275_000,
                     debris_removal=True, other_structures_limit=110_000, contents_limit=550_000,
                     loss_of_use_limit=330_000, deductible_all_perils=2_500, last_coverage_update_year=2025)
CASE_2_HOME = dict(zip="90272", sq_ft=2_000, contents_value_estimate=300_000)


def run_case(monkeypatch, policy: dict, home: dict, rent: float):
    monkeypatch.setattr(scenario, "monthly_rent", lambda zip_code: rent)
    return run_coverage_analysis(PolicyInput(**policy), HomeInput(**home), RiskInput(), as_of_year=AS_OF)


def table(result) -> dict:
    """component: (cost low, cost high, payout low, payout high, shortfall low, shortfall high)"""
    return {c.name: (c.cost.low, c.cost.high, c.payout.low, c.payout.high, c.shortfall.low, c.shortfall.high)
            for c in result.components}


def test_case_1_fair_plan_only_underinsured(monkeypatch):
    result = run_case(monkeypatch, CASE_1_POLICY, CASE_1_HOME, 4_000)
    assert table(result) == {
        "rebuild": (540_000, 900_000, 405_000, 450_000, 90_000, 495_000),
        "code_upgrade": (112_500, 225_000, 0, 0, 112_500, 225_000),
        "other_structures": (54_000, 90_000, 45_000, 45_000, 9_000, 45_000),
        "contents": (100_000, 100_000, 0, 0, 100_000, 100_000),
        "living_expenses": (96_000, 144_000, 0, 0, 96_000, 144_000),
    }
    assert result.total_shortfall == Range(low=408_500, high=1_010_000)
    assert sorted(g.gap for g in result.gaps) == sorted([
        "underinsured", "stale_coverage", "fair_no_dic", "actual_cash_value", "low_extended_replacement",
        "no_code_upgrade", "no_debris_removal", "no_living_expenses", "no_contents",
    ])
    assert "$250/sq ft" in next(g for g in result.gaps if g.gap == "underinsured").evidence
    config = load_config()
    assert config.acv_warning.text in result.warnings
    assert config.debris_removal_note.text in result.warnings


def test_case_2_private_policy_well_covered(monkeypatch):
    result = run_case(monkeypatch, CASE_2_POLICY, CASE_2_HOME, 5_000)
    assert table(result) == {
        "rebuild": (600_000, 1_000_000, 600_000, 1_000_000, 0, 0),
        "code_upgrade": (275_000, 550_000, 275_000, 275_000, 0, 275_000),
        "other_structures": (60_000, 100_000, 110_000, 110_000, 0, 0),
        "contents": (300_000, 300_000, 550_000, 550_000, 0, 0),
        "living_expenses": (120_000, 180_000, 330_000, 330_000, 0, 0),
    }
    assert result.total_shortfall == Range(low=2_500, high=277_500)
    assert not [g for g in result.gaps if g.severity == "high"]


def test_case_3_high_value_home_on_the_fair_plan(monkeypatch):
    result = run_case(monkeypatch, CASE_1_POLICY, dict(CASE_1_HOME, sq_ft=5_500, contents_value_estimate=600_000), 4_000)
    assert table(result) == {
        "rebuild": (1_650_000, 2_750_000, 405_000, 450_000, 1_200_000, 2_345_000),
        "code_upgrade": (112_500, 225_000, 0, 0, 112_500, 225_000),
        "other_structures": (165_000, 275_000, 45_000, 45_000, 120_000, 230_000),
        "contents": (600_000, 600_000, 0, 0, 600_000, 600_000),
        "living_expenses": (96_000, 144_000, 0, 0, 96_000, 144_000),
    }
    assert result.total_shortfall == Range(low=2_129_500, high=3_545_000)
    assert "above_fair_cap" in [g.gap for g in result.gaps]


def test_case_4_acv_with_unknown_add_ons(monkeypatch):
    policy = dict(CASE_2_POLICY, dwelling_settlement="actual_cash_value", code_upgrade=None,
                  code_upgrade_amount=None, loss_of_use_limit=None)
    result = run_case(monkeypatch, policy, CASE_2_HOME, 5_000)
    assert load_config().acv_warning.text in result.warnings
    unknown = [g for g in result.gaps if g.gap == "unknown_field"]
    assert len(unknown) == 2
    assert all(g.severity == "info" for g in unknown)
    assert any("code_upgrade" in g.evidence for g in unknown)
    assert any("loss_of_use_limit" in g.evidence for g in unknown)
    components = {c.name: c for c in result.components}
    assert components["code_upgrade"].shortfall == Range(low=0, high=550_000)
    assert components["living_expenses"].shortfall == Range(low=0, high=180_000)
    assert result.total_shortfall == Range(low=2_500, high=732_500)


def test_case_5_everything_unknown_except_zip_and_sqft(monkeypatch):
    result = run_case(monkeypatch, {}, dict(zip="91001", sq_ft=1_800), 4_000)
    assert result.scope_note == "Total-loss scenario only. Partial damage not modeled."
    assert table(result) == {
        "rebuild": (540_000, 900_000, 0, 900_000, 0, 900_000),
        "code_upgrade": (None, None, None, None, None, None),
        "other_structures": (54_000, 90_000, 0, 90_000, 0, 90_000),
        "contents": (None, None, None, None, None, None),
        "living_expenses": (96_000, 144_000, 0, 144_000, 0, 144_000),
    }
    assert result.total_shortfall == Range(low=0, high=1_134_000)
    assert result.deductible is None
    assert [g.gap for g in result.gaps].count("unknown_field") == 4
    assert any("code_upgrade, contents" in w for w in result.warnings)
    assert CoverageResult.model_validate_json(result.model_dump_json()) == result


# --------------------------------------------------------- Rule 9: final review
def test_returned_ranges_are_independent_of_later_calls(monkeypatch):
    monkeypatch.setattr(scenario, "monthly_rent", lambda zip_code: None)
    first = run_coverage_analysis(PolicyInput(), HomeInput(zip="00000"), RiskInput())
    first.total_cost.low = 123.0
    first.components[0].cost.low = 456.0
    second = run_coverage_analysis(PolicyInput(), HomeInput(zip="00000"), RiskInput())
    assert second.total_cost == UNKNOWN
    assert second.components[0].cost == UNKNOWN


def random_inputs(rng):
    money = [None, 0, 1, 50_000, 450_000, 1_100_000, 5_000_000]
    policy = PolicyInput(
        document_type=rng.choice([None, "fair_plan", "dic", "homeowners", "dwelling_fire", "other"]),
        has_dic=rng.choice([None, True, False]), dic_covers=rng.choice([[], ["theft"]]),
        premium_total=rng.choice(money), dwelling_limit=rng.choice(money),
        other_structures_limit=rng.choice(money), contents_limit=rng.choice(money),
        loss_of_use_limit=rng.choice(money),
        dwelling_settlement=rng.choice([None, "actual_cash_value", "replacement_cost", "unknown"]),
        extended_replacement_pct=rng.choice([None, 0, 0.25, 1]), guaranteed_replacement=rng.choice([None, True, False]),
        contents_settlement=rng.choice([None, "actual_cash_value", "replacement_cost", "unknown"]),
        code_upgrade=rng.choice([None, True, False]), code_upgrade_amount=rng.choice(money),
        debris_removal=rng.choice([None, True, False]), deductible_all_perils=rng.choice(money),
        deductible_wildfire=rng.choice(money), last_coverage_update_year=rng.choice([None, 2000, 2026, 2030]),
        nonrenewal_notice=rng.choice([None, True, False]),
    )
    home = HomeInput(
        zip="91001", sq_ft=rng.choice([None, 0, 1, 1_800, 20_000]), stories=rng.choice([None, 1]),
        year_built=rng.choice([None, 1958]), contents_value_estimate=rng.choice(money),
        other_structures_estimate=rng.choice(money), renovated_since_update=rng.choice([None, True, False]),
    )
    return policy, home, rng.choice([None, 0.0, 0.5, 1.0]), rng.choice([None, 0.0, 1_500.0, 12_849.0])


def test_any_mix_of_inputs_gives_a_consistent_result(monkeypatch):
    import random

    rng = random.Random(2026)
    for _ in range(3_000):
        policy, home, p_destroyed, rent = random_inputs(rng)
        monkeypatch.setattr(scenario, "monthly_rent", lambda zip_code, rent=rent: rent)
        result = run_coverage_analysis(policy, home, RiskInput(p_destroyed=p_destroyed), as_of_year=AS_OF)
        assert CoverageResult.model_validate_json(result.model_dump_json()) == result
        assert result.scope_note and result.assumptions
        ranges = [r for c in result.components for r in (c.cost, c.payout, c.shortfall)]
        ranges += [result.total_cost, result.total_payout, result.total_shortfall]
        for r in ranges:
            assert (r.low is None) == (r.high is None)
            if r.low is not None:
                assert 0 <= r.low <= r.high
        for c in result.components:
            if c.cost.low is None:
                assert c.shortfall == UNKNOWN
            else:
                assert c.shortfall.high <= c.cost.high
        if result.total_cost.low is not None:
            assert result.total_payout.high <= result.total_cost.high
