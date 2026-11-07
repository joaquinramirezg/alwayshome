"""Step 4: the cost of a total loss, by component."""
import pytest

from msba_vibathon_2026.coverage import costs
from msba_vibathon_2026.coverage.config import load_config
from msba_vibathon_2026.coverage.costs import compute_costs
from msba_vibathon_2026.coverage.schemas import HomeInput, PolicyInput, Range

COMPONENTS = ["rebuild", "code_upgrade", "other_structures", "contents", "living_expenses"]
UNKNOWN = Range(low=None, high=None)


def run(policy=None, rent=None, **home):
    return compute_costs(policy or PolicyInput(), HomeInput(zip="91001", **home), rent)


def has_note(item, text: str) -> bool:
    return any(text.lower() in note.lower() for note in item.notes)


def test_every_component_is_returned_in_order():
    assert list(run().items) == COMPONENTS


def test_debris_removal_is_a_warning_not_a_component():
    result = run()
    assert "debris_removal" not in result.items
    assert result.warnings == [load_config().debris_removal_note.text]


# --------------------------------------------------------------------- rebuild
def test_rebuild_uses_the_per_sqft_range():
    assert run(sq_ft=1_800).items["rebuild"].cost == Range(low=540_000, high=900_000)


def test_rebuild_is_unknown_without_sqft():
    item = run().items["rebuild"]
    assert item.cost == UNKNOWN
    assert has_note(item, "square footage")


# ---------------------------------------------------------------- code upgrade
def test_code_upgrade_is_a_share_of_the_dwelling_limit():
    item = run(PolicyInput(dwelling_limit=450_000)).items["code_upgrade"]
    assert item.cost == Range(low=112_500, high=225_000)


def test_code_upgrade_is_labelled_as_an_assumption():
    item = run(PolicyInput(dwelling_limit=450_000)).items["code_upgrade"]
    assert has_note(item, "assumption")
    assert has_note(item, "not a measured cost")


def test_code_upgrade_is_unknown_without_a_dwelling_limit():
    item = run().items["code_upgrade"]
    assert item.cost == UNKNOWN
    assert has_note(item, "dwelling limit")


# ------------------------------------------------------------ other structures
def test_other_structures_defaults_to_a_share_of_rebuild():
    item = run(sq_ft=1_800).items["other_structures"]
    assert item.cost == Range(low=54_000, high=90_000)
    assert has_note(item, "assumed")


def test_other_structures_share_has_no_float_noise():
    assert run(sq_ft=5_500).items["other_structures"].cost == Range(low=165_000, high=275_000)


def test_other_structures_prefers_the_user_estimate():
    item = run(sq_ft=1_800, other_structures_estimate=30_000).items["other_structures"]
    assert item.cost == Range(low=30_000, high=30_000)
    assert not has_note(item, "assumed")


def test_other_structures_estimate_of_zero_is_kept():
    assert run(sq_ft=1_800, other_structures_estimate=0).items["other_structures"].cost == Range(low=0, high=0)


def test_other_structures_estimate_works_without_sqft():
    assert run(other_structures_estimate=30_000).items["other_structures"].cost == Range(low=30_000, high=30_000)


def test_other_structures_is_unknown_without_rebuild_or_estimate():
    item = run().items["other_structures"]
    assert item.cost == UNKNOWN
    assert has_note(item, "other structures")


# -------------------------------------------------------------------- contents
def test_contents_prefers_the_user_estimate():
    item = run(PolicyInput(contents_limit=550_000), contents_value_estimate=300_000).items["contents"]
    assert item.cost == Range(low=300_000, high=300_000)
    assert not has_note(item, "assumed equal to your limit")


def test_contents_estimate_of_zero_is_kept():
    item = run(PolicyInput(contents_limit=550_000), contents_value_estimate=0).items["contents"]
    assert item.cost == Range(low=0, high=0)


def test_contents_falls_back_to_the_limit_with_a_flag():
    item = run(PolicyInput(contents_limit=200_000)).items["contents"]
    assert item.cost == Range(low=200_000, high=200_000)
    assert has_note(item, "assumed equal to your limit")


def test_contents_is_unknown_when_both_are_missing():
    item = run().items["contents"]
    assert item.cost == UNKNOWN
    assert has_note(item, "contents")


# ------------------------------------------------------------- living expenses
def test_living_expenses_use_rent_for_24_to_36_months():
    assert run(rent=4_000).items["living_expenses"].cost == Range(low=96_000, high=144_000)


def test_living_expenses_are_unknown_without_rent():
    item = run().items["living_expenses"]
    assert item.cost == UNKNOWN
    assert has_note(item, "no rent data for ZIP")


# ------------------------------------------------------ hand-calculated columns
def test_case_1_cost_column():
    policy = PolicyInput(document_type="fair_plan", dwelling_limit=450_000, contents_limit=0)
    items = run(policy, rent=4_000, sq_ft=1_800, contents_value_estimate=100_000).items
    assert {name: (i.cost.low, i.cost.high) for name, i in items.items()} == {
        "rebuild": (540_000, 900_000),
        "code_upgrade": (112_500, 225_000),
        "other_structures": (54_000, 90_000),
        "contents": (100_000, 100_000),
        "living_expenses": (96_000, 144_000),
    }


def test_case_2_cost_column():
    policy = PolicyInput(document_type="homeowners", dwelling_limit=1_100_000, contents_limit=550_000)
    items = run(policy, rent=5_000, sq_ft=2_000, contents_value_estimate=300_000).items
    assert {name: (i.cost.low, i.cost.high) for name, i in items.items()} == {
        "rebuild": (600_000, 1_000_000),
        "code_upgrade": (275_000, 550_000),
        "other_structures": (60_000, 100_000),
        "contents": (300_000, 300_000),
        "living_expenses": (120_000, 180_000),
    }


# ---------------------------------------------------------------------- general
def test_all_unknown_does_not_crash():
    assert all(item.cost == UNKNOWN for item in run().items.values())


def test_numbers_come_from_config(monkeypatch):
    config = load_config()
    changed = config.model_copy(update={
        "rebuild_cost_per_sqft": config.rebuild_cost_per_sqft.model_copy(update={"low": 100, "high": 200}),
    })
    monkeypatch.setattr(costs, "load_config", lambda: changed)
    assert run(sq_ft=1_000).items["rebuild"].cost == Range(low=100_000, high=200_000)


@pytest.mark.parametrize("name", COMPONENTS)
def test_notes_are_not_shared_between_calls(name):
    run().items[name].notes.append("extra")
    assert "extra" not in run().items[name].notes
