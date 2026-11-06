"""Download every raw dataset into data/raw/. Safe to re-run: existing files are skipped.

A source that needs a login, has moved, or refuses automated access is not worked
around. It is logged in data/raw/manifest.json as manual_required, and the run goes on.
"""
from __future__ import annotations

import re
import sys

import geopandas as gpd

from utils import (BlockedDownload, MANUAL, RAW, SESSION, add_file, download,
                   fetch_arcgis_layer, load_manifest, record)

CDI_PAGE = "https://www.insurance.ca.gov/01-consumers/200-wrr/DataAnalysisOnWildfiresAndInsurance.cfm"
CDI_UPLOAD = "https://www.insurance.ca.gov/01-consumers/200-wrr/upload/"
CDI_FILES = [
    "Residential-Property-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2015-2021.xlsx",
    "Residential-Insurance-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2020-2023.xlsx",
    "Number-of-Residential-Dwelling-Units-Insured-in-2022-FAIR-Plan-vs-Voluntary.pdf",
]
FAQ_URL = ("https://www.insurance.ca.gov/01-consumers/105-type/95-guides/03-res/upload/"
           "faq-safer-from-wildfire-regulation.pdf")

ARCGIS = "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/"
FHSZ_SRA = ARCGIS + "FHSZSRA_23_3/FeatureServer/0"
FHSZ_LRA = ARCGIS + "FHSALRA25_v1_All/FeatureServer/0"
PERIMETERS = ARCGIS + "California_Historic_Fire_Perimeters/FeatureServer/0"
DINS = ARCGIS + "POSTFIRE_MASTER_DATA_SHARE/FeatureServer/0"

WRC_PAGE = "https://wildfirerisk.org/download/"
NRI_SOURCE = "https://www.fema.gov (OpenFEMA NRI page)"
NRI_VERSION = "v1.20, December 2025"
ZILLOW_PAGE = "https://www.zillow.com/research/data/"
ZILLOW_CSV = ("https://files.zillowstatic.com/research/public_csvs/zhvi/"
              "Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv")
ZILLOW_RENT_CSV = "https://files.zillowstatic.com/research/public_csvs/zori/Zip_zori_uc_sfrcondomfr_sm_month.csv"
ZILLOW_RENT_DIR = "zillow_rent"  # separate from zillow/: 02_process reads the one CSV in that folder

ACS_YEAR = 2024
ACS_BASE = (f"https://www2.census.gov/programs-surveys/acs/summary_file/{ACS_YEAR}/"
            f"table-based-SF/data/5YRData/acsdt5y{ACS_YEAR}-")
ZCTA_COUNTY = "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt"
COUNTY_SHP = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_us_county_500k.zip"
PLACE_SHP = "https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_06_place_500k.zip"


def boundaries():
    for url in (COUNTY_SHP, PLACE_SHP):
        path = download(url, RAW / "boundaries" / url.rsplit("/", 1)[1])
        add_file("boundaries", url, path)


def la_bbox(pad_deg: float = 0.15) -> tuple[float, float, float, float]:
    """LA County bounding box, padded by more than the 10 km fire perimeter buffer."""
    counties = gpd.read_file(RAW / "boundaries" / "cb_2024_us_county_500k.zip")
    x0, y0, x1, y1 = counties[counties["GEOID"] == "06037"].total_bounds
    return (round(x0 - pad_deg, 4), round(y0 - pad_deg, 4), round(x1 + pad_deg, 4), round(y1 + pad_deg, 4))


def cdi():
    for name in CDI_FILES:
        add_file("cdi", CDI_UPLOAD + name, download(CDI_UPLOAD + name, RAW / "cdi" / name))
    record("cdi", source_page=CDI_PAGE)
    add_file("cdi_faq", FAQ_URL, download(FAQ_URL, RAW / "cdi" / "faq-safer-from-wildfire-regulation.pdf"))


def fhsz(bbox):
    for label, url in (("sra", FHSZ_SRA), ("lra", FHSZ_LRA)):
        add_file("fhsz", url, fetch_arcgis_layer(url, RAW / "fhsz" / f"fhsz_{label}_la_bbox.geojson", bbox=bbox, page_size=200))
    record("fhsz", source_page="https://gis.data.cnra.ca.gov/",
           version="SRA: FHSZSRA_23_3, adopted effective 2024-04-01. "
                   "LRA: FHSZLRA25_v1_All, State Fire Marshal map dated 2025-03-24.")


def perimeters(bbox):
    path = fetch_arcgis_layer(PERIMETERS, RAW / "perimeters" / "fire_perimeters_la_bbox.geojson",
                              where="YEAR_ >= 1950", bbox=bbox)
    add_file("perimeters", PERIMETERS, path)
    record("perimeters", source_page="https://data.ca.gov/dataset/california-fire-perimeters-all")


def wrc():
    existing = sorted((RAW / "wrc").glob("wrc_download_*.xlsx"))
    if existing:
        print(f"  skip (exists): {existing[-1].name}")
        return
    html = SESSION.get(WRC_PAGE, timeout=60)
    if html.status_code != 200:
        raise BlockedDownload(f"HTTP {html.status_code} from {WRC_PAGE}")
    links = re.findall(r'href="([^"]*wrc_download_\d+\.xlsx)"', html.text)
    if not links:
        raise BlockedDownload(f"No wrc_download_*.xlsx link found on {WRC_PAGE}")
    add_file("wrc", links[0], download(links[0], RAW / "wrc" / links[0].rsplit("/", 1)[1]))
    record("wrc", source_page=WRC_PAGE)


def nri():
    """NRI is supplied by hand: hazards.fema.gov refuses automated clients (HTTP 403)."""
    record("nri", source_page=NRI_SOURCE, version=NRI_VERSION)
    extracted = MANUAL / "NRI_Table_CensusTracts" / "NRI_Table_CensusTracts.csv"
    zips = sorted(MANUAL.glob("NRI_Table_CensusTracts*.zip"))
    if extracted.exists() or zips:
        add_file("nri", NRI_SOURCE, extracted if extracted.exists() else zips[0],
                 note="National census tract table and data dictionary, downloaded by hand from OpenFEMA.")
        return
    record("nri", status="manual_required", error="National NRI table not found in data/manual/.",
           manual_action="Download the census tract table from the OpenFEMA NRI page on https://www.fema.gov "
                         "and put it in data/manual/NRI_Table_CensusTracts/ (extracted) or data/manual/ (ZIP).")
    print("  MANUAL ACTION NEEDED: national NRI table not found in data/manual/")


def zillow():
    path = download(ZILLOW_CSV, RAW / "zillow" / ZILLOW_CSV.rsplit("/", 1)[1])
    add_file("zillow", ZILLOW_CSV, path,
             note=f"{ZILLOW_PAGE} refuses automated clients (HTTP 403). The CSV is the file Zillow "
                  "publishes on its public CDN, and the CDN serves it without any workaround.")
    record("zillow", source_page=ZILLOW_PAGE)


def zillow_rent():
    path = download(ZILLOW_RENT_CSV, RAW / ZILLOW_RENT_DIR / ZILLOW_RENT_CSV.rsplit("/", 1)[1])
    add_file("zillow_rent", ZILLOW_RENT_CSV, path,
             note=f"Zillow Observed Rent Index by ZIP. {ZILLOW_PAGE} refuses automated clients (HTTP 403). "
                  "The CSV is the file Zillow publishes on its public CDN.")
    record("zillow_rent", source_page=ZILLOW_PAGE)


def census():
    for table in ("b19013", "b25077", "b25003"):
        url = f"{ACS_BASE}{table}.dat"
        add_file("census", url, download(url, RAW / "census" / f"acsdt5y{ACS_YEAR}-{table}.dat"))
    add_file("census", ZCTA_COUNTY, download(ZCTA_COUNTY, RAW / "census" / ZCTA_COUNTY.rsplit("/", 1)[1]))
    record("census", source_page="https://www.census.gov/programs-surveys/acs/data/summary-file.html",
           vintage=f"ACS 5-year {ACS_YEAR - 4}-{ACS_YEAR}",
           note="The Census API now refuses keyless requests (redirects to missing_key.html). "
                "These are the same estimates from the Census Bureau's public table-based summary files.")


def dins():
    where = "INCIDENTNAME IN ('Eaton','Palisades') AND INCIDENTSTARTDATE >= DATE '2025-01-01'"
    path = fetch_arcgis_layer(DINS, RAW / "dins" / "dins_2025_eaton_palisades.geojson", where=where, page_size=1000)
    add_file("dins", DINS, path)
    record("dins", source_page="https://data.ca.gov/dataset/cal-fire-damage-inspection-dins-data")


def main() -> int:
    boundaries()
    bbox = la_bbox()
    steps = [("cdi", cdi), ("fhsz", lambda: fhsz(bbox)), ("perimeters", lambda: perimeters(bbox)),
             ("wrc", wrc), ("nri", nri), ("zillow", zillow), ("zillow_rent", zillow_rent), ("census", census), ("dins", dins)]
    for name, step in steps:
        print(f"[{name}]")
        try:
            step()
        except BlockedDownload as exc:
            record(name, status="manual_required", error=str(exc))
            print(f"  MANUAL ACTION NEEDED for {name}: {exc}")
        except Exception as exc:  # keep going so one source cannot stop the others
            record(name, status="failed", error=repr(exc))
            print(f"  FAILED {name}: {exc!r}")

    print("\nStatus:")
    manifest = load_manifest()
    for name, entry in manifest.items():
        print(f"  {name:12s} {entry.get('status')}  {entry.get('manual_action') or entry.get('error') or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
