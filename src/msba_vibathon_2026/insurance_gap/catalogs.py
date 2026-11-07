"""Load reviewed public reference snapshots, separately from arithmetic.

These are descriptions/guidance, never quotes. Historical unit-cost observations
are retained but cannot drive LA whole-project totals. See the source register.
"""
from copy import deepcopy
from importlib.resources import files
import json


def load_reference_catalogs():
    root = files(__package__).joinpath('reference_data')
    def read(name):
        return json.loads(root.joinpath(name + '.json').read_text(encoding='utf-8'))
    sources = read('sources')
    by_id = {s['source_id']: s for s in sources}
    if len(by_id) != len(sources):
        raise ValueError('Repeated reference source ID')
    def resolve(rows):
        for row in rows:
            row['source'] = deepcopy(by_id[row['source_id']])
            for feature in row.get('features', {}).values():
                feature['source'] = deepcopy(by_id[feature['source_id']])
        return rows
    return {'sources': sources, 'products': resolve(read('products')),
            'requirements': resolve(read('requirements')),
            'costs': resolve(read('upgrade_costs'))}


_CATALOGS = load_reference_catalogs()
PRODUCTS = tuple(_CATALOGS['products'])
REQUIREMENTS = tuple(_CATALOGS['requirements'])
UPGRADE_COSTS = tuple(_CATALOGS['costs'])
