"""Shared deterministic validation; monetary amounts are nominal USD strings."""
from datetime import date
from decimal import Decimal, InvalidOperation


def money(value):
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError('Boolean is not a monetary amount')
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('Invalid monetary amount') from None
    if not number.is_finite() or number < 0 or len(number.as_tuple().digits) > 24 or abs(number.adjusted()) > 15:
        raise ValueError('Expected finite nonnegative monetary amount within supported precision')
    return number


def text_money(value):
    return None if value is None else format(value, 'f')


def verified(source, as_of):
    """Attestation validation only; never authenticates a policy or quote."""
    if not isinstance(source, dict) or source.get('verified') is not True or not source.get('reference'):
        return False
    try:
        return date.fromisoformat(source['valid_from']) <= date.fromisoformat(as_of) <= date.fromisoformat(source['valid_through'])
    except (KeyError, TypeError, ValueError):
        return False


def unique(rows, key):
    ids = [r[key] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f'Duplicate {key}')


def validate_context(data):
    date.fromisoformat(data['as_of'])
    if data.get('currency') != 'USD':
        raise ValueError('Only USD supported')
    if not data.get('subject_id'):
        raise ValueError('subject_id required')
