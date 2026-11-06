"""Extract coverage fields from an insurance declarations-page PDF.

Follows docs/policy_extraction_spec.md. Approach:

1. Claude reads the PDF natively (text layer and page images), so scanned pages work too.
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
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO_CACHE = ROOT / "data" / "demo" / "policy_extractions.json"
MODEL = "claude-opus-5-5"


class ExtractionUnavailable(RuntimeError):
    """No cached result and no way to call the API (no key, or the call failed)."""


# ---------------------------------------------------------------- schema
# Kept flat and small on purpose: the API limits structured-output schemas (at most 16
# nullable parameters, and a maximum compiled size). So nothing is nullable: the model
# lists missing fields in `not_found`, puts placeholders in their slots, and cites each
# value once in `evidence`. `normalize()` turns that into {value, source_text, page}.
NUM = {"type": "number"}
STR = {"type": "string"}
ADDON_STATUS = {"type": "string", "enum": ["covered", "excluded", "not_mentioned"]}

# field -> (label shown in the app, priority 1 must / 2 should)
FIELDS: dict[str, tuple[str, int]] = {
    "document_type": ("Document type", 1),
    "insurer_name": ("Insurer", 2),
    "effective_date": ("Effective date (YYYY-MM-DD)", 1),
    "dwelling_limit": ("Dwelling limit (Coverage A)", 1),
    "other_structures_limit": ("Other structures (Coverage B)", 2),
    "contents_limit": ("Contents (Coverage C)", 2),
    "loss_of_use_limit": ("Loss of use (Coverage D)", 2),
    "liability_limit": ("Personal liability (Coverage E)", 2),
    "dwelling_settlement": ("How the dwelling is paid", 1),
    "extended_replacement_pct": ("Extended replacement cost %", 1),
    "code_upgrade": ("Building code upgrade (ordinance or law)", 1),
    "debris_removal": ("Debris removal", 1),
    "deductible_all_perils": ("Deductible (all perils)", 2),
    "deductible_wildfire": ("Wildfire deductible", 2),
    "premium_total": ("Total annual premium", 1),
    "discounts_listed": ("Discounts listed", 2),
    "dic_covers": ("What the DIC policy adds", 2),
}

_PROPS = {
    "document_type": {"type": "string", "enum": ["fair_plan", "dic", "homeowners", "dwelling_fire", "other"]},
    "insurer_name": STR,
    "effective_date": STR,
    "dwelling_limit": NUM,
    "other_structures_limit": NUM,
    "contents_limit": NUM,
    "loss_of_use_limit": NUM,
    "liability_limit": NUM,
    "dwelling_settlement": {"type": "string", "enum": ["actual_cash_value", "replacement_cost", "unknown"]},
    "extended_replacement_pct": NUM,
    "code_upgrade": ADDON_STATUS,
    "code_upgrade_pct": NUM,
    "debris_removal": ADDON_STATUS,
    "deductible_all_perils": NUM,
    "deductible_wildfire_amount": NUM,
    "deductible_wildfire_pct": NUM,
    "premium_total": NUM,
    "discounts_listed": {"type": "array", "items": {"type": "object", "properties": {"name": STR, "amount": NUM},
                                                    "required": ["name", "amount"], "additionalProperties": False}},
    "dic_covers": {"type": "array", "items": STR},
    "not_found": {"type": "array", "items": STR},
    "evidence": {"type": "array", "items": {"type": "object", "properties": {"field": STR, "quote": STR, "page": {"type": "integer"}},
                                            "required": ["field", "quote", "page"], "additionalProperties": False}},
}
SCHEMA = {"type": "object", "properties": _PROPS, "required": list(_PROPS), "additionalProperties": False}

SYSTEM = """You extract fields from a homeowner's insurance declarations page for a coverage review.

Fields: """ + ", ".join(FIELDS) + """.

Rules:
- Fill every property. If a field is not on the page, add its name to not_found and put a placeholder in its slot (0, "", "unknown", "other", "not_mentioned" or []). Never infer, estimate or calculate a value.
- evidence: one entry per field you found, with field (the field name), quote (the exact words copied from the PDF that show the value, verbatim, one line or phrase) and page (1-indexed).
- Dollar amounts are plain numbers (650000, not "$650,000"). Percentages are numbers (25 for 25%). Dates as YYYY-MM-DD.
- Coverages B, C and D: in not_found if missing; value 0 (found) only if the page explicitly says not covered, not purchased or excluded.
- code_upgrade and debris_removal: covered if listed, excluded if marked declined, not included or excluded, not_mentioned otherwise. code_upgrade_pct only if printed, else 0.
- deductible_wildfire: deductible_wildfire_amount and deductible_wildfire_pct as printed, 0 for whichever is not printed.
- discounts_listed: every discount or credit line, amount as a positive number.
- document_type: fair_plan for the California FAIR Plan, dic for a difference-in-conditions / supplemental policy, homeowners for HO-3 style policies, dwelling_fire for DP forms, other for anything that is not a declarations page.
- dic_covers only for DIC policies: short names of the perils or coverages it adds (e.g. theft, liability, water damage, loss of use).
- Do not extract personal data: names of insured people, policy numbers, mortgage companies, phone numbers or emails. Never put them in a quote either; if the only evidence line contains personal data, quote just the part with the value."""


def normalize(raw: dict) -> dict:
    """Flat model output -> internal shape: {field: {value, source_text, page}}, nulls when not found."""
    missing = set(raw.get("not_found") or [])
    evidence = {}
    for e in raw.get("evidence") or []:
        evidence.setdefault(e.get("field"), e)
    out = {}
    for name in FIELDS:
        if name in missing:
            out[name] = {"value": None, "source_text": None, "page": None}
            continue
        if name in ("code_upgrade", "debris_removal"):
            status = raw.get(name)
            pct = raw.get("code_upgrade_pct") or None if name == "code_upgrade" else None
            v = None if status in (None, "not_mentioned") else {"covered": status == "covered", "limit": None, "pct": pct}
        elif name == "deductible_wildfire":
            amount, pct = raw.get("deductible_wildfire_amount") or None, raw.get("deductible_wildfire_pct") or None
            v = {"amount": amount, "pct": pct} if (amount or pct) else None
        else:
            v = raw.get(name)
            if (name == "dwelling_settlement" and v == "unknown") or (isinstance(v, (list, str)) and not v):
                v = None
        e = evidence.get(name, {})
        out[name] = {"value": v, "source_text": e.get("quote") or None, "page": e.get("page") or None}
    return out


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


def _call_claude(pdf_bytes: bytes) -> dict:
    import base64

    import anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {
                    "type": "base64", "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode()}},
                {"type": "text", "text": "Extract the fields from this declarations page."},
            ],
        }],
    )
    if response.stop_reason == "refusal":
        raise ExtractionUnavailable("The model declined to read this document.")
    if response.stop_reason == "max_tokens":
        raise ExtractionUnavailable("The response was cut off.")
    text = next(b.text for b in response.content if b.type == "text")
    return normalize(json.loads(text))


# ---------------------------------------------------------------- public API
def extract(pdf_bytes: bytes, *, write_cache: bool = False) -> dict:
    """Return {"fields": {...}, "source": "cache" | "claude", "text_layer": bool}.

    Each field: value, source_text, page, verified (True/False/None), optional flag.
    Raises ExtractionUnavailable when there is no cached result and the API can't be used.
    """
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    cache = _load_cache()
    if digest in cache:
        raw, source = copy.deepcopy(cache[digest]), "cache"
    else:
        if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("ANTHROPIC_AUTH_TOKEN"):
            raise ExtractionUnavailable("No ANTHROPIC_API_KEY set and this PDF is not one of the cached samples.")
        try:
            raw = _call_claude(pdf_bytes)
        except ExtractionUnavailable:
            raise
        except Exception as e:  # network, auth, rate limit: the app falls back to manual entry
            raise ExtractionUnavailable(f"AI extraction failed: {e}") from e
        source = "claude"
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
