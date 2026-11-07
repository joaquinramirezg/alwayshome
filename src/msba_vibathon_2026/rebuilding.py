"""Deterministic, offline reconstruction planning estimates; no insurance advice.

Public API: estimate_rebuilding(request, *, benchmarks=None) -> JSON-safe dict.
All decimal monetary outputs are strings, preserving exact arithmetic. Input
provenance is caller-supplied; this engine cannot authenticate a contractor quote.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext

from .rebuilding_benchmarks import BENCHMARKS

CATEGORIES = (
    'construction', 'contractor_overhead_profit', 'demolition_debris',
    'professional_services', 'permits_agency_fees', 'incremental_code',
    'extraordinary_site_utilities', 'incremental_disaster_pressure', 'contingency',
)
SCENARIOS = ('low', 'central', 'high')
EXCLUDED = ('land', 'mortgage', 'sale_commissions', 'movable_contents',
            'temporary_accommodation', 'landscaping', 'optional_betterments',
            'detached_structures', 'financing_carrying_costs')
NOTE = ('Planning estimate of reconstruction cost excluding land; '
        'not an insurer-certified replacement-cost valuation.')


class InputError(ValueError):
    """Invalid or internally inconsistent request, suitable for user correction."""


def _number(value, field, *, positive=False):
    if isinstance(value, bool):
        raise InputError(f'{field}: expected a finite number')
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise InputError(f'{field}: expected a finite number') from None
    if not result.is_finite() or result < 0 or (positive and result == 0):
        raise InputError(f'{field}: expected a finite {"positive" if positive else "nonnegative"} number')
    if len(result.as_tuple().digits) > 28 or abs(result.adjusted()) > 20:
        raise InputError(f'{field}: numeric precision or magnitude exceeds supported range')
    return result


def _date(value, field):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise InputError(f'{field}: expected an ISO date') from None


def _known(value):
    return value is not None and str(value).strip().lower() not in ('', 'unknown')


def _property_missing(req):
    missing = []
    for section, fields in {
        'location': ('county_fips', 'permitting_jurisdiction'),
        'home': ('living_area_sqft', 'area_definition', 'construction_type',
                 'foundation_type', 'stories', 'year_built', 'dwelling_type', 'unit_count'),
        'estimate_context': ('estimate_as_of', 'target_price_date', 'market_scenario',
                             'permit_date_assumption', 'rebuild_scope', 'currency'),
    }.items():
        for field in fields:
            if not _known(req.get(section, {}).get(field)):
                missing.append(f'{section}.{field}')
    if not _known(req.get('address')):
        missing.append('address')
    h = req.get('home', {})
    for field in ('source_category', 'description'):
        if not _known(h.get('quality', {}).get(field)):
            missing.append('home.quality.' + field)
    if h.get('quality', {}).get('homeowner_confirmed') is not True:
        missing.append('home.quality.homeowner_confirmed')
    for field in ('roof', 'exterior'):
        if not _known(h.get('materials', {}).get(field)):
            missing.append('home.materials.' + field)
    for section, field in (('location', 'jurisdiction_verified'),
                           ('home', 'area_confirmed'), ('home', 'features_reviewed'),
                           ('site', 'screening_complete')):
        if req.get(section, {}).get(field) is not True:
            missing.append(section + '.' + field)
    if not _known(h.get('area_source')):
        missing.append('home.area_source')
    return missing


def _evidence_issues(e, req, mode):
    issues = []
    for field in ('evidence_id', 'source_id', 'source_url_or_document_ref',
                  'scope_description', 'reviewer', 'publication_date', 'price_base_date',
                  'valid_through', 'reviewed_at', 'year'):
        if not _known(e.get(field)):
            issues.append('evidence.' + field)
    if issues:
        return issues
    ctx, home, loc = req['estimate_context'], req['home'], req['location']
    base = _date(e['price_base_date'], 'evidence.price_base_date')
    published = _date(e['publication_date'], 'evidence.publication_date')
    reviewed = _date(e['reviewed_at'], 'evidence.reviewed_at')
    through = _date(e['valid_through'], 'evidence.valid_through')
    asof = _date(ctx['estimate_as_of'], 'estimate_as_of')
    if published > asof or reviewed > asof or through < asof or through < base:
        issues.append('evidence freshness/review dates')
    if base > asof and ctx['market_scenario'] != 'future_stress':
        issues.append('future price basis requires an explicit future_stress scenario')
    if reviewed < published:
        issues.append('evidence reviewed before publication')
    if str(e['year']) != str(base.year):
        issues.append('evidence.year')
    # No approved location or time adjustment model exists yet.
    if e['price_base_date'] != ctx['target_price_date']:
        issues.append('evidence.price_base_date differs from target; refreshed pricing required')
    if e.get('verification_status') != 'full_document_verified':
        issues.append('evidence.verification_status')
    if e.get('parameter_status') != 'approved_for_this_scope':
        issues.append('evidence.parameter_status')
    for field, expected in (
        ('county_fips', loc['county_fips']),
        ('permitting_jurisdiction', loc['permitting_jurisdiction']),
        ('quality', home['quality']['source_category']),
        ('construction_type', home['construction_type']),
        ('area_definition', home['area_definition']),
        ('property_scope', home['dwelling_type']),
        ('currency', ctx['currency']), ('market_scenario', ctx['market_scenario']),
        ('rebuild_scope', ctx['rebuild_scope']),
    ):
        if e.get(field) != expected:
            issues.append('evidence mismatch: ' + field)
    if _number(e.get('stories'), 'evidence.stories', positive=True) != _number(home['stories'], 'home.stories', positive=True):
        issues.append('evidence mismatch: stories')
    if mode == 'benchmark':
        band = e.get('size_band_sqft')
        if not isinstance(band, list) or len(band) != 2:
            issues.append('evidence.size_band_sqft')
        elif not (_number(band[0], 'size_band minimum') <= _number(home['living_area_sqft'], 'area') <= _number(band[1], 'size_band maximum')):
            issues.append('evidence mismatch: size_band_sqft')
        if e.get('unit') != 'USD_per_finished_sqft':
            issues.append('benchmark unit must be USD_per_finished_sqft')
    else:
        if e.get('unit') not in ('USD_per_finished_sqft', 'USD_lump_sum'):
            issues.append('unsupported quote unit')
        if e.get('quoted_address') != req['address']:
            issues.append('evidence mismatch: quoted_address')
        if e.get('quoted_living_area_sqft') is None:
            issues.append('evidence.quoted_living_area_sqft')
        elif _number(e['quoted_living_area_sqft'], 'quoted_living_area_sqft', positive=True) != _number(home['living_area_sqft'], 'area'):
            issues.append('evidence mismatch: quoted_living_area_sqft')
    if e.get('location_adjustment') is not None or e.get('time_adjustment') is not None:
        issues.append('Explicit adjustments unsupported; supply localized, refreshed pricing')
    if e.get('building_scope_confirmed') is not True:
        issues.append('building scope (foundation, fixed systems, attached features, taxes) unconfirmed')
    includes, excludes = e.get('includes'), e.get('excludes')
    if not isinstance(includes, list) or not isinstance(excludes, list):
        issues.append('evidence includes/excludes required')
    elif (set(includes) & set(excludes) or set(includes + excludes) != set(CATEGORIES)
          or 'construction' not in includes or len(includes + excludes) != len(CATEGORIES)):
        raise InputError('Evidence must partition all cost categories into includes and excludes')
    return issues


def _scenario(name, data, e, req):
    if not isinstance(data, dict) or not _known(data.get('rationale')):
        raise InputError(f'{name}: scenario evidence/rationale required')
    price = data.get('base_value')
    if price is None:
        return None
    base = _number(price, f'{name}.base_value', positive=True)
    if e['unit'] == 'USD_per_finished_sqft':
        base *= _number(req['home']['living_area_sqft'], 'living_area_sqft', positive=True)
    items = data.get('items', [])
    if not isinstance(items, list):
        raise InputError(f'{name}.items must be a list')
    ledger = {'construction': {'scope_state': 'separately_priced',
                               'amount_usd': str(base), 'evidence_id': e['evidence_id']}}
    unresolved, seen = [], set()
    total = base
    for item in items:
        cat, state = item.get('category'), item.get('scope_state')
        if cat not in CATEGORIES[1:] or cat in seen:
            raise InputError(f'{name}: unknown, repeated or construction item: {cat}')
        seen.add(cat)
        amount = item.get('amount_usd')
        if state == 'included_in_base':
            if cat not in e['includes'] or amount is not None:
                raise InputError(f'{name}.{cat}: inconsistent embedded cost or duplicate amount')
        elif state in ('separately_priced', 'not_applicable_verified'):
            if cat in e['includes']:
                raise InputError(f'{name}.{cat}: already included in base')
            if not _known(item.get('documentation')):
                raise InputError(f'{name}.{cat}: documentation required')
            if state == 'separately_priced':
                value = _number(amount, f'{name}.{cat}.amount_usd')
                total += value
            elif amount is not None:
                raise InputError(f'{name}.{cat}: inapplicable costs must not carry an amount')
        elif state == 'unresolved':
            if amount is not None or cat in e['includes']:
                raise InputError(f'{name}.{cat}: inconsistent unresolved cost')
            unresolved.append(cat)
        else:
            raise InputError(f'{name}.{cat}: invalid scope state')
        ledger[cat] = deepcopy(item)
        if amount is not None:
            ledger[cat]['amount_usd'] = str(_number(amount, cat))
        ledger[cat]['evidence_id'] = e['evidence_id']
    for cat in CATEGORIES[1:]:
        if cat not in seen:
            if cat in e['includes']:
                ledger[cat] = {'scope_state': 'included_in_base', 'amount_usd': None,
                               'evidence_id': e['evidence_id']}
            else:
                unresolved.append(cat)
                ledger[cat] = {'scope_state': 'unresolved', 'amount_usd': None}
    return {
        'reconstruction_total_usd': None if unresolved else str(total),
        'known_cost_subtotal_usd': str(total), 'construction_subtotal_usd': str(base),
        'component_totals': ledger, 'unresolved_categories': unresolved,
        'completeness': 'incomplete_scope' if unresolved else 'complete',
        'price_basis': deepcopy(e), 'rationale': data['rationale'],
        'assumptions': deepcopy(data.get('assumptions', [])),
        'adjustments': {'location_factor': '1', 'time_factor': '1'},
    }


def estimate_rebuilding(request: dict, *, benchmarks=None) -> dict:
    """Return structured status instead of guessing missing property/pricing data.

    mode='benchmark' selects evidence only from the separately supplied trusted
    catalog (default: empty). mode='documented' accepts one reviewed quote/rate.
    Malformed inputs return invalid_input; unavailable data returns actionable
    missing/review flags. No network, file writes, clock reads or input mutation.
    """
    result = {
        'method_version': 'rebuild-v1', 'status': 'needs_property_inputs',
        'estimated_rebuilding_cost_usd': None,
        'scenarios': dict.fromkeys(SCENARIOS), 'missing_inputs': [], 'review_flags': [],
        'excluded_costs': list(EXCLUDED), 'included_cost_components': [],
        'assumptions': [], 'limitations': [NOTE, 'Evidence authenticity and scope require human review.',
            'Scenario bounds are planning cases, not statistical confidence intervals.',
            'No automatic geographic, age, disaster, or future inflation adjustments.'],
        'coverage_comparison_ready': False, 'display_note': NOTE,
    }
    try:
        if not isinstance(request, dict):
            raise InputError('request must be an object')
        req = deepcopy(request)
        mode = req.get('mode')
        if mode not in ('benchmark', 'documented'):
            raise InputError('mode must be benchmark or documented')
        result['confirmed_inputs'] = req
        result['missing_inputs'] = _property_missing(req)
        # Reject malformed supplied numeric inputs even if other fields are missing.
        h = req.get('home', {})
        for field in ('living_area_sqft', 'stories', 'unit_count'):
            if h.get(field) is not None:
                _number(h[field], 'home.' + field, positive=True)
        if result['missing_inputs']:
            return result
        ctx, loc = req['estimate_context'], req['location']
        asof = _date(ctx['estimate_as_of'], 'estimate_as_of')
        _date(ctx['target_price_date'], 'target_price_date')
        _date(ctx['permit_date_assumption'], 'permit_date_assumption')
        year = _number(h['year_built'], 'year_built', positive=True)
        if year != year.to_integral_value() or year > asof.year:
            raise InputError('year_built must be an integer no later than estimate_as_of')
        if ctx['currency'] != 'USD':
            raise InputError('Only USD supported')
        if ctx['market_scenario'] not in ('ordinary_current', 'disaster_current', 'future_stress'):
            raise InputError('Unsupported market_scenario')
        result.update(estimate_as_of=ctx['estimate_as_of'], currency='USD',
                      target_price_date=ctx['target_price_date'])
        if (loc['county_fips'] != '06037' or h['dwelling_type'] != 'detached_site_built_single_family'
                or _number(h['unit_count'], 'unit_count') != 1):
            result['status'] = 'out_of_scope'
            return result
        if req.get('site', {}).get('requires_specialist') is not False:
            result['status'] = 'professional_review_required'
            result['review_flags'] = ['site.requires_specialist must be reviewed and explicitly false']
            return result
        if mode == 'benchmark':
            candidates = BENCHMARKS if benchmarks is None else benchmarks
            selected = [e for e in candidates if e.get('evidence_id') == req.get('benchmark_id')]
            if len(selected) != 1:
                result['status'] = 'pricing_unavailable'
                result['review_flags'] = ['No uniquely selected approved benchmark; no default rates available.']
                return result
            e = selected[0]
        else:
            e = req.get('cost_evidence')
            if not isinstance(e, dict):
                result['status'] = 'needs_cost_evidence'
                result['missing_inputs'] = ['cost_evidence']
                return result
        issues = _evidence_issues(e, req, mode)
        if issues:
            result['status'] = 'pricing_unavailable' if mode == 'benchmark' else 'needs_cost_evidence'
            result['review_flags'] = issues
            return result
        offered = e.get('scenarios', {})
        if not isinstance(offered, dict) or set(offered) - set(SCENARIOS):
            raise InputError('Unsupported scenario names')
        if not offered or not any(v.get('base_value') is not None for v in offered.values()):
            result['status'] = 'pricing_unavailable' if mode == 'benchmark' else 'needs_cost_evidence'
            result['missing_inputs'] = ['cost_evidence.scenarios.base_value']
            return result
        with localcontext() as context:
            context.prec = 80
            for name in SCENARIOS:
                if name in offered:
                    result['scenarios'][name] = _scenario(name, offered[name], e, req)
        totals = [Decimal(s['reconstruction_total_usd']) for s in result['scenarios'].values()
                  if s and s['reconstruction_total_usd'] is not None]
        if totals != sorted(totals):
            raise InputError('Scenario totals must be ordered low <= central <= high')
        available = [s for s in result['scenarios'].values() if s]
        result['status'] = ('incomplete_scope' if any(s['unresolved_categories'] for s in available)
                            else 'complete_planning_estimate')
        result['missing_inputs'] = [f'scenarios.{name}.{cat}' for name, s in result['scenarios'].items()
                                    if s for cat in s['unresolved_categories']]
        result['included_cost_components'] = list(e['includes'])
        result['source'] = {k: e[k] for k in ('evidence_id', 'source_id',
                            'source_url_or_document_ref', 'publication_date', 'price_base_date')}
        result['assumptions'] = [a for s in available for a in s['assumptions']]
        central = result['scenarios']['central']
        if central and result['status'] == 'complete_planning_estimate':
            result['estimated_rebuilding_cost_usd'] = central['reconstruction_total_usd']
        return result
    except (InputError, TypeError, AttributeError, KeyError) as exc:
        result.update(status='invalid_input', estimated_rebuilding_cost_usd=None,
                      scenarios=dict.fromkeys(SCENARIOS), review_flags=[str(exc)])
        return result
