"""HTTP API (api/main.py) used by the hosted frontend. No API key needed."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.main import app, _ai_calls
from msba_vibathon_2026.scenarios import load_scenarios, scenario_inputs

client = TestClient(app)
SCENARIOS = load_scenarios()


def test_health(no_key):
    r = client.get("/api/health").json()
    assert r["ok"] and r["ai_enabled"] is False and r["sources"]["wildfire"] == "real"


def test_samples_list():
    r = client.get("/api/samples").json()
    assert set(r["homeowners"]) == set(SCENARIOS) and "fair_plan_altadena.pdf" in r["policies"]


def test_area_demo_address_offline():
    r = client.get("/api/area", params={"address": "1000 E Mariposa St, Altadena, CA 91001"})
    assert r.status_code == 200 and r.json()["geocode"]["zip"] == "91001"
    assert r.json()["wildfire"]["score"] == 73.2


def test_area_empty_address():
    assert client.get("/api/area", params={"address": "  "}).status_code == 422


@pytest.mark.parametrize("sid", list(SCENARIOS))
def test_assess_every_sample(sid):
    r = client.post("/api/assess", json={"inputs": scenario_inputs(SCENARIOS[sid])})
    assert r.status_code == 200, r.text
    out = r.json()
    assert sorted(f["measure_id"] for f in out["future"]["fixes"]) == sorted(SCENARIOS[sid]["expect"]["fixes"])


def test_assess_rejects_bad_inputs():
    inputs = scenario_inputs(SCENARIOS["altadena_fair_only"])
    inputs["home"]["EAVES"] = "Open"
    r = client.post("/api/assess", json={"inputs": inputs})
    assert r.status_code == 422 and "EAVES" in str(r.json())


def test_sample_policy_from_cache(no_key, monkeypatch):
    from msba_vibathon_2026 import policy_extract
    monkeypatch.setattr(policy_extract, "DEMO_CACHE", policy_extract.ROOT / "data" / "demo" / "policy_extractions.json")
    r = client.get("/api/policy/sample/dic_altadena.pdf").json()
    assert r["documents"][0]["source"] == "cache" and r["merged"]["has_dic"] is True


def test_sample_policy_rejects_path_tricks():
    assert client.get("/api/policy/sample/..%2F..%2Fpyproject.toml").status_code == 404
    assert client.get("/api/policy/sample/answer_key.json").status_code == 404


def test_upload_needs_ai(no_key, pdf_bytes):
    files = [("files", ("p.pdf", pdf_bytes("fair_plan_altadena.pdf"), "application/pdf"))]
    assert client.post("/api/policy/extract", files=files).status_code == 503


def test_upload_with_fake_claude(fake_claude, pdf_bytes):
    _ai_calls.clear()
    files = [("files", ("fair.pdf", pdf_bytes("fair_plan_altadena.pdf"), "application/pdf")),
             ("files", ("dic.pdf", pdf_bytes("dic_altadena.pdf"), "application/pdf"))]
    r = client.post("/api/policy/extract", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["merged"]["premium_total"] == 6180 + 1450
    dl = next(f for f in body["documents"][0]["fields"] if f["field"] == "dwelling_limit")
    assert dl["value"] == 650000 and dl["verified"] is True and dl["must_have"] is True


def test_upload_rejects_non_pdf(fake_claude):
    _ai_calls.clear()
    r = client.post("/api/policy/extract", files=[("files", ("x.pdf", b"hello", "application/pdf"))])
    assert r.status_code == 415


def test_ai_quota(fake_claude, pdf_bytes, monkeypatch):
    _ai_calls.clear()
    monkeypatch.setenv("AI_CALLS_PER_HOUR", "1")
    files = [("files", ("p.pdf", pdf_bytes("fair_plan_altadena.pdf"), "application/pdf"))]
    assert client.post("/api/policy/extract", files=files).status_code == 200
    assert client.post("/api/policy/extract", files=files).status_code == 429


def test_report_template(no_key):
    out = client.post("/api/assess", json={"inputs": scenario_inputs(SCENARIOS["altadena_fair_only"])}).json()
    r = client.post("/api/report", json={"address": "x", "result": out, "ai": True}).json()
    assert r["source"] == "template" and r["markdown"].startswith("# Your AlwaysON plan")


def test_several_samples_merged(no_key, monkeypatch):
    from msba_vibathon_2026 import policy_extract
    monkeypatch.setattr(policy_extract, "DEMO_CACHE", policy_extract.ROOT / "data" / "demo" / "policy_extractions.json")
    r = client.get("/api/policy/samples", params=[("names", "fair_plan_altadena.pdf"), ("names", "dic_altadena.pdf")])
    assert r.status_code == 200 and r.json()["merged"]["premium_total"] == 6180 + 1450
    assert len(r.json()["documents"]) == 2


def test_quota_uses_forwarded_ip(fake_claude, pdf_bytes, monkeypatch):
    _ai_calls.clear()
    monkeypatch.setenv("AI_CALLS_PER_HOUR", "1")
    files = [("files", ("p.pdf", pdf_bytes("fair_plan_altadena.pdf"), "application/pdf"))]
    assert client.post("/api/policy/extract", files=files, headers={"x-forwarded-for": "1.1.1.1"}).status_code == 200
    assert client.post("/api/policy/extract", files=files, headers={"x-forwarded-for": "2.2.2.2"}).status_code == 200
    assert client.post("/api/policy/extract", files=files, headers={"x-forwarded-for": "1.1.1.1"}).status_code == 429
