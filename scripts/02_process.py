"""Clean raw downloads into data/processed/. Re-runnable; each step fails on its own.

Usage: python scripts/02_process.py [step ...]     (default: every step)
"""
from __future__ import annotations

import csv
import json
import re
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pdfplumber
from shapely import make_valid

from utils import (CRS_LATLON, CRS_METERS, LA_COUNTY_FIPS, MANUAL, PROCESS_LOG, PROCESSED,
                   RAW, normalize_name)

LOG: dict[str, dict] = {}
FAQ_URL = ("https://www.insurance.ca.gov/01-consumers/105-type/95-guides/03-res/upload/"
           "faq-safer-from-wildfire-regulation.pdf")


def note(step: str, **fields) -> None:
    LOG.setdefault(step, {}).update(fields)


def to_num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype("string").str.replace(",", "").str.strip(), errors="coerce")


def la_county_polygon(buffer_m: float = 0):
    """LA County as one shapely geometry in EPSG:3310."""
    counties = gpd.read_file(RAW / "boundaries" / "cb_2024_us_county_500k.zip")
    geom = counties[counties["GEOID"] == LA_COUNTY_FIPS].to_crs(CRS_METERS).union_all()
    return geom.buffer(buffer_m) if buffer_m else geom


def la_zips() -> set[str]:
    """ZIPs with any address in an LA County tract, from the HUD crosswalk."""
    return set(pd.read_parquet(PROCESSED / "zip_tract_crosswalk.parquet", columns=["zip"])["zip"])


def fix_geometries(gdf: gpd.GeoDataFrame, polygons_only: bool = False) -> tuple[gpd.GeoDataFrame, int]:
    """make_valid wherever needed; returns the frame and how many rows were repaired."""
    invalid = ~gdf.geometry.is_valid
    n = int(invalid.sum())
    if n:
        gdf.loc[invalid, gdf.geometry.name] = make_valid(gdf.geometry[invalid].values)
    if polygons_only:
        gdf = gdf.explode(index_parts=False)
        gdf = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
    return gdf[~gdf.geometry.is_empty & gdf.geometry.notna()], n


# ------------------------------------------------------------------ 9. HUD
def crosswalks():
    zt = pd.read_excel(MANUAL / "ZIP-TRACT_062026.xlsx", dtype=str)
    # In ZIP-TRACT, `zip` is the ZIP and `geoid` the tract.
    zt = zt.rename(columns={"geoid": "tract_geoid"})
    tz = pd.read_excel(MANUAL / "TRACT-ZIP_062026.xlsx", dtype=str)
    # In TRACT-ZIP the meanings flip: `tract` is the tract and `geoid` the ZIP.
    tz = tz.rename(columns={"tract": "tract_geoid", "geoid": "zip"})

    summary = {}
    for name, df, group, out, order in (
        ("zip_tract", zt, "zip", "zip_tract_crosswalk", ["zip", "tract_geoid"]),
        ("tract_zip", tz, "tract_geoid", "tract_zip_crosswalk", ["tract_geoid", "zip"]),
    ):
        df["zip"] = df["zip"].str.strip().str.zfill(5)
        df["tract_geoid"] = df["tract_geoid"].str.strip().str.zfill(11)
        for col in ("res_ratio", "bus_ratio", "oth_ratio", "tot_ratio"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        national = df.groupby(group)["res_ratio"].sum()
        la = df[df["tract_geoid"].str.startswith(LA_COUNTY_FIPS)].copy()
        la = la[order + ["res_ratio", "tot_ratio"]].sort_values(order)
        la.to_parquet(PROCESSED / f"{out}.parquet", index=False)
        summary[name] = {"rows_national": len(df), "rows_la": len(la), "keys_la": int(la[group].nunique()),
                         "national_res_sum_min": float(national.min()), "national_res_sum_max": float(national.max())}
    note("crosswalks", **summary)


# ------------------------------------------------------------------- 1. CDI
def cdi_policies():
    raw = RAW / "cdi"
    frames = []
    for path in sorted(raw.glob("*by-ZIP*.xlsx")):
        df = pd.read_excel(path, dtype=str)
        df = df.rename(columns=lambda c: re.sub(r"[^a-z]", "", c.lower()))
        df = df.rename(columns={"zipcode": "zip", "insuredinitiatednonrenewed": "nonrenewed_insured",
                                "insurerinitiatednonrenewed": "nonrenewed_insurer", "nonrenewed": "nonrenewed_total"})
        df["source_file"] = path.name
        frames.append(df)
    # Sorted by name: "Residential-Insurance" (2020-23) first, then "Residential-Property" (2015-21).
    newer = next(f for f in frames if "nonrenewed_total" in f.columns)
    older = next(f for f in frames if "nonrenewed_insurer" in f.columns)

    for df in (newer, older):
        df["zip"] = df["zip"].str.strip().str.zfill(5)
        df["year"] = to_num(df["year"]).astype("Int64")
        df["county"] = df["county"].str.strip().replace("", pd.NA)
        for col in ("new", "renewed", "nonrenewed_total", "nonrenewed_insured", "nonrenewed_insurer"):
            if col in df:
                df[col] = to_num(df[col]).astype("Int64")
    older["nonrenewed_total"] = older["nonrenewed_insured"] + older["nonrenewed_insurer"]

    # Measure how far the two publications disagree on the years they share.
    both = older.merge(newer, on=["zip", "year"], suffixes=("_old", "_new"))
    both = both.groupby("year")[["new_old", "new_new", "renewed_old", "renewed_new", "nonrenewed_total_old", "nonrenewed_total_new"]].sum()
    note("cdi_policies", overlap_statewide={str(k): {c: int(v) for c, v in r.items()} for k, r in both.iterrows()})

    # The newer publication wins where both report a ZIP-year. It keeps 2020-23 on one
    # method, and the older file's split columns stay attached where available.
    split = older[["zip", "year", "nonrenewed_insurer", "nonrenewed_insured"]]
    merged = newer.merge(split, on=["zip", "year"], how="left")
    extra = older.merge(newer[["zip", "year"]], on=["zip", "year"], how="left", indicator=True)
    extra = extra[extra["_merge"] == "left_only"].drop(columns="_merge")
    out = pd.concat([merged, extra], ignore_index=True)

    denom = (out["new"] + out["renewed"] + out["nonrenewed_total"]).astype("Float64")
    out["nonrenewal_rate"] = (out["nonrenewed_total"].astype("Float64") / denom.replace(0, pd.NA))

    scope = la_zips()
    statewide_rows = len(out)
    out = out[(out["county"] == "Los Angeles") | out["zip"].isin(scope)]
    cols = ["zip", "year", "county", "new", "renewed", "nonrenewed_insurer", "nonrenewed_insured",
            "nonrenewed_total", "nonrenewal_rate", "source_file"]
    out = out[cols].sort_values(["zip", "year"])
    out.to_parquet(PROCESSED / "zip_insurance.parquet", index=False)
    note("cdi_policies", rows_statewide=statewide_rows, rows_la=len(out))


NUM_TOKEN = re.compile(r"^(\d{1,3}(,\d{3})*|-)$")


def split_fair_counts(tokens: list[str], pct: float) -> tuple[float, float] | None:
    """Rebuild two counts from PDF tokens, where some numbers extract as "1 0,249".

    Accepts a split only if both parts are well formed and reproduce the printed
    percentage, so an ambiguous line stays empty instead of getting a guessed value.
    """
    fits = []
    for i in range(1, len(tokens)):
        left, right = "".join(tokens[:i]), "".join(tokens[i:])
        if NUM_TOKEN.match(left) and NUM_TOKEN.match(right):
            vol = 0.0 if left == "-" else float(left.replace(",", ""))
            fair = 0.0 if right == "-" else float(right.replace(",", ""))
            total = vol + fair
            if total and abs(100 * fair / total - pct) <= 0.06 or (not total and pct == 0):
                fits.append((vol, fair))
    return fits[0] if len(fits) == 1 else None


def cdi_fair_plan():
    path = RAW / "cdi" / "Number-of-Residential-Dwelling-Units-Insured-in-2022-FAIR-Plan-vs-Voluntary.pdf"
    line_re = re.compile(r"^(?P<county>[A-Z][A-Z .'\-]*?) (?P<zip>\d{5}) (?P<city>.*?) ?(?P<nums>(?:[\d,]+ |- )+)(?P<pct>[\d.]+)%$")
    rows, unparsed, unsplit = [], [], 0
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                m = line_re.match(line.strip())
                if not m:
                    if re.search(r"\d{5}", line) and "%" in line:
                        unparsed.append(line)
                    continue
                pct = float(m["pct"])
                counts = split_fair_counts(m["nums"].split(), pct)
                unsplit += counts is None
                rows.append({"zip": m["zip"], "county": m["county"].strip().title(), "city": m["city"].strip(),
                             "dwelling_units_voluntary": counts[0] if counts else np.nan,
                             "dwelling_units_fair": counts[1] if counts else np.nan,
                             "fair_plan_share": round(pct / 100, 4), "data_year": 2022})
    df = pd.DataFrame(rows)
    statewide = len(df)
    scope = la_zips()
    df = df[(df["county"] == "Los Angeles") | df["zip"].isin(scope)].drop_duplicates(["zip", "county"])
    # A ZIP listed under several counties keeps its LA row.
    df = df.sort_values("county", key=lambda s: s != "Los Angeles").drop_duplicates("zip").sort_values("zip")
    df = df[["zip", "fair_plan_share", "data_year", "county", "city", "dwelling_units_voluntary", "dwelling_units_fair"]]
    df.to_parquet(PROCESSED / "zip_fair_plan.parquet", index=False)
    note("cdi_fair_plan", rows_statewide=statewide, rows_la=len(df), unparsed_lines=unparsed[:20],
         n_unparsed=len(unparsed), lines_with_unresolved_counts=int(unsplit))


# ---------------------------------------------------------------- 2. hazard
def hazard_zones():
    la = la_county_polygon()
    frames = [gpd.read_file(RAW / "fhsz" / f"fhsz_{x}_la_bbox.geojson") for x in ("sra", "lra")]
    gdf = pd.concat(frames, ignore_index=True)
    counts = gdf.groupby(["SRA", "FHSZ_Description"]).size()
    # "NonWildland" (FHSZ = -3) is the LRA layer's label for land with no severity class.
    gdf = gdf[gdf["FHSZ_Description"].isin(["Moderate", "High", "Very High"])]
    gdf = gdf.rename(columns={"FHSZ_Description": "hazard_class", "SRA": "responsibility_area"})
    gdf = gdf[["hazard_class", "responsibility_area", "geometry"]].to_crs(CRS_METERS)
    gdf, _ = fix_geometries(gdf)
    gdf = gpd.clip(gdf, la)
    gdf["geometry"] = gdf.geometry.simplify(5, preserve_topology=True)
    gdf, repaired_m = fix_geometries(gdf, polygons_only=True)
    gdf = gdf.to_crs(CRS_LATLON)
    gdf, repaired_ll = fix_geometries(gdf, polygons_only=True)
    gdf = gdf.reset_index(drop=True)
    gdf.to_parquet(PROCESSED / "hazard_zones.parquet", index=False)
    note("hazard_zones", raw_counts_in_bbox={" / ".join(k): int(v) for k, v in counts.items()},
         nonwildland_dropped=int(counts.xs("NonWildland", level=1).sum()) if "NonWildland" in counts.index.get_level_values(1) else 0,
         rows=len(gdf), repaired_after_simplify=repaired_m, repaired_after_reproject=repaired_ll,
         rows_by_class={" / ".join(k): int(v) for k, v in gdf.groupby(["responsibility_area", "hazard_class"]).size().items()})


# ------------------------------------------------------------- 3. perimeters
def fire_perimeters():
    gdf = gpd.read_file(RAW / "perimeters" / "fire_perimeters_la_bbox.geojson")
    meta = json.loads((RAW / "perimeters" / "fire_perimeters_la_bbox_layer_metadata.json").read_text())
    domain = next((f.get("domain") for f in meta["fields"] if f["name"] == "CAUSE"), None) or {}
    codes = {c["code"]: c["name"] for c in domain.get("codedValues", [])}
    note("fire_perimeters", rows_in_bbox=len(gdf), cause_domain_found=bool(codes))

    area = la_county_polygon(buffer_m=10_000)
    gdf = gdf.to_crs(CRS_METERS)
    gdf, _ = fix_geometries(gdf)
    gdf = gdf[gdf.intersects(area)]
    gdf = gdf[to_num(gdf["YEAR_"]) >= 1950]

    alarm = gdf["ALARM_DATE"]
    alarm_dt = (pd.to_datetime(to_num(alarm), unit="ms", utc=True) if pd.api.types.is_numeric_dtype(alarm)
                else pd.to_datetime(alarm, utc=True, errors="coerce"))
    out = gpd.GeoDataFrame({
        "fire_name": gdf["FIRE_NAME"].astype("string").str.strip().replace("", pd.NA),
        "year": to_num(gdf["YEAR_"]).astype("Int64"),
        "alarm_date": alarm_dt.dt.tz_localize(None),
        "acres": to_num(gdf["GIS_ACRES"]).astype("Float64"),
        "cause": to_num(gdf["CAUSE"]).map(codes).astype("string") if codes else gdf["CAUSE"].astype("string"),
        "geometry": gdf.geometry,
    }, crs=CRS_METERS).to_crs(CRS_LATLON)
    out, repaired = fix_geometries(out)
    out = out.reset_index(drop=True)
    out.to_parquet(PROCESSED / "fire_perimeters.parquet", index=False)
    note("fire_perimeters", rows=len(out), repaired=repaired, year_min=int(out["year"].min()), year_max=int(out["year"].max()))


# ------------------------------------------------------------------- 4. WRC
def wrc_communities():
    path = next((RAW / "wrc").glob("wrc_download_*.xlsx"))
    frames = []
    for sheet, level, width in (("Communities", "community", 7), ("Counties", "county", 5)):
        df = pd.read_excel(path, sheet_name=sheet, dtype={"GEOID": str, "STATEFP": str, "COUNTYFP": str, "PLACEFP": str})
        df = df[df["STUSPS"] == "CA"].copy()
        df["geoid"] = df["GEOID"].str.strip().str.zfill(width)
        df["geo_level"] = level
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["community"] = df["NAME"].str.replace(r",\s*CA$", "", regex=True).str.strip()
    # WRC disambiguates some names as "Burbank (Los Angeles)"; the county column holds that.
    df["name_normalized"] = df["community"].str.replace(r"\s*\([^)]*\)$", "", regex=True).map(normalize_name)

    # The spreadsheet names no county for a community, so take the county holding
    # most of the Census place's area.
    places = gpd.read_file(RAW / "boundaries" / "cb_2024_06_place_500k.zip")[["GEOID", "geometry"]].to_crs(CRS_METERS)
    counties = gpd.read_file(RAW / "boundaries" / "cb_2024_us_county_500k.zip")
    counties = counties[counties["STATEFP"] == "06"][["NAME", "geometry"]].rename(columns={"NAME": "county_name"}).to_crs(CRS_METERS)
    overlay = gpd.overlay(places, counties, how="intersection", keep_geom_type=True)
    overlay["a"] = overlay.area
    place_county = overlay.sort_values("a", ascending=False).drop_duplicates("GEOID").set_index("GEOID")["county_name"]
    df["county"] = df["geoid"].map(place_county)
    is_county = df["geo_level"] == "county"
    df.loc[is_county, "county"] = df.loc[is_county, "community"].str.replace(r"\s+County$", "", regex=True)

    out = df.rename(columns={
        "RISK_STATE_RANK": "risk_to_homes_pctile_state", "RISK_NATIONAL_RANK": "risk_to_homes_pctile_national",
        "BP_STATE_RANK": "wildfire_likelihood_pctile_state", "BP_NATIONAL_RANK": "wildfire_likelihood_pctile_national",
        "TOTAL_BUILDINGS": "total_buildings", "BUILDINGS_FRACTION_ME": "buildings_share_minimal_exposure",
        "BUILDINGS_FRACTION_IE": "buildings_share_indirect_exposure", "BUILDINGS_FRACTION_DE": "buildings_share_direct_exposure",
        "INSUFFICIENT_DATA": "insufficient_data"})
    # This release publishes percentiles only, so the raw values stay empty.
    out["risk_to_homes"] = np.nan
    out["wildfire_likelihood"] = np.nan
    cols = ["geoid", "geo_level", "community", "name_normalized", "county", "risk_to_homes", "risk_to_homes_pctile_state",
            "risk_to_homes_pctile_national", "wildfire_likelihood", "wildfire_likelihood_pctile_state",
            "wildfire_likelihood_pctile_national", "total_buildings", "buildings_share_minimal_exposure",
            "buildings_share_indirect_exposure", "buildings_share_direct_exposure", "insufficient_data"]
    out[cols].sort_values(["geo_level", "community"]).to_parquet(PROCESSED / "wrc_communities.parquet", index=False)
    note("wrc_communities", rows=len(out), source=path.name,
         communities_without_county=int(out.loc[~is_county, "county"].isna().sum()))


# ------------------------------------------------------------------- 5. NRI
NRI_TABLE = "NRI_Table_CensusTracts.csv"
NRI_DICTIONARY = "NRIDataDictionary.csv"
NRI_LAYERS = ("National Risk Index", "Social Vulnerability", "Community Resilience", "Wildfire")
NRI_ID_COLUMNS = ["STATEFIPS", "COUNTYFIPS", "TRACTFIPS", "COUNTY", "POPULATION", "BUILDVALUE", "AREA"]


def _nri_open(name: str, manual_dir: Path):
    """Open an NRI file from the extracted folder, or from a national ZIP in data/manual/."""
    folder = manual_dir / "NRI_Table_CensusTracts" / name
    if folder.exists():
        return open(folder, "rb")
    zips = sorted(manual_dir.glob("NRI_Table_CensusTracts*.zip"))
    if not zips:
        raise FileNotFoundError(name)
    archive = zipfile.ZipFile(zips[0])
    member = next(n for n in archive.namelist() if n.rsplit("/", 1)[-1] == name)
    return archive.open(member)


def nri_tracts(manual_dir: Path = MANUAL, out_dir: Path = PROCESSED):
    """Filter FEMA's national tract table to LA County, with columns chosen from its data dictionary."""
    try:
        with _nri_open(NRI_DICTIONARY, manual_dir) as f:
            dictionary = pd.read_csv(f, dtype=str, encoding="utf-8-sig")
        with _nri_open(NRI_TABLE, manual_dir) as f:
            header = pd.read_csv(f, dtype=str, encoding="utf-8-sig", nrows=0).columns
    except FileNotFoundError:
        (out_dir / "nri_tracts.parquet").unlink(missing_ok=True)
        note("nri_tracts", status="skipped", reason="source file not available; see manifest for the manual download")
        return

    chosen = dictionary[dictionary["Relevant Layer"].isin(NRI_LAYERS)]
    fields = [f for f in chosen["Field Name"] if f not in NRI_ID_COLUMNS]
    absent = sorted(set(fields + NRI_ID_COLUMNS) - set(header))
    if absent:
        raise ValueError(f"NRI table lacks fields named in its dictionary: {absent}")

    keep = NRI_ID_COLUMNS + fields
    with _nri_open(NRI_TABLE, manual_dir) as f:
        national = pd.read_csv(f, dtype=str, encoding="utf-8-sig", usecols=keep)
    df = national[(national["STATEFIPS"].str.zfill(2) == LA_COUNTY_FIPS[:2])
                  & (national["COUNTYFIPS"].str.zfill(3) == LA_COUNTY_FIPS[2:])].copy()
    df["tract_geoid"] = df["TRACTFIPS"].str.strip().str.zfill(11)

    # The dictionary's Type column decides which fields are numeric.
    types = dictionary.set_index("Field Name")["Type"]
    for col in keep:
        if types.get(col) in ("Double", "Integer"):
            df[col] = pd.to_numeric(df[col], errors="coerce")

    out = df[["tract_geoid", "COUNTY", "POPULATION", "BUILDVALUE", "AREA"] + fields].sort_values("tract_geoid")
    out.to_parquet(out_dir / "nri_tracts.parquet", index=False)
    versions = sorted(set(dictionary["Version"].dropna() + " (" + dictionary["Version Date"].dropna() + ")"))
    note("nri_tracts", status="ok", rows_national=len(national), rows=len(out), dictionary_version=versions,
         fields_by_layer={k: int(v) for k, v in chosen["Relevant Layer"].value_counts().items()},
         wildfire_eal_field="WFIR_EALT", wildfire_eal_alias=dictionary.set_index("Field Name")["Field Alias"].get("WFIR_EALT"))


# ---------------------------------------------------------------- 6. Zillow
def zillow():
    path = next((RAW / "zillow").glob("*.csv"))
    id_cols = ["RegionID", "SizeRank", "RegionName", "RegionType", "StateName", "State", "City", "Metro", "CountyName"]
    df = pd.read_csv(path, dtype={c: str for c in id_cols})
    df["zip"] = df["RegionName"].str.strip().str.zfill(5)
    scope = la_zips()
    df = df[(df["State"] == "CA") & ((df["CountyName"] == "Los Angeles County") | df["zip"].isin(scope))]
    long = df.melt(id_vars="zip", value_vars=[c for c in df.columns if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c)],
                   var_name="date", value_name="zhvi").dropna(subset=["zhvi"])
    long["date"] = pd.to_datetime(long["date"])
    long = long.sort_values(["zip", "date"])
    long[["zip", "date", "zhvi"]].to_parquet(PROCESSED / "zip_home_values.parquet", index=False)

    latest = long.groupby("zip").tail(1).rename(columns={"zhvi": "zhvi_latest", "date": "latest_date"})
    latest["past"] = latest["latest_date"] - pd.DateOffset(years=5) + pd.offsets.MonthEnd(0)
    past = long.rename(columns={"zhvi": "zhvi_past", "date": "past"})
    latest = latest.merge(past, on=["zip", "past"], how="left")
    latest["zhvi_5yr_change"] = latest["zhvi_latest"] / latest["zhvi_past"] - 1
    latest[["zip", "zhvi_latest", "zhvi_5yr_change", "latest_date"]].to_parquet(PROCESSED / "zip_home_values_latest.parquet", index=False)
    note("zillow", rows_long=len(long), zips=int(long["zip"].nunique()), latest_date=str(long["date"].max().date()),
         zips_without_5yr=int(latest["zhvi_5yr_change"].isna().sum()))


def zillow_rent():
    path = next((RAW / "zillow_rent").glob("*.csv"))
    id_cols = ["RegionID", "SizeRank", "RegionName", "RegionType", "StateName", "State", "City", "Metro", "CountyName"]
    df = pd.read_csv(path, dtype={c: str for c in id_cols})
    df["zip"] = df["RegionName"].str.strip().str.zfill(5)
    scope = la_zips()
    df = df[(df["State"] == "CA") & ((df["CountyName"] == "Los Angeles County") | df["zip"].isin(scope))]
    long = df.melt(id_vars="zip", value_vars=[c for c in df.columns if re.fullmatch(r"\d{4}-\d{2}-\d{2}", c)],
                   var_name="latest_date", value_name="rent_latest").dropna(subset=["rent_latest"])
    long["latest_date"] = pd.to_datetime(long["latest_date"])
    long["rent_latest"] = long["rent_latest"].astype(float)
    latest = long.sort_values(["zip", "latest_date"]).groupby("zip").tail(1)
    latest[["zip", "rent_latest", "latest_date"]].to_parquet(PROCESSED / "zip_rent_latest.parquet", index=False)
    note("zillow_rent", zips=len(latest), latest_date=str(latest["latest_date"].max().date()),
         zips_not_at_latest_date=int((latest["latest_date"] < latest["latest_date"].max()).sum()))


# ---------------------------------------------------------------- 7. Census
def census():
    tables = {
        "b19013": {"B19013_E001": "median_household_income", "B19013_M001": "median_household_income_moe"},
        "b25077": {"B25077_E001": "median_home_value", "B25077_M001": "median_home_value_moe"},
        "b25003": {"B25003_E001": "occupied_units", "B25003_M001": "occupied_units_moe",
                  "B25003_E002": "owner_occupied_units", "B25003_M002": "owner_occupied_units_moe"},
    }
    rel = pd.read_csv(next((RAW / "census").glob("tab20_zcta520_county20*")), sep="|", dtype=str)
    rel = rel.dropna(subset=["GEOID_ZCTA5_20"])
    ca = set(rel.loc[rel["GEOID_COUNTY_20"].str.startswith("06"), "GEOID_ZCTA5_20"])
    la = set(rel.loc[rel["GEOID_COUNTY_20"] == LA_COUNTY_FIPS, "GEOID_ZCTA5_20"])

    out, sentinels = None, {}
    for table, columns in tables.items():
        path = next((RAW / "census").glob(f"acsdt5y*-{table}.dat"))
        keep = []
        for chunk in pd.read_csv(path, sep="|", dtype=str, chunksize=500_000):
            keep.append(chunk[chunk["GEO_ID"].str.startswith("860Z200US")])
        df = pd.concat(keep)
        df["zcta"] = df["GEO_ID"].str[-5:]
        df = df[df["zcta"].isin(ca)][["zcta"] + list(columns)].rename(columns=columns)
        for col in columns.values():
            values = to_num(df[col])
            # ACS jam values such as -666666666 mark "not available", so negatives become null.
            sentinels[col] = int((values < 0).sum())
            df[col] = values.mask(values < 0)
        out = df if out is None else out.merge(df, on="zcta", how="outer")
    out["in_la_county"] = out["zcta"].isin(la)
    vintage = re.search(r"acsdt5y(\d{4})", path.name).group(1)
    out["acs_vintage"] = f"{int(vintage) - 4}-{vintage}"
    out.sort_values("zcta").to_parquet(PROCESSED / "zcta_census.parquet", index=False)
    note("census", rows=len(out), la_zctas=int(out["in_la_county"].sum()), sentinels_nulled=sentinels, vintage=out["acs_vintage"].iloc[0])


# ------------------------------------------------------------------ 8. DINS
RESIDENTIAL = ["Single Residence", "Multiple Residence", "Mixed Commercial/Residential"]
DINS_ATTRS = ["ROOFCONSTRUCTION", "EAVES", "VENTSCREEN", "EXTERIORSIDING", "WINDOWPANE", "DECKPORCHONGRADE",
              "DECKPORCHELEVATED", "PATIOCOVERCARPORT", "FENCEATTACHEDTOSTRUCTURE", "PROPANETANKDISTANCE",
              "UTILITYMISCSTRUCTUREDISTANCE", "WHEREFIRESTARTEDONSTRUCTURE", "WHATDIDFIRESTARTFROM",
              "DEFENSIVEACTIONS", "STRUCTURETYPE", "STRUCTURECATEGORY"]
MISSING_TOKENS = {"", "unknown", "unk", "none", "null", "nan"}


def dins_domains() -> dict[str, dict[str, str]]:
    """Per field, map each lowercased code and label in the DINS data dictionary to one clean label."""
    meta = json.loads((RAW / "dins" / "dins_2025_eaton_palisades_layer_metadata.json").read_text())
    domains = {}
    for field in meta["fields"]:
        values = (field.get("domain") or {}).get("codedValues")
        if not values:
            continue
        mapping = {}
        for item in values:
            label = re.sub(r"\s*(- Describe.*|\(If used.*\))$", "", item["name"]).strip()
            mapping[str(item["code"]).strip().lower()] = label
            mapping[str(item["name"]).strip().lower()] = label
        domains[field["name"]] = mapping
    return domains


def clean_category(series: pd.Series, domain: dict[str, str] | None = None) -> tuple[pd.Series, dict[str, int]]:
    """Standardize one DINS attribute. Returns clean values and any out-of-domain values.

    Blanks and unknown tokens become "Unknown". A value outside the field's domain
    (such as "Asphalt" under WINDOWPANE, an entry in the wrong field) also becomes
    "Unknown", and is counted for the report.
    """
    domain = domain or {}
    rejected: dict[str, int] = {}

    def fix(value):
        if value is None or value is pd.NA or (isinstance(value, float) and np.isnan(value)):
            return "Unknown"
        text = re.sub(r"\s+", " ", str(value)).strip()
        key = text.lower()
        if key in domain:
            return domain[key]
        if key in MISSING_TOKENS:
            return "Unknown"
        if domain:
            rejected[text] = rejected.get(text, 0) + 1
            return "Unknown"
        return text

    return series.map(fix).astype("string"), rejected


def dins():
    gdf = gpd.read_file(RAW / "dins" / "dins_2025_eaton_palisades.geojson")
    total = len(gdf)
    all_counts = gdf.groupby(["INCIDENTNAME", "DAMAGE"]).size()
    gdf = gdf[gdf["STRUCTURECATEGORY"].isin(RESIDENTIAL)].copy()
    note("dins", rows_all_structures=total, rows_residential=len(gdf), attributes_cleaned=DINS_ATTRS,
         all_counts={" / ".join(k): int(v) for k, v in all_counts.items()},
         raw_field_names=[c for c in gdf.columns if c != "geometry"])

    gdf["destroyed"] = (gdf["DAMAGE"] == "Destroyed (>50%)").astype(int)
    gdf["damage_assessed"] = gdf["DAMAGE"] != "Inaccessible"
    gdf["fire"] = gdf["INCIDENTNAME"].str.strip().str.title()
    domains, rejected = dins_domains(), {}
    for col in DINS_ATTRS:
        gdf[col + "_clean"], bad = clean_category(gdf[col], domains.get(col))
        if bad:
            rejected[col] = bad
    for col in ("CITY", "COMMUNITY", "STREETNAME", "SITEADDRESS"):
        gdf[col] = gdf[col].astype("string").str.strip()
    note("dins", out_of_domain_values_set_to_unknown=rejected)

    year = to_num(gdf["YEARBUILT"])
    gdf["year_built_clean"] = year.where(year.between(1800, 2025)).astype("Float64")
    gdf["ZIPCODE"] = to_num(gdf["ZIPCODE"]).astype("Int64").astype("string").str.zfill(5)

    date_col = gdf["INCIDENTSTARTDATE"]
    gdf["INCIDENTSTARTDATE"] = (pd.to_datetime(date_col, unit="ms", utc=True) if pd.api.types.is_numeric_dtype(date_col)
                                else pd.to_datetime(date_col, utc=True, errors="coerce")).dt.tz_localize(None)

    no_geom = int((gdf.geometry.isna() | gdf.geometry.is_empty).sum())
    gdf = gdf.set_crs(CRS_LATLON, allow_override=True).reset_index(drop=True)
    gdf.to_parquet(PROCESSED / "dins_2025_la.parquet", index=False)
    note("dins", rows=len(gdf), missing_geometry=no_geom, year_built_outside_range=int((year.notna() & ~year.between(1800, 2025)).sum()))


# ------------------------------------------------------------ 10. ZIP->ZCTA
def zip_zcta():
    zctas = set(pd.read_parquet(PROCESSED / "zcta_census.parquet", columns=["zcta"])["zcta"])
    universe = set(la_zips())
    sources = {"zip_insurance": "zip", "zip_fair_plan": "zip", "zip_home_values_latest": "zip"}
    for table, col in sources.items():
        path = PROCESSED / f"{table}.parquet"
        if path.exists():
            universe |= set(pd.read_parquet(path, columns=[col])[col])
    df = pd.DataFrame({"zip": sorted(universe)})
    df["has_matching_zcta"] = df["zip"].isin(zctas)
    df["zcta"] = df["zip"].where(df["has_matching_zcta"], None)
    df["method"] = "assumed ZIP = ZCTA"
    df[["zip", "zcta", "has_matching_zcta", "method"]].to_parquet(PROCESSED / "zip_zcta.parquet", index=False)
    note("zip_zcta", rows=len(df), zips_without_zcta=sorted(df.loc[~df["has_matching_zcta"], "zip"]))


# ------------------------------------------------------------- C. templates
# Names quoted from the "Do more, save more" list in the CDI FAQ (September 2026).
# The PDF's text layer drops "fi" ligatures, restored here. All else is left blank.
FAQ_MEASURES = [
    ("class_a_roof", "Class A fire-rated roof"),
    ("ember_zone_5ft", "5-foot ember-resistant zone around the structure"),
    ("noncombustible_6in_walls", "Noncombustible 6 inches at the bottom of walls"),
    ("ember_resistant_vents", "Ember- and fire-resistant vents"),
    ("double_pane_or_shutters", "Double pane windows or added shutters"),
    ("enclosed_eaves", "Enclosed eaves"),
    ("clear_under_decks", "Cleared vegetation and debris from under decks"),
    ("outbuildings_30ft", "Move sheds and outbuildings at least 30 feet away"),
    ("defensible_space", "Trim trees and remove brush in compliance with state and local defensible space laws"),
    ("firewise_usa", "Neighborhoods can form a Firewise USA community"),
    ("fire_risk_reduction_community", "Cities, counties, and local districts can become certified as a Fire Risk Reduction Community"),
]


def templates():
    """Write the hand-filled CSV templates. Never overwrites an existing file."""
    columns = {
        "measures.csv": ["measure_id", "name", "description", "category", "cost_low", "cost_high",
                         "certifications", "dins_feature", "source_url"],
        "discounts.csv": ["insurer", "measure_id", "discount_pct", "effective_date", "source_url"],
        "grants.csv": ["grant_id", "name", "covers_measures", "max_amount", "income_limit", "status", "source_url"],
    }
    written, kept = [], []
    for name, header in columns.items():
        path = PROCESSED / name
        if path.exists():
            kept.append(name)
            continue
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            if name == "measures.csv":
                for measure_id, measure in FAQ_MEASURES:
                    writer.writerow([measure_id, measure, "", "", "", "", "", "", FAQ_URL])
        written.append(name)
    note("templates", written=written, kept_existing=kept)


STEPS = {"crosswalks": crosswalks, "cdi_policies": cdi_policies, "cdi_fair_plan": cdi_fair_plan,
         "hazard_zones": hazard_zones, "fire_perimeters": fire_perimeters, "wrc_communities": wrc_communities,
         "nri_tracts": nri_tracts, "zillow": zillow, "zillow_rent": zillow_rent, "census": census, "dins": dins,
         "zip_zcta": zip_zcta, "templates": templates}


def main(argv: list[str]) -> int:
    global LOG
    PROCESSED.mkdir(parents=True, exist_ok=True)
    LOG = json.loads(PROCESS_LOG.read_text()) if PROCESS_LOG.exists() else {}
    failed = []
    for name in argv or STEPS:
        print(f"[{name}]")
        LOG[name] = {}
        try:
            STEPS[name]()
            LOG[name].setdefault("status", "ok")
        except Exception as exc:  # one broken dataset must not block the rest
            LOG[name] |= {"status": "failed", "error": repr(exc)}
            failed.append(name)
            print(f"  FAILED: {exc!r}")
        print(f"  {json.dumps({k: v for k, v in LOG[name].items() if k not in ('raw_field_names', 'all_counts')}, default=str)[:900]}")
        PROCESS_LOG.write_text(json.dumps(LOG, indent=2, default=str))
    print("Failed steps:", failed or "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
