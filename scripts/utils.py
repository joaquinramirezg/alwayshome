"""Shared helpers: paths, downloads, manifest, Census geocoder, area_context()."""
from __future__ import annotations

import json
import math
import re
import time
from datetime import date
from functools import lru_cache
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANUAL = ROOT / "data" / "manual"
PROCESSED = ROOT / "data" / "processed"
CACHE = ROOT / "data" / "cache"
DOCS = ROOT / "docs"
MANIFEST = RAW / "manifest.json"
PROCESS_LOG = PROCESSED / "_process_log.json"

LA_COUNTY_FIPS = "06037"
CRS_LATLON = "EPSG:4326"
CRS_METERS = "EPSG:3310"  # California Albers

# Identify the pipeline honestly. Never swap this for a browser user agent:
# a site that refuses this client goes in the report as a manual download.
USER_AGENT = "msba-vibathon-2026-data-pipeline/0.1 (UCLA hackathon research)"

SESSION = requests.Session()
SESSION.headers["User-Agent"] = USER_AGENT


class BlockedDownload(RuntimeError):
    """The source needs a login, has moved, or refuses automated access."""


# ---------------------------------------------------------------- manifest
def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}


def record(dataset: str, **fields) -> None:
    """Merge fields into a dataset's manifest entry."""
    manifest = load_manifest()
    manifest.setdefault(dataset, {}).update(fields)
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def add_file(dataset: str, url: str, path: Path, note: str | None = None) -> None:
    """Add one downloaded file to a dataset; keeps its original download date."""
    entry = load_manifest().get(dataset, {})
    files = entry.get("files", {})
    rel = str(path.relative_to(ROOT))
    if rel not in files:
        files[rel] = {"url": url, "downloaded": date.today().isoformat()}
    fields = {"files": files, "status": "ok", "manual_action": None, "error": None}
    if note:
        fields["note"] = note
    record(dataset, **fields)


# --------------------------------------------------------------- downloads
def download(url: str, dest: Path, timeout: int = 300) -> Path:
    """Stream url to dest. Skips if dest exists. Raises BlockedDownload on refusal."""
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  skip (exists): {dest.relative_to(ROOT)}")
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  GET {url}")
    with SESSION.get(url, stream=True, timeout=timeout, allow_redirects=True) as r:
        if r.status_code in (401, 403, 404, 407, 410, 429, 451):
            raise BlockedDownload(f"HTTP {r.status_code} from {url}")
        r.raise_for_status()
        if "login" in r.url.lower() or "missing_key" in r.url.lower():
            raise BlockedDownload(f"Redirected to {r.url}")
        tmp = dest.with_suffix(dest.suffix + ".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    tmp.rename(dest)
    print(f"  saved {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def arcgis_get(url: str, params: dict, retries: int = 4) -> dict:
    """GET an ArcGIS REST endpoint, retrying transient errors with backoff."""
    last = None
    for attempt in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=300)
            if r.status_code in (401, 403):
                raise BlockedDownload(f"HTTP {r.status_code} from {url}")
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise RuntimeError(f"ArcGIS error from {url}: {data['error']}")
            return data
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Giving up on {url}: {last}")


def fetch_arcgis_layer(layer_url: str, dest: Path, where: str = "1=1",
                       bbox: tuple[float, float, float, float] | None = None,
                       page_size: int = 500) -> Path:
    """Page a feature layer to a GeoJSON file in EPSG:4326, plus its field metadata."""
    meta_path = dest.with_name(dest.stem + "_layer_metadata.json")
    if not meta_path.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(json.dumps(arcgis_get(layer_url, {"f": "json"}), indent=1))
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  skip (exists): {dest.relative_to(ROOT)}")
        return dest

    params = {"where": where, "outFields": "*", "outSR": 4326, "f": "geojson",
              "orderByFields": "OBJECTID", "returnGeometry": "true"}
    if bbox:
        params |= {"geometry": ",".join(map(str, bbox)), "inSR": 4326,
                   "geometryType": "esriGeometryEnvelope",
                   "spatialRel": "esriSpatialRelIntersects"}
    count_params = {k: v for k, v in params.items() if k not in ("orderByFields", "outFields", "outSR", "returnGeometry")}
    expected = arcgis_get(layer_url + "/query", count_params | {"f": "json", "returnCountOnly": "true"})["count"]

    features, offset = [], 0
    while True:
        page = arcgis_get(layer_url + "/query", params | {"resultOffset": offset, "resultRecordCount": page_size})
        batch = page.get("features", [])
        features += batch
        offset += len(batch)
        print(f"  {dest.name}: {len(features)}/{expected}", end="\r", flush=True)
        if not batch or len(features) >= expected:
            break
    print()
    if len(features) != expected:
        raise RuntimeError(f"{dest.name}: got {len(features)} features, service reports {expected}")
    tmp = dest.with_suffix(".part")
    tmp.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    tmp.rename(dest)
    print(f"  saved {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:.1f} MB, {len(features)} features)")
    return dest


# ------------------------------------------------------------------ cleaning
def normalize_name(name: str | None) -> str | None:
    """Lowercase, strip punctuation, collapse whitespace (for name matching)."""
    if name is None or (isinstance(name, float) and math.isnan(name)):
        return None
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(name).lower())).strip()


# ------------------------------------------------------------------ geocoder
GEOCODE_CACHE = CACHE / "geocode_cache.json"
PLACE_LAYERS = ("Incorporated Places", "Census Designated Places")


def geocode(address: str) -> dict:
    """Geocode via Census "Find Geographies" (current benchmark and vintage).

    Returns lat, lon, matched_address, zip, tract_geoid (11 chars), county_fips
    (5 chars), place and place_geoid. Results are cached in data/cache/geocode_cache.json.
    Raises ValueError when the geocoder finds no match.

    Show users matched_address: the geocoder can return a near match ("200 N Spring St"
    came back as "200 S SPRING ST"), and its ZIP comes from TIGER address ranges, so it
    can differ from the postal ZIP.
    """
    import censusgeocode

    key = " ".join(address.lower().split())
    cache = json.loads(GEOCODE_CACHE.read_text()) if GEOCODE_CACHE.exists() else {}
    if key in cache:
        return cache[key]

    client = censusgeocode.CensusGeocode(benchmark="Public_AR_Current", vintage="Current_Current")
    matches = client.onelineaddress(address, returntype="geographies")
    if not matches:
        raise ValueError(f"Census geocoder found no match for address: {address!r}")

    best = matches[0]
    geos = best.get("geographies", {})
    tract = (geos.get("Census Tracts") or [{}])[0].get("GEOID")
    county = (geos.get("Counties") or [{}])[0].get("GEOID")
    place = next((geos[layer][0] for layer in PLACE_LAYERS if geos.get(layer)), {})
    result = {
        "lat": float(best["coordinates"]["y"]),
        "lon": float(best["coordinates"]["x"]),
        "matched_address": best["matchedAddress"],
        "zip": best.get("addressComponents", {}).get("zip"),
        "tract_geoid": str(tract).zfill(11) if tract else None,
        "county_fips": str(county).zfill(5) if county else None,
        "place": place.get("BASENAME"),
        "place_geoid": str(place["GEOID"]).zfill(7) if place.get("GEOID") else None,
    }
    cache[key] = result
    GEOCODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    GEOCODE_CACHE.write_text(json.dumps(cache, indent=2))
    return result


# -------------------------------------------------------------- area context
@lru_cache(maxsize=None)
def _table(name: str):
    """Load a processed table once; None if it has not been built."""
    import geopandas as gpd
    import pandas as pd
    import pyarrow.parquet as pq

    path = PROCESSED / f"{name}.parquet"
    if not path.exists():
        return None
    is_geo = b"geo" in (pq.read_schema(path).metadata or {})
    return gpd.read_parquet(path) if is_geo else pd.read_parquet(path)


HAZARD_ORDER = {"Very High": 3, "High": 2, "Moderate": 1}
ALL_CONTEXT_TABLES = ("hazard_zones", "fire_perimeters", "zip_insurance", "zip_fair_plan",
                      "nri_tracts", "zip_home_values_latest", "zip_zcta", "zcta_census",
                      "wrc_communities")


def _scalar(value):
    """numpy/pandas scalar to plain Python, with missing values as None."""
    import pandas as pd

    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return None
    return value.item() if hasattr(value, "item") else value


def area_context(address: str) -> dict:
    """Geocode address and gather hazard, fire, insurance, value and income context.

    A value that is unavailable is None, never estimated. `missing_tables` names
    processed files that have not been built (for example NRI awaiting a manual
    download), so callers can tell "no data for this place" from "table absent".
    """
    import geopandas as gpd
    from shapely.geometry import Point

    geo = geocode(address)
    point = Point(geo["lon"], geo["lat"])
    ctx = {"address": address, "geocode": geo}
    ctx["missing_tables"] = [t for t in ALL_CONTEXT_TABLES if _table(t) is None]

    zones = _table("hazard_zones")
    if zones is not None:
        hits = zones.iloc[list(zones.sindex.query(point, predicate="intersects"))]
        classes = sorted(set(hits["hazard_class"]), key=lambda c: -HAZARD_ORDER.get(c, 0))
        ctx["hazard_class"] = classes[0] if classes else None
        ctx["hazard_responsibility_area"] = (
            hits.loc[hits["hazard_class"] == classes[0], "responsibility_area"].iloc[0] if classes else None
        )

    fires = _table("fire_perimeters")
    if fires is not None:
        here = gpd.GeoSeries([point], crs=CRS_LATLON).to_crs(CRS_METERS).iloc[0]
        metric = _metric_fires()
        idx = metric.sindex.query(here.buffer(5000), predicate="intersects")
        near = metric.iloc[idx]
        rows = [{"fire_name": _scalar(fires.loc[i, "fire_name"]), "year": _scalar(fires.loc[i, "year"]),
                 "distance_km": round(g.distance(here) / 1000, 2)} for i, g in near.items()]
        ctx["fires_within_5km"] = sorted(rows, key=lambda r: (-(r["year"] or 0), r["distance_km"]))

    zip_code = geo["zip"]
    insurance = _table("zip_insurance")
    if insurance is not None:
        trend = insurance[insurance["zip"] == zip_code].sort_values("year")
        ctx["zip_insurance_trend"] = [
            {k: _scalar(row[k]) for k in ("year", "new", "renewed", "nonrenewed_total", "nonrenewal_rate")}
            for _, row in trend.iterrows()
        ]

    fair = _table("zip_fair_plan")
    if fair is not None:
        row = fair[fair["zip"] == zip_code]
        ctx["fair_plan_share"] = _scalar(row["fair_plan_share"].iloc[0]) if len(row) else None
        ctx["fair_plan_data_year"] = _scalar(row["data_year"].iloc[0]) if len(row) else None

    nri = _table("nri_tracts")
    if nri is not None:
        row = nri[nri["tract_geoid"] == geo["tract_geoid"]]
        ctx["tract_wildfire_eal"] = _scalar(row["WFIR_EALT"].iloc[0]) if len(row) and "WFIR_EALT" in row else None
    else:
        ctx["tract_wildfire_eal"] = None

    values = _table("zip_home_values_latest")
    if values is not None:
        row = values[values["zip"] == zip_code]
        ctx["zip_home_value"] = _scalar(row["zhvi_latest"].iloc[0]) if len(row) else None
        ctx["zip_home_value_5yr_change"] = _scalar(row["zhvi_5yr_change"].iloc[0]) if len(row) else None

    xwalk, census = _table("zip_zcta"), _table("zcta_census")
    ctx["zcta_median_income"] = None
    if xwalk is not None and census is not None:
        match = xwalk.loc[xwalk["zip"] == zip_code, "zcta"]
        if len(match) and match.iloc[0] is not None:
            row = census[census["zcta"] == match.iloc[0]]
            ctx["zcta_median_income"] = _scalar(row["median_household_income"].iloc[0]) if len(row) else None

    wrc = _table("wrc_communities")
    ctx["wrc_community"] = None
    if wrc is not None and geo["place_geoid"]:
        rows = wrc[(wrc["geo_level"] == "community") & (wrc["geoid"] == geo["place_geoid"])]
        if len(rows):
            r = rows.iloc[0]
            ctx["wrc_community"] = {k: _scalar(r[k]) for k in (
                "community", "risk_to_homes_pctile_state", "risk_to_homes_pctile_national",
                "wildfire_likelihood_pctile_state", "wildfire_likelihood_pctile_national")}
    return ctx


@lru_cache(maxsize=1)
def _metric_fires():
    """Fire perimeter geometries projected to meters, indexed like fire_perimeters."""
    return _table("fire_perimeters").geometry.to_crs(CRS_METERS)
