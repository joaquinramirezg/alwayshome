"""Actual rebuild -> reviewed scope allocation -> gap report with real catalogs.

All homeowner data is explicitly synthetic; no quoted premiums or local upgrade
prices are fabricated. Saved JSON artifacts are validated against live execution.
"""
from copy import deepcopy
import json
from pathlib import Path
import runpy
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
HARNESS = runpy.run_path(str(ROOT / 'scripts/validate_insurance_gap_e2e.py'))
from msba_vibathon_2026.insurance_gap import analyze_insurance_gap


def finding(report, category):
    return next(f for f in report['gap_report']['coverage']['findings'] if f['category'] == category)


class EndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.outputs = {r['scenario_id']: r for r in HARNESS['generate_reports']()}

    def test_three_artifacts_reproduce_actual_engine(self):
        self.assertEqual(len(self.outputs), 3)
        for name, result in self.outputs.items():
            saved = json.loads((ROOT / 'docs/examples/e2e' / (name+'.json')).read_text())
            self.assertEqual(saved, result)
            self.assertTrue(saved['synthetic_test_only'])
            self.assertEqual(saved['gap_report']['status'], 'incomplete')
            self.assertEqual(result, HARNESS['execute_case'](next(c for c in json.loads(
                (ROOT/'tests/fixtures/insurance_gap_e2e.json').read_text()) if c['scenario_id']==name)))

    def test_underinsured_calculations_and_allocation(self):
        r = self.outputs['synthetic_underinsured']
        self.assertEqual(r['rebuilding_result']['estimated_rebuilding_cost_usd'], '860000')
        self.assertEqual(finding(r,'dwelling')['need_usd'], '785000')
        self.assertEqual(finding(r,'dwelling')['gap_usd'], '185000')
        self.assertEqual(finding(r,'extended_replacement')['conditional_limit_usd'], '750000')
        self.assertEqual(finding(r,'extended_replacement')['gap_usd'], '35000')
        self.assertEqual(finding(r,'ale')['gap_usd'], '24000')
        self.assertEqual(finding(r,'ale')['duration_gap_months'], '6')
        self.assertEqual(finding(r,'ordinance_law')['gap_usd'], '25000')
        self.assertEqual(finding(r,'debris')['gap_usd'], '15000')
        self.assertEqual(finding(r,'deductible')['exposure_usd'], '2500')
        self.assertIsNone(r['gap_report']['coverage']['aggregate_gap_usd'])

    def test_sufficient_supplied_limits_do_not_imply_property_pass(self):
        r = self.outputs['synthetic_adequate_unknown_property']
        self.assertEqual(r['rebuilding_result']['estimated_rebuilding_cost_usd'], '950000')
        for cat in ('dwelling','ale','ordinance_law','debris'):
            self.assertEqual(finding(r,cat)['gap_usd'], '0')
        self.assertEqual(finding(r,'extended_replacement')['conditional_limit_usd'], '1250000')
        self.assertEqual(finding(r,'deductible')['exposure_usd'], '20000')
        self.assertTrue(all(f['status']=='unknown' for f in r['gap_report']['property_requirements']['findings']))
        self.assertEqual(r['gap_report']['upgrades']['projects'], [])
        self.assertTrue(any(a['kind']=='verify_property' for a in r['gap_report']['actions']))

    def test_fair_uncertainty_and_acv_not_replacement_proceeds(self):
        r = self.outputs['synthetic_limited_fair_uncertain']
        self.assertEqual(r['rebuilding_result']['status'], 'needs_cost_evidence')
        self.assertIsNone(r['rebuilding_result']['estimated_rebuilding_cost_usd'])
        self.assertEqual(finding(r,'dwelling')['status'], 'settlement_review')
        self.assertIsNone(finding(r,'dwelling')['gap_usd'])
        self.assertEqual(finding(r,'debris')['status'], 'shared_limit_review')
        self.assertIsNone(finding(r,'ordinance_law')['gap_usd'])
        self.assertIsNone(finding(r,'ale')['gap_usd'])
        self.assertEqual(finding(r,'deductible')['exposure_usd'], '1000')
        self.assertTrue(any(f['requirement_id'].startswith('fair_') for f in r['gap_report']['property_requirements']['findings']))

    def test_reference_limits_unknown_prices_and_deduplicated_actions(self):
        for r in self.outputs.values():
            gap=r['gap_report']
            for product in gap['alternatives']['products']:
                self.assertEqual(product['status'], 'description_only')
                self.assertIsNone(product['annual_premium_usd'])
                self.assertIsNone(product['premium_difference_usd'])
                self.assertEqual(product['eligibility'], 'not_determined')
            self.assertIsNone(gap['upgrades']['total_low_usd'])
            projects=gap['upgrades']['projects']
            ids=[p['project_id'] for p in projects]
            self.assertEqual(len(ids),len(set(ids)))
            self.assertTrue(all(p['status']=='pricing_unavailable' for p in projects))
            action_ids=[a['project_id'] for a in gap['actions'] if a['kind']=='property_upgrade']
            self.assertEqual(len(action_ids),len(set(action_ids)))
        vents=next(p for p in self.outputs['synthetic_underinsured']['gap_report']['upgrades']['projects'] if p['project_id']=='ember_resistant_vents')
        self.assertGreater(len(vents['requirement_ids']),1)

    def test_legal_applicability_and_priority(self):
        r=self.outputs['synthetic_underinsured']['gap_report']
        rule=next(f for f in r['property_requirements']['findings'] if f['requirement_id']=='calfire_applicable_dspace')
        self.assertEqual(rule['status'],'improvement_needed')
        tiers=[a['priority_tier'] for a in r['actions']]
        self.assertEqual(tiers,sorted(tiers))
        self.assertTrue(all(a['kind']=='policy_review' for a in r['actions'] if a['priority_tier']==1))
        self.assertTrue(any(a['project_id']=='defensible_space' and a['priority_tier']==2 for a in r['actions'] if a['kind']=='property_upgrade'))

    def test_ale_duration_only_shortfall_is_high_priority(self):
        p=deepcopy(self.outputs['synthetic_underinsured']['gap_input'])
        p['policy']['coverages']['ale']['limit_usd']='100000'
        r=analyze_insurance_gap(p)
        action=next(a for a in r['actions'] if a.get('category')=='ale')
        self.assertEqual(action['priority_tier'],1)

    def test_unknown_or_missing_settlement_blocks_quantification(self):
        for state in (None,'unknown','actual_cash_value'):
            p=deepcopy(self.outputs['synthetic_underinsured']['gap_input'])
            p['policy']['coverages']['dwelling']['settlement']=state
            r=analyze_insurance_gap(p)
            f=next(f for f in r['coverage']['findings'] if f['category']=='dwelling')
            self.assertEqual(f['status'],'settlement_review')
            self.assertIsNone(f['gap_usd'])
            ext=next(f for f in r['coverage']['findings'] if f['category']=='extended_replacement')
            self.assertIsNone(ext['gap_usd'])

    def test_mapping_review_cannot_be_bypassed(self):
        p=deepcopy(self.outputs['synthetic_underinsured']['gap_input'])
        p['needs']['dwelling']['allocation_review_required']=True
        r=analyze_insurance_gap(p)
        self.assertIsNone(next(f for f in r['coverage']['findings'] if f['category']=='dwelling')['gap_usd'])


if __name__=='__main__':
    unittest.main()
