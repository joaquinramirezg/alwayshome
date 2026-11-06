# Data validation report

Generated 2026-11-06 by `scripts/03_validate.py`.

**Results:** 42 passed, 1 failed, 8 warnings, 0 skipped.

**Failed checks and warnings:**

- **WARN:** NRI and the crosswalks list the same tracts (2,494 shared; NRI only: 06037980020; crosswalks only: none).
- **WARN:** 870 of 2,321 perimeters (37%) have no fire name, and 46 have no alarm date. Left empty as published.
- **FAIL:** central Altadena (34.1897, -118.1312): outside any zone.
- **WARN:** DINS attributes are missing far more often for destroyed homes (EAVES, WINDOWPANE and VENTSCREEN above all), so `Unknown` nearly encodes the label and must not be a model feature value.
- **WARN:** WHEREFIRESTARTEDONSTRUCTURE and WHATDIDFIRESTARTFROM are filled for 1,173 structures, 0 of them destroyed. They describe the outcome and would leak it.
- **WARN:** WFIR_EALT is exactly 0 for 1,783 of 2,495 LA tracts (71%), rated `No Expected Annual Losses`. It varies sharply within ZIPs: the Altadena test tract is about $17 a year, while 91001 also has tracts rated Very High.
- **WARN:** RESL_SCORE, RESL_RATNG, RESL_SPCTL, RESL_VALUE have one value across all LA tracts, because FEMA publishes resilience at county level. They cannot separate tracts here.
- **WARN:** Entirely empty in the source: WFIR_EVNTS.
- **WARN:** Median income within $10k to $300k: range $2,499 to $250,001; 1 California ZCTAs outside, 0 in LA County.

## 1. Datasets

### `zip_insurance`

- Source page: https://www.insurance.ca.gov/01-consumers/200-wrr/DataAnalysisOnWildfiresAndInsurance.cfm
- File: `data/raw/cdi/Number-of-Residential-Dwelling-Units-Insured-in-2022-FAIR-Plan-vs-Voluntary.pdf`
  - URL: https://www.insurance.ca.gov/01-consumers/200-wrr/upload/Number-of-Residential-Dwelling-Units-Insured-in-2022-FAIR-Plan-vs-Voluntary.pdf
  - Downloaded: 2026-11-06
- File: `data/raw/cdi/Residential-Insurance-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2020-2023.xlsx`
  - URL: https://www.insurance.ca.gov/01-consumers/200-wrr/upload/Residential-Insurance-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2020-2023.xlsx
  - Downloaded: 2026-11-06
- File: `data/raw/cdi/Residential-Property-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2015-2021.xlsx`
  - URL: https://www.insurance.ca.gov/01-consumers/200-wrr/upload/Residential-Property-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2015-2021.xlsx
  - Downloaded: 2026-11-06
- Rows: 3,186
- Columns (10): `zip`, `year`, `county`, `new`, `renewed`, `nonrenewed_insurer`, `nonrenewed_insured`, `nonrenewed_total`, `nonrenewal_rate`, `source_file`
- Nulls in key columns: `zip` 0, `year` 0

### `zip_fair_plan`

- Source page: https://www.insurance.ca.gov/01-consumers/200-wrr/DataAnalysisOnWildfiresAndInsurance.cfm
- File: `data/raw/cdi/Number-of-Residential-Dwelling-Units-Insured-in-2022-FAIR-Plan-vs-Voluntary.pdf`
  - URL: https://www.insurance.ca.gov/01-consumers/200-wrr/upload/Number-of-Residential-Dwelling-Units-Insured-in-2022-FAIR-Plan-vs-Voluntary.pdf
  - Downloaded: 2026-11-06
- File: `data/raw/cdi/Residential-Insurance-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2020-2023.xlsx`
  - URL: https://www.insurance.ca.gov/01-consumers/200-wrr/upload/Residential-Insurance-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2020-2023.xlsx
  - Downloaded: 2026-11-06
- File: `data/raw/cdi/Residential-Property-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2015-2021.xlsx`
  - URL: https://www.insurance.ca.gov/01-consumers/200-wrr/upload/Residential-Property-Voluntary-Market-New-Renew-NonRenew-by-ZIP-2015-2021.xlsx
  - Downloaded: 2026-11-06
- Rows: 291
- Columns (7): `zip`, `fair_plan_share`, `data_year`, `county`, `city`, `dwelling_units_voluntary`, `dwelling_units_fair`
- Nulls in key columns: `zip` 0

### `hazard_zones`

- Source page: https://gis.data.cnra.ca.gov/
- File: `data/raw/fhsz/fhsz_lra_la_bbox.geojson`
  - URL: https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/FHSALRA25_v1_All/FeatureServer/0
  - Downloaded: 2026-11-06
- File: `data/raw/fhsz/fhsz_sra_la_bbox.geojson`
  - URL: https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/FHSZSRA_23_3/FeatureServer/0
  - Downloaded: 2026-11-06
- Version: SRA: FHSZSRA_23_3, adopted effective 2024-04-01. LRA: FHSZLRA25_v1_All, State Fire Marshal map dated 2025-03-24.
- Rows: 553
- Columns (3): `hazard_class`, `responsibility_area`
- Nulls in key columns: `hazard_class` 0, `responsibility_area` 0

### `fire_perimeters`

- Source page: https://data.ca.gov/dataset/california-fire-perimeters-all
- File: `data/raw/perimeters/fire_perimeters_la_bbox.geojson`
  - URL: https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/California_Historic_Fire_Perimeters/FeatureServer/0
  - Downloaded: 2026-11-06
- Rows: 2,321
- Columns (6): `fire_name`, `year`, `alarm_date`, `acres`, `cause`
- Nulls in key columns: `fire_name` 870, `year` 0, `alarm_date` 46

### `wrc_communities`

- Source page: https://wildfirerisk.org/download/
- File: `data/raw/wrc/wrc_download_20260415.xlsx`
  - URL: https://wildfirerisk.org/wp-content/uploads/2026/04/wrc_download_20260415.xlsx
  - Downloaded: 2026-11-06
- Rows: 1,676
- Columns (16): `geoid`, `geo_level`, `community`, `name_normalized`, `county`, `risk_to_homes`, `risk_to_homes_pctile_state`, `risk_to_homes_pctile_national`, `wildfire_likelihood`, `wildfire_likelihood_pctile_state`, `wildfire_likelihood_pctile_national`, `total_buildings`, `buildings_share_minimal_exposure`, `buildings_share_indirect_exposure`, `buildings_share_direct_exposure`, `insufficient_data`
- Nulls in key columns: `geoid` 0, `community` 0, `county` 0

### `nri_tracts`

- Source page: https://www.fema.gov (OpenFEMA NRI page)
- File: `data/manual/NRI_Table_CensusTracts/NRI_Table_CensusTracts.csv`
  - URL: https://www.fema.gov (OpenFEMA NRI page)
  - Downloaded: 2026-11-06
- Version: v1.20, December 2025
- Note: National census tract table and data dictionary, downloaded by hand from OpenFEMA.
- Rows: 2,495
- Columns (42): `tract_geoid`, `COUNTY`, `POPULATION`, `BUILDVALUE`, `AREA`, `RISK_VALUE`, `RISK_SCORE`, `RISK_RATNG`, `RISK_SPCTL`, `SOVI_SCORE`, `SOVI_RATNG`, `SOVI_SPCTL`, `RESL_SCORE`, `RESL_RATNG`, `RESL_SPCTL`, `RESL_VALUE`, `WFIR_EVNTS`, `WFIR_AFREQ`, `WFIR_EXPB`, `WFIR_EXPP`, `WFIR_EXPPE`, `WFIR_EXPA`, `WFIR_EXPT`, `WFIR_EXP_AREA`, `WFIR_HLRB`, `WFIR_HLRP`, `WFIR_HLRA`, `WFIR_HLRR`, `WFIR_EALB`, `WFIR_EALP`, `WFIR_EALPE`, `WFIR_EALA`, `WFIR_EALT`, `WFIR_EALS`, `WFIR_EALR`, `WFIR_ALRB`, `WFIR_ALRP`, `WFIR_ALRA`, `WFIR_ALR_NPCTL`, `WFIR_RISKV`, `WFIR_RISKS`, `WFIR_RISKR`
- Nulls in key columns: `tract_geoid` 0

### `zip_home_values`

- Source page: https://www.zillow.com/research/data/
- File: `data/raw/zillow/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv`
  - URL: https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv
  - Downloaded: 2026-11-06
- Note: https://www.zillow.com/research/data/ refuses automated clients (HTTP 403). The CSV is the file Zillow publishes on its public CDN, and the CDN serves it without any workaround.
- Rows: 91,686
- Columns (3): `zip`, `date`, `zhvi`
- Nulls in key columns: `zip` 0, `date` 0

### `zip_home_values_latest`

- Source page: https://www.zillow.com/research/data/
- File: `data/raw/zillow/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv`
  - URL: https://files.zillowstatic.com/research/public_csvs/zhvi/Zip_zhvi_uc_sfrcondo_tier_0.33_0.67_sm_sa_month.csv
  - Downloaded: 2026-11-06
- Note: https://www.zillow.com/research/data/ refuses automated clients (HTTP 403). The CSV is the file Zillow publishes on its public CDN, and the CDN serves it without any workaround.
- Rows: 287
- Columns (4): `zip`, `zhvi_latest`, `zhvi_5yr_change`, `latest_date`
- Nulls in key columns: `zip` 0

### `zcta_census`

- Source page: https://www.census.gov/programs-surveys/acs/data/summary-file.html
- File: `data/raw/census/acsdt5y2024-b19013.dat`
  - URL: https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b19013.dat
  - Downloaded: 2026-11-06
- File: `data/raw/census/acsdt5y2024-b25003.dat`
  - URL: https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25003.dat
  - Downloaded: 2026-11-06
- File: `data/raw/census/acsdt5y2024-b25077.dat`
  - URL: https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25077.dat
  - Downloaded: 2026-11-06
- File: `data/raw/census/tab20_zcta520_county20_natl.txt`
  - URL: https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/tab20_zcta520_county20_natl.txt
  - Downloaded: 2026-11-06
- Version: ACS 5-year 2020-2024
- Note: The Census API now refuses keyless requests (redirects to missing_key.html). These are the same estimates from the Census Bureau's public table-based summary files.
- Rows: 1,808
- Columns (11): `zcta`, `median_household_income`, `median_household_income_moe`, `median_home_value`, `median_home_value_moe`, `occupied_units`, `occupied_units_moe`, `owner_occupied_units`, `owner_occupied_units_moe`, `in_la_county`, `acs_vintage`
- Nulls in key columns: `zcta` 0

### `dins_2025_la`

- Source page: https://data.ca.gov/dataset/cal-fire-damage-inspection-dins-data
- File: `data/raw/dins/dins_2025_eaton_palisades.geojson`
  - URL: https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/POSTFIRE_MASTER_DATA_SHARE/FeatureServer/0
  - Downloaded: 2026-11-06
- Rows: 22,152
- Columns (66): `OBJECTID`, `GLOBALID`, `DAMAGE`, `STRUCTURETYPE`, `STREETNUMBER`, `STREETNAME`, `STREETTYPE`, `STREETSUFFIX`, `CITY`, `STATE`, `ZIPCODE`, `CALFIREUNIT`, `COUNTY`, `COMMUNITY`, `BATTALION`, `INCIDENTNAME`, `INCIDENTNUM`, `INCIDENTSTARTDATE`, `HAZARDTYPE`, `WHEREFIRESTARTEDONSTRUCTURE`, `WHATDIDFIRESTARTFROM`, `DEFENSIVEACTIONS`, `STRUCTURECATEGORY`, `NUMBEROFUNITPERSTRUCTURE`, `NOOUTBUILDINGSDAMAGED`, `NOOUTBUILDINGSNOTDAMAGED`, `NOOFCARSONPROPERTY`, `ROOFCONSTRUCTION`, `EAVES`, `VENTSCREEN`, `EXTERIORSIDING`, `WINDOWPANE`, `DECKPORCHONGRADE`, `DECKPORCHELEVATED`, `PATIOCOVERCARPORT`, `FENCEATTACHEDTOSTRUCTURE`, `PROPANETANKDISTANCE`, `UTILITYMISCSTRUCTUREDISTANCE`, `FIRENAME`, `APN`, `ASSESSEDIMPROVEDVALUE`, `YEARBUILT`, `SITEADDRESS`, `LATITUDE`, `LONGITUDE`, `destroyed`, `damage_assessed`, `fire`, `ROOFCONSTRUCTION_clean`, `EAVES_clean`, `VENTSCREEN_clean`, `EXTERIORSIDING_clean`, `WINDOWPANE_clean`, `DECKPORCHONGRADE_clean`, `DECKPORCHELEVATED_clean`, `PATIOCOVERCARPORT_clean`, `FENCEATTACHEDTOSTRUCTURE_clean`, `PROPANETANKDISTANCE_clean`, `UTILITYMISCSTRUCTUREDISTANCE_clean`, `WHEREFIRESTARTEDONSTRUCTURE_clean`, `WHATDIDFIRESTARTFROM_clean`, `DEFENSIVEACTIONS_clean`, `STRUCTURETYPE_clean`, `STRUCTURECATEGORY_clean`, `year_built_clean`
- Nulls in key columns: `GLOBALID` 0, `DAMAGE` 0, `destroyed` 0

### `zip_tract_crosswalk`

- Source: HUD USPS crosswalks supplied by hand in `data/manual/` (2026 Q2, 2020 Census geographies)
- Download date: not recorded in the files (file timestamp 2026-11-06)
- Rows: 4,273
- Columns (4): `zip`, `tract_geoid`, `res_ratio`, `tot_ratio`
- Nulls in key columns: `zip` 0, `tract_geoid` 0

### `tract_zip_crosswalk`

- Source: HUD USPS crosswalks supplied by hand in `data/manual/` (2026 Q2, 2020 Census geographies)
- Download date: not recorded in the files (file timestamp 2026-11-06)
- Rows: 4,273
- Columns (4): `tract_geoid`, `zip`, `res_ratio`, `tot_ratio`
- Nulls in key columns: `tract_geoid` 0, `zip` 0

### `zip_zcta`

- Source: derived from `zcta_census` and the ZIP tables; assumes ZIP = ZCTA
- Rows: 490
- Columns (4): `zip`, `zcta`, `has_matching_zcta`, `method`
- Nulls in key columns: `zip` 0

## 2. Structural checks

- **PASS** `zip_insurance.zip`: all 5-character strings (0 bad).
- **PASS** `zip_fair_plan.zip`: all 5-character strings (0 bad).
- **PASS** `zip_home_values.zip`: all 5-character strings (0 bad).
- **PASS** `zip_home_values_latest.zip`: all 5-character strings (0 bad).
- **PASS** `zip_tract_crosswalk.zip`: all 5-character strings (0 bad).
- **PASS** `tract_zip_crosswalk.zip`: all 5-character strings (0 bad).
- **PASS** `zip_zcta.zip`: all 5-character strings (0 bad).
- **PASS** `zcta_census.zcta`: all 5-character strings (0 bad).
- **PASS** `zip_tract_crosswalk.tract_geoid`: all 11-character strings starting 06037 (0 bad).
- **PASS** `tract_zip_crosswalk.tract_geoid`: all 11-character strings starting 06037 (0 bad).
- **PASS** `nri_tracts.tract_geoid`: all 11-character strings starting 06037 (0 bad).
- **PASS** `zip_insurance`: no duplicate zip+year (0 found).
- **PASS** `zip_fair_plan`: no duplicate zip (0 found).
- **PASS** `wrc_communities`: no duplicate geoid (0 found).
- **PASS** `nri_tracts`: no duplicate tract_geoid (0 found).
- **PASS** `zip_home_values`: no duplicate zip+date (0 found).
- **PASS** `zip_home_values_latest`: no duplicate zip (0 found).
- **PASS** `zcta_census`: no duplicate zcta (0 found).
- **PASS** `dins_2025_la`: no duplicate GLOBALID (0 found).
- **PASS** `zip_tract_crosswalk`: no duplicate zip+tract_geoid (0 found).
- **PASS** `tract_zip_crosswalk`: no duplicate tract_geoid+zip (0 found).
- **PASS** `zip_zcta`: no duplicate zip (0 found).
- **PASS** `hazard_zones`: geometries valid (0 invalid) in EPSG:4326.
- **PASS** `fire_perimeters`: geometries valid (0 invalid) in EPSG:4326.
- **PASS** `dins_2025_la`: geometries valid (0 invalid) in EPSG:4326.

## 3. Crosswalk ratio checks

**ZIP-TRACT, national:** 39,350 keys. 3,449 do not sum to 1 within 0.01, and 3,449 of those sum to exactly 0 (no residential addresses, such as PO Box or business-only ZIPs).

- **PASS** ZIP-TRACT: every key with residential addresses sums to about 1 (0 exceptions).

477 ZIPs touch an LA County tract. 41 have no residential addresses at all. 16 cross the county line, keeping less than 99% of their residential addresses in LA:

| zip | res_ratio_in_la |
| --- | --- |
| 92301 | 0.0001 |
| 93063 | 0.0001 |
| 91710 | 0.0002 |
| 91709 | 0.001 |
| 93560 | 0.0018 |
| 91786 | 0.0019 |
| 90630 | 0.0037 |
| 92397 | 0.0049 |
| 93243 | 0.0155 |
| 90623 | 0.016 |
| 91362 | 0.0287 |
| 90631 | 0.0919 |
| 91361 | 0.3387 |
| 91307 | 0.9188 |
| 91766 | 0.9471 |
| 90265 | 0.9569 |

**TRACT-ZIP, national:** 84,932 keys. 230 do not sum to 1 within 0.01, and 230 of those sum to exactly 0 (no residential addresses, such as PO Box or business-only ZIPs).

- **PASS** TRACT-ZIP: every key with residential addresses sums to about 1 (0 exceptions).

2,494 LA tracts. 7 do not sum to about 1: 06037980005, 06037980006, 06037980007, 06037980034, 06037980037, 06037980038, 06037980039.


## 4. Cross-dataset coverage (reported, not failed)

LA ZIP universe: 490 ZIPs in any ZIP table, 436 of them with residential addresses in LA County.

| table | ZIPs in universe | missing, all | missing, residential in LA |
| --- | --- | --- | --- |
| CDI policies | 452 | 38 | 15 |
| CDI FAIR Plan | 291 | 199 | 146 |
| Zillow | 287 | 203 | 149 |
| Census ZCTA | 307 | 183 | 142 |
| HUD crosswalk | 477 | 13 | 0 |

<details><summary>Residential LA ZIPs missing from CDI policies (15)</summary>

90072, 90075, 90076, 90081, 90087, 90306, 90310, 90408, 90409, 90662, 91043, 91115, 91385, 91408, 91507

</details>

<details><summary>Residential LA ZIPs missing from CDI FAIR Plan (146)</summary>

90009, 90030, 90050, 90051, 90053, 90054, 90060, 90070, 90072, 90075, 90076, 90078, 90079, 90081, 90082, 90083, 90086, 90087, 90089, 90091, 90093, 90095, 90202, 90209, 90213, 90223, 90224, 90231, 90239, 90251, 90264, 90267, 90294, 90295, 90296, 90306, 90307, 90308, 90309, 90310, 90406, 90408, 90409, 90507, 90508, 90510, 90607, 90608, 90609, 90637, 90651, 90652, 90662, 90702, 90707, 90711, 90714, 90733, 90734, 90748, 90749, 90801, 90809, 90832, 90853, 91003, 91009, 91012, 91017, 91021, 91025, 91031, 91041, 91043, 91046, 91066, 91077, 91102, 91109, 91114, 91115, 91116, 91117, 91118, 91209, 91221, 91222, 91224, 91225, 91226, 91305, 91308, 91309, 91310, 91313, 91322, 91327, 91328, 91330, 91333, 91334, 91337, 91341, 91346, 91353, 91357, 91365, 91372, 91376, 91380, 91385, 91386, 91392, 91393, 91394, 91395, 91396, 91404, 91407, 91408, 91409, 91412, 91413, 91416, 91426, 91503, 91507, 91508, 91510, 91603, 91609, 91610, 91614, 91615, 91617, 91715, 91734, 91747, 91769, 91778, 91788, 91793, 91802, 93539, 93584, 93590

</details>

<details><summary>Residential LA ZIPs missing from Zillow (149)</summary>

90009, 90030, 90050, 90051, 90053, 90054, 90060, 90070, 90071, 90072, 90075, 90076, 90078, 90079, 90081, 90082, 90083, 90086, 90087, 90089, 90091, 90093, 90095, 90202, 90209, 90213, 90223, 90224, 90231, 90239, 90251, 90264, 90267, 90294, 90295, 90296, 90306, 90307, 90308, 90309, 90310, 90406, 90408, 90409, 90507, 90508, 90510, 90607, 90608, 90609, 90637, 90651, 90652, 90662, 90702, 90707, 90711, 90714, 90733, 90734, 90748, 90749, 90801, 90809, 90832, 90853, 91003, 91009, 91012, 91017, 91021, 91023, 91025, 91031, 91041, 91043, 91046, 91066, 91077, 91102, 91109, 91114, 91115, 91116, 91117, 91118, 91209, 91221, 91222, 91224, 91225, 91226, 91305, 91308, 91309, 91310, 91313, 91322, 91327, 91328, 91330, 91333, 91334, 91337, 91341, 91346, 91353, 91357, 91365, 91372, 91376, 91380, 91385, 91386, 91392, 91393, 91394, 91395, 91396, 91404, 91407, 91408, 91409, 91412, 91413, 91416, 91426, 91503, 91507, 91508, 91510, 91603, 91609, 91610, 91614, 91615, 91617, 91715, 91734, 91747, 91769, 91778, 91788, 91793, 91802, 93539, 93563, 93584, 93590

</details>

<details><summary>Residential LA ZIPs missing from Census ZCTA (142)</summary>

90009, 90030, 90050, 90051, 90053, 90054, 90060, 90070, 90072, 90075, 90076, 90078, 90081, 90082, 90083, 90086, 90087, 90091, 90093, 90202, 90209, 90213, 90223, 90224, 90231, 90239, 90251, 90264, 90267, 90294, 90295, 90296, 90306, 90307, 90308, 90309, 90310, 90406, 90408, 90409, 90507, 90508, 90510, 90607, 90608, 90609, 90637, 90651, 90652, 90662, 90702, 90707, 90711, 90714, 90733, 90734, 90748, 90749, 90801, 90809, 90832, 90853, 91003, 91009, 91012, 91017, 91021, 91023, 91025, 91031, 91041, 91043, 91066, 91077, 91102, 91109, 91114, 91115, 91116, 91117, 91118, 91209, 91221, 91222, 91224, 91225, 91226, 91305, 91308, 91309, 91310, 91313, 91322, 91327, 91328, 91333, 91334, 91337, 91341, 91346, 91353, 91357, 91365, 91372, 91376, 91380, 91385, 91386, 91392, 91393, 91394, 91395, 91396, 91404, 91407, 91408, 91409, 91412, 91413, 91416, 91426, 91503, 91507, 91508, 91510, 91603, 91609, 91610, 91614, 91615, 91617, 91715, 91734, 91747, 91769, 91778, 91788, 91793, 91802, 93539, 93584, 93590

</details>

<details><summary>Residential LA ZIPs missing from HUD crosswalk (0)</summary>

none

</details>

<details><summary>ZIPs with no matching ZCTA, flagged in zip_zcta (183)</summary>

90009, 90030, 90050, 90051, 90053, 90054, 90060, 90070, 90072, 90074, 90075, 90076, 90078, 90081, 90082, 90083, 90084, 90086, 90087, 90088, 90091, 90093, 90140, 90189, 90202, 90205, 90209, 90213, 90223, 90224, 90231, 90239, 90251, 90264, 90267, 90294, 90295, 90296, 90306, 90307, 90308, 90309, 90310, 90406, 90407, 90408, 90409, 90507, 90508, 90509, 90510, 90607, 90608, 90609, 90610, 90637, 90651, 90652, 90661, 90662, 90702, 90707, 90711, 90714, 90733, 90734, 90748, 90749, 90801, 90809, 90832, 90833, 90844, 90846, 90853, 90895, 91003, 91009, 91012, 91017, 91021, 91023, 91025, 91031, 91041, 91043, 91066, 91077, 91102, 91109, 91114, 91115, 91116, 91117, 91118, 91121, 91123, 91124, 91126, 91129, 91182, 91184, 91185, 91188, 91189, 91199, 91209, 91221, 91222, 91224, 91225, 91226, 91305, 91308, 91309, 91310, 91313, 91322, 91327, 91328, 91333, 91334, 91337, 91341, 91346, 91353, 91357, 91365, 91372, 91376, 91380, 91383, 91385, 91386, 91392, 91393, 91394, 91395, 91396, 91404, 91407, 91408, 91409, 91410, 91412, 91413, 91416, 91426, 91470, 91482, 91495, 91503, 91507, 91508, 91510, 91521, 91522, 91523, 91603, 91609, 91610, 91614, 91615, 91616, 91617, 91715, 91716, 91734, 91747, 91756, 91769, 91771, 91772, 91778, 91788, 91793, 91802, 91804, 93539, 93584, 93586, 93590, 93599

</details>

CDI ZIPs per year: 2015: 430, 2016: 389, 2017: 347, 2018: 329, 2019: 342, 2020: 370, 2021: 354, 2022: 311, 2023: 314

Crosswalk tracts: 2,494 in TRACT-ZIP and 2,494 in ZIP-TRACT.

- **PASS** Both crosswalks list the same LA tracts.
**NRI versus crosswalk tracts:** 2,495 LA tracts in NRI, 2,494 in the crosswalks, 2,494 match. 1 are in NRI only and 0 in the crosswalks only.

<details><summary>NRI tracts missing from the crosswalks (1)</summary>

06037980020

</details>

<details><summary>Crosswalk tracts missing from NRI (0)</summary>

none

</details>

- **WARN** NRI and the crosswalks list the same tracts (2,494 shared; NRI only: 06037980020; crosswalks only: none).

## 5. Sanity checks against known facts

### CDI non-renewal rate, 2023

- **PASS** ZIP 91001: 7.50%, expected about 7.5%.
- **PASS** ZIP 90272: 8.29%, expected about 8.3%.

Method: `nonrenewed_total / (new + renewed + nonrenewed_total)`. Other denominators miss the published figures (for 91001: 8.0% on renewed + non-renewed, 8.7% on renewed alone).

### Fire perimeters

- **PASS** 2025 EATON fire present: 14,056 acres.
- **PASS** 2025 PALISADES fire present: 23,449 acres.
- **WARN** 870 of 2,321 perimeters (37%) have no fire name, and 46 have no alarm date. Left empty as published.

### Hazard zones

- **FAIL** central Altadena (34.1897, -118.1312): outside any zone.
- **PASS** Pacific Palisades (34.0469, -118.5259): Very High.
- **PASS** downtown LA (34.0522, -118.2437): outside any zone.

Central Altadena check: the point sits in land the LRA map labels `NonWildland`, confirmed by querying CAL FIRE's live service. That is the official map, not a processing error. Zones start about 450 m away: Lake Ave at Loma Alta Dr (34.1985, -118.1312) is High, and the foothills above are Very High. `NonWildland` is dropped because it has no severity class, so `hazard_class` is null there.

### DINS

| fire | Affected (>0-10%) | Destroyed (>50%) | Inaccessible | Major (25-50%) | Minor (10-25%) | No Damage | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Eaton | 632 | 6116 | 31 | 39 | 111 | 5290 | 12219 |
| Palisades | 619 | 5566 | 50 | 58 | 143 | 3497 | 9933 |
| Total | 1251 | 11682 | 81 | 97 | 254 | 8787 | 22152 |

- **PASS** Eaton: 6,116 destroyed residential structures.
- **PASS** Palisades: 5,566 destroyed residential structures.
**Missingness by outcome.** This matters for the model:

| attribute | Unknown, destroyed | Unknown, not destroyed | destroyed rate when Unknown | destroyed rate when known |
| --- | --- | --- | --- | --- |
| ROOFCONSTRUCTION | 11.3% | 2.1% | 85.5% | 50.3% |
| EAVES | 70.9% | 0.6% | 99.2% | 24.6% |
| VENTSCREEN | 40.7% | 4.1% | 91.7% | 40.8% |
| EXTERIORSIDING | 3.3% | 0.5% | 88.1% | 52.0% |
| WINDOWPANE | 42.4% | 0.8% | 98.4% | 39.3% |
| DECKPORCHONGRADE | 8.8% | 1.1% | 90.0% | 50.7% |
| DECKPORCHELEVATED | 24.1% | 2.1% | 92.7% | 46.4% |
| PATIOCOVERCARPORT | 28.2% | 1.7% | 94.9% | 44.9% |
| FENCEATTACHEDTOSTRUCTURE | 11.1% | 0.7% | 94.8% | 50.0% |
| PROPANETANKDISTANCE | 64.5% | 63.3% | 53.2% | 51.9% |
| UTILITYMISCSTRUCTUREDISTANCE | 65.8% | 63.0% | 53.8% | 50.8% |
| WHEREFIRESTARTEDONSTRUCTURE | 100.0% | 88.9% | 55.7% | 0.0% |
| WHATDIDFIRESTARTFROM | 100.0% | 88.8% | 55.7% | 0.0% |
| DEFENSIVEACTIONS | 96.4% | 91.5% | 54.0% | 32.2% |
| STRUCTURETYPE | 0.0% | 0.0% |  | 52.7% |
| STRUCTURECATEGORY | 0.0% | 0.0% |  | 52.7% |

`year_built_clean` null: 1.4% of destroyed, 2.0% of not destroyed.

- **WARN** DINS attributes are missing far more often for destroyed homes (EAVES, WINDOWPANE and VENTSCREEN above all), so `Unknown` nearly encodes the label and must not be a model feature value.
- **WARN** WHEREFIRESTARTEDONSTRUCTURE and WHATDIDFIRESTARTFROM are filled for 1,173 structures, 0 of them destroyed. They describe the outcome and would leak it.
**Destroyed residential structures by hazard zone:**

| hazard_class | Eaton | Palisades | Total destroyed | All structures | Destroyed rate |
| --- | --- | --- | --- | --- | --- |
| High | 579 | 0 | 579 | 982 | 59.0% |
| Moderate | 560 | 0 | 560 | 900 | 62.2% |
| Outside any zone | 3607 | 57 | 3664 | 6882 | 53.2% |
| Very High | 1370 | 5509 | 6879 | 13388 | 51.4% |

### NRI

- **PASS** WFIR_EALT is non-negative (min 0).
- **PASS** WFIR_EALT present for 100.0% of tracts.
- **WARN** WFIR_EALT is exactly 0 for 1,783 of 2,495 LA tracts (71%), rated `No Expected Annual Losses`. It varies sharply within ZIPs: the Altadena test tract is about $17 a year, while 91001 also has tracts rated Very High.
- **WARN** RESL_SCORE, RESL_RATNG, RESL_SPCTL, RESL_VALUE have one value across all LA tracts, because FEMA publishes resilience at county level. They cannot separate tracts here.
- **WARN** Entirely empty in the source: WFIR_EVNTS.

### Census

- **WARN** Median income within $10k to $300k: range $2,499 to $250,001; 1 California ZCTAs outside, 0 in LA County.
| zcta | median_household_income | median_household_income_moe | occupied_units | in_la_county |
| --- | --- | --- | --- | --- |
| 95930 | 2499 |  | 155 | False |

- `median_household_income`: 17 ZCTAs at the ACS top code 250,001, 0 in LA County.
- `median_home_value`: 68 ZCTAs at the ACS top code 2,000,001, 15 in LA County.
- `median_household_income`: 1 ZCTAs at the ACS bottom code 2,499.
- Null in LA County: income 20, home value 19.

## 6. End-to-end smoke test: `area_context(address)`

Geocoder behavior to design around: Los Angeles City Hall, typed as `200 N Spring St`, matched `200 S SPRING ST`, so it was replaced as the downtown test address. The Central Library, typed with postal ZIP 90071, came back as 90012 because the geocoder's ZIP comes from TIGER address ranges. Pacific Palisades has no Census place of its own, so its WRC row is the whole City of Los Angeles.

### Altadena (Altadena Library): `600 E Mariposa St, Altadena, CA 91001`

- **PASS** Altadena (Altadena Library): geocoded to 600 E MARIPOSA ST, ALTADENA, CA, 91001, tract 06037461100.

```json
{
 "address": "600 E Mariposa St, Altadena, CA 91001",
 "geocode": {
  "lat": 34.189637011412,
  "lon": -118.137393868125,
  "matched_address": "600 E MARIPOSA ST, ALTADENA, CA, 91001",
  "zip": "91001",
  "tract_geoid": "06037461100",
  "county_fips": "06037",
  "place": "Altadena",
  "place_geoid": "0601290"
 },
 "missing_tables": [],
 "hazard_class": null,
 "hazard_responsibility_area": null,
 "fires_within_5km": [
  {
   "fire_name": "EATON",
   "year": 2025,
   "distance_km": 0.0
  },
  {
   "fire_name": "LOWE",
   "year": 2019,
   "distance_km": 2.85
  },
  {
   "fire_name": "COYOTE",
   "year": 2017,
   "distance_km": 3.81
  },
  {
   "fire_name": "STATION",
   "year": 2009,
   "distance_km": 2.42
  },
  {
   "fire_name": "LOWE",
   "year": 2007,
   "distance_km": 2.4
  },
  {
   "fire_name": "KINNELOA",
   "year": 1995,
   "distance_km": 4.53
  },
  {
   "fire_name": "KINNELOA",
   "year": 1993,
   "distance_km": 1.66
  },
  {
   "fire_name": "GLEN ALLEN",
   "year": 1993,
   "distance_km": 2.27
  },
  {
   "fire_name": "VINEHILL",
   "year": 1992,
   "distance_km": 1.95
  },
  {
   "fire_name": null,
   "year": 1991,
   "distance_km": 4.88
  },
  {
   "fire_name": "FLINTRIDGE",
   "year": 1986,
   "distance_km": 4.38
  },
  {
   "fire_name": "CREST",
   "year": 1984,
   "distance_km": 4.95
  },
  {
   "fire_name": null,
   "year": 1979,
   "distance_km": 1.76
  },
  {
   "fire_name": "PINECREST/USFS",
   "year": 1979,
   "distance_km": 1.82
  },
  {
   "fire_name": null,
   "year": 1977,
   "distance_km": 3.74
  },
  {
   "fire_name": null,
   "year": 1976,
   "distance_km": 3.95
  },
  {
   "fire_name": null,
   "year": 1968,
   "distance_km": 2.26
  },
  {
   "fire_name": null,
   "year": 1968,
   "distance_km": 2.38
  },
  {
   "fire_name": null,
   "year": 1968,
   "distance_km": 3.5
  },
  {
   "fire_name": null,
   "year": 1962,
   "distance_km": 2.02
  },
  {
   "fire_name": null,
   "year": 1960,
   "distance_km": 1.77
  },
  {
   "fire_name": null,
   "year": 1960,
   "distance_km": 2.38
  },
  {
   "fire_name": null,
   "year": 1960,
   "distance_km": 3.81
  },
  {
   "fire_name": "WOODWARDIA",
   "year": 1959,
   "distance_km": 3.63
  },
  {
   "fire_name": null,
   "year": 1959,
   "distance_km": 4.59
  }
 ],
 "zip_insurance_trend": [
  {
   "year": 2015,
   "new": 1107,
   "renewed": 9991,
   "nonrenewed_total": 1007,
   "nonrenewal_rate": 0.08318876497315159
  },
  {
   "year": 2016,
   "new": 1106,
   "renewed": 10080,
   "nonrenewed_total": 1049,
   "nonrenewal_rate": 0.08573763792398856
  },
  {
   "year": 2017,
   "new": 1047,
   "renewed": 10126,
   "nonrenewed_total": 929,
   "nonrenewal_rate": 0.07676417121137002
  },
  {
   "year": 2018,
   "new": 1150,
   "renewed": 10135,
   "nonrenewed_total": 1111,
   "nonrenewal_rate": 0.08962568570506615
  },
  {
   "year": 2019,
   "new": 1237,
   "renewed": 10089,
   "nonrenewed_total": 1094,
   "nonrenewal_rate": 0.08808373590982287
  },
  {
   "year": 2020,
   "new": 1008,
   "renewed": 10083,
   "nonrenewed_total": 864,
   "nonrenewal_rate": 0.07227101631116688
  },
  {
   "year": 2021,
   "new": 1021,
   "renewed": 10124,
   "nonrenewed_total": 1015,
   "nonrenewal_rate": 0.0834703947368421
  },
  {
   "year": 2022,
   "new": 1080,
   "renewed": 10004,
   "nonrenewed_total": 1078,
   "nonrenewal_rate": 0.0886367373787206
  },
  {
   "year": 2023,
   "new": 736,
   "renewed": 10036,
   "nonrenewed_total": 874,
   "nonrenewal_rate": 0.07504722651554181
  }
 ],
 "fair_plan_share": 0.059,
 "fair_plan_data_year": 2022,
 "tract_wildfire_eal": 17.49873159736938,
 "zip_home_value": 1126420.156415316,
 "zip_home_value_5yr_change": 0.021469436218161775,
 "zcta_median_income": 134903,
 "wrc_community": {
  "community": "Altadena",
  "risk_to_homes_pctile_state": 0.95,
  "risk_to_homes_pctile_national": 0.996,
  "wildfire_likelihood_pctile_state": 0.924,
  "wildfire_likelihood_pctile_national": 0.992
 }
}
```

### Pacific Palisades (Palisades Library): `861 Alma Real Dr, Pacific Palisades, CA 90272`

- **PASS** Pacific Palisades (Palisades Library): geocoded to 861 ALMA REAL DR, PACIFIC PALISADES, CA, 90272, tract 06037262706.

```json
{
 "address": "861 Alma Real Dr, Pacific Palisades, CA 90272",
 "geocode": {
  "lat": 34.044297333392,
  "lon": -118.524823334174,
  "matched_address": "861 ALMA REAL DR, PACIFIC PALISADES, CA, 90272",
  "zip": "90272",
  "tract_geoid": "06037262706",
  "county_fips": "06037",
  "place": "Los Angeles",
  "place_geoid": "0644000"
 },
 "missing_tables": [],
 "hazard_class": "Very High",
 "hazard_responsibility_area": "LRA",
 "fires_within_5km": [
  {
   "fire_name": "PALISADES",
   "year": 2025,
   "distance_km": 0.0
  },
  {
   "fire_name": "PALISADES 2",
   "year": 2019,
   "distance_km": 2.85
  },
  {
   "fire_name": "GETTY",
   "year": 2019,
   "distance_km": 4.99
  },
  {
   "fire_name": "TOPANGA",
   "year": 2017,
   "distance_km": 4.92
  },
  {
   "fire_name": "TEMESCAL",
   "year": 2015,
   "distance_km": 1.12
  },
  {
   "fire_name": "OAKMONT",
   "year": 2015,
   "distance_km": 3.99
  },
  {
   "fire_name": "PALISADES",
   "year": 2014,
   "distance_km": 1.42
  },
  {
   "fire_name": "RUSTIC",
   "year": 2012,
   "distance_km": 3.12
  },
  {
   "fire_name": "OLD TOPANGA",
   "year": 1993,
   "distance_km": 4.96
  },
  {
   "fire_name": null,
   "year": 1989,
   "distance_km": 3.69
  },
  {
   "fire_name": null,
   "year": 1980,
   "distance_km": 2.73
  },
  {
   "fire_name": "MANDEVILLE/LA CITY",
   "year": 1978,
   "distance_km": 0.86
  },
  {
   "fire_name": null,
   "year": 1975,
   "distance_km": 1.2
  },
  {
   "fire_name": "TRIPPET",
   "year": 1973,
   "distance_km": 3.14
  },
  {
   "fire_name": null,
   "year": 1961,
   "distance_km": 3.18
  },
  {
   "fire_name": "BEL AIR",
   "year": 1961,
   "distance_km": 4.14
  }
 ],
 "zip_insurance_trend": [
  {
   "year": 2015,
   "new": 775,
   "renewed": 6565,
   "nonrenewed_total": 782,
   "nonrenewal_rate": 0.0962817040137897
  },
  {
   "year": 2016,
   "new": 790,
   "renewed": 6562,
   "nonrenewed_total": 789,
   "nonrenewal_rate": 0.09691684068296279
  },
  {
   "year": 2017,
   "new": 679,
   "renewed": 6659,
   "nonrenewed_total": 662,
   "nonrenewal_rate": 0.08275
  },
  {
   "year": 2018,
   "new": 636,
   "renewed": 6678,
   "nonrenewed_total": 637,
   "nonrenewal_rate": 0.08011570871588479
  },
  {
   "year": 2019,
   "new": 748,
   "renewed": 6473,
   "nonrenewed_total": 777,
   "nonrenewal_rate": 0.09714928732183045
  },
  {
   "year": 2020,
   "new": 609,
   "renewed": 6172,
   "nonrenewed_total": 560,
   "nonrenewal_rate": 0.07628388502928757
  },
  {
   "year": 2021,
   "new": 961,
   "renewed": 5765,
   "nonrenewed_total": 950,
   "nonrenewal_rate": 0.12376237623762376
  },
  {
   "year": 2022,
   "new": 727,
   "renewed": 5852,
   "nonrenewed_total": 731,
   "nonrenewal_rate": 0.1
  },
  {
   "year": 2023,
   "new": 408,
   "renewed": 5907,
   "nonrenewed_total": 571,
   "nonrenewal_rate": 0.08292187046180656
  }
 ],
 "fair_plan_share": 0.08,
 "fair_plan_data_year": 2022,
 "tract_wildfire_eal": 51.855659770917256,
 "zip_home_value": 2850078.8137227073,
 "zip_home_value_5yr_change": -0.03376704544618825,
 "zcta_median_income": 189713,
 "wrc_community": {
  "community": "Los Angeles",
  "risk_to_homes_pctile_state": 0.823,
  "risk_to_homes_pctile_national": 0.978,
  "wildfire_likelihood_pctile_state": 0.785,
  "wildfire_likelihood_pctile_national": 0.963
 }
}
```

### Downtown LA (Central Library): `630 W 5th St, Los Angeles, CA 90071`

- **PASS** Downtown LA (Central Library): geocoded to 630 W 5TH ST, LOS ANGELES, CA, 90012, tract 06037207712.

```json
{
 "address": "630 W 5th St, Los Angeles, CA 90071",
 "geocode": {
  "lat": 34.051747923407,
  "lon": -118.256474469338,
  "matched_address": "630 W 5TH ST, LOS ANGELES, CA, 90012",
  "zip": "90012",
  "tract_geoid": "06037207712",
  "county_fips": "06037",
  "place": "Los Angeles",
  "place_geoid": "0644000"
 },
 "missing_tables": [],
 "hazard_class": null,
 "hazard_responsibility_area": null,
 "fires_within_5km": [
  {
   "fire_name": null,
   "year": 1981,
   "distance_km": 2.84
  },
  {
   "fire_name": null,
   "year": 1976,
   "distance_km": 3.26
  },
  {
   "fire_name": null,
   "year": 1976,
   "distance_km": 4.64
  },
  {
   "fire_name": null,
   "year": 1974,
   "distance_km": 3.24
  },
  {
   "fire_name": null,
   "year": 1966,
   "distance_km": 3.06
  },
  {
   "fire_name": null,
   "year": 1963,
   "distance_km": 4.04
  },
  {
   "fire_name": null,
   "year": 1957,
   "distance_km": 2.39
  }
 ],
 "zip_insurance_trend": [
  {
   "year": 2015,
   "new": 72,
   "renewed": 637,
   "nonrenewed_total": 74,
   "nonrenewal_rate": 0.09450830140485313
  },
  {
   "year": 2016,
   "new": 72,
   "renewed": 639,
   "nonrenewed_total": 74,
   "nonrenewal_rate": 0.09426751592356689
  },
  {
   "year": 2017,
   "new": 77,
   "renewed": 622,
   "nonrenewed_total": 68,
   "nonrenewal_rate": 0.08865710560625815
  },
  {
   "year": 2018,
   "new": 57,
   "renewed": 658,
   "nonrenewed_total": 75,
   "nonrenewal_rate": 0.0949367088607595
  },
  {
   "year": 2019,
   "new": 78,
   "renewed": 649,
   "nonrenewed_total": 61,
   "nonrenewal_rate": 0.07741116751269035
  },
  {
   "year": 2020,
   "new": 72,
   "renewed": 690,
   "nonrenewed_total": 69,
   "nonrenewal_rate": 0.08303249097472924
  },
  {
   "year": 2021,
   "new": 100,
   "renewed": 682,
   "nonrenewed_total": 91,
   "nonrenewal_rate": 0.10423825887743414
  },
  {
   "year": 2022,
   "new": 72,
   "renewed": 703,
   "nonrenewed_total": 74,
   "nonrenewal_rate": 0.08716136631330977
  },
  {
   "year": 2023,
   "new": 67,
   "renewed": 679,
   "nonrenewed_total": 77,
   "nonrenewal_rate": 0.09356014580801944
  }
 ],
 "fair_plan_share": 0.095,
 "fair_plan_data_year": 2022,
 "tract_wildfire_eal": 0.0,
 "zip_home_value": 579084.4607338422,
 "zip_home_value_5yr_change": -0.08921035633176855,
 "zcta_median_income": 66860,
 "wrc_community": {
  "community": "Los Angeles",
  "risk_to_homes_pctile_state": 0.823,
  "risk_to_homes_pctile_national": 0.978,
  "wildfire_likelihood_pctile_state": 0.785,
  "wildfire_likelihood_pctile_national": 0.963
 }
}
```

## 7. Processed file sizes

| file | MB | over 50 MB |
| --- | --- | --- |
| dins_2025_la.parquet | 2.72 |  |
| discounts.csv | 0.00 |  |
| fire_perimeters.parquet | 13.91 |  |
| grants.csv | 0.00 |  |
| hazard_zones.parquet | 2.43 |  |
| measures.csv | 0.00 |  |
| nri_tracts.parquet | 0.33 |  |
| tract_zip_crosswalk.parquet | 0.08 |  |
| wrc_communities.parquet | 0.13 |  |
| zcta_census.parquet | 0.08 |  |
| zip_fair_plan.parquet | 0.01 |  |
| zip_home_values.parquet | 0.95 |  |
| zip_home_values_latest.parquet | 0.01 |  |
| zip_insurance.parquet | 0.08 |  |
| zip_tract_crosswalk.parquet | 0.10 |  |
| zip_zcta.parquet | 0.01 |  |

- **PASS** No processed file over 50 MB.

## 8. Processing notes

**CDI publications disagree on 2020 and 2021** (statewide sums over ZIP-years in both files):

| year | new_old | new_new | renewed_old | renewed_new | nonrenewed_total_old | nonrenewed_total_new |
| --- | --- | --- | --- | --- | --- | --- |
| 2020 | 1057382 | 1007406 | 7631096 | 7572611 | 991951 | 898062 |
| 2021 | 1107156 | 1091083 | 7620458 | 7514465 | 1118264 | 1037753 |

The newer file wins, so there is a series break between 2019 and 2020.

**DINS out-of-domain values set to Unknown:** `{'ROOFCONSTRUCTION': {'Combustible': 1, 'Non Combustible': 1}, 'EAVES': {'Combustible': 2}, 'VENTSCREEN': {'Attached Fence': 1}, 'WINDOWPANE': {'Asphalt': 1}}`

**DINS field names (statewide service):** `OBJECTID`, `GLOBALID`, `DAMAGE`, `STRUCTURETYPE`, `STREETNUMBER`, `STREETNAME`, `STREETTYPE`, `STREETSUFFIX`, `CITY`, `STATE`, `ZIPCODE`, `CALFIREUNIT`, `COUNTY`, `COMMUNITY`, `BATTALION`, `INCIDENTNAME`, `INCIDENTNUM`, `INCIDENTSTARTDATE`, `HAZARDTYPE`, `WHEREFIRESTARTEDONSTRUCTURE`, `WHATDIDFIRESTARTFROM`, `DEFENSIVEACTIONS`, `STRUCTURECATEGORY`, `NUMBEROFUNITPERSTRUCTURE`, `NOOUTBUILDINGSDAMAGED`, `NOOUTBUILDINGSNOTDAMAGED`, `NOOFCARSONPROPERTY`, `ROOFCONSTRUCTION`, `EAVES`, `VENTSCREEN`, `EXTERIORSIDING`, `WINDOWPANE`, `DECKPORCHONGRADE`, `DECKPORCHELEVATED`, `PATIOCOVERCARPORT`, `FENCEATTACHEDTOSTRUCTURE`, `PROPANETANKDISTANCE`, `UTILITYMISCSTRUCTUREDISTANCE`, `FIRENAME`, `APN`, `ASSESSEDIMPROVEDVALUE`, `YEARBUILT`, `SITEADDRESS`, `LATITUDE`, `LONGITUDE`

**DINS year built:** 373 rows outside 1800-2025 (mostly 0) set to null in `year_built_clean`.

**Hazard polygons in the LA bounding box before clipping:** `{'LRA / High': 209, 'LRA / Moderate': 230, 'LRA / NonWildland': 511, 'LRA / Very High': 104, 'SRA / High': 139, 'SRA / Moderate': 90, 'SRA / Very High': 337}`

