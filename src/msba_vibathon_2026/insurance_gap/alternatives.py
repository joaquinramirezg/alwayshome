"""Documented feature comparison; descriptions never imply an offer to insure."""
from copy import deepcopy
from decimal import localcontext
from .common import money, text_money, unique, verified


def compare_alternatives(policy, products, *, as_of, subject_id, county_fips):
    with localcontext() as ctx:
        ctx.prec = 80
        return _compare(policy, products, as_of=as_of, subject_id=subject_id, county_fips=county_fips)


def _compare(policy, products, *, as_of, subject_id, county_fips):
    unique(products, 'product_id')
    rows = []
    for product in products:
        row = {'product_id': product['product_id'], 'name': product.get('name'),
               'status': 'unverified_or_inapplicable', 'eligibility': 'not_determined',
               'annual_premium_usd': None, 'premium_difference_usd': None,
               'source': deepcopy(product.get('source')), 'features': [],
               'limitations': ['Public descriptions are not offers, acceptance decisions, or binding coverage.']}
        if (not verified(product.get('source'), as_of) or county_fips not in product.get('county_fips', [])
                or product.get('verification_status', 'verified_public_description_only') not in
                ('verified_public_description_only', 'verified_actual_quote')):
            rows.append(row); continue
        if product.get('evidence_type') not in ('public_description', 'actual_quote'):
            rows.append(row); continue
        row['status'] = 'description_only'
        for key in sorted(set(product.get('features', {})) | set(policy.get('features', {}))):
            target, current = product.get('features', {}).get(key, {}), policy.get('features', {}).get(key, {})
            ok = verified(target.get('source'), as_of)
            old_ok = verified(current.get('source'), as_of)
            row['features'].append({'feature': key,
                'current': deepcopy(current.get('value')) if old_ok else None,
                'alternative': deepcopy(target.get('value')) if ok else None,
                'comparison': 'different_terms_review' if ok and old_ok and target.get('value') != current.get('value')
                              else 'same_documented_value' if ok and old_ok else 'unknown',
                'source': deepcopy(target.get('source'))})
        row['current_coverage_terms'] = deepcopy(policy.get('coverages', {}))
        row['current_deductible'] = deepcopy(policy.get('deductible', {}))
        row['current_exclusions'] = deepcopy(policy.get('exclusions', []))
        if 'availability_status' in product:
            row['reference_metadata'] = {key: deepcopy(product.get(key)) for key in
                ('insurer', 'verification_status', 'geographic_applicability', 'availability_status')}
        row['coverage_terms'] = deepcopy(product.get('coverage_terms', {}))
        row['deductibles'] = deepcopy(product.get('deductibles', []))
        row['exclusions'] = deepcopy(product.get('exclusions', []))
        row['requirements_pending'] = product.get('requirement_ids', [])[:]
        quote = product.get('quote', {})
        if (product['evidence_type'] == 'actual_quote' and quote.get('subject_id') == subject_id
                and verified(quote.get('source'), as_of) and quote.get('currency') == 'USD'):
            premium = money(quote.get('annual_premium_usd'))
            row.update(status='quoted_terms_review', annual_premium_usd=text_money(premium),
                       eligibility='quote_received_acceptance_not_guaranteed')
            current = policy.get('premium', {})
            if (premium is not None and policy.get('subject_id') == subject_id
                    and current.get('currency') == 'USD' and verified(current.get('source'), as_of)
                    and quote.get('comparison_basis') == current.get('comparison_basis')
                    and quote.get('comparison_basis')):
                old = money(current.get('annual_premium_usd'))
                if old is not None:
                    row['premium_difference_usd'] = text_money(premium - old)
        rows.append(row)
    return {'status': 'catalog_unavailable' if not rows else 'incomplete' if any(r['status'] == 'unverified_or_inapplicable' for r in rows) else 'compared', 'products': rows,
            'ranking': None, 'limitations': ['No universal best product or automatic eligibility ranking.',
                'Premium differences require documented quotes and matching comparison periods/basis.']}
