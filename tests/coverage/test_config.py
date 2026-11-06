"""Step 1: config.yaml holds the plan's exact values, and config.py validates them."""
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from msba_vibathon_2026.coverage.config import Config, load_config

CONFIG_PATH = Path(__file__).resolve().parents[2] / "src/msba_vibathon_2026/coverage/config.yaml"
ALL_SECTIONS = {
    "rebuild_cost_per_sqft", "price_surge_note", "code_upgrade_recommended_pct_of_dwelling",
    "other_structures_cost_pct_of_rebuild", "fair_plan_other_structures_pct_of_dwelling",
    "living_expense_months", "fair_plan_combined_cap", "extended_replacement_recommended_min_pct",
    "stale_coverage_years", "contents_no_inventory_rule", "debris_removal_note", "acv_warning",
}


def raw_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text())


def test_yaml_has_exactly_the_planned_sections():
    assert set(raw_config()) == ALL_SECTIONS


def test_numeric_values_match_the_plan():
    c = load_config()
    assert (c.rebuild_cost_per_sqft.low, c.rebuild_cost_per_sqft.high) == (300, 500)
    assert (c.code_upgrade_recommended_pct_of_dwelling.low,
            c.code_upgrade_recommended_pct_of_dwelling.high) == (0.25, 0.50)
    assert c.other_structures_cost_pct_of_rebuild.value == 0.10
    assert c.fair_plan_other_structures_pct_of_dwelling.value == 0.10
    assert (c.living_expense_months.low, c.living_expense_months.high) == (24, 36)
    assert c.fair_plan_combined_cap.value == 3_000_000
    assert c.extended_replacement_recommended_min_pct.value == 0.25
    assert c.stale_coverage_years.value == 3
    assert c.contents_no_inventory_rule.pct_of_limit == 0.60
    assert c.contents_no_inventory_rule.cap == 350_000
    assert c.contents_no_inventory_rule.effective == "2026-01"


def test_assumption_flags_match_the_plan():
    c = load_config()
    assert c.other_structures_cost_pct_of_rebuild.assumption is True
    assert c.stale_coverage_years.assumption is True
    assert c.rebuild_cost_per_sqft.assumption is False
    assert c.fair_plan_combined_cap.assumption is False


def test_source_urls_match_the_plan():
    c = load_config()
    assert c.rebuild_cost_per_sqft.source_url == (
        "https://uphelp.org/wildfire-survivors-are-finding-out-they-are-underinsured-after-losing-their-homes/")
    assert c.fair_plan_combined_cap.source_url == "https://www.valuepenguin.com/california-fair-plan-home-insurance"
    assert c.contents_no_inventory_rule.source_url == (
        "https://www.insurance.ca.gov/0400-news/0100-press-releases/2025/release067-2025.cfm")
    assert c.acv_warning.source_url == (
        "https://www.propertyinsurancecoveragelaw.com/blog/"
        "california-wildfires-strike-again-a-summary-of-changes-in-the-law-to-help-policyholders/")


def test_warning_texts_are_loaded():
    c = load_config()
    assert c.price_surge_note.text.startswith("Contractor prices after disasters")
    assert "Not included in the dollar shortfall" in c.debris_removal_note.text
    assert c.acv_warning.text.startswith("Your policy pays actual cash value")


def test_both_verify_before_demo_items_stay_marked():
    c = load_config()
    assert "VERIFY" in c.fair_plan_combined_cap.note
    assert "VERIFY" in c.acv_warning.note


def test_every_section_has_a_source_or_is_marked_assumption():
    for name, section in raw_config().items():
        assert section.get("source_url") or section.get("assumption") is True, name


def test_load_config_loads_once():
    assert load_config() is load_config()


def test_config_values_cannot_be_changed():
    with pytest.raises(ValidationError):
        load_config().stale_coverage_years.value = 99


@pytest.mark.parametrize("section", sorted(ALL_SECTIONS))
def test_missing_section_is_rejected(section):
    data = raw_config()
    del data[section]
    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_missing_value_is_rejected():
    data = raw_config()
    del data["rebuild_cost_per_sqft"]["high"]
    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_value_of_the_wrong_type_is_rejected():
    data = raw_config()
    data["fair_plan_combined_cap"]["value"] = "about three million"
    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_value_without_source_or_assumption_flag_is_rejected():
    data = raw_config()
    del data["fair_plan_combined_cap"]["source_url"]
    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_unexpected_key_is_rejected():
    data = raw_config()
    data["new_threshold"] = {"value": 1, "assumption": True}
    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_range_with_low_above_high_is_rejected():
    data = raw_config()
    data["rebuild_cost_per_sqft"] |= {"low": 600, "high": 500}
    with pytest.raises(ValidationError):
        Config.model_validate(data)


def test_sb_495_note_says_the_inventory_is_deferred_not_waived():
    note = load_config().contents_no_inventory_rule.note
    assert "without a detailed inventory for at least 100 days" in note
    assert "without an itemized inventory" not in note
