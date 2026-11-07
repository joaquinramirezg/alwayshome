# Insurance Gap Engine: canonical input/output contract

Version `gap-v1`, 2026-11-06. This contract is a boundary owned by the gap engine,
not a claim that David's upstream schema is final. No property assessment, policy
extraction, frontend, geocoding or wildfire scoring occurs in these modules.
See [integration guide](insurance_gap_integration.md) and the entirely fictional
[synthetic payload/catalog example](examples/insurance_gap_synthetic_input.json).
All monetary fields are nominal USD, with decimal strings recommended on input
and always used for monetary outputs. Numeric unknowns are null, never zero.

## Evidence object used throughout

`source = {reference: string, verified: boolean, valid_from: ISO-date,
valid_through: ISO-date}`. A reference can be a URL or a private document/page
identifier. The caller attests that the source and structured interpretation were
reviewed and apply for that date interval. The engine checks those assertions and
dates, not the document's authenticity. No extraction is attempted. Invalid dates,
expired/unverified sources or absent references prevent evidentiary use.
Do not use synthetic sources in real decisions. Do not put homeowner documents in Git.

## Top-level input

| Field | Shape and meaning |
|---|---|
| schema_version | Required `gap-v1`. |
| as_of | Required ISO date; supplied rather than read from a clock. |
| currency | Required `USD`. No currency conversion. |
| subject_id | Required stable property identifier; must match property and current policy. |
| property | `{subject_id, county_fips, jurisdiction, facts}`; LA scope is county `06037`. |
| policy | Structured normalized policy object, or null if not yet available. |
| needs | Object keyed by dwelling, ale, ordinance_law, debris. |
| selected_product_ids | Product/program IDs whose individual requirements should be evaluated. An empty list does not apply every insurer's rules. |

Each `property.facts[field]` is `{value, status, source}`. `status` is `confirmed`
for a usable fact; uncertain/missing/unknown facts are not interpreted as failed
conditions. Values retain their types: boolean true does not equal integer 1.
Property facts may include assessments David already computed. This engine only
compares them with documented targets.

Each `needs[category]` is `{amount_usd, scope_id, source}` and optional
`duration_months` for ALE. It is a reviewed cost requirement for that exact policy
scope, not market value. A null amount means no monetary comparison. Living-cost
needs/duration must come from a documented user/reviewer budget, not an invented
percentage of rebuilding cost. No implicit summation across needs is performed.

### Rebuilding-estimator allocation

The existing estimator can contain demolition, code and other scope inside its
construction/base quote. Do not compare its full R to dwelling and then charge
those same embedded items again as independent deficits. First supply a reviewed
cost-to-policy mapping. `map_rebuild_need(result, scenario=..., amount_usd=...,
scope_id=..., source=...)` validates a complete scenario and an allocation no larger
than its total. It sets `allocation_review_required: true`; a reviewer must resolve
that flag to false before coverage quantification. The helper neither infers scope
nor proves that allocations across categories do not overlap. Keep that mapping
and underlying ledger in the upstream evidence record. Call per scenario when
low/central/high cost cases are supported; do not invent missing scenarios.

## Normalized policy object

| Field | Shape / behavior |
|---|---|
| subject_id, source | Subject match and current reviewed evidence. |
| terms_reviewed, exclusions_reviewed | Must both be true for quantitative coverage screens. Unknown extraction is not an absence finding. |
| coverages | Object keyed by dwelling, ale, ordinance_law, debris. |
| extended_replacement | Extension object below; separate from base dwelling limit. |
| deductible | Deductible object below; one documented applicable scenario/peril. |
| exclusions | List of `{peril, effect, categories, description?, source}`. |
| endorsements | List of source-backed structured terms/notes for human review. |
| features | Optional feature-key to `{value, source}` for product comparisons. |
| premium | Optional `{annual_premium_usd, currency, comparison_basis, source}`. |

Each coverage object: `{status, limit_usd, limit_basis, scope_id, source}` plus
optional `duration_months` for ALE. Present dwelling coverage additionally requires
`settlement: replacement_cost` for replacement-cost gap arithmetic.
Actual_cash_value, unknown or missing settlement produces `settlement_review` with
null dwelling/extension gap amounts; it does not imply the policy has no benefits.
`status` is present/absent/unknown. Explicit
source-backed absent coverage permits using zero as the limit; an unknown does
not. Contradictory absent coverage with a positive limit is invalid.
`limit_basis` is standalone/additional/within_dwelling/shared/unknown.
Only standalone/additional limits can be independently screened. Within-dwelling,
shared, and unknown bases yield `shared_limit_review`; the engine does not allocate
shared pools or add percentages to Coverage A automatically.

For a reviewed matching scope, `gap_usd = max(need_usd - limit_usd, 0)`. This is a
scope-specific limit screen, not expected proceeds. A no-shortfall result never
means the entire policy is adequate. ALE dollar and duration shortfalls are
reported separately; missing duration keeps the assessment incomplete.

Extended replacement: `{kind, value, conditions_verified, scope_id, source}`.
Kinds: none/percentage/additional_limit/guaranteed/unknown. Percentage is entered
in percentage points: `25` means 25%, not `.25`. Where the dwelling scope is
quantified and conditions are verified, conditional capacity is base limit times
`(1 + value/100)` or base limit plus additional_limit. This is not unconditional
cash; the report preserves the base shortfall and extension screen separately.
Guaranteed replacement gets a terms-review finding, not an infinite dollar limit.
A missing extension is flagged even if the current cost screen shows no shortfall.
No aggregate dollar gap is calculated across findings or policies.

Deductible: fixed `{kind: fixed, amount_usd, source}` or percentage
`{kind: percentage, percent, basis_usd, basis_verified: true, source}`.
The second computes percent × documented basis / 100. Different peril deductibles
or multiple-policy interactions require separate reviewed inputs/calls. It is
reported as personal exposure, not added to a summed gap or subtracted from every
limit. An affordability threshold is not invented.

Wildfire exclusions matching a category produce `excluded` with no numeric
shortfall/proceeds claim. Documented limitations require review before that
category is quantified. Unverified exclusions block quantitative screens.
Endorsements remain explicit review findings: the caller must already have
normalized their effects into the supplied coverage limits/conditions. The engine
cannot interpret arbitrary policy text, decide legal applicability or combine
FAIR Plan/DIC policies. A qualified upstream reviewer must resolve those interactions.

## Catalogs: trusted keyword arguments, not homeowner declarations

Default `catalogs.py` loads the reviewed public-reference snapshot described in
[reference catalogs](insurance_reference_catalogs.md). Explicit empty catalogs
remain supported. No data is invented from the existing blank tables.

**Product** fields: unique product_id, name, evidence_type
(public_description/actual_quote), county_fips list, source, features map,
coverage_terms object, deductibles list, exclusions list, requirement_ids list.
Features each have value/source; limits and condition descriptions are displayed
as documented terms rather than merged into the current policy. Different feature
values trigger review, not a claim of superiority. Application reviewers must
ensure broad term objects are covered by the product source.

Optional quote: subject_id, currency USD, annual_premium_usd, comparison_basis,
source. Premiums display only for an actual_quote with a current source and exact
subject match. A premium difference additionally needs verified current premium
with the same comparison_basis (period/peril/package scope). A public-description
entry's quote-like numbers are ignored. Receiving a quote is not a guarantee of
binding/acceptance. No product ranking or universal “best insurer” is asserted.

**Requirement** fields: unique requirement_id, classification
(verified_requirement/recommendation/potential_discount_condition), product_ids,
county_fips, field, operator (equals/one_of), target, improvement, project_id,
practical_impact (high/medium/low/unspecified), source. Empty product_ids is reserved
for recognized general recommendations/program standards, not an undocumented
universal underwriting rule. The curator must establish rule authority and
classification. Named-product rules apply only to selected IDs. Unknown source or
fact produces an unknown finding with no automatic upgrade. One_of uses a typed
list of target values. Numeric engineering/code thresholds must be normalized into
an independently verified structured fact upstream; no numeric threshold is inferred.

**Upgrade cost** fields: unique cost_id, project_id, county_fips, jurisdiction,
price_date, source, unit USD_per_project, low_usd, high_usd, scope_reviewed true,
scope_description and nonempty scope_tags. Costs represent a documented installed
whole project. Jurisdiction must match exactly; no time/location multipliers,
contingency, percentage discounts or extrapolation by square footage is added.
Multiple applicable rows for one project yield ambiguous_pricing rather than a
silent selection. Missing/expired/unverified price evidence leaves amounts null.

## Output

`gap-report-v1` contains status, subject_id, as_of, currency, coverage,
alternatives, property_requirements, upgrades, actions, missing_inputs,
prioritization_assumption and limitations. Normal statuses are screened/incomplete;
invalid_input contains errors and no actions; out_of_scope returns no actions.
Screened means a preliminary screen ran, not that coverage or eligibility is adequate.

- Coverage: findings per category plus exclusions/endorsements, gap_usd (nullable),
  need/available/conditional limit strings, deductible exposure, ALE duration gap,
  evidence and action; aggregate_gap_usd is always null.
- Alternatives: source-dated product terms, per-feature comparisons, nullable actual
  quote premiums/differences and explicit uncertain eligibility; ranking is null.
- Property requirements: observed/target conditions, classification, improvement,
  status met/improvement_needed/unknown, named products, sources and verification.
- Upgrades: unique projects, contributing rule IDs, non-overlapping scope prices,
  sources, geography/date, per-project status and nullable low/high total.
- Actions: stable ordering, reason, priority tier, property/policy follow-up and
  supported amounts. Missing facts lead to verification, not assumed construction.

Projects with identical project_id merge once. Different projects sharing a
scope_tag both become overlap_review_required and no combined total is given.
This requires consistent scope tags from the curator. Semantic overlap cannot be
detected if the curator incorrectly assigns disjoint tags. Missing project prices
make the total null; no partial subtotal is mislabeled a whole plan. No identified
projects yields null totals, not proof that no mitigation is needed.

Prioritization is an explicit MVP product assumption: exclusions first, quantified
coverage shortfalls/missing coverage next, named requirements, verification/exposure
tasks, then recommendations/discount conditions. Within a tier, documented practical
impact high/medium/low is followed by known low cost ascending. Unpriced work is
not represented as free. No quantified loss reduction, premium savings, payback,
fixed eligibility outcome or legal urgency is inferred from this ranking.
