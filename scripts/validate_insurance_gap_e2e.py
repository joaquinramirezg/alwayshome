"""Generate three offline E2E artifacts from explicitly synthetic household inputs.

Run: .venv/bin/python scripts/validate_insurance_gap_e2e.py
No real quote, premium, current local upgrade cost, or property assessment is created.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from msba_vibathon_2026.rebuilding import estimate_rebuilding
from msba_vibathon_2026.insurance_gap import analyze_insurance_gap, map_rebuild_need
from msba_vibathon_2026.insurance_gap.catalogs import load_reference_catalogs


def execute_case(case):
    if case.get('synthetic_test_only') is not True or case.get('allocation_review_is_synthetic_test_only') is not True:
        raise ValueError('This harness is exclusively for labeled synthetic cases')
    req = deepcopy(case['payload'])
    rebuild = estimate_rebuilding(case['rebuilding_request'])
    allocation = case['reviewed_dwelling_allocation_usd']
    if allocation is not None:
        need = map_rebuild_need(rebuild, scenario='central', amount_usd=allocation,
                               scope_id=req['needs']['dwelling']['scope_id'],
                               source=req['needs']['dwelling']['source'])
        # Explicit review assertion supplied by the fixture, never production inference.
        need['allocation_review_required'] = False
        req['needs']['dwelling'] = need
    catalogs = load_reference_catalogs()
    report = analyze_insurance_gap(req, products=catalogs['products'],
                                   requirements=catalogs['requirements'], costs=catalogs['costs'])
    if report['status'] == 'invalid_input':
        raise ValueError(report['errors'])
    return {'synthetic_test_only': True, 'scenario_id': case['scenario_id'],
            'description': case['description'],
            'warning': 'All household amounts/conditions are synthetic. No actual quote or premium is represented.',
            'rebuilding_result': rebuild, 'gap_input': req, 'gap_report': report}


def generate_reports():
    cases = json.loads((ROOT / 'tests/fixtures/insurance_gap_e2e.json').read_text())
    return [execute_case(case) for case in cases]


if __name__ == '__main__':
    target = ROOT / 'docs/examples/e2e'
    target.mkdir(parents=True, exist_ok=True)
    for report in generate_reports():
        path = target / (report['scenario_id'] + '.json')
        path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        print(f"{path.relative_to(ROOT)}: rebuild={report['rebuilding_result']['status']}, gap={report['gap_report']['status']}")
