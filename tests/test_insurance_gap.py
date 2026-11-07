"""Every source, product, rule and price below is SYNTHETIC TEST DATA ONLY."""
from copy import deepcopy
from decimal import getcontext
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from msba_vibathon_2026.insurance_gap import analyze_insurance_gap, map_rebuild_need
from msba_vibathon_2026.insurance_gap.coverage import analyze_coverage
from msba_vibathon_2026.insurance_gap.alternatives import compare_alternatives
from msba_vibathon_2026.insurance_gap.requirements import match_requirements
from msba_vibathon_2026.insurance_gap.upgrades import estimate_upgrades


def source():
    return {'reference': 'fixture://SYNTHETIC-NOT-REAL-EVIDENCE', 'verified': True,
            'valid_from': '2026-01-01', 'valid_through': '2026-12-31'}


def fixture():
    needs, covers = {}, {}
    for cat, need, limit in [('dwelling', '200000', '150000'), ('ale', '30000', '20000'),
                              ('ordinance_law', '10000', '5000'), ('debris', '10000', '10000')]:
        needs[cat] = {'amount_usd': need, 'scope_id': cat+'-test-scope', 'source': source()}
        covers[cat] = {'status': 'present', 'limit_usd': limit, 'scope_id': cat+'-test-scope',
                       'limit_basis': 'standalone', 'source': source()}
    covers['dwelling']['settlement'] = 'replacement_cost'
    needs['ale']['duration_months'] = '24'; covers['ale']['duration_months'] = '12'
    payload = {'schema_version': 'gap-v1', 'as_of': '2026-11-06', 'currency': 'USD', 'subject_id': 'TEST-HOME',
        'property': {'subject_id': 'TEST-HOME', 'county_fips': '06037', 'jurisdiction': 'TEST-CITY',
                     'facts': {'vent_type': {'status': 'confirmed', 'value': 'test_old', 'source': source()}}},
        'policy': {'subject_id': 'TEST-HOME', 'source': source(), 'terms_reviewed': True,
            'exclusions_reviewed': True, 'coverages': covers, 'exclusions': [], 'endorsements': [],
            'extended_replacement': {'kind': 'percentage', 'value': '25', 'conditions_verified': True,
                                     'scope_id': 'dwelling-test-scope', 'source': source()},
            'deductible': {'kind': 'fixed', 'amount_usd': '1000', 'source': source()},
            'features': {'test_wildfire_feature': {'value': False, 'source': source()}},
            'premium': {'annual_premium_usd': '2000', 'currency': 'USD',
                        'comparison_basis': 'test-annual-period', 'source': source()}},
        'needs': needs, 'selected_product_ids': ['TEST-PRODUCT']}
    products = [{'product_id': 'TEST-PRODUCT', 'name': 'SYNTHETIC product, not an insurer',
        'evidence_type': 'public_description', 'county_fips': ['06037'], 'source': source(),
        'features': {'test_wildfire_feature': {'value': True, 'source': source()}},
        'coverage_terms': {'description': 'Synthetic higher protection subject to terms'},
        'requirement_ids': ['test-vent-rule']}]
    rules = [{'requirement_id': 'test-vent-rule', 'classification': 'verified_requirement',
        'product_ids': ['TEST-PRODUCT'], 'county_fips': ['06037'], 'source': source(),
        'field': 'vent_type', 'operator': 'equals', 'target': 'test_new',
        'improvement': 'Synthetic test vent upgrade', 'project_id': 'test-vents',
        'practical_impact': 'high'}]
    costs = [{'cost_id': 'test-vent-cost', 'project_id': 'test-vents', 'county_fips': ['06037'],
        'jurisdiction': 'TEST-CITY', 'source': source(), 'scope_reviewed': True, 'price_date': '2026-11-01',
        'unit': 'USD_per_project', 'low_usd': '100', 'high_usd': '200',
        'scope_tags': ['all_test_vents'], 'scope_description': 'Synthetic whole-project installed cost'}]
    return payload, products, rules, costs


def run_fixture(payload=None, products=None, rules=None, costs=None):
    p, a, r, c = fixture()
    return analyze_insurance_gap(p if payload is None else payload,
        products=a if products is None else products, requirements=r if rules is None else rules,
        costs=c if costs is None else costs)


def finding(report, category):
    return next(f for f in report['coverage']['findings'] if f['category'] == category)


class GapTests(unittest.TestCase):
    def test_underinsurance_and_no_aggregate_double_count(self):
        r = run_fixture()
        self.assertEqual(finding(r, 'dwelling')['gap_usd'], '50000')
        self.assertEqual(finding(r, 'extended_replacement')['conditional_limit_usd'], '187500')
        self.assertEqual(finding(r, 'extended_replacement')['gap_usd'], '12500')
        self.assertIsNone(r['coverage']['aggregate_gap_usd'])
        self.assertEqual(finding(r, 'ale')['duration_gap_months'], '12')
        self.assertEqual(finding(r, 'deductible')['exposure_usd'], '1000')

    def test_adequate_scopes_and_erc(self):
        p, *_ = fixture()
        for cat in p['needs']:
            p['policy']['coverages'][cat]['limit_usd'] = p['needs'][cat]['amount_usd']
        p['policy']['coverages']['ale']['duration_months'] = '24'
        r = run_fixture(payload=p)
        for cat in p['needs']:
            self.assertEqual(finding(r, cat)['gap_usd'], '0')
        self.assertEqual(finding(r, 'extended_replacement')['status'], 'conditional_no_shortfall_identified')

    def test_missing_policy_is_not_zero(self):
        p, *_ = fixture(); p['policy'] = None
        r = run_fixture(payload=p)
        self.assertEqual(r['status'], 'incomplete')
        self.assertIsNone(finding(r, 'dwelling')['gap_usd'])
        p, *_ = fixture(); p['needs']['dwelling']['amount_usd'] = None
        self.assertIsNone(finding(run_fixture(payload=p), 'dwelling')['gap_usd'])

    def test_verified_absent_and_unknown_coverage(self):
        p, *_ = fixture(); c = p['policy']['coverages']['ordinance_law']; c.update(status='absent', limit_usd=None)
        self.assertEqual(finding(run_fixture(payload=p), 'ordinance_law')['gap_usd'], '10000')
        c['status'] = 'unknown'
        self.assertIsNone(finding(run_fixture(payload=p), 'ordinance_law')['gap_usd'])

    def test_extensions_conditions_and_guaranteed(self):
        p, *_ = fixture(); e = p['policy']['extended_replacement']
        e['conditions_verified'] = False
        self.assertIsNone(finding(run_fixture(payload=p), 'extended_replacement')['gap_usd'])
        e['kind'] = 'guaranteed'
        self.assertEqual(finding(run_fixture(payload=p), 'extended_replacement')['status'], 'guaranteed_terms_review')
        e.update(kind='additional_limit', value='60000', conditions_verified=True)
        self.assertEqual(finding(run_fixture(payload=p), 'extended_replacement')['gap_usd'], '0')
        e['kind'] = 'none'
        self.assertEqual(finding(run_fixture(payload=p), 'extended_replacement')['status'], 'missing_extension')

    def test_exclusions_and_endorsements(self):
        p, *_ = fixture(); p['policy']['exclusions'] = [{'peril': 'wildfire', 'effect': 'excluded',
            'categories': ['dwelling'], 'source': source()}]
        p['policy']['endorsements'] = [{'description': 'TEST endorsement', 'source': source()}]
        r = run_fixture(payload=p)
        self.assertEqual(finding(r, 'dwelling')['status'], 'excluded')
        self.assertIsNone(finding(r, 'dwelling')['gap_usd'])
        self.assertEqual(finding(r, 'endorsement')['status'], 'review_required')
        self.assertEqual(r['actions'][0]['category'], 'dwelling')

    def test_shared_limit_and_scope_mismatch(self):
        p, *_ = fixture(); p['policy']['coverages']['debris']['limit_basis'] = 'within_dwelling'
        self.assertEqual(finding(run_fixture(payload=p), 'debris')['status'], 'shared_limit_review')
        p['needs']['dwelling']['scope_id'] = 'different'
        self.assertIsNone(finding(run_fixture(payload=p), 'dwelling')['gap_usd'])

    def test_percentage_deductible(self):
        p, *_ = fixture(); p['policy']['deductible'] = {'kind': 'percentage', 'percent': '2',
            'basis_usd': '150000', 'basis_verified': True, 'source': source()}
        self.assertEqual(finding(run_fixture(payload=p), 'deductible')['exposure_usd'], '3000')
        p['policy']['deductible']['basis_verified'] = False
        self.assertIsNone(finding(run_fixture(payload=p), 'deductible')['exposure_usd'])

    def test_public_product_does_not_supply_premium(self):
        p, products, *_ = fixture(); products[0]['quote'] = {'annual_premium_usd': '1'}
        r = run_fixture(products=products)['alternatives']['products'][0]
        self.assertEqual(r['status'], 'description_only')
        self.assertIsNone(r['annual_premium_usd'])
        self.assertEqual(r['features'][0]['comparison'], 'different_terms_review')
        self.assertEqual(r['eligibility'], 'not_determined')

    def test_actual_quote_and_wrong_subject_expiry(self):
        p, products, *_ = fixture(); q = {'subject_id': 'TEST-HOME', 'source': source(),
            'currency': 'USD', 'annual_premium_usd': '2500', 'comparison_basis': 'test-annual-period'}
        products[0].update(evidence_type='actual_quote', quote=q)
        self.assertEqual(run_fixture(products=products)['alternatives']['products'][0]['premium_difference_usd'], '500')
        q['subject_id'] = 'OTHER'
        self.assertIsNone(run_fixture(products=products)['alternatives']['products'][0]['annual_premium_usd'])
        q['subject_id'] = 'TEST-HOME'; q['source']['valid_through'] = '2026-01-01'
        self.assertIsNone(run_fixture(products=products)['alternatives']['products'][0]['annual_premium_usd'])

    def test_requirements_typed_and_unknown(self):
        p, *_ = fixture(); p['property']['facts']['vent_type']['status'] = 'uncertain'
        r = run_fixture(payload=p)
        self.assertEqual(r['property_requirements']['findings'][0]['status'], 'unknown')
        self.assertEqual(r['upgrades']['projects'], [])
        self.assertTrue(any(a['kind'] == 'verify_property' for a in r['actions']))
        p['property']['facts']['vent_type'].update(status='confirmed', value='test_new')
        self.assertEqual(run_fixture(payload=p)['property_requirements']['findings'][0]['status'], 'met')

    def test_product_specific_rules(self):
        p, *_ = fixture(); p['selected_product_ids'] = ['OTHER']
        self.assertEqual(run_fixture(payload=p)['property_requirements']['findings'], [])

    def test_upgrade_price_and_missing(self):
        r = run_fixture()
        self.assertEqual(r['upgrades']['total_low_usd'], '100')
        self.assertEqual(r['upgrades']['total_high_usd'], '200')
        r = run_fixture(costs=[])
        self.assertEqual(r['upgrades']['projects'][0]['status'], 'pricing_unavailable')
        self.assertIsNone(r['upgrades']['total_low_usd'])

    def test_duplicate_projects_and_overlap(self):
        p, products, rules, costs = fixture()
        duplicate = deepcopy(rules[0]); duplicate['requirement_id'] = 'another-test-rule'; rules.append(duplicate)
        r = run_fixture(rules=rules)
        self.assertEqual(len(r['upgrades']['projects']), 1)
        self.assertEqual(r['upgrades']['total_low_usd'], '100')
        duplicate['project_id'] = 'test-second-project'
        c = deepcopy(costs[0]); c.update(cost_id='another-cost', project_id='test-second-project'); costs.append(c)
        r = run_fixture(rules=rules, costs=costs)
        self.assertIsNone(r['upgrades']['total_low_usd'])
        self.assertTrue(all(p['status'] == 'overlap_review_required' for p in r['upgrades']['projects']))

    def test_recommendation_priority_and_no_unknown_zero_cost(self):
        p, products, rules, costs = fixture()
        rec = deepcopy(rules[0]); rec.update(requirement_id='rec', project_id='rec-project', classification='recommendation')
        rules.append(rec)
        r = run_fixture(rules=rules, costs=costs)
        tiers = [a['priority_tier'] for a in r['actions']]
        self.assertEqual(tiers, sorted(tiers))
        self.assertEqual([a['project_id'] for a in r['actions'] if a['kind'] == 'property_upgrade'], ['test-vents', 'rec-project'])

    def test_empty_catalogs_and_bad_input(self):
        p, *_ = fixture(); r = analyze_insurance_gap(p, products=[], requirements=[], costs=[])
        self.assertEqual(r['status'], 'incomplete')
        self.assertEqual(r['alternatives']['status'], 'catalog_unavailable')
        self.assertEqual(analyze_insurance_gap({})['status'], 'invalid_input')
        p['policy']['coverages']['dwelling']['limit_usd'] = '-1'
        self.assertEqual(run_fixture(payload=p)['status'], 'invalid_input')

    def test_adapter_reproducibility_and_precision(self):
        p, a, r, c = fixture(); original = deepcopy(p)
        direct = run_fixture(payload=p)
        adapted = analyze_insurance_gap({'david_v_next': p}, adapter=lambda x: x['david_v_next'], products=a, requirements=r, costs=c)
        self.assertEqual(direct, adapted)
        self.assertEqual(p, original)
        previous = getcontext().prec
        try:
            getcontext().prec = 6
            self.assertEqual(run_fixture(payload=p), direct)
        finally:
            getcontext().prec = previous
        json.dumps(direct, allow_nan=False)

    def test_unverified_and_limited_terms_block_amounts(self):
        p, *_ = fixture()
        p['policy']['source']['valid_through'] = '2026-01-01'
        self.assertIsNone(finding(run_fixture(payload=p), 'dwelling')['gap_usd'])
        p, *_ = fixture()
        p['policy']['exclusions'] = [{'effect': 'limited', 'peril': 'wildfire',
                                     'categories': ['dwelling'], 'source': source()}]
        r = run_fixture(payload=p)
        self.assertEqual(finding(r, 'dwelling')['status'], 'limitation_review')
        self.assertIsNone(finding(r, 'dwelling')['gap_usd'])
        p, *_ = fixture(); p['needs']['dwelling']['allocation_review_required'] = True
        self.assertIsNone(finding(run_fixture(payload=p), 'dwelling')['gap_usd'])

    def test_cost_expiry_geography_and_ambiguity(self):
        p, a, rules, costs = fixture()
        costs[0]['jurisdiction'] = 'OTHER'
        self.assertIsNone(run_fixture(costs=costs)['upgrades']['total_low_usd'])
        p, a, rules, costs = fixture()
        costs[0]['source']['valid_through'] = '2026-01-01'
        self.assertIsNone(run_fixture(costs=costs)['upgrades']['total_low_usd'])
        p, a, rules, costs = fixture()
        second = deepcopy(costs[0]); second['cost_id'] = 'duplicate-option'; costs.append(second)
        self.assertEqual(run_fixture(costs=costs)['upgrades']['projects'][0]['status'], 'ambiguous_pricing')

    def test_recommendations_discounts_and_unverified_facts(self):
        p, a, rules, costs = fixture()
        rules[0].update(classification='potential_discount_condition', product_ids=[])
        self.assertEqual(run_fixture(rules=rules)['property_requirements']['findings'][0]['classification'], 'potential_discount_condition')
        p['property']['facts']['vent_type']['source']['verified'] = False
        self.assertEqual(run_fixture(payload=p, rules=rules)['upgrades']['projects'], [])

    def test_missing_ale_duration_and_need_keep_report_incomplete(self):
        p, *_ = fixture()
        del p['needs']['ale']['duration_months']
        r = run_fixture(payload=p)
        self.assertEqual(r['status'], 'incomplete')
        self.assertIn('policy_or_need.ale.duration_months', r['missing_inputs'])
        p, *_ = fixture()
        p['policy']['coverages']['debris'].update(status='absent', limit_usd=None)
        p['needs']['debris']['amount_usd'] = None
        r = run_fixture(payload=p)
        self.assertEqual(r['coverage']['status'], 'incomplete')
        self.assertIsNone(finding(r, 'debris')['gap_usd'])

    def test_bad_numbers_and_duplicate_catalog_ids(self):
        for amount in (True, 'NaN', 'Infinity', '-1'):
            p, *_ = fixture(); p['policy']['coverages']['dwelling']['limit_usd'] = amount
            self.assertEqual(run_fixture(payload=p)['status'], 'invalid_input')
        _, products, *_ = fixture()
        self.assertEqual(run_fixture(products=products+deepcopy(products))['status'], 'invalid_input')

    def test_synthetic_example_reports_match_current_engine(self):
        folder = Path(__file__).resolve().parents[1] / 'docs/examples'
        expected = json.loads((folder / 'insurance_gap_underinsured_synthetic.json').read_text())
        self.assertTrue(expected['synthetic_test_only'])
        self.assertEqual(expected['data'], run_fixture())
        p, *_ = fixture(); p['policy'] = None
        expected = json.loads((folder / 'insurance_gap_missing_policy_synthetic.json').read_text())
        self.assertEqual(expected['data'], run_fixture(payload=p))

    def test_rebuild_allocation_requires_complete_case(self):
        with self.assertRaises(ValueError):
            map_rebuild_need({'scenarios': {}}, scenario='central', amount_usd='1', scope_id='x', source=source())
        result = {'scenarios': {'central': {'completeness': 'complete', 'reconstruction_total_usd': '100'}}}
        self.assertEqual(map_rebuild_need(result, scenario='central', amount_usd='80', scope_id='x', source=source())['amount_usd'], '80')
        with self.assertRaises(ValueError):
            map_rebuild_need(result, scenario='central', amount_usd='101', scope_id='x', source=source())


if __name__ == '__main__':
    unittest.main()
