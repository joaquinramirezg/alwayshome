"""Wildfire analysis: Atharva's tract exposure index (docs/wildfire_methodology.md).

Reads data/processed/tract_wildfire_features.parquet (built by scripts/build_wildfire_features.py).
`relative_exposure_score_0_100` is a descriptive index relative to LA County tracts, NOT a
probability: the app shows it as a score and rating. FEMA's annualized wildfire frequency
(`nri_wfir_afreq`) for the same tract is the only per-year figure, used for expected-loss math.

Fallbacks, in order: the tract -> the ZIP's residential-weighted mean -> the hazard zone alone.
"""
from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRACTS = ROOT / "data" / "processed" / "tract_wildfire_features.parquet"
ZIPS = ROOT / "data" / "processed" / "zip_wildfire_features.parquet"

# Rating cut points: quartiles of the score among the 884 LA tracts with any exposure (Nov 6 data).
CUTS = ((9.0, "Low"), (29.0, "Moderate"), (50.0, "High"))
METHOD = "Tract exposure index v2 (Atharva): very-high and high hazard share, burned footprint, FEMA expected loss"

# Used only when neither the tract nor the ZIP is available (e.g. the address lookup failed).
_HAZARD_ONLY = {"Very High": ("Very High", 0.015), "High": ("High", 0.008), "Moderate": ("Moderate", 0.003)}


def rating(score: float | None) -> str:
    if score is None:
        return "Unknown"
    if score == 0:
        return "No observed exposure"
    for cut, label in CUTS:
        if score < cut:
            return label
    return "Very High"


@lru_cache(maxsize=1)
def _tracts():
    import pandas as pd

    return pd.read_parquet(TRACTS).set_index("tract_geoid") if TRACTS.exists() else None


@lru_cache(maxsize=1)
def _zips():
    import pandas as pd

    return pd.read_parquet(ZIPS).set_index("zip") if ZIPS.exists() else None


def _val(x):
    if x is None:
        return None
    try:
        if isinstance(x, float) and math.isnan(x):
            return None
        import pandas as pd

        if pd.isna(x):
            return None
    except (TypeError, ValueError):
        pass
    return x.item() if hasattr(x, "item") else x


def wildfire_analysis(area: dict) -> dict:
    """Return the contract's `current.wildfire` block for an area_context() dict."""
    geo = area.get("geocode") or {}
    tract, zip_code = geo.get("tract_geoid"), geo.get("zip")

    t = _tracts()
    if t is not None and tract in t.index:
        r = t.loc[tract]
        score = _val(r["relative_exposure_score_0_100"])
        afreq = _val(r["nri_wfir_afreq"])
        return {
            "score": score,
            "rating": rating(score),
            "p_fire_annual": round(afreq, 5) if afreq is not None else 0.0,
            "level": "tract",
            "tract_geoid": tract,
            "components": {
                "very_high_hazard_pct": _val(r["hazard_very_high_pct"]),
                "high_hazard_pct": _val(r["hazard_high_pct"]),
                "burned_footprint_pct": _val(r["historical_burned_footprint_pct"]),
                "fires_since_2015": _val(r["fire_intersections_since_2015"]),
                "last_fire_year": _val(r["last_fire_year"]),
                "fema_expected_annual_loss": _val(r["nri_wfir_ealt"]),
                "indicators_used": _val(r["score_indicator_count"]),
            },
            "method": METHOD,
            "stub": False,
        }

    z = _zips()
    if z is not None and zip_code in z.index:
        r = z.loc[zip_code]
        score = _val(r["mean_relative_exposure_score_0_100"])
        if score is not None:
            afreq = _val(r.get("mean_nri_wfir_afreq"))
            return {
                "score": round(score, 1), "rating": rating(score),
                "p_fire_annual": round(afreq, 5) if afreq is not None else 0.0,
                "level": "zip", "zip": zip_code, "components": {}, "method": METHOD + " (ZIP average)", "stub": False,
            }

    hz = area.get("hazard_class")
    label, p = _HAZARD_ONLY.get(hz, ("Outside mapped zones", 0.001))
    return {"score": None, "rating": label, "p_fire_annual": p, "level": "hazard_zone_only", "components": {},
            "method": "Hazard zone only (address not found); annual frequency is a placeholder", "stub": True}
