# Real insurance reference catalogs: coverage and handoff

Research snapshot **2026-11-06**, on `feature/insurance-gap-analysis`.
[Source register](insurance_reference_sources.md) records exact primary URLs and
verification limits. No premiums or homeowner-specific quotes were obtained.

## Contents

| Catalog | Verified entries | Executable meaning |
|---|---:|---|
| Products | 3 public descriptions | Two California-specific references; one multistate overview with CA feature applicability explicitly unresolved. None is an available/bindable quote. |
| Property rules | 23 | 17 potential discount conditions, 5 recommendations, 1 conditional defensible-space legal-compliance screen. |
| Upgrade costs | 5 historical observations | Context only. Zero approved current LA installed-project prices. One additional record explicitly represents missing vegetation pricing. |
| Source register | 10 full-content reviews | One-day snapshot; publication/effective dates are separately retained. |

No product catalog entry supplies a premium, automatically populates a current
policy or determines acceptance. Farmers describes an extended replacement option
and ALE; actual amounts require forms/quotes. Mercury's overview is multistate:
its advertised extension is retained as qualified text, with CA feature values
left unknown. FAIR Plan coverage terms distinguish elected options, shared debris
limits and fair rental value; these do not become a generic comprehensive ALE
benefit. Product deductions/limits remain null where not verified. Obtain current
issued forms before applying any terms to a homeowner.

## Loading and compatibility

```python
from msba_vibathon_2026.insurance_gap.catalogs import load_reference_catalogs
from msba_vibathon_2026.insurance_gap import analyze_insurance_gap

reference = load_reference_catalogs()
report = analyze_insurance_gap(
    david_canonical_payload,
    products=reference['products'],
    requirements=reference['requirements'],
    costs=reference['costs'],
)
```

Default module constants load the same JSON catalogs through `importlib.resources`.
Each call to the loader returns fresh copies. Source IDs are expanded into the
existing source-object schema, including feature sources. No new dependency or
network step was added to reporting. Failed/unavailable upstream assessment remains
unknown. The orchestrator still accepts explicitly empty catalogs for fallback/testing.

Minimal schema extensions in gap-owned modules only:

- `applies_when`: rule map of prerequisite fact names to typed expected values.
  Missing, uncertain, unverified or expired prerequisite facts yield unknown
  applicability; confirmed false prerequisites yield not_applicable. Only a
  confirmed match permits a compliance finding. No jurisdiction is guessed.
- `verification_status`: explicit unverified real entries cannot pass source checks
  merely because their shared source has been read. Legacy synthetic fixtures with
  no such metadata retain their existing source-attestation behavior.
- `target_details` and applicability notes remain visible in real rule findings;
  product reference metadata preserves the distinction between known descriptions
  and unverified availability.
- Historical cost records intentionally fail unit/geography/scope checks. Per-unit
  prices are never automatically interpreted as whole-house installed estimates.

The existing [gap contract](insurance_gap_contract.md) remains the canonical
David/Joaquin boundary; these additions refine reference-data application only.
No upstream extraction, assessment, app integration, wildfire or teammate modules
were changed.

## Property facts David must supply

All matching targets are boolean confirmations of the whole documented condition.
A material name, photograph inference or existing unknown must not be promoted to
true/false without David's confirmation/evidence workflow. Each rule's target_details
contains the scope. Unknown facts trigger verification rather than presumed failure.

Core keys: `roof_class_a`, `ember_zone_5ft`, `ember_resistant_vents`,
`noncombustible_wall_base_6in`, `enclosed_eaves`, `upgraded_windows`,
`under_deck_clear`, `outbuildings_separation_confirmed`,
`defensible_space_compliant`, `recognized_community`,
`noncombustible_gutter_covers`, `gutters_clear`, `zone2_fuel_management_confirmed`.

`calfire_listed_vents_airflow_confirmed` is separate from generic vent/mesh facts:
retain the specialist ventilation review. Insurer-specific facts have `fair_`
prefixes; do not equate their complete discount criteria automatically to general
recommendations. Only selecting `ca_fair_dwelling` applies FAIR-specific rules.
Other products do not inherit those conditions.

`defensible_space_legal_applicability_confirmed` must come from verified site/legal
review, not simply an LA ZIP, a hazard class, or the wildfire score. The single
verified_requirement rule is dormant until that fact is confirmed true. It concerns
applicable defensible-space law, not a compulsory insurer mitigation list.

## What recommendations are now supported

With appropriately confirmed facts, reports can flag source-backed hardening and
maintenance recommendations and potential discount conditions, identify the specific
FAIR Plan discount condition being considered, and suggest documenting compliance.
Multiple rules sharing one project ID still merge into one project. They cannot
quantify premium savings or promise that mitigation opens a particular insurer.

Public product terms support questions for an agent about replacement-cost options,
ALE, optional/shared debris and code provisions. They never override David's current
policy extraction. Dollar gap calculations still depend on reviewed policy terms,
complete reconstruction evidence and explicit scope allocations from prior work.

Upgrade totals remain null with these historical costs. Missing LA pricing is
visible; scope tags and existing duplicate/overlap protections are preserved.
No source supports turning a low-cost label into a numeric price or a quote.

## Remote teammate changes observed

Fetched origin references, without merge, branch switch or checkout. At review:
`origin/main` was `a54242b`, `origin/app-streamlit` was `4db5840`, and
`origin/coverage-gap` was `2890f26`. Read-only logs/diffs and the remote coverage
module guide show a separate coverage package, extraction contract, frontend and
rent dataset. These were not imported, modified or overwritten. Integration must
reconcile these boundaries with teammates; this catalog work stays in insurance_gap.

## Remaining evidence gaps

- Actual available products/quotes, address acceptance and issued policy endorsements.
- Complete CA-specific Mercury forms and product-specific deductibles/limits not
  supplied by the public overviews; FAIR form-date discrepancy.
- Insurer-specific mandatory underwriting rules beyond documented discount conditions.
- Applicable local code/adoption, permit-date and Zone 0 legal determinations.
- Current installed LA prices, quantities, scope, labor/access and contractor evidence.
- Detailed eligibility/certification checks for community recognition and discounts.
- Refresh/approval workflow after this snapshot; source dates are not future guarantees.

No unsupported costs, discounts, premiums, underwriting outcomes, code deadlines or
coverage availability have been filled in. Existing data/processed tables and the
rebuilding-price catalog remain unchanged.
