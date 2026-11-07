"""The coverage module connected to assess(), the contract, the report and the real Streamlit app."""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from msba_vibathon_2026 import policy_extract
from msba_vibathon_2026.assess_stub import assess
from msba_vibathon_2026.contract import validate_output
from msba_vibathon_2026.coverage import adapter, scenario
from msba_vibathon_2026.coverage.adapter import to_home_input, to_policy_input
from msba_vibathon_2026.report import template_report
from msba_vibathon_2026.scenarios import cached_area, load_scenarios, scenario_inputs

APP = str(Path(__file__).resolve().parents[2] / "app.py")
SCENARIOS = load_scenarios()


def run_scenario(sid: str) -> dict:
    s = SCENARIOS[sid]
    return assess(scenario_inputs(s), cached_area(s["address"]))


# -------------------------------------------------------------- policy conversion
def test_extended_replacement_percent_becomes_a_fraction():
    assert to_policy_input({"extended_replacement_pct": 25}).extended_replacement_pct == 0.25
    assert to_policy_input({"extended_replacement_pct": 0}).extended_replacement_pct == 0
    assert to_policy_input({}).extended_replacement_pct is None


@pytest.mark.parametrize("documents, expected", [
    (["fair_plan"], "fair_plan"),
    (["fair_plan", "dic"], "fair_plan"),
    (["dic", "fair_plan"], "fair_plan"),
    (["homeowners"], "homeowners"),
    ([], None),
])
def test_documents_become_one_document_type(documents, expected):
    assert to_policy_input({"documents": documents}).document_type == expected


def test_a_single_document_type_also_works():
    assert to_policy_input({"document_type": "fair_plan"}).document_type == "fair_plan"


def test_extractor_addons_become_booleans():
    policy = to_policy_input({"code_upgrade": {"covered": True, "limit": None, "pct": None},
                              "debris_removal": {"covered": False, "limit": None, "pct": None}})
    assert policy.code_upgrade is True
    assert policy.debris_removal is False


def test_code_upgrade_percent_becomes_dollars():
    policy = to_policy_input({"dwelling_limit": 500_000, "code_upgrade": {"covered": True, "limit": None, "pct": 10}})
    assert policy.code_upgrade_amount == 50_000


def test_code_upgrade_amount_from_the_form_wins():
    policy = to_policy_input({"dwelling_limit": 500_000, "code_upgrade": True, "code_upgrade_amount": 20_000})
    assert policy.code_upgrade_amount == 20_000


@pytest.mark.parametrize("value, expected", [
    ({"amount": 5_000, "pct": None}, 5_000),
    ({"amount": None, "pct": 2}, 10_000),
    (7_500, 7_500),
    (None, None),
])
def test_wildfire_deductible_becomes_dollars(value, expected):
    assert to_policy_input({"dwelling_limit": 500_000, "deductible_wildfire": value}).deductible_wildfire == expected


def test_form_deductible_is_the_all_perils_deductible():
    assert to_policy_input({"deductible": 1_000}).deductible_all_perils == 1_000


def test_merged_policy_from_the_extractor_converts():
    fields = {name: {"value": None} for name in policy_extract.FIELDS}
    fair = {**fields, "document_type": {"value": "fair_plan"}, "dwelling_limit": {"value": 650_000},
            "extended_replacement_pct": {"value": 25}, "dwelling_settlement": {"value": "actual_cash_value"}}
    dic = {**fields, "document_type": {"value": "dic"}, "dic_covers": {"value": ["theft"]},
           "loss_of_use_limit": {"value": 130_000}}
    merged = policy_extract.merge_policies([{"fields": fair}, {"fields": dic}])
    policy = to_policy_input(merged)
    assert policy.document_type == "fair_plan"
    assert policy.has_dic is True and policy.dic_covers == ["theft"]
    assert policy.dwelling_limit == 650_000
    assert policy.extended_replacement_pct == 0.25
    assert policy.loss_of_use_limit == 130_000


def test_home_uses_the_contract_field_names_and_the_area_zip():
    home = to_home_input({"living_area_sqft": 1_800, "stories": 1, "year_built": 1958, "contents_value_estimate": 5},
                         {"geocode": {"zip": "91001"}})
    assert (home.zip, home.sq_ft, home.stories, home.year_built, home.contents_value_estimate) == (
        "91001", 1_800, 1, 1958, 5)


def test_home_without_a_geocode_has_an_empty_zip():
    assert to_home_input({}, {"hazard_class": "High"}).zip == ""


# ------------------------------------------------------------------ assess() output
@pytest.mark.parametrize("sid", list(SCENARIOS))
def test_every_sample_gets_a_coverage_block_that_passes_the_contract(sid):
    out = run_scenario(sid)
    coverage = out["current"]["coverage"]
    assert coverage["scope_note"]
    assert len(coverage["components"]) == 5
    assert validate_output(out) == []


def test_fair_plan_sample_matches_a_hand_calculation(monkeypatch):
    # 1,800 sq ft, $650,000 ACV, no code upgrade or Coverage B, contents $0 limit and $100,000 value, $4,000 rent.
    monkeypatch.setattr(scenario, "monthly_rent", lambda zip_code: 4_000.0)
    coverage = run_scenario("altadena_fair_only")["current"]["coverage"]
    assert {c["name"]: (c["shortfall"]["low"], c["shortfall"]["high"]) for c in coverage["components"]} == {
        "rebuild": (0, 315_000),
        "code_upgrade": (162_500, 325_000),
        "other_structures": (0, 25_000),
        "contents": (100_000, 100_000),
        "living_expenses": (96_000, 144_000),
    }
    assert coverage["total_shortfall"] == {"low": 358_500, "high": 909_000}


def test_real_rent_for_the_zip_is_used():
    coverage = run_scenario("altadena_fair_only")["current"]["coverage"]
    assert coverage["total_shortfall"] == {"low": 354_490, "high": 902_985}
    assert any("91001" in a and "$3,833" in a for a in coverage["assumptions"])


def test_no_probability_is_passed_while_the_house_model_is_a_placeholder():
    coverage = run_scenario("altadena_fair_only")["current"]["coverage"]
    assert coverage["p_destroyed"] is None
    assert coverage["expected_shortfall"] is None


# --------------------------------------------------------------------- gap list
def test_gap_list_comes_from_the_module_with_its_numbers():
    gaps = {g["gap"]: g for g in run_scenario("altadena_fair_only")["current"]["insurance_gap"]}
    assert "Coverage may not pay for a full rebuild" in gaps
    assert "$361/sq ft" in gaps["Coverage may not pay for a full rebuild"]["why"]
    assert "No contents coverage" in gaps


def test_gap_list_keeps_the_liability_rule():
    names = [g["gap"] for g in run_scenario("altadena_fair_only")["current"]["insurance_gap"]]
    assert "No personal liability coverage" in names
    names = [g["gap"] for g in run_scenario("altadena_fair_dic")["current"]["insurance_gap"]]
    assert "No personal liability coverage" not in names


def test_gap_list_uses_contract_severities_in_order():
    inputs = scenario_inputs(SCENARIOS["altadena_fair_only"])
    inputs["insurance"]["dwelling_settlement"] = None
    inputs["insurance"]["code_upgrade"] = None
    out = assess(inputs, cached_area(inputs["address"]))
    order = [g["severity"] for g in out["current"]["insurance_gap"]]
    assert set(order) <= {"high", "medium", "low"}
    assert "low" in order
    assert order == sorted(order, key=["high", "medium", "low"].index)
    assert validate_output(out) == []


def test_only_one_rebuild_range_is_shown_to_the_homeowner():
    out = run_scenario("altadena_fair_only")
    text = " ".join(g["why"] for g in out["current"]["insurance_gap"])
    assert "$450" not in text
    assert "$300" in text and "$500" in text


# --------------------------------------------------------------------- fallback
def test_plan_still_finishes_if_the_module_fails(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("module failed")

    monkeypatch.setattr(adapter, "run_coverage_analysis", boom)
    out = run_scenario("altadena_fair_only")
    assert out["current"]["coverage"] is None
    assert out["current"]["insurance_gap"], "the older rules still give a gap list"
    assert out["future"]["fixes"]
    assert validate_output(out) == []
    assert "Please note" in template_report("x", out)


def test_plan_still_finishes_with_an_impossible_extended_percent():
    inputs = scenario_inputs(SCENARIOS["altadena_fair_only"])
    inputs["insurance"]["extended_replacement_pct"] = 500
    out = assess(inputs, cached_area(inputs["address"]))
    assert out["current"]["coverage"] is None
    assert out["future"]["fixes"]


def test_plan_works_when_only_the_hazard_zone_is_known():
    s = SCENARIOS["altadena_fair_only"]
    out = assess(scenario_inputs(s), {"hazard_class": "High"})
    coverage = out["current"]["coverage"]
    assert coverage["components"][4]["cost"] == {"low": None, "high": None}
    assert any("living_expenses" in w for w in coverage["warnings"])
    assert validate_output(out) == []


# --------------------------------------------------------------------- contract
def test_contract_flags_a_broken_coverage_block():
    out = run_scenario("altadena_fair_only")
    out["current"]["coverage"]["total_shortfall"] = {"low": 10, "high": 1}
    assert any("coverage.total_shortfall" in e for e in validate_output(out))
    out = run_scenario("altadena_fair_only")
    del out["current"]["coverage"]["scope_note"]
    assert any("coverage.scope_note" in e for e in validate_output(out))


# ----------------------------------------------------------------------- report
def test_report_has_the_loss_scenario():
    text = template_report("x", run_scenario("altadena_fair_only"))
    assert "## If your home is destroyed" in text
    assert "$355K to $905K" in text  # report rounds to executive format ($354,490 to $902,985)
    assert "Total-loss scenario only" in text


def test_report_says_a_partial_total_is_a_minimum():
    s = SCENARIOS["altadena_fair_only"]
    text = template_report("x", assess(scenario_inputs(s), {"hazard_class": "High"}))
    assert "at least" in text.lower()


# -------------------------------------------------------------------------- app
def start():
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception, at.exception
    return at


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception, at.exception


def fill(at, sid):
    next(s for s in at.selectbox if s.label == "Sample homeowner").set_value(sid).run()
    click(at, "Fill form")


def number(at, label):
    return next(n for n in at.number_input if n.label == label)


def test_app_shows_the_loss_scenario(no_key):
    at = start()
    fill(at, "altadena_fair_only")
    click(at, "Show my plan")
    md = " ".join(m.value for m in at.markdown)
    assert "$354,490 to $902,985" in md
    assert "**$948,490 to $1,552,985**" in md
    assert "**$594,000 to $715,000**" in md
    assert not [m.label for m in at.metric if " to " in m.value], "metrics cut off long ranges; use text that wraps"
    assert any("Total-loss scenario only" in c.value for c in at.caption)


def test_app_passes_the_new_form_fields_to_the_module(no_key):
    at = start()
    fill(at, "altadena_fair_only")
    number(at, "Other structures limit, Coverage B ($)").set_value(100_000)
    number(at, "Contents limit, Coverage C ($)").set_value(50_000)
    number(at, "Deductible ($)").set_value(2_500)
    number(at, "Code upgrade amount ($)").set_value(10_000)
    number(at, "Value of your belongings ($)").set_value(80_000)
    number(at, "Value of sheds, fences and other structures ($)").set_value(40_000)
    at.run()
    click(at, "Show my plan")
    inputs = at.session_state["result_inputs"]
    assert inputs["insurance"]["other_structures_limit"] == 100_000
    assert inputs["insurance"]["contents_limit"] == 50_000
    assert inputs["insurance"]["deductible"] == 2_500
    assert inputs["insurance"]["code_upgrade_amount"] == 10_000
    assert inputs["home"]["contents_value_estimate"] == 80_000
    assert inputs["home"]["other_structures_estimate"] == 40_000
    coverage = at.session_state["result"]["current"]["coverage"]
    assert coverage["deductible"] == 2_500
    components = {c["name"]: c for c in coverage["components"]}
    assert components["contents"]["shortfall"] == {"low": 30_000, "high": 30_000}
    assert components["other_structures"]["shortfall"] == {"low": 0, "high": 0}


def test_loading_a_sample_clears_earlier_optional_values(no_key):
    at = start()
    fill(at, "altadena_fair_only")
    number(at, "Deductible ($)").set_value(2_500)
    number(at, "Value of your belongings ($)").set_value(80_000)
    at.run()
    fill(at, "altadena_fair_dic")
    assert at.session_state["deductible"] is None
    assert at.session_state["contents_value_estimate"] is None


def test_clear_all_resets_the_new_fields(no_key):
    at = start()
    fill(at, "altadena_fair_only")
    click(at, "Clear all")
    assert at.session_state["contents_limit"] is None
    assert at.session_state["contents_value_estimate"] is None
    assert at.session_state["dic_covers"] == []


def test_reading_a_policy_fills_the_coverage_fields(fake_claude):
    at = start()
    next(s for s in at.selectbox if s.label == "Or use a sample policy").set_value("FAIR Plan + DIC (Altadena)").run()
    click(at, "Read policy")
    assert at.session_state["ins_type"] == "FAIR Plan + DIC policy"
    assert at.session_state["dwelling_limit"] == 650_000


def test_apply_policy_keeps_values_the_form_used_to_drop(no_key, monkeypatch):
    fields = {name: {"value": None, "source_text": None, "page": None} for name in policy_extract.FIELDS}
    fair = {**fields, "document_type": {"value": "fair_plan"}, "dwelling_limit": {"value": 500_000},
            "contents_limit": {"value": 60_000}, "other_structures_limit": {"value": 25_000},
            "deductible_all_perils": {"value": 1_000},
            "deductible_wildfire": {"value": {"amount": None, "pct": 2}},
            "code_upgrade": {"value": {"covered": True, "limit": None, "pct": 10}}}
    dic = {**fields, "document_type": {"value": "dic"}, "dic_covers": {"value": ["theft", "liability"]}}
    results = iter([{"fields": fair, "text_layer": True, "source": "cache"},
                    {"fields": dic, "text_layer": True, "source": "cache"}])
    monkeypatch.setattr(policy_extract, "extract", lambda data: next(results))
    at = start()
    next(s for s in at.selectbox if s.label == "Or use a sample policy").set_value("FAIR Plan + DIC (Altadena)").run()
    click(at, "Read policy")
    ss = at.session_state
    assert ss["contents_limit"] == 60_000
    assert ss["other_structures_limit"] == 25_000
    assert ss["deductible"] == 10_000, "2% wildfire deductible on a $500,000 dwelling limit"
    assert ss["code_upgrade_amount"] == 50_000
    assert ss["dic_covers"] == ["theft", "liability"]
