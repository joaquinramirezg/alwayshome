# Coverage gap and loss scenario module

Answers one question: if a wildfire destroys this home, what does it cost, what does the policy pay, and who pays the rest? **Total loss only; partial damage is not modeled.**

The code is in `src/msba_vibathon_2026/coverage/`, and every rate and threshold is in `config.yaml`. It makes no network calls. Rent comes from `data/processed/zip_rent_latest.parquet`.

## How to call it

```python
from msba_vibathon_2026.coverage.scenario import run_coverage_analysis
from msba_vibathon_2026.coverage.schemas import HomeInput, PolicyInput, RiskInput

result = run_coverage_analysis(
    PolicyInput(document_type="fair_plan", has_dic=False, dwelling_limit=450_000,
                dwelling_settlement="actual_cash_value", code_upgrade=False, debris_removal=False,
                contents_limit=0, deductible_all_perils=1_000, last_coverage_update_year=2017),
    HomeInput(zip="91001", sq_ft=1_800, contents_value_estimate=100_000),
    RiskInput(p_destroyed=None),   # None until the risk model exists
)
result.total_shortfall.low, result.total_shortfall.high
```

`as_of_year` is an optional fourth argument for the stale coverage rule, and it defaults to the current year. Only `HomeInput.zip` is required. `None` means unknown, and `0` means explicitly not covered. Run the tests with `uv run pytest tests/coverage -q`.

## Example: Case 1

This uses the inputs above with a mocked rent of $4,000 a month and `as_of_year=2026`. **With real data, 91001's rent is about $3,833, so the live total is $404,490 to $958,985.**

| Component | Cost | Payout | Shortfall |
| --- | --- | --- | --- |
| rebuild | 540,000 to 900,000 | 450,000 | 90,000 to 450,000 |
| code_upgrade | 112,500 to 225,000 | 0 | 112,500 to 225,000 |
| other_structures | 54,000 to 90,000 | 45,000 | 9,000 to 45,000 |
| contents | 100,000 | 0 | 100,000 |
| living_expenses | 96,000 to 144,000 | 0 | 96,000 to 144,000 |

```json
{
  "scope_note": "Total-loss scenario only. Partial damage not modeled.",
  "p_destroyed": null,
  "deductible": 1000.0,
  "total_cost": {"low": 902500.0, "high": 1459000.0},
  "total_payout": {"low": 495000.0, "high": 495000.0},
  "total_shortfall": {"low": 408500.0, "high": 965000.0},
  "expected_shortfall": null,
  "premium_total": null
}
```

The result also has `components`, `warnings` (ACV, debris, price surge) and `assumptions`. Case 1's `gaps`:

| Gap | Severity | Evidence |
| --- | --- | --- |
| `underinsured` | high | Coverage $250/sq ft; rebuild estimates $300 to $500+/sq ft. |
| `stale_coverage` | medium | Coverage last updated in 2017, 9 years ago (flagged at 3 years). |
| `fair_no_dic` | high | FAIR Plan policy with no supplemental (DIC) policy. |
| `actual_cash_value` | high | Dwelling settlement is actual cash value. The $450,000 dwelling limit may not be what you are paid. |
| `low_extended_replacement` | medium | Extended replacement: none listed; advised at least 25%. |
| `no_code_upgrade` | high | No code upgrade coverage on this policy. Estimated code upgrade cost: $112,500 to $225,000. |
| `no_debris_removal` | medium | No debris removal coverage on this policy. |
| `no_living_expenses` | high | Loss of use limit: not on the page. Estimated living expenses: $96,000 to $144,000. |
| `no_contents` | high | Contents limit: $0. Your estimated contents: $100,000. |

## Reading the numbers

- **Partly unknown totals are minimums.** Totals leave out components with unknown cost, and a warning names them. Show that warning next to the total.
- **`total_payout` caps each component at its cost,** because a limit above the loss isn't money paid. Component payouts show the full limit.
- **Actual cash value policies are computed as if they paid replacement cost.** The real shortfall may be above the high figure, and the output warns about this.
- **The DIC policy adds no dollars.** It only adds a note listing `dic_covers`.

## Connecting it to the app

Nothing calls this module yet. The caller has to convert these, based on `origin/app-streamlit` at the time of writing:

| App or extractor | This module | Conversion |
| --- | --- | --- |
| `extended_replacement_pct` of `25` | `0.25` | **Divide by 100.** Values above 1 raise a validation error. |
| `living_area_sqft` | `sq_ft` | Rename |
| `deductible_wildfire` as a percentage | Dollars | Convert first; a percentage isn't accepted as dollars. |
| `documents` list | `document_type` plus `has_dic` | Use `fair_plan` as the type when a FAIR Plan is present. |
| Not extracted | `code_upgrade_amount`, `last_coverage_update_year`, `nonrenewal_notice` | Ask the user, or leave as `None`. `stale_coverage` and `renewal_risk` can't fire on these fields without them. |

`origin/app-streamlit` also has its own `gaps.py` with a hard-coded $450/sq ft, while this module uses $300 to $500. Use one or the other, or the demo can show two answers.

## Assumptions and sources

`result.assumptions` lists these on every run, plus the rent used.

| Config entry | Value | Status | Source |
| --- | --- | --- | --- |
| `rebuild_cost_per_sqft` | $300 to $500 | Sourced | [United Policyholders](https://uphelp.org/wildfire-survivors-are-finding-out-they-are-underinsured-after-losing-their-homes/) |
| `price_surge_note` | 30% to 50% (warning text) | Sourced | [Coverage Cat](https://www.coveragecat.com/insurance-types/which-homeowners-endorsements-are-worth-the-money) |
| `code_upgrade_recommended_pct_of_dwelling` | 25% to 50% | **Used as an assumption:** a recommendation, not a measured cost | [Coverage Cat](https://www.coveragecat.com/insurance-types/which-homeowners-endorsements-are-worth-the-money) |
| `other_structures_cost_pct_of_rebuild` | 10% | **Assumption** | None |
| `fair_plan_other_structures_pct_of_dwelling` | 10% | Sourced, see open issues | [United Policyholders PDF](https://uphelp.org/wp-content/uploads/2022/07/1-5-22-FINAL-CFP-Claims-and-Coverage-Basics-.pdf) |
| `living_expense_months` | 24 to 36 | Sourced | [Merlin Law](https://www.propertyinsurancecoveragelaw.com/blog/wildfire-rebuilding-timelines-and-ale-extensions/) |
| `fair_plan_combined_cap` | $3,000,000 | Sourced, **VERIFY** | [ValuePenguin](https://www.valuepenguin.com/california-fair-plan-home-insurance) |
| `extended_replacement_recommended_min_pct` | 25% | Sourced | [Coverage Cat](https://www.coveragecat.com/insurance-types/which-homeowners-endorsements-are-worth-the-money) |
| `stale_coverage_years` | 3 | **Assumption** | None |
| `contents_no_inventory_rule` | 60%, up to $350,000 | Sourced, see open issues | [CDI](https://www.insurance.ca.gov/0400-news/0100-press-releases/2025/release067-2025.cfm) |
| `debris_removal_note` | Warning text | Sourced | [AOL](https://www.aol.com/news/fire-debris-clearance-decide-between-002402432.html) |
| `acv_warning` | Warning text | Sourced, **VERIFY** | [Merlin Law](https://www.propertyinsurancecoveragelaw.com/blog/california-wildfires-strike-again-a-summary-of-changes-in-the-law-to-help-policyholders/) |
| Rent (not in config) | By ZIP | Data | [Zillow ZORI](https://www.zillow.com/research/data/) |

## Verify before the demo

1. **FAIR Plan cap ($3,000,000).** ValuePenguin says $3 million combined for home and belongings. The cfpnet.com homepage and dwelling page state no limit, so it's not confirmed there. The [sample dwelling policy](https://www.cfpnet.com/wp-content/uploads/2026/01/Dwelling-Fire-Policy_effective-3-17-26.pdf) hasn't been checked.
2. **ACV deadline (Ins. Code 2051.5).** The cited 2020 post says 24 months plus 6 for good cause. A January 2026 post by the same firm describes at least 36 months for the repair or rebuild deadline. The warning text gives no number, so it doesn't need changing, but check the current code before quoting one.

## Open issues from the source check

- **FAIR Plan Coverage B may be counted twice.** The United Policyholders PDF says that with no Coverage B on the declarations, "you can use up to 10% of the Coverage A limit" (slide 25). Slide 26 says other structures cover can be within or on top of the dwelling limit, depending on what was sold. The module follows the build plan and pays it on top. If it comes out of Coverage A, Case 1's total is $453,500 to $1,010,000.
- **SB 495 wording.** The config note says insurers pay "without an itemized inventory". CDI says no detailed inventory is needed "for at least 100 days", so it's deferred, not waived. The note appears in the contents component's notes.

## Limits

- Total loss only, and only LA County ZIPs with Zillow rent data (260 of them). 176 of the 436 residential LA ZIPs have no rent, so living expenses are unknown there.
- Rent is a ZIP-wide typical figure, not the rent of a comparable home, and can be high (90272 is about $12,849 a month).
- The rebuild rate is a rule of thumb, not a contractor estimate. A price surge is a warning, not part of the numbers.
- Code upgrade cost scales with the dwelling limit, so it's lower for more underinsured homes.
- Each component is capped by its own limit. California law lets some policyholders combine dwelling and other structures limits after a declared emergency (slide 27 of the same PDF), which isn't modeled.
- Gaps explain problems and never recommend an insurer or product.
