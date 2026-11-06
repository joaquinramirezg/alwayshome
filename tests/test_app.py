"""Drive the real Streamlit app headlessly (streamlit.testing). No browser, no API key."""
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from msba_vibathon_2026.scenarios import load_scenarios

APP = str(Path(__file__).resolve().parents[1] / "app.py")
SCENARIOS = load_scenarios()


def start(dev=False):
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not at.exception, at.exception
    if dev:
        at.toggle[0].set_value(True).run()
    return at


def click(at, label):
    next(b for b in at.button if b.label == label).click().run()
    assert not at.exception, at.exception
    return at


def select(at, label, value):
    next(s for s in at.selectbox if s.label == label).set_value(value).run()
    assert not at.exception, at.exception
    return at


@pytest.mark.parametrize("sid", list(SCENARIOS))
def test_load_scenario_and_plan(sid, no_key):
    at = start(dev=True)
    select(at, "Sample homeowner", sid)
    click(at, "Load this homeowner")
    assert at.session_state["address"] == SCENARIOS[sid]["address"]
    assert at.session_state["budget"] == SCENARIOS[sid]["budget"]
    click(at, "Show my plan")
    md = " ".join(m.value for m in at.markdown)
    assert "Inputs contract:** ✅ valid" in md and "Output contract:** ✅ valid" in md
    for g in SCENARIOS[sid]["expect"]["gaps_include"]:
        assert g.lower() in md.lower(), f"{sid}: gap {g!r} not shown"
    click(at, "Write report")
    assert any("Your AlwaysON plan" in m.value for m in at.markdown)


@pytest.mark.parametrize("sample", [
    "FAIR Plan + DIC (Altadena)", "FAIR Plan only (Altadena)", "FAIR Plan, scanned copy (no text layer)",
    "Private HO-3, underinsured (Palisades)", "Private HO-3, two pages (Altadena)",
    "Private HO-3, well covered (Wilshire)", "Not a policy: non-renewal letter",
])
def test_read_sample_policy_with_ai(sample, fake_claude):
    at = start()
    select(at, "Or use a sample policy", sample)
    click(at, "Read policy")
    assert not at.error, [e.value for e in at.error]
    assert at.session_state["extractions"], "extraction table missing"
    if "scanned" in sample:
        assert any("Scanned PDF" in w.value for w in at.warning)


def test_policy_prefills_form(fake_claude):
    at = start()
    select(at, "Or use a sample policy", "FAIR Plan + DIC (Altadena)")
    click(at, "Read policy")
    ss = at.session_state
    assert ss["ins_type"] == "FAIR Plan + DIC policy"
    assert ss["dwelling_limit"] == 650_000
    assert ss["dwelling_settlement"] == "actual_cash_value"
    assert ss["premium_total"] == 6180 + 1450
    assert ss["debris_removal"] is True


def test_read_policy_without_key_falls_back(no_key):
    at = start()
    select(at, "Or use a sample policy", "FAIR Plan only (Altadena)")
    click(at, "Read policy")
    assert at.error and "enter by hand" in at.error[0].value.lower()
    click(at, "Show my plan")  # the rest of the app still works


@pytest.mark.parametrize("address", [
    "1200 Chautauqua Blvd, Pacific Palisades, CA 90272",
    "1000 E Mariposa St, Altadena, CA 91001",
    "3200 Wilshire Blvd, Los Angeles, CA 90010",
])
def test_demo_addresses_load_offline(address, no_key):
    at = start()
    select(at, "Or pick a demo address", address)
    assert at.session_state["address"] == address
    assert any(m.label == "Fire hazard zone" for m in at.metric)


def test_changed_inputs_warn_stale_plan(no_key):
    at = start()
    click(at, "Show my plan")
    at.slider[0].set_value(30_000).run()
    assert any("Inputs changed" in i.value for i in at.info)
