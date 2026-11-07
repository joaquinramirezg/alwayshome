"""Step 5: what the policy pays, shortfalls, totals and expected shortfall."""
from msba_vibathon_2026.coverage import payout as payout_module
from msba_vibathon_2026.coverage.config import load_config
from msba_vibathon_2026.coverage.costs import compute_costs
from msba_vibathon_2026.coverage.payout import compute_payouts, compute_totals
from msba_vibathon_2026.coverage.schemas import HomeInput, PolicyInput, Range

UNKNOWN = Range(low=None, high=None)
CASE_1_POLICY = dict(document_type="fair_plan", has_dic=False, dwelling_limit=450_000,
                     dwelling_settlement="actual_cash_value", code_upgrade=False, debris_removal=False,
                     contents_limit=0, deductible_all_perils=1_000, last_coverage_update_year=2017)
CASE_1_HOME = dict(sq_ft=1_800, contents_value_estimate=100_000)
CASE_2_POLICY = dict(document_type="homeowners", dwelling_limit=1_100_000, dwelling_settlement="replacement_cost",
                     extended_replacement_pct=0.50, code_upgrade=True, code_upgrade_amount=275_000,
                     debris_removal=True, other_structures_limit=110_000, contents_limit=550_000,
                     loss_of_use_limit=330_000, deductible_all_perils=2_500, last_coverage_update_year=2025)
CASE_2_HOME = dict(sq_ft=2_000, contents_value_estimate=300_000)


def run(policy: dict, home: dict, rent=None, p_destroyed=None):
    policy_in = PolicyInput(**policy)
    costs = compute_costs(policy_in, HomeInput(zip="91001", **home), rent)
    payouts = compute_payouts(policy_in, costs)
    return costs, payouts, compute_totals(policy_in, costs, payouts, p_destroyed)


def payouts_for(rent=None, home=None, **policy):
    return run(policy, home if home is not None else {"sq_ft": 1_800}, rent)[1]


def item(name: str, rent=None, home=None, **policy):
    return payouts_for(rent, home, **policy).items[name]


def has_note(found, text: str) -> bool:
    return any(text.lower() in note.lower() for note in found.notes)


# --------------------------------------------------------------------- rebuild
def test_guaranteed_replacement_pays_the_full_cost():
    found = item("rebuild", dwelling_limit=100_000, guaranteed_replacement=True)
    assert found.payout == Range(low=540_000, high=900_000)
    assert found.shortfall == Range(low=0, high=0)


def test_rebuild_pays_up_to_the_dwelling_limit():
    found = item("rebuild", dwelling_limit=450_000, dwelling_settlement="replacement_cost")
    assert found.payout == Range(low=450_000, high=450_000)
    assert found.shortfall == Range(low=90_000, high=450_000)


def test_rebuild_adds_extended_replacement_to_the_limit():
    found = item("rebuild", dwelling_limit=400_000, extended_replacement_pct=0.5,
                 dwelling_settlement="replacement_cost")
    assert found.payout == Range(low=540_000, high=600_000)
    assert found.shortfall == Range(low=0, high=300_000)


def test_rebuild_shortfall_when_the_limit_falls_inside_the_cost_range():
    found = item("rebuild", dwelling_limit=700_000, dwelling_settlement="replacement_cost")
    assert found.payout == Range(low=540_000, high=700_000)
    assert found.shortfall == Range(low=0, high=200_000)


def test_acv_is_computed_the_same_and_warned():
    result = payouts_for(dwelling_limit=450_000, dwelling_settlement="actual_cash_value")
    assert result.items["rebuild"].shortfall == Range(low=90_000, high=450_000)
    assert load_config().acv_warning.text in result.warnings
    assert has_note(result.items["rebuild"], "replacement cost")


def test_replacement_cost_has_no_acv_warning():
    result = payouts_for(dwelling_limit=450_000, dwelling_settlement="replacement_cost")
    assert load_config().acv_warning.text not in result.warnings


def test_unknown_settlement_is_treated_as_replacement_cost_with_a_flag():
    for settlement in ("unknown", None):
        found = item("rebuild", dwelling_limit=450_000, dwelling_settlement=settlement)
        assert found.shortfall == Range(low=90_000, high=450_000)
        assert has_note(found, "settlement")


def test_unknown_dwelling_limit_widens_the_rebuild_range():
    found = item("rebuild")
    assert found.payout == Range(low=0, high=900_000)
    assert found.shortfall == Range(low=0, high=900_000)
    assert has_note(found, "dwelling limit")


def test_unknown_rebuild_cost_has_no_shortfall():
    found = item("rebuild", home={}, dwelling_limit=450_000)
    assert found.shortfall == UNKNOWN


# ------------------------------------------- FAIR Plan with no Coverage B: range
def test_fair_plan_without_coverage_b_widens_the_rebuild_range():
    for limit in (None, 0):
        found = item("rebuild", document_type="fair_plan", dwelling_limit=450_000, other_structures_limit=limit)
        assert found.payout == Range(low=405_000, high=450_000)
        assert found.shortfall == Range(low=90_000, high=495_000)
        assert has_note(found, "coverage a")


def test_fair_plan_widening_when_the_limit_falls_inside_the_cost_range():
    found = item("rebuild", document_type="fair_plan", dwelling_limit=700_000)
    assert found.payout == Range(low=540_000, high=700_000)
    assert found.shortfall == Range(low=0, high=270_000)


def test_fair_plan_widening_only_takes_what_other_structures_needs():
    found = item("rebuild", home={"sq_ft": 1_800, "other_structures_estimate": 10_000},
                 document_type="fair_plan", dwelling_limit=450_000)
    assert found.payout == Range(low=440_000, high=450_000)
    assert found.shortfall == Range(low=90_000, high=460_000)


def test_fair_plan_widening_applies_to_the_extended_limit():
    found = item("rebuild", document_type="fair_plan", dwelling_limit=400_000, extended_replacement_pct=0.25)
    assert found.payout == Range(low=460_000, high=500_000)
    assert found.shortfall == Range(low=40_000, high=440_000)


def test_fair_plan_with_coverage_b_does_not_widen():
    found = item("rebuild", document_type="fair_plan", dwelling_limit=450_000, other_structures_limit=20_000)
    assert found.payout == Range(low=450_000, high=450_000)
    assert found.shortfall == Range(low=90_000, high=450_000)
    assert not has_note(found, "coverage a")


def test_other_policies_do_not_widen():
    found = item("rebuild", document_type="homeowners", dwelling_limit=450_000, other_structures_limit=0)
    assert found.shortfall == Range(low=90_000, high=450_000)


def test_guaranteed_replacement_does_not_widen():
    found = item("rebuild", document_type="fair_plan", dwelling_limit=450_000, guaranteed_replacement=True)
    assert found.shortfall == Range(low=0, high=0)


def test_other_structures_payout_stays_the_same_in_both_cases():
    found = item("other_structures", document_type="fair_plan", dwelling_limit=450_000)
    assert found.payout == Range(low=45_000, high=45_000)
    assert found.shortfall == Range(low=9_000, high=45_000)


# ---------------------------------------------------------------- code upgrade
def test_code_upgrade_pays_the_amount_given():
    found = item("code_upgrade", dwelling_limit=1_100_000, code_upgrade=True, code_upgrade_amount=275_000)
    assert found.payout == Range(low=275_000, high=275_000)
    assert found.shortfall == Range(low=0, high=275_000)


def test_code_upgrade_false_pays_nothing():
    found = item("code_upgrade", dwelling_limit=450_000, code_upgrade=False)
    assert found.payout == Range(low=0, high=0)
    assert found.shortfall == Range(low=112_500, high=225_000)


def test_code_upgrade_true_without_amount_or_unknown_widens():
    for value in (True, None):
        found = item("code_upgrade", dwelling_limit=450_000, code_upgrade=value)
        assert found.payout == Range(low=0, high=225_000)
        assert found.shortfall == Range(low=0, high=225_000)
        assert has_note(found, "code upgrade")


def test_code_upgrade_has_no_shortfall_without_a_cost():
    assert item("code_upgrade", code_upgrade=False).shortfall == UNKNOWN


# ------------------------------------------------------------ other structures
def test_other_structures_pays_its_limit():
    found = item("other_structures", other_structures_limit=110_000, document_type="homeowners")
    assert found.payout == Range(low=110_000, high=110_000)
    assert found.shortfall == Range(low=0, high=0)


def test_fair_plan_without_coverage_b_uses_a_share_of_the_dwelling_limit():
    for limit in (None, 0):
        found = item("other_structures", document_type="fair_plan", dwelling_limit=450_000,
                     other_structures_limit=limit)
        assert found.payout == Range(low=45_000, high=45_000)
        assert found.shortfall == Range(low=9_000, high=45_000)
        assert has_note(found, "coverage a")


def test_fair_plan_with_coverage_b_uses_that_limit():
    found = item("other_structures", document_type="fair_plan", dwelling_limit=450_000,
                 other_structures_limit=20_000)
    assert found.payout == Range(low=20_000, high=20_000)


def test_fair_plan_without_coverage_a_or_b_widens():
    found = item("other_structures", document_type="fair_plan")
    assert found.shortfall == Range(low=0, high=90_000)


def test_other_policy_with_zero_limit_pays_nothing():
    found = item("other_structures", document_type="homeowners", other_structures_limit=0)
    assert found.payout == Range(low=0, high=0)
    assert found.shortfall == Range(low=54_000, high=90_000)


def test_other_policy_with_unknown_limit_widens():
    found = item("other_structures", document_type="homeowners")
    assert found.payout == Range(low=0, high=90_000)
    assert found.shortfall == Range(low=0, high=90_000)


# -------------------------------------------------------------------- contents
def test_contents_pays_its_limit_with_the_sb_495_note():
    found = item("contents", home={"contents_value_estimate": 300_000}, contents_limit=200_000)
    assert found.payout == Range(low=200_000, high=200_000)
    assert found.shortfall == Range(low=100_000, high=100_000)
    assert has_note(found, "SB 495")


def test_contents_zero_limit_pays_nothing_without_the_sb_495_note():
    found = item("contents", home={"contents_value_estimate": 100_000}, contents_limit=0)
    assert found.payout == Range(low=0, high=0)
    assert found.shortfall == Range(low=100_000, high=100_000)
    assert not has_note(found, "SB 495")


def test_contents_unknown_limit_widens():
    found = item("contents", home={"contents_value_estimate": 100_000})
    assert found.payout == Range(low=0, high=100_000)
    assert found.shortfall == Range(low=0, high=100_000)


def test_contents_acv_adds_a_warning():
    result = payouts_for(home={"contents_value_estimate": 1}, contents_limit=1, contents_settlement="actual_cash_value")
    assert any("contents" in w.lower() and "actual cash value" in w.lower() for w in result.warnings)


# ------------------------------------------------------------- living expenses
def test_living_expenses_pay_the_limit():
    found = item("living_expenses", rent=4_000, loss_of_use_limit=100_000, document_type="homeowners")
    assert found.payout == Range(low=100_000, high=100_000)
    assert found.shortfall == Range(low=0, high=44_000)


def test_living_expenses_unknown_on_fair_plan_pay_nothing_with_a_note():
    found = item("living_expenses", rent=4_000, document_type="fair_plan")
    assert found.payout == Range(low=0, high=0)
    assert found.shortfall == Range(low=96_000, high=144_000)
    assert has_note(found, "FAIR Plan")


def test_living_expenses_unknown_elsewhere_widen():
    found = item("living_expenses", rent=4_000, document_type="homeowners")
    assert found.payout == Range(low=0, high=144_000)
    assert found.shortfall == Range(low=0, high=144_000)


def test_living_expenses_without_rent_have_no_shortfall():
    assert item("living_expenses", loss_of_use_limit=100_000).shortfall == UNKNOWN


# ------------------------------------------------------------------------- DIC
def test_dic_adds_a_note_but_no_dollars():
    without = run(dict(CASE_1_POLICY), CASE_1_HOME, 4_000)
    with_dic = run(dict(CASE_1_POLICY, has_dic=True, dic_covers=["theft", "water damage"]), CASE_1_HOME, 4_000)
    assert with_dic[2].total_shortfall == without[2].total_shortfall
    assert with_dic[2].total_payout == without[2].total_payout
    assert any("theft, water damage" in w for w in with_dic[1].warnings)
    assert not any("DIC" in w for w in without[1].warnings)


# ---------------------------------------------------------------------- totals
def test_case_1_payout_and_shortfall_columns_and_total():
    _, payouts, totals = run(CASE_1_POLICY, CASE_1_HOME, 4_000)
    assert {n: (i.payout.low, i.payout.high, i.shortfall.low, i.shortfall.high)
            for n, i in payouts.items.items()} == {
        "rebuild": (405_000, 450_000, 90_000, 495_000),
        "code_upgrade": (0, 0, 112_500, 225_000),
        "other_structures": (45_000, 45_000, 9_000, 45_000),
        "contents": (0, 0, 100_000, 100_000),
        "living_expenses": (0, 0, 96_000, 144_000),
    }
    assert totals.total_shortfall == Range(low=408_500, high=1_010_000)
    assert totals.deductible == 1_000


def test_case_2_payout_and_shortfall_columns_and_total():
    _, payouts, totals = run(CASE_2_POLICY, CASE_2_HOME, 5_000)
    assert {n: (i.shortfall.low, i.shortfall.high) for n, i in payouts.items.items()} == {
        "rebuild": (0, 0),
        "code_upgrade": (0, 275_000),
        "other_structures": (0, 0),
        "contents": (0, 0),
        "living_expenses": (0, 0),
    }
    assert payouts.items["rebuild"].payout == Range(low=600_000, high=1_000_000)
    assert payouts.items["contents"].payout == Range(low=550_000, high=550_000)
    assert totals.total_shortfall == Range(low=2_500, high=277_500)


def test_case_3_total():
    _, _, totals = run(CASE_1_POLICY, dict(sq_ft=5_500, contents_value_estimate=600_000), 4_000)
    assert totals.total_shortfall == Range(low=2_129_500, high=3_545_000)


def test_case_4_total():
    policy = dict(CASE_2_POLICY, dwelling_settlement="actual_cash_value", code_upgrade=None,
                  code_upgrade_amount=None, loss_of_use_limit=None)
    _, _, totals = run(policy, CASE_2_HOME, 5_000)
    assert totals.total_shortfall == Range(low=2_500, high=732_500)


def test_total_cost_sums_the_components():
    assert run(CASE_1_POLICY, CASE_1_HOME, 4_000)[2].total_cost == Range(low=902_500, high=1_459_000)


def test_total_payout_caps_each_component_at_its_cost():
    assert run(CASE_1_POLICY, CASE_1_HOME, 4_000)[2].total_payout == Range(low=450_000, high=495_000)
    assert run(CASE_2_POLICY, CASE_2_HOME, 5_000)[2].total_payout == Range(low=1_355_000, high=1_855_000)


def test_wildfire_deductible_wins():
    policy = dict(CASE_2_POLICY, deductible_wildfire=10_000)
    totals = run(policy, CASE_2_HOME, 5_000)[2]
    assert totals.deductible == 10_000
    assert totals.total_shortfall == Range(low=10_000, high=285_000)


def test_unknown_deductible_counts_as_zero_with_a_flag():
    policy = dict(CASE_2_POLICY, deductible_all_perils=None)
    totals = run(policy, CASE_2_HOME, 5_000)[2]
    assert totals.deductible is None
    assert totals.total_shortfall == Range(low=0, high=275_000)
    assert any("deductible" in w.lower() for w in totals.warnings)


def test_totals_leave_out_unknown_components_and_name_them():
    totals = run({"dwelling_limit": 450_000, "contents_limit": 0}, {"sq_ft": 1_800})[2]
    assert any("living_expenses" in w for w in totals.warnings)
    assert totals.total_cost == Range(low=540_000 + 112_500 + 54_000, high=900_000 + 225_000 + 90_000)


def test_expected_shortfall_scales_the_total():
    totals = run(CASE_1_POLICY, CASE_1_HOME, 4_000, p_destroyed=0.5)[2]
    assert totals.expected_shortfall == Range(low=204_250, high=505_000)


def test_expected_shortfall_is_none_without_a_probability():
    assert run(CASE_1_POLICY, CASE_1_HOME, 4_000)[2].expected_shortfall is None


# -------------------------------------------------------------------- unknowns
def test_only_sqft_known_does_not_crash():
    _, payouts, totals = run({}, {"sq_ft": 1_800})
    assert payouts.items["rebuild"].shortfall == Range(low=0, high=900_000)
    assert payouts.items["contents"].shortfall == UNKNOWN
    assert totals.total_shortfall == Range(low=0, high=990_000)


def test_everything_unknown_does_not_crash():
    _, payouts, totals = run({}, {}, p_destroyed=0.5)
    assert all(i.shortfall == UNKNOWN for i in payouts.items.values())
    assert totals.total_cost == UNKNOWN
    assert totals.total_payout == UNKNOWN
    assert totals.total_shortfall == UNKNOWN
    assert totals.expected_shortfall is None


def test_numbers_come_from_config(monkeypatch):
    config = load_config()
    changed = config.model_copy(update={
        "fair_plan_other_structures_pct_of_dwelling":
            config.fair_plan_other_structures_pct_of_dwelling.model_copy(update={"value": 0.2}),
    })
    monkeypatch.setattr(payout_module, "load_config", lambda: changed)
    found = item("other_structures", document_type="fair_plan", dwelling_limit=450_000)
    assert found.payout == Range(low=90_000, high=90_000)
