# Data dictionary

All files are in `data/processed/`. Everything was retrieved on **2026-11-06** unless noted. Scope is Los Angeles County (FIPS 06037) unless noted. Parquet files with geometry are GeoParquet in EPSG:4326.

ZIPs, ZCTAs, FIPS codes and tract IDs are strings with leading zeros. A missing value means the source did not provide it. Nothing is estimated or filled in.

**"LA ZIP" in this project** means a ZIP that the HUD crosswalk places at least partly in an LA County tract, or that the source itself assigns to LA County. This includes border ZIPs that are almost entirely in another county, such as 92301 at 0.01% of residential addresses in LA. Use `zip_tract_crosswalk.res_ratio` to filter them. `docs/validation_report.md` lists them.

---

## `zip_insurance.parquet`

Residential voluntary-market policy counts by ZIP and year, 2015 to 2023.

- **Source:** [CDI, Data Analysis on Wildfires and Insurance](https://www.insurance.ca.gov/01-consumers/200-wrr/DataAnalysisOnWildfiresAndInsurance.cfm): `Residential-Property-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2015-2021.xlsx` and `Residential-Insurance-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2020-2023.xlsx`
- **Join key:** `zip` + `year`

| Column | Type | Meaning |
| --- | --- | --- |
| `zip` | string | 5-digit ZIP |
| `year` | int | Policy year |
| `county` | string | County as published; null where the source left it blank |
| `new` | int | New policies |
| `renewed` | int | Renewed policies |
| `nonrenewed_insurer` | int | Insurer-initiated non-renewals. From the 2015-2021 file only, so null for 2022-2023 |
| `nonrenewed_insured` | int | Insured-initiated non-renewals. Same coverage |
| `nonrenewed_total` | int | All non-renewals. Published directly in the 2020-2023 file; insurer + insured for rows from the 2015-2021 file |
| `nonrenewal_rate` | float | `nonrenewed_total / (new + renewed + nonrenewed_total)` as a fraction. Null if the denominator is 0. This formula reproduces the published 7.5% for 91001 and 8.3% for 90272 in 2023 |
| `source_file` | string | Which CDI file supplied the row's counts |

**Limitations**

- **Data ends in 2023**, before the January 2025 fires.
- **Series break between 2019 and 2020.** The two files overlap on 2020-2021 and disagree (statewide non-renewals for 2020: 991,951 in the older file, 898,062 in the newer). The newer file wins for those years, so 2015-2019 and 2020-2023 are not strictly comparable.
- **For 2020-2021, the split columns do not add up to the total.** They come from the older file and the total from the newer one. For 91001 in 2020, 249 + 750 = 999, against a total of 864.
- **`nonrenewed_total` counts both insurer and policyholder decisions.** It is not a measure of insurers dropping customers on its own. Only 2015-2021 can separate the two.
- Voluntary market only, so FAIR Plan policies are excluded.

---

## `zip_fair_plan.parquet`

Share of residential dwelling units insured by the FAIR Plan, 2022.

- **Source:** [CDI PDF](https://www.insurance.ca.gov/01-consumers/200-wrr/upload/Number-of-Residential-Dwelling-Units-Insured-in-2022-FAIR-Plan-vs-Voluntary.pdf)
- **Join key:** `zip`

| Column | Type | Meaning |
| --- | --- | --- |
| `zip` | string | 5-digit ZIP |
| `fair_plan_share` | float | Published percentage as a fraction (0.233 = 23.3%) |
| `data_year` | int | Always 2022, the only year on the CDI page |
| `county` | string | County as listed |
| `city` | string | City as listed |
| `dwelling_units_voluntary` | float | Units in the voluntary market. A printed `-` is stored as 0 |
| `dwelling_units_fair` | float | Units in the FAIR Plan. A printed `-` is stored as 0 |

**Limitations:** Parsed from PDF text. Some numbers extract with stray spaces ("1 0,249"), so each row's counts were accepted only if they reproduce the printed percentage; all 1,719 statewide rows passed. Covers homeowners' and dwelling fire policies of 4 units or fewer and mobile homes, and excludes renters and condo unit-owners. Single year, before the fires.

---

## `hazard_zones.parquet` (GeoParquet)

CAL FIRE Fire Hazard Severity Zones clipped to LA County. Geometry simplified at 5 m tolerance in EPSG:3310.

- **Source:** [CNRA GIS hub](https://gis.data.cnra.ca.gov/): [FHSZSRA_23_3](https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/FHSZSRA_23_3/FeatureServer/0) and [FHSZLRA25_v1_All](https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/FHSALRA25_v1_All/FeatureServer/0)
- **Join key:** spatial
- **Version:** SRA as adopted effective **2024-04-01**. LRA is the State Fire Marshal map dated **2025-03-24**.

| Column | Type | Meaning |
| --- | --- | --- |
| `hazard_class` | string | `Moderate`, `High` or `Very High` |
| `responsibility_area` | string | Source layer: `SRA` (state) or `LRA` (local) |
| `geometry` | polygon | Zone polygon |

**Limitations**

- **The LRA layer may not be the legally adopted map everywhere.** It is the State Fire Marshal's map that local agencies must then adopt by ordinance. No statewide "as adopted" LRA layer was found, and local adoption was not verified.
- **`NonWildland` polygons are dropped** (511 in the LA bounding box) because they carry no severity class. An address there has a null `hazard_class`, same as one outside any polygon.
- **No zone does not mean no risk.** 3,664 of the 11,682 destroyed homes in DINS are outside any zone, including 59% of those destroyed in the Eaton Fire.

---

## `fire_perimeters.parquet` (GeoParquet)

Fires from 1950 onward intersecting LA County plus a 10 km buffer.

- **Source:** [California Fire Perimeters (all)](https://data.ca.gov/dataset/california-fire-perimeters-all), [service layer](https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/California_Historic_Fire_Perimeters/FeatureServer/0)
- **Join key:** spatial

| Column | Type | Meaning |
| --- | --- | --- |
| `fire_name` | string | Name as published, uppercase. Null for 870 of 2,321 rows |
| `year` | int | Fire year |
| `alarm_date` | timestamp | Alarm date. Null for 46 rows |
| `acres` | float | GIS acres for the whole fire, including any part outside the buffer |
| `cause` | string | Label decoded from the layer's own cause codes |
| `geometry` | polygon | Perimeter |

**Limitations:** No row key. Name + year is not unique, and most rows are recorded as `Unknown / Unidentified` cause.

---

## `wrc_communities.parquet`

Wildfire Risk to Communities percentiles for California communities and counties. Statewide by design.

- **Source:** [wildfirerisk.org/download](https://wildfirerisk.org/download/), `wrc_download_20260415.xlsx`
- **Join key:** `geoid` (best; `geocode()` returns `place_geoid`) or `name_normalized` + `county`

| Column | Type | Meaning |
| --- | --- | --- |
| `geoid` | string | Census place (7 chars) or county (5 chars) |
| `geo_level` | string | `community` or `county` |
| `community` | string | Name as published, without ", CA" |
| `name_normalized` | string | Lowercase, no punctuation, parenthetical county removed. Not unique across counties |
| `county` | string | County. The spreadsheet has none for communities, so it is the county holding most of the place's area, from Census boundaries |
| `risk_to_homes` | float | **Always empty.** This release publishes percentiles only |
| `risk_to_homes_pctile_state` | float | Mean risk to potential structures, percentile within California (0-1) |
| `risk_to_homes_pctile_national` | float | Same, within the US |
| `wildfire_likelihood` | float | **Always empty.** This release publishes percentiles only |
| `wildfire_likelihood_pctile_state` | float | Mean burn probability, percentile within California |
| `wildfire_likelihood_pctile_national` | float | Same, within the US |
| `total_buildings` | float | Buildings inside the boundary |
| `buildings_share_minimal_exposure` | float | Share of buildings minimally exposed |
| `buildings_share_indirect_exposure` | float | Share indirectly exposed |
| `buildings_share_direct_exposure` | float | Share directly exposed |
| `insufficient_data` | string | Source flag; null for counties |

**Limitations:** Covers Census places only. Pacific Palisades is part of the City of Los Angeles, so it gets the citywide figure.

---

## `nri_tracts.parquet`

FEMA National Risk Index for LA County census tracts. 2,495 rows, 42 columns.

- **Source:** https://www.fema.gov (OpenFEMA NRI page), **version v1.20, December 2025**. The national tract table and data dictionary were downloaded by hand; the table's rows are filtered to `STATEFIPS` 06 and `COUNTYFIPS` 037. The dictionary's own version field reads `1.20.0`, `December 2025`.
- **Input:** `data/manual/NRI_Table_CensusTracts/` (extracted folder, gitignored). A ZIP named `NRI_Table_CensusTracts*.zip` in `data/manual/` also works.
- **Join key:** `tract_geoid`
- **Column selection:** driven by `NRIDataDictionary.csv`. Every field whose `Relevant Layer` is National Risk Index, Social Vulnerability, Community Resilience or Wildfire is kept, and the dictionary's `Type` decides which are numeric.

| Column | Type | Meaning (dictionary alias) |
| --- | --- | --- |
| `tract_geoid` | string | 11-digit tract, from `TRACTFIPS` |
| `COUNTY` | string | County Name |
| `POPULATION` | int | Population (2020) |
| `BUILDVALUE` | float | Building Value ($) |
| `AREA` | float | Area (sq mi) |
| `RISK_VALUE` | float | National Risk Index - Value - Composite |
| `RISK_SCORE` | float | National Risk Index - Score - Composite |
| `RISK_RATNG` | string | National Risk Index - Rating - Composite |
| `RISK_SPCTL` | float | National Risk Index - State Percentile - Composite |
| `SOVI_SCORE` | float | Social Vulnerability - Score |
| `SOVI_RATNG` | string | Social Vulnerability - Rating |
| `SOVI_SPCTL` | float | Social Vulnerability - State Percentile |
| `RESL_SCORE` | float | Community Resilience - Score |
| `RESL_RATNG` | string | Community Resilience - Rating |
| `RESL_SPCTL` | float | Community Resilience - State Percentile |
| `RESL_VALUE` | float | Community Resilience - Value |
| `WFIR_EVNTS` | float | Wildfire - Number of Events (empty) |
| `WFIR_AFREQ` | float | Wildfire - Annualized Frequency |
| `WFIR_EXP_AREA` | float | Wildfire - Exposure - Impacted Area (sq mi) |
| `WFIR_EXPB` | float | Wildfire - Exposure - Building Value |
| `WFIR_EXPP` | float | Wildfire - Exposure - Population |
| `WFIR_EXPPE` | float | Wildfire - Exposure - Population Equivalence |
| `WFIR_EXPA` | float | Wildfire - Exposure - Agriculture Value |
| `WFIR_EXPT` | float | Wildfire - Exposure - Total |
| `WFIR_HLRB` | float | Wildfire - Historic Loss Ratio - Buildings |
| `WFIR_HLRP` | float | Wildfire - Historic Loss Ratio - Population |
| `WFIR_HLRA` | float | Wildfire - Historic Loss Ratio - Agriculture |
| `WFIR_HLRR` | string | Wildfire - Historic Loss Ratio - Total Rating |
| `WFIR_EALB` | float | Wildfire - Expected Annual Loss - Building Value |
| `WFIR_EALP` | float | Wildfire - Expected Annual Loss - Population |
| `WFIR_EALPE` | float | Wildfire - Expected Annual Loss - Population Equivalence |
| `WFIR_EALA` | float | Wildfire - Expected Annual Loss - Agriculture Value |
| **`WFIR_EALT`** | float | **Wildfire - Expected Annual Loss - Total. Read by `area_context()` as `tract_wildfire_eal`** |
| `WFIR_EALS` | float | Wildfire - Expected Annual Loss Score |
| `WFIR_EALR` | string | Wildfire - Expected Annual Loss Rating |
| `WFIR_ALRB` | float | Wildfire - Expected Annual Loss Rate - Building |
| `WFIR_ALRP` | float | Wildfire - Expected Annual Loss Rate - Population |
| `WFIR_ALRA` | float | Wildfire - Expected Annual Loss Rate - Agriculture |
| `WFIR_ALR_NPCTL` | float | Wildfire - Expected Annual Loss Rate - National Percentile |
| `WFIR_RISKV` | float | Wildfire - Hazard Type Risk Index Value |
| `WFIR_RISKS` | float | Wildfire - Hazard Type Risk Index Score |
| `WFIR_RISKR` | string | Wildfire - Hazard Type Risk Index Rating |

**Limitations**

- **`WFIR_EALT` is 0 for 1,783 of 2,495 LA tracts (71%)**, against 18% nationally. Those tracts are rated `No Expected Annual Losses`.
- **It can look wrong for a burned neighborhood.** The tract holding the Altadena Library is $17 a year and the one holding the Palisades Library is $52 a year, matching FEMA's raw file. Other tracts in the same ZIPs are rated Very High, with up to about $2.8M in 91001 and $3.8M in 90272. A low tract value does not mean an address is safe.
- **Heavily skewed:** the 44 tracts rated Very High hold 67% of LA County's total.
- **`RESL_*` columns are constant across LA tracts**, because FEMA's resilience values do not vary within a county. They are useless for comparing LA tracts.
- `WFIR_EVNTS` is empty nationally. `RISK_RATNG` is null for 1 tract.
- **Crosswalk match:** 2,494 of 2,495 tracts. `06037980020` is NRI-only: population 0, with a wildfire EAL of about $4,862. Its loss would be left out of any tract-to-ZIP rollup.

---

## `zip_home_values.parquet`

Zillow Home Value Index by ZIP and month: all homes, mid tier, smoothed, seasonally adjusted.

- **Source:** [Zillow Research](https://www.zillow.com/research/data/), [CSV](https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv)
- **Join key:** `zip` + `date`

| Column | Type | Meaning |
| --- | --- | --- |
| `zip` | string | 5-digit ZIP |
| `date` | timestamp | Month end, January 2000 to September 2026 |
| `zhvi` | float | Typical home value in dollars. Empty months are dropped |

**Limitations:** 287 ZIPs only. Zillow has no series for PO Box ZIPs and many low-volume ZIPs.

## `zip_home_values_latest.parquet`

- **Source and join key:** as above; join on `zip`

| Column | Type | Meaning |
| --- | --- | --- |
| `zip` | string | 5-digit ZIP |
| `zhvi_latest` | float | Most recent non-empty value |
| `zhvi_5yr_change` | float | `zhvi_latest / value 5 years earlier - 1` as a fraction (0.10 = +10%) |
| `latest_date` | timestamp | Month of `zhvi_latest` |

---

## `zcta_census.parquet`

ACS 5-year estimates (2020-2024) by ZCTA. All California ZCTAs by design.

- **Source:** [Census ACS table-based summary files](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/) for B19013, B25077 and B25003; [2020 ZCTA-county relationship file](https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt)
- **Join key:** `zcta` (via `zip_zcta` from a ZIP)

| Column | Type | ACS variable | Meaning |
| --- | --- | --- | --- |
| `zcta` | string | | 5-digit ZCTA |
| `median_household_income` | float | B19013_001E | Dollars |
| `median_household_income_moe` | float | B19013_001M | Margin of error |
| `median_home_value` | float | B25077_001E | Dollars |
| `median_home_value_moe` | float | B25077_001M | Margin of error |
| `occupied_units` | float | B25003_001E | Total occupied units |
| `occupied_units_moe` | float | B25003_001M | Margin of error |
| `owner_occupied_units` | float | B25003_002E | Owner-occupied units |
| `owner_occupied_units_moe` | float | B25003_002M | Margin of error |
| `in_la_county` | bool | | ZCTA overlaps LA County in the relationship file |
| `acs_vintage` | string | | `2020-2024` |

**Limitations:** The brief asked for the Census API, which now refuses requests without a key. The summary files are the Census Bureau's published version of the same tables. Negative jam values became null. **Coded limits are kept as published:** income 250,001 means "$250,000 or more", income 2,499 means "$2,500 or less", and home value 2,000,001 means "$2,000,000 or more" (15 LA ZCTAs). Treat them as bounds. Estimates predate the fires.

---

## `dins_2025_la.parquet` (GeoParquet, points)

CAL FIRE damage inspections for residential structures, Eaton and Palisades Fires, 2025. One row per structure inspected.

- **Source:** [CAL FIRE DINS data](https://data.ca.gov/dataset/cal-fire-damage-inspection-dins-data), [service layer](https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/POSTFIRE_MASTER_DATA_SHARE/FeatureServer/0). Field definitions are the service's own, saved at `data/raw/dins/dins_2025_eaton_palisades_layer_metadata.json`.
- **Join key:** `GLOBALID`; spatial; or `APN`
- **Residential** means `STRUCTURECATEGORY` is `Single Residence`, `Multiple Residence` or `Mixed Commercial/Residential`. Filter on it to narrow this.

**Derived columns**

| Column | Type | Meaning |
| --- | --- | --- |
| `destroyed` | int | 1 if `DAMAGE` is `Destroyed (>50%)`, else 0 |
| `damage_assessed` | bool | False if `DAMAGE` is `Inaccessible` (81 rows). Those have `destroyed` = 0 only because the rule says "else 0"; their real outcome is unknown, so exclude them from training |
| `fire` | string | `Eaton` or `Palisades` |
| `year_built_clean` | float | `YEARBUILT`, null if outside 1800-2025 (373 rows, mostly 0) |
| `<FIELD>_clean` | string | Standardized copy of each attribute below: labels from the data dictionary, with blanks and out-of-domain entries set to `Unknown` |

**Attributes with a `_clean` version**

| Field | Values in the data dictionary |
| --- | --- |
| `ROOFCONSTRUCTION` | Wood, Asphalt, Concrete, Tile, Metal, Other, Unknown |
| `EAVES` | Enclosed, Unenclosed, No Eaves, Unknown |
| `VENTSCREEN` | Mesh Screen <= 1/8", Mesh Screen > 1/8", Unscreened, No Vents, Unknown |
| `EXTERIORSIDING` | Metal, Stucco/Brick/Cement, Vinyl, Wood, Other, Unknown |
| `WINDOWPANE` | Single Pane, Multi Pane, No Windows, Unknown |
| `DECKPORCHONGRADE` | Composite, Wood, Masonry/Concrete, No Deck/Porch, Unknown |
| `DECKPORCHELEVATED` | Composite, Wood, Masonry/Concrete, No Deck/Porch, Unknown |
| `PATIOCOVERCARPORT` | Combustible, Non Combustible, No Patio Cover/Carport, Unknown |
| `FENCEATTACHEDTOSTRUCTURE` | Combustible, Non Combustible, No Fence, Unknown |
| `PROPANETANKDISTANCE` | 0-10', 11-20', 21-30', >30', Not Applicable |
| `UTILITYMISCSTRUCTUREDISTANCE` | <30', 30-50', >50', Not Applicable |
| `WHEREFIRESTARTEDONSTRUCTURE` | Roof, Eaves, Vent, Siding, Window, Deck on Grade, Deck Elevated, Attached Patio Cover/Carport, Attached Fence, Unknown |
| `WHATDIDFIRESTARTFROM` | Direct flame impingement, Embers, Radiant Heat, Unknown |
| `DEFENSIVEACTIONS` | Combination of Actions, Dozer Fuel Break, Engine Company Actions, Fire Retardant Drop, Hand Crew Fuel Break, Other, Unknown |
| `STRUCTURETYPE` | Single family, multi family, mobile home, motor home and mixed-use types |
| `STRUCTURECATEGORY` | Single Residence, Multiple Residence, Mixed Commercial/Residential |

**Other source fields kept as published:** `OBJECTID`, `GLOBALID`, `DAMAGE`, `STREETNUMBER`, `STREETNAME`, `STREETTYPE`, `STREETSUFFIX`, `CITY`, `STATE`, `ZIPCODE` (5-char string), `CALFIREUNIT`, `COUNTY`, `COMMUNITY`, `BATTALION`, `INCIDENTNAME`, `INCIDENTNUM`, `INCIDENTSTARTDATE`, `HAZARDTYPE`, `NUMBEROFUNITPERSTRUCTURE`, `NOOUTBUILDINGSDAMAGED`, `NOOUTBUILDINGSNOTDAMAGED`, `NOOFCARSONPROPERTY`, `FIRENAME` (entirely empty), `APN`, `ASSESSEDIMPROVEDVALUE`, `YEARBUILT`, `SITEADDRESS`, `LATITUDE`, `LONGITUDE`, `geometry`.

**Limitations**

- **No distance-to-vegetation field exists** in this dataset. The only distance fields are propane tank and utility structure.
- **`Unknown` depends on the outcome.** `EAVES` is Unknown for 70.9% of destroyed homes and 0.6% of the rest, because a burned home often can't be assessed. Treating `Unknown` as a category leaks the label. Dropping those rows biases the sample toward survivors.
- **Fields recorded after the fire must not be features:** `WHEREFIRESTARTEDONSTRUCTURE`, `WHATDIDFIRESTARTFROM`, `DEFENSIVEACTIONS`, and the outbuilding and car damage counts.
- **Selection:** DINS covers structures in and around the two fires, so there is no unexposed comparison group. It estimates damage given fire exposure, not the chance of a fire reaching a home.
- Contains street addresses of individual homes, as published by CAL FIRE.

---

## `zip_tract_crosswalk.parquet`

Use to allocate ZIP-level data to tracts.

- **Source:** HUD USPS crosswalk `data/manual/ZIP-TRACT_062026.xlsx` (2026 Q2, 2020 Census geographies), supplied by hand
- **Join key:** `zip` + `tract_geoid`

| Column | Type | Meaning |
| --- | --- | --- |
| `zip` | string | 5-digit ZIP |
| `tract_geoid` | string | 11-digit tract, starting 06037 |
| `res_ratio` | float | Share of the **ZIP's** residential addresses in this tract |
| `tot_ratio` | float | Share of the ZIP's total addresses in this tract |

**Limitations:** LA tracts only, so ratios sum to less than 1 for ZIPs crossing the county line. 41 ZIPs have no residential addresses (ratios sum to 0). Ratios count addresses, not people or value.

## `tract_zip_crosswalk.parquet`

Use to roll tract-level data up to ZIPs.

- **Source:** HUD USPS crosswalk `data/manual/TRACT-ZIP_062026.xlsx`. In this file `tract` is the tract and `geoid` is the ZIP.
- **Join key:** `tract_geoid` + `zip`

| Column | Type | Meaning |
| --- | --- | --- |
| `tract_geoid` | string | 11-digit tract, starting 06037 |
| `zip` | string | 5-digit ZIP |
| `res_ratio` | float | Share of the **tract's** residential addresses in this ZIP |
| `tot_ratio` | float | Share of the tract's total addresses in this ZIP |

**Limitations:** 2,494 tracts. 7 special-use tracts (06037980xxx) have no residential addresses.

---

## `zip_zcta.parquet`

Maps each LA ZIP to its ZCTA, so a ZIP can be joined to `zcta_census`.

- **Source:** derived. No official Census ZIP-to-ZCTA crosswalk exists, so it assumes ZIP = ZCTA and checks that the ZCTA exists in ACS.
- **Join key:** `zip`

| Column | Type | Meaning |
| --- | --- | --- |
| `zip` | string | Every LA ZIP in the crosswalk, CDI or Zillow tables |
| `zcta` | string | Same code if that ZCTA exists, else null |
| `has_matching_zcta` | bool | False for 183 ZIPs, which look like PO Box and single-organization ZIPs |
| `method` | string | Always `assumed ZIP = ZCTA` |

**Limitations:** A ZIP and a ZCTA with the same code can cover different areas. An address in an unmatched ZIP gets no income data.

---

## Hand-filled templates

Re-running `02_process.py` never overwrites these once they exist.

### `measures.csv`

Prefilled: `measure_id` (a short ID added for joins), `name` (from the "Do more, save more" list in the [CDI Safer from Wildfires FAQ](https://www.insurance.ca.gov/01-consumers/105-type/95-guides/03-res/upload/faq-safer-from-wildfire-regulation.pdf), September 2026 edition) and `source_url`. To fill in by hand: `description`, `category`, `cost_low`, `cost_high`, `certifications`, `dins_feature`. The FAQ lists these measures by name only.

### `discounts.csv`

Headers only: `insurer`, `measure_id`, `discount_pct`, `effective_date`, `source_url`.

### `grants.csv`

Headers only: `grant_id`, `name`, `covers_measures`, `max_amount`, `income_limit`, `status`, `source_url`.

---

## Other files

- `_process_log.json`: row counts and notes from the last `02_process.py` run, read by the validation script.
- `data/raw/manifest.json`: source URL, download date and status for each raw file.
- `data/cache/geocode_cache.json`: `geocode()` results. Holds looked-up addresses and is gitignored.
