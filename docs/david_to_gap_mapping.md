# David → Insurance Gap Engine mapping and open decisions

Inspected read-only on **2026-11-06** after fetching origin. No branch switch,
merge, checkout or execution of teammate code occurred. Most recent shared
coverage reference: **ec119560920357b9d6b878351a3704af340022d1**
(`origin/coverage-gap`); app/extraction reference:
**4db5840f312bf5b6fce2bcd007959bfd9d16e899** (`origin/app-streamlit`).
Main was `a54242b871abc8b684ff5cde919862bebc2c6ef7`.

The available interfaces are the shared extractor, app contract and coverage
schemas. There is no separately identifiable finalized David property-assessment
output in that tree; `assess_stub.house_impact` remains a placeholder. This document
therefore describes observed shared interfaces, not an invented David API.
The AST-derived [field inventory](david_interface_inventory.json) records all
observed raw, normalized, PolicyInput and HomeInput field names at the pinned commit.

Reviewed paths at that commit:

- `src/msba_vibathon_2026/policy_extract.py`: `_PROPS`, `FIELDS`, normalize,
  verify_quotes, extract and merge_policies.
- `src/msba_vibathon_2026/coverage/schemas.py`: PolicyInput, HomeInput, CoverageResult.
- `src/msba_vibathon_2026/coverage/adapter.py`: existing app-to-coverage adapter.
- `src/msba_vibathon_2026/contract.py`, `assess_stub.py`.
- `docs/policy_extraction_spec.md`, `docs/inputs_and_contract.md`.

## Adapter decision: defer a concrete David adapter

The normalized extractor's shape is sufficiently visible for field unwrapping,
but it does **not** provide sufficient semantics/provenance to produce reviewed
canonical gap-v1 automatically. Three live shapes differ, the written spec includes
fields the actual extractor no longer emits, and merge_policies drops provenance.
The existing generic `adapt_inputs(..., adapter=...)` remains the boundary. No
David-specific adapter is added until the input variant, units, confirmation and
sidecar evidence contract are agreed. Mapping is possible only with explicit
additional reviewed context; absence of that context must remain unknown.

## Shapes and evidence transformations

1. Raw structured extraction uses plain values plus `not_found` placeholders and
   `evidence[{field, quote, page}]`. **Never use its placeholder zero as absence.**
2. `extract()` returns `{fields, source: cache|claude, text_layer: bool}`. Every
   normalized field has `{value, source_text, page, verified}` and optional `flag`.
   A null value/flagged field stays unknown. `verified` means quote text matched a
   PDF text layer, not that policy scope, exclusions or homeowner identity were
   reviewed. Scanned evidence can have verified null.
3. `merge_policies()` returns a flat insurance dictionary and a `documents` list.
   It unwraps values, drops per-field evidence, fills DIC fields selectively and
   sums premium amounts with zero fallbacks. It defaults has_dic false when none
   appears. Do not use this dictionary as authoritative evidence of no DIC,
   complete combined premiums, independent limits or policy verification.
4. Remote `PolicyInput` is another flattened Pydantic object with no field-level
   source/confirmation. It changes ERC units to fractions; it also loses percentage
   deductible basis and code/debris sharing details. Do not re-adapt it as though it
   were normalized extractor output.
5. Gap sources need a document/page reference, explicit interpretation review and
   applicable date interval. Raw quote text, verification flags and original value
   should be preserved in a provenance sidecar. A filename/model name is not review.
6. Monetary numbers → `Decimal(str(value))` → canonical decimal strings, preserving
   null and explicit absence separately. No binary-float arithmetic for conversions.
   USD and source price dates must be confirmed, not assumed from an untyped number.

## Complete normalized extraction field mapping

| Shared field (inside fields, value wrapper) | Gap destination / required transformation |
|---|---|
| document_type | Preserve metadata; fair_plan may select ca_fair_dwelling only after homeowner/product confirmation. Does not set coverage absences or insurer acceptance. |
| insurer_name | Preserve metadata, not an automatic catalog/product match. |
| effective_date | Candidate source.valid_from after review; expiration is not emitted, so valid_through still missing. |
| dwelling_limit | policy.coverages.dwelling.limit_usd after review; status, scope_id, standalone/shared basis, settlement and source must be separately established. |
| other_structures_limit | No current numeric gap category. Preserve as context; do not add to dwelling. |
| contents_limit | No current numeric gap category. Preserve as context; do not add to dwelling. |
| loss_of_use_limit | Candidate ALE limit **only if ALE confirmed**. Field also accepts fair rental value: retain unknown ALE until semantics are resolved. Duration is absent. |
| liability_limit | No current numeric gap category. Preserve context; no invented recommendation amount. |
| dwelling_settlement | Map actual_cash_value/replacement_cost/unknown to dwelling.settlement. ACV/unknown blocks replacement-cost gap arithmetic and extension proceeds. |
| extended_replacement_pct | Normalized extraction uses percentage points (25). Map directly to extension percentage value; null remains unknown. Need scope/source/conditions_verified separately. |
| code_upgrade | Normalized value is null or {covered, limit, pct}. Declined/excluded is verified absence only after review. True without a limit is not infinite coverage. Percent × verified declared basis only after confirming basis and independent/shared nature. |
| debris_removal | Normalized null or {covered, limit, pct}; current normalize emits null amount. Needs actual limit and limit_basis; presence alone cannot quantify. FAIR base debris can share property limits. |
| deductible_all_perils | Candidate fixed deductible only when applicable to the wildfire scenario; do not override a more specific wildfire term. |
| deductible_wildfire | {amount,pct} or null. Select documented fixed amount or percentage/basis; do not add both or assume percentage basis is Coverage A without review. |
| premium_total | Current-policy premium metadata only after term/package/annualization review; never an alternative quote. Add currency/comparison_basis/source. Partial combined premium from merged inputs is not complete evidence. |
| discounts_listed | Preserve evidence/context, not an inferred mitigation fact, savings forecast or new quote. |
| dic_covers | Preserve separate policy/peril metadata; no automatic limit stacking or sharing assumptions. |

All 17 normalized fields are covered above. Extra raw-only controls:

| Raw field | Normalization / caveat |
|---|---|
| code_upgrade_pct | Folded into code_upgrade.value.pct; not preserved as separate normalized field. |
| deductible_wildfire_amount / deductible_wildfire_pct | Folded into deductible_wildfire.value; zero placeholders can become null. |
| not_found | Essential for placeholder-to-null conversion; preserve missingness during normalization. |
| evidence | Becomes field source_text/page; retain document identity and review outcome separately. |

The raw `code_upgrade` / `debris_removal` enums covered/excluded/not_mentioned
become covered true/false or null, not the booleans described by the older spec.
The extractor does not currently emit a debris amount. Do not guess one.

## Remote PolicyInput additions and unit differences

All 19 fields are accounted for by the normalized table or these additions:

| PolicyInput-only/different field | Gap handling |
|---|---|
| extended_replacement_pct | Fraction (.25) → percentage points (25) with Decimal × 100. Input variant must be explicit: .25 from extraction means .25%, not 25%. |
| has_dic | Metadata only, verified policy inventory required; merged default false is not proof of absence. |
| guaranteed_replacement | Map true to guaranteed_terms_review; false alone does not prove no other extension. Not emitted by current extractor. |
| contents_settlement | Context only; not a supported contents-gap calculation. |
| code_upgrade_amount | Possible reviewed ordinance/law limit; source/percentage basis and sharing details absent. |
| last_coverage_update_year | Context/review note; no invented age-based multiplier or automatic annual inflation. |
| nonrenewal_notice | Context/follow-up, not acceptance/rejection of other products. |

Its numeric deductible_wildfire and boolean code/debris fields have already lost
original percentage/basis/scope distinctions; retrieve original evidence rather
than reverse-engineering them. The existing remote coverage adapter computes some
percentage bases; that does not establish those bases for this stricter engine.

## Property and rebuilding mapping

| Shared input | Required gap/rebuild handling |
|---|---|
| address | Geocode/subject confirmation belongs upstream. Postal text alone cannot establish county or permitting authority. |
| area.geocode.zip / HomeInput.zip | Preserve string; insufficient for verified legal or insurer applicability. |
| home.living_area_sqft / HomeInput.sq_ft | Rebuild living_area_sqft; add area definition, source and confirmation. |
| stories / year_built | Rebuild screening fields; no story multiplier or age depreciation. |
| ROOFCONSTRUCTION | Material context only. Asphalt/Tile/Metal does not prove Class A assembly rating. |
| EAVES | Candidate enclosed_eaves only after confirmation; No Eaves is not a failed retrofit condition. |
| VENTSCREEN | Mesh description does not establish tested/listed vent assembly or airflow compliance. Keep CAL FIRE listed-vent fact separate. |
| EXTERIORSIDING | Does not prove framing or measured six-inch noncombustible wall base. |
| WINDOWPANE | Multi Pane may support upgraded_windows after source-specific confirmation; shutters are another route. No Windows is not a failure. |
| DECKPORCHELEVATED / DECKPORCHONGRADE | Material/presence context, not evidence that under-deck debris is cleared; No Deck requires applicability handling rather than a false gap. |
| FENCEATTACHEDTOSTRUCTURE | Cannot alone prove a complete five-foot ember-resistant zone. |
| UTILITYMISCSTRUCTUREDISTANCE | Binned distance can inform review; applicability, control and source-specific separation conditions need confirmation. |
| PATIOCOVERCARPORT / PROPANETANKDISTANCE | In older proposal, not current validated HOME_OPTIONS. Preserve context; no active direct fact mapping. |
| YEARBUILT | Older DINS field may need explicit year_built normalization; no silent precedence over confirmed home.year_built. |
| measures_done | Positive user checklist assertions only. Not listed means unknown, never automatically false. Add evidence/date/source-specific review. |
| contents_value_estimate / other_structures_estimate | No current numeric gap categories; do not repurpose as reconstruction cost. |
| renovated_since_update | Context only; not proof of code compliance. |
| current.house.impact/rating/missing | Placeholder-derived output at inspected revision; not confirmed physical facts or actual underwriting rules. |
| current.wildfire / RiskInput.p_destroyed | Do not use as cost factors, coverage eligibility or site legal applicability. No expected-loss calculation in this engine. |
| budget | Current engine prioritizes actions; does not optimize a budget or produce payback. No direct mapping. |

The seven remote HomeInput fields are zip, sq_ft, stories, year_built,
contents_value_estimate, other_structures_estimate, renovated_since_update, all
covered above. Live contract validates eight DINS categorical fields; the older
proposal additionally lists the legacy fields above.

Checklist IDs → candidate fact/project mapping (confirmation still required):

| measures_done ID | Fact | Project |
|---|---|---|
| class_a_roof | roof_class_a | class_a_roof |
| ember_zone_5ft | ember_zone_5ft | ember_zone_5ft |
| noncombustible_6in_walls | noncombustible_wall_base_6in | noncombustible_6in_walls |
| ember_resistant_vents | ember_resistant_vents | ember_resistant_vents |
| double_pane_or_shutters | upgraded_windows | upgraded_windows |
| enclosed_eaves | enclosed_eaves | enclosed_eaves |
| clear_under_decks | under_deck_clear | under_deck_clearance |
| outbuildings_30ft | outbuildings_separation_confirmed | outbuilding_separation |
| defensible_space | defensible_space_compliant | defensible_space |
| firewise_usa / fire_risk_reduction_community | recognized_community after membership review | community_recognition |

Separate fair_-prefixed facts must satisfy FAIR-specific criteria; do not copy
all generic facts automatically. Missing: noncombustible_gutter_covers,
gutters_clear, zone2_fuel_management_confirmed, calfire_listed_vents_airflow_confirmed
and defensible_space_legal_applicability_confirmed. Unknown stays unknown.

Rebuilding also needs construction/quality/foundation, area convention, materials,
site/feature review, jurisdiction, confirmed price date, and reviewed cost evidence.
Those are not supplied by HomeInput. No price default is currently approved.
needs.dwelling/ordinance_law/debris require a non-overlapping cost allocation, not
copying gross rebuilding R three times. ALE needs a separate documented budget
and duration. The scenario harness demonstrates explicit synthetic allocations.

## Target fields absent from shared outputs (blocking automatic activation)

- schema version/variant, currency, as_of and stable subject identity; verified
  policy/property subject match, county and actual permitting jurisdiction.
- Field-level interpretation approval, source reference, complete effective interval,
  scanned-document/user confirmation and flagged-value resolution.
- terms_reviewed/exclusions_reviewed, structured exclusions, endorsement conditions,
  independent/shared limit basis and cost scope IDs.
- Explicit replacement settlement confirmation, extension trigger/maintenance
  confirmation, percentage deductible basis and ALE-versus-rental interpretation.
- Complete reconstruction evidence and cost-to-policy scope allocation; ALE duration.
- Confirmed boolean property targets, source-specific applicability and legal review.
- Subject-specific alternative quotes, annual comparison basis and current local prices.

The older extraction spec additionally lists policy_form, expiration_date,
property_city_zip, medical_payments_limit, guaranteed_replacement,
contents_settlement, inflation_guard, trees_plants_shrubs, optional_perils,
water_damage, endorsement_codes, premium_items and dic_dwelling_limit. None is in
the current 17-field normalized extractor. Some can be supplied manually/shared
elsewhere; absence must not be inferred as declined coverage. Source extraction
code, rather than the aspirational spec, is the observed inventory authority.

## Report/output mismatch with Joaquin's app

Gap-report-v1 is not CoverageResult or assess output. It uses decimal strings,
nullable individual findings, no summed payout/shortfall, no expected loss and no
risk probabilities. Remote CoverageResult uses float low/high totals (including
its own deductible treatment), components and severity strings high/medium/info.
The assess app expects current.insurance_gap entries with gap/severity/why and
future.fixes with impact/payback fields. Do not inject our findings into those
slots or derive missing impact, savings or payback. Keep a separate versioned report
until a deliberate app adapter is approved. See [Joaquin handoff](insurance_gap_joaquin.md).

## Questions to resolve with David (no external message sent)

1. Which input variant is the stable handoff: normalized extraction, reviewed form,
   or PolicyInput? Can original field provenance survive merging?
2. Who supplies subject match, currency, expiry dates, interpretation confirmation
   and source intervals, especially for scanned/manual data?
3. Can ALE and fair rental value, shared debris and ordinance limits be distinguished?
4. Who confirms ERC conditions, deductible basis and replacement-cost settlement?
5. Which property facts are assessed/confirmed, and how are inapplicable features
   distinguished from unknown or failed conditions?
6. Who owns reconstruction evidence, cost allocations and ALE budget/duration review?
7. Should the new report coexist with or replace the existing remote coverage module?
   Avoid conflicting dollar totals and different unknown-data policies.

All findings above are code/interface observations, not legal interpretations or
independent validation of extraction accuracy on real policies.
