"""Validate data/processed/ and write docs/validation_report.md. Failed checks are reported, not fixed."""
from __future__ import annotations

import json
from datetime import date

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

from utils import (DOCS, LA_COUNTY_FIPS, MANUAL, PROCESS_LOG, PROCESSED, ROOT,
                   area_context, load_manifest)

TEST_ADDRESSES = {
    "Altadena (Altadena Library)": "600 E Mariposa St, Altadena, CA 91001",
    "Pacific Palisades (Palisades Library)": "861 Alma Real Dr, Pacific Palisades, CA 90272",
    "Downtown LA (Central Library)": "630 W 5th St, Los Angeles, CA 90071",
}
HAZARD_POINTS = {
    "central Altadena": (-118.1312, 34.1897, True),
    "Pacific Palisades": (-118.5259, 34.0469, True),
    "downtown LA": (-118.2437, 34.0522, False),
}
CDI_EXPECTED = {"91001": 0.075, "90272": 0.083}
SIZE_LIMIT_MB = 50

DATASETS = [  # file, manifest key, key columns
    ("zip_insurance", "cdi", ["zip", "year"]),
    ("zip_fair_plan", "cdi", ["zip"]),
    ("hazard_zones", "fhsz", ["hazard_class", "responsibility_area"]),
    ("fire_perimeters", "perimeters", ["fire_name", "year", "alarm_date"]),
    ("wrc_communities", "wrc", ["geoid", "community", "county"]),
    ("nri_tracts", "nri", ["tract_geoid"]),
    ("zip_home_values", "zillow", ["zip", "date"]),
    ("zip_home_values_latest", "zillow", ["zip"]),
    ("zcta_census", "census", ["zcta"]),
    ("dins_2025_la", "dins", ["GLOBALID", "DAMAGE", "destroyed"]),
    ("zip_tract_crosswalk", "hud", ["zip", "tract_geoid"]),
    ("tract_zip_crosswalk", "hud", ["tract_geoid", "zip"]),
    ("zip_zcta", "zip_zcta", ["zip"]),
]
DUPLICATE_KEYS = {
    "zip_insurance": ["zip", "year"], "zip_fair_plan": ["zip"], "wrc_communities": ["geoid"],
    "nri_tracts": ["tract_geoid"], "zip_home_values": ["zip", "date"], "zip_home_values_latest": ["zip"],
    "zcta_census": ["zcta"], "dins_2025_la": ["GLOBALID"], "zip_tract_crosswalk": ["zip", "tract_geoid"],
    "tract_zip_crosswalk": ["tract_geoid", "zip"], "zip_zcta": ["zip"],
}
ZIP_COLUMNS = {"zip_insurance": "zip", "zip_fair_plan": "zip", "zip_home_values": "zip", "zip_home_values_latest": "zip",
               "zip_tract_crosswalk": "zip", "tract_zip_crosswalk": "zip", "zip_zcta": "zip", "zcta_census": "zcta"}
TRACT_COLUMNS = {"zip_tract_crosswalk": "tract_geoid", "tract_zip_crosswalk": "tract_geoid", "nri_tracts": "tract_geoid"}
GEO_TABLES = ["hazard_zones", "fire_perimeters", "dins_2025_la"]

lines: list[str] = []
tally = {"PASS": 0, "FAIL": 0, "WARN": 0, "SKIP": 0}
failures: list[str] = []


def out(text: str = "") -> None:
    lines.append(text)


def check(status: str, text: str) -> None:
    tally[status] += 1
    if status in ("FAIL", "WARN"):
        failures.append(f"**{status}:** {text}")
    out(f"- **{status}** {text}")


def passfail(ok: bool, text: str, on_false: str = "FAIL") -> None:
    check("PASS" if ok else on_false, text)


def load(name: str):
    path = PROCESSED / f"{name}.parquet"
    if not path.exists():
        return None
    return gpd.read_parquet(path) if name in GEO_TABLES else pd.read_parquet(path)


def table(df: pd.DataFrame) -> str:
    """Render a DataFrame as a Markdown table."""
    rows = [" | ".join(map(str, df.columns))] + [" | ".join(["---"] * df.shape[1])]
    rows += [" | ".join("" if pd.isna(v) else str(v) for v in row) for row in df.itertuples(index=False)]
    return "\n".join(f"| {r} |" for r in rows)


def details(summary: str, items) -> None:
    items = list(items)
    out(f"<details><summary>{summary} ({len(items)})</summary>\n\n{', '.join(map(str, items)) or 'none'}\n\n</details>\n")


def overview(tables: dict, manifest: dict) -> None:
    out("## 1. Datasets\n")
    for name, key, key_cols in DATASETS:
        df = tables.get(name)
        out(f"### `{name}`\n")
        entry = manifest.get(key, {})
        if key == "hud":
            out("- Source: HUD USPS crosswalks supplied by hand in `data/manual/` (2026 Q2, 2020 Census geographies)\n"
                "- Download date: not recorded in the files (file timestamp 2026-11-06)")
        elif key == "zip_zcta":
            out("- Source: derived from `zcta_census` and the ZIP tables; assumes ZIP = ZCTA")
        else:
            files = entry.get("files", {})
            out(f"- Source page: {entry.get('source_page', 'n/a')}")
            for path, info in files.items():
                out(f"- File: `{path}`\n  - URL: {info['url']}\n  - Downloaded: {info['downloaded']}")
            if entry.get("version") or entry.get("vintage"):
                out(f"- Version: {entry.get('version') or entry.get('vintage')}")
            if entry.get("note"):
                out(f"- Note: {entry['note']}")
        if df is None:
            out(f"- **Not built.** Status: `{entry.get('status')}`. {entry.get('error') or ''}")
            if entry.get("manual_action"):
                out(f"- **Manual action:** {entry['manual_action']}")
            out()
            continue
        out(f"- Rows: {len(df):,}")
        out(f"- Columns ({df.shape[1]}): " + ", ".join(f"`{c}`" for c in df.columns if c != "geometry"))
        nulls = {c: int(df[c].isna().sum()) for c in key_cols if c in df}
        out("- Nulls in key columns: " + ", ".join(f"`{c}` {n:,}" for c, n in nulls.items()) + "\n")


def structural(tables: dict) -> None:
    out("## 2. Structural checks\n")
    for name, col in ZIP_COLUMNS.items():
        if (df := tables.get(name)) is not None:
            bad = df[col][~df[col].astype("string").str.fullmatch(r"\d{5}")]
            passfail(bad.empty, f"`{name}.{col}`: all 5-character strings ({len(bad)} bad).")
    for name, col in TRACT_COLUMNS.items():
        if (df := tables.get(name)) is not None:
            bad = df[col][~df[col].astype("string").str.fullmatch(LA_COUNTY_FIPS + r"\d{6}")]
            passfail(bad.empty, f"`{name}.{col}`: all 11-character strings starting 06037 ({len(bad)} bad).")
        else:
            check("SKIP", f"`{name}` not built, so its tract IDs were not checked.")
    for name, keys in DUPLICATE_KEYS.items():
        if (df := tables.get(name)) is not None:
            n = int(df.duplicated(keys).sum())
            passfail(n == 0, f"`{name}`: no duplicate {'+'.join(keys)} ({n} found).")
    for name in GEO_TABLES:
        if (df := tables.get(name)) is not None:
            invalid = int((~df.geometry.is_valid).sum())
            passfail(invalid == 0 and df.crs.to_epsg() == 4326,
                     f"`{name}`: geometries valid ({invalid} invalid) in EPSG:{df.crs.to_epsg()}.")
    out()


def crosswalk_ratios(tables: dict) -> None:
    out("## 3. Crosswalk ratio checks\n")
    for label, path, rename, group in (
        ("ZIP-TRACT", "ZIP-TRACT_062026.xlsx", {"geoid": "tract"}, "zip"),
        ("TRACT-ZIP", "TRACT-ZIP_062026.xlsx", {"geoid": "zip"}, "tract"),
    ):
        df = pd.read_excel(MANUAL / path, dtype=str).rename(columns=rename)
        df["res_ratio"] = pd.to_numeric(df["res_ratio"])
        total = df.groupby(group)["res_ratio"].sum()
        off = total[(total - 1).abs() > 0.01]
        zero = off[off == 0]
        out(f"**{label}, national:** {len(total):,} keys. {len(off):,} do not sum to 1 within 0.01, "
            f"and {len(zero):,} of those sum to exactly 0 (no residential addresses, such as PO Box or business-only ZIPs).\n")
        passfail((len(off) - len(zero)) == 0, f"{label}: every key with residential addresses sums to about 1 "
                 f"({len(off) - len(zero)} exceptions).", on_false="WARN")
        if label == "ZIP-TRACT":
            la = df[df["tract"].str.startswith(LA_COUNTY_FIPS)].groupby("zip")["res_ratio"].sum()
            whole = total.reindex(la.index)
            partial = la[(la < 0.99) & (whole > 0.99)].sort_values()
            out(f"\n{len(la):,} ZIPs touch an LA County tract. {(whole == 0).sum()} have no residential addresses at all. "
                f"{len(partial)} cross the county line, keeping less than 99% of their residential addresses in LA:\n")
            out(table(partial.round(4).rename("res_ratio_in_la").reset_index()) + "\n")
        else:
            la = df[df["tract"].str.startswith(LA_COUNTY_FIPS)].groupby("tract")["res_ratio"].sum()
            off_la = la[(la - 1).abs() > 0.01]
            out(f"\n{len(la):,} LA tracts. {len(off_la)} do not sum to about 1"
                f"{': ' + ', '.join(off_la.index) if len(off_la) else ''}.\n")
    out()


def coverage(tables: dict) -> None:
    out("## 4. Cross-dataset coverage (reported, not failed)\n")
    sets = {
        "CDI policies": set(tables["zip_insurance"]["zip"]) if tables.get("zip_insurance") is not None else set(),
        "CDI FAIR Plan": set(tables["zip_fair_plan"]["zip"]) if tables.get("zip_fair_plan") is not None else set(),
        "Zillow": set(tables["zip_home_values_latest"]["zip"]) if tables.get("zip_home_values_latest") is not None else set(),
        "Census ZCTA": set(tables["zcta_census"]["zcta"]) if tables.get("zcta_census") is not None else set(),
        "HUD crosswalk": set(tables["zip_tract_crosswalk"]["zip"]) if tables.get("zip_tract_crosswalk") is not None else set(),
    }
    xw = tables["zip_tract_crosswalk"]
    residential = set(xw.groupby("zip")["res_ratio"].sum().loc[lambda s: s > 0].index)
    universe = set().union(*sets.values()) - (sets["Census ZCTA"] - sets["HUD crosswalk"] - sets["CDI policies"] - sets["Zillow"] - sets["CDI FAIR Plan"])
    out(f"LA ZIP universe: {len(universe)} ZIPs in any ZIP table, {len(residential)} of them with residential addresses in LA County.\n")
    rows = [{"table": k, "ZIPs in universe": len(v & universe), "missing, all": len(universe - v),
             "missing, residential in LA": len(residential - v)} for k, v in sets.items()]
    out(table(pd.DataFrame(rows)) + "\n")
    for name, zips in sets.items():
        details(f"Residential LA ZIPs missing from {name}", sorted(residential - zips))
    details("ZIPs with no matching ZCTA, flagged in zip_zcta", sorted(tables["zip_zcta"].query("~has_matching_zcta")["zip"]))

    if tables.get("zip_insurance") is not None:
        by_year = tables["zip_insurance"].groupby("year")["zip"].nunique()
        out("CDI ZIPs per year: " + ", ".join(f"{y}: {n}" for y, n in by_year.items()) + "\n")

    tz = tables["tract_zip_crosswalk"]
    tracts = set(tz["tract_geoid"])
    out(f"Crosswalk tracts: {len(tracts):,} in TRACT-ZIP and {xw['tract_geoid'].nunique():,} in ZIP-TRACT.\n")
    passfail(tracts == set(xw["tract_geoid"]), "Both crosswalks list the same LA tracts.", on_false="WARN")
    if tables.get("nri_tracts") is not None:
        nri = set(tables["nri_tracts"]["tract_geoid"])
        out(f"**NRI versus crosswalk tracts:** {len(nri):,} LA tracts in NRI, {len(tracts):,} in the crosswalks, "
            f"{len(nri & tracts):,} match. {len(nri - tracts)} are in NRI only and {len(tracts - nri)} in the crosswalks only.\n")
        details("NRI tracts missing from the crosswalks", sorted(nri - tracts))
        details("Crosswalk tracts missing from NRI", sorted(tracts - nri))
        passfail(nri == tracts, f"NRI and the crosswalks list the same tracts ({len(nri & tracts):,} shared; "
                 f"NRI only: {', '.join(sorted(nri - tracts)) or 'none'}; crosswalks only: {', '.join(sorted(tracts - nri)) or 'none'}).", on_false="WARN")
    else:
        check("SKIP", "NRI versus crosswalk tracts: NRI awaits a manual download.")
    out()


def sanity(tables: dict) -> None:
    out("## 5. Sanity checks against known facts\n")
    out("### CDI non-renewal rate, 2023\n")
    ins = tables.get("zip_insurance")
    if ins is not None:
        for zip_code, expected in CDI_EXPECTED.items():
            got = float(ins[(ins["zip"] == zip_code) & (ins["year"] == 2023)]["nonrenewal_rate"].iloc[0])
            passfail(abs(got - expected) <= 0.003, f"ZIP {zip_code}: {got:.2%}, expected about {expected:.1%}.")
        out("\nMethod: `nonrenewed_total / (new + renewed + nonrenewed_total)`. Other denominators miss the "
            "published figures (for 91001: 8.0% on renewed + non-renewed, 8.7% on renewed alone).\n")

    out("### Fire perimeters\n")
    fires = tables.get("fire_perimeters")
    if fires is not None:
        for name in ("EATON", "PALISADES"):
            hit = fires[fires["year"].eq(2025).fillna(False) & fires["fire_name"].eq(name).fillna(False)]
            acres = f"{hit['acres'].sum():,.0f} acres" if len(hit) else "no rows"
            passfail(len(hit) > 0, f"2025 {name} fire present: {acres}.")
        nameless = int(fires["fire_name"].isna().sum())
        check("WARN", f"{nameless:,} of {len(fires):,} perimeters ({nameless / len(fires):.0%}) have no fire name, "
                      f"and {int(fires['alarm_date'].isna().sum())} have no alarm date. Left empty as published.")

    out("\n### Hazard zones\n")
    zones = tables.get("hazard_zones")
    if zones is not None:
        for label, (lon, lat, should_hit) in HAZARD_POINTS.items():
            hits = sorted(set(zones[zones.intersects(Point(lon, lat))]["hazard_class"]))
            shown = ", ".join(hits) or "outside any zone"
            ok = bool(set(hits) & {"High", "Very High"}) if should_hit else not hits
            passfail(ok, f"{label} ({lat}, {lon}): {shown}.")
        out("\nCentral Altadena check: the point sits in land the LRA map labels `NonWildland`, confirmed by querying "
            "CAL FIRE's live service. That is the official map, not a processing error. Zones start about 450 m away: "
            "Lake Ave at Loma Alta Dr (34.1985, -118.1312) is High, and the foothills above are Very High. "
            "`NonWildland` is dropped because it has no severity class, so `hazard_class` is null there.\n")

    out("### DINS\n")
    dins = tables.get("dins_2025_la")
    if dins is not None:
        counts = pd.crosstab(dins["fire"], dins["DAMAGE"], margins=True, margins_name="Total").reset_index()
        out(table(counts) + "\n")
        for fire, n in dins[dins["destroyed"] == 1].groupby("fire").size().items():
            passfail(n >= 1000, f"{fire}: {n:,} destroyed residential structures.")
        dins_detail(dins, zones)

    out("### NRI\n")
    nri = tables.get("nri_tracts")
    if nri is None:
        check("SKIP", "NRI wildfire expected annual loss: table awaits a manual download.")
    else:
        eal = pd.to_numeric(nri["WFIR_EALT"], errors="coerce")
        passfail((eal.dropna() >= 0).all(), f"WFIR_EALT is non-negative (min {eal.min():,.0f}).")
        passfail(eal.notna().mean() > 0.9, f"WFIR_EALT present for {eal.notna().mean():.1%} of tracts.")
        zero = int((eal == 0).sum())
        check("WARN", f"WFIR_EALT is exactly 0 for {zero:,} of {len(nri):,} LA tracts ({zero / len(nri):.0%}), rated "
                      f"`No Expected Annual Losses`. It varies sharply within ZIPs: the Altadena test tract is "
                      f"about $17 a year, while 91001 also has tracts rated Very High.")
        constant = [c for c in ("RESL_SCORE", "RESL_RATNG", "RESL_SPCTL", "RESL_VALUE") if nri[c].nunique(dropna=False) == 1]
        if constant:
            check("WARN", f"{', '.join(constant)} have one value across all LA tracts, because FEMA publishes resilience "
                          "at county level. They cannot separate tracts here.")
        empty = [c for c in nri.columns if nri[c].isna().all()]
        if empty:
            check("WARN", f"Entirely empty in the source: {', '.join(empty)}.")

    out("\n### Census\n")
    census = tables.get("zcta_census")
    if census is not None:
        income = census["median_household_income"].dropna()
        outside = census[census["median_household_income"].notna() & ~census["median_household_income"].between(10_000, 300_000)]
        la_outside = outside[outside["in_la_county"]]
        passfail(outside.empty, f"Median income within $10k to $300k: range ${income.min():,.0f} to ${income.max():,.0f}; "
                 f"{len(outside)} California ZCTAs outside, {len(la_outside)} in LA County.", on_false="WARN")
        if len(outside):
            out(table(outside[["zcta", "median_household_income", "median_household_income_moe", "occupied_units", "in_la_county"]]) + "\n")
        for col, code in (("median_household_income", 250001), ("median_home_value", 2000001)):
            out(f"- `{col}`: {(census[col] == code).sum()} ZCTAs at the ACS top code {code:,}, "
                f"{census.loc[census['in_la_county'], col].eq(code).sum()} in LA County.")
        out(f"- `median_household_income`: {(census['median_household_income'] == 2499).sum()} ZCTAs at the ACS bottom code 2,499.")
        out(f"- Null in LA County: income {census.loc[census['in_la_county'], 'median_household_income'].isna().sum()}, "
            f"home value {census.loc[census['in_la_county'], 'median_home_value'].isna().sum()}.\n")


def dins_detail(dins: gpd.GeoDataFrame, zones) -> None:
    domain_rows = []
    fields = [c[:-6] for c in dins.columns if c.endswith("_clean") and c != "year_built_clean"]
    for col in fields:
        unknown = dins[col + "_clean"] == "Unknown"
        known = dins[~unknown]
        domain_rows.append({
            "attribute": col,
            "Unknown, destroyed": f"{unknown[dins['destroyed'] == 1].mean():.1%}",
            "Unknown, not destroyed": f"{unknown[dins['destroyed'] == 0].mean():.1%}",
            "destroyed rate when Unknown": f"{dins.loc[unknown, 'destroyed'].mean():.1%}" if unknown.any() else "",
            "destroyed rate when known": f"{known['destroyed'].mean():.1%}" if len(known) else "",
        })
    out("**Missingness by outcome.** This matters for the model:\n")
    out(table(pd.DataFrame(domain_rows)) + "\n")
    year = dins["year_built_clean"].isna()
    out(f"`year_built_clean` null: {year[dins['destroyed'] == 1].mean():.1%} of destroyed, "
        f"{year[dins['destroyed'] == 0].mean():.1%} of not destroyed.\n")
    check("WARN", "DINS attributes are missing far more often for destroyed homes (EAVES, WINDOWPANE and VENTSCREEN above all), "
                  "so `Unknown` nearly encodes the label and must not be a model feature value.")
    leak = dins[dins["WHATDIDFIRESTARTFROM_clean"] != "Unknown"]
    check("WARN", f"WHEREFIRESTARTEDONSTRUCTURE and WHATDIDFIRESTARTFROM are filled for {len(leak):,} structures, "
                  f"{int(leak['destroyed'].sum())} of them destroyed. They describe the outcome and would leak it.")
    if zones is not None:
        points = dins[["destroyed", "fire", "geometry"]]
        order = {"Very High": 3, "High": 2, "Moderate": 1}
        hits = gpd.sjoin(points, zones[["hazard_class", "geometry"]], how="left", predicate="intersects")
        hits["rank"] = hits["hazard_class"].map(order).fillna(0)
        best = hits.sort_values("rank").groupby(level=0).tail(1)
        best["hazard_class"] = best["hazard_class"].fillna("Outside any zone")
        summary = pd.crosstab(best["hazard_class"], best["fire"], values=best["destroyed"], aggfunc="sum").fillna(0).astype(int)
        summary["Total destroyed"] = summary.sum(axis=1)
        summary["All structures"] = best.groupby("hazard_class").size()
        summary["Destroyed rate"] = (summary["Total destroyed"] / summary["All structures"]).map("{:.1%}".format)
        out("**Destroyed residential structures by hazard zone:**\n")
        out(table(summary.reset_index()) + "\n")


def smoke_test() -> None:
    out("## 6. End-to-end smoke test: `area_context(address)`\n")
    out("Geocoder behavior to design around: Los Angeles City Hall, typed as `200 N Spring St`, matched "
        "`200 S SPRING ST`, so it was replaced as the downtown test address. The Central Library, typed with postal ZIP "
        "90071, came back as 90012 because the geocoder's ZIP comes from TIGER address ranges. Pacific Palisades "
        "has no Census place of its own, so its WRC row is the whole City of Los Angeles.\n")
    for label, address in TEST_ADDRESSES.items():
        out(f"### {label}: `{address}`\n")
        try:
            ctx = area_context(address)
        except Exception as exc:
            check("FAIL", f"{label}: {exc!r}")
            continue
        missing = ctx["missing_tables"]
        passfail(ctx["geocode"]["county_fips"] == LA_COUNTY_FIPS and len(ctx["geocode"]["tract_geoid"]) == 11,
                 f"{label}: geocoded to {ctx['geocode']['matched_address']}, tract {ctx['geocode']['tract_geoid']}.")
        if missing:
            check("WARN", f"{label}: result incomplete, tables not built: {', '.join(missing)}.")
        out("\n```json\n" + json.dumps(ctx, indent=1, default=str) + "\n```\n")


def sizes() -> None:
    out("## 7. Processed file sizes\n")
    rows, big = [], []
    for path in sorted(PROCESSED.iterdir()):
        if path.name.startswith("_"):
            continue
        mb = path.stat().st_size / 1e6
        rows.append({"file": path.name, "MB": f"{mb:.2f}", "over 50 MB": "YES" if mb > SIZE_LIMIT_MB else ""})
        if mb > SIZE_LIMIT_MB:
            big.append(path.name)
    out(table(pd.DataFrame(rows)) + "\n")
    passfail(not big, f"No processed file over {SIZE_LIMIT_MB} MB{': ' + ', '.join(big) if big else ''}.", on_false="WARN")
    out()


def main() -> int:
    manifest, log = load_manifest(), json.loads(PROCESS_LOG.read_text()) if PROCESS_LOG.exists() else {}
    tables = {name: load(name) for name, _, _ in DATASETS}

    overview(tables, manifest)
    structural(tables)
    crosswalk_ratios(tables)
    coverage(tables)
    sanity(tables)
    smoke_test()
    sizes()

    out("## 8. Processing notes\n")
    overlap = log.get("cdi_policies", {}).get("overlap_statewide")
    if overlap:
        out("**CDI publications disagree on 2020 and 2021** (statewide sums over ZIP-years in both files):\n")
        rows = [{"year": y, **v} for y, v in overlap.items()]
        out(table(pd.DataFrame(rows)) + "\n")
        out("The newer file wins, so there is a series break between 2019 and 2020.\n")
    if log.get("dins"):
        out(f"**DINS out-of-domain values set to Unknown:** `{log['dins'].get('out_of_domain_values_set_to_unknown')}`\n")
        out(f"**DINS field names (statewide service):** {', '.join(f'`{c}`' for c in log['dins'].get('raw_field_names', []))}\n")
        out(f"**DINS year built:** {log['dins'].get('year_built_outside_range')} rows outside 1800-2025 (mostly 0) set to null in `year_built_clean`.\n")
    if log.get("hazard_zones"):
        out(f"**Hazard polygons in the LA bounding box before clipping:** `{log['hazard_zones'].get('raw_counts_in_bbox')}`\n")

    body = lines[:]
    lines.clear()
    out("# Data validation report\n")
    out(f"Generated {date.today().isoformat()} by `scripts/03_validate.py`.\n")
    out(f"**Results:** {tally['PASS']} passed, {tally['FAIL']} failed, {tally['WARN']} warnings, {tally['SKIP']} skipped.\n")
    needs_manual = {k: v for k, v in manifest.items() if v.get("status") != "ok"}
    if needs_manual:
        out("**Datasets not available:**\n")
        for name, entry in needs_manual.items():
            out(f"- `{name}` ({entry.get('status')}): {entry.get('manual_action') or entry.get('error')}")
        out()
    out("**Failed checks and warnings:**\n")
    lines.extend(f"- {f}" for f in failures)
    out()
    (DOCS / "validation_report.md").write_text("\n".join(lines + body) + "\n")
    print(f"Wrote {(DOCS / 'validation_report.md').relative_to(ROOT)}: {tally}")
    for f in failures:
        print(" ", f[:220])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
