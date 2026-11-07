# Joaquin integration instructions and acceptance checklist

End-to-end validation, 2026-11-06. No frontend or shared app files changed.
The shared app/coverage interfaces were inspected at pinned revisions in
[David mapping](david_to_gap_mapping.md); a concrete automatic David adapter remains
blocked on reviewed provenance and semantics. This guide does not claim deployment
or compatibility with the current app's assess/CoverageResult output schema.

## Call boundary

```python
from msba_vibathon_2026.insurance_gap import analyze_insurance_gap
from msba_vibathon_2026.insurance_gap.catalogs import load_reference_catalogs

# canonical_payload must have gone through the confirmation/mapping workflow.
refs = load_reference_catalogs()
report = analyze_insurance_gap(
    canonical_payload,
    products=refs['products'], requirements=refs['requirements'], costs=refs['costs'],
)
```

Use `uv sync` to install the src-layout package, or run the provided scenario CLI
which locates src explicitly. No key, PDF, network or ML call occurs in this engine.
Rebuilding is called separately via estimate_rebuilding. Complete rebuild output
still needs explicit cost-to-policy scope allocation. Do not set source verification,
review flags or allocation approval merely to obtain a dollar result.

The optional adapter keyword accepts trusted application Python mapping code, not
arbitrary user code. For now use canonical gap-v1 fixtures for UI exploration and
coordinate the missing fields with David before mapping live extraction.

## Mount separately from existing app coverage

Prefer a separately versioned report object/view under an agreed app key; proposed
name `insurance_gap_report`. This is a proposal, not a patch to the app contract.
Do not overwrite `current.coverage`, reinterpret current.insurance_gap severities,
or append our gaps to an existing summed coverage deficit. Remote CoverageResult
uses a different model and arithmetic. Resolve which report owns the homeowner
numbers before enabling both. No payment, expected-loss, discount/payback or house
impact figure can be generated from this report by display-layer inference.

## Rendering behavior

- Check schema_version and status before reading nested result fields. invalid_input
  has errors/no actions; out_of_scope has no assessment. Show actionable validation
  feedback, not an all-clear. Do not silently retry by filling zeros.
- An incomplete report is still useful: show supported findings with their sources,
  missing_inputs and reasons. Each finding's own status governs its dollar display.
- Render decimal monetary strings with a display formatter only; preserve source
  values. Null is “unknown / needs verification,” never $0. A $0 **gap** means no
  shortfall identified for that one reviewed scope, not a free project or fully
  insured property.
- Show base dwelling shortfall and conditional ERC screen separately. Do not add
  these together. ACV/unknown settlement needs review; a face limit is not proven
  replacement proceeds. Missing settlement also blocks monetary gap arithmetic.
- Deductible exposure is separate cash planning, not another coverage limit or an
  amount to add to every finding. The engine intentionally has no aggregate gap.
- ALE amount and duration are separate; a duration-only deficit is prioritized as
  a shortfall. Fair rental value must not be relabeled comprehensive ALE.
- Display product entries as public references, not selectable guaranteed offers.
  Premiums/availability/eligibility remain unknown; Mercury's CA-specific feature
  applicability is unresolved in the public reference. Do not show savings badges.
- Property statuses distinguish unknown, not_applicable, met and improvement_needed.
  A verification task is not a mandate to replace an unknown feature. Named-product
  discount conditions are not universal mandatory underwriting rules.
- Show unique project IDs, scope and price status. The real catalog contains no
  approved current LA installed prices. Do not price projects from historical
  per-vent/per-foot examples, substitute remote app assumptions, or present null as
  zero. Overlapping scope tags prevent a total until reviewed.
- Preserve priority tiers and reasons as product assumptions. Do not relabel ordering
  as measured loss reduction or a guarantee of acceptance/discounts.

## Ready-to-run synthetic examples

Run:

```sh
.venv/bin/python scripts/validate_insurance_gap_e2e.py
.venv/bin/python -m unittest discover -s tests -v
```

The fixture is `tests/fixtures/insurance_gap_e2e.json`. Generated artifacts are in
[examples/e2e](examples/e2e/): each includes synthetic labels, exact request, actual
rebuilding result, reviewed synthetic gap_input and actual gap_report. Three cases:
underinsured with mitigation gaps; sufficient supplied limits but unknown property
facts; limited FAIR-type coverage with unknown reconstruction pricing.

All household amounts and conditions are synthetic. None is a real quote/premium,
current LA mitigation cost or actual homeowner assertion. The real reference snapshot
is deliberately pinned to 2026-11-06. Do not change the as_of date to mask expired
reference data; reverify the catalog or show incomplete results for later dates.

## Pre-integration acceptance gates

1. Agree with David on normalized versus merged versus PolicyInput input variant,
   ERC units, subject matching, confirmation and source/date sidecars.
2. Confirm policy settlement, shared/independent limits, exclusions and endorsements.
   Do not treat a text-match verified flag as an interpretation review.
3. Establish reconstruction evidence and non-overlapping allocations; provide
   documented ALE budget and duration. Unknown reconstruction remains unknown.
4. Agree whether this engine replaces or coexists with origin/coverage-gap's now
   connected app scenario module; no duplicate payout totals or mixed assumptions.
5. Verify the report can be displayed without changing the existing app's future.fixes
   schema or manufacturing savings/impact/payback fields.
6. Refresh public sources for the actual report date; obtain prices/quotes separately.

These are integration blockers/dependencies, not requests for permission to change
team-owned code. No integration or production-readiness approval is implied by
passing local tests.
