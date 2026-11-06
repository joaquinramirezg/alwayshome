"""Click through the whole Streamlit app without a browser and fail on any error.

Run: uv run python scripts/smoke_test.py
Checks every demo address, every sample policy set and the plan screen.
Needs no API key: without one, reading a policy must show an error message, not crash.
"""
from __future__ import annotations

import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def button(at, label):
    return next(b for b in at.button if b.label == label)


def check(at, step: str) -> None:
    if at.exception:
        print(f"FAIL  {step}: {at.exception[0].value}")
        sys.exit(1)
    print(f"ok    {step}")


def main() -> None:
    at = AppTest.from_file(APP, default_timeout=180).run()
    check(at, "app loads")

    addresses = [o for o in at.selectbox[0].options if o != "-"]
    for a in addresses:
        at.selectbox[0].set_value(a).run()
        zone = next(m.value for m in at.metric if m.label == "Fire hazard zone")
        check(at, f"address: {a} (zone: {zone})")

    sample_box = next(s for s in at.selectbox if s.label == "Or use a sample policy")
    for name in [o for o in sample_box.options if o != "-"]:
        sample_box.set_value(name).run()
        button(at, "Read policy").click().run()
        outcome = "read" if not at.error else "fallback message shown (no key and no cached result)"
        check(at, f"policy: {name} -> {outcome}")
        sample_box = next(s for s in at.selectbox if s.label == "Or use a sample policy")

    button(at, "Show my plan").click().run()
    check(at, "plan screen")
    print("metrics:", {m.label: m.value for m in at.metric if m.label in (
        "Wildfire likelihood (per year)", "Damage if fire reaches the house", "After your plan")})
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
