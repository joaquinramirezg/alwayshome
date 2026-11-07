# David and Joaquin: Insurance Gap Engine handoff

On `feature/insurance-gap-analysis`, no commits or pushes. No property assessment,
policy extraction, frontend or wildfire file changes are part of this implementation.

```python
from msba_vibathon_2026.insurance_gap import analyze_insurance_gap

report = analyze_insurance_gap(
    canonical_payload,
    products=reviewed_products,
    requirements=reviewed_requirements,
    costs=reviewed_upgrade_costs,
)
```

The project Python environment installs this src-layout package (`uv sync`). No
extra library, remote API, keys or network is required. Money uses decimal strings
without rounding for display; report arithmetic is deterministic and independent
of the process-wide decimal precision. Inputs are defensively copied. The public
orchestrator catches malformed data as invalid_input; individual module functions
may raise ValueError for invalid catalog or numeric entries.

## Integration ownership and boundaries

David supplies subject-matched structured property facts and reviewed normalized
policy terms with evidence, not documents to parse. The gap team owns this boundary
and the arithmetic. The [contract](insurance_gap_contract.md) is intentionally
versioned independently from David's eventual schema. Supply a trusted adapter:

```python
report = analyze_insurance_gap(
    david_payload,
    adapter=my_david_to_gap_v1_adapter,
    products=reviewed_products,
    requirements=reviewed_requirements,
    costs=reviewed_upgrade_costs,
)
```

The callback receives a deep copy and must return canonical gap-v1. Do not execute
user-provided adapter code. No David-specific field mappings were guessed or added
to his modules. David/reviewer needs to confirm cost-to-coverage scope mapping,
policy effective dates, known absences versus unknowns, shared limits, endorsement
conditions, exclusions, deductibles, quote subjects, and evidence applicability.

Joaquin calls the function and renders returned sections/statuses. Incomplete
reports still contain useful supported findings and next actions. Do not render
null as $0, no_shortfall_identified as “fully insured,” a description as a quote,
or a named requirement as guaranteed eligibility. No frontend code is included.
Invalid inputs yield errors/no actions; failed extraction should pass null policy
or unknown facts so the local report can finish. Current source dates are supplied
by callers, not refreshed by this engine.

## Independent modules

- adapter.py: canonical boundary and explicit reviewed rebuilding allocation helper.
- coverage.py: dwelling, conditional ERC, ALE money/time, ordinance/law, debris,
  exclusions/endorsements and deductible exposure.
- alternatives.py: configurable product/quote distinction and documented comparisons.
- requirements.py: typed structured fact matching to individually documented rules.
- upgrades.py: reviewed cost ranges, deduplication and overlap detection.
- report.py: orchestration, missing-data statuses and prioritized homeowner actions.
- catalogs.py: reviewed public-reference loader; see [catalog coverage](insurance_reference_catalogs.md).
- common.py: finite Decimal parsing and source/date validation.

No module imports wildfire scoring, property extraction or frontend functionality.
The rebuilding estimator remains unchanged; its results need explicit policy-scope
allocation. No-shortfall findings use supplied planning evidence only. The engine
does not assert regulatory compliance or act as an insurer-certified valuation.

## Synthetic examples and validation

`docs/examples/insurance_gap_synthetic_input.json` contains an entirely fictional
subject, policy, product, requirement and cost catalog. Reports:

- `insurance_gap_underinsured_synthetic.json`: base dwelling gap $50,000;
  conditional 25% extension leaves $12,500; ALE dollar gap $10,000 and 12-month
  duration gap; ordinance/law gap $5,000; test upgrade range $100–$200.
- `insurance_gap_missing_policy_synthetic.json`: policy amounts unknown, retained
  property follow-up, no invented monetary gaps.

All values/sources/products in these files are synthetic tests, **not LA prices,
real insurance offers or underwriting advice**. They can be used to exercise UI
states without waiting for live catalog data. No fixture populates production defaults.

Run `.venv/bin/python -m unittest discover -s tests -v`. New tests cover missing and
adequate/insufficient limits, conditional extensions, shared scopes, exclusions,
deductibles, actual quotes versus descriptions, unknown facts, product-specific
rules, cost absence/expiry/geography, overlapping/duplicate work, priorities,
adapter behavior and deterministic arithmetic. Existing rebuild/wildfire tests
remain part of the full regression suite.

## Missing datasets and review dependencies

1. David's finalized schema/adapter, reviewed property facts and policy terms with
   source references and confirmation workflow. Unknown extraction is not absence.
2. Complete scope-supported reconstruction estimate; reviewed dwelling/debris/code
   allocations. Existing public benchmarks remain unapproved for default pricing.
3. Homeowner-specific documented ALE budget and plausible rebuilding duration;
   no universal percentage/month count is supplied.
4. Real product forms, endorsements, exclusions, geography and documented features
   with effective dates; verified current availability is separate from description.
5. Subject-specific actual quotes with periods and package scope to compare premiums.
6. Insurer/program-specific documented underwriting requirements and authoritative
   recognized mitigation recommendations/discount conditions. Existing measures.csv
   names/URLs alone do not establish universal underwriting rules or amounts.
7. Dated locally applicable installed-project price ranges or bids, reviewed project
   scope and consistent overlap tags. measures.csv prices are blank; discounts.csv
   supplies no numerical discount catalog. No blanks were filled.
8. Product review of priority assumptions; qualified policy review for overlapping
   coverages, FAIR Plan/DIC combinations, guaranteed-replacement conditions and
   legal questions. The engine deliberately does not resolve these from text.

The [reference catalog update](insurance_reference_catalogs.md) adds verified public
descriptions and mitigation guidance. Subject-specific quotes, policy interpretations
and current local project pricing remain missing; reports can remain incomplete.
Synthetic examples are never promoted into production data.
