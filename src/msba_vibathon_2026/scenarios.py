"""Sample homeowners (data/samples/scenarios.json) turned into assess() inputs, plus cached area data."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_FILE = ROOT / "data" / "samples" / "scenarios.json"
AREA_CACHE = ROOT / "data" / "demo" / "area_cache.json"

INS_DOCS = {"FAIR Plan only": ["fair_plan"], "FAIR Plan + DIC policy": ["fair_plan", "dic"],
            "Private homeowners": ["homeowners"]}


def load_scenarios() -> dict:
    return json.loads(SCENARIOS_FILE.read_text())


def cached_area(address: str) -> dict:
    cache = json.loads(AREA_CACHE.read_text())
    return cache[" ".join(address.lower().split())]


def scenario_inputs(s: dict) -> dict:
    ins = dict(s["insurance"])
    kind = ins.pop("type")
    return {
        "address": s["address"],
        "home": dict(s["home"]),
        "measures_done": list(s["measures_done"]),
        "insurance": {"documents": INS_DOCS[kind], "has_dic": kind == "FAIR Plan + DIC policy", **ins},
        "budget": s["budget"],
    }
