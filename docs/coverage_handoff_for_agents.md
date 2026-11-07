# Handoff: connecting the ROI and plan-comparison model to the coverage module

**Audience:** Atharva's AI coding agent, or anyone building the model that compares switching plans and fire-safety repairs. Assume no earlier context. Written Nov 6, 2026, against `main` at `d7d3982`.

**The first thing to know:** the field list Atharva asked for is **not available yet**. Nothing named `build_profile()` exists. This document says exactly what exists, what's missing, where the traps are, and how to build the rest. If code and this document disagree, trust the code and tell David.

## Read first

1. `AGENTS.md`: project rules. Rules 1, 3 and 4 matter most here: the demo must not break, assumptions are labeled, and AI never invents numbers.
2. `docs/coverage_module.md`: how the coverage module works and its sources.
3. `docs/inputs_and_contract.md`: the `assess()` input and output contract.
4. `docs/policy_extraction_spec.md`: the policy PDF extraction spec.

Judges review from 6:00 PM on Nov 6. **Don't push anything to `main` that fails `uv run pytest` or `uv run python scripts/smoke_test.py`.**

## How data flows today

```
Policy PDFs -> policy_extract.extract() -> merge_policies() -> app.apply_policy() -> form (session state)
Address     -> scripts/utils.area_context()  -------------------------------------> area dict
Home form   ----------------------------------------------------------------------> build_inputs()
                                                                                         |
                                                     assess_stub.assess(inputs, area) <--+
                                                                |
          wildfire.wildfire_analysis(area)     -> current.wildfire   (Atharva's exposure index, real)
          assess_stub.house_impact(missing)    -> current.house      (PLACEHOLDER weights)
          coverage.adapter.coverage_for_assess -> current.coverage   (total-loss scenario)
          coverage.adapter.display_gaps        -> current.insurance_gap
          assess_stub.assess fix loop          -> future.fixes       (assumed costs and discounts)
```

| File | Job |
| --- | --- |
| `src/msba_vibathon_2026/assess_stub.py` | `assess()`, the only function the app calls for results |
| `src/msba_vibathon_2026/coverage/scenario.py` | `run_coverage_analysis(policy, home, risk, as_of_year=None)`. Pure, no network |
| `src/msba_vibathon_2026/coverage/adapter.py` | Converts app dicts to module inputs. **The conversion layer: put new mappings here** |
| `src/msba_vibathon_2026/coverage/schemas.py` | Pydantic inputs and outputs |
| `src/msba_vibathon_2026/coverage/config.yaml` | Every coverage rate and threshold, with sources |
| `src/msba_vibathon_2026/policy_extract.py` | PDF to fields, with quote checks |
| `src/msba_vibathon_2026/contract.py` | `validate_inputs` and `validate_output` |
| `app.py` | Streamlit form and display |

The `origin/deploy` branch (Joaquín, not merged) adds `api/main.py`, whose `POST /api/assess` calls `assess()`. It also changes `app.py`, so pull before editing the form.

## Run it

```bash
uv sync
```

```bash
uv run pytest
```

```bash
uv run python scripts/smoke_test.py
```

```bash
uv run streamlit run app.py
```

Tests need no API key. Without `ANTHROPIC_API_KEY`, only cached sample PDFs and manual entry work.

This runs the full path on a sample, and the values are real output at `d7d3982`:

```python
from msba_vibathon_2026.assess_stub import assess
from msba_vibathon_2026.scenarios import cached_area, load_scenarios, scenario_inputs

sample = load_scenarios()["altadena_fair_only"]
out = assess(scenario_inputs(sample), cached_area(sample["address"]))
coverage = out["current"]["coverage"]

assert coverage["total_shortfall"] == {"low": 354490.0, "high": 902985.0}
assert coverage["total_cost"] == {"low": 948490.0, "high": 1552985.0}
assert coverage["total_payout"] == {"low": 594000.0, "high": 715000.0}
assert coverage["premium_total"] == 6180.0
assert out["current"]["wildfire"]["score"] == 73.2
assert out["current"]["house"]["stub"] is True
```

## Using the module for plan comparison

`run_coverage_analysis()` is pure, so you can run it once on the current policy and again on a hypothetical one, then compare. The non-FAIR logic exists and is tested, even though the team's demo cases are FAIR Plan homes.

```python
from msba_vibathon_2026.coverage.scenario import run_coverage_analysis
from msba_vibathon_2026.coverage.schemas import HomeInput, PolicyInput, RiskInput

home = HomeInput(zip="91001", sq_ft=1_800, contents_value_estimate=100_000)
current = PolicyInput(document_type="fair_plan", has_dic=False, dwelling_limit=650_000,
                      dwelling_settlement="actual_cash_value", code_upgrade=False, debris_removal=True,
                      contents_limit=0, loss_of_use_limit=0, extended_replacement_pct=0)
option = PolicyInput(document_type="homeowners", dwelling_limit=900_000, dwelling_settlement="replacement_cost",
                     extended_replacement_pct=0.25, code_upgrade=True, code_upgrade_amount=225_000,
                     debris_removal=True, other_structures_limit=90_000, contents_limit=450_000,
                     loss_of_use_limit=180_000, deductible_wildfire=5_000)

before = run_coverage_analysis(current, home, RiskInput(), as_of_year=2026).total_shortfall
after = run_coverage_analysis(option, home, RiskInput(), as_of_year=2026).total_shortfall
assert before.low == 354_490 and before.high == 902_985
assert after.low == 5_000 and after.high == 230_000  # code upgrade $225,000 to $450,000, pays $225,000, plus deductible
```

**The difference between those two is one event's shortfall, not annual savings or ROI.** To annualize it you need a probability the home is destroyed, and **we don't have one**:

- `current.wildfire.score` is a relative index from 0 to 100. **It is not a probability.**
- `current.wildfire.p_fire_annual` is FEMA's annualized frequency for the tract, not the chance this home is destroyed. It's `0.0` if FEMA has no value. If the tract and ZIP lookups both fail, it's a **placeholder** and `wildfire["stub"]` is `True`.
- `current.house.impact` is **placeholder weights**, and `house["stub"]` is `True`. Multiplying it by `p_fire_annual` looks like a probability and isn't. That's why `p_destroyed` is deliberately `None` and `expected_shortfall` is empty.

## Traps in the current outputs

| Trap | What actually happens | What to do |
| --- | --- | --- |
| Percent units | `PolicyInput.extended_replacement_pct` is a **fraction** (`0.25`). App, extractor and `to_policy_input()` use a **whole number** (`25`). Above 1 raises a validation error. | Use `to_policy_input()` for app dicts. Don't convert twice. |
| Low and high | Separate best and worst cases. `cost.high - payout.low` does **not** equal `shortfall.high`, because some unknowns are resolved differently per case. | Compare shortfall to shortfall. Never subtract across fields. |
| Partial totals | Components with unknown cost are left out, so totals are **minimums**. A warning starting `Totals leave out` names them. | Check for it, or sum `components` yourself. |
| `total_payout` | Each component is capped at its cost. Component `payout` values can show the full limit. | Use the total for money paid. |
| ACV policies | Computed as if replacement cost, plus a warning. The real shortfall may exceed the high figure. | Don't treat the high as a worst case for ACV, and don't read an ACV-to-replacement switch as $0 benefit. The current numbers can't show that benefit. |
| FAIR Plan with no Coverage B | 10% of Coverage A pays other structures. The low assumes on top of A, the high assumes out of A, because sources say it depends on the policy. Differs from `docs/coverage_gap_build_plan.md`. | Expect a wider rebuild range. `coverage_module.md` is correct; the build plan's Case 1 total isn't current. |
| `document_type` | `None` skips FAIR-specific rules: a missing loss of use becomes "unknown" rather than $0, and the Coverage B rule and cap don't apply. | Always set it. `to_policy_input()` derives it from `documents`. |
| DIC | No DIC dollars for the dwelling. `merge_policies()` fills `loss_of_use_limit`, `contents_limit` and `liability_limit` from the DIC when the FAIR Plan has none, and `premium_total` adds both premiums. | Other DIC cover isn't counted, so FAIR + DIC shortfalls may be overstated. |
| Rebuild rates | Coverage uses $300 to $500/sq ft from `config.yaml`. `gaps.REBUILD_COST_PER_SQFT = 450` is still used in `assess()` for `est_avoided_loss` and by the fallback gap rules. | See task 3. Don't add a third rate. |
| `future.fixes` benefit | `est_annual_benefit` = assumed discount + `p_fire_annual` x placeholder impact change x rebuild at $450/sq ft. | **Don't present this as a real ROI.** It rests on assumed discounts and a placeholder model. |
| Repairs and the shortfall | Fixes don't change `total_shortfall`, which assumes total loss. | Repairs only affect probability or premium in your model, not this number. |
| Rent | `monthly_rent()` returns `None` for 176 of 436 residential LA ZIPs, and some are very high (90272 is about $12,849 a month). | Handle `None`. Living expenses are left out of totals there. |
| Coverage can be missing | `current.coverage` is `None` if the module raises, for example `extended_replacement_pct` of 500. | Handle `None`, and keep the demo running. |
| Severity words | Module gaps use `info`. `current.insurance_gap` uses `low`. | Read from one or the other, not both. |

## The rule that needs real work: unknown is not zero

Atharva requires every field to distinguish **confirmed zero, not applicable and unknown**, and to never assume missing means no coverage. **Today's code breaks this in these places:**

| Location | Behavior today | Why it's a problem |
| --- | --- | --- |
| `app.py` `build_inputs()`, `zero()` | Empty liability, loss of use and extended replacement become `0` | Unknown looks like confirmed zero |
| `app.py` checkboxes and `DEFAULTS` | `code_upgrade` and `debris_removal` default to `False` | An unanswered box looks like "not covered" |
| `payout.py` `_living_expenses` | FAIR Plan with loss of use `None` pays $0, per the build plan | Assumes no coverage |
| `payout.py` `compute_totals` | Deductible `None` counts as $0, with a warning | Can understate the shortfall |
| `payout.py` `_rebuild` | Extended `None` counts as 0; guaranteed `None` counts as not included | No widening |
| `gaps.py` `low_extended_replacement` | `None` counts as 0, so the gap fires | Reports a gap for an unknown |
| `policy_extract.py` `normalize()` | `amount or None`, `pct or None` | A confirmed 0% or $0 is lost |
| `policy_extract.py` `merge_policies()` | Keeps values only | `source_text`, `page` and `verified` are lost |

**The extractor already has the raw material.** `not_found` lists fields absent from the page, and `code_upgrade` and `debris_removal` come in as `covered`, `excluded` or `not_mentioned`. Build statuses from those. The per-field evidence is in `st.session_state["extractions"]` as `(filename, {"fields": {name: {"value", "source_text", "page", "verified"}}, "source", "text_layer"})`.

Changing the payout rules above changes tested numbers, including Case 1 in `tests/coverage/test_payout.py`. **Ask David before changing them.** You can report honest statuses in the new output without touching the math.

## Field map

**Status:** ✅ available, 🟡 partial, ❌ not captured. "Extractor" is a field in `policy_extract.FIELDS`. "Form" is a key in `app.py` session state.

### Policy details

| Atharva's field | Priority | Status | Where it is now | What's needed |
| --- | --- | --- | --- | --- |
| Insurance company | Yes | 🟡 | Extractor `insurer_name` | Dropped by `apply_policy` and `build_inputs`; carry it through. Read from the document only; AI must not generate names |
| Policy type | Yes | 🟡 | Extractor `document_type`; form `ins_type` | No form type such as HO-3. Extraction spec lists `policy_form`, but the code doesn't extract it |
| Effective and expiration dates | Yes | 🟡 | Extractor `effective_date` | No expiration date |
| Dwelling, Coverage A | Critical | ✅ | Extractor and form `dwelling_limit` | |
| Extended replacement | Critical | 🟡 | Extractor and form `extended_replacement_pct` | Form can't say "none" vs "unknown" |
| Guaranteed replacement | Yes | ❌ | `PolicyInput.guaranteed_replacement` accepts it, nothing supplies it | Add to form and extractor |
| Wildfire deductible | Critical | 🟡 | Extractor `deductible_wildfire` as `{amount, pct}`; form `deductible` is one number | Keep the percentage and its basis; form loses which deductible it was |
| Annual premium | Yes | ✅ | Extractor and form `premium_total` | Sums FAIR and DIC |
| ALE | Yes | 🟡 | Extractor and form `loss_of_use_limit` | No months |
| Ordinance or law | Yes | 🟡 | Extractor `code_upgrade` as `{covered, limit, pct}`; form `code_upgrade`, `code_upgrade_amount` | `limit` is always `None` from the extractor today |
| Debris removal | Yes | 🟡 | Extractor and form `debris_removal` | No limit, nothing on whether it's inside Coverage A |
| Coverage B | Yes | ✅ | Extractor and form `other_structures_limit` | |
| Coverage C | Recommended | ✅ | Extractor and form `contents_limit` | |
| Wildfire coverage status | Critical | ❌ | Nowhere | Add to form, or the extractor (see trap below) |
| Exclusions and endorsements | Critical | ❌ | Nowhere | Extractor schema change |
| Source and verification | Critical | 🟡 | Per field in extractions | Lost in `merge_policies()`; manual entries have no source |

### Property

| Atharva's field | Priority | Status | Where it is now | What's needed |
| --- | --- | --- | --- | --- |
| Full address | Critical | ✅ | `inputs["address"]`; `area["geocode"]["matched_address"]`, `["zip"]` | |
| Living area | Critical | ✅ | `home["living_area_sqft"]` | |
| Year built | Yes | ✅ | `home["year_built"]` | |
| Stories | Yes | ✅ | `home["stories"]` | |
| Roof material | Critical | ✅ | `home["ROOFCONSTRUCTION"]` | DINS options |
| Exterior siding | Yes | ✅ | `home["EXTERIORSIDING"]` | DINS options |
| Vent type | Critical | 🟡 | `home["VENTSCREEN"]` | Mesh size, not ember-resistant; a mapping would be an assumption |
| Window type | Recommended | 🟡 | `home["WINDOWPANE"]` | No tempered option |
| Defensible space 0–5 ft | Critical | 🟡 | `measures_done` has `ember_zone_5ft` | Only a checkbox: unchecked isn't unknown |
| Defensible space 5–30 ft | Critical | 🟡 | `measures_done` has `defensible_space` | One checkbox, not by zone |
| Attached structures | Yes | 🟡 | `DECKPORCHELEVATED`, `FENCEATTACHEDTOSTRUCTURE`, `UTILITYMISCSTRUCTUREDISTANCE` | No garage |
| Property type | Critical | ❌ | Not asked | Add |
| Roof fire class | Critical | ❌ | Not asked. `class_a_roof` is inferred from material | Add. **Don't infer class from material without labeling it** |
| Assessment source | Critical | ❌ | Not asked | Add; sample and form data are homeowner-reported |
| Construction material, finish quality | Yes | ❌ | Not asked | Add |
| Gutters | Yes | ❌ | Not asked | Add |
| Defensible space 30–100 ft | Yes | ❌ | Not asked | Add |
| Vegetation proximity | Yes | ❌ | Not asked | Add |
| Roof age and condition, site constraints | Recommended | ❌ | Not asked | Add later |

`contract.validate_inputs()` rejects unknown values only for fields in `HOME_OPTIONS`, so new `home` keys are allowed. If you reuse DINS fields for model features, read the warnings in `docs/validation_report.md`: DINS `Unknown` values leak the outcome.

### Rebuild cost evidence

None of the seven fields is captured: existing estimate, its source and date, rate per sq ft, scope, demolition, permits and soft costs. All are optional or "if available", so add them as optional and report `unknown`. Atharva's estimator isn't in the repo at `d7d3982`.

## Build order

Do these in order. Tasks 1 and 2 don't change existing numbers.

### 1. Add a read-only profile

Add `src/msba_vibathon_2026/coverage/profile.py` with `build_profile(inputs, area, extractions=None) -> dict`, and call it from nowhere that can break the plan. Suggested shape, a proposal to confirm with Atharva:

```json
{
  "policy": {
    "dwelling_limit": {"value": 650000, "status": "confirmed", "source": {"type": "document", "file": "fair_plan_altadena.pdf", "page": 1, "quote": "...", "verified": true}},
    "guaranteed_replacement": {"value": null, "status": "unknown", "source": null}
  },
  "property": {},
  "rebuild_evidence": {}
}
```

- `status` is one of `confirmed`, `confirmed_zero`, `not_applicable`, `unknown`.
- **Include every field on the list above,** reporting `unknown` when not captured, so the shape never changes.
- A form value of `0` from `zero()` isn't a confirmed zero. Treat it as `unknown` unless the extractor found it or you've added a real "none" answer.

### 2. Collect the missing Critical answers

Add these to the form with an explicit "I don't know" option: property type, roof fire class, defensible space by zone, assessment source, wildfire coverage status. Follow the `OPTIONAL_INSURANCE` and `OPTIONAL_HOME` pattern in `app.py`: define the key, add it to `DEFAULTS`, and reset it in `load_scenario`. Existing tests fill the form by label, so don't rename labels.

### 3. Connect the rebuild estimator

There's no way to pass an estimate in yet. `costs._rebuild()` reads the config range. Add an optional input such as `HomeInput.rebuild_estimate: Range | None`, use it when present, and fall back to config. Then `other_structures` follows automatically, because it's a share of rebuild. Also review `underinsured` and `possibly_underinsured` in `gaps.py`, `above_fair_cap`, and `rebuild` in `assess()`, so **one number** reaches the screen. Label it with its source.

### 4. Build the comparison

Put it in a new module and add its result under a new optional key such as `future.plan_comparison`. Wrap the call so that a failure leaves the plan working, the way `coverage_for_assess()` does. Extend `contract.validate_output()` for the new key.

### 5. Extractor changes last

Wildfire status, exclusions, expiration date and `policy_form` need a change to `_PROPS` in `policy_extract.py`. **This is the riskiest step:**

- Joaquín already had to fix this schema for API limits.
- `_PROPS` is strict, with every field required.
- Cached results in `data/demo/policy_extractions.json` don't have new fields.
- It can't be proven without a live API key. Fake-Claude tests alone don't show the real API accepts it.

Skip it before the demo unless someone can test it live.

## Guardrails

**Stop and ask David or the team before you:**

- Change `config.yaml` values, or the Case 1 to 5 numbers in `tests/coverage/test_scenario.py`.
- Change payout rules for unknown inputs.
- Add alternative-plan premiums from any source. **`docs/hackathon_brief.md` says there's no public premium per home, and `discounts.csv` and `grants.csv` are empty.** If premiums are assumed, they must be labeled in the data and in the app (`AGENTS.md` rule 3).
- Recommend a specific insurer. The coverage module's rule is to explain gaps and never recommend an insurer or product, and AI must never produce insurer names (`AGENTS.md` rule 4). Compare plan **types and coverage levels** unless the team decides otherwise.
- Fill a blank in `measures.csv`, `discounts.csv` or `grants.csv` without a source or an assumption flag.

**Never:**

- Treat the exposure score as a probability, or derive `p_destroyed` from placeholder scores without labeling it.
- Present assumed numbers as real savings, or let AI add a number that code didn't compute.
- Hand-edit files in `data/processed/`. Change `scripts/02_process.py` and rerun it.
- Add `Unknown` DINS values or post-fire DINS fields as model features.
- Let a failure in new code stop the plan from finishing. Keep the fallback pattern.

## Known unverified items

Don't build anything that depends on these as facts:

- The $3,000,000 FAIR Plan cap isn't confirmed on the cfpnet.com pages checked.
- The ACV deadline in Ins. Code 2051.5 needs checking; sources disagree.
- The Coverage Cat and AOL citations in `config.yaml` weren't reviewed.
- The house damage score is a placeholder.
- Live PDF reading through `coverage/adapter.py` and the new form fields wasn't tested with a real API key.

## Done checklist

- [ ] `uv run pytest` passes, with new tests written for new behavior.
- [ ] `uv run python scripts/smoke_test.py` passes.
- [ ] The two code blocks in "Run it" and "Using the module" still pass, or are updated.
- [ ] `altadena_fair_only` still shows $354,490 to $902,985, or the change is explained and David agreed.
- [ ] Every field on Atharva's list is in the profile with a status, and nothing unknown is reported as zero.
- [ ] A forced failure in the new model leaves the plan finishing, with a test.
- [ ] Every assumed number is labeled in the data and in the app.
- [ ] You ran the app in a browser. Headless tests missed clipped text once already: `st.metric` cuts off long ranges, so use text for ranges.
- [ ] `AGENTS.md`, `docs/inputs_and_contract.md` and this document are updated.
