# Insurance Gap Engine end-to-end validation

Validated **2026-11-06** on `feature/insurance-gap-analysis`.
Outcome: the offline engine and synthetic canonical-input flow pass validation.
Live upstream/application integration remains **blocked on semantic/provenance
mapping**, not declared production-ready. No actual quotes or current LA project
prices were obtained or fabricated.

## Scope and inspection

Reviewed rebuilding.py and rebuilding_benchmarks.py; insurance_gap adapter,
coverage, alternatives, requirements, upgrades, common helpers, catalog loader and
report orchestration; all four JSON reference catalogs; prior methodology/schema/
source/engine and gap contract/integration/reference documents; existing automated
tests and synthetic examples. The validation uses the actual functions and real
reference catalogs, not mocked response totals or substituted model outputs.

Fetched origin without merge, switch, checkout or teammate file edits. Latest shared
coverage commit was ec119560920357b9d6b878351a3704af340022d1. Inspected extraction,
contract, schemas, coverage adapter, stub and shared documentation directly with
git show. See the [complete field mapping](david_to_gap_mapping.md),
[observed inventory](david_interface_inventory.json), and
[Joaquin instructions](insurance_gap_joaquin.md). No upstream extractor/model API was
called, no PDFs uploaded and no teammate modules imported into the working tree.

## Reproducible scenarios

Fixture: `tests/fixtures/insurance_gap_e2e.json`.
Runner: `scripts/validate_insurance_gap_e2e.py`.
Each artifact contains exact input, actual rebuilding output, explicit synthetic
reviewed allocation and actual gap-engine output. All household rates, limits,
needs, conditions and confirmation attestations are synthetic test fixtures. No
premium or claimed offer from any insurer is present.

| Case | Reconstruction | Dwelling scope comparison | Other checks | Overall status |
|---|---|---|---|---|
| [Underinsured](examples/e2e/synthetic_underinsured.json) | $860,000 total; $785,000 reviewed dwelling allocation | $600,000 base → $185,000 base gap; conditional 25% extension gives $750,000 capacity → $35,000 conditional gap | ALE $24,000 and 6 months short; code $25,000 short; debris $15,000 short; deductible $2,500 | incomplete: unknown remaining facts and no eligible local project prices |
| [Sufficient limits / missing facts](examples/e2e/synthetic_adequate_unknown_property.json) | $950,000 total; $880,000 dwelling allocation | $1,000,000 base → $0 gap; conditional cap $1,250,000 | No supplied ALE/code/debris deficit; 2% verified-basis deductible → $20,000; mitigation facts remain unknown | incomplete: property information missing |
| [Limited FAIR-type / uncertain costs](examples/e2e/synthetic_limited_fair_uncertain.json) | No construction rate; needs_cost_evidence and null total | $450,000 face limit with ACV; settlement_review and null dollar gap | Shared debris review; ALE not equated to rental value; no invented ordinance need; fixed deductible $1,000 | incomplete: unresolved reconstruction, scope and property information |

The first two allocation ledgers reconcile without double-counting:

- Case 1: $720,000 construction + $45,000 professional + $10,000 permits + $10,000
  site = $785,000 dwelling scope; plus $30,000 debris and $45,000 incremental code
  = $860,000. ALE is separate from rebuilding.
- Case 2: $800,000 construction + $50,000 professional + $10,000 permits + $20,000
  site = $880,000 dwelling scope; plus $30,000 debris and $40,000 code = $950,000.

These allocations are explicit fictional review decisions, not universal policy
coverage mappings. The helper's allocation_review_required flag is resolved only
inside the labeled synthetic harness. Production still needs an actual reviewer.

## Findings, corrections and regression coverage

| Validation area | Result |
|---|---|
| Dwelling arithmetic | Scope-matched need minus base limit, floored at zero; conditional ERC capacity compared separately. No aggregate gap produced. |
| ACV/unknown settlement | **Corrected:** explicit settlement review gate now blocks treating ACV or missing/unknown settlement as replacement-cost proceeds. Present dwelling inputs require confirmed replacement_cost for these calculations. |
| ERC | Source/conditions/scope required; missing conditions remain unknown. Guaranteed replacement remains review-only, not infinite cash. |
| Deductibles | Fixed and documented percentage bases computed once as separate exposure; not subtracted/added to every component. |
| ALE duration | **Corrected:** duration-only deficit gets shortfall priority even with sufficient dollars. Pending allocation review also blocks a duration gap calculation. |
| Missing data | Unpriced reconstruction, unknown policy needs and unconfirmed property facts remain null/unknown. Sufficient limits do not mark unknown property conditions as passed. |
| Products | All three real references remain description_only with null premiums/differences and undetermined eligibility. They do not overwrite current policy terms. |
| Rules | FAIR rules only for selected product; legal screen only with confirmed applicability. Unknown conditions create verification tasks, not assumed failure. |
| Upgrades | Real historical/unit costs are rejected as current LA whole-project prices. Project IDs deduplicate multiple matching rules. |
| Overlap | Existing synthetic catalog regression blocks combined totals for projects sharing scope tags; no automatic selection/addition of overlapping work. |
| Priority | Exclusions/coverage deficits precede property work; verified applicable requirement precedes recommendations; unknown work is not priced as free. |
| Reproducibility | Saved artifacts equal live engine outputs; inputs remain unchanged; previous decimal-context tests still pass. |

No insurance, frontend or wildfire feature was added beyond these gap-owned fixes.
The original synthetic examples were refreshed to include explicit settlement in
their input payloads; their expected monetary results are unchanged.

## Verification commands and result

```sh
.venv/bin/python scripts/validate_insurance_gap_e2e.py
.venv/bin/python -m unittest discover -s tests -v
```

The full local suite passes **66 tests**: previous 57 plus 9 end-to-end tests.
The suite includes rebuilding, real-reference catalogs, gap engine, saved artifacts
and wildfire regressions. Syntax/JSON/local documentation link checks and Git
whitespace checks also pass. Teammates' remote test suites were not run or merged;
this is a local canonical-contract validation, not an app end-to-end browser test.

## Handoff limitations and blockers

- No safe automatic David adapter yet: extractor percentage points versus PolicyInput
  fractions; provenance dropped by merged dicts; no expiry/subject/interpretation
  metadata; ambiguous ALE/fair-rental and shared coverage scopes.
- No finalized independently identifiable David property-model schema in the shared
  tree; DINS materials/placeholder scores do not prove the catalog's boolean targets.
- Existing remote coverage package is already connected to assess/report/app and
  differs from this engine in output shape and assumptions. Decide coexistence or
  replacement with Joaquin before integration; never combine its aggregate and ours.
- No approved rebuilding-price defaults, actual insurer quotes, current installed LA
  mitigation prices, guaranteed discount/acceptance outcomes or calibrated scenario
  probabilities. Synthetic rates are not promoted into reference data.
- Scope tags depend on correct curator declarations; disjoint labels cannot prove
  physically disjoint work. Shared coverage pools and multiple policies need review.
- Catalog verification is a one-day research snapshot, not a future product or legal
  guarantee. Reverify for later as-of dates.
- Passing tests validates calculation/contract behavior, not extraction accuracy,
  legal applicability, prediction quality, insurer certification or policy adequacy.

No commit, push, merge or branch switch was performed. David's files, application,
wildfire pipeline and processed source datasets were not modified.
