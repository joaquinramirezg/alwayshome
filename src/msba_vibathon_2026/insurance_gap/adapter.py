"""Boundary for David's structured outputs; no assessment or document extraction."""
from copy import deepcopy


def adapt_inputs(payload, *, adapter=None):
    """An app-supplied adapter maps David's evolving schema into gap-v1.

    Adapter is trusted Python code, never a string/function supplied by a user.
    Canonical payloads pass through with a defensive copy.
    """
    result = adapter(deepcopy(payload)) if adapter else deepcopy(payload)
    if not isinstance(result, dict) or result.get('schema_version') != 'gap-v1':
        raise ValueError('Expected canonical schema_version gap-v1; supply a schema adapter')
    return result


def map_rebuild_need(rebuild_result, *, scenario, amount_usd, scope_id, source):
    """Explicit reviewed coverage allocation; never assume gross rebuild = Coverage A.

    David/reviewer supplies an allocation to one policy scope. Embedded debris/code
    costs cannot automatically be extracted from the estimator's combined totals.
    """
    from .common import money
    case = rebuild_result.get('scenarios', {}).get(scenario)
    if not case or case.get('completeness') != 'complete' or case.get('reconstruction_total_usd') is None:
        raise ValueError('A complete supported rebuilding scenario is required')
    value = money(amount_usd)
    if value is None or value > money(case['reconstruction_total_usd']) or not scope_id:
        raise ValueError('Invalid reviewed coverage allocation')
    return {'amount_usd': str(value), 'scope_id': scope_id, 'source': deepcopy(source),
            'rebuild_scenario': scenario, 'allocation_review_required': True}
