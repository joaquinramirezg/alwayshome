# How to run and test everything locally

Works on macOS, Linux and Windows. Takes about 5 minutes the first time.

## 1. One-time setup

1. Install `uv` (it manages Python and packages for this project; nothing touches your other Python or conda installs):
   - macOS: `brew install uv`
   - macOS / Linux without Homebrew: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. Get the code (everything is on `main`):
   ```
   git clone https://github.com/joaquinramirezg/msba-vibathon-2026.git
   cd msba-vibathon-2026
   ```
   Already cloned? `git switch main && git pull` instead.
3. Install everything:
   ```
   uv sync
   ```
   This creates a private `.venv/` folder inside the repo with Python 3.14 and all packages. It is git-ignored.

Run every command below from the repo folder, always prefixed with `uv run`.

## 2. Run the app

```
uv run streamlit run app.py
```

It opens at http://localhost:8501. Stop it with Ctrl+C.

### Fastest way to try everything: sample homeowners

The app starts **empty**, like a real homeowner's first visit: type the address, answer the home questions, enter or upload the insurance, then press **Show my plan** (it lists anything still missing).

To skip typing, use **Demo shortcuts** in the sidebar: pick a **Sample homeowner** and press **Fill form**. It fills the same fields a user would (address, home, insurance, budget), so the demo looks like real input. **Clear all** empties the form again.

| Sample homeowner | What it shows |
|---|---|
| Altadena, FAIR Plan only, older home | Every coverage gap, all 9 fixes, small budget |
| Altadena, FAIR Plan + DIC, partly hardened | The DIC policy closes the liability and FAIR-only gaps |
| Pacific Palisades, private HO-3, underinsured | Underinsured vs. rebuild cost, no extended replacement |
| Wilshire, well covered, fully hardened | Control case: no fixes, no gaps |
| Unknown to everything, no budget | Every fix listed, none in the plan |
| Unknown to everything, large budget | Every fix fits the plan |

The same cases, with their expected results, are in `data/samples/scenarios.json`; the tests check them.

Turn on **Developer panel** in the sidebar to see the exact `inputs`, the `area_context` data, the `assess()` output, timings, and whether both sides of the model contract are valid.

### Demo walkthrough (what to click)

1. **Location:** type an address and press Enter (or pick one under "Or just a demo address" in the sidebar):
   - Pacific Palisades: Very High hazard zone
   - Altadena: outside any mapped zone, yet burned in January 2025 ("no zone does not mean no risk")
   - Wilshire: low risk
   Any other LA County address works too if you are online (the Census geocoder takes a few seconds).
2. **Home:** answer the checklist. Use "Unknown" when unsure.
3. **Insurance:** either
   - tab "Upload policy": pick a sample policy (or upload a PDF) and press **Read policy**, then check the values in tab "Enter by hand", or
   - tab "Enter by hand": type the numbers yourself.
4. **Plan:** set a budget and press **Show my plan**. The **Report** tab writes a plain-language plan you can download (**Rewrite with AI** needs an API key; otherwise it uses the template).

The wildfire exposure score is real (Atharva's tract index); the house damage score is still a placeholder, and the app says so on screen.

## 3. The AI policy reader (needs an API key)

Reading a policy PDF calls the Claude API. Without a key, **Read policy** shows a message and you use "Enter by hand"; nothing breaks.

1. Get a key at https://console.anthropic.com (API credit is separate from a Claude.ai subscription).
2. Set it in the terminal you run the app from. Never commit it.
   ```
   export ANTHROPIC_API_KEY=sk-ant-...        # macOS / Linux
   $env:ANTHROPIC_API_KEY="sk-ant-..."        # Windows PowerShell
   ```
3. Score the extractor on the 4 synthetic sample PDFs and save the results so the demo works offline:
   ```
   uv run python scripts/eval_policy_extraction.py --refresh
   ```
   It prints each must-have field as `ok` or `MISS`, the accuracy, and any quotes that could not be found on the page.
   **Result on Nov 6 (claude-opus-5-5): 56/56 must-have fields correct (100%) on all 7 samples, including the scanned and two-page PDFs; every quote found on its page; no personal data extracted.** These results are already saved in the repo, so the demo reads every sample policy without a key. The saved results go to `data/demo/policy_extractions.json`; commit that file so everyone's demo works without a key.

Without `--refresh` the script only scores what is already cached (or calls the API for anything missing, if a key is set).

The sample PDFs and their answer key are in `data/samples/policies/` (all fictional, marked SAMPLE):

| PDF | What it tests |
|---|---|
| `fair_plan_altadena.pdf` | FAIR Plan page: actual cash value, coverages not purchased |
| `dic_altadena.pdf` | Supplemental DIC policy, merged with the FAIR Plan |
| `fair_plan_scanned.pdf` | Scanned image, no text layer: quotes can't be auto-checked |
| `homeowners_palisades_underinsured.pdf` | Private HO-3, % wildfire deductible, discount line |
| `homeowners_two_page.pdf` | Coverage on page 2, 50% extended replacement, ordinance not included |
| `homeowners_well_covered.pdf` | Strong private policy |
| `nonrenewal_letter.pdf` | Not a policy: everything should come back empty |

Every PDF also contains fake names and policy numbers, to check that they are never extracted. To change or add samples, edit `scripts/make_sample_policies.py`, then:
```
uv run python scripts/make_sample_policies.py
uv run python scripts/eval_policy_extraction.py --refresh
```

## 4. Automated checks

Run everything:
```
uv run pytest
```
About 85 tests, a few seconds, **no API key needed**. Claude is replaced by a fake that returns the answer key, so the whole AI path (quote checks, flags, caching, merging, fallbacks) is still tested. Expected: `N passed`.

| Test file | Covers |
|---|---|
| `tests/test_policy_extract.py` | Every sample PDF, quote verification, invented quotes, wrong page numbers, implausible values, scanned PDFs, no key, API errors, cache, FAIR + DIC merge, no personal data in the schema |
| `tests/test_plan.py` | Each coverage gap rule, every sample homeowner end to end against its expected results, budget limits, the model contract checker, the report and its AI fallback |
| `tests/test_app.py` | The real Streamlit UI: loading each homeowner, reading each sample policy, form pre-fill, fallbacks, demo addresses, stale-plan warning |

Run one file or one test: `uv run pytest tests/test_plan.py` or `uv run pytest -k palisades`.

Other checks:

| Command | What it checks | Needs |
|---|---|---|
| `uv run python scripts/smoke_test.py` | Clicks through the whole app without a browser: all demo addresses, all sample policies, the plan screen. Fails on any error. | nothing |
| `uv run python scripts/eval_policy_extraction.py` | Policy reader accuracy against the answer key | API key, or cached results |
| `uv run python scripts/03_validate.py` | Data checks; rewrites `docs/validation_report.md` | processed data (in the repo) |

Run `uv run pytest` before every push to `main`.

## 5. For the model team: plugging in `assess()`

The app calls `assess(inputs, area)` from `src/msba_vibathon_2026/assess_stub.py`. Input and output shapes are in `docs/inputs_and_contract.md`.

1. Wildfire is done: `wildfire.py` reads Atharva's `tract_wildfire_features.parquet`. Rebuilding that file updates the app automatically.
2. For the house model, replace `house_impact()` in `assess_stub.py`, keeping the output keys, then set `SOURCES["house"] = "real"` and `STUB = False` so the placeholder warning disappears.
3. Run `uv run pytest`. `test_scenario_end_to_end` runs the model on every sample homeowner and `validate_output()` (in `src/msba_vibathon_2026/contract.py`) reports any shape problem, e.g. a probability above 1 or a fix missing a field.
4. Open the app, turn on **Developer panel**, load each sample homeowner, and check the numbers look sensible.

If your model changes which fixes are recommended, update the `fixes` lists in `data/samples/scenarios.json`.

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `uv: command not found` | Install uv (step 1), then open a new terminal |
| `ModuleNotFoundError` | Run `uv sync`, and start commands with `uv run` |
| Address lookup fails | You are offline or the Census geocoder is down: use a demo address (cached) or pick the hazard zone by hand when asked |
| "No ANTHROPIC_API_KEY set" | Expected without a key; set it (section 3) or use "Enter by hand" |
| Port 8501 in use | `uv run streamlit run app.py --server.port 8502` |
| Changes to code not showing | Press "R" in the browser, or "Rerun" in the app menu |
