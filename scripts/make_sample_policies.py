"""Build synthetic declarations-page PDFs and their answer key.

All insurers, people, policy numbers and addresses on these pages are made up
(the FAIR Plan pages imitate the layout of a FAIR Plan declaration, marked SAMPLE).
They include fake personal data on purpose, to test that the extractor leaves it out.

Run: uv run python scripts/make_sample_policies.py
Writes data/samples/policies/*.pdf and data/samples/policies/answer_key.json
"""
from __future__ import annotations

import json
from pathlib import Path

from fpdf import FPDF

OUT = Path(__file__).resolve().parents[1] / "data" / "samples" / "policies"

SAMPLES = {
    "fair_plan_altadena.pdf": {
        "header": ["California FAIR Plan Association", "Dwelling Fire Policy - Declarations", "SAMPLE - SYNTHETIC DOCUMENT FOR TESTING"],
        "lines": [
            ("Named insured", "Maria Example"),
            ("Policy number", "CFP 0099 1234 5678"),
            ("Mortgagee", "Example Home Loans, PO Box 100"),
            ("Policy period", "Effective 2026-03-01 to 2027-03-01"),
            ("Insured location", "Altadena, CA 91001"),
            ("", ""),
            ("Coverage A - Dwelling", "$650,000"),
            ("Loss settlement - Dwelling", "Actual cash value"),
            ("Coverage B - Other structures", "Not purchased"),
            ("Coverage C - Personal property", "$100,000"),
            ("Coverage D - Fair rental value", "Not purchased"),
            ("Perils insured", "Fire, Lightning, Internal Explosion"),
            ("Optional: Extended coverage", "Not purchased"),
            ("Debris removal", "Included within Coverage A limit"),
            ("Deductible - all perils", "$2,500"),
            ("", ""),
            ("Total annual premium", "$6,180"),
        ],
        "answer": {"document_type": "fair_plan", "effective_date": "2026-03-01", "dwelling_limit": 650000,
                   "dwelling_settlement": "actual_cash_value", "extended_replacement_pct": None,
                   "code_upgrade": None, "debris_removal": True, "premium_total": 6180},
    },
    "dic_altadena.pdf": {
        "header": ["Sierra Shield Insurance Co. (fictional)", "Difference in Conditions Policy - Declarations",
                   "Companion to a California FAIR Plan policy", "SAMPLE - SYNTHETIC DOCUMENT FOR TESTING"],
        "lines": [
            ("Named insured", "Maria Example"),
            ("Policy number", "DIC-55-000123"),
            ("Policy period", "Effective 2026-03-01 to 2027-03-01"),
            ("Insured location", "Altadena, CA 91001"),
            ("", ""),
            ("Coverage A - Dwelling (excluding fire)", "$650,000"),
            ("Loss settlement - Dwelling", "Replacement cost"),
            ("Coverage D - Loss of use", "$130,000"),
            ("Coverage E - Personal liability", "$300,000"),
            ("Coverage F - Medical payments", "$1,000"),
            ("Covered perils added", "Theft, Water damage, Windstorm, Personal liability"),
            ("Fire and smoke", "Excluded - covered by FAIR Plan"),
            ("Deductible - all perils", "$1,000"),
            ("", ""),
            ("Total annual premium", "$1,450"),
        ],
        "answer": {"document_type": "dic", "effective_date": "2026-03-01", "dwelling_limit": 650000,
                   "dwelling_settlement": "replacement_cost", "extended_replacement_pct": None,
                   "code_upgrade": None, "debris_removal": None, "premium_total": 1450},
    },
    "homeowners_palisades_underinsured.pdf": {
        "header": ["Golden Poppy Mutual Insurance (fictional)", "Homeowners Policy HO-3 - Declarations",
                   "SAMPLE - SYNTHETIC DOCUMENT FOR TESTING"],
        "lines": [
            ("Named insured", "James Sample"),
            ("Policy number", "GPM-HO3-778812"),
            ("Policy period", "Effective 2026-07-15 to 2027-07-15"),
            ("Residence premises", "Pacific Palisades, CA 90272"),
            ("Policy form", "HO 00 03"),
            ("", ""),
            ("Coverage A - Dwelling", "$900,000"),
            ("Coverage B - Other structures", "$90,000"),
            ("Coverage C - Personal property", "$450,000"),
            ("Coverage D - Loss of use", "$180,000"),
            ("Coverage E - Personal liability", "$500,000"),
            ("Coverage F - Medical payments", "$5,000"),
            ("Loss settlement - Dwelling", "Replacement cost"),
            ("Ordinance or law (HO 04 77)", "10% of Coverage A"),
            ("Debris removal", "Additional 5% of Coverage A"),
            ("Deductible - all other perils", "$2,500"),
            ("Wildfire deductible", "2% of Coverage A ($18,000)"),
            ("", ""),
            ("Premium - base", "$9,530"),
            ("Discount - Safer from Wildfires (Class A roof)", "-$310"),
            ("Total annual premium", "$9,220"),
        ],
        "answer": {"document_type": "homeowners", "effective_date": "2026-07-15", "dwelling_limit": 900000,
                   "dwelling_settlement": "replacement_cost", "extended_replacement_pct": None,
                   "code_upgrade": True, "debris_removal": True, "premium_total": 9220},
    },
    "homeowners_well_covered.pdf": {
        "header": ["Golden Poppy Mutual Insurance (fictional)", "Homeowners Policy HO-3 - Declarations",
                   "SAMPLE - SYNTHETIC DOCUMENT FOR TESTING"],
        "lines": [
            ("Named insured", "Ana Placeholder"),
            ("Policy number", "GPM-HO3-990001"),
            ("Policy period", "Effective 2026-05-01 to 2027-05-01"),
            ("Residence premises", "Los Angeles, CA 90010"),
            ("", ""),
            ("Coverage A - Dwelling", "$1,400,000"),
            ("Extended replacement cost", "25% above Coverage A"),
            ("Coverage B - Other structures", "$140,000"),
            ("Coverage C - Personal property", "$700,000"),
            ("Coverage D - Loss of use", "$280,000"),
            ("Coverage E - Personal liability", "$1,000,000"),
            ("Loss settlement - Dwelling", "Replacement cost"),
            ("Building code upgrade (HO 04 77)", "25% of Coverage A"),
            ("Debris removal", "Additional 5% of Coverage A"),
            ("Deductible - all perils", "$5,000"),
            ("", ""),
            ("Total annual premium", "$4,210"),
        ],
        "answer": {"document_type": "homeowners", "effective_date": "2026-05-01", "dwelling_limit": 1400000,
                   "dwelling_settlement": "replacement_cost", "extended_replacement_pct": 25,
                   "code_upgrade": True, "debris_removal": True, "premium_total": 4210},
    },
}


def build(name: str, spec: dict) -> None:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    for i, line in enumerate(spec["header"]):
        pdf.set_font("Helvetica", "B" if i == 0 else "", 14 if i == 0 else 10)
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 10)
    for label, value in spec["lines"]:
        if not label:
            pdf.ln(3)
            continue
        pdf.cell(95, 7, label)
        pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(OUT / name))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in SAMPLES.items():
        build(name, spec)
    key = {name: spec["answer"] for name, spec in SAMPLES.items()}
    (OUT / "answer_key.json").write_text(json.dumps(key, indent=2))
    print(f"Wrote {len(SAMPLES)} PDFs and answer_key.json to {OUT}")


if __name__ == "__main__":
    main()
