"""AlwaysON - Streamlit prototype.

Run: uv run streamlit run app.py
Optional: export ANTHROPIC_API_KEY=... to read new policy PDFs (sample PDFs are cached).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from msba_vibathon_2026.assess_stub import MEASURES, assess  # noqa: E402
from msba_vibathon_2026.policy_extract import FIELDS, ExtractionUnavailable, extract, merge_policies  # noqa: E402

AREA_CACHE = ROOT / "data" / "demo" / "area_cache.json"
SAMPLES = ROOT / "data" / "samples" / "policies"
DEMO_ADDRESSES = [
    "1200 Chautauqua Blvd, Pacific Palisades, CA 90272",
    "1000 E Mariposa St, Altadena, CA 91001",
    "3200 Wilshire Blvd, Los Angeles, CA 90010",
]
SAMPLE_SETS = {
    "FAIR Plan + DIC (Altadena)": ["fair_plan_altadena.pdf", "dic_altadena.pdf"],
    "FAIR Plan only (Altadena)": ["fair_plan_altadena.pdf"],
    "Private HO-3, underinsured (Palisades)": ["homeowners_palisades_underinsured.pdf"],
    "Private HO-3, well covered (Wilshire)": ["homeowners_well_covered.pdf"],
}

# DINS answer options (docs/inputs_and_contract.md)
HOME_QUESTIONS = {
    "ROOFCONSTRUCTION": ("Roof material", ["Asphalt", "Tile", "Metal", "Concrete", "Wood", "Other"]),
    "EAVES": ("Eaves", ["Enclosed", "Unenclosed", "No Eaves"]),
    "VENTSCREEN": ("Vent screens", ['Mesh Screen <= 1/8"', 'Mesh Screen > 1/8"', "Unscreened", "No Vents"]),
    "EXTERIORSIDING": ("Exterior siding", ["Stucco/Brick/Cement", "Wood", "Vinyl", "Metal", "Other"]),
    "WINDOWPANE": ("Windows", ["Multi Pane", "Single Pane"]),
    "DECKPORCHELEVATED": ("Elevated deck", ["No Deck/Porch", "Wood", "Composite", "Masonry/Concrete"]),
    "FENCEATTACHEDTOSTRUCTURE": ("Fence attached to the house", ["No Fence", "Combustible", "Non Combustible"]),
    "UTILITYMISCSTRUCTUREDISTANCE": ("Sheds or outbuildings", ["Not Applicable", "<30'", "30-50'", ">50'"]),
}
EXTRA_MEASURES = {
    "defensible_space": "Defensible space done (trees trimmed, brush cleared)",
    "ember_zone_5ft": "5-foot zone around the house is free of combustibles",
    "noncombustible_6in_walls": "Bottom 6 inches of walls are noncombustible",
    "clear_under_decks": "Nothing stored or growing under decks",
}

st.set_page_config(page_title="AlwaysON", page_icon="🔥", layout="wide")


# ------------------------------------------------------------------ data helpers
def _key(a: str) -> str:
    return " ".join(a.lower().split())


@st.cache_data(show_spinner=False)
def load_area(address: str) -> dict:
    cache = json.loads(AREA_CACHE.read_text()) if AREA_CACHE.exists() else {}
    if _key(address) in cache:
        return cache[_key(address)]
    from utils import area_context  # David's helper, needs network for geocoding

    return json.loads(json.dumps(area_context(address), default=str))


def fmt_money(x) -> str:
    return "n/a" if x is None else f"${x:,.0f}"


# ------------------------------------------------------------------ header
st.title("AlwaysON")
st.caption("Find the fire-safety fixes that move your home closest to affordable private insurance.")

# ------------------------------------------------------------------ 1. address
st.header("1. Your home's location")
c1, c2 = st.columns([3, 2])
with c1:
    address = st.text_input("Address", value=st.session_state.get("address", DEMO_ADDRESSES[0]))
with c2:
    demo = st.selectbox("Or pick a demo address", ["-"] + DEMO_ADDRESSES)
    if demo != "-":
        address = demo
st.session_state["address"] = address

area: dict = {}
try:
    with st.spinner("Looking up hazard zone, fire history and insurance market..."):
        area = load_area(address)
except Exception as e:  # geocoder down or no match: the rest of the app still works
    st.warning(f"Could not look up this address ({e}). Choose the hazard zone by hand.")
    area = {"hazard_class": st.selectbox("Fire hazard zone", ["Very High", "High", "Moderate", None])}

if area.get("geocode"):
    g = area["geocode"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Fire hazard zone", area.get("hazard_class") or "Outside mapped zones")
    share = area.get("fair_plan_share")
    m2.metric("Homes on the FAIR Plan (ZIP, 2022)", f"{share:.1%}" if share is not None else "n/a")
    m3.metric("Past fires within 5 km", len(area.get("fires_within_5km") or []))
    m4.metric("ZIP home value", fmt_money(area.get("zip_home_value")))
    st.caption(f"Matched: {g['matched_address']} (ZIP {g['zip']})")
    if not area.get("hazard_class"):
        st.info("No mapped hazard zone does not mean no risk: most homes destroyed in the 2025 Eaton Fire were outside any zone.")
    trend = pd.DataFrame(area.get("zip_insurance_trend") or [])
    if not trend.empty:
        with st.expander("Insurance market in this ZIP (CDI, 2015 to 2023)"):
            st.line_chart(trend.set_index("year")["nonrenewal_rate"], y_label="Non-renewal rate")
            st.caption("Share of voluntary-market policies not renewed. Data ends in 2023, before the 2025 fires.")

# ------------------------------------------------------------------ 2. home
st.header("2. Your home")
home: dict = {}
cols = st.columns(4)
for i, (field, (label, options)) in enumerate(HOME_QUESTIONS.items()):
    with cols[i % 4]:
        home[field] = st.selectbox(label, options + ["Unknown"], key=field)
c1, c2, c3 = st.columns(3)
home["year_built"] = c1.number_input("Year built", 1900, 2026, 1965)
home["living_area_sqft"] = c2.number_input("Living area (sq ft)", 400, 15000, 1800, step=100)
home["stories"] = c3.number_input("Stories", 1, 4, 1)
done = [k for k, label in EXTRA_MEASURES.items() if st.checkbox(label, key=f"done_{k}")]

# ------------------------------------------------------------------ 3. insurance
st.header("3. Your insurance")
tab_pdf, tab_manual = st.tabs(["Upload policy (AI reads it)", "Enter by hand"])

with tab_pdf:
    st.write("Upload your declarations page (FAIR Plan, and your supplemental DIC policy if you have one). "
             "The AI copies each value with the exact line it came from; you confirm everything. Files are not stored.")
    uploads = st.file_uploader("Declarations page PDFs", type="pdf", accept_multiple_files=True)
    sample = st.selectbox("Or use a sample policy", ["-"] + list(SAMPLE_SETS))
    files = [(u.name, u.getvalue()) for u in uploads or []]
    if not files and sample != "-":
        files = [(n, (SAMPLES / n).read_bytes()) for n in SAMPLE_SETS[sample]]

    if files and st.button("Read policy", type="primary"):
        results, errors = [], []
        for name, data in files:
            try:
                with st.spinner(f"Reading {name}..."):
                    results.append((name, extract(data)))
            except ExtractionUnavailable as e:
                errors.append(f"{name}: {e}")
        for err in errors:
            st.error(err + " Use 'Enter by hand' instead.")
        if results:
            st.session_state["extractions"] = results
            merged = merge_policies([r for _, r in results])
            st.session_state["prefill"] = merged

    for name, res in st.session_state.get("extractions", []):
        st.subheader(f"{name}  ·  {res['fields']['document_type']['value']}")
        rows = []
        for f, (_, label, prio) in FIELDS.items():
            v = res["fields"][f]
            val = v["value"]
            if isinstance(val, dict):
                val = ", ".join(f"{k}={x}" for k, x in val.items() if x is not None) or None
            elif isinstance(val, list):
                val = "; ".join(x if isinstance(x, str) else f"{x['name']} {x['amount']}" for x in val) or None
            rows.append({
                "Field": label, "Value": "—" if val is None else str(val),
                "Found on page": v.get("source_text") or "", "Page": v.get("page") or "",
                "Check": {True: "✅ quote found", False: "⚠️ quote not found", None: ""}[v.get("verified")]
                + (f" ⚠️ {v['flag']}" if v.get("flag") else ""),
                "Must have": "★" if prio == 1 else "",
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.caption(f"Source: {'cached sample result' if res['source'] == 'cache' else 'Claude (live)'}. "
                   "Values are pre-filled in 'Enter by hand': review and correct them there.")

with tab_manual:
    p = st.session_state.get("prefill", {})
    docs = p.get("documents") or []
    default_type = 1 if "fair_plan" in docs and p.get("has_dic") else 0 if "fair_plan" in docs else 2 if docs else 0
    ins_type = st.radio("Current coverage", ["FAIR Plan only", "FAIR Plan + DIC policy", "Private homeowners"],
                        index=default_type, horizontal=True)
    c1, c2, c3 = st.columns(3)
    dwelling = c1.number_input("Dwelling limit ($)", 0, 10_000_000, int(p.get("dwelling_limit") or 650_000), step=10_000)
    settlement = c2.selectbox("How the dwelling is paid", ["replacement_cost", "actual_cash_value", "unknown"],
                              index=["replacement_cost", "actual_cash_value", "unknown"].index(
                                  p.get("dwelling_settlement") or "unknown"))
    ext = c3.number_input("Extended replacement (%)", 0, 100, int(p.get("extended_replacement_pct") or 0))
    c1, c2, c3 = st.columns(3)
    premium = c1.number_input("Total annual premium ($)", 0, 100_000, int(p.get("premium_total") or 6_000), step=100)
    liability = c2.number_input("Personal liability ($)", 0, 5_000_000, int(p.get("liability_limit") or 0), step=50_000)
    lou = c3.number_input("Loss of use ($)", 0, 2_000_000, int(p.get("loss_of_use_limit") or 0), step=10_000)

    def _covered(x):
        return bool(x.get("covered")) if isinstance(x, dict) else bool(x)

    c1, c2 = st.columns(2)
    code = c1.checkbox("Building code upgrade coverage", value=_covered(p.get("code_upgrade")))
    debris = c2.checkbox("Debris removal coverage", value=_covered(p.get("debris_removal")))

insurance = {
    "documents": {"FAIR Plan only": ["fair_plan"], "FAIR Plan + DIC policy": ["fair_plan", "dic"],
                  "Private homeowners": ["homeowners"]}[ins_type],
    "has_dic": ins_type == "FAIR Plan + DIC policy",
    "dwelling_limit": dwelling, "dwelling_settlement": settlement, "extended_replacement_pct": ext,
    "premium_total": premium, "liability_limit": liability,
    "loss_of_use_limit": lou, "code_upgrade": code, "debris_removal": debris,
}

# ------------------------------------------------------------------ 4. budget + results
st.header("4. Your plan")
budget = st.slider("Budget for fire-safety work ($)", 0, 60_000, 10_000, step=1_000)

if st.button("Show my plan", type="primary"):
    st.session_state["result"] = assess(
        {"address": address, "home": home, "measures_done": done, "insurance": insurance, "budget": budget}, area)

res = st.session_state.get("result")
if res:
    cur, fut = res["current"], res["future"]
    if res.get("stub"):
        st.warning("Prototype: wildfire and house scores are placeholders until the team's model is plugged in.")

    st.subheader("Where you are today")
    m1, m2, m3 = st.columns(3)
    m1.metric("Wildfire likelihood (per year)", f"{cur['wildfire']['p_fire_annual']:.1%}", cur["wildfire"]["rating"])
    m2.metric("Damage if fire reaches the house", f"{cur['house']['impact']:.0%}", cur["house"]["rating"], delta_color="off")
    m3.metric("After your plan", f"{fut['house_after_plan']['impact']:.0%}",
              f"{fut['house_after_plan']['impact'] - cur['house']['impact']:+.0%}", delta_color="inverse")

    st.markdown("**Coverage gaps**")
    if not cur["insurance_gap"]:
        st.success("No major coverage gaps found.")
    for gp in cur["insurance_gap"]:
        icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}[gp["severity"]]
        st.markdown(f"{icon} **{gp['gap']}**: {gp['why']}")

    st.subheader("Recommended fixes, best value first")
    if fut["fixes"]:
        df = pd.DataFrame([{
            "In plan": "✅" if f["within_budget"] else "",
            "Fix": f["name"],
            "Cost (assumed)": f"${f['cost_low']:,} to ${f['cost_high']:,}",
            "Yearly benefit (est.)": fmt_money(f["est_annual_benefit"]),
            "Payback (years)": f["payback_years"],
            "Damage after this fix": f"{f['impact_after']:.0%}",
            "Why": f["why"],
        } for f in fut["fixes"]])
        st.dataframe(df, hide_index=True, width="stretch")
        st.caption(f"Plan within budget: {len(fut['plan_within_budget'])} fixes from {fmt_money(fut['plan_cost_low'])}. "
                   "Yearly benefit = assumed premium discount + avoided expected loss.")
    else:
        st.success("Your home already meets every measure we check.")

    with st.expander("Assumptions and limits"):
        for c in res["caveats"]:
            st.markdown(f"- {c}")
        st.markdown("- Cost ranges and discounts per fix: " + ", ".join(
            f"{v[0]} ${v[1]:,}-${v[2]:,} ({v[3]:.0%})" for v in MEASURES.values()))
