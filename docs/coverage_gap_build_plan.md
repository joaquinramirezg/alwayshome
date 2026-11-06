# Build plan: Coverage gap and loss scenario module

## Context

We're building a Streamlit app for a 24-hour hackathon (UCLA Anderson MSBA Vibathon, theme "Uninsurable"). It helps California homeowners on the FAIR Plan understand why their home is hard to insure and what to do about it.

You are building one backend module: **the coverage gap and loss scenario engine.** It answers: "If a wildfire reaches my home, what happens, and who pays?"

- Inputs: the homeowner's policy (already extracted from a PDF and confirmed by the user), home details, area data, and the risk model's probability of destruction.
- Outputs: coverage gaps (what's wrong with the policy) and a total-loss scenario (cost to recover vs. what the policy pays vs. out-of-pocket shortfall).

Other teammates own: PDF extraction, the risk model, the optimizer, the frontend, and the AI report. Do not build those.

## Ground rules

- **Never invent numbers.** Every threshold, rate or assumption lives in `config.yaml` with a `source_url` and a `note`. If a value has no source, it's marked `assumption: true`.
- **Ranges everywhere.** Every cost, payout and shortfall is a `{low, high}` pair. Never a single estimate.
- **Unknown inputs widen the range, they never crash.** For any `None` input, the low shortfall assumes the favorable case and the high shortfall assumes the unfavorable case, and an `info` flag is added.
- **Total loss only.** Partial damage is out of scope; say so in the output (`scope_note`).
- **Explain gaps, never recommend a specific insurer or product.**
- Python 3.11+, Pydantic v2, pytest. Pure functions, no network calls at runtime (rent data is preloaded).
- Use only existing data files in `data/processed/` plus the rent file you add in Step 2.

## Project layout

```
src/coverage/
  __init__.py
  config.yaml        # all numbers + sources
  config.py          # loads and validates config.yaml
  schemas.py         # Pydantic models (inputs + outputs)
  costs.py           # cost of a total loss, by component
  payout.py          # what the policy pays, by component
  gaps.py            # coverage gap rules
  scenario.py        # combines everything: run_coverage_analysis()
  rent.py            # monthly rent lookup by ZIP
tests/coverage/
  test_costs.py
  test_payout.py
  test_gaps.py
  test_scenario.py   # the 5 hand-calculated cases below
```

## Step 1: `config.yaml`

Use exactly these values and sources.

```yaml
rebuild_cost_per_sqft:
  low: 300
  high: 500
  source_url: https://uphelp.org/wildfire-survivors-are-finding-out-they-are-underinsured-after-losing-their-homes/
  note: "United Policyholders rule of thumb: coverage of at least $300/sq ft; experts say rebuilding may need upwards of $500/sq ft. Post-disaster price surges can add more."

price_surge_note:
  text: "Contractor prices after disasters can run 30% to 50% above normal."
  source_url: https://www.coveragecat.com/insurance-types/which-homeowners-endorsements-are-worth-the-money

code_upgrade_recommended_pct_of_dwelling:
  low: 0.25
  high: 0.50
  source_url: https://www.coveragecat.com/insurance-types/which-homeowners-endorsements-are-worth-the-money
  note: "Expert recommendation for older California homes, not a measured cost. Policies commonly carry 5% to 20%. United Policyholders: code upgrades can hit six figures (https://uphelp.org/cracking-the-code/)."

other_structures_cost_pct_of_rebuild:
  value: 0.10
  assumption: true
  note: "Default when the user gives no estimate. Mirrors the common 10% of Coverage A convention."

fair_plan_other_structures_pct_of_dwelling:
  value: 0.10
  source_url: https://uphelp.org/wp-content/uploads/2022/07/1-5-22-FINAL-CFP-Claims-and-Coverage-Basics-.pdf
  note: "If Coverage B is not purchased on a FAIR Plan policy, up to 10% of Coverage A may be used."

living_expense_months:
  low: 24
  high: 36
  source_url: https://www.propertyinsurancecoveragelaw.com/blog/wildfire-rebuilding-timelines-and-ale-extensions/
  note: "CA law: ALE paid at least 24 months after a declared wildfire emergency, mandatory extensions up to 36 months in some cases. Rebuilding often takes longer (Pepperdine study: 5 to 6+ years)."

fair_plan_combined_cap:
  value: 3000000
  source_url: https://www.valuepenguin.com/california-fair-plan-home-insurance
  note: "Combined maximum for dwelling + personal property. VERIFY on cfpnet.com before the demo."

extended_replacement_recommended_min_pct:
  value: 0.25
  source_url: https://www.coveragecat.com/insurance-types/which-homeowners-endorsements-are-worth-the-money
  note: "Typical range 10% to 50%; at least 25% to 50% advised in California."

stale_coverage_years:
  value: 3
  assumption: true
  note: "Coverage not updated in this many years is flagged. United Policyholders cites a family whose policy hadn't been updated since 2017."

contents_no_inventory_rule:
  pct_of_limit: 0.60
  cap: 350000
  effective: "2026-01"
  source_url: https://www.insurance.ca.gov/0400-news/0100-press-releases/2025/release067-2025.cfm
  note: "SB 495: insurers pay 60% of contents limit, up to $350,000, without an itemized inventory after a declared-emergency total loss. Informational only."

debris_removal_note:
  text: "In the LA County government cleanup program, the county recovers the policy's debris-removal amount from the insurer, and owners were not supposed to pay out of pocket or be liable beyond that coverage. Not included in the dollar shortfall."
  source_url: https://www.aol.com/news/fire-debris-clearance-decide-between-002402432.html

acv_warning:
  text: "Your policy pays actual cash value (depreciated value). For a total loss, the payout could be much lower than the amounts shown. Replacement cost may be recoverable only if you rebuild within the legal deadline."
  source_url: https://www.propertyinsurancecoveragelaw.com/blog/california-wildfires-strike-again-a-summary-of-changes-in-the-law-to-help-policyholders/
  note: "Sources disagree on the current deadline (24+6 months vs at least 36 months). VERIFY current Ins. Code 2051.5 before the demo."
```

`config.py` loads this once, validates required keys, and exposes typed values.

## Step 2: Rent data

1. Add Zillow Observed Rent Index (ZORI) by ZIP to the existing data pipeline (`scripts/01_download.py` and `02_process.py`), following the same pattern as the Zillow home value file (public CSV on Zillow's CDN, same research page: https://www.zillow.com/research/data/). If the CDN file can't be found or downloaded, stop and tell me which file to download by hand.
2. Output `data/processed/zip_rent_latest.parquet` with `zip` (5-char string), `rent_latest` (float), `latest_date`. LA County ZIPs only.
3. `rent.py`: `monthly_rent(zip) -> float | None`. Returns `None` if the ZIP has no data.
4. Update `docs/data_dictionary.md` and add a coverage row to the validation report.

## Step 3: Schemas (`schemas.py`)

Field names match the PDF extraction spec. Every field is optional (`None` = unknown).

```python
class PolicyInput(BaseModel):
    document_type: Literal["fair_plan", "dic", "homeowners", "dwelling_fire", "other"] | None
    has_dic: bool | None                      # supplemental policy present (FAIR Plan only)
    dic_covers: list[str] = []
    premium_total: float | None               # all policies combined, per year
    dwelling_limit: float | None              # Coverage A
    other_structures_limit: float | None      # Coverage B; None = not on page; 0 = explicitly not covered
    contents_limit: float | None              # Coverage C
    loss_of_use_limit: float | None           # Coverage D (ALE or fair rental value)
    dwelling_settlement: Literal["actual_cash_value", "replacement_cost", "unknown"] | None
    extended_replacement_pct: float | None    # 0.25 for 25%
    guaranteed_replacement: bool | None
    contents_settlement: Literal["actual_cash_value", "replacement_cost", "unknown"] | None
    code_upgrade: bool | None
    code_upgrade_amount: float | None
    debris_removal: bool | None
    deductible_all_perils: float | None
    deductible_wildfire: float | None
    last_coverage_update_year: int | None
    nonrenewal_notice: bool | None

class HomeInput(BaseModel):
    zip: str
    sq_ft: float | None
    stories: int | None
    year_built: int | None
    contents_value_estimate: float | None
    other_structures_estimate: float | None
    renovated_since_update: bool | None

class RiskInput(BaseModel):
    p_destroyed: float | None                 # from the risk model; placeholder until it exists
```

Output models:

```python
class Range(BaseModel):
    low: float | None
    high: float | None

class Component(BaseModel):
    name: Literal["rebuild", "code_upgrade", "other_structures", "contents", "living_expenses"]
    cost: Range
    payout: Range
    shortfall: Range
    notes: list[str] = []

class Gap(BaseModel):
    gap: str
    severity: Literal["high", "medium", "info"]
    evidence: str          # plain language, includes the numbers
    action: str            # what to ask or check, never a product recommendation
    source_url: str | None

class CoverageResult(BaseModel):
    scope_note: str                          # "Total-loss scenario only. Partial damage not modeled."
    p_destroyed: float | None
    components: list[Component]
    deductible: float | None
    total_cost: Range
    total_payout: Range
    total_shortfall: Range                   # includes deductible
    expected_shortfall: Range | None         # p_destroyed x total_shortfall; secondary display
    gaps: list[Gap]
    warnings: list[str]                      # ACV, debris note, price surge, etc.
    premium_total: float | None              # passed through for the optimizer
    assumptions: list[str]                   # every config value used, with its source
```

## Step 4: Costs of a total loss (`costs.py`)

| Component | Low | High | If input unknown |
| --- | --- | --- | --- |
| rebuild | sq_ft x 300 | sq_ft x 500 | sq_ft None: cost None, flag |
| code_upgrade | 0.25 x dwelling_limit | 0.50 x dwelling_limit | dwelling_limit None: None, flag |
| other_structures | user estimate, else 0.10 x rebuild low | user estimate, else 0.10 x rebuild high | |
| contents | user estimate, else contents_limit (flag "assumed equal to your limit") | same | both None: None, flag |
| living_expenses | rent x 24 | rent x 36 | rent None: None, flag "no rent data for ZIP" |

Debris removal is **not** a cost component; add `debris_removal_note` to warnings.

## Step 5: Policy payout (`payout.py`)

| Component | Payout rule |
| --- | --- |
| rebuild | `guaranteed_replacement` True: = rebuild cost. Otherwise min(rebuild cost, dwelling_limit x (1 + extended_replacement_pct or 0)). If `dwelling_settlement` is `actual_cash_value`, compute the same but add `acv_warning` to warnings. If `unknown`/None: treat as replacement cost and add an info flag. |
| code_upgrade | `code_upgrade_amount` if given. `code_upgrade` False: 0. True with no amount, or None: unknown (low shortfall assumes fully covered, high assumes 0). |
| other_structures | `other_structures_limit` if > 0. If FAIR Plan and limit is None or 0: 0.10 x dwelling_limit. Otherwise None/0 as given. |
| contents | `contents_limit` (0 if explicitly not covered). Add the SB 495 note when contents_limit > 0. If `contents_settlement` is ACV, add a warning. |
| living_expenses | `loss_of_use_limit` (None on a FAIR Plan page = 0 with a note; None elsewhere = unknown). |

Per component: `shortfall.low = max(0, cost.low - payout_high_case)`, `shortfall.high = max(0, cost.high - payout_low_case)`, where the payout cases differ only when an input is unknown.

Totals: sum components; add the deductible once to both total shortfall bounds (use `deductible_wildfire` if present, else `deductible_all_perils`, else 0 with a flag). `expected_shortfall = p_destroyed x total_shortfall` when p_destroyed is known.

**FAIR Plan + supplemental:** if `has_dic` is True, the dwelling payout stays the FAIR Plan's. Do not add DIC dollar amounts to the shortfall math in this version; instead note which perils/items the DIC covers (`dic_covers`).

## Step 6: Gap rules (`gaps.py`)

Each rule is a small function returning `Gap | None`. Keep them in a list so new rules are easy to add.

| gap | Fires when | Severity | Action text (adapt) |
| --- | --- | --- | --- |
| `underinsured` | dwelling_limit / sq_ft < rebuild low ($300) | high | "Ask your insurer to update your dwelling limit to current rebuild costs." |
| `possibly_underinsured` | between $300 and $500/sq ft | medium | "Your coverage may not cover a full rebuild at today's costs." |
| `stale_coverage` | last update >= 3 years ago, or renovated since | medium | "Ask your insurer to review your coverage amount." |
| `fair_no_dic` | FAIR Plan and has_dic is False | high | "The FAIR Plan doesn't cover water damage, theft or liability. A supplemental (DIC) policy fills those gaps." |
| `actual_cash_value` | dwelling_settlement = ACV | high | "Ask about replacement cost coverage." |
| `low_extended_replacement` | extended_replacement_pct < 0.25 and not guaranteed | medium | "California experts advise 25% to 50% extended replacement cost." |
| `no_code_upgrade` | code_upgrade False, or amount < 0.25 x dwelling_limit | high if False, medium if low | "Code upgrades after a fire can reach six figures." |
| `no_debris_removal` | debris_removal False | medium | Use `debris_removal_note`. |
| `no_living_expenses` | loss_of_use_limit is 0/None on a FAIR Plan | high | "If your home is destroyed, you'd pay rent yourself during rebuilding." |
| `no_contents` | contents_limit is 0 | high | "Your belongings aren't covered." |
| `above_fair_cap` | FAIR Plan and rebuild high + contents cost > $3,000,000 | high | "Your needs may exceed the FAIR Plan's combined limit." |
| `renewal_risk` | nonrenewal_notice True | medium | "Prioritize fire-safety fixes before your renewal date." |
| `unknown_field` | any of: dwelling_limit, dwelling_settlement, code_upgrade, loss_of_use_limit is None | info | "Check your declarations page for X." |

Every gap's `evidence` includes the actual numbers (e.g. "Coverage $250/sq ft; rebuild estimates $300 to $500+/sq ft").

## Step 7: Main function (`scenario.py`)

```python
def run_coverage_analysis(policy: PolicyInput, home: HomeInput, risk: RiskInput) -> CoverageResult
```

Order: costs, payouts, shortfalls, totals, gaps, warnings, assumptions list (every config value used, with source). Until the risk model exists, callers pass `RiskInput(p_destroyed=None)`; the function must work either way.

## Step 8: Tests (`tests/coverage/`)

Unit tests per rule and per component, plus these five hand-calculated scenarios. Use a mocked rent value (not the real file) so results are deterministic.

### Case 1: FAIR Plan only, underinsured (demo case)
Inputs: FAIR Plan, has_dic False, sq_ft 1,800, dwelling 450,000, ACV, no extended, code_upgrade False, debris False, B not purchased (None), contents_limit 0, loss_of_use None, deductible 1,000, last update 2017, contents estimate 100,000, rent 4,000/month.

| Component | Cost low/high | Payout | Shortfall low/high |
| --- | --- | --- | --- |
| rebuild | 540,000 / 900,000 | 450,000 | 90,000 / 450,000 |
| code_upgrade | 112,500 / 225,000 | 0 | 112,500 / 225,000 |
| other_structures | 54,000 / 90,000 | 45,000 | 9,000 / 45,000 |
| contents | 100,000 / 100,000 | 0 | 100,000 / 100,000 |
| living_expenses | 96,000 / 144,000 | 0 | 96,000 / 144,000 |

Total shortfall incl. deductible: **408,500 / 965,000**.
Expected gaps: underinsured ($250/sq ft), stale_coverage, fair_no_dic, actual_cash_value, low_extended_replacement, no_code_upgrade, no_debris_removal, no_living_expenses, no_contents. Warnings include ACV and debris notes.

### Case 2: Private HO-3, well covered
Inputs: homeowners, sq_ft 2,000, dwelling 1,100,000, replacement cost, extended 0.50, code_upgrade True with amount 275,000, debris True, B 110,000, C 550,000, D 330,000, deductible 2,500, last update 2025, contents estimate 300,000, rent 5,000.

| Component | Cost low/high | Payout | Shortfall low/high |
| --- | --- | --- | --- |
| rebuild | 600,000 / 1,000,000 | = cost (limit 1.65M) | 0 / 0 |
| code_upgrade | 275,000 / 550,000 | 275,000 | 0 / 275,000 |
| other_structures | 60,000 / 100,000 | 110,000 | 0 / 0 |
| contents | 300,000 / 300,000 | 550,000 | 0 / 0 |
| living_expenses | 120,000 / 180,000 | 330,000 | 0 / 0 |

Total shortfall incl. deductible: **2,500 / 277,500**. Expected gaps: none high severity.

### Case 3: High-value home on the FAIR Plan
Inputs: FAIR Plan, sq_ft 5,500, contents estimate 600,000, other fields as Case 1.
Rebuild high = 2,750,000; + contents 600,000 = 3,350,000 > 3,000,000 cap. Expected: `above_fair_cap` fires.

### Case 4: ACV with unknown add-ons
Inputs: dwelling_settlement ACV, code_upgrade None, loss_of_use_limit None, other fields as Case 2.
Expected: ACV warning, `unknown_field` info gaps for code_upgrade and loss_of_use, wider shortfall ranges (low assumes covered, high assumes not), no crash.

### Case 5: Everything unknown
Inputs: only `zip` and `sq_ft` set.
Expected: no exception; costs computed where possible; payouts and shortfalls null or wide; `unknown_field` gaps listed; `scope_note` present.

## Definition of done

- All tests pass, including the five cases with exact numbers above.
- `run_coverage_analysis()` output validates against `CoverageResult`.
- Every number in the output traces to inputs or `config.yaml`.
- `docs/coverage_module.md`: how to call it, input/output examples (Case 1), list of assumptions and sources, and the two "VERIFY before demo" items (FAIR Plan cap, ACV deadline).
- Short summary back to me: what was built, anything skipped, any value you couldn't source.
