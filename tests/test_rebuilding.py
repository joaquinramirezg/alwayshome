"""SYNTHETIC FIXTURES ONLY: amounts are arithmetic examples, NOT LA prices."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from msba_vibathon_2026.rebuilding import CATEGORIES, estimate_rebuilding


def fixture():
    """Entire fixture, including source/reviewer, is fictional test data."""
    req = {
        'mode': 'documented', 'address': 'SYNTHETIC TEST HOUSE',
        'location': {'county_fips': '06037', 'permitting_jurisdiction': 'TEST JURISDICTION',
                     'jurisdiction_verified': True},
        'home': {'living_area_sqft': 1000, 'area_definition': 'finished_living_area',
                 'area_confirmed': True, 'area_source': 'synthetic plans', 'stories': 2,
                 'year_built': 1980, 'dwelling_type': 'detached_site_built_single_family',
                 'unit_count': 1, 'construction_type': 'test_frame', 'foundation_type': 'test_slab',
                 'features_reviewed': True, 'materials': {'roof': 'test_roof', 'exterior': 'test_siding'},
                 'quality': {'source_category': 'test_standard', 'description': 'synthetic finish',
                             'homeowner_confirmed': True}},
        'site': {'screening_complete': True, 'requires_specialist': False},
        'estimate_context': {'estimate_as_of': '2026-11-06', 'target_price_date': '2026-11-01',
                             'permit_date_assumption': '2026-11-06', 'currency': 'USD',
                             'market_scenario': 'ordinary_current', 'rebuild_scope': 'equivalent_size_quality'},
    }
    e = {
        'evidence_id': 'synthetic-only', 'source_id': 'TEST-NOT-REAL-PRICING',
        'source_url_or_document_ref': 'fixture://fictional-quote',
        'quoted_address': 'SYNTHETIC TEST HOUSE', 'quoted_living_area_sqft': 1000,
        'scope_description': 'Synthetic complete building scope; test purposes only',
        'reviewer': 'fictional reviewer', 'publication_date': '2026-11-01',
        'price_base_date': '2026-11-01', 'year': 2026, 'reviewed_at': '2026-11-02',
        'valid_through': '2026-11-30', 'verification_status': 'full_document_verified',
        'parameter_status': 'approved_for_this_scope', 'county_fips': '06037',
        'permitting_jurisdiction': 'TEST JURISDICTION', 'quality': 'test_standard',
        'construction_type': 'test_frame', 'stories': 2, 'area_definition': 'finished_living_area',
        'property_scope': 'detached_site_built_single_family', 'currency': 'USD',
        'market_scenario': 'ordinary_current', 'rebuild_scope': 'equivalent_size_quality',
        'building_scope_confirmed': True, 'unit': 'USD_per_finished_sqft',
        'includes': ['construction', 'contractor_overhead_profit'],
        'excludes': list(CATEGORIES[2:]), 'size_band_sqft': [900, 1100],
        'scenarios': {'central': {'base_value': '100', 'rationale': 'Synthetic arithmetic case',
            'assumptions': ['All amounts are synthetic test fixtures.'], 'items': []}},
    }
    for cat, amount in [('demolition_debris', 10000), ('professional_services', 5000),
                         ('permits_agency_fees', 2000), ('incremental_code', 3000),
                         ('extraordinary_site_utilities', 4000)]:
        e['scenarios']['central']['items'].append({'category': cat, 'scope_state': 'separately_priced',
            'amount_usd': amount, 'documentation': 'Synthetic quote item; no real-world pricing'})
    for cat in ('incremental_disaster_pressure', 'contingency'):
        e['scenarios']['central']['items'].append({'category': cat,
            'scope_state': 'not_applicable_verified', 'documentation': 'Synthetic scenario explicitly excludes allowance'})
    req['cost_evidence'] = e
    return req


class RebuildingTests(unittest.TestCase):
    def test_standard_and_no_story_multiplier(self):
        result = estimate_rebuilding(fixture())
        self.assertEqual(result['status'], 'complete_planning_estimate')
        self.assertEqual(result['estimated_rebuilding_cost_usd'], '124000')
        self.assertIsNone(result['scenarios']['low'])
        self.assertFalse(result['coverage_comparison_ready'])
        json.dumps(result, allow_nan=False)

    def test_missing_rate_and_empty_catalog(self):
        req = fixture()
        del req['cost_evidence']['scenarios']['central']['base_value']
        self.assertEqual(estimate_rebuilding(req)['status'], 'needs_cost_evidence')
        req['mode'] = 'benchmark'
        req['benchmark_id'] = 'not-available'
        self.assertEqual(estimate_rebuilding(req)['status'], 'pricing_unavailable')
        req['mode'] = 'documented'
        del req['cost_evidence']
        self.assertEqual(estimate_rebuilding(req)['status'], 'needs_cost_evidence')

    def test_missing_components_are_not_zero(self):
        req = fixture()
        req['cost_evidence']['scenarios']['central']['items'] = []
        r = estimate_rebuilding(req)
        self.assertEqual(r['status'], 'incomplete_scope')
        self.assertIsNone(r['estimated_rebuilding_cost_usd'])
        self.assertIsNone(r['scenarios']['central']['reconstruction_total_usd'])
        self.assertEqual(r['scenarios']['central']['known_cost_subtotal_usd'], '100000')
        self.assertIn('scenarios.central.demolition_debris', r['missing_inputs'])

    def test_bad_square_footage(self):
        for area in [0, -1, True, 'nan', 'Infinity', 'abc']:
            with self.subTest(area=area):
                req = fixture(); req['home']['living_area_sqft'] = area
                self.assertEqual(estimate_rebuilding(req)['status'], 'invalid_input')
        req = fixture(); req['home']['living_area_sqft'] = None
        self.assertEqual(estimate_rebuilding(req)['status'], 'needs_property_inputs')

    def test_double_counting_and_duplicate_categories(self):
        for item in [
            {'category': 'contractor_overhead_profit', 'scope_state': 'separately_priced',
             'amount_usd': 100, 'documentation': 'test'},
            {'category': 'contractor_overhead_profit', 'scope_state': 'included_in_base', 'amount_usd': 100},
            {'category': 'demolition_debris', 'scope_state': 'not_applicable_verified', 'documentation': 'test'},
        ]:
            req = fixture(); req['cost_evidence']['scenarios']['central']['items'].append(item)
            self.assertEqual(estimate_rebuilding(req)['status'], 'invalid_input')

    def test_scenarios_and_order(self):
        req = fixture(); s = req['cost_evidence']['scenarios']
        for name, rate in [('low', 90), ('high', 120)]:
            s[name] = deepcopy(s['central']); s[name]['base_value'] = rate
        r = estimate_rebuilding(req)
        self.assertEqual([r['scenarios'][s]['reconstruction_total_usd'] for s in ('low', 'central', 'high')],
                         ['114000', '124000', '144000'])
        s['low']['base_value'] = 200
        self.assertEqual(estimate_rebuilding(req)['status'], 'invalid_input')

    def test_mismatch_and_unverified_evidence(self):
        for key, value in [('quoted_address', 'OTHER TEST HOUSE'), ('quoted_living_area_sqft', 2000),
                           ('quality', 'luxury'), ('county_fips', '06059'),
                           ('permitting_jurisdiction', 'different city'), ('stories', 1),
                           ('construction_type', 'other'), ('unit', 'index_points'),
                           ('area_definition', 'footprint'), ('parameter_status', 'context_only'),
                           ('verification_status', 'indexed_extract_only'),
                           ('valid_through', '2026-10-01'), ('price_base_date', '2025-11-01')]:
            with self.subTest(key=key):
                req = fixture(); req['cost_evidence'][key] = value
                r = estimate_rebuilding(req)
                self.assertIn(r['status'], ('needs_cost_evidence', 'invalid_input'))
                self.assertIsNone(r['estimated_rebuilding_cost_usd'])

    def test_lump_sum_and_all_in_quote(self):
        req = fixture(); e = req['cost_evidence']; e['unit'] = 'USD_lump_sum'
        e['scenarios']['central']['base_value'] = 100000
        self.assertEqual(estimate_rebuilding(req)['estimated_rebuilding_cost_usd'], '124000')
        e['includes'] = list(CATEGORIES); e['excludes'] = []
        e['scenarios']['central']['base_value'] = 124000
        e['scenarios']['central']['items'] = []
        r = estimate_rebuilding(req)
        self.assertEqual(r['estimated_rebuilding_cost_usd'], '124000')
        self.assertEqual(r['scenarios']['central']['component_totals']['demolition_debris']['scope_state'], 'included_in_base')

    def test_benchmark_catalog_and_size(self):
        req = fixture(); e = deepcopy(req.pop('cost_evidence'))
        req.update(mode='benchmark', benchmark_id=e['evidence_id'])
        self.assertEqual(estimate_rebuilding(req, benchmarks=[e])['estimated_rebuilding_cost_usd'], '124000')
        e['size_band_sqft'] = [1100, 1200]
        self.assertEqual(estimate_rebuilding(req, benchmarks=[e])['status'], 'pricing_unavailable')
        e['size_band_sqft'] = [900, 1100]; e['parameter_status'] = 'context_only'
        self.assertEqual(estimate_rebuilding(req, benchmarks=[e])['status'], 'pricing_unavailable')

    def test_reproducible_nonmutating_and_unrelated_insurance_ignored(self):
        req = fixture(); before = deepcopy(req)
        self.assertEqual(estimate_rebuilding(req), estimate_rebuilding(req))
        self.assertEqual(req, before)
        req['insurance'] = {'dwelling_limit': 1, 'market_value': 99999999}
        self.assertEqual(estimate_rebuilding(req)['estimated_rebuilding_cost_usd'], '124000')

    def test_property_scope_and_missing_screening(self):
        req = fixture(); req['location']['county_fips'] = '06059'
        self.assertEqual(estimate_rebuilding(req)['status'], 'out_of_scope')
        req = fixture(); req['site']['requires_specialist'] = True
        self.assertEqual(estimate_rebuilding(req)['status'], 'professional_review_required')
        req = fixture(); req['home']['quality']['homeowner_confirmed'] = False
        self.assertEqual(estimate_rebuilding(req)['status'], 'needs_property_inputs')

    def test_bad_costs_dates_and_undocumented_allowances(self):
        for value in [-1, 'NaN', True]:
            req = fixture(); req['cost_evidence']['scenarios']['central']['items'][0]['amount_usd'] = value
            self.assertEqual(estimate_rebuilding(req)['status'], 'invalid_input')
        req = fixture(); del req['cost_evidence']['scenarios']['central']['items'][0]['documentation']
        self.assertEqual(estimate_rebuilding(req)['status'], 'invalid_input')
        req = fixture(); req['estimate_context']['estimate_as_of'] = 'not-date'
        self.assertEqual(estimate_rebuilding(req)['status'], 'invalid_input')

    def test_explicit_unresolved_and_no_central_invention(self):
        req = fixture(); e = req['cost_evidence']
        item = e['scenarios']['central']['items'][0]
        item.update(scope_state='unresolved', amount_usd=None)
        self.assertEqual(estimate_rebuilding(req)['status'], 'incomplete_scope')
        self.assertIsNone(estimate_rebuilding(req)['estimated_rebuilding_cost_usd'])
        req = fixture(); e = req['cost_evidence']
        e['scenarios']['high'] = e['scenarios'].pop('central')
        r = estimate_rebuilding(req)
        self.assertEqual(r['status'], 'complete_planning_estimate')
        self.assertIsNone(r['estimated_rebuilding_cost_usd'])
        self.assertIsNone(r['scenarios']['central'])
        self.assertEqual(r['scenarios']['high']['reconstruction_total_usd'], '124000')

    def test_adjustments_and_bad_scope_rejected(self):
        for field in ('location_adjustment', 'time_adjustment'):
            req = fixture(); req['cost_evidence'][field] = {'factor': 1.1}
            self.assertEqual(estimate_rebuilding(req)['status'], 'needs_cost_evidence')
        req = fixture(); req['cost_evidence']['excludes'].append('construction')
        self.assertEqual(estimate_rebuilding(req)['status'], 'invalid_input')
        req = fixture(); req['cost_evidence']['scenarios']['central']['items'][0]['category'] = 'land'
        self.assertEqual(estimate_rebuilding(req)['status'], 'invalid_input')

    def test_malformed_requests_return_status(self):
        for request in (None, [], {}, {'mode': 'documented', 'home': []}):
            with self.subTest(request=request):
                self.assertEqual(estimate_rebuilding(request)['status'], 'invalid_input')

    def test_decimal_precision(self):
        req = fixture(); e = req['cost_evidence']; e['includes'] = list(CATEGORIES); e['excludes'] = []
        e['scenarios']['central'].update(base_value='0.1', items=[])
        req['home']['living_area_sqft'] = '1000.1'
        e['quoted_living_area_sqft'] = '1000.1'
        self.assertEqual(estimate_rebuilding(req)['estimated_rebuilding_cost_usd'], '100.01')


if __name__ == '__main__':
    unittest.main()
