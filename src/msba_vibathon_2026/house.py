"""House analysis: chance the house is destroyed if a wildfire reaches it (docs/house_model.md).

Logistic regression trained on 22,071 CAL FIRE damage inspections from the 2025 Eaton and Palisades
fires (scripts/train_house_model.py -> data/processed/house_model.json), with a fire x ZIP location
effect. Predictions average over locations, so they describe a typical home that faced those fires.

- "Unknown" answers are scored as the frequency-weighted average of the known answers (the training
  "Unknown" dummy leaks the outcome and is never used here).
- A fix is valued by switching one answer to its hardened value. When the data show no reduction
  (siding, attached fence), the effect is 0: we don't claim a benefit the data don't support.
- Fixes the inspections don't record (defensible space, clearing under decks) use a small assumed
  relative reduction, labelled as an assumption.
Associations from two fires, not causal effects or an inspection of this home.
"""
from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "data" / "processed" / "house_model.json"

# fix -> (checklist field, hardened answer) for fixes the inspection data record
HARDENED = {
    "class_a_roof": ("ROOFCONSTRUCTION", "Tile"),
    "ember_resistant_vents": ("VENTSCREEN", 'Mesh Screen <= 1/8"'),
    "enclosed_eaves": ("EAVES", "Enclosed"),
    "double_pane_or_shutters": ("WINDOWPANE", "Multi Pane"),
    "ember_zone_5ft": ("FENCEATTACHEDTOSTRUCTURE", "Non Combustible"),
    "noncombustible_6in_walls": ("EXTERIORSIDING", "Stucco/Brick/Cement"),
    "outbuildings_30ft": ("UTILITYMISCSTRUCTUREDISTANCE", ">50'"),
}
# fix -> assumed relative reduction in damage chance (not in the inspection data)
ASSUMED = {"defensible_space": 0.10, "clear_under_decks": 0.05}


@lru_cache(maxsize=1)
def model() -> dict | None:
    return json.loads(MODEL.read_text()) if MODEL.exists() else None


def _coef(m: dict, field: str, value) -> float:
    coefs = m["fields"][field]
    if value in coefs and value != "Unknown":
        return coefs[value]
    freq = m["frequencies"][field]  # "I don't know" or unseen answer: weighted average of known answers
    return sum(coefs.get(k, 0.0) * w for k, w in freq.items())


def p_destroyed(home: dict) -> float:
    """Chance of destruction if fire reaches the house, averaged over the 2025 fire locations."""
    m = model()
    base = m["intercept"] + sum(_coef(m, f, home.get(f)) for f in m["fields"])
    return sum(w / (1 + math.exp(-(base + m["fire_effects"][loc]))) for loc, w in m["fire_weight"].items())


def impact_with_fixes(home: dict, fixes: list[str]) -> float:
    """Damage chance after applying fixes; never higher than without them."""
    now = p_destroyed(home)
    h = dict(home)
    for f in fixes:
        if f in HARDENED:
            field, value = HARDENED[f]
            h[field] = value
    p = min(now, p_destroyed(h))
    # a hardened answer the data rate as riskier is ignored field by field
    for f in fixes:
        if f in HARDENED:
            field, value = HARDENED[f]
            single = dict(home, **{field: value})
            if p_destroyed(single) > now:
                h[field] = home.get(field)
    p = min(now, p_destroyed(h))
    for f in fixes:
        p *= 1 - ASSUMED.get(f, 0.0)
    return p


def effect_basis(fix: str, home: dict) -> str:
    if fix in ASSUMED:
        return "assumed"
    if fix in HARDENED:
        field, value = HARDENED[fix]
        return "data" if p_destroyed(dict(home, **{field: value})) < p_destroyed(home) else "no_measured_effect"
    return "none"
