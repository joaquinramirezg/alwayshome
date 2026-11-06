"""Build LA County tract/ZIP wildfire exposure features from processed Vibathon data.
Run from repository root: .venv/bin/python scripts/build_wildfire_features.py
Requires geopandas, pandas, numpy, pyarrow and the committed LA tract boundary cache.
"""
from pathlib import Path
import re
import numpy as np
import pandas as pd
import geopandas as gpd

DATA = Path(__file__).resolve().parents[1] / 'data/processed'
OUT = DATA
AREA_CRS = 'EPSG:3310'  # California Albers equal-area meters
TRACT_URL = 'https://www2.census.gov/geo/tiger/GENZ2024/shp/cb_2024_06_tract_500k.zip'


def pick(df, *candidates):
    lookup = {re.sub(r'[^a-z0-9]', '', str(c).lower()): c for c in df.columns}
    for candidate in candidates:
        key = re.sub(r'[^a-z0-9]', '', candidate.lower())
        if key in lookup:
            return lookup[key]
    return None


def geoid(series, width):
    return series.astype('string').str.replace(r'\.0$', '', regex=True).str.extract(r'(\d+)', expand=False).str.zfill(width).str[-width:]


def load_tracts():
    cache = DATA / 'la_tract_boundaries.parquet'
    if cache.exists():
        tr = gpd.read_parquet(cache)
    else:
        print('Reading local Census tract geometry archive...')
        tr = gpd.read_file(DATA / 'census_tracts_2024_ca.zip')
        tr = tr[(tr['STATEFP'] == '06') & (tr['COUNTYFP'] == '037')].copy()
        tr = tr[['GEOID', 'geometry']]
        tr.to_parquet(cache)
    tr['tract_geoid'] = geoid(tr['GEOID'], 11)
    tr = tr[['tract_geoid', 'geometry']].dropna(subset=['geometry'])
    if tr.tract_geoid.duplicated().any() or not tr.tract_geoid.str.fullmatch(r'06037\d{6}').all():
        raise ValueError('Tract boundaries must have unique LA County identifiers')
    if tr.crs is None or not tr.is_valid.all() or tr.geometry.is_empty.any():
        raise ValueError('Invalid tract geometry or missing CRS')
    return tr.to_crs(AREA_CRS)


def polygon_union_features(tracts, filepath, prefix, class_column=None):
    if not filepath.exists():
        print('Missing optional:', filepath)
        return pd.DataFrame({'tract_geoid': tracts['tract_geoid']})
    polys = gpd.read_parquet(filepath)
    polys = polys[polys.geometry.notna() & ~polys.geometry.is_empty].copy()
    polys = polys.to_crs(AREA_CRS)
    # Clip once to county footprint to reduce work, then overlay tract by tract.
    if class_column:
        c = pick(polys, class_column)
        if not c:
            raise ValueError(f'{filepath}: cannot find {class_column}; columns={polys.columns.tolist()}')
        polys['_class'] = polys[c].astype(str).str.lower().str.strip()
    else:
        polys['_class'] = 'all'
    tr = tracts[['tract_geoid', 'geometry']].copy()
    # Overlay intersection can count overlaps more than once; dissolve before area calculation.
    out = tr[['tract_geoid']].copy()
    for cls in sorted(polys['_class'].unique()):
        part = polys.loc[polys['_class'] == cls, ['geometry']]
        if part.empty:
            continue
        dissolved = part.geometry.union_all()
        # Intersection per tract is robust to overlapping source polygons.
        intersection = tr.geometry.intersection(dissolved)
        frac = (intersection.area / tr.geometry.area).clip(0, 1).fillna(0)
        suffix = re.sub(r'[^a-z0-9]+', '_', cls).strip('_')
        out[f'{prefix}_{suffix}_pct'] = (100 * frac).round(3).to_numpy()
    return out


def fire_features(tracts):
    path = DATA / 'fire_perimeters.parquet'
    out = tracts[['tract_geoid']].copy()
    if not path.exists():
        return out
    fires = gpd.read_parquet(path).to_crs(AREA_CRS)
    year_col = pick(fires, 'fire_year', 'year', 'fireyear', 'alarm_date', 'alarmdate', 'incident_date', 'incidentdate', 'date', 'year_')
    if year_col:
        if 'year' in year_col.lower():
            fires['_year'] = pd.to_numeric(fires[year_col], errors='coerce')
        else:
            fires['_year'] = pd.to_datetime(fires[year_col], errors='coerce').dt.year
    else:
        print('WARNING: fire year not detected; using all-year fire features only.')
        fires['_year'] = np.nan
    fires = fires[fires.geometry.notna() & ~fires.geometry.is_empty].copy().reset_index(drop=True)
    fires['_fire_id'] = np.arange(len(fires))
    print('Fire year field:', year_col, '| records:', len(fires))
    # Spatial join: one row per fire/tract intersection.
    matches = gpd.sjoin(fires[['_fire_id', '_year', 'geometry']], tracts[['tract_geoid', 'geometry']], how='inner', predicate='intersects')
    counts = matches.groupby('tract_geoid').agg(fire_intersections=('_fire_id', 'nunique'), last_fire_year=('_year', 'max')).reset_index()
    out = out.merge(counts, on='tract_geoid', how='left')
    out['fire_intersections'] = out['fire_intersections'].fillna(0).astype(int)
    for cutoff in (2000, 2015, 2020):
        recent = matches[matches['_year'] >= cutoff].groupby('tract_geoid')['_fire_id'].nunique()
        out[f'fire_intersections_since_{cutoff}'] = out['tract_geoid'].map(recent).fillna(0).astype(int)
    # Distinct burned footprint (all years), unioned to avoid double-counting overlaps.
    burned = fires.geometry.union_all()
    out['historical_burned_footprint_pct'] = (100 * tracts.geometry.intersection(burned).area / tracts.geometry.area).clip(0, 100).round(3).to_numpy()
    return out


def nri_features():
    path = DATA / 'nri_tracts.parquet'
    if not path.exists():
        return None
    nri = pd.read_parquet(path)
    key = pick(nri, 'tract_geoid', 'geoid', 'tractfips', 'tract_fips', 'tract', 'stcofips')
    if key is None:
        print('WARNING: NRI tract identifier not found:', nri.columns.tolist())
        return None
    nri['tract_geoid'] = geoid(nri[key], 11)
    fields = [c for c in nri.columns if str(c).upper().startswith('WFIR_')]
    selected = ['tract_geoid'] + fields
    print('NRI wildfire columns:', fields)
    if nri.tract_geoid.duplicated().any():
        raise ValueError('Duplicate FEMA tract identifiers')
    result = nri[selected].rename(columns={c: 'nri_' + c.lower() for c in fields})
    result['nri_record_available'] = True
    return result


SCORE_COLUMNS = ['hazard_very_high_pct', 'hazard_high_pct',
                 'historical_burned_footprint_pct', 'nri_wfir_ealt']
SCORE_METHOD = 'v2: zero-anchored positive percentile; equal available indicator weights; descriptive'


def positive_percentile(values):
    """Observed zero -> 0; positives ranked only against positives; missing stays missing."""
    values = pd.to_numeric(values, errors='coerce')
    if (values.dropna() < 0).any():
        raise ValueError('Exposure indicators must be nonnegative')
    result = values.where(values.isna(), 0.0).astype(float)
    positive = values > 0
    result.loc[positive] = values.loc[positive].rank(pct=True, method='average')
    return result


def add_score(features):
    parts = pd.DataFrame({c: positive_percentile(features[c]) if c in features
                          else pd.Series(np.nan, index=features.index)
                          for c in SCORE_COLUMNS})
    features = features.copy()
    features['score_indicator_count'] = parts.notna().sum(axis=1)
    features['relative_exposure_score_0_100'] = (100 * parts.mean(axis=1)).round(1)
    features['risk_score_method'] = SCORE_METHOD
    features['nri_record_available'] = features.get(
        'nri_record_available', pd.Series(False, index=features.index)).fillna(False).astype(bool)
    return features


def build_zip(tract):
    # Direction matters: ZIP-TRACT ratios are shares of ZIP addresses, not tract shares.
    x = pd.read_parquet(DATA / 'zip_tract_crosswalk.parquet')
    if x.duplicated(['zip', 'tract_geoid']).any():
        raise ValueError('Duplicate ZIP/tract crosswalk pairs')
    if x.res_ratio.isna().any() or not x.res_ratio.between(0, 1).all():
        raise ValueError('Invalid residential crosswalk weights')
    merged = x.merge(tract.drop(columns=['geometry'], errors='ignore'),
                     on='tract_geoid', how='left', validate='many_to_one', indicator=True)
    groups = merged.groupby('zip')
    z = groups.agg(tract_count=('tract_geoid', 'nunique'),
                   la_residential_share=('res_ratio', 'sum'))
    merged['_matched_weight'] = merged.res_ratio.where(merged['_merge'] == 'both', 0)
    z['matched_residential_share'] = merged.groupby('zip')._matched_weight.sum()
    numeric = tract.select_dtypes(include='number').columns.difference(['tract_area_km2'])
    for c in numeric:
        # Separate denominator for every field: missing is never treated as zero.
        weights = merged.res_ratio.where(merged[c].notna(), 0)
        denom = weights.groupby(merged.zip).sum()
        numerator = (merged[c].fillna(0) * weights).groupby(merged.zip).sum()
        z['mean_' + c] = numerator / denom.where(denom > 0)
        z[c + '_residential_share'] = denom
    z = z.reset_index()
    z.to_parquet(OUT / 'zip_wildfire_features.parquet', index=False)
    print('Saved ZIP features | ZIPs:', len(z))
    return z


def main():
    tr = load_tracts()
    tr['tract_area_km2'] = tr.geometry.area / 1e6
    features = tr[['tract_geoid', 'tract_area_km2']].copy()
    hazards = polygon_union_features(tr, DATA / 'hazard_zones.parquet', 'hazard', 'hazard_class')
    features = features.merge(hazards, on='tract_geoid', how='left')
    fires = fire_features(tr)
    features = features.merge(fires, on='tract_geoid', how='left')
    nri = nri_features()
    if nri is not None:
        features = features.merge(nri, on='tract_geoid', how='left')
    features = add_score(features)
    features.to_parquet(OUT / 'tract_wildfire_features.parquet', index=False)
    print('Saved tract_wildfire_features.parquet | tracts:', len(features), '| fields:', features.columns.tolist())
    build_zip(features)


if __name__ == '__main__':
    main()
