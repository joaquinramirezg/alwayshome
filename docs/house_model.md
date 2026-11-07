# House-damage model

**Question:** if a wildfire reaches this house, how likely is it to be destroyed, given what the homeowner reports?

- **Data:** CAL FIRE damage inspections (DINS) for the January 2025 Eaton and Palisades fires: 22,071 residential structures with an assessed outcome, 52.9% destroyed (`data/processed/dins_2025_la.parquet`).
- **Model:** logistic regression (L2) on the 8 checklist answers, one-hot, plus a fire x ZIP location effect that compares homes facing similar fire conditions. Training: `uv run python scripts/train_house_model.py` → `data/processed/house_model.json` (coefficients only; the app needs no ML library).
- **Accuracy (5-fold cross-validation):** AUC 0.80 on the 4,525 homes with every feature recorded (the honest figure). AUC on all rows is 0.95 but inflated, because "Unknown" is recorded far more often for destroyed homes.
- **Leakage handling:** "Unknown" gets its own dummy in training so it absorbs that leakage, and is never used for predictions. A homeowner's "I don't know" is scored as the frequency-weighted average of the known answers. Post-fire fields are excluded.
- **Prediction:** averaged over the 2025 fire locations, weighted by homes: "a home like yours in those fires".

## What the data say (coefficients, higher = more likely destroyed)

| Feature | Direction |
|---|---|
| Roof | Wood far worst; tile best among common roofs |
| Eaves | Unenclosed worse than enclosed |
| Vents | Coarse mesh worse than fine (1/8") mesh |
| Windows | Single pane worse than multi pane |
| Sheds / outbuildings | Under 30 ft worst |
| Siding, attached fence | Opposite of expectations (likely inspection bias: siding is only visible on homes that survived) |

## How fixes are valued

- Fix = switch one answer to its hardened value (`HARDENED` in `src/msba_vibathon_2026/house.py`) and re-score. Badge in the app: **backed by 2025 fire data**.
- Where the data show no reduction (siding for the 6-inch noncombustible base, attached fence for the 5-foot zone), no damage reduction is claimed: **no measured effect; discount only**.
- Not recorded in the inspections: defensible space (assumed 10% relative reduction) and clearing under decks (5%): **effect assumed**.
- More fixes never increase the estimate (tested).

## Limits

Associations from two fires in one county, not causal effects; not an inspection of the home; the fire location effect is averaged, so neighborhood exposure comes from the separate wildfire score. Expected yearly loss = FEMA yearly wildfire frequency for the tract x this chance x rebuild cost.
