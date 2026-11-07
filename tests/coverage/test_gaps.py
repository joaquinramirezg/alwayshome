"""Step 6: coverage gap rules."""
import pytest

from msba_vibathon_2026.coverage import gaps as gaps_module
from msba_vibathon_2026.coverage.config import load_config
from msba_vibathon_2026.coverage.costs import compute_costs
from msba_vibathon_2026.coverage.gaps import GAP_RULES, find_gaps
from msba_vibathon_2026.coverage.schemas import HomeInput, PolicyInput

AS_OF = 2026
CASE_1_POLICY = dict(document_type="fair_plan", has_dic=False, dwelling_limit=450_000,
                     dwelling_settlement="actual_cash_value", code_upgrade=False, debris_removal=False,
                     contents_limit=0, deductible_all_perils=1_000, last_coverage_update_year=2017)
CASE_1_HOME = dict(sq_ft=1_800, contents_value_estimate=100_000)
CASE_2_POLICY = dict(document_type="homeowners", dwelling_limit=1_100_000, dwelling_settlement="replacement_cost",
                     extended_replacement_pct=0.50, code_upgrade=True, code_upgrade_amount=275_000,
                     debris_removal=True, other_structures_limit=110_000, contents_limit=550_000,
                     loss_of_use_limit=330_000, deductible_all_perils=2_500, last_coverage_update_year=2025)
CASE_2_HOME = dict(sq_ft=2_000, contents_value_estimate=300_000)


def run(policy=None, home=None, rent=None, as_of_year=AS_OF):
    policy_in = PolicyInput(**(policy or {}))
    home_in = HomeInput(zip="91001", **(home or {}))
    return find_gaps(policy_in, home_in, compute_costs(policy_in, home_in, rent), as_of_year=as_of_year)


def names(found) -> list[str]:
    return [g.gap for g in found]


def get(found, name):
    matches = [g for g in found if g.gap == name]
    assert len(matches) == 1, names(found)
    return matches[0]


# ---------------------------------------------------------------- underinsured
def test_underinsured_below_the_low_rebuild_rate():
    gap = get(run({"dwelling_limit": 450_000}, {"sq_ft": 1_800}), "underinsured")
    assert gap.severity == "high"
    assert "$250/sq ft" in gap.evidence
    assert "$300" in gap.evidence and "$500" in gap.evidence


@pytest.mark.parametrize("limit", [540_000, 720_000, 899_999])
def test_possibly_underinsured_from_low_rate_to_below_high_rate(limit):
    found = run({"dwelling_limit": limit}, {"sq_ft": 1_800})
    assert get(found, "possibly_underinsured").severity == "medium"
    assert "underinsured" not in names(found)


def test_no_underinsured_gap_at_the_high_rate():
    found = names(run({"dwelling_limit": 900_000}, {"sq_ft": 1_800}))
    assert "underinsured" not in found and "possibly_underinsured" not in found


@pytest.mark.parametrize("policy, home", [({"dwelling_limit": 450_000}, {}), ({}, {"sq_ft": 1_800}),
                                          ({"dwelling_limit": 450_000}, {"sq_ft": 0})])
def test_underinsured_needs_a_limit_and_a_positive_sqft(policy, home):
    found = names(run(policy, home))
    assert "underinsured" not in found and "possibly_underinsured" not in found


# ------------------------------------------------------------- stale coverage
def test_stale_at_the_threshold():
    gap = get(run({"last_coverage_update_year": 2023}), "stale_coverage")
    assert gap.severity == "medium"
    assert "2023" in gap.evidence and "3 years" in gap.evidence


def test_not_stale_below_the_threshold():
    assert "stale_coverage" not in names(run({"last_coverage_update_year": 2024}))


def test_stale_when_renovated_since_update():
    gap = get(run(home={"renovated_since_update": True}), "stale_coverage")
    assert "renovated" in gap.evidence.lower()


def test_stale_uses_the_given_year():
    assert "stale_coverage" in names(run({"last_coverage_update_year": 2025}, as_of_year=2028))
    assert "stale_coverage" not in names(run({"last_coverage_update_year": 2025}, as_of_year=2027))


def test_stale_defaults_to_the_current_year():
    policy = PolicyInput(last_coverage_update_year=1990)
    home = HomeInput(zip="91001")
    assert "stale_coverage" in names(find_gaps(policy, home, compute_costs(policy, home, None)))


def test_stale_is_silent_when_unknown():
    assert "stale_coverage" not in names(run())


# ----------------------------------------------------------------- fair no dic
def test_fair_plan_without_dic():
    gap = get(run({"document_type": "fair_plan", "has_dic": False}), "fair_no_dic")
    assert gap.severity == "high"
    assert "water damage" in gap.action


@pytest.mark.parametrize("policy", [{"document_type": "fair_plan", "has_dic": True},
                                    {"document_type": "fair_plan"},
                                    {"document_type": "homeowners", "has_dic": False}])
def test_fair_no_dic_is_silent_otherwise(policy):
    assert "fair_no_dic" not in names(run(policy))


# ------------------------------------------------------------------------- ACV
def test_actual_cash_value():
    gap = get(run({"dwelling_settlement": "actual_cash_value"}), "actual_cash_value")
    assert gap.severity == "high"
    assert gap.source_url == load_config().acv_warning.source_url


@pytest.mark.parametrize("value", ["replacement_cost", "unknown", None])
def test_actual_cash_value_is_silent_otherwise(value):
    assert "actual_cash_value" not in names(run({"dwelling_settlement": value}))


# -------------------------------------------------------- extended replacement
@pytest.mark.parametrize("value", [None, 0, 0.1, 0.24])
def test_low_extended_replacement_fires(value):
    gap = get(run({"extended_replacement_pct": value}), "low_extended_replacement")
    assert gap.severity == "medium"
    assert "25%" in gap.evidence


def test_low_extended_replacement_stops_at_the_threshold():
    assert "low_extended_replacement" not in names(run({"extended_replacement_pct": 0.25}))


def test_low_extended_replacement_is_silent_when_guaranteed():
    assert "low_extended_replacement" not in names(run({"guaranteed_replacement": True}))


# ---------------------------------------------------------------- code upgrade
def test_no_code_upgrade_is_high_when_false():
    assert get(run({"code_upgrade": False}), "no_code_upgrade").severity == "high"


def test_low_code_upgrade_amount_is_medium():
    gap = get(run({"code_upgrade": True, "code_upgrade_amount": 50_000, "dwelling_limit": 450_000}), "no_code_upgrade")
    assert gap.severity == "medium"
    assert "$50,000" in gap.evidence and "$112,500" in gap.evidence


def test_code_upgrade_amount_at_the_threshold_is_silent():
    found = run({"code_upgrade": True, "code_upgrade_amount": 112_500, "dwelling_limit": 450_000})
    assert "no_code_upgrade" not in names(found)


@pytest.mark.parametrize("policy", [{}, {"code_upgrade": True}, {"code_upgrade_amount": 50_000}])
def test_no_code_upgrade_is_silent_without_enough_information(policy):
    assert "no_code_upgrade" not in names(run(policy))


# --------------------------------------------------------------- other policy gaps
def test_no_debris_removal_uses_the_config_note():
    gap = get(run({"debris_removal": False}), "no_debris_removal")
    assert gap.severity == "medium"
    assert gap.action == load_config().debris_removal_note.text


@pytest.mark.parametrize("value", [True, None])
def test_no_debris_removal_is_silent_otherwise(value):
    assert "no_debris_removal" not in names(run({"debris_removal": value}))


@pytest.mark.parametrize("limit", [0, None])
def test_no_living_expenses_on_fair_plan(limit):
    gap = get(run({"document_type": "fair_plan", "loss_of_use_limit": limit}, rent=4_000), "no_living_expenses")
    assert gap.severity == "high"
    assert "$96,000" in gap.evidence and "$144,000" in gap.evidence


def test_no_living_expenses_works_without_rent():
    assert "no_living_expenses" in names(run({"document_type": "fair_plan"}))


@pytest.mark.parametrize("policy", [{"document_type": "homeowners", "loss_of_use_limit": 0},
                                    {"document_type": "fair_plan", "loss_of_use_limit": 50_000}])
def test_no_living_expenses_is_silent_otherwise(policy):
    assert "no_living_expenses" not in names(run(policy))


def test_no_contents_when_the_limit_is_zero():
    gap = get(run({"contents_limit": 0}), "no_contents")
    assert gap.severity == "high"
    assert "$0" in gap.evidence


@pytest.mark.parametrize("value", [None, 100_000])
def test_no_contents_is_silent_otherwise(value):
    assert "no_contents" not in names(run({"contents_limit": value}))


# ------------------------------------------------------------------- FAIR cap
def test_above_fair_cap_case_3():
    gap = get(run({"document_type": "fair_plan"}, {"sq_ft": 5_500, "contents_value_estimate": 600_000}),
              "above_fair_cap")
    assert gap.severity == "high"
    assert "$3,350,000" in gap.evidence and "$3,000,000" in gap.evidence


def test_above_fair_cap_stops_at_the_cap():
    found = run({"document_type": "fair_plan"}, {"sq_ft": 5_000, "contents_value_estimate": 500_000})
    assert "above_fair_cap" not in names(found)


def test_above_fair_cap_uses_rebuild_alone_without_contents():
    assert "above_fair_cap" in names(run({"document_type": "fair_plan"}, {"sq_ft": 6_100}))
    assert "above_fair_cap" not in names(run({"document_type": "fair_plan"}, {"sq_ft": 5_500}))


def test_above_fair_cap_is_silent_without_rebuild():
    found = run({"document_type": "fair_plan"}, {"contents_value_estimate": 4_000_000})
    assert "above_fair_cap" not in names(found)


def test_above_fair_cap_is_fair_plan_only():
    found = run({"document_type": "homeowners"}, {"sq_ft": 5_500, "contents_value_estimate": 600_000})
    assert "above_fair_cap" not in names(found)


# --------------------------------------------------------------- renewal risk
def test_renewal_risk():
    assert get(run({"nonrenewal_notice": True}), "renewal_risk").severity == "medium"


@pytest.mark.parametrize("value", [False, None])
def test_renewal_risk_is_silent_otherwise(value):
    assert "renewal_risk" not in names(run({"nonrenewal_notice": value}))


# --------------------------------------------------------------- unknown field
def test_each_unknown_field_gets_its_own_info_gap():
    found = [g for g in run() if g.gap == "unknown_field"]
    assert len(found) == 4
    assert all(g.severity == "info" for g in found)
    for field in ("dwelling_limit", "dwelling_settlement", "code_upgrade", "loss_of_use_limit"):
        assert any(field in g.evidence for g in found), field


def test_unknown_field_is_silent_when_known():
    policy = dict(dwelling_limit=1, dwelling_settlement="replacement_cost", code_upgrade=True, loss_of_use_limit=1)
    assert "unknown_field" not in names(run(policy))


def test_unknown_loss_of_use_is_not_repeated_on_a_fair_plan():
    found = run({"document_type": "fair_plan"})
    assert not any("loss_of_use_limit" in g.evidence for g in found if g.gap == "unknown_field")


# ----------------------------------------------------------------- the five cases
def test_case_1_gaps_are_exactly_the_planned_list():
    found = run(CASE_1_POLICY, CASE_1_HOME, rent=4_000)
    assert sorted(names(found)) == sorted([
        "underinsured", "stale_coverage", "fair_no_dic", "actual_cash_value", "low_extended_replacement",
        "no_code_upgrade", "no_debris_removal", "no_living_expenses", "no_contents",
    ])
    assert "$250/sq ft" in get(found, "underinsured").evidence


def test_case_2_has_no_high_severity_gaps():
    found = run(CASE_2_POLICY, CASE_2_HOME, rent=5_000)
    assert not [g for g in found if g.severity == "high"]


def test_case_3_fires_above_fair_cap():
    assert "above_fair_cap" in names(run(CASE_1_POLICY, {"sq_ft": 5_500, "contents_value_estimate": 600_000}, 4_000))


def test_case_4_gaps():
    policy = dict(CASE_2_POLICY, dwelling_settlement="actual_cash_value", code_upgrade=None,
                  code_upgrade_amount=None, loss_of_use_limit=None)
    found = run(policy, CASE_2_HOME, rent=5_000)
    assert "actual_cash_value" in names(found)
    unknown = [g.evidence for g in found if g.gap == "unknown_field"]
    assert len(unknown) == 2
    assert any("code_upgrade" in e for e in unknown) and any("loss_of_use_limit" in e for e in unknown)


def test_case_5_lists_the_unknown_fields_and_does_not_crash():
    found = run(home={"sq_ft": 1_800})
    assert names(found).count("unknown_field") == 4


# --------------------------------------------------------------------- general
def test_rules_are_a_list_that_can_be_extended(monkeypatch):
    extra = gaps_module.Gap(gap="extra", severity="info", evidence="e", action="a", source_url=None)
    monkeypatch.setattr(gaps_module, "GAP_RULES", [*GAP_RULES, lambda ctx: extra])
    assert "extra" in names(run())


def test_every_gap_explains_itself_and_never_names_an_insurer():
    found = run(CASE_1_POLICY | {"nonrenewal_notice": True}, {"sq_ft": 5_500, "contents_value_estimate": 600_000}, 4_000)
    found += run()
    for gap in found:
        assert gap.evidence and gap.action
        for insurer in ("State Farm", "Allstate", "Farmers", "Mercury", "USAA"):
            assert insurer not in gap.action and insurer not in gap.evidence


def test_numbers_come_from_config(monkeypatch):
    config = load_config()
    changed = config.model_copy(update={
        "rebuild_cost_per_sqft": config.rebuild_cost_per_sqft.model_copy(update={"low": 200, "high": 240}),
    })
    monkeypatch.setattr(gaps_module, "load_config", lambda: changed)
    found = names(run({"dwelling_limit": 450_000}, {"sq_ft": 1_800}))
    assert "underinsured" not in found and "possibly_underinsured" not in found


# --------------------------------------------------------- Rule 9: final review
def test_acv_evidence_includes_the_dwelling_limit():
    gap = get(run({"dwelling_settlement": "actual_cash_value", "dwelling_limit": 450_000}), "actual_cash_value")
    assert "$450,000" in gap.evidence


def test_no_code_upgrade_evidence_includes_the_estimated_cost():
    gap = get(run({"code_upgrade": False, "dwelling_limit": 450_000}), "no_code_upgrade")
    assert "$112,500" in gap.evidence and "$225,000" in gap.evidence


def test_no_contents_evidence_includes_the_estimated_contents():
    gap = get(run({"contents_limit": 0}, {"contents_value_estimate": 100_000}), "no_contents")
    assert "$0" in gap.evidence and "$100,000" in gap.evidence
