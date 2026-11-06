# Wildfire exposure features and validation

Validated November 6, 2026 on `feature/wildfire-risk`.

Reproduce from the repository root:

```sh
.venv/bin/python scripts/build_wildfire_features.py
.venv/bin/python -m unittest discover -s tests -v
```

The builder regenerates `data/processed/tract_wildfire_features.parquet` and
`zip_wildfire_features.parquet`. Source processed tables are unchanged. No API,
model call, or network access is used. Tract boundaries come from the existing
local LA GeoParquet cache, or the local 2024 California Census cartographic
boundary archive if the cache is absent. That archive must be supplied locally;
the builder does not download it. Seven automated tests pass.

## Geographic coverage

There are 2,498 unique LA County tract geometries (11-digit IDs beginning 06037),
including special-use tracts. Cached boundaries are valid, nonempty, and have
positive projected area. All 2,495 processed FEMA tract IDs match these boundaries.
All tract IDs in the ZIP-to-tract crosswalk also match. The three boundary tracts
without FEMA records are `06037990100`, `06037990200`, and `06037990300`.
They are not imputed, dropped, or assigned zero FEMA loss. Their scores use three
indicators, versus four for other tracts; `score_indicator_count` and
`nri_record_available` expose that difference. FEMA's `WFIR_EVNTS` is entirely
missing and is retained as missing, not used in scoring.

This updates the older crosswalk-only coverage note in the general data dictionary:
`06037980020` is present in these boundary-based tract features, even though it
has no ZIP crosswalk match. It contributes no ZIP summary. Boundary coverage is
validated against the supplied local cache, not independently certified against
a second Census download. Census cartographic boundaries are generalized, not
parcel boundaries. HUD uses 2020 tract geography; the boundary archive is the
2024 cartographic release. Matching identifiers do not independently prove
identical geometry across releases. Areas use EPSG:3310, California Albers.

## Exposure measurements

Hazard percentages are tract area intersected with the union of polygons of each
severity class, divided by tract area. Overlaps within a class are counted once.
Classes are computed independently; their sum is not guaranteed to be disjoint
across source maps. Percentages are rounded to three decimals. Moderate hazard is
retained as context but is not a scoring component. A zero mapped hazard share
means no overlap in this dataset, not absence of wildfire risk. Source map adoption
and simplification caveats in `data_dictionary.md` still apply.

Historical counts use spatial `intersects`: one count per source perimeter record
per tract, including a boundary touch. They do not count unique named incidents
or repeated burns at an individual house. Source names and years cannot uniquely
identify an incident. Counts since 2000, 2015, and 2020 include their cutoff year;
last fire year is null for a tract without a dated intersection. Burned footprint
uses the union of all source perimeters, so repeated burns do not inflate area.
The processed source contains 2,321 perimeter records, from 1950 onward within
the county's buffered study area. No recency decay or fire count enters the score.

The outlier `06037930400` covers **1,494.503 km²**. Direct intersection checks
confirm **253** source records, all with positive overlap area, spanning 1951–2025.
Its unioned historical footprint covers **94.626%**. There are no exact duplicate
perimeter geometries in the source. The outlier is retained: its large tract area
explains why it can intersect many perimeters. This is not evidence of 253 fires
at any home, and distinct source records may still describe related incidents.
All input fire, hazard, and boundary geometries passed validity checks during audit.

## Score correction

The previous formula ranked zeros with ordinary average percentile ranks. Large
zero ties produced a substantial positive baseline; missing values were then
assigned an unsupported 50th percentile. This explains the old 39.2–95.8 range.

Version 2 keeps the original four indicators to isolate that correction:
very-high hazard area share, high hazard area share, historical burned footprint
share, and FEMA wildfire expected annual loss (`WFIR_EALT`). For each indicator:

1. Observed zero maps to zero.
2. Positive values receive their average rank among positive observations divided
   by the number of positive observations (ties share a rank).
3. Missing values remain missing.

The score is 100 times the mean of available indicator components, rounded to one
decimal. All-missing rows produce a null score. Weights are an explicit prototype
assumption: equal weights across available indicators. No missing midpoint is
invented. Scores now span **0–79.5**, with **1,614** zero-score tracts. Scores need
not reach 100 because each component's maximum can occur in a different tract.

This is a descriptive index relative to these LA County data, not a calibrated
probability, county-wide percentile, property inspection, underwriting decision,
premium estimate, or validated prediction. A zero score means zeros in the selected
observed indicators. FEMA expected annual loss includes exposed value, is highly
skewed, and has 1,783 observed zero values; it is not a pure hazard measure. Its
source limitations near the 2025 fires remain applicable. Correlated indicators,
omission of Moderate hazard from scoring, separate High/Very High ranks, and
changing positive reference populations affect comparisons. No claim of predictive
accuracy or causal benefit from mitigation is made. Use source components alongside
the index; scores with different availability are not strictly comparable.

## ZIP summaries

The output preserves all **477** ZIPs. Previous summaries were unweighted means
of crosswalk-linked tracts. Version 2 uses `zip_tract_crosswalk.res_ratio`: the
fraction of each ZIP's residential addresses in a tract. The opposite-direction
`tract_zip_crosswalk` ratios allocate tract totals; they cannot directly weight a
ZIP mean without tract address counts.

For each numeric feature, `mean_<feature>` is `sum(weight * value) / sum(weight)`
over nonmissing values with positive residential weight. `<feature>_residential_share`
is that denominator, in shares of the entire ZIP, not a normalized percentage.
`la_residential_share` gives the county crosswalk's full residential weight;
`matched_residential_share` gives the boundary-matched weight. `tract_count` counts
all linked tract IDs, including zero-weight links. Area is excluded from means.
Mean fire counts, years, FEMA losses and indicator counts are descriptive averages,
not unique ZIP fire counts, latest ZIP fire years, allocated dollar totals, or
building-level measurements. These means are retained for compatibility and must
be interpreted by their `mean_` prefix.

All crosswalk tracts match boundaries. **22** ZIPs have positive but incomplete
county residential coverage (sum below 0.99999), so their means describe the LA
portion only. **41** ZIPs have zero residential weight: their means stay null, with
no unweighted fallback. Available ZIP mean scores span **0–70.9**. Missing feature
values use separate denominators and are never treated as zero. Address weighting
assumes each tract's feature represents all residential addresses in that tract;
it does not locate homes within hazard polygons and is not population weighting.

## Automated checks

Tests cover zero ties, positive ordering, negative-value rejection, missing and
all-missing scores, direction-specific ZIP weights, partial and zero denominators,
tract/ZIP uniqueness and coverage, geometry validity, FEMA joins, score and area
bounds, direct geometry verification of the 253-record outlier and its recent
counts, temporal count nesting, and deterministic ZIP output reproduction.
Counts are dataset-specific regression checks: a source refresh should trigger
review of expected coverage and this report, rather than silently accepting drift.

## Teammate setup and data dependencies

Install the locked Python environment with `uv sync` (Python 3.14 or newer),
then run the reproduction commands above. The committed outputs are ready to read;
regeneration needs no download when the committed input files are present.

Required inputs, all included in Git:

- `data/processed/la_tract_boundaries.parquet`: LA-only boundary cache, about 4.4 MB.
- `data/processed/hazard_zones.parquet`: processed hazard polygons.
- `data/processed/fire_perimeters.parquet`: processed historical fire polygons.
- `data/processed/nri_tracts.parquet`: LA-only FEMA records.
- `data/processed/zip_tract_crosswalk.parquet`: ZIP residential weights.

The two committed feature outputs total about 0.5 MB. The statewide Census ZIP
archive is deliberately excluded from this commit; teammates do not need it.
If rebuilding the boundary cache itself, download
`https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_06_tract_500k.zip`
to `data/processed/census_tracts_2024_ca.zip` and run the builder with the cache
absent. It filters to state 06, county 037 and writes the LA cache. Do not add the
statewide archive to Git. Source provenance and regeneration of the other processed
inputs are covered by `docs/data_dictionary.md`, `scripts/01_download.py`, and
`scripts/02_process.py`; rebuilding those sources requires their documented raw
or manual downloads, including the FEMA national extract and HUD crosswalks.
Those large/manual sources are unnecessary for rerunning this feature builder.
