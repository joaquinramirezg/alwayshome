# Working notes for AI coding assistants

Tool-agnostic instructions for any coding assistant (Claude, Copilot, Cursor, ChatGPT and others) working in this repo. People can read it too.

## What this project is

**AlwaysON**, a one-day hackathon prototype (UCLA Anderson MSBA Vibathon, Fri Nov 6 2026, theme 04 "Uninsurable"). Judges review from 6:00 PM.

> We help California homeowners on the FAIR Plan find the fire-safety fixes that move them closest to affordable private insurance, ranked by cost and benefit for their home and budget.

Core demo: address in, then hazard zone, fire history and ZIP insurance context, then a checklist of the fire-safety items the home already meets, then ranked fixes with cost and what each one unlocks.

Read first:

- `docs/hackathon_brief.md`: rules, judging criteria, problem, demo flow, scope
- `docs/data_dictionary.md`: every processed table, its columns, join keys and limitations
- `docs/validation_report.md`: data checks and known data problems

## Rules

1. **The demo must not break.** The core path (address to ranked fixes) is plain code and local data. Any AI or network step needs a fallback (cached result or blank checklist) so the app still finishes.
2. **Work from `data/processed/`.** Never load raw downloads, full GIS files or the FEMA national table into an assistant's context. To change processed data, edit `scripts/02_process.py` and rerun it rather than hand-editing outputs.
3. **Label assumptions.** Fix costs and discount sizes are not public. Anything assumed must be marked as such in the data and in the app. Never fill a blank in `measures.csv`, `discounts.csv` or `grants.csv` without a source or an explicit assumption flag.
4. **The AI never invents numbers.** Model calls may read an image or rewrite numbers the code computed; they must not produce costs, discounts or insurer names.
5. **Respect the data warnings** in `docs/validation_report.md`, for example: DINS `Unknown` values and outcome fields leak the label, so they must not be model features; "no hazard zone" does not mean no risk.
6. **Secrets stay out of the repo.** API keys come from environment variables (for example `ANTHROPIC_API_KEY`) or a git-ignored `.env`.
7. **Essential features first.** Build the core demo before anything marked High or lower in the Vision & Design doc. Ask the team before widening scope.

## Layout

```
scripts/01_download.py   download raw sources to data/raw/ (git-ignored)
scripts/02_process.py    build data/processed/ (LA County scope)
scripts/03_validate.py   checks, writes docs/validation_report.md
scripts/utils.py         geocode(address) and area_context(address) helpers
data/processed/          tables the app reads (parquet, GeoParquet, CSV)
data/manual/             hand-downloaded inputs (HUD crosswalks)
docs/                    brief, data dictionary, validation report
src/msba_vibathon_2026/  app logic:
  policy_extract.py      policy PDF -> fields (any LLM via llm.py + pdfplumber quote check), spec in docs/policy_extraction_spec.md
  gaps.py                coverage gap rules
  assess_stub.py         placeholder assess() until the model replaces it (contract in docs/inputs_and_contract.md)
app.py                   Streamlit app
data/demo/               cached lookups and extractions so the demo runs offline
data/samples/policies/   synthetic declarations pages + answer_key.json
```

## Running

Python 3.14 with `uv`:

```
uv sync
uv run streamlit run app.py              # the app
uv run python scripts/03_validate.py     # data checks
```

Reading new policy PDFs needs one AI key: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY` (plus `LLM_MODEL` for OpenAI or Gemini, and `uv add openai` / `uv add google-genai`). See `src/msba_vibathon_2026/llm.py`. Without it, only the cached sample PDFs work and the manual form is the fallback.

## Git

Three people commit to `main` during the day. Pull before you push, keep commits small, and do not rewrite shared history. Commit only what the whole team needs; personal notes stay outside the repo.
