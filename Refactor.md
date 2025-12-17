Refactor Runbook (helpers currently in streamlit_app.py)
Step 0 — Branch + baseline
git checkout -b refactor/ai-summary-split
streamlit run streamlit_app.py

Step 1 — Create new files

At repo root, create:

ai_summary_core.py

ai_summary_ui.py

Step 2 — Move constants + helpers into ai_summary_core.py

From streamlit_app.py, cut/paste these into ai_summary_core.py:

Put at top of ai_summary_core.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib
import json

Move these items from streamlit_app.py into ai_summary_core.py

AI_SUMMARY_SYSTEM_PROMPT

AI_SUMMARY_MAX_OUTPUT_TOKENS

load_settings (only if it doesn’t render UI; if it uses st.*, keep it in UI file and pass ai_model in)

_hash_payload

_load_cached_ai_summary

_save_cached_ai_summary

_generate_ai_summary_text

Rule: ai_summary_core.py must NOT import streamlit and must NOT call st.*.

If _generate_ai_summary_text currently uses Streamlit secrets/session/etc, refactor it so it takes everything as arguments or reads environment/settings without Streamlit.

Step 3 — Add a clean “core API” (agent should implement)

In ai_summary_core.py, ensure these functions exist and are imported by UI:

def compute_input_hash(ai_input: dict, model: str, max_output_tokens: int, system_prompt: str) -> str:
    payload = {
        "ai_input": ai_input,
        "model": model,
        "max_output_tokens": max_output_tokens,
        "system_prompt": system_prompt,
    }
    return _hash_payload(payload)

def resolve_cache_state(cached: dict | None, input_hash: str) -> tuple[str | None, str | None]:
    """
    Returns (cached_text, cache_status) where cache_status is: 'current' | 'outdated' | None
    """
    if not cached:
        return None, None
    if cached.get("input_hash") == input_hash:
        return cached.get("summary"), "current"
    if cached.get("summary"):
        return cached.get("summary"), "outdated"
    return None, None


(This is optional but HIGH ROI: removes duplication and future errors.)

Step 4 — Move the UI component into ai_summary_ui.py

In ai_summary_ui.py, add:

from pathlib import Path
import time
import streamlit as st

from ai_summary_core import (
    AI_SUMMARY_SYSTEM_PROMPT,
    AI_SUMMARY_MAX_OUTPUT_TOKENS,
    AI_MAX_N,
    AI_MAX_COMPILED_N,
    _load_cached_ai_summary,
    _save_cached_ai_summary,
    _generate_ai_summary_text,
    compute_input_hash,
    resolve_cache_state,
)

from ui_core import load_settings  # ONLY if load_settings uses streamlit; otherwise import from core


Then paste your full working function into this file and rename it:

_render_ai_summary_block → render_ai_summary_block

Inside that function:

replace your input_hash = _hash_payload(cache_basis) with:

input_hash = compute_input_hash(ai_input, ai_model, AI_SUMMARY_MAX_OUTPUT_TOKENS, AI_SUMMARY_SYSTEM_PROMPT)


replace your cache state logic with:

cached_text, cache_status = resolve_cache_state(cached, input_hash)


Everything else can remain identical.

Step 5 — Update streamlit_app.py

Add import:

from ai_summary_ui import render_ai_summary_block


Replace call sites:

render_ai_summary_block(cache_path=..., ai_input=..., auto_generate=True)


Delete the old _render_ai_summary_block from streamlit_app.py.

Step 6 — Run + fix any import misses
streamlit run streamlit_app.py


If something is missing, it will be one of:

helper still left in streamlit_app.py

helper uses st.* and needs to stay in UI layer

Rule: keep moving helpers into ai_summary_core.py until UI imports cleanly.

Step 7 — Commit
git add ai_summary_core.py ai_summary_ui.py streamlit_app.py
git commit -m "Extract AI Summary into core + UI modules"

Agent Guardrails (must follow)

Do not import anything from streamlit_app.py into the new modules.

ai_summary_core.py must be streamlit-free (no import streamlit as st).

UI file owns session state keys + buttons + CSS.

Core file owns hashing/cache read/write/generation.

If you paste the signatures of your current helper functions (just the def ... lines) I can tell you exactly which ones are “safe core” vs “UI-coupled” so your agent doesn’t waste cycles.

should we also include the ai max n and ai max compiled n in ai summary ui?
yes or no i will add it

Yes — include them in ai_summary_ui.

Why (short + decisive):

They are UI-driven constraints (how much the user sees / how much you compile for display), not model-agnostic logic.

They directly affect rendering, truncation, overflow, and UX guarantees.

Keeping them in core would couple your core logic to presentation concerns (which you just worked hard to separate).

Rule of thumb (use this going forward):

❌ Core: what is generated, cached, hashed, saved

✅ UI: how much, when, how it’s shown, how it’s constrained

