# Rebuilding engine integration

Implemented API on `feature/insurance-gap-analysis`; no insurance comparison or
wildfire integration. The methodology, schema and source register remain the
pricing/scope authority. This document defines the narrower executable v1 adapter.

```python
from msba_vibathon_2026.rebuilding import estimate_rebuilding

result = estimate_rebuilding(request)
# JSON-safe result; inspect status before displaying any amount.
```

Run with the project environment (`uv sync` installs the src-layout package).
No additional dependencies, API keys or network are required. Tests can be run with
`.venv/bin/python -m unittest discover -s tests -v`.

## Resolved ambiguities and deferred features

- **No approved numerical benchmark exists.** `rebuilding_benchmarks.py` holds an
  empty catalog. Benchmark mode returns `pricing_unavailable`, the requested
  explicit subtype of the design's `needs_cost_evidence`. There is no rate fallback.
  The county range and national survey remain context only.
- **Freshness threshold is not approved.** Require a human reviewer's explicit
  `valid_through` date instead of inventing a universal age threshold. This is a
  caller assertion, not independent authentication. Recheck pricing before reliance.
- **Location and time adjustment models are not approved.** V1 requires an exact
  jurisdiction and target price-date match, so L=T=1. Obtain refreshed localized
  evidence rather than supplying unreviewed multipliers. Quality, construction,
  stories, area convention, market scenario and rebuild scope must match too.
- **No automatic quality/age/surge/contingency markups.** Extra categories accept
  documented dollar amounts in the same reviewed estimate. Percentage and
  quantity-based allowances must be resolved to documented USD outside this engine.
- **Complex site support remains outside standard MVP.** Require explicit completed
  site screening and `requires_specialist: false`; true/unknown requires review.
- **One evidence packet per call.** A reviewer must reconcile source documents and
  included/excluded scope into that packet. No merging of unrelated quotes or
  scenarios, automatic currency conversion, geocoding, policy interpretation or
  index lookup occurs here. Source verification/approval fields are trusted human
  attestations; passing them is not certification.
- **Scope completeness is categorical.** Each category is covered exactly once.
  One separate line per category; aggregate substantiated subitems before calling.
  Embedded categories cannot also carry an extra amount. Category checks cannot
  detect two misleading descriptions of the same real-world work: the reviewer
  must reconcile scope, taxes, attached features and foundation work explicitly.
- **Determinism:** no generated wall-clock timestamp is added. `estimate_as_of` is
  supplied. Decimal arithmetic uses a local fixed precision; outputs are exact
  decimal strings in nominal USD, without display rounding. Numeric inputs accept
  strings/numbers, reject bool/nonfinite/negative values; input is not mutated.
- **Validation behavior:** malformed requests return `invalid_input`; missing
  property data returns `needs_property_inputs`; unsuitable quote evidence returns
  `needs_cost_evidence`; supported evidence with missing cost scope returns
  `incomplete_scope`. None produces a complete dollar estimate. Out-of-scope homes
  and complex sites have explicit statuses. This adapter does not implement every
  optional field in the proposed schema.

## Request contract

Use the executable synthetic fixture in `tests/test_rebuilding.py::fixture` as a
complete payload example. **All its rates, amounts, address, jurisdiction, quality
categories, source and reviewer are fictional test data. Never seed production
pricing with it.**

Top-level `mode` is `documented` or `benchmark`. Reuse `address`, `home`,
`location` and `estimate_context` as described in the proposed schema. Required
screening includes:

- `home`: positive total `living_area_sqft`, `area_definition`, `area_source`,
  `area_confirmed: true`, construction/foundation type, stories, year built,
  detached site-built single-family `dwelling_type`, `unit_count: 1`,
  `quality` object (source_category, description, homeowner_confirmed: true),
  `materials` (roof/exterior), and `features_reviewed: true`.
- `location`: county_fips `06037`, actual permitting_jurisdiction,
  jurisdiction_verified: true. Caller resolves county and jurisdiction; postal
  address alone does not prove them.
- `site`: screening_complete: true, requires_specialist: false. These confirmations
  assert the schema's site/feature checklist was reviewed; retain underlying notes
  in field_provenance/site fields.
- `estimate_context`: ISO estimate_as_of, target_price_date, permit_date_assumption;
  currency USD; market_scenario ordinary_current/disaster_current/future_stress;
  rebuild_scope (must agree with evidence). Year built cannot exceed as-of year.

In documented mode `cost_evidence` is **one object**, rather than the proposed
array. It represents a consolidated reviewed reconstruction quote/rate packet:

| Field | Requirement |
|---|---|
| evidence_id, source_id, source_url_or_document_ref | Nonempty evidence identity and document/URL reference; retain private quotes outside Git. |
| publication_date, price_base_date, year | ISO document/price dates; year matches price-base year. Quote date is publication_date. |
| reviewer, reviewed_at, valid_through | Named scope reviewer, ISO review and expiry dates; review/publication cannot be after estimate_as_of; expiry cannot precede as-of or base date. |
| verification_status, parameter_status | full_document_verified and approved_for_this_scope. |
| quoted_address, quoted_living_area_sqft | Exact subject address and confirmed area; prevents applying an unrelated lump-sum quote to another home/size. |
| county_fips, permitting_jurisdiction | Exact location match. |
| quality, construction_type, stories, area_definition, property_scope | Exact match to property; property_scope matches dwelling_type. |
| currency, market_scenario, rebuild_scope | Exact match to estimate_context. |
| scope_description, building_scope_confirmed | Description plus true confirmation that foundation, fixed systems, attached features and taxes are reconciled. |
| unit | USD_per_finished_sqft or USD_lump_sum. |
| includes, excludes | Disjoint lists partitioning all nine engine cost categories; construction must be included. |
| scenarios | Only supported low/central/high cases, each with base_value, rationale, optional assumptions array and items array. |

Benchmark mode selects `benchmark_id` from the separate trusted catalog. Entries
use the same evidence fields, plus a numeric `[minimum, maximum]` size_band_sqft;
quoted-address/area fields are unnecessary. Only USD_per_finished_sqft is supported
for benchmarks. The optional Python keyword `benchmarks=` is a catalog injection
point for application-owned reviewed data/tests, not an untrusted homeowner input.
Selection must be unique; applicability and approval checks still run. Production
catalog entries must additionally satisfy the source register's provenance and
reuse approval requirements; none are currently supplied.

Scenario `base_value` means USD/ft² or lump-sum USD according to unit. It is the
priced construction/combined-quote base, not a policy limit or market value.
For each excluded category, supply one item with `category`, `scope_state` and:

- separately_priced: nonnegative `amount_usd` and nonempty `documentation` from
  the reviewed packet describing source/scope and basis;
- not_applicable_verified: nonempty documentation, no amount;
- unresolved: no amount; total remains null.

Included categories appear automatically in the ledger as included_in_base with
no additional amount. An explicit included_in_base item is allowed only if the
source already includes that category and the item has no amount. Repeated
categories, a second construction item, or amounts for embedded/inapplicable scope
are rejected. Missing excluded categories remain unresolved. Zero amounts are
accepted only as explicit documented values, never inferred from missing data.

Engine categories (the methodology's H/O/D/P/F/C/U/W/Q) are `construction`,
`contractor_overhead_profit`, `demolition_debris`, `professional_services`,
`permits_agency_fees`, `incremental_code`, `extraordinary_site_utilities`,
`incremental_disaster_pressure`, `contingency`.

## Output and example

`status` is the primary UI gate. `scenarios` always has low/central/high keys;
unsupported cases are null. Each offered case returns a complete total or null,
a clearly separate known-cost subtotal, construction subtotal, per-category
scope ledger, unresolved categories, evidence metadata, rationale, assumptions,
and identity adjustment factors. `source` records the main document/date;
item documentation preserves the consolidated supporting references.

`estimated_rebuilding_cost_usd` is the central total only when every offered
scenario is complete and central exists. Complete low/high cases may exist with
no central; do not manufacture one. Scenario totals are checked in low-to-high
order where complete totals exist. Bounds are evidence-supplied planning cases,
not confidence intervals. Included categories, excluded non-reconstruction costs,
missing inputs, review flags, assumptions and limitations are explicit.
`coverage_comparison_ready` always remains false: policy comparison is unimplemented.

Synthetic test: 1,000 ft² × **$100/ft²** = $100,000. Add demolition $10,000,
professional services $5,000, fees $2,000, incremental code $3,000 and site costs
$4,000, all fictional. Overhead/profit is already in the base; disaster allowance
and contingency are explicitly reviewed as inapplicable to this synthetic case.
Central total = **$124,000**. Two stories do not multiply total living area again.
Supplied synthetic rates of $90/$100/$120 with the same itemized additions yield
low/central/high totals of **$114,000/$124,000/$144,000**. No real LA price is implied.
