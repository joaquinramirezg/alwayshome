"""Orchestrate an actionable deterministic report without frontend/extraction work."""
from decimal import Decimal, localcontext
from .adapter import adapt_inputs
from .alternatives import compare_alternatives
from .catalogs import PRODUCTS, REQUIREMENTS, UPGRADE_COSTS
from .common import validate_context, money
from .coverage import analyze_coverage
from .requirements import match_requirements
from .upgrades import estimate_upgrades


def _actions(coverage, requirements, upgrades):
    actions = []
    for f in coverage['findings']:
        if f['status'] in ('no_shortfall_identified', 'conditional_no_shortfall_identified') and not f.get('duration_status'):
            continue
        urgent = (f['status'] in ('shortfall', 'excluded', 'missing_coverage', 'conditional_shortfall')
                  or f.get('duration_status') == 'shortfall')
        actions.append({'kind': 'policy_review', 'category': f['category'],
                        'priority_tier': 0 if f['status'] == 'excluded' else 1 if urgent else 3, 'action': f['action'],
                        'gap_usd': f.get('gap_usd'),
                        'reason': 'Documented coverage shortfall/exclusion.' if urgent else 'Verify terms or plan for exposure.'})
    for p in upgrades['projects']:
        tier = 2 if 'verified_requirement' in p['classifications'] else 4
        actions.append({'kind': 'property_upgrade', 'project_id': p['project_id'], 'priority_tier': tier,
                        'action': p['improvements'], 'low_usd': p['low_usd'], 'high_usd': p['high_usd'],
                        'practical_impacts': p['practical_impacts'],
                        'reason': 'Named product/program requirement.' if tier == 2 else 'Documented recommendation or potential discount condition.',
                        'pricing_status': p['status']})
    for f in requirements['findings']:
        if f['status'] == 'unknown' or (f['status'] == 'improvement_needed' and not f.get('project_id')):
            actions.append({'kind': 'verify_property', 'priority_tier': 3,
                            'requirement_id': f['requirement_id'], 'action': 'Verify ' + str(f['field']),
                            'reason': 'Unknown condition or unverified rule; do not schedule work based on uncertainty.'})
    # Explicit, reviewable ordering assumption, not a model of loss reduction.
    actions.sort(key=lambda a: (a['priority_tier'],
        min(({'high': 0, 'medium': 1, 'low': 2}.get(i, 3) for i in a.get('practical_impacts', [])), default=3),
        a.get('pricing_status') not in (None, 'priced'),
        a.get('low_usd') is None, money(a.get('low_usd')) or Decimal(0),
        str(a.get('category', a.get('project_id', a.get('requirement_id', ''))))))
    for index, action in enumerate(actions, 1):
        action['order'] = index
    return actions


def analyze_insurance_gap(payload, *, adapter=None, products=None, requirements=None, costs=None):
    """Application entry point; supply reviewed catalogs as trusted keyword arguments."""
    try:
        data = adapt_inputs(payload, adapter=adapter)
        validate_context(data)
        prop = data.get('property', {})
        if prop.get('county_fips') != '06037':
            return {'schema_version': 'gap-report-v1', 'status': 'out_of_scope', 'actions': []}
        if prop.get('subject_id') != data['subject_id']:
            raise ValueError('Property subject_id mismatch')
        policy = data.get('policy') or {}
        if policy.get('subject_id') not in (None, data['subject_id']):
            raise ValueError('Policy subject_id mismatch')
        with localcontext() as ctx:
            ctx.prec = 80
            coverage = analyze_coverage(policy, data.get('needs', {}), as_of=data['as_of'], subject_id=data['subject_id'])
            alternatives = compare_alternatives(policy, PRODUCTS if products is None else products,
                as_of=data['as_of'], subject_id=data['subject_id'], county_fips=prop['county_fips'])
            matching = match_requirements(prop, REQUIREMENTS if requirements is None else requirements,
                selected_products=data.get('selected_product_ids', []), county_fips=prop['county_fips'], as_of=data['as_of'])
            upgrades = estimate_upgrades(matching['findings'], UPGRADE_COSTS if costs is None else costs,
                county_fips=prop['county_fips'], jurisdiction=prop.get('jurisdiction'), as_of=data['as_of'])
        incomplete = (coverage['status'] == 'incomplete' or alternatives['status'] in ('catalog_unavailable', 'incomplete')
                      or matching['status'] in ('catalog_unavailable', 'incomplete') or upgrades['status'] == 'incomplete')
        return {'schema_version': 'gap-report-v1', 'status': 'incomplete' if incomplete else 'screened',
                'subject_id': data['subject_id'], 'as_of': data['as_of'], 'currency': 'USD',
                'coverage': coverage, 'alternatives': alternatives, 'property_requirements': matching,
                'upgrades': upgrades, 'actions': _actions(coverage, matching, upgrades),
                'missing_inputs': [f"policy_or_need.{f['category']}" for f in coverage['findings'] if f['status'] in ('unknown', 'missing_coverage')]
                    + ['policy_or_need.ale.duration_months' for f in coverage['findings'] if f.get('duration_status') == 'unknown']
                    + [f"property_or_rule.{f['requirement_id']}" for f in matching['findings'] if f['status'] in ('unknown', 'missing_coverage')]
                    + [f"cost.{p['project_id']}" for p in upgrades['projects'] if p['status'] != 'priced']
                    + (['product_catalog'] if alternatives['status'] == 'catalog_unavailable' else [])
                    + (['requirements_catalog'] if matching['status'] == 'catalog_unavailable' else []),
                'prioritization_assumption': 'Exclusions, coverage shortfalls, named requirements, verification tasks, then recommendations; documented high/medium/low practical impact followed by known cost ascending within each tier. This ordering is a transparent product assumption, not measured loss reduction.',
                'limitations': ['Preliminary planning report, not a claim settlement or insurer-certified valuation.',
                    'No product acceptance, premium savings or underwriting outcome is promised.',
                    'Source verification flags are trusted upstream attestations; no document extraction is performed.']}
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        return {'schema_version': 'gap-report-v1', 'status': 'invalid_input', 'errors': [str(exc)], 'actions': []}
