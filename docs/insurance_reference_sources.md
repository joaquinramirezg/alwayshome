# Insurance reference source register

Accessed **2026-11-06**. Catalog files are in
`src/msba_vibathon_2026/insurance_gap/reference_data/`. Source IDs resolve to exact
URLs, publication/effective dates (null when unknown), retrieval date, verification
status and limitations in `sources.json`. “Verified” describes the referenced
content, not availability, underwriting approval, a legal opinion or a quote.

| ID | Primary source | Publication/effective date | Use and limits |
|---|---|---|---|
| cdi_sfw | [CDI framework](https://www.insurance.ca.gov/01-consumers/200-wrr/Safer-from-Wildfires.cfm) | Undated live page | Ten potential discount-condition records; no premium amounts. |
| calfire_retrofit | [CAL FIRE retrofit guide](https://readyforwildfire.org/wp-content/uploads/2025/04/Low-Cost-Retrofit-Flyer-Handout-.pdf) | Updated April 2025 | Recommendations; no dollar estimates. |
| calfire_space | [CAL FIRE defensible space](https://www.fire.ca.gov/dspace/) | Undated live page | Fuel-management guidance; legal application must be established for the property. |
| la_fire | [LA County Fire guidance](https://fire.lacounty.gov/fire-hazard-reduction-programs/) | Undated live page | Local gutter-maintenance recommendation; site clearance orders may differ. |
| bof_zone0 | [Board of Forestry](https://bof.fire.ca.gov/projects-and-programs/defensible-space-zones-0-1-and-2) | Undated live status; September 2026 guidance linked | Final regulatory review described as pending; not used to assert a mandate/deadline. |
| fair_form | [FAIR Plan dwelling form](https://www.cfpnet.com/wp-content/uploads/2026/01/Dwelling-Fire-Policy_effective-3-17-26.pdf) | Form edition 05/2026; URL suggests March 17; effective date unresolved | Public specimen terms only. Check elected coverages and actual issued form. |
| fair_discounts | [FAIR Plan discount sheet](https://www.cfpnet.com/wp-content/uploads/2025/11/Discounts-for-Dwelling-Fire-Commercial-Policies-2025.11.15.pdf) | Revised October 2025; applicable November 15, 2025 | Seven selected conditional measures; not acceptance criteria. No calculated savings. |
| farmers_ca | [Farmers California overview](https://www.farmers.com/california/home-insurance/) | Undated live page | Smart Plan Home options; no individual price or limits inferred. |
| mercury_home | [Mercury overview](https://www.mercuryinsurance.com/insurance/homeowners/) | Undated live page | Multistate description; CA applicability of specific advertised options unresolved. |
| headwaters_2024 | [Headwaters retrofit study](https://headwaterseconomics.org/wp-content/uploads/2024/06/Wildfire_Retrofit_Report_20240624.pdf) | Spring 2024; summer/fall 2023 price basis | Historical unit/example observations, primarily Northern California. No current LA project pricing. |

All ten source documents/pages were read through the web research tool. The numeric
observations use the study's named example-cost sections, recorded per row. No
local full GIS, national source tables or raw downloads were loaded or changed.

## Verification and date semantics

`source.valid_from` and `valid_through` are both **2026-11-06**: this is deliberately
a one-day research snapshot, not an invented legal effective date or promise of
continued availability. `publication_date` and `effective_date` are separate fields.
Reverify mutable source content and extend the snapshot only after review. Other
as-of dates naturally retain unavailable/unknown behavior. Missing publication dates
are null, not filled with the retrieval date. Year-month and seasonal publication
labels are preserved at their actual precision.

## Cost observations and evidence gaps

Five observations are retained for context; point estimates are marked as points,
not fabricated uncertainty ranges. No Southern California multiplier, inflation
forecast, quantities or invented markup is applied. They do not establish an
installed whole-project LA budget. Vegetation management has a separate null-priced
evidence-gap record. Locally scoped bids are still required for automatic totals.

Primary-source local searches did not establish suitable whole-project prices.
Inspection fees, municipal road/curb-gutter costs, grant reimbursement caps and
retail material prices do not measure installed residential wildfire mitigation.
They were not substituted. The [study](https://headwaterseconomics.org/wp-content/uploads/2024/06/Wildfire_Retrofit_Report_20240624.pdf)
is the only numerical retrofit source admitted, with the limitations above.

## Code/legal research held for further verification

- [DGS code index](https://www.dgs.ca.gov/BSC/Codes): indexed official text identifies
  the 2025 code cycle/Part 7 and January 2026 statewide effective date, but the direct
  page returned 403. No detailed compulsory retrofit rule was created from it.
- [PRC 4291 official text](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?sectionNum=4291.&lawCode=PRC):
  direct access returned 403. The executable defensible-space rule uses CAL FIRE's
  public explanation and requires a separate verified fact confirming site legal
  applicability. It is not a universal insurer requirement or a legal determination.
- Local amendments, permit dates, existing-building exceptions and authority-specific
  instructions remain review dependencies. No automatic Zone 0 legal classification
  was created from drafts or news.
