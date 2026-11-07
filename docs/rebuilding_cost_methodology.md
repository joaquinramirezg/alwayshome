# Residential rebuilding-cost methodology proposal

Research/design only, **2026-11-06**, Los Angeles County MVP. No estimator is
implemented. This is a planning estimate of single-property reconstruction after
a total loss at the original site, excluding land. It is not an insurer-certified
replacement-cost valuation, a contractor bid, a promise of policy benefits, or a
finding that the dwelling limit is adequate. Dollar parameters remain unapproved.

Companion deliverables: [source register](rebuilding_cost_sources.md) and
[proposed input/output schema](rebuilding_cost_schema.md).

## Repository findings and reuse

The repository uses Python 3.14+, pandas, GeoPandas, PyArrow, requests and existing
Census geocoding helpers in `scripts/utils.py` (`geocode`, `area_context`). No new
library is necessary for a later transparent arithmetic estimator. The package
entry point is a placeholder; no reconstruction estimator or cost benchmark table
was found. `docs/inputs_and_contract.md` already asks for address, living area,
stories, year built and dwelling limit: reuse those fields rather than asking twice.
It explicitly calls rebuild USD/ft² an assumption; this proposal replaces that
placeholder with a provenance requirement, without changing the existing contract.

Processed assets include Zillow ZIP values, ACS median values, DINS building
attributes/cleaned year built and assessed improvement value, FEMA tract building
values, insurance aggregates and wildfire features. **None is a property rebuilding
cost dataset.** ZIP market values, sales prices, assessed land or improvement values,
and FEMA aggregate building exposure must never substitute for rebuilding cost.
DINS is a disaster-inspection sample, not a complete county property inventory.
Its missingness/outcome leakage warnings remain applicable; do not infer construction
quality or costs from observed destruction. No general assessor parcel inventory
or verified labor/material price catalog is currently processed.

Reuse geocoding and existing hazard context as read-only inputs. A postal city or
ZIP is not the building department; resolve the actual permitting jurisdiction.
Geocoder failures should lead to manual location confirmation. Do not turn the
wildfire score into a cost multiplier. The wildfire pipeline is outside this work.

## Estimand and MVP scope

Recommend an initial scope of detached, site-built, single-family dwellings rebuilt
to equivalent size and finish quality, with applicable code compliance. Count all
finished living floors once. Record the area convention used by the cost source;
finished living area, gross construction area and footprint are not interchangeable.
Do not multiply total living area by stories again.

Include the dwelling's foundation, structure, roof, finishes, fixed equipment,
utilities serving the dwelling and attached features when explicitly priced.
Exclude land acquisition/value, mortgage balance, sale commissions, movable
contents, temporary accommodation/ALE, landscaping and optional betterments.
Detached garages/ADUs, pools and other structures need separate budgets and policy
mapping; do not silently fold them into dwelling living area. Separate optional
financing/carrying costs from the core reconstruction subtotal until their scope
and relevance to the later policy comparison are reviewed.

Condominiums, manufactured homes, mixed-use buildings, multifamily properties,
major historic restoration, and unusual hillside/coastal/geotechnical work require
specialist assessment rather than extrapolation from a standard house rate.

## Inputs and their priority

| Input | MVP requirement | Use and treatment if unknown |
|---|---|---|
| Address, county and actual permitting jurisdiction | Essential | Select local evidence and fees; unresolved match prevents a localized estimate. |
| Living area, ft², area convention and source | Essential | Positive homeowner-confirmed total; no size inferred from ZIP averages. |
| Dwelling type and units | Essential | Gate the initial single-family scope. |
| Framing/construction type, foundation, roof/exterior materials | Essential screening | Match estimate scope; unknown needs clarification or professional review, not a silent “wood frame” default. Reuse existing material questions. |
| Construction/finish quality | Essential | Homeowner-confirmed description of finishes, custom work and complexity; use definitions from the selected quote/source, not an invented quality multiplier. |
| Stories | Essential | Select comparable construction, not a second area multiplier. |
| Year built and major renovation dates | Essential screening | Flag potential code/hazardous-material review; do not depreciate replacement cost or apply a generic age percentage. Unknown flags review. |
| Attached garage, decks, porches, basement and unusual features | Essential screening; areas/details conditional | Establish whether already in rate or separately priced. |
| Slope/access constraints, foundation reuse, utility/septic status | Essential screening | Unknown or complex sites need site review; assume no foundation salvage credit without engineering evidence. |
| Price date, local labor/material environment and benchmark scope | Essential cost evidence | Prefer a current local single-property quote; no numerical output without a supported rate. |
| Demolition/debris, code work, soft costs, fees and site work | Essential cost categories | Each must be included, separately priced, verified inapplicable, or unresolved. |
| Reconstruction timing and ordinary versus disaster-market scenario | Essential scenario context | Distinguish current-date estimate from future price forecast. |
| Detailed quantities, roof geometry, bathrooms, systems, custom joinery | Optional refinement for simple homes | Become essential if the selected source depends on them or features are material. |
| Assessor ID, plans, prior reconstruction estimate | Optional evidence | Helps confirm area and scope; assessor prices remain excluded. |
| Dwelling limit, endorsements and deductibles | Later gap calculator | Not needed to estimate cost; never use coverage limit to calibrate cost. |

## Recommended calculation

For scenario s in {low, central, high}, first define a documented comparable
single-home construction rate:

`H_s = A × b_s × L_s × T_s`

- `A`: confirmed living area in ft², aligned to the source denominator.
- `b_s`: sourced construction USD/ft² at its stated price date and location,
  matched to construction, quality and stories. The source must say whether
  foundation, attached features, taxes and contractor overhead/profit are included.
- `L_s`: documented location adjustment only if the source is not already local.
- `T_s`: documented time adjustment only when the source and estimate dates differ.

`L_s = 1` for a source already applicable to this location and `T_s = 1` for the
same price date: these are scope identities, not estimated universal multipliers.
Otherwise unknown factors remain null. Avoid a national rate for the MVP because
no defensible LA spatial factor has been verified. DGS CCCI may later support
`T = index_target / index_base` for compatible labor/material scope, following
review; it is not a local residential bid index or a disaster surge measure [S4].

Then calculate a reconciled budget:

`R_s = H_s + O_s + D_s + P_s + F_s + C_s + U_s + W_s + Q_s`

| Term | Meaning | Double-counting control |
|---|---|---|
| H | Matched construction subtotal | Labor/materials and defined building work; record all embedded categories. |
| O | Contractor overhead/profit not already in H | Add only with source and an explicit eligible dollar base; no automatic markup on the entire budget. |
| D | Demolition, debris hauling/disposal, hazardous material handling | Separate ordinary and hazardous scope; do not assume a government cleanup program makes economic cost zero. |
| P | Architecture, structural/geotechnical engineering, survey, energy documentation and related professional services | Add only services excluded from H and other items. |
| F | Building/plan check, fire, planning and other applicable agency fees | Jurisdiction- and project-specific; distinguish deferral from waiver. |
| C | Incremental code compliance outside the priced construction specification | Current-code work already in H must not be charged again. |
| U | Extraordinary site preparation/access, utilities, foundation or other dwelling-related work outside H | Include normal foundation work in one place; no unverified salvage credit. |
| W | Documented incremental disaster-market cost not captured elsewhere | Apply only to specified affected categories; recent disaster-market quotes may already include it. |
| Q | Explicit scenario contingency allowance for identified residual uncertainty | No unsupported percentage; cannot replace missing known scope or duplicate W/code allowances. |

Each category has a scope state: `included_in_base`, `separately_priced`,
`not_applicable_verified`, or `unresolved`. Embedded/inapplicable terms add no
increment, but that is not evidence their underlying work has no cost. Unresolved
terms produce an **incomplete estimate with a null total**, optionally displaying
a clearly labeled known-cost subtotal. Never present that subtotal as a full rebuild
budget. An all-in contractor quote can provide R directly if its inclusions are
reconciled; do not add categories that quote already includes.

The objective is gross resource cost. Track confirmed fee relief or other assistance
separately, with eligibility and date, rather than silently subtracting it from
reconstruction cost. Do not assume public debris removal or relief will be available
for a hypothetical future wildfire. These distinctions require review in a later
cash-needed calculator.

## Evidence and benchmark decisions

The [register](rebuilding_cost_sources.md) gives exact links, dates, geography,
units and verification status. CDI guidance favors a local contractor estimate
and explicitly flags disaster-driven shortages [S1]. Replacement-cost estimating
standards supply a useful scope checklist, but current full-text/legal review is
still required [S2]. Public FEMA damage tools serve a different flood-regulatory
purpose; their structure-market-value tests are not insurance cost benchmarks [S9].

A county memo dated June 6, 2025 reports a broad $300–$800/ft² range in the
Eaton/Palisades recovery context [S3]. Its inclusions and sample are insufficiently
specified. Retain it as historical plausibility context only; do not select its
midpoint as a “central” estimate or add fees to it as though exclusions were known.
NAHB's national 2024 construction figure is also unsuitable as an LA rebuild default;
its scope already contains some soft costs while separating overhead/profit [S5].

**Recommended MVP:** homeowner supplies a dated, scoped local contractor/qualified
estimator reconstruction estimate, or a reviewer-approved comparable local rate.
The tool reconciles living area, scope and additional costs transparently. If no
such evidence exists, return `needs_cost_evidence`, provide the input checklist,
and do not fabricate an address-only amount. A broad sourced contextual range
may be shown separately with its date and limitations, never as the homeowner's
estimated budget or underinsurance verdict.

No public source reviewed establishes a complete, current, free LA single-property
cost matrix by construction quality/stories. Obtain scope-aligned local estimates
before enabling numerical defaults. Commercial replacement-cost products may be
investigated later with licensing and coverage review; none is integrated here.

## Scenarios and uncertainty

Low, central and high must hold the home's size, quality and rebuild scope constant.
Use comparable local estimates reconciled to the same inclusions, or documented
line-item bounds from a qualified estimator. Central is a selected best-supported
estimate, not automatically the arithmetic midpoint. Low/high are planning scenarios,
not confidence bounds, minimum/maximum possible costs, or statistical percentiles.
No arbitrary ± percentage, automatic wildfire surcharge or age uplift is approved.

Separate uncertainty in property data, estimate scope, prices, site conditions,
code applicability and timing. Document dependence between items: demand surge may
already affect labor, fees may depend on valuation, and design/site costs may move
together. Do not combine unrelated minima and maxima and claim statistical coverage.
If only one estimate is supported, report only central; low/high remain null.
For missing critical inputs return missing fields, not a deceptively wide interval.
Future escalation beyond an observed index month is an explicit reviewed scenario,
not a verified future price. Store price-base and target dates and freshness status.

## Code, location and wildfire limitations

Building age informs screening for obsolete systems, hazardous materials and
historic conditions; it is not a reduction for physical depreciation. Applicable
code depends on permit timing, local amendments and rebuild relief. Most parts of
the 2025 state code cycle took effect in January 2026 [S8], but that alone does not
establish the requirements for a particular house. Review fire-resistant exterior
work, sprinklers, energy/seismic requirements and utility reconnection with the
actual building department. County and City processes differ [S6, S7]. Do not
assign universal code-upgrade costs or permanent fee-waiver assumptions.

A catastrophe can alter labor availability, hauling, material procurement and
schedule. Those conditions require contemporary quote evidence [S1]; hazard zone
or exposure score alone cannot quantify a surge. Current dollars and a future
post-catastrophe budget should be distinct scenarios. Existing foundation/site
condition, contamination and constrained hillside access can dominate a square-foot
estimate. Complex cases remain outside standard-rate eligibility.

## Later insurance-gap integration

Preserve dwelling construction, debris, code, other-structure and excluded-cost
subtotals separately. Policy limits, extended/guaranteed replacement conditions,
ordinance/law coverage, debris sublimits, deductibles and DIC wording must be
reviewed before assigning available benefits. A simple R minus Coverage A can
misstate the gap if scopes differ. Do not add overlapping policy limits or treat
endorsements as unconditional cash. The future calculator should call any simple
comparison a preliminary coverage screen and retain policy-review status. This
proposal does not implement that calculation.

## Decisions and data gaps requiring review

1. Approve initial dwelling scope and specialist referral rules, including attached
   features, unusual construction and hillside sites.
2. Acquire current local single-property estimates with explicit area denominators,
   taxes, contractor overhead/profit, code and soft-cost scope; approve comparability
   rules, reuse permissions, freshness threshold and reviewer ownership.
3. Verify numerical demolition, professional, fee, code and site allowances; no
   defaults are currently approved for these or for surge/contingency/location.
4. Confirm current official replacement-estimate requirements and intended product
   wording with a qualified reviewer; do not claim regulatory compliance from this design.
5. Confirm jurisdiction, permit-date code requirements and relief eligibility.
6. Decide whether DGS time indexing is compatible with each cost category; archive
   verified base/target tables before adopting index values.
7. Define homeowner quality descriptions and reconcile reported living area,
   garages, additions, foundation conditions and existing plan evidence.
8. Approve scenario construction and eventual calibration against scope-matched
   quotes/settled rebuild costs; this proposal has no measured predictive accuracy.
9. Review policy-component mapping and treatment of assistance, carrying costs and
   contingent benefits before producing underinsurance recommendations.

## Future validation plan (no implementation in this change)

Check positive area, units, date/currency consistency, LA jurisdiction, source
approval and scenario ordering; reject incompatible scope and duplicated categories.
Confirm that changing policy limits or market value cannot change estimated cost.
Test that stories do not multiply total floor area, included costs are not added
again, unresolved items block complete totals, and missing bounds remain null.
Reconcile a sample of actual scoped local estimates by category and document
errors before enabling generic automated pricing.
