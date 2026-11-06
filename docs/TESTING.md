# How to run and test everything locally

Works on macOS, Linux and Windows. Takes about 5 minutes the first time.

## 1. One-time setup

1. Install `uv` (it manages Python and packages for this project; nothing touches your other Python or conda installs):
   - macOS: `brew install uv`
   - macOS / Linux without Homebrew: `curl -LsSf https://astral.sh/uv/install.sh | sh`
   - Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`
2. Get the code and switch to the app branch:
   ```
   git clone https://github.com/joaquinramirezg/msba-vibathon-2026.git
   cd msba-vibathon-2026
   git fetch
   git switch app-streamlit      # until it is merged into main
   ```
   Already cloned? `git pull` instead.
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

### Demo walkthrough (what to click)

1. **Location:** pick a demo address from the dropdown:
   - Pacific Palisades: Very High hazard zone
   - Altadena: outside any mapped zone, yet burned in January 2025 ("no zone does not mean no risk")
   - Wilshire: low risk
   Any other LA County address works too if you are online (the Census geocoder takes a few seconds).
2. **Home:** answer the checklist. Use "Unknown" when unsure.
3. **Insurance:** either
   - tab "Upload policy": pick a sample policy (or upload a PDF) and press **Read policy**, then check the values in tab "Enter by hand", or
   - tab "Enter by hand": type the numbers yourself.
4. **Plan:** set a budget and press **Show my plan**.

Wildfire and house scores are placeholders until the model is plugged in; the app says so on screen.

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
   It prints each must-have field as `ok` or `MISS`, the accuracy, and any quotes that could not be found on the page. The saved results go to `data/demo/policy_extractions.json`; commit that file so everyone's demo works without a key.

Without `--refresh` the script only scores what is already cached (or calls the API for anything missing, if a key is set).

The sample PDFs and their answer key are in `data/samples/policies/`. To change or add samples, edit `scripts/make_sample_policies.py`, then:
```
uv run python scripts/make_sample_policies.py
uv run python scripts/eval_policy_extraction.py --refresh
```

## 4. Automated checks

| Command | What it checks | Needs |
|---|---|---|
| `uv run python scripts/smoke_test.py` | Clicks through the whole app without a browser: all demo addresses, all sample policies, the plan screen. Fails on any error. | nothing |
| `uv run python scripts/eval_policy_extraction.py` | Policy reader accuracy against the answer key | API key, or cached results |
| `uv run python scripts/03_validate.py` | Data checks; rewrites `docs/validation_report.md` | processed data (in the repo) |

Run the smoke test before every push to `main`. Expected last line: `All checks passed.`

## 5. For the model team: plugging in `assess()`

The app calls `assess(inputs, area)` from `src/msba_vibathon_2026/assess_stub.py`. Input and output shapes are in `docs/inputs_and_contract.md`.

1. Replace `wildfire_score()` and `house_impact()` (or the whole `assess()`) with the model, keeping the output keys.
2. Set `STUB = False` so the "placeholder" warning disappears.
3. Run `uv run python scripts/smoke_test.py`, then open the app and check the numbers look sensible for the three demo addresses.

## 6. Troubleshooting

| Problem | Fix |
|---|---|
| `uv: command not found` | Install uv (step 1), then open a new terminal |
| `ModuleNotFoundError` | Run `uv sync`, and start commands with `uv run` |
| Address lookup fails | You are offline or the Census geocoder is down: use a demo address (cached) or pick the hazard zone by hand when asked |
| "No ANTHROPIC_API_KEY set" | Expected without a key; set it (section 3) or use "Enter by hand" |
| Port 8501 in use | `uv run streamlit run app.py --server.port 8502` |
| Changes to code not showing | Press "R" in the browser, or "Rerun" in the app menu |
