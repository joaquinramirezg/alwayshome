"""Train the house-damage model on CAL FIRE damage inspections (DINS), Eaton and Palisades fires 2025.

Question it answers: if a wildfire reaches this house, how likely is it to be destroyed,
given the features the homeowner reports? Output: data/processed/house_model.json (small,
read by src/msba_vibathon_2026/house.py; no scikit-learn needed at runtime).

Choices (see docs/house_model.md):
- Residential structures with an assessed outcome only (81 inaccessible rows dropped).
- Features: the 8 checklist fields, one-hot, plus a fire x ZIP location fixed effect (controls for
  neighborhood fire intensity); predictions average over locations, weighted by homes.
- "Unknown" leaks the label (inspectors often can't assess a destroyed home), so it gets its own
  dummy during training to absorb that leakage, and is NEVER used at prediction time: a homeowner's
  "I don't know" is scored as the average over the known answers, weighted by how common they are.
- Post-fire fields (where the fire started, defensive actions, damage counts) are excluded.
- Logistic regression with L2; 5-fold cross-validated AUC is reported. Associations, not causes.

Run: uv run python scripts/train_house_model.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.metrics import roc_auc_score, brier_score_loss

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "house_model.json"
FIELDS = ["ROOFCONSTRUCTION", "EAVES", "VENTSCREEN", "EXTERIORSIDING", "WINDOWPANE",
          "DECKPORCHELEVATED", "FENCEATTACHEDTOSTRUCTURE", "UTILITYMISCSTRUCTUREDISTANCE"]
RESIDENTIAL = {"Single Residence", "Multiple Residence", "Mixed Commercial/Residential"}


def main() -> None:
    cols = ["STRUCTURECATEGORY", "damage_assessed", "destroyed", "fire", "ZIPCODE"] + [f + "_clean" for f in FIELDS]
    d = pd.read_parquet(ROOT / "data" / "processed" / "dins_2025_la.parquet", columns=cols)
    d = d[d["STRUCTURECATEGORY"].isin(RESIDENTIAL) & d["damage_assessed"]].copy()
    d.columns = [c.removesuffix("_clean") for c in d.columns]

    # Location fixed effect (ZIP within each fire) absorbs neighborhood differences in fire intensity
    # and building age, so the house features compare homes that faced similar fire conditions.
    d["loc"] = d["fire"].astype(str) + ":" + d["ZIPCODE"].fillna("na").astype(str)
    X = pd.get_dummies(d[FIELDS + ["loc"]].astype(str), prefix_sep="=", dtype=float)
    y = d["destroyed"].astype(int).to_numpy()
    model = LogisticRegression(C=1.0, max_iter=2000)

    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    p_cv = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
    known = (d[FIELDS] != "Unknown").all(axis=1).to_numpy()
    metrics = {
        "rows": int(len(d)), "destroyed_share": round(float(y.mean()), 3),
        "cv_auc_all": round(float(roc_auc_score(y, p_cv)), 3),
        "cv_auc_rows_without_unknown": round(float(roc_auc_score(y[known], p_cv[known])), 3),
        "rows_without_unknown": int(known.sum()),
        "cv_brier_all": round(float(brier_score_loss(y, p_cv)), 3),
    }
    model.fit(X, y)

    coefs = dict(zip(X.columns, model.coef_[0]))
    out = {"intercept": float(model.intercept_[0]), "fields": {}, "fire_effects": {}, "frequencies": {}}
    for col, c in coefs.items():
        field, value = col.split("=", 1)
        if field == "loc":
            out["fire_effects"][value] = float(c)
        else:
            out["fields"].setdefault(field, {})[value] = round(float(c), 5)
    for f in FIELDS:  # frequency of each known answer, for scoring "I don't know"
        vc = d.loc[d[f] != "Unknown", f].value_counts(normalize=True)
        out["frequencies"][f] = {k: round(float(v), 5) for k, v in vc.items()}
    fires = d["loc"].value_counts(normalize=True)
    out["fire_weight"] = {k: round(float(v), 4) for k, v in fires.items()}
    out["metrics"] = metrics
    out["trained_on"] = str(date.today())
    out["source"] = "CAL FIRE DINS, Eaton and Palisades fires, January 2025 (data/processed/dins_2025_la.parquet)"
    OUT.write_text(json.dumps(out, indent=1, sort_keys=True))
    print(json.dumps(metrics, indent=1))
    for f in FIELDS:
        print(f, {k: round(v, 2) for k, v in sorted(out["fields"][f].items(), key=lambda kv: kv[1])})


if __name__ == "__main__":
    main()
