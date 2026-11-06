# Inputs, sources and the model-app contract

Proposal (Nov 6, 2:30 PM). Split: **B. Model** (Atharva, David) and **A. App** (Joaquin, Streamlit for now). This file fixes what each side hands the other so both can build in parallel.

## 1. Where each input comes from

Legend: **Data** = pulled automatically from `data/processed/` via `scripts/utils.py`. **Ask** = the homeowner answers. **AI** = optional pre-fill from a photo, always confirmed by the user. **Assume** = our own labelled assumption.

### Location and area risk (all Data, no questions)

| Item | Source | Already in `area_context()` |
|---|---|---|
| Lat/lon, ZIP, tract, place | Census geocoder | yes |
| Fire hazard zone (Moderate / High / Very High / none) | `hazard_zones` | yes |
| Past fires within 5 km | `fire_perimeters` | yes |
| Non-renewal trend 2015-2023 | `zip_insurance` | yes |
| FAIR Plan share of the ZIP (2022) | `zip_fair_plan` | yes |
| Wildfire annual frequency and expected loss for the tract | `nri_tracts` (`WFIR_AFREQ`, `WFIR_EALT`) | EAL yes, frequency not yet |
| Community risk percentiles | `wrc_communities` | yes |
| ZIP home value, median income | Zillow, ACS | yes |

### The home (Ask, using the DINS categories)

Ask these with the answer options CAL FIRE uses in its damage inspections (DINS), so the answers line up with the data.

| Question | DINS field | Options | AI pre-fill possible? |
|---|---|---|---|
| Roof material | `ROOFCONSTRUCTION` | Wood, Asphalt, Concrete, Tile, Metal, Other | yes: aerial or photo |
| Eaves | `EAVES` | Enclosed, Unenclosed, No eaves | yes: home photo |
| Vent screens | `VENTSCREEN` | Mesh <= 1/8", Mesh > 1/8", Unscreened, No vents | no, ask |
| Exterior siding | `EXTERIORSIDING` | Metal, Stucco/Brick/Cement, Vinyl, Wood, Other | yes: home photo |
| Windows | `WINDOWPANE` | Single pane, Multi pane | no, ask |
| Deck on ground | `DECKPORCHONGRADE` | Composite, Wood, Masonry/Concrete, None | yes: photo |
| Elevated deck | `DECKPORCHELEVATED` | same | yes: photo |
| Patio cover or carport | `PATIOCOVERCARPORT` | Combustible, Non combustible, None | yes: photo |
| Fence attached to the house | `FENCEATTACHEDTOSTRUCTURE` | Combustible, Non combustible, None | yes: photo |
| Propane tank distance | `PROPANETANKDISTANCE` | 0-10', 11-20', 21-30', >30', none | no, ask |
| Sheds and outbuildings distance | `UTILITYMISCSTRUCTUREDISTANCE` | <30', 30-50', >50', none | yes: aerial |
| Year built | `YEARBUILT` | number | ask (assessor data is a later add) |
| Living area (sq ft) and stories | not in DINS | number | ask; scales fix costs |

Also ask the official measures (`measures.csv`) not covered above: 5-foot ember-resistant zone, 6 inches of noncombustible wall base, cleared under decks, defensible space done, community is Firewise USA or a Fire Risk Reduction Community.

Drop "date of purchase": it does not change risk, cost or eligibility.

There is **no public per-home fire rating**. The hazard zone is an area rating; the home's own rating is what the model computes from the answers above.

### Insurance (Ask; there is no public data per home)

| Question | Why |
|---|---|
| Current insurer type: FAIR Plan only, FAIR Plan + difference-in-conditions (DIC) policy, private, none | Drives the gap analysis |
| Annual premium (total, and each policy if there are two) | Baseline cost; savings are measured from it |
| Dwelling coverage limit | Underinsurance check against rebuild cost |
| Deductible | Shown in the gap view |
| Was it non-renewed, and when? | Context and urgency |

Gap rules need no model: FAIR Plan alone covers fire (and some named perils) but not theft, liability or water damage, so "FAIR only, no DIC" is a coverage gap. A dwelling limit well below the rebuild estimate is an underinsurance gap.

Policy PDF upload stays on the roadmap.

### Costs and discounts (Assume, labelled)

| Item | Source |
|---|---|
| Cost range per measure | `measures.csv` `cost_low` / `cost_high`, filled by us with a cited source or `is_assumption` |
| Discount per measure | `discounts.csv`; no public amounts, so an assumed percentage range, labelled |
| Rebuild cost per sq ft | assumption, labelled |

## 2. What the model does (B)

One model built by Atharva and David, with two outputs:

- **Wildfire analysis:** how exposed the home's tract is to wildfire. **Done (Atharva):** `relative_exposure_score_0_100` from `data/processed/tract_wildfire_features.parquet` (method in `docs/wildfire_methodology.md`), read by `src/msba_vibathon_2026/wildfire.py`. It is a relative index, not a probability; `p_fire_annual` is FEMA's annualized wildfire frequency for the tract, used only for expected-loss math. Ratings: 0 = No observed exposure; then Low / Moderate / High / Very High at the quartiles of positive scores (9, 29, 50).
- **House analysis:** how much damage that would do to this house, given its features. **Still a placeholder** (`house_impact()` in `assess_stub.py`).

The model team decides the method and features. For the app, only the contract below matters.

## 3. The contract

The model exposes one function. The app calls only this, so it can start with a stub that returns hard-coded output in the same shape.

```python
def assess(inputs: dict) -> dict: ...
```

`inputs`:

```json
{
  "address": "123 Example St, Altadena, CA 91001",
  "home": {
    "ROOFCONSTRUCTION": "Asphalt", "EAVES": "Unenclosed", "VENTSCREEN": "Mesh Screen > 1/8\"",
    "EXTERIORSIDING": "Wood", "WINDOWPANE": "Single Pane",
    "DECKPORCHONGRADE": "Wood", "DECKPORCHELEVATED": "No Deck/Porch",
    "PATIOCOVERCARPORT": "Combustible", "FENCEATTACHEDTOSTRUCTURE": "Combustible",
    "PROPANETANKDISTANCE": "Not Applicable", "UTILITYMISCSTRUCTUREDISTANCE": "<30'",
    "year_built": 1958, "living_area_sqft": 1800, "stories": 1
  },
  "measures_done": ["defensible_space"],
  "insurance": {
    "type": "fair_only", "annual_premium": 6200, "dwelling_limit": 900000, "deductible": 2500,
    "nonrenewed": true, "nonrenewed_date": "2025-03"
  },
  "budget": 15000
}
```

Unknown answers are sent as `"Unknown"` (home fields) or `null` (numbers).

`output`:

```json
{
  "current": {
    "area": { "...": "the area_context() dict, for display" },
    "wildfire": {
      "score": 73.2, "rating": "Very High", "level": "tract", "tract_geoid": "06037460101",
      "p_fire_annual": 0.02199,
      "components": { "very_high_hazard_pct": 51.7, "high_hazard_pct": 9.9, "burned_footprint_pct": 86.5,
                      "fires_since_2015": 1, "last_fire_year": 2025, "fema_expected_annual_loss": 2701245 }
    },
    "house": { "impact": 0.71, "rating": "High", "top_drivers": ["EAVES", "VENTSCREEN"] },
    "insurance_gap": [ { "gap": "FAIR Plan only, no theft or liability cover", "severity": "high" } ]
  },
  "future": {
    "fixes": [
      { "measure_id": "ember_resistant_vents", "name": "Ember- and fire-resistant vents",
        "cost_low": 500, "cost_high": 2000, "impact_after": 0.62,
        "est_annual_benefit": 450, "payback_years": 2.8, "within_budget": true,
        "why": "Unscreened or coarse vents let embers into the attic", "assumptions": ["cost", "discount"] }
    ],
    "plan_within_budget": ["ember_resistant_vents", "ember_zone_5ft"],
    "house_after_plan": { "impact": 0.48, "rating": "Moderate" }
  },
  "caveats": ["Data ends 2023, before the January 2025 fires", "..."]
}
```

The AI report (app side) only rewrites this output into plain language; it never adds numbers.

## 4. Open decisions

1. Who fills the cost and discount assumptions, and from which sources.
2. Whether the photo pre-fill makes the first demo, or comes after the model works.
