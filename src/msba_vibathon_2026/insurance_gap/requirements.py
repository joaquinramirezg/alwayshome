"""Match upstream-confirmed facts to individually sourced rules, never assess photos."""
from copy import deepcopy
from .common import unique, verified


def match_requirements(properties, rules, *, selected_products, county_fips, as_of):
    unique(rules, 'requirement_id')
    findings = []
    for rule in rules:
        classification = rule.get('classification')
        if classification not in ('verified_requirement', 'recommendation', 'potential_discount_condition'):
            raise ValueError('Unknown requirement classification')
        applicable = rule.get('product_ids', [])
        if applicable and not set(applicable) & set(selected_products):
            continue
        if county_fips not in rule.get('county_fips', []):
            continue
        fact = properties.get('facts', {}).get(rule.get('field'), {})
        finding = {'requirement_id': rule['requirement_id'], 'classification': classification,
                   'product_ids': deepcopy(applicable), 'existing_condition': deepcopy(fact.get('value')),
                   'target_condition': deepcopy(rule.get('target')), 'field': rule.get('field'),
                   'status': 'unknown', 'verification_status': 'unverified',
                   'required_improvement': rule.get('improvement'), 'project_id': rule.get('project_id'),
                   'source': deepcopy(rule.get('source')), 'property_source': deepcopy(fact.get('source')),
                   'practical_impact': rule.get('practical_impact', 'unspecified')}
        if 'target_details' in rule:
            finding['target_details'] = rule['target_details']
            finding['applicability'] = rule.get('applicability')
        if (not verified(rule.get('source'), as_of)
                or rule.get('verification_status', 'verified_guidance') not in
                ('verified_guidance', 'verified_conditional_rule')):
            findings.append(finding); continue
        finding['verification_status'] = 'documented_rule'
        applicable = True
        for field, expected in rule.get('applies_when', {}).items():
            condition = properties.get('facts', {}).get(field, {})
            known = (condition.get('status') == 'confirmed' and verified(condition.get('source'), as_of)
                     and condition.get('value') is not None)
            if not known:
                finding['applicability_status'] = 'unknown'
                applicable = False
                break
            if type(condition['value']) is not type(expected) or condition['value'] != expected:
                finding.update(status='not_applicable', applicability_status='not_applicable')
                applicable = False
                break
        if not applicable:
            findings.append(finding)
            continue
        if (fact.get('status') != 'confirmed' or not verified(fact.get('source'), as_of)
                or fact.get('value') is None or str(fact.get('value')).lower() == 'unknown'):
            findings.append(finding); continue
        op, target, value = rule.get('operator'), rule.get('target'), fact['value']
        if op == 'equals':
            satisfied = type(value) is type(target) and value == target
        elif op == 'one_of' and isinstance(target, list):
            satisfied = any(type(value) is type(t) and value == t for t in target)
        else:
            raise ValueError('Only typed equals and one_of requirement operators supported')
        finding['status'] = 'met' if satisfied else 'improvement_needed'
        findings.append(finding)
    return {'status': 'catalog_unavailable' if not rules else
            'incomplete' if any(f['status'] == 'unknown' for f in findings) else 'matched',
            'findings': findings, 'limitations': [
                'A matched rule does not establish complete underwriting eligibility or a guaranteed discount.',
                'Product rules apply only to their named products; recommendations are not insurer requirements.']}
