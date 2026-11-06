"""Wildfire analysis wired from Atharva's tract features (docs/wildfire_methodology.md)."""
from __future__ import annotations

import pytest

from msba_vibathon_2026 import wildfire
from msba_vibathon_2026.assess_stub import assess
from msba_vibathon_2026.contract import validate_output
from msba_vibathon_2026.report import template_report
from msba_vibathon_2026.scenarios import cached_area, load_scenarios, scenario_inputs
from msba_vibathon_2026.wildfire import rating, wildfire_analysis

SCENARIOS = load_scenarios()


@pytest.mark.parametrize("address,score,label", [
    ("1200 Chautauqua Blvd, Pacific Palisades, CA 90272", 70.1, "Very High"),
    ("1000 E Mariposa St, Altadena, CA 91001", 73.2, "Very High"),
    ("3200 Wilshire Blvd, Los Angeles, CA 90010", 0.0, "No observed exposure"),
])
def test_demo_addresses_use_tract_score(address, score, label):
    wf = wildfire_analysis(cached_area(address))
    assert wf["level"] == "tract" and wf["stub"] is False
    assert wf["score"] == score and wf["rating"] == label
    assert 0 <= wf["p_fire_annual"] <= 1


def test_altadena_outside_zone_but_tract_exposed():
    """The house point is outside any mapped zone, yet its tract is half Very High and burned in 2025."""
    area = cached_area("1000 E Mariposa St, Altadena, CA 91001")
    wf = wildfire_analysis(area)
    assert area["hazard_class"] is None
    assert wf["components"]["very_high_hazard_pct"] > 50 and wf["components"]["last_fire_year"] == 2025


@pytest.mark.parametrize("score,label", [
    (None, "Unknown"), (0, "No observed exposure"), (5, "Low"), (8.99, "Low"), (9, "Moderate"),
    (28.9, "Moderate"), (29, "High"), (49.9, "High"), (50, "Very High"), (79.5, "Very High"),
])
def test_rating_bands(score, label):
    assert rating(score) == label


def test_zip_fallback_when_tract_unknown():
    wf = wildfire_analysis({"geocode": {"tract_geoid": "06037999999", "zip": "91001"}})
    assert wf["level"] == "zip" and 50 < wf["score"] < 53 and wf["stub"] is False


def test_hazard_zone_fallback_when_address_not_found():
    wf = wildfire_analysis({"hazard_class": "High"})
    assert wf["level"] == "hazard_zone_only" and wf["score"] is None and wf["stub"] is True
    assert wf["rating"] == "High"


def test_every_la_tract_gives_a_valid_block():
    t = wildfire._tracts()
    assert len(t) == 2498
    for tract in t.index:
        wf = wildfire_analysis({"geocode": {"tract_geoid": tract, "zip": None}})
        assert wf["score"] is None or 0 <= wf["score"] <= 100, tract
        assert 0 <= wf["p_fire_annual"] <= 1, tract


def test_assess_marks_wildfire_real_and_house_placeholder():
    s = SCENARIOS["altadena_fair_only"]
    out = assess(scenario_inputs(s), cached_area(s["address"]))
    assert out["sources"] == {"wildfire": "real", "house": "placeholder"}
    assert out["current"]["wildfire"]["score"] == 73.2
    assert validate_output(out) == []
    assert "73 out of 100" in template_report(s["address"], out)


def test_tract_with_zero_fema_frequency_has_no_avoided_loss():
    s = SCENARIOS["wilshire_fully_hardened"]
    inputs = scenario_inputs(s)
    inputs["home"]["EAVES"] = "Unenclosed"  # force one fix
    out = assess(inputs, cached_area(s["address"]))
    fix = out["future"]["fixes"][0]
    assert out["current"]["wildfire"]["p_fire_annual"] == 0
    assert fix["est_avoided_loss"] == 0, "no FEMA wildfire frequency in this tract, so no avoided loss"
