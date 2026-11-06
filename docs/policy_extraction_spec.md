# Policy PDF Extraction Spec

What the PDF ingestion pipeline should extract from a homeowner's insurance declarations page. The output feeds the coverage gap rules and the review screen, where the user confirms every value before it is used.

## Output rules (apply to every field)

- Return `value`, `source_text` (the exact words from the PDF) and `page` for each field.
- If a field isn't on the page, return `null`. Never infer or calculate a value.
- Dollar amounts as numbers (`650000`, not `"$650,000"`).
- **Do not extract personal data:** insured names, policy number, mortgage company, phone, email. We don't need them.
- A user may upload two PDFs (FAIR Plan + supplemental DIC policy). Extract each one separately; merging happens downstream.

Example for one field:

```json
"dwelling_limit": {
  "value": 650000,
  "source_text": "Coverage A - Dwelling   $650,000",
  "page": 1
}
```

## 1. Document info

| Field | Type | Common labels | Notes |
| --- | --- | --- | --- |
| `document_type` | enum: `fair_plan`, `dic`, `homeowners`, `dwelling_fire`, `other` | "California FAIR Plan", "Difference in Conditions", "Homeowners HO-3", "Dwelling Fire DP-3" | Decides which rules apply |
| `insurer_name` | string | Company name in the header | |
| `policy_form` | string | "HO 00 03", "HO-3", "DP-3", "Form" | |
| `effective_date` / `expiration_date` | date | "Policy period", "Effective", "Expires" | Used for renewal timing |
| `property_city_zip` | string | "Location", "Insured location", "Residence premises" | City + ZIP only, to check it matches the address entered |

## 2. Coverage limits (most important)

| Field | Type | Common labels |
| --- | --- | --- |
| `dwelling_limit` | number | "Coverage A", "Dwelling" |
| `other_structures_limit` | number | "Coverage B", "Other structures" |
| `contents_limit` | number | "Coverage C", "Personal property", "Contents" |
| `loss_of_use_limit` | number | "Coverage D", "Loss of use", "Additional living expense (ALE)", "Fair rental value" |
| `liability_limit` | number | "Coverage E", "Personal liability" |
| `medical_payments_limit` | number | "Coverage F", "Medical payments to others" |

On FAIR Plan pages, B, C and D may be missing or marked not purchased. Return `null` if missing, and `0` only if the page explicitly says "not covered" or "excluded".

## 3. How losses are paid

| Field | Type | Common labels | Notes |
| --- | --- | --- | --- |
| `dwelling_settlement` | enum: `actual_cash_value`, `replacement_cost`, `unknown` | "Replacement cost", "Actual cash value (ACV)", "Loss settlement" | ACV pays depreciated value, a major gap |
| `extended_replacement_pct` | number | "Extended replacement cost 25%", "Additional replacement cost" | `25` for 25%; `null` if none |
| `guaranteed_replacement` | boolean | "Guaranteed replacement cost" | |
| `contents_settlement` | enum: `actual_cash_value`, `replacement_cost`, `unknown` | "Personal property replacement cost" | |
| `inflation_guard` | boolean | "Inflation guard", "HO 04 46" | |

## 4. Add-ons and endorsements

| Field | Type | Common labels |
| --- | --- | --- |
| `code_upgrade` | boolean + amount | "Ordinance or law", "Building code upgrade", "HO 04 77" |
| `debris_removal` | boolean + amount | "Debris removal" |
| `trees_plants_shrubs` | boolean + amount | "Trees, plants and shrubs" |
| `optional_perils` | list | FAIR Plan: "Extended coverage", "Vandalism and malicious mischief", "Windstorm", "Hail" |
| `water_damage` | boolean | "Water damage", "Water backup", "Sump overflow" |
| `endorsement_codes` | list of {code, description} | Any form codes listed (e.g. "HO 04 90") |

For booleans: `true` if listed, `false` if marked declined or excluded, `null` if not mentioned.

## 5. Deductibles

| Field | Type | Common labels |
| --- | --- | --- |
| `deductible_all_perils` | number | "Deductible", "All other perils" |
| `deductible_wildfire` | number or % | "Wildfire deductible", "Fire deductible" |

If a deductible is a percentage, return both the % and the dollar amount if the page shows it.

## 6. Premium and discounts

| Field | Type | Common labels |
| --- | --- | --- |
| `premium_total` | number | "Total premium", "Annual premium", "Policy premium" |
| `premium_items` | list of {item, amount} | Line items per coverage or endorsement |
| `discounts_listed` | list of {name, amount} | "Mitigation discount", "Safer from Wildfires", "Protective device credit", "Wildfire Prepared Home" |

`discounts_listed` matters: it shows which fire-safety discounts the homeowner already receives.

## 7. Supplemental (DIC) policy only

If `document_type` is `dic`, also extract:

| Field | Type | Notes |
| --- | --- | --- |
| `dic_covers` | list | e.g. water damage, theft, liability, loss of use |
| `dic_dwelling_limit` | number | Should match the FAIR Plan dwelling limit |

## Priority if time is short

1. **Must have:** `document_type`, `dwelling_limit`, `dwelling_settlement`, `extended_replacement_pct`, `code_upgrade`, `debris_removal`, `premium_total`, `effective_date`
2. **Should have:** other limits (B to D), deductibles, `discounts_listed`, DIC fields
3. **Nice to have:** everything else

The must-haves alone power the main gap rules: underinsured, actual cash value settlement, missing code upgrade and debris removal, and FAIR Plan without a supplemental policy.

## After extraction (pipeline checks)

- Validate types against the schema.
- Plausibility checks; set the value to `null` and flag it if it fails:
  - `dwelling_limit` between $50,000 and $10,000,000
  - deductible below `dwelling_limit`
  - `premium_total` above 0
- Process files in memory; don't store uploaded PDFs.
- Test on the five synthetic sample PDFs against the answer key and report field accuracy.
