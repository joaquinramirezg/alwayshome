"""Score policy extraction on the synthetic sample PDFs against the answer key.

Run: uv run python scripts/eval_policy_extraction.py            (uses cached results, or the API if a key is set)
     uv run python scripts/eval_policy_extraction.py --refresh  (calls the API and saves results to data/demo/
                                                                  so the demo works offline; needs ANTHROPIC_API_KEY)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from msba_vibathon_2026 import policy_extract  # noqa: E402

SAMPLES = ROOT / "data" / "samples" / "policies"


def comparable(field: str, value):
    """Answer key stores add-ons as covered true/false; dates as YYYY-MM-DD."""
    if isinstance(value, dict) and "covered" in value:
        return value["covered"]
    return value


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="ignore the cache, call the API, save new results")
    args = ap.parse_args()

    key = json.loads((SAMPLES / "answer_key.json").read_text())
    if args.refresh and policy_extract.DEMO_CACHE.exists():
        cache = json.loads(policy_extract.DEMO_CACHE.read_text())
        for name in key:
            cache.pop(hashlib.sha256((SAMPLES / name).read_bytes()).hexdigest(), None)
        policy_extract.DEMO_CACHE.write_text(json.dumps(cache, indent=2, sort_keys=True))

    right = total = 0
    unverified = []
    for name, expected in key.items():
        try:
            res = policy_extract.extract((SAMPLES / name).read_bytes(), write_cache=args.refresh)
        except policy_extract.ExtractionUnavailable as e:
            print(f"SKIP  {name}: {e}")
            continue
        print(f"\n{name}  (source: {res['source']})")
        for field, want in expected.items():
            got = comparable(field, res["fields"][field]["value"])
            ok = got == want
            right += ok
            total += 1
            print(f"  {'ok  ' if ok else 'MISS'}  {field:26} expected={want!r:22} got={got!r}")
        unverified += [f"{name}:{f}" for f, v in res["fields"].items() if v.get("verified") is False]

    if total:
        print(f"\nMust-have field accuracy: {right}/{total} = {right / total:.0%}")
        print(f"Quotes not found on the page: {len(unverified)} {unverified if unverified else ''}")
    else:
        print("\nNothing scored: set ANTHROPIC_API_KEY and run with --refresh once.")


if __name__ == "__main__":
    main()
