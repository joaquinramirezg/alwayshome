"""Provider-agnostic call: PDF + instructions + JSON schema in, parsed JSON out.

All three providers read PDFs natively (text layer plus page images) and support
JSON-schema-constrained output, so the schema, prompt and checks in policy_extract.py
are shared and only this adapter differs.

Choose with environment variables:
  LLM_PROVIDER = anthropic | openai | gemini   (default: the first one with a key set)
  LLM_MODEL    = model id                       (required for openai and gemini)
Keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY (or GOOGLE_API_KEY).
The openai and google-genai packages are optional: `uv add openai` or `uv add google-genai`.
"""
from __future__ import annotations

import base64
import json
import os

KEYS = {
    "anthropic": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
    "openai": ("OPENAI_API_KEY",),
    "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
}
DEFAULT_MODEL = {"anthropic": "claude-opus-5-5"}


class LLMUnavailable(RuntimeError):
    pass


def provider() -> str | None:
    chosen = os.environ.get("LLM_PROVIDER", "").lower().strip()
    if chosen:
        if chosen not in KEYS:
            raise LLMUnavailable(f"Unknown LLM_PROVIDER {chosen!r}; use one of {', '.join(KEYS)}.")
        return chosen if any(os.environ.get(k) for k in KEYS[chosen]) else None
    return next((p for p, keys in KEYS.items() if any(os.environ.get(k) for k in keys)), None)


def _model(p: str) -> str:
    m = os.environ.get("LLM_MODEL") or DEFAULT_MODEL.get(p)
    if not m:
        raise LLMUnavailable(f"Set LLM_MODEL to a {p} model id.")
    return m


def extract_json(pdf_bytes: bytes, system: str, instruction: str, schema: dict) -> tuple[dict, str]:
    """Return (parsed JSON, "provider/model"). Raises LLMUnavailable on any failure."""
    p = provider()
    if p is None:
        raise LLMUnavailable("No API key set (ANTHROPIC_API_KEY, OPENAI_API_KEY or GEMINI_API_KEY).")
    model = _model(p)
    try:
        text = {"anthropic": _anthropic, "openai": _openai, "gemini": _gemini}[p](
            pdf_bytes, system, instruction, schema, model)
        return json.loads(text), f"{p}/{model}"
    except LLMUnavailable:
        raise
    except ImportError as e:
        raise LLMUnavailable(f"{p} SDK not installed ({e.name}).") from e
    except Exception as e:  # network, auth, rate limit, bad JSON: caller falls back to manual entry
        raise LLMUnavailable(f"{p} extraction failed: {e}") from e


def _anthropic(pdf, system, instruction, schema, model) -> str:
    import anthropic

    r = anthropic.Anthropic().messages.create(
        model=model,
        max_tokens=16000,
        system=system,
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                            "data": base64.standard_b64encode(pdf).decode()}},
            {"type": "text", "text": instruction},
        ]}],
    )
    if r.stop_reason in ("refusal", "max_tokens"):
        raise LLMUnavailable(f"anthropic stopped early ({r.stop_reason}).")
    return next(b.text for b in r.content if b.type == "text")


def _openai(pdf, system, instruction, schema, model) -> str:
    from openai import OpenAI

    r = OpenAI().responses.create(
        model=model,
        instructions=system,
        input=[{"role": "user", "content": [
            {"type": "input_file", "filename": "policy.pdf",
             "file_data": "data:application/pdf;base64," + base64.standard_b64encode(pdf).decode()},
            {"type": "input_text", "text": instruction},
        ]}],
        text={"format": {"type": "json_schema", "name": "policy_fields", "schema": schema, "strict": True}},
    )
    return r.output_text


def _gemini(pdf, system, instruction, schema, model) -> str:
    from google import genai
    from google.genai import types

    r = genai.Client().models.generate_content(
        model=model,
        contents=[types.Part.from_bytes(data=pdf, mime_type="application/pdf"), instruction],
        config=types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema,
        ),
    )
    return r.text
