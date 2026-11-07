"""Monthly rent by ZIP, from the preloaded Zillow rent table. No network calls."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

RENT_PATH = Path(__file__).resolve().parents[3] / "data" / "processed" / "zip_rent_latest.parquet"
RENT_SOURCE_URL = "https://www.zillow.com/research/data/"


@lru_cache(maxsize=1)
def _rents() -> dict[str, float]:
    """Read the table once. A missing table means no rent data, not a crash."""
    if not RENT_PATH.exists():
        return {}
    df = pd.read_parquet(RENT_PATH, columns=["zip", "rent_latest"])
    return dict(zip(df["zip"], df["rent_latest"].astype(float)))


def monthly_rent(zip: str) -> float | None:
    """Latest typical monthly rent for a 5-digit ZIP, or None if the ZIP has no data."""
    return _rents().get(zip)
