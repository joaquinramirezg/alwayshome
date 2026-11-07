"""AlwaysON HTTP API for the hosted frontend (phase 2, see docs/DEPLOYMENT.md).

Same logic as the Streamlit app, exposed as JSON:
  GET  /api/health                         status, AI availability, which parts are real or placeholder
  GET  /api/samples                        sample homeowners and sample policy PDFs
  GET  /api/area?address=...               hazard zone, fire history, insurance market (area_context)
  POST /api/assess                         contract inputs -> contract output (docs/inputs_and_contract.md)
  POST /api/policy/extract                 upload 1-2 declarations PDFs -> fields with quotes + merged insurance
  GET  /api/policy/sample/{name}           same, for a bundled sample PDF (cached, works without a key)
  POST /api/report                         plan -> Markdown report (template, or AI rewrite when allowed)

Run locally:  uv run uvicorn api.main:app --reload --port 8000   (docs at http://localhost:8000/docs)
Env: ANTHROPIC_API_KEY (optional), ALLOWED_ORIGINS (comma-separated, for the frontend),
     AI_CALLS_PER_HOUR (per client IP, default 20).
"""
from __future__ import annotations

import json
import os
import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]

from msba_vibathon_2026.assess_stub import SOURCES, assess  # noqa: E402
from msba_vibathon_2026.contract import validate_inputs, validate_output  # noqa: E402
from msba_vibathon_2026.policy_extract import FIELDS, ExtractionUnavailable, extract, merge_policies  # noqa: E402
from msba_vibathon_2026.report import ai_report, template_report  # noqa: E402
from msba_vibathon_2026.scenarios import load_scenarios  # noqa: E402

SAMPLES = ROOT / "data" / "samples" / "policies"
AREA_CACHE = ROOT / "data" / "demo" / "area_cache.json"
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_FILES = 2

app = FastAPI(title="AlwaysON API", version="0.1.0",
              description="Fire-safety fixes and coverage gaps for California homeowners on the FAIR Plan.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ helpers
def ai_enabled() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


_ai_calls: dict[str, deque] = defaultdict(deque)


def check_ai_quota(request: Request) -> None:
    """Simple per-IP limit on paid AI calls, so a public URL can't run up the API bill."""
    limit = int(os.environ.get("AI_CALLS_PER_HOUR", "20"))
    ip = request.client.host if request.client else "unknown"
    q, now = _ai_calls[ip], time.time()
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, f"AI limit reached ({limit} per hour). Enter the values by hand instead.")
    q.append(now)


def _key(a: str) -> str:
    return " ".join(a.lower().split())


def load_area(address: str) -> dict:
    cache = json.loads(AREA_CACHE.read_text()) if AREA_CACHE.exists() else {}
    if _key(address) in cache:
        return cache[_key(address)]
    from utils import area_context  # needs network for the Census geocoder

    return json.loads(json.dumps(area_context(address), default=str))


def _extraction_payload(name: str, res: dict) -> dict:
    return {"file": name, "source": res["source"], "text_layer": res["text_layer"],
            "fields": [{"field": f, "label": label, "must_have": prio == 1, **res["fields"][f]}
                       for f, (label, prio) in FIELDS.items()]}


# ------------------------------------------------------------------ endpoints
@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "ai_enabled": ai_enabled(), "sources": SOURCES}


@app.get("/api/samples")
def samples() -> dict:
    return {"homeowners": load_scenarios(),
            "policies": sorted(p.name for p in SAMPLES.glob("*.pdf"))}


@app.get("/api/area")
def area(address: str) -> dict:
    if not address.strip():
        raise HTTPException(422, "address is empty")
    try:
        return load_area(address)
    except ValueError as e:  # geocoder found no match
        raise HTTPException(404, str(e)) from e
    except Exception as e:  # geocoder down
        raise HTTPException(503, f"Address lookup unavailable: {e}") from e


class AssessRequest(BaseModel):
    inputs: dict
    area: dict | None = None  # pass the /api/area result to skip a second lookup


@app.post("/api/assess")
def run_assess(req: AssessRequest) -> dict:
    errs = validate_inputs(req.inputs)
    if errs:
        raise HTTPException(422, {"input_errors": errs})
    area_data = req.area if req.area is not None else area(req.inputs["address"])
    out = assess(req.inputs, area_data)
    out_errs = validate_output(out)
    if out_errs:  # model returned a bad shape: fail loudly rather than show wrong numbers
        raise HTTPException(500, {"output_errors": out_errs})
    return out


@app.post("/api/policy/extract")
async def policy_extract(request: Request, files: list[UploadFile] = File(...)) -> dict:
    if not 1 <= len(files) <= MAX_FILES:
        raise HTTPException(422, f"Upload 1 or {MAX_FILES} PDFs (FAIR Plan, plus DIC if you have one).")
    if not ai_enabled():
        raise HTTPException(503, "AI policy reading is not configured. Enter the values by hand.")
    check_ai_quota(request)
    results = []
    for f in files:
        data = await f.read()  # kept in memory only, never written to disk
        if len(data) > MAX_PDF_BYTES:
            raise HTTPException(413, f"{f.filename} is larger than 10 MB.")
        if not data.startswith(b"%PDF"):
            raise HTTPException(415, f"{f.filename} is not a PDF.")
        try:
            results.append((f.filename, extract(data)))
        except ExtractionUnavailable as e:
            raise HTTPException(502, str(e)) from e
    return {"documents": [_extraction_payload(n, r) for n, r in results],
            "merged": merge_policies([r for _, r in results])}


@app.get("/api/policy/sample/{name}")
def policy_sample(name: str) -> dict:
    path = SAMPLES / name
    if path.suffix != ".pdf" or path.parent != SAMPLES or not path.exists():
        raise HTTPException(404, "unknown sample")
    try:
        res = extract(path.read_bytes())  # served from data/demo cache: no key needed
    except ExtractionUnavailable as e:
        raise HTTPException(503, str(e)) from e
    return {"documents": [_extraction_payload(name, res)], "merged": merge_policies([res])}


class ReportRequest(BaseModel):
    address: str
    result: dict
    ai: bool = False


@app.post("/api/report")
def report(req: ReportRequest, request: Request) -> dict:
    if req.ai and ai_enabled():
        check_ai_quota(request)
        text, source = ai_report(req.address, req.result)
    else:
        text, source = template_report(req.address, req.result), "template"
    return {"markdown": text, "source": source}
