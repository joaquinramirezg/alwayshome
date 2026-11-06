"""Shared fixtures. `fake_claude` stands in for the Claude API so the AI path is tested without a key.

The fake answers are built from the sample PDFs' answer key and the exact lines printed on each PDF,
so they look like what a correct model would return. They are test fixtures, not AI output.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from make_sample_policies import SAMPLES as PDF_SPECS
from msba_vibathon_2026 import policy_extract

ROOT = Path(__file__).resolve().parents[1]
PDFS = ROOT / "data" / "samples" / "policies"
ANSWERS = json.loads((PDFS / "answer_key.json").read_text())

# field -> label text to find the evidence line on the sample PDF
LABELS = {
    "effective_date": "Policy period",
    "dwelling_limit": "Coverage A",
    "dwelling_settlement": "Loss settlement",
    "extended_replacement_pct": "Extended replacement",
    "code_upgrade": ("Ordinance", "code upgrade"),
    "debris_removal": "Debris removal",
    "premium_total": "Total annual premium",
}


def _spec(name):
    spec = PDF_SPECS[name]
    return PDF_SPECS[spec["copy_of"]] if spec.get("copy_of") else spec


def _evidence(name, field):
    spec = _spec(name)
    labels = LABELS[field] if isinstance(LABELS[field], tuple) else (LABELS[field],)
    for page, lines in ((1, spec["lines"]), (2, spec.get("page2", []))):
        for label, value in lines:
            if any(l.lower() in label.lower() for l in labels):
                return f"{label} {value}", page
    return None, None


def fake_response(name: str) -> dict:
    """What a correct model would return for one sample PDF."""
    answer = ANSWERS[name]
    out = {f: {"value": None, "source_text": None, "page": None} for f in policy_extract.FIELDS}
    spec = _spec(name)
    out["document_type"] = {"value": answer["document_type"], "source_text": spec["header"][1], "page": 1}
    for field, value in answer.items():
        if field == "document_type" or value is None:
            continue
        quote, page = _evidence(name, field)
        if field in ("code_upgrade", "debris_removal"):
            value = {"covered": value, "limit": None, "pct": None}
        out[field] = {"value": value, "source_text": quote, "page": page}
    return out


@pytest.fixture
def pdf_bytes():
    return lambda name: (PDFS / name).read_bytes()


@pytest.fixture
def tmp_cache(tmp_path, monkeypatch):
    """Point the extraction cache at an empty temp file so tests never touch data/demo/."""
    path = tmp_path / "policy_extractions.json"
    monkeypatch.setattr(policy_extract, "DEMO_CACHE", path)
    return path


@pytest.fixture
def fake_claude(monkeypatch, tmp_cache):
    """Replace the Claude call with answers keyed by the PDF's hash; records how often it was called."""
    by_hash = {hashlib.sha256((PDFS / n).read_bytes()).hexdigest(): n for n in ANSWERS}
    calls = []

    def _fake(pdf: bytes) -> dict:
        name = by_hash[hashlib.sha256(pdf).hexdigest()]
        calls.append(name)
        return fake_response(name)

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-not-real")
    monkeypatch.setattr(policy_extract, "_call_claude", _fake)
    return calls


@pytest.fixture
def no_key(monkeypatch, tmp_cache):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
