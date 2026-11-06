"""Gap rules, assess() contract, every sample homeowner end to end, and the report."""
from __future__ import annotations

import pytest

from msba_vibathon_2026.assess_stub import MEASURES, assess
from msba_vibathon_2026.contract import validate_inputs, validate_output
from msba_vibathon_2026.gaps import REBUILD_COST_PER_SQFT, coverage_gaps
from msba_vibathon_2026.report import ai_report, template_report
from msba_vibathon_2026.scenarios import cached_area, load_scenarios, scenario_inputs

SCENARIOS = load_scenarios()


def gap_names(gaps):
    return " | ".join(g["gap"] for g in gaps).lower()


# ---------------------------------------------------------------- gap rules
BASE = {"documents": ["homeowners"], "has_dic": False, "dwelling_limit": 1_000_000,
        "dwelling_settlement": "replacement_cost", "extended_replacement_pct": 25, "premium_total": 5000,
        "liability_limit": 500_000, "loss_of_use_limit": 200_000, "code_upgrade": True, "debris_removal": True}


def test_well_covered_policy_has_no_gaps():
    assert coverage_gaps(BASE, living_area_sqft=1800) == []


@pytest.mark.parametrize("change,expected", [
    ({"documents": ["fair_plan"]}, "fair plan only"),
    ({"liability_limit": 0}, "liability"),
    ({"loss_of_use_limit": 0}, "loss-of-use"),
    ({"dwelling_settlement": "actual_cash_value"}, "actual cash value"),
    ({"extended_replacement_pct": 0}, "extended replacement"),
    ({"code_upgrade": False}, "code upgrade"),
    ({"code_upgrade": {"covered": False, "limit": None, "pct": None}}, "code upgrade"),
    ({"debris_removal": None}, "debris removal"),
    ({"dwelling_limit": 500_000, "extended_replacement_pct": 0}, "underinsured"),
])
def test_each_gap_rule_fires(change, expected):
    assert expected in gap_names(coverage_gaps({**BASE, **change}, living_area_sqft=1800))


def test_dic_closes_fair_plan_gap():
    ins = {**BASE, "documents": ["fair_plan", "dic"], "has_dic": True}
    assert "fair plan only" not in gap_names(coverage_gaps(ins, 1800))


def test_extended_replacement_counts_toward_underinsurance():
    rebuild = 2000 * REBUILD_COST_PER_SQFT  # 900k
    ins = {**BASE, "dwelling_limit": 760_000, "extended_replacement_pct": 0}
    assert "underinsured" in gap_names(coverage_gaps(ins, 2000))
    ins["extended_replacement_pct"] = 25  # 950k effective
    assert "underinsured" not in gap_names(coverage_gaps(ins, 2000))
    assert rebuild == 900_000


def test_no_living_area_skips_underinsurance():
    ins = {**BASE, "dwelling_limit": 100_000}
    assert "underinsured" not in gap_names(coverage_gaps(ins, None))


def test_gaps_sorted_by_severity():
    gaps = coverage_gaps({**BASE, "documents": ["fair_plan"], "debris_removal": False, "code_upgrade": False}, 1800)
    order = [g["severity"] for g in gaps]
    assert order == sorted(order, key=["high", "medium", "low"].index)


# ---------------------------------------------------------------- every sample homeowner
@pytest.mark.parametrize("sid", list(SCENARIOS))
def test_scenario_end_to_end(sid):
    s = SCENARIOS[sid]
    inputs = scenario_inputs(s)
    assert validate_inputs(inputs) == []
    out = assess(inputs, cached_area(s["address"]))
    assert validate_output(out) == [], validate_output(out)

    exp = s["expect"]
    names = gap_names(out["current"]["insurance_gap"])
    for g in exp["gaps_include"]:
        assert g.lower() in names, f"{sid}: expected gap {g!r} in {names!r}"
    for g in exp["gaps_exclude"]:
        assert g.lower() not in names, f"{sid}: unexpected gap {g!r}"

    fixes = out["future"]["fixes"]
    assert sorted(f["measure_id"] for f in fixes) == sorted(exp["fixes"])

    plan = out["future"]["plan_within_budget"]
    assert sum(MEASURES[m][1] for m in plan) <= inputs["budget"], "plan must fit the budget (low estimate)"
    if exp.get("plan_empty"):
        assert plan == []
    if exp.get("plan_all"):
        assert sorted(plan) == sorted(exp["fixes"])
    assert out["future"]["house_after_plan"]["impact"] <= out["current"]["house"]["impact"]


@pytest.mark.parametrize("sid", list(SCENARIOS))
def test_report_renders_for_every_scenario(sid, no_key):
    s = SCENARIOS[sid]
    out = assess(scenario_inputs(s), cached_area(s["address"]))
    text = template_report(s["address"], out)
    assert text.startswith("# Your AlwaysON plan") and "Please note" in text
    for f in out["future"]["fixes"]:
        assert f["name"] in text
    md, source = ai_report(s["address"], out)
    assert source == "template" and md == text, "without a key the AI report falls back to the template"


def test_ai_report_falls_back_on_api_error(monkeypatch):
    import anthropic

    s = SCENARIOS["altadena_fair_only"]
    out = assess(scenario_inputs(s), cached_area(s["address"]))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")

    class Broken:
        def __init__(self, *a, **k):
            raise ConnectionError("down")
    monkeypatch.setattr(anthropic, "Anthropic", Broken)
    assert ai_report(s["address"], out)[1] == "template"


# ---------------------------------------------------------------- contract checker catches bad model output
def test_contract_flags_bad_output():
    s = SCENARIOS["altadena_fair_only"]
    out = assess(scenario_inputs(s), cached_area(s["address"]))
    out["current"]["wildfire"]["p_fire_annual"] = 3
    out["future"]["fixes"][0]["cost_low"] = 10**9
    out["future"]["plan_within_budget"].append("not_a_fix")
    errs = " ".join(validate_output(out))
    assert "p_fire_annual" in errs and "cost_low > cost_high" in errs and "plan_within_budget" in errs


def test_contract_flags_bad_inputs():
    inputs = scenario_inputs(SCENARIOS["altadena_fair_only"])
    inputs["home"]["EAVES"] = "Open"
    inputs["budget"] = -5
    errs = " ".join(validate_inputs(inputs))
    assert "EAVES" in errs and "budget" in errs


def test_area_without_hazard_zone_still_works():
    s = SCENARIOS["altadena_fair_only"]
    out = assess(scenario_inputs(s), {"hazard_class": None})
    assert validate_output(out) == []
