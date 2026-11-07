"""House-damage model trained on CAL FIRE inspections (src/msba_vibathon_2026/house.py)."""
from __future__ import annotations

import pytest

from msba_vibathon_2026 import house
from msba_vibathon_2026.assess_stub import assess
from msba_vibathon_2026.contract import validate_output
from msba_vibathon_2026.scenarios import cached_area, load_scenarios, scenario_inputs

SCENARIOS = load_scenarios()
WORST = {"ROOFCONSTRUCTION": "Wood", "EAVES": "Unenclosed", "VENTSCREEN": 'Mesh Screen > 1/8"', "EXTERIORSIDING": "Wood",
         "WINDOWPANE": "Single Pane", "DECKPORCHELEVATED": "Wood", "FENCEATTACHEDTOSTRUCTURE": "Combustible",
         "UTILITYMISCSTRUCTUREDISTANCE": "<30'"}


def test_model_file_and_honest_metrics():
    m = house.model()
    assert m is not None and m["metrics"]["rows"] > 20_000
    assert m["metrics"]["cv_auc_rows_without_unknown"] >= 0.75, "honest AUC on rows without Unknown"


def test_probability_bounds_and_unknown_is_not_the_leaky_dummy():
    p_unknown = house.p_destroyed({f: "Unknown" for f in WORST})
    assert 0 < p_unknown < 1
    m = house.model()
    leaky = m["fields"]["EAVES"]["Unknown"]
    assert house._coef(m, "EAVES", "Unknown") != leaky, "I don't know must use the known-answer average"


@pytest.mark.parametrize("fix", ["class_a_roof", "ember_resistant_vents", "enclosed_eaves", "double_pane_or_shutters", "outbuildings_30ft"])
def test_data_backed_fixes_reduce_damage(fix):
    assert house.impact_with_fixes(WORST, [fix]) < house.p_destroyed(WORST)
    assert house.effect_basis(fix, WORST) == "data"


@pytest.mark.parametrize("fix", ["ember_zone_5ft", "noncombustible_6in_walls"])
def test_no_benefit_claimed_where_data_show_none(fix):
    assert house.impact_with_fixes(WORST, [fix]) == pytest.approx(house.p_destroyed(WORST))
    assert house.effect_basis(fix, WORST) == "no_measured_effect"


def test_assumed_fixes_are_labelled():
    assert house.effect_basis("defensible_space", WORST) == "assumed"
    assert house.impact_with_fixes(WORST, ["defensible_space"]) == pytest.approx(house.p_destroyed(WORST) * 0.9)


def test_more_fixes_never_increase_damage():
    fixes = list(house.HARDENED) + list(house.ASSUMED)
    p = house.p_destroyed(WORST)
    for i in range(1, len(fixes) + 1):
        q = house.impact_with_fixes(WORST, fixes[:i])
        assert q <= p + 1e-12
        p = q


@pytest.mark.parametrize("sid", list(SCENARIOS))
def test_assess_uses_real_house_model(sid):
    s = SCENARIOS[sid]
    out = assess(scenario_inputs(s), cached_area(s["address"]))
    assert out["sources"]["house"] == "real" and validate_output(out) == []
    for f in out["future"]["fixes"]:
        assert f["effect_basis"] in ("data", "assumed", "no_measured_effect")
