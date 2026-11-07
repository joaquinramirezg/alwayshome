"""Scope-matched preliminary coverage screens, not claim settlement predictions."""
from copy import deepcopy
from decimal import Decimal, localcontext
from .common import money, text_money, verified

COVERAGES = ('dwelling', 'ale', 'ordinance_law', 'debris')


def analyze_coverage(policy, needs, *, as_of, subject_id):
    with localcontext() as ctx:
        ctx.prec = 80
        return _analyze(policy, needs, as_of, subject_id)


def _analyze(policy, needs, as_of, subject_id):
    findings = []
    exclusions = deepcopy(policy.get('exclusions', []))
    policy_ok = (policy.get('subject_id') == subject_id and verified(policy.get('source'), as_of)
                 and policy.get('terms_reviewed') is True and policy.get('exclusions_reviewed') is True)
    for category in COVERAGES:
        cover = policy.get('coverages', {}).get(category, {})
        need = needs.get(category, {})
        row = {'category': category, 'status': 'unknown', 'gap_usd': None,
               'need_usd': None, 'available_limit_usd': None, 'action': 'Verify policy terms and scope-matched need.',
               'source': deepcopy(cover.get('source')), 'need_source': deepcopy(need.get('source'))}
        if not policy_ok or not verified(cover.get('source'), as_of):
            findings.append(row); continue
        excluded = any(e.get('effect') == 'excluded' and e.get('peril') == 'wildfire'
                       and category in e.get('categories', []) and verified(e.get('source'), as_of)
                       for e in exclusions)
        if any(not verified(e.get('source'), as_of) for e in exclusions):
            row['action'] = 'Resolve unverified exclusions before quantifying.'
            findings.append(row); continue
        limited = any(e.get('effect') != 'excluded' and category in e.get('categories', [])
                      for e in exclusions)
        if limited:
            row.update(status='limitation_review', action='Resolve the documented limitation before quantifying coverage.')
            findings.append(row); continue
        if any(not isinstance(e.get('categories'), list) or not e['categories'] for e in exclusions):
            row.update(status='limitation_review', action='Resolve the affected categories of each exclusion before quantifying.')
            findings.append(row); continue
        state = cover.get('status', 'unknown')
        if excluded:
            row.update(status='excluded', action='Ask a licensed agent about wildfire coverage for this scope.')
            findings.append(row); continue
        if state not in ('present', 'absent'):
            findings.append(row); continue
        if category == 'dwelling' and state == 'present' and cover.get('settlement') != 'replacement_cost':
            row.update(status='settlement_review',
                       action='Verify settlement basis; an ACV or unknown limit is not replacement-cost proceeds.')
            findings.append(row); continue
        if cover.get('limit_basis') not in ('standalone', 'additional'):
            row.update(status='shared_limit_review', action='Review shared/within-dwelling limits; do not add them to Coverage A.')
            findings.append(row); continue
        if state == 'absent' and cover.get('limit_usd') not in (None, '0', 0):
            raise ValueError('Absent coverage cannot have a positive limit')
        limit = Decimal(0) if state == 'absent' else money(cover.get('limit_usd'))
        need_amount = money(need.get('amount_usd'))
        row['available_limit_usd'] = text_money(limit)
        if (limit is None or need_amount is None or not verified(need.get('source'), as_of)
                or need.get('allocation_review_required') is True
                or not need.get('scope_id') or need.get('scope_id') != cover.get('scope_id')):
            row.update(status='missing_coverage' if state == 'absent' else 'unknown',
                       action='Confirm coverage need and matching cost scope.')
        else:
            gap = max(Decimal(0), need_amount - limit)
            row.update(status='shortfall' if gap else 'no_shortfall_identified', gap_usd=text_money(gap),
                       need_usd=text_money(need_amount),
                       action='Discuss higher protection for this scope.' if gap else 'Confirm terms remain applicable at renewal.')
        if category == 'ale':
            duration, required = money(cover.get('duration_months')), money(need.get('duration_months'))
            row['duration_gap_months'] = (text_money(max(Decimal(0), required-duration))
                if duration is not None and required is not None and verified(need.get('source'), as_of)
                and need.get('scope_id') == cover.get('scope_id')
                and need.get('allocation_review_required') is not True else None)
            if row['duration_gap_months'] is None:
                row['duration_status'] = 'unknown'
            if row['duration_gap_months'] is not None and Decimal(row['duration_gap_months']) > 0:
                row['duration_status'] = 'shortfall'
                row['action'] = 'Discuss both ALE dollar limits and rebuilding-duration protection.'
        findings.append(row)
    dwelling = findings[0]
    erc = policy.get('extended_replacement', {})
    extension = {'category': 'extended_replacement', 'status': 'unknown', 'gap_usd': None,
                 'conditional_limit_usd': None, 'source': deepcopy(erc.get('source')),
                 'action': 'Verify extension, triggers, maintenance conditions and covered cost scope.'}
    if policy_ok and verified(erc.get('source'), as_of):
        kind = erc.get('kind', 'unknown')
        if kind == 'none':
            extension['status'] = 'missing_extension'
        elif kind == 'guaranteed':
            extension['status'] = 'guaranteed_terms_review'
        elif kind in ('percentage', 'additional_limit'):
            base = money(dwelling['available_limit_usd'])
            value = money(erc.get('value'))
            if (base is not None and value is not None and erc.get('conditions_verified') is True
                    and erc.get('scope_id') == policy.get('coverages', {}).get('dwelling', {}).get('scope_id')
                    and policy.get('coverages', {}).get('dwelling', {}).get('status') == 'present'
                    and dwelling['status'] in ('shortfall', 'no_shortfall_identified')):
                cap = base + (base * value / 100 if kind == 'percentage' else value)
                gap = max(Decimal(0), money(dwelling['need_usd']) - cap)
                extension.update(status='conditional_shortfall' if gap else 'conditional_no_shortfall_identified',
                                 conditional_limit_usd=text_money(cap), gap_usd=text_money(gap))
            else:
                extension['status'] = 'conditional_terms_unresolved'
    findings.append(extension)
    deductible = policy.get('deductible', {})
    exposure = None
    if policy_ok and verified(deductible.get('source'), as_of):
        if deductible.get('kind') == 'fixed':
            exposure = money(deductible.get('amount_usd'))
        elif deductible.get('kind') == 'percentage' and deductible.get('basis_verified') is True:
            pct, basis = money(deductible.get('percent')), money(deductible.get('basis_usd'))
            if pct is not None and pct > 100:
                raise ValueError('Deductible percent cannot exceed 100')
            if pct is not None and basis is not None:
                exposure = pct * basis / 100
    findings.append({'category': 'deductible', 'status': 'known_exposure' if exposure is not None else 'unknown',
                     'exposure_usd': text_money(exposure), 'gap_usd': None,
                     'source': deepcopy(deductible.get('source')),
                     'action': 'Plan for the applicable deductible; it is not an additional coverage limit.'})
    for index, exclusion in enumerate(exclusions):
        findings.append({'category': 'exclusion', 'status': 'review_required', 'gap_usd': None,
                         'details': exclusion, 'action': 'Review this exclusion or limitation with a licensed agent.',
                         'id': f'exclusion-{index}'})
    for index, endorsement in enumerate(policy.get('endorsements', [])):
        findings.append({'category': 'endorsement', 'status': 'review_required', 'gap_usd': None,
                         'details': deepcopy(endorsement), 'id': f'endorsement-{index}',
                         'action': 'Confirm endorsement scope, conditions and interaction with other limits.'})
    unresolved = any(r.get('duration_status') == 'unknown' for r in findings) or any(r['status'] in ('unknown', 'shared_limit_review', 'conditional_terms_unresolved',
                                    'guaranteed_terms_review', 'review_required', 'limitation_review', 'missing_coverage', 'settlement_review') for r in findings)
    return {'status': 'incomplete' if unresolved else 'screened', 'findings': findings,
            'aggregate_gap_usd': None, 'limitations': [
                'No aggregate gap: limits may overlap; extensions are conditional, not guaranteed proceeds.',
                'No-shortfall findings apply only to supplied scope and scenarios, not overall insurance adequacy.']}
