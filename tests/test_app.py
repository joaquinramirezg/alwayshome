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


def widget(items, label):
    return next(w for w in items if w.label == label)


def select(at, label, value):
    widget(at.selectbox, label).set_value(value).run()
    assert not at.exception, at.exception
    return at


def fill_sample(at, sid):
    select(at, "Sample homeowner", sid)
    return click(at, "Fill form")


# ---------------------------------------------------------------- a real homeowner's first visit
def test_starts_empty(no_key):
    at = start()
    ss = at.session_state
    assert ss["address"] == "" and ss["ROOFCONSTRUCTION"] is None and ss["dwelling_limit"] is None
    assert any("Enter your address" in i.value for i in at.info)
    assert not any(m.label == "Fire hazard zone" for m in at.metric), "no lookup before an address is entered"
    click(at, "Show my plan")
    assert at.error and "Please fill in" in at.error[0].value and "your address" in at.error[0].value
    assert "result" not in ss


def test_homeowner_types_everything_by_hand(no_key):
    """Fill the form field by field, the way a homeowner would, with no sample loaded."""
    at = start(dev=True)
    widget(at.text_input, "Street address in Los Angeles County").input("1000 E Mariposa St, Altadena, CA 91001").run()
    assert any(m.label == "Fire hazard zone" for m in at.metric)
    for label, value in [("Roof material", "Asphalt"), ("Eaves", "Unenclosed"), ("Vent screens", 'Mesh Screen > 1/8"'),
                         ("Exterior siding", "Stucco/Brick/Cement"), ("Windows", "Unknown"),
                         ("Elevated deck", "No Deck/Porch"), ("Fence attached to the house", "Combustible"),
                         ("Sheds or outbuildings", "Not Applicable")]:
        widget(at.selectbox, label).set_value(value)
    widget(at.number_input, "Year built").set_value(1958)
    widget(at.number_input, "Living area (sq ft)").set_value(1600)
    widget(at.number_input, "Stories").set_value(1)
    widget(at.checkbox, "Defensible space done (trees trimmed, brush cleared)").check()
    at.run()
    click(at, "Show my plan")
    assert at.error and "current coverage" in at.error[0].value, "insurance still missing"
    widget(at.radio, "Current coverage").set_value("FAIR Plan only")
    widget(at.number_input, "Dwelling limit ($)").set_value(600_000)
    widget(at.selectbox, "How the dwelling is paid").set_value("actual_cash_value")
    widget(at.number_input, "Total annual premium ($)").set_value(5_900)
    at.run()
    click(at, "Show my plan")
    assert not at.error
    md = " ".join(m.value for m in at.markdown)
    assert "Inputs contract:** ✅ valid" in md and "Output contract:** ✅ valid" in md
    assert "FAIR Plan only" in md and "actual cash value" in md.lower()
    assert at.session_state["result_inputs"]["insurance"]["liability_limit"] == 0, "empty optional amount means none"


def test_clear_all_resets_form(no_key):
    at = start()
    fill_sample(at, "altadena_fair_only")
    click(at, "Show my plan")
    click(at, "Clear all")
    ss = at.session_state
    assert ss["address"] == "" and ss["EAVES"] is None and ss["ins_type"] is None and "result" not in ss


# ---------------------------------------------------------------- sample homeowners
@pytest.mark.parametrize("sid", list(SCENARIOS))
def test_fill_sample_and_plan(sid, no_key):
    at = start(dev=True)
    fill_sample(at, sid)
    assert at.session_state["address"] == SCENARIOS[sid]["address"]
    assert at.session_state["budget"] == SCENARIOS[sid]["budget"]
    click(at, "Show my plan")
    assert not at.error, [e.value for e in at.error]
    md = " ".join(m.value for m in at.markdown)
    assert "Inputs contract:** ✅ valid" in md and "Output contract:** ✅ valid" in md
    for g in SCENARIOS[sid]["expect"]["gaps_include"]:
        assert g.lower() in md.lower(), f"{sid}: gap {g!r} not shown"
    click(at, "Write report")
    assert any("Your AlwaysHome plan" in m.value for m in at.markdown)


def test_changed_inputs_warn_stale_plan(no_key):
    at = start()
    fill_sample(at, "altadena_fair_only")
    click(at, "Show my plan")
    at.slider[0].set_value(30_000).run()
    assert any("Inputs changed" in i.value for i in at.info)


# ---------------------------------------------------------------- policy PDFs
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


def test_policy_fills_empty_insurance_form(fake_claude):
    at = start()
    assert at.session_state["dwelling_limit"] is None
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
    fill_sample(at, "altadena_fair_only")
    click(at, "Show my plan")  # the rest of the app still works
    assert "result" in at.session_state


# ---------------------------------------------------------------- addresses
@pytest.mark.parametrize("address", [
    "1200 Chautauqua Blvd, Pacific Palisades, CA 90272",
    "1000 E Mariposa St, Altadena, CA 91001",
    "3200 Wilshire Blvd, Los Angeles, CA 90010",
])
def test_demo_addresses_load_offline(address, no_key):
    at = start()
    select(at, "Or just a demo address", address)
    assert at.session_state["address"] == address
    assert any(m.label == "Fire hazard zone" for m in at.metric)


def test_plan_shows_real_wildfire_score(no_key):
    at = start()
    fill_sample(at, "altadena_fair_only")
    click(at, "Show my plan")
    m = {x.label: x.value for x in at.metric}
    assert m["Wildfire exposure of your area"] == "73 / 100"
    assert m["Tract in Very High zone"] == "52%"
    assert not any("placeholder" in w.value for w in at.warning), "both models are real now"


def test_password_gate(no_key, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "fire123")
    at = AppTest.from_file(APP, default_timeout=180).run()
    assert not any(h.value == "1. Your home's location" for h in at.header), "form must be hidden"
    at.text_input[0].input("wrong").run()
    assert not any(h.value == "1. Your home's location" for h in at.header)
    at.text_input[0].input("fire123").run()
    assert any(h.value == "1. Your home's location" for h in at.header)


def test_ai_budget_per_session(fake_claude, monkeypatch):
    monkeypatch.setenv("AI_CALLS_PER_SESSION", "1")
    at = start()
    select(at, "Or use a sample policy", "FAIR Plan only (Altadena)")
    click(at, "Read policy")
    assert not at.error and at.session_state["ai_calls"] == 1
    click(at, "Read policy")
    assert at.error and "AI limit" in at.error[0].value
