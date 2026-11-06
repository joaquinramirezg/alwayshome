"""Run: .venv/bin/python -m unittest discover -s tests -v"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('wildfire', ROOT / 'scripts/build_wildfire_features.py')
w = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w)


class ScoringTests(unittest.TestCase):
    def test_zero_ties_missing_and_positive_order(self):
        result = w.positive_percentile(pd.Series([0, 0, 1, 1, 2, np.nan]))
        np.testing.assert_allclose(result[:5], [0, 0, .5, .5, 1])
        self.assertTrue(pd.isna(result.iloc[5]))
        with self.assertRaises(ValueError):
            w.positive_percentile(pd.Series([-1]))

    def test_missing_is_not_midpoint(self):
        f = pd.DataFrame({c: [0, np.nan] for c in w.SCORE_COLUMNS})
        f.loc[1, w.SCORE_COLUMNS[0]] = 1
        result = w.add_score(f)
        self.assertEqual(result.score_indicator_count.tolist(), [4, 1])
        self.assertEqual(result.relative_exposure_score_0_100.tolist(), [0, 100])
        self.assertTrue(pd.isna(w.add_score(pd.DataFrame(index=[0])).relative_exposure_score_0_100.iloc[0]))

    def test_zip_weight_direction_missing_and_zero_denominator(self):
        x = pd.DataFrame({'zip': ['90001'] * 2 + ['90002'],
                          'tract_geoid': ['a', 'b', 'a'], 'res_ratio': [.1, .3, 0]})
        t = pd.DataFrame({'tract_geoid': ['a', 'b'], 'value': [0., 100.],
                          'partial': [np.nan, 20.]})
        with tempfile.TemporaryDirectory() as tmp, patch.object(w, 'OUT', Path(tmp)), patch.object(w.pd, 'read_parquet', return_value=x):
            z = w.build_zip(t).set_index('zip')
        self.assertAlmostEqual(z.loc['90001', 'mean_value'], 75)
        self.assertAlmostEqual(z.loc['90001', 'la_residential_share'], .4)
        self.assertAlmostEqual(z.loc['90001', 'partial_residential_share'], .3)
        self.assertEqual(z.loc['90001', 'mean_partial'], 20)
        self.assertTrue(pd.isna(z.loc['90002', 'mean_value']))


class ProcessedDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = pd.read_parquet(w.DATA / 'tract_wildfire_features.parquet')
        cls.z = pd.read_parquet(w.DATA / 'zip_wildfire_features.parquet')
        cls.tr = w.load_tracts()

    def test_geographic_coverage(self):
        self.assertEqual(len(self.t), 2498)
        self.assertTrue(self.t.tract_geoid.is_unique)
        self.assertEqual(set(self.t.tract_geoid), set(self.tr.tract_geoid))
        self.assertTrue(self.tr.is_valid.all())
        self.assertTrue((self.t.tract_area_km2 > 0).all())
        x = pd.read_parquet(w.DATA / 'zip_tract_crosswalk.parquet')
        self.assertEqual(set(self.z.zip), set(x.zip))
        self.assertEqual(len(self.z), 477)
        self.assertTrue(self.z.zip.is_unique)
        self.assertTrue(self.z.la_residential_share.between(0, 1.00001).all())

    def test_fema_missing_and_score(self):
        n = pd.read_parquet(w.DATA / 'nri_tracts.parquet')
        self.assertEqual(set(n.tract_geoid) - set(self.t.tract_geoid), set())
        self.assertEqual(set(self.t.loc[~self.t.nri_record_available, 'tract_geoid']),
                         {'06037990100', '06037990200', '06037990300'})
        pd.testing.assert_series_equal(self.t.relative_exposure_score_0_100,
                                      w.add_score(self.t).relative_exposure_score_0_100)
        self.assertEqual(self.t.relative_exposure_score_0_100.min(), 0)
        self.assertTrue(self.t.relative_exposure_score_0_100.between(0, 100).all())
        for c in [c for c in self.t if c.endswith('_pct')]:
            self.assertTrue(self.t[c].between(0, 100).all(), c)
        zero = self.t[w.SCORE_COLUMNS].eq(0).all(axis=1)
        self.assertTrue((self.t.loc[zero, 'relative_exposure_score_0_100'] == 0).all())

    def test_fire_outlier_independent_geometry_check(self):
        fires = gpd.read_parquet(w.DATA / 'fire_perimeters.parquet').to_crs(w.AREA_CRS)
        geom = self.tr.set_index('tract_geoid').loc['06037930400'].geometry
        hits = fires[fires.intersects(geom)]
        self.assertEqual(len(hits), 253)
        self.assertTrue((hits.intersection(geom).area > 0).all())
        self.assertFalse(fires.geometry.to_wkb().duplicated().any())
        self.assertEqual(self.t.set_index('tract_geoid').loc['06037930400', 'fire_intersections'], len(hits))
        for c in (2000, 2015, 2020):
            expected = (hits.year >= c).sum()
            self.assertEqual(self.t.set_index('tract_geoid').loc['06037930400', f'fire_intersections_since_{c}'], expected)
        self.assertTrue((self.t.fire_intersections_since_2020 <= self.t.fire_intersections_since_2015).all())

    def test_zip_reproduction(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(w, 'OUT', Path(tmp)):
            rebuilt = w.build_zip(self.t)
        pd.testing.assert_frame_equal(self.z, rebuilt)


if __name__ == '__main__':
    unittest.main()
