"""Extract coverage fields from an insurance declarations-page PDF.

Follows docs/policy_extraction_spec.md. Approach:

1. An LLM reads the PDF natively (text layer and page images), so scanned pages work too.
   Provider-agnostic: Claude, OpenAI or Gemini via llm.py (LLM_PROVIDER / LLM_MODEL).
2. Structured outputs (`output_config.format` with a JSON schema) force valid JSON:
   every field is {value, source_text, page}, null when the page doesn't show it.
3. pdfplumber reads the PDF's text layer locally, and each `source_text` quote is
   checked against the page it claims to come from. Quotes that can't be found are
   flagged for the user, never silently trusted.
4. Plausibility checks from the spec null out impossible values and flag them.
5. The user confirms every value in the app before it is used.

PDFs are processed in memory and never written to disk. Results for the synthetic
sample PDFs are cached in data/demo/ so the demo runs without network or API key.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import re
from pathlib import Path

from .llm import LLMUnavailable, extract_json

ROOT = Path(__file__).resolve().parents[2]
DEMO_CACHE = ROOT / "data" / "demo" / "policy_extractions.json"


class ExtractionUnavailable(RuntimeError):
    """No cached result and no way to call the API (no key, or the call failed)."""


# ---------------------------------------------------------------- schema
def _nullable(t: dict) -> dict:
    return {"anyOf": [t, {"type": "null"}]}


NUM = _nullable({"type": "number"})
STR = _nullable({"type": "string"})
BOOL = _nullable({"type": "boolean"})
SETTLEMENT = _nullable({"type": "string", "enum": ["actual_cash_value", "replacement_cost", "unknown"]})
DOC_TYPE = {"type": "string", "enum": ["fair_plan", "dic", "homeowners", "dwelling_fire", "other"]}
ADDON = _nullable({
    "type": "object",
    "properties": {"covered": BOOL, "limit": NUM, "pct": NUM},
    "required": ["covered", "limit", "pct"],
    "additionalProperties": False,
})
PCT_OR_AMOUNT = _nullable({
    "type": "object",
    "properties": {"amount": NUM, "pct": NUM},
    "required": ["amount", "pct"],
    "additionalProperties": False,
})
NAMED_AMOUNTS = _nullable({
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"name": {"type": "string"}, "amount": NUM},
        "required": ["name", "amount"],
        "additionalProperties": False,
    },
})
STR_LIST = _nullable({"type": "array", "items": {"type": "string"}})

# field -> (value schema, label shown in the app, priority 1 must / 2 should)
FIELDS: dict[str, tuple[dict, str, int]] = {
    "document_type": (_nullable(DOC_TYPE), "Document type", 1),
    "insurer_name": (STR, "Insurer", 2),
    "effective_date": (STR, "Effective date (YYYY-MM-DD)", 1),
    "dwelling_limit": (NUM, "Dwelling limit (Coverage A)", 1),
    "other_structures_limit": (NUM, "Other structures (Coverage B)", 2),
    "contents_limit": (NUM, "Contents (Coverage C)", 2),
    "loss_of_use_limit": (NUM, "Loss of use (Coverage D)", 2),
    "liability_limit": (NUM, "Personal liability (Coverage E)", 2),
    "dwelling_settlement": (SETTLEMENT, "How the dwelling is paid", 1),
    "extended_replacement_pct": (NUM, "Extended replacement cost %", 1),
    "code_upgrade": (ADDON, "Building code upgrade (ordinance or law)", 1),
    "debris_removal": (ADDON, "Debris removal", 1),
    "deductible_all_perils": (NUM, "Deductible (all perils)", 2),
    "deductible_wildfire": (PCT_OR_AMOUNT, "Wildfire deductible", 2),
    "premium_total": (NUM, "Total annual premium", 1),
    "discounts_listed": (NAMED_AMOUNTS, "Discounts listed", 2),
    "dic_covers": (STR_LIST, "What the DIC policy adds", 2),
}


def _field_schema(value_schema: dict) -> dict:
    return {
        "type": "object",
        "properties": {"value": value_schema, "source_text": STR, "page": _nullable({"type": "integer"})},
        "required": ["value", "source_text", "page"],
        "additionalProperties": False,
    }


SCHEMA = {
    "type": "object",
    "properties": {name: _field_schema(s) for name, (s, _, _) in FIELDS.items()},
    "required": list(FIELDS),
    "additionalProperties": False,
}

SYSTEM = """You extract fields from a homeowner's insurance declarations page for a coverage review.

Rules:
- For every field return value, source_text and page. source_text is the exact words copied from the PDF that show the value (one line or phrase, verbatim). page is 1-indexed.
- If a field is not on the page, return null for value, source_text and page. Never infer, estimate or calculate a value.
- Dollar amounts are plain numbers (650000, not "$650,000"). Percentages are numbers (25 for 25%).
- For coverages B, C and D on FAIR Plan pages: null if missing; 0 only if the page explicitly says not covered, not purchased or excluded.
- For add-ons (code_upgrade, debris_removal): covered true if listed, false if marked declined or excluded, null if not mentioned. Fill limit or pct only if printed.
- document_type: fair_plan for the California FAIR Plan, dic for a difference-in-conditions / supplemental policy, homeowners for HO-3 style policies, dwelling_fire for DP forms.
- dic_covers only for DIC policies: short names of the perils or coverages it adds (e.g. theft, liability, water damage, loss of use).
- Do not extract personal data: names of insured people, policy numbers, mortgage companies, phone numbers or emails. Never put them in source_text either; if the only evidence line contains personal data, quote just the part with the value."""


# ---------------------------------------------------------------- helpers
def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9%$.]+", " ", s.lower()).strip()


def page_texts(pdf_bytes: bytes) -> list[str]:
    """Text layer per page via pdfplumber (empty strings for scanned pages)."""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def verify_quotes(fields: dict, pages: list[str]) -> dict:
    """Mark each field verified if its source_text appears on the cited page (or any page)."""
    normed = [_norm(t) for t in pages]
    has_text = any(normed)
    for f in fields.values():
        quote = f.get("source_text")
        if f.get("value") is None or not quote:
            f["verified"] = None
            continue
        if not has_text:
            f["verified"] = None  # scanned PDF: nothing to check against
            continue
        q = _norm(quote)
        page = f.get("page")
        on_page = page and 1 <= page <= len(normed) and q in normed[page - 1]
        f["verified"] = bool(on_page or any(q in t for t in normed))
    return fields


def plausibility(fields: dict) -> dict:
    """Spec checks: impossible values become null and get a flag."""
    def fail(name, why):
        fields[name]["flag"] = f"{why} (was {fields[name]['value']!r})"
        fields[name]["value"] = None

    dw = fields["dwelling_limit"]["value"]
    if dw is not None and not 50_000 <= dw <= 10_000_000:
        fail("dwelling_limit", "Outside $50k to $10M")
        dw = None
    ded = fields["deductible_all_perils"]["value"]
    if ded is not None and dw is not None and ded >= dw:
        fail("deductible_all_perils", "Deductible not below dwelling limit")
    prem = fields["premium_total"]["value"]
    if prem is not None and prem <= 0:
        fail("premium_total", "Premium must be above 0")
    return fields


def _load_cache() -> dict:
    return json.loads(DEMO_CACHE.read_text()) if DEMO_CACHE.exists() else {}


# ---------------------------------------------------------------- public API
def extract(pdf_bytes: bytes, *, write_cache: bool = False) -> dict:
    """Return {"fields": {...}, "source": "cache" | "<provider>/<model>", "text_layer": bool}.

    Each field: value, source_text, page, verified (True/False/None), optional flag.
    Raises ExtractionUnavailable when there is no cached result and the API can't be used.
    """
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    cache = _load_cache()
    if digest in cache:
        raw, source = copy.deepcopy(cache[digest]), "cache"
    else:
        try:
            raw, source = extract_json(pdf_bytes, SYSTEM, "Extract the fields from this declarations page.", SCHEMA)
        except LLMUnavailable as e:
            raise ExtractionUnavailable(str(e)) from e
        if write_cache:
            cache[digest] = raw
            DEMO_CACHE.parent.mkdir(parents=True, exist_ok=True)
            DEMO_CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True))

    pages = page_texts(pdf_bytes)
    fields = plausibility(verify_quotes(raw, pages))
    return {"fields": fields, "source": source, "text_layer": any(t.strip() for t in pages)}


def merge_policies(extractions: list[dict]) -> dict:
    """Combine a FAIR Plan and a DIC extraction into one flat insurance dict for the gap rules."""
    out: dict = {"documents": []}
    for ex in extractions:
        f = {k: v.get("value") for k, v in ex["fields"].items()}
        out["documents"].append(f.get("document_type"))
        if f.get("document_type") == "dic":
            out["has_dic"] = True
            out["dic_covers"] = f.get("dic_covers") or []
            out["dic_premium"] = f.get("premium_total")
            for k in ("liability_limit", "loss_of_use_limit", "contents_limit"):
                if f.get(k) is not None and out.get(k) is None:
                    out[k] = f[k]
            continue
        for k, v in f.items():
            if v is not None and out.get(k) is None:
                out[k] = v
    out["has_dic"] = out.get("has_dic", False)
    out["premium_total"] = (out.get("premium_total") or 0) + (out.get("dic_premium") or 0) or None
    return out
