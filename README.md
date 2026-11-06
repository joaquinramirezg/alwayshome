# AlwaysON

UCLA Anderson MSBA Vibathon 2026, theme 04 "Uninsurable". Helps California homeowners on the FAIR Plan find the fire-safety fixes that move them closest to affordable private insurance.

```
uv sync
uv run streamlit run app.py
```

Optional: set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `GEMINI_API_KEY` to let the app read new policy PDFs (details in `src/msba_vibathon_2026/llm.py`). See `AGENTS.md` and `docs/` for everything else.
