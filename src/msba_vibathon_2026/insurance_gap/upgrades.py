"""Deduplicate project scopes and price reviewed, non-overlapping catalog entries."""
from copy import deepcopy
from datetime import date
from decimal import Decimal, localcontext
from .common import money, text_money, unique, verified


def estimate_upgrades(findings, costs, *, county_fips, jurisdiction, as_of):
    unique(costs, 'cost_id')
    projects = {}
    for f in findings:
        if f.get('status') != 'improvement_needed' or not f.get('project_id'):
            continue
        project = projects.setdefault(f['project_id'], {
            'project_id': f['project_id'], 'requirement_ids': [], 'classifications': [],
            'improvements': [], 'practical_impacts': [], 'status': 'pricing_unavailable',
            'low_usd': None, 'high_usd': None, 'source': None})
        for field, value in [('requirement_ids', f['requirement_id']),
                             ('classifications', f['classification']),
                             ('improvements', f['required_improvement']),
                             ('practical_impacts', f['practical_impact'])]:
            if value not in project[field]:
                project[field].append(value)
    for project in projects.values():
        options = [c for c in costs if c.get('project_id') == project['project_id']
                   and county_fips in c.get('county_fips', []) and c.get('jurisdiction') == jurisdiction
                   and verified(c.get('source'), as_of) and c.get('unit') == 'USD_per_project'
                   and c.get('scope_reviewed') is True
                   and c.get('verification_status', 'verified_installed_project') == 'verified_installed_project']
        if len(options) > 1:
            project['status'] = 'ambiguous_pricing'; continue
        if not options:
            continue
        c = options[0]
        low, high = money(c.get('low_usd')), money(c.get('high_usd'))
        try:
            if date.fromisoformat(c.get('price_date')) > date.fromisoformat(as_of):
                continue
        except (TypeError, ValueError):
            continue
        tags = c.get('scope_tags')
        if low is None or high is None or not isinstance(tags, list) or not tags or not c.get('scope_description'):
            continue
        if low > high or len(tags) != len(set(tags)):
            raise ValueError('Invalid upgrade range or repeated scope tags')
        project.update(status='priced', low_usd=text_money(low), high_usd=text_money(high),
                       source=deepcopy(c['source']), scope_tags=tags[:], cost_id=c['cost_id'],
                       scope_description=c.get('scope_description'), geography=jurisdiction, price_date=c['price_date'])
    rows = list(projects.values())
    for index, first in enumerate(rows):
        for second in rows[index+1:]:
            if set(first.get('scope_tags', [])) & set(second.get('scope_tags', [])):
                first['status'] = second['status'] = 'overlap_review_required'
    complete = all(p['status'] == 'priced' for p in rows)
    with localcontext() as ctx:
        ctx.prec = 80
        low = sum((money(p['low_usd']) for p in rows), Decimal(0)) if complete else None
        high = sum((money(p['high_usd']) for p in rows), Decimal(0)) if complete else None
    return {'status': 'no_identified_projects' if not rows else 'priced' if complete else 'incomplete',
            'projects': rows, 'total_low_usd': text_money(low) if rows else None,
            'total_high_usd': text_money(high) if rows else None,
            'limitations': ['Catalog estimates are not bids. No premium savings or eligibility improvement is quantified.',
                'Scope tags must identify shared work consistently; overlaps require human reconciliation.']}
