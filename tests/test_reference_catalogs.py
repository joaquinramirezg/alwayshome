"""Real public-reference regression checks; property observations are synthetic."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from msba_vibathon_2026.insurance_gap.catalogs import load_reference_catalogs
from msba_vibathon_2026.insurance_gap.alternatives import compare_alternatives
from msba_vibathon_2026.insurance_gap.requirements import match_requirements
from msba_vibathon_2026.insurance_gap.upgrades import estimate_upgrades

DAY = '2026-11-06'


def fact(value):
    return {'status': 'confirmed', 'value': value, 'source': {
        'reference': 'fixture://synthetic-property-observation', 'verified': True,
        'valid_from': DAY, 'valid_through': DAY}}


class ReferenceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.c = load_reference_catalogs()

    def match(self, facts, rules=None, selected=()):
        return match_requirements({'facts': facts}, self.c['requirements'] if rules is None else rules,
                                  selected_products=selected, county_fips='06037', as_of=DAY)

    def test_catalog_sizes_sources_and_unique_ids(self):
        for key, idkey, expected in [('products', 'product_id', 3), ('requirements', 'requirement_id', 23),
                                      ('costs', 'cost_id', 6), ('sources', 'source_id', 10)]:
            rows = self.c[key]
            self.assertEqual(len(rows), expected)
            self.assertEqual(len({r[idkey] for r in rows}), expected)
        for r in self.c['products']+self.c['requirements']+self.c['costs']:
            self.assertTrue(r['source']['reference'].startswith('https://'))
            self.assertEqual(r['source']['accessed_date'], DAY)
        self.c['products'][0]['name'] = 'changed locally'
        self.assertNotEqual(load_reference_catalogs()['products'][0]['name'], 'changed locally')

    def test_real_descriptions_never_quotes(self):
        r = compare_alternatives({}, self.c['products'], as_of=DAY, subject_id='TEST', county_fips='06037')
        self.assertEqual(r['status'], 'compared')
        for product in r['products']:
            self.assertEqual(product['status'], 'description_only')
            self.assertIsNone(product['annual_premium_usd'])
            self.assertEqual(product['eligibility'], 'not_determined')
        mercury = next(p for p in r['products'] if p['product_id']=='mercury_home_overview')
        self.assertTrue(all(f['alternative'] is None for f in mercury['features']))

    def test_fair_terms_no_false_ale_or_independent_debris_limit(self):
        fair = self.c['products'][0]
        self.assertIn('Fair rental value', fair['coverage_terms']['ale'])
        self.assertIn('damaged-property limits', fair['coverage_terms']['debris'])
        self.assertIsNone(fair['coverage_terms']['limits_usd'])
        self.assertIsNone(fair['coverage_terms']['effective_date'])

    def test_real_cdi_and_calfire_matching(self):
        r = self.match({'roof_class_a': fact(False), 'noncombustible_gutter_covers': fact(False)})
        by_id = {f['requirement_id']: f for f in r['findings']}
        self.assertEqual(by_id['cdi_roof_class_a']['classification'], 'potential_discount_condition')
        self.assertEqual(by_id['cdi_roof_class_a']['status'], 'improvement_needed')
        self.assertEqual(by_id['calfire_gutters']['classification'], 'recommendation')
        self.assertFalse(any(f['requirement_id'].startswith('fair_') for f in r['findings']))

    def test_fair_discount_only_when_selected(self):
        r = self.match({'fair_enclosed_eaves': fact(False)}, selected=['ca_fair_dwelling'])
        f = next(f for f in r['findings'] if f['requirement_id']=='fair_enclosed_eaves')
        self.assertEqual(f['classification'], 'potential_discount_condition')
        self.assertEqual(f['status'], 'improvement_needed')
        self.assertNotEqual(f['classification'], 'verified_requirement')

    def test_legal_rule_applicability_unknown_false_true(self):
        rule = next(r for r in self.c['requirements'] if r['requirement_id']=='calfire_applicable_dspace')
        for value, expected in [(None, 'unknown'), (False, 'not_applicable'), (True, 'improvement_needed')]:
            facts = {'defensible_space_compliant': fact(False)}
            if value is not None:
                facts['defensible_space_legal_applicability_confirmed'] = fact(value)
            finding = self.match(facts, rules=[rule])['findings'][0]
            self.assertEqual(finding['status'], expected)

    def test_unverified_entry_cannot_recommend(self):
        rule = deepcopy(self.c['requirements'][0])
        rule['verification_status'] = 'unverified'
        self.assertEqual(self.match({'roof_class_a':fact(False)}, rules=[rule])['findings'][0]['status'], 'unknown')
        rule['verification_status'] = 'verified_guidance'; rule['source']['verified'] = False
        self.assertEqual(self.match({'roof_class_a':fact(False)}, rules=[rule])['findings'][0]['status'], 'unknown')
        product = deepcopy(self.c['products'][0]); product['verification_status'] = 'unverified'
        r = compare_alternatives({}, [product], as_of=DAY, subject_id='TEST', county_fips='06037')
        self.assertEqual(r['products'][0]['status'], 'unverified_or_inapplicable')

    def test_unknown_property_does_not_schedule_upgrade(self):
        r = self.match({})
        self.assertTrue(all(f['status']=='unknown' for f in r['findings']))
        u = estimate_upgrades(r['findings'], self.c['costs'], county_fips='06037', jurisdiction='Los Angeles', as_of=DAY)
        self.assertEqual(u['projects'], [])
        self.assertIsNone(u['total_low_usd'])

    def test_historical_units_never_become_la_project_prices(self):
        r = self.match({'roof_class_a':fact(False), 'noncombustible_gutter_covers':fact(False)})
        u = estimate_upgrades(r['findings'], self.c['costs'], county_fips='06037', jurisdiction='Los Angeles', as_of=DAY)
        self.assertGreater(len(u['projects']), 0)
        self.assertIsNone(u['total_low_usd'])
        self.assertTrue(all(p['status']=='pricing_unavailable' for p in u['projects']))
        observations = [c for c in self.c['costs'] if c['verification_status']=='verified_historical_benchmark']
        self.assertEqual(len(observations), 5)
        self.assertTrue(all(c['scope_reviewed'] is False for c in observations))

    def test_snapshot_expiry_requires_reverification(self):
        r = compare_alternatives({}, self.c['products'], as_of='2026-11-07', subject_id='TEST', county_fips='06037')
        self.assertTrue(all(p['status']=='unverified_or_inapplicable' for p in r['products']))
        r = match_requirements({'facts':{'roof_class_a':fact(False)}}, self.c['requirements'],
            selected_products=[], county_fips='06037', as_of='2026-11-07')
        self.assertTrue(all(f['status']=='unknown' for f in r['findings']))


if __name__ == '__main__':
    unittest.main()
