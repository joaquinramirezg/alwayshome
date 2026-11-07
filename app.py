"""AlwaysON - Streamlit prototype.

Run: uv run streamlit run app.py
Optional: export ANTHROPIC_API_KEY=... to read new policy PDFs and rewrite the report with AI.
Without a key everything still works: cached sample policies, manual entry, template report.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from msba_vibathon_2026.assess_stub import MEASURES, SOURCES, assess  # noqa: E402
from msba_vibathon_2026.contract import validate_inputs, validate_output  # noqa: E402
from msba_vibathon_2026.coverage.adapter import to_policy_input  # noqa: E402
from msba_vibathon_2026.policy_extract import FIELDS, ExtractionUnavailable, extract, merge_policies  # noqa: E402
from msba_vibathon_2026.report import ai_report, template_report  # noqa: E402

AREA_CACHE = ROOT / "data" / "demo" / "area_cache.json"
SAMPLES = ROOT / "data" / "samples" / "policies"
SCENARIOS = json.loads((ROOT / "data" / "samples" / "scenarios.json").read_text())
DEMO_ADDRESSES = [
    "1200 Chautauqua Blvd, Pacific Palisades, CA 90272",
    "1000 E Mariposa St, Altadena, CA 91001",
    "3200 Wilshire Blvd, Los Angeles, CA 90010",
]
SAMPLE_SETS = {
    "FAIR Plan + DIC (Altadena)": ["fair_plan_altadena.pdf", "dic_altadena.pdf"],
    "FAIR Plan only (Altadena)": ["fair_plan_altadena.pdf"],
    "FAIR Plan, scanned copy (no text layer)": ["fair_plan_scanned.pdf"],
    "Private HO-3, underinsured (Palisades)": ["homeowners_palisades_underinsured.pdf"],
    "Private HO-3, two pages (Altadena)": ["homeowners_two_page.pdf"],
    "Private HO-3, well covered (Wilshire)": ["homeowners_well_covered.pdf"],
    "Not a policy: non-renewal letter": ["nonrenewal_letter.pdf"],
}
HOME_QUESTIONS = {  # DINS answer options (docs/inputs_and_contract.md)
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
INS_TYPES = ["FAIR Plan only", "FAIR Plan + DIC policy", "Private homeowners"]
SETTLEMENTS = ["replacement_cost", "actual_cash_value", "unknown"]
# Used by the loss scenario. Empty means unknown here, which widens the range instead of assuming $0.
OPTIONAL_INSURANCE = ("other_structures_limit", "contents_limit", "deductible", "code_upgrade_amount")
OPTIONAL_HOME = ("contents_value_estimate", "other_structures_estimate")
# The app starts empty: the homeowner fills in everything (or loads a sample from the sidebar).
DEFAULTS = {
    "address": "",
    **{f: None for f in HOME_QUESTIONS},
    "year_built": None, "living_area_sqft": None, "stories": None,
    **{f"done_{k}": False for k in EXTRA_MEASURES},
    "ins_type": None, "dwelling_limit": None, "dwelling_settlement": None,
    "extended_replacement_pct": None, "premium_total": None, "liability_limit": None, "loss_of_use_limit": None,
    "code_upgrade": False, "debris_removal": False, "budget": 10_000,
    **{k: None for k in OPTIONAL_INSURANCE + OPTIONAL_HOME}, "dic_covers": [],
}
TRANSIENT = ("result", "result_inputs", "extractions", "extraction_errors", "report")

st.set_page_config(page_title="AlwaysON", page_icon="🔥", layout="wide")
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)


# ------------------------------------------------------------------ state helpers
def load_scenario(sid: str) -> None:
    s = SCENARIOS[sid]
    st.session_state["address"] = s["address"]
    for k, v in s["home"].items():
        st.session_state[k] = v
    for k in EXTRA_MEASURES:
        st.session_state[f"done_{k}"] = k in s["measures_done"]
    ins = s["insurance"]
    st.session_state["ins_type"] = ins["type"]
    for k in ("dwelling_limit", "dwelling_settlement", "extended_replacement_pct", "premium_total",
              "liability_limit", "loss_of_use_limit", "code_upgrade", "debris_removal"):
        st.session_state[k] = ins[k]
    for k in OPTIONAL_INSURANCE:
        st.session_state[k] = ins.get(k)
    for k in OPTIONAL_HOME:
        st.session_state[k] = s["home"].get(k)
    st.session_state["dic_covers"] = []
    st.session_state["budget"] = s["budget"]
    for k in TRANSIENT:
        st.session_state.pop(k, None)


def clear_all() -> None:
    for k, v in DEFAULTS.items():
        st.session_state[k] = v
    for k in TRANSIENT + ("sample_policy",):
        st.session_state.pop(k, None)


def missing_fields(area: dict) -> list[str]:
    """What the homeowner still has to fill in before a plan can be made."""
    ss, miss = st.session_state, []
    if not ss["address"].strip():
        miss.append("your address")
    elif not area:
        miss.append("a valid address (or the fire hazard zone)")
    miss += [label for f, (label, _) in HOME_QUESTIONS.items() if ss[f] is None]
    if not ss["living_area_sqft"]:
        miss.append("living area")
    if ss["ins_type"] is None:
        miss.append("current coverage")
    if not ss["dwelling_limit"]:
        miss.append("dwelling limit")
    if ss["dwelling_settlement"] is None:
        miss.append("how the dwelling is paid")
    if not ss["premium_total"]:
        miss.append("annual premium")
    return miss


def apply_policy(merged: dict) -> None:
    """Pre-fill the insurance form from extracted values (the user then confirms them)."""
    docs = merged.get("documents") or []
    if "fair_plan" in docs:
        st.session_state["ins_type"] = INS_TYPES[1] if merged.get("has_dic") else INS_TYPES[0]
    elif {"homeowners", "dwelling_fire"} & set(docs):
        st.session_state["ins_type"] = INS_TYPES[2]
    for k in ("dwelling_limit", "extended_replacement_pct", "premium_total", "liability_limit", "loss_of_use_limit"):
        if merged.get(k) is not None:
            st.session_state[k] = int(merged[k])
    if merged.get("dwelling_settlement") in SETTLEMENTS:
        st.session_state["dwelling_settlement"] = merged["dwelling_settlement"]
    for k in ("code_upgrade", "debris_removal"):
        v = merged.get(k)
        if v is not None:
            st.session_state[k] = bool(v.get("covered")) if isinstance(v, dict) else bool(v)
    policy = to_policy_input(merged)  # converts add-on and deductible percentages to dollars
    for k in ("other_structures_limit", "contents_limit"):
        if merged.get(k) is not None:
            st.session_state[k] = int(merged[k])
    deductible = policy.deductible_wildfire if policy.deductible_wildfire is not None else policy.deductible_all_perils
    if deductible is not None:
        st.session_state["deductible"] = int(deductible)
    if policy.code_upgrade_amount is not None:
        st.session_state["code_upgrade_amount"] = int(policy.code_upgrade_amount)
    st.session_state["dic_covers"] = merged.get("dic_covers") or []


def build_inputs() -> dict:
    ss = st.session_state
    zero = lambda k: ss[k] or 0  # optional amounts left empty mean "not on my policy"  # noqa: E731
    return {
        "address": ss["address"],
        "home": {**{f: ss[f] for f in HOME_QUESTIONS}, "year_built": ss["year_built"],
                 "living_area_sqft": ss["living_area_sqft"], "stories": ss["stories"],
                 **{k: ss[k] for k in OPTIONAL_HOME}},
        "measures_done": [k for k in EXTRA_MEASURES if ss[f"done_{k}"]],
        "insurance": {
            "documents": {INS_TYPES[0]: ["fair_plan"], INS_TYPES[1]: ["fair_plan", "dic"],
                          INS_TYPES[2]: ["homeowners"], None: []}[ss["ins_type"]],
            "has_dic": ss["ins_type"] == INS_TYPES[1],
            **{k: ss[k] for k in ("dwelling_limit", "dwelling_settlement", "premium_total", "code_upgrade", "debris_removal")},
            **{k: zero(k) for k in ("extended_replacement_pct", "liability_limit", "loss_of_use_limit")},
            **{k: ss[k] for k in OPTIONAL_INSURANCE}, "dic_covers": ss["dic_covers"],
        },
        "budget": ss["budget"],
    }


def _key(a: str) -> str:
    return " ".join(a.lower().split())


@st.cache_data(show_spinner=False)
def load_area(address: str) -> dict:
    cache = json.loads(AREA_CACHE.read_text()) if AREA_CACHE.exists() else {}
    if _key(address) in cache:
        return cache[_key(address)]
    from utils import area_context  # David's helper; needs network for geocoding

    return json.loads(json.dumps(area_context(address), default=str))


def fmt_money(x) -> str:
    return "n/a" if x is None else f"${x:,.0f}"


def fmt_range(r: dict) -> str:
    if r["low"] is None:
        return "n/a"
    return fmt_money(r["low"]) if r["low"] == r["high"] else f"{fmt_money(r['low'])} to {fmt_money(r['high'])}"


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("Demo shortcuts")
    st.caption("For testing only. A real homeowner fills in the form on the right.")
    sid = st.selectbox("Sample homeowner", list(SCENARIOS), format_func=lambda k: SCENARIOS[k]["title"])
    st.caption(SCENARIOS[sid]["description"])
    c1, c2 = st.columns(2)
    c1.button("Fill form", on_click=load_scenario, args=(sid,), width="stretch", type="primary")
    c2.button("Clear all", on_click=clear_all, width="stretch")
    st.selectbox("Or just a demo address", ["-"] + DEMO_ADDRESSES, key="demo_pick",
                 on_change=lambda: st.session_state.update(address=st.session_state["demo_pick"])
                 if st.session_state["demo_pick"] != "-" else None)
    st.divider()
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))
    st.markdown(f"**Claude API key:** {'✅ set' if has_key else '❌ not set (cached samples and manual entry only)'}")
    badge = {"real": "✅ team model", "placeholder": "⚠️ placeholder"}
    st.markdown(f"**Wildfire analysis:** {badge[SOURCES['wildfire']]}  \n**House analysis:** {badge[SOURCES['house']]}")
    dev = st.toggle("Developer panel", value=False)

# ------------------------------------------------------------------ header
st.title("AlwaysON")
st.caption("Find the fire-safety fixes that move your home closest to affordable private insurance.")

# ------------------------------------------------------------------ 1. address
st.header("1. Your home's location")
st.text_input("Street address in Los Angeles County", key="address",
              placeholder="e.g. 1000 E Mariposa St, Altadena, CA 91001",
              help="Press Enter to look it up. Used only to find your hazard zone, fire history and local insurance data.")

area: dict = {}
t0 = time.time()
if st.session_state["address"].strip():
    try:
        with st.spinner("Looking up hazard zone, fire history and insurance market..."):
            area = load_area(st.session_state["address"])
    except Exception as e:  # geocoder down or no match: the rest of the app still works
        st.warning(f"Could not look up this address ({e}). Check it, or choose the fire hazard zone by hand.")
        zone = st.selectbox("Fire hazard zone", ["Very High", "High", "Moderate", "Outside mapped zones"],
                            index=None, placeholder="Select...")
        if zone:
            area = {"hazard_class": None if zone == "Outside mapped zones" else zone}
else:
    st.info("Enter your address to start.")
area_seconds = time.time() - t0

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
    with st.expander("Insurance market and fire history"):
        if not trend.empty:
            st.line_chart(trend.set_index("year")["nonrenewal_rate"], y_label="Non-renewal rate")
            st.caption("Share of voluntary-market policies not renewed in this ZIP (CDI). Data ends in 2023, before the 2025 fires.")
        fires = pd.DataFrame(area.get("fires_within_5km") or [])
        if not fires.empty:
            st.dataframe(fires.head(10), hide_index=True, width="stretch")
        wrc = area.get("wrc_community")
        if wrc:
            st.caption(f"Wildfire Risk to Communities ({wrc['community']}): risk to homes higher than "
                       f"{wrc['risk_to_homes_pctile_state']:.0%} of California communities.")

# ------------------------------------------------------------------ 2. home
st.header("2. Your home")
cols = st.columns(4)
for i, (field, (label, options)) in enumerate(HOME_QUESTIONS.items()):
    cols[i % 4].selectbox(label, options + ["Unknown"], key=field, placeholder="Select...",
                          format_func=lambda o: "I don't know" if o == "Unknown" else o)
c1, c2, c3 = st.columns(3)
c1.number_input("Year built", 1900, 2026, key="year_built", placeholder="e.g. 1965")
c2.number_input("Living area (sq ft)", 400, 15000, step=100, key="living_area_sqft", placeholder="e.g. 1800")
c3.number_input("Stories", 1, 4, key="stories", placeholder="e.g. 1")
st.caption("Already done any of these?")
for k, label in EXTRA_MEASURES.items():
    st.checkbox(label, key=f"done_{k}")

# ------------------------------------------------------------------ 3. insurance
st.header("3. Your insurance")
tab_pdf, tab_manual = st.tabs(["Upload policy (AI reads it)", "Confirm or enter by hand"])

with tab_pdf:
    st.write("Upload your declarations page (FAIR Plan, plus your supplemental DIC policy if you have one). "
             "The AI copies each value with the exact line it came from; you confirm everything. Files are not stored.")
    uploads = st.file_uploader("Declarations page PDFs", type="pdf", accept_multiple_files=True)
    sample = st.selectbox("Or use a sample policy", ["-"] + list(SAMPLE_SETS), key="sample_policy")
    files = [(u.name, u.getvalue()) for u in uploads or []]
    if not files and sample != "-":
        files = [(n, (SAMPLES / n).read_bytes()) for n in SAMPLE_SETS[sample]]
        with st.expander("Preview the sample PDF text"):
            from msba_vibathon_2026.policy_extract import page_texts
            for n, data in files:
                pages = page_texts(data)
                st.markdown(f"**{n}**: {len(pages)} page(s)")
                st.text("\n---\n".join(pages) if any(p.strip() for p in pages) else "(no text layer: scanned image)")

    if files and st.button("Read policy", type="primary"):
        results, errors = [], []
        for name, data in files:
            try:
                with st.spinner(f"Reading {name}..."):
                    results.append((name, extract(data)))
            except ExtractionUnavailable as e:
                errors.append(f"{name}: {e}")
        st.session_state["extraction_errors"] = errors
        st.session_state["extractions"] = results
        if results:
            apply_policy(merge_policies([r for _, r in results]))

    for err in st.session_state.get("extraction_errors", []):
        st.error(err + " Use 'Confirm or enter by hand' instead.")
    for name, res in st.session_state.get("extractions", []):
        st.subheader(f"{name}  ·  {res['fields']['document_type']['value']}")
        if not res["text_layer"]:
            st.warning("Scanned PDF: quotes can't be checked automatically. Compare each value with the document.")
        rows = []
        for f, (label, prio) in FIELDS.items():
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
                   "Values are pre-filled in the next tab: review and correct them there.")

with tab_manual:
    if st.session_state.get("extractions"):
        st.info("Pre-filled from your policy. Check every value before continuing.")
    st.radio("Current coverage", INS_TYPES, horizontal=True, key="ins_type")
    st.caption("Find these numbers on your declarations page. Leave optional amounts empty if your policy doesn't include them.")
    c1, c2, c3 = st.columns(3)
    c1.number_input("Dwelling limit ($)", 0, 10_000_000, step=10_000, key="dwelling_limit", placeholder="Coverage A, e.g. 650000")
    c2.selectbox("How the dwelling is paid", SETTLEMENTS, key="dwelling_settlement", placeholder="Select...",
                 format_func=lambda s: {"replacement_cost": "Replacement cost", "actual_cash_value": "Actual cash value",
                                        "unknown": "Not sure"}[s])
    c3.number_input("Extended replacement (%, optional)", 0, 100, key="extended_replacement_pct", placeholder="e.g. 25")
    c1, c2, c3 = st.columns(3)
    c1.number_input("Total annual premium ($)", 0, 100_000, step=100, key="premium_total", placeholder="all policies, e.g. 6200")
    c2.number_input("Personal liability ($, optional)", 0, 5_000_000, step=50_000, key="liability_limit", placeholder="Coverage E")
    c3.number_input("Loss of use ($, optional)", 0, 2_000_000, step=10_000, key="loss_of_use_limit", placeholder="Coverage D")
    c1, c2 = st.columns(2)
    c1.checkbox("Building code upgrade coverage", key="code_upgrade")
    c2.checkbox("Debris removal coverage", key="debris_removal")
    with st.expander("More details for the loss estimate (optional)"):
        st.caption("Leave empty if you don't know. Unknown amounts widen the estimate; nothing is assumed to be $0.")
        c1, c2, c3 = st.columns(3)
        c1.number_input("Other structures limit, Coverage B ($)", 0, 5_000_000, step=10_000, key="other_structures_limit")
        c2.number_input("Contents limit, Coverage C ($)", 0, 5_000_000, step=10_000, key="contents_limit",
                        help="Enter 0 if your policy explicitly doesn't cover belongings.")
        c3.number_input("Deductible ($)", 0, 1_000_000, step=500, key="deductible")
        c1, c2, c3 = st.columns(3)
        c1.number_input("Code upgrade amount ($)", 0, 5_000_000, step=10_000, key="code_upgrade_amount")
        c2.number_input("Value of your belongings ($)", 0, 10_000_000, step=10_000, key="contents_value_estimate")
        c3.number_input("Value of sheds, fences and other structures ($)", 0, 5_000_000, step=5_000,
                        key="other_structures_estimate")

# ------------------------------------------------------------------ 4. plan
st.header("4. Your plan")
st.slider("Budget for fire-safety work ($)", 0, 60_000, step=1_000, key="budget")
inputs = build_inputs()

missing = missing_fields(area)
if st.button("Show my plan", type="primary"):
    if missing:
        st.error("Please fill in: " + ", ".join(missing) + ".")
    else:
        t0 = time.time()
        st.session_state["result"] = assess(inputs, area)
        st.session_state["assess_seconds"] = time.time() - t0
        st.session_state["result_inputs"] = inputs
        st.session_state.pop("report", None)

res = st.session_state.get("result")
if res:
    cur, fut = res["current"], res["future"]
    if st.session_state.get("result_inputs") != inputs:
        st.info("Inputs changed since this plan was made. Press 'Show my plan' again to update it.")
    src = res.get("sources", {})
    if src.get("house") == "placeholder":
        st.warning("Prototype: the house damage score is a placeholder until the house model is plugged in. "
                   "The wildfire exposure score is real.")
    if src.get("wildfire") == "placeholder":
        st.warning("The address could not be matched to a census tract, so wildfire exposure uses the hazard zone only.")

    tab_plan, tab_report = st.tabs(["Plan", "Report"])
    with tab_plan:
        st.subheader("Where you are today")
        m1, m2, m3 = st.columns(3)
        wf = cur["wildfire"]
        m1.metric("Wildfire exposure of your area", f"{wf['score']:.0f} / 100" if wf.get("score") is not None else "n/a",
                  wf["rating"], delta_color="off",
                  help="Relative index for your census tract vs. other LA County tracts (not a probability). "
                       "Combines very-high and high hazard area, past burned area and FEMA expected loss.")
        m2.metric("Damage if fire reaches the house", f"{cur['house']['impact']:.0%}", cur["house"]["rating"],
                  delta_color="off")
        m3.metric("After your plan", f"{fut['house_after_plan']['impact']:.0%}",
                  f"{fut['house_after_plan']['impact'] - cur['house']['impact']:+.0%}", delta_color="inverse")

        comp = wf.get("components") or {}
        if comp:
            with st.expander(f"Why your area scores {wf['score']:.0f} / 100"):
                c = st.columns(4)
                c[0].metric("Tract in Very High zone", f"{comp['very_high_hazard_pct']:.0f}%")
                c[1].metric("Tract in High zone", f"{comp['high_hazard_pct']:.0f}%")
                c[2].metric("Tract area burned since 1950", f"{comp['burned_footprint_pct']:.0f}%")
                c[3].metric("Last fire touching the tract", comp["last_fire_year"] or "none on record")
                st.caption(f"FEMA estimates a wildfire frequency of {wf['p_fire_annual']:.2%} per year for this tract and "
                           f"expected losses of {fmt_money(comp['fema_expected_annual_loss'])} per year across it. "
                           f"Tract {wf.get('tract_geoid')}. {wf['method']}. Relative to LA County, not a probability or inspection.")

        st.markdown("**Coverage gaps**")
        if not cur["insurance_gap"]:
            st.success("No major coverage gaps found.")
        for gp in cur["insurance_gap"]:
            icon = {"high": "🔴", "medium": "🟠", "low": "🟡"}[gp["severity"]]
            st.markdown(f"{icon} **{gp['gap']}**: {gp['why']}")

        cov = cur.get("coverage")
        if cov:
            st.subheader("If your home is destroyed")
            at_least = "at least " if any(w.startswith("Totals leave out") for w in cov["warnings"]) else ""
            with st.container(border=True):  # text, because st.metric cuts off a long range
                st.markdown("You would pay")
                st.markdown(f"### {at_least}{fmt_range(cov['total_shortfall'])}")
                st.markdown(f"Cost to recover: **{at_least}{fmt_range(cov['total_cost'])}**  \n"
                            f"Policy pays: **{at_least}{fmt_range(cov['total_payout'])}**")
            st.caption(f"{cov['scope_note']} The low and high figures are separate best and worst cases, "
                       "so they don't subtract line by line. All are estimates, not a quote or a claim outcome.")
            st.dataframe(pd.DataFrame([{
                "Part of the loss": c["name"].replace("_", " ").capitalize(),
                "Cost": fmt_range(c["cost"]), "Policy pays": fmt_range(c["payout"]),
                "You would pay": fmt_range(c["shortfall"]),
            } for c in cov["components"]]), hide_index=True, width="stretch")
            with st.expander("What could change these numbers"):
                for w in cov["warnings"]:
                    st.markdown(f"- {w}")
                for c in cov["components"]:
                    for n in c["notes"]:
                        st.markdown(f"- {c['name'].replace('_', ' ').capitalize()}: {n}")
            with st.expander("Sources and assumptions for the loss estimate"):
                for a in cov["assumptions"]:
                    st.markdown(f"- {a}")
        else:
            st.info("The loss estimate isn't available for these inputs. Your fixes and basic coverage gaps are still shown.")

        st.subheader("Recommended fixes, best value first")
        if fut["fixes"]:
            st.dataframe(pd.DataFrame([{
                "In plan": "✅" if f["within_budget"] else "",
                "Fix": f["name"],
                "Cost (assumed)": f"${f['cost_low']:,} to ${f['cost_high']:,}",
                "Yearly benefit (est.)": fmt_money(f["est_annual_benefit"]),
                "Payback (years)": f["payback_years"],
                "Damage after this fix": f"{f['impact_after']:.0%}",
                "Why": f["why"],
            } for f in fut["fixes"]]), hide_index=True, width="stretch")
            st.caption(f"Plan within budget: {len(fut['plan_within_budget'])} fixes from {fmt_money(fut['plan_cost_low'])}. "
                       "Yearly benefit = assumed premium discount + avoided expected loss.")
        else:
            st.success("Your home already meets every measure we check.")

        with st.expander("Assumptions and limits"):
            for c in res["caveats"]:
                st.markdown(f"- {c}")
            st.markdown("- Cost ranges and assumed discounts per fix: " + "; ".join(
                f"{v[0]} ${v[1]:,} to ${v[2]:,} ({v[3]:.0%})" for v in MEASURES.values()))

    with tab_report:
        c1, c2 = st.columns(2)
        if c1.button("Write report"):
            st.session_state["report"] = (template_report(inputs["address"], res), "template")
        if c2.button("Rewrite with AI", disabled=not has_key, help=None if has_key else "Needs ANTHROPIC_API_KEY"):
            with st.spinner("Rewriting..."):
                st.session_state["report"] = ai_report(inputs["address"], res)
        if "report" in st.session_state:
            text, source = st.session_state["report"]
            st.caption("Written by Claude from the plan's numbers" if source == "ai" else "Template report")
            st.markdown(text)
            st.download_button("Download report (.md)", text, file_name="alwayson_plan.md")

# ------------------------------------------------------------------ developer panel
if dev:
    st.divider()
    st.header("Developer panel")
    in_errs = validate_inputs(inputs)
    st.markdown(f"**Inputs contract:** {'✅ valid' if not in_errs else '❌ ' + '; '.join(in_errs)}")
    if res:
        out_errs = validate_output(res)
        st.markdown(f"**Output contract:** {'✅ valid' if not out_errs else '❌ ' + '; '.join(out_errs)}")
        st.caption(f"assess() took {st.session_state.get('assess_seconds', 0):.2f}s; area lookup {area_seconds:.2f}s")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**inputs**")
        st.json(inputs, expanded=False)
    with c2:
        st.markdown("**area_context**")
        st.json(area, expanded=False)
    with c3:
        st.markdown("**assess() output**")
        st.json(res or {}, expanded=False)
