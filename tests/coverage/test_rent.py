"""Step 2: the ZORI pipeline step, the processed rent table, and monthly_rent()."""
import importlib
import sys
from pathlib import Path

import pandas as pd
import pytest

from msba_vibathon_2026.coverage import rent

ROOT = Path(__file__).resolve().parents[2]
RENT_TABLE = ROOT / "data/processed/zip_rent_latest.parquet"
CROSSWALK = ROOT / "data/processed/zip_tract_crosswalk.parquet"


def load_script(name: str):
    sys.path.insert(0, str(ROOT / "scripts"))
    return importlib.import_module(name)


@pytest.fixture
def rent_file(tmp_path, monkeypatch):
    path = tmp_path / "zip_rent_latest.parquet"
    pd.DataFrame({
        "zip": ["91001", "90272"],
        "rent_latest": [3200.5, 6100.0],
        "latest_date": pd.to_datetime(["2026-09-30", "2026-09-30"]),
    }).to_parquet(path, index=False)
    monkeypatch.setattr(rent, "RENT_PATH", path)
    rent._rents.cache_clear()
    yield path
    rent._rents.cache_clear()


# ---------------------------------------------------------------- monthly_rent
def test_monthly_rent_returns_the_zip_rent(rent_file):
    assert rent.monthly_rent("91001") == 3200.5


def test_monthly_rent_returns_a_plain_float(rent_file):
    assert type(rent.monthly_rent("90272")) is float


def test_monthly_rent_is_none_for_a_zip_without_data(rent_file):
    assert rent.monthly_rent("00000") is None


def test_monthly_rent_is_none_when_the_table_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(rent, "RENT_PATH", tmp_path / "absent.parquet")
    rent._rents.cache_clear()
    assert rent.monthly_rent("91001") is None
    rent._rents.cache_clear()


def test_the_table_is_read_only_once(rent_file):
    rent.monthly_rent("91001")
    rent_file.unlink()
    assert rent.monthly_rent("90272") == 6100.0


# --------------------------------------------------------------- pipeline step
def test_pipeline_step_keeps_la_zips_and_their_latest_non_empty_rent(tmp_path, monkeypatch):
    process = load_script("02_process")
    raw_dir = tmp_path / "raw" / "zillow_rent"
    raw_dir.mkdir(parents=True)
    pd.DataFrame({
        "RegionID": ["1", "2", "3", "4"], "SizeRank": ["1", "2", "3", "4"],
        "RegionName": ["91001", "90272", "10001", "96001"],
        "RegionType": ["zip"] * 4, "StateName": ["CA", "CA", "NY", "CA"], "State": ["CA", "CA", "NY", "CA"],
        "City": ["Altadena", "Los Angeles", "New York", "Redding"], "Metro": ["LA", "LA", "NY", "Redding"],
        "CountyName": ["Los Angeles County", "Other", "New York County", "Shasta County"],
        "2026-08-31": [3000.0, 6000.0, 4000.0, 1500.0],
        "2026-09-30": [3100.0, None, 4100.0, 1600.0],
    }).to_csv(raw_dir / "zori.csv", index=False)
    monkeypatch.setattr(process, "RAW", tmp_path / "raw")
    monkeypatch.setattr(process, "PROCESSED", tmp_path)
    monkeypatch.setattr(process, "la_zips", lambda: {"90272"})

    process.zillow_rent()

    out = pd.read_parquet(tmp_path / "zip_rent_latest.parquet").set_index("zip")
    assert sorted(out.index) == ["90272", "91001"]
    assert out.loc["91001", "rent_latest"] == 3100.0
    assert out.loc["90272", "rent_latest"] == 6000.0
    assert out.loc["90272", "latest_date"] == pd.Timestamp("2026-08-31")


def test_rent_download_does_not_share_the_home_value_folder():
    download = load_script("01_download")
    assert download.ZILLOW_RENT_DIR != "zillow"
    assert "/zori/" in download.ZILLOW_RENT_CSV


# ----------------------------------------------------------- the real table
def test_real_table_has_the_planned_columns():
    assert list(pd.read_parquet(RENT_TABLE).columns) == ["zip", "rent_latest", "latest_date"]


def test_real_table_has_one_clean_row_per_zip():
    df = pd.read_parquet(RENT_TABLE)
    assert len(df) > 0
    assert df["zip"].str.fullmatch(r"\d{5}").all()
    assert df["zip"].is_unique
    assert df.notna().all().all()
    assert pd.api.types.is_float_dtype(df["rent_latest"])
    assert (df["rent_latest"] > 0).all()


def test_real_table_is_la_county_only():
    df = pd.read_parquet(RENT_TABLE)
    scope = set(pd.read_parquet(CROSSWALK, columns=["zip"])["zip"])
    assert set(df["zip"]) <= scope
