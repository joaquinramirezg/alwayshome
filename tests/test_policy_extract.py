"""Policy PDF reading: quote checks, plausibility, caching, fallbacks, merging. No API key needed."""
from __future__ import annotations

import copy
import json

import pytest

from conftest import ANSWERS, fake_response
from msba_vibathon_2026 import policy_extract
from msba_vibathon_2026.policy_extract import ExtractionUnavailable, extract, merge_policies, page_texts


def value(res, field):
    v = res["fields"][field]["value"]
    return v["covered"] if isinstance(v, dict) and "covered" in v else v


# ---------------------------------------------------------------- sample PDFs
@pytest.mark.parametrize("name", list(ANSWERS))
def test_sample_pdf_opens(pdf_bytes, name):
    pages = page_texts(pdf_bytes(name))
    assert pages, name
    if name == "fair_plan_scanned.pdf":
        assert not any(p.strip() for p in pages), "scanned sample must have no text layer"
    else:
        assert any(p.strip() for p in pages)


def test_two_page_sample_has_coverage_on_page_2(pdf_bytes):
    pages = page_texts(pdf_bytes("homeowners_two_page.pdf"))
    assert len(pages) == 2 and "Coverage A" in pages[1] and "Coverage A" not in pages[0]


# ---------------------------------------------------------------- full extraction path (fake Claude)
@pytest.mark.parametrize("name", list(ANSWERS))
def test_extract_matches_answer_key(fake_claude, pdf_bytes, name):
    res = extract(pdf_bytes(name))
    for field, expected in ANSWERS[name].items():
        assert value(res, field) == expected, f"{name}:{field}"
    assert res["source"] == "claude"


@pytest.mark.parametrize("name", [n for n in ANSWERS if n != "fair_plan_scanned.pdf"])
def test_correct_quotes_are_verified(fake_claude, pdf_bytes, name):
    res = extract(pdf_bytes(name))
    for field, f in res["fields"].items():
        if f["value"] is not None and f["source_text"]:
            assert f["verified"] is True, f"{name}:{field} quote {f['source_text']!r} not found"


def test_scanned_pdf_quotes_cannot_be_checked(fake_claude, pdf_bytes):
    res = extract(pdf_bytes("fair_plan_scanned.pdf"))
    assert res["text_layer"] is False
    assert all(f["verified"] is None for f in res["fields"].values())


def test_invented_quote_is_flagged(fake_claude, pdf_bytes, monkeypatch):
    bad = fake_response("fair_plan_altadena.pdf")
    bad["dwelling_limit"]["source_text"] = "Coverage A - Dwelling $750,000"  # not on the page
    monkeypatch.setattr(policy_extract, "_call_claude", lambda pdf: copy.deepcopy(bad))
    res = extract(pdf_bytes("fair_plan_altadena.pdf"))
    assert res["fields"]["dwelling_limit"]["verified"] is False


def test_quote_on_wrong_page_still_found(fake_claude, pdf_bytes, monkeypatch):
    r = fake_response("homeowners_two_page.pdf")
    r["dwelling_limit"]["page"] = 1  # really on page 2
    monkeypatch.setattr(policy_extract, "_call_claude", lambda pdf: copy.deepcopy(r))
    res = extract(pdf_bytes("homeowners_two_page.pdf"))
    assert res["fields"]["dwelling_limit"]["verified"] is True


@pytest.mark.parametrize("field,bad,expect_flag", [
    ("dwelling_limit", 5_000, "Outside $50k to $10M"),
    ("dwelling_limit", 50_000_000, "Outside $50k to $10M"),
    ("premium_total", 0, "Premium must be above 0"),
])
def test_implausible_values_are_nulled_and_flagged(fake_claude, pdf_bytes, monkeypatch, field, bad, expect_flag):
    r = fake_response("fair_plan_altadena.pdf")
    r[field]["value"] = bad
    monkeypatch.setattr(policy_extract, "_call_claude", lambda pdf: copy.deepcopy(r))
    res = extract(pdf_bytes("fair_plan_altadena.pdf"))
    assert res["fields"][field]["value"] is None
    assert expect_flag in res["fields"][field]["flag"]


def test_deductible_above_limit_is_flagged(fake_claude, pdf_bytes, monkeypatch):
    r = fake_response("fair_plan_altadena.pdf")
    r["deductible_all_perils"] = {"value": 900_000, "source_text": None, "page": None}
    monkeypatch.setattr(policy_extract, "_call_claude", lambda pdf: copy.deepcopy(r))
    res = extract(pdf_bytes("fair_plan_altadena.pdf"))
    assert res["fields"]["deductible_all_perils"]["value"] is None


def test_no_personal_data_fields_in_schema():
    banned = {"insured_name", "named_insured", "policy_number", "mortgagee", "phone", "email"}
    assert not banned & set(policy_extract.FIELDS)
    assert not banned & set(policy_extract.SCHEMA["properties"])
    assert policy_extract.SCHEMA["additionalProperties"] is False


def test_schema_has_no_union_types():
    """The API rejects schemas with more than 16 nullable/union parameters; we use none."""
    s = json.dumps(policy_extract.SCHEMA)
    assert "anyOf" not in s and '"null"' not in s and '"type": [' not in s


def _flat(**over):
    raw = {k: (0 if v.get("type") == "number" else [] if v.get("type") == "array" else "")
           for k, v in policy_extract.SCHEMA["properties"].items()}
    raw.update(document_type="other", dwelling_settlement="unknown", code_upgrade="not_mentioned",
               debris_removal="not_mentioned", not_found=[], evidence=[])
    raw.update(over)
    return raw


def test_normalize_maps_placeholders_to_nulls():
    raw = _flat(
        document_type="homeowners", dwelling_limit=650000, contents_limit=0,
        code_upgrade="excluded", debris_removal="covered", deductible_wildfire_pct=2, dwelling_settlement="unknown",
        not_found=["premium_total", "insurer_name"],
        evidence=[{"field": "dwelling_limit", "quote": "Coverage A - Dwelling $650,000", "page": 1},
                  {"field": "contents_limit", "quote": "Coverage C Not purchased", "page": 1}],
    )
    n = policy_extract.normalize(raw)
    assert set(n) == set(policy_extract.FIELDS)
    assert n["dwelling_limit"] == {"value": 650000, "source_text": "Coverage A - Dwelling $650,000", "page": 1}
    assert n["contents_limit"]["value"] == 0, "explicit 'not purchased' stays 0"
    assert n["premium_total"] == {"value": None, "source_text": None, "page": None}
    assert n["insurer_name"]["value"] is None
    assert n["code_upgrade"]["value"] == {"covered": False, "limit": None, "pct": None}
    assert n["debris_removal"]["value"] == {"covered": True, "limit": None, "pct": None}
    assert n["deductible_wildfire"]["value"] == {"amount": None, "pct": 2}
    assert n["dwelling_settlement"]["value"] is None
    assert n["dic_covers"]["value"] is None


# ---------------------------------------------------------------- cache and fallbacks
def test_no_key_and_no_cache_raises(no_key, pdf_bytes):
    with pytest.raises(ExtractionUnavailable):
        extract(pdf_bytes("fair_plan_altadena.pdf"))


def test_api_error_becomes_extraction_unavailable(fake_claude, pdf_bytes, monkeypatch):
    def boom(pdf):
        raise ConnectionError("network down")
    monkeypatch.setattr(policy_extract, "_call_claude", boom)
    with pytest.raises(ExtractionUnavailable, match="network down"):
        extract(pdf_bytes("fair_plan_altadena.pdf"))


def test_write_cache_then_read_offline(fake_claude, pdf_bytes, tmp_cache, monkeypatch):
    extract(pdf_bytes("dic_altadena.pdf"), write_cache=True)
    assert tmp_cache.exists() and len(json.loads(tmp_cache.read_text())) == 1
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    res = extract(pdf_bytes("dic_altadena.pdf"))
    assert res["source"] == "cache" and value(res, "premium_total") == 1450
    assert fake_claude == ["dic_altadena.pdf"], "second read must come from the cache"


def test_uploads_are_not_cached_by_default(fake_claude, pdf_bytes, tmp_cache):
    extract(pdf_bytes("fair_plan_altadena.pdf"))
    assert not tmp_cache.exists()


# ---------------------------------------------------------------- merging FAIR Plan + DIC
def test_merge_fair_and_dic(fake_claude, pdf_bytes):
    fair = extract(pdf_bytes("fair_plan_altadena.pdf"))
    dic = extract(pdf_bytes("dic_altadena.pdf"))
    m = merge_policies([fair, dic])
    assert m["has_dic"] is True
    assert m["documents"] == ["fair_plan", "dic"]
    assert m["dwelling_limit"] == 650_000
    assert m["dwelling_settlement"] == "actual_cash_value", "dwelling terms come from the FAIR Plan, not the DIC"
    assert m["premium_total"] == 6180 + 1450


def test_merge_single_private_policy(fake_claude, pdf_bytes):
    m = merge_policies([extract(pdf_bytes("homeowners_well_covered.pdf"))])
    assert m["has_dic"] is False and m["extended_replacement_pct"] == 25 and m["premium_total"] == 4210


# ---------------------------------------------------------------- committed demo results
@pytest.mark.parametrize("name", list(ANSWERS))
def test_demo_cache_reads_every_sample_offline(name, pdf_bytes, monkeypatch):
    """data/demo/policy_extractions.json (real Claude output) must cover every sample PDF, so the demo needs no key.
    Fails if the sample PDFs were regenerated with different bytes: rerun eval_policy_extraction.py --refresh."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    res = extract(pdf_bytes(name))
    assert res["source"] == "cache"
    for field, expected in ANSWERS[name].items():
        assert value(res, field) == expected, f"{name}:{field}"
