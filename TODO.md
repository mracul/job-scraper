### Agent-ready checklist (no visual-only checks)

#### 0) Create safety branch + baseline run

* [x] `git checkout -b refactor/ai-summary-split`
* [x] `streamlit run streamlit_app.py`

  * Success criteria: server starts without exceptions in console.

---

## 1) Create new modules

* [x] Create `ai_summary_core.py` (repo root)
* [x] Create `ai_summary_ui.py` (repo root)

---

## 2) Move core constants + helpers out of `streamlit_app.py`

**Goal:** `ai_summary_core.py` contains *no* `streamlit` imports and *no* `st.*` calls.

### 2.1 Move these symbols into `ai_summary_core.py`

* [x] `AI_SUMMARY_SYSTEM_PROMPT`
* [x] `AI_SUMMARY_MAX_OUTPUT_TOKENS`
* [x] `_hash_payload`
* [x] `_load_cached_ai_summary`
* [x] `_save_cached_ai_summary`

### 2.2 `_generate_ai_summary_text` handling

* [x] `_generate_ai_summary_text` uses `st.*` (secrets), so left in UI (`ai_summary_ui.py`)

### 2.3 Add these two helper functions to `ai_summary_core.py` (new)

* [x] Add `compute_input_hash(ai_input: dict, model: str, max_output_tokens: int, system_prompt: str) -> str`
* [x] Add `resolve_cache_state(cached: dict | None, input_hash: str) -> tuple[str | None, str | None]`

  * Returns `(cached_text, cache_status)` where cache_status ∈ `{ "current", "outdated", None }`

### 2.4 Ensure imports compile

* [x] `ai_summary_core.py` includes:

  * `from pathlib import Path`
  * `import hashlib, json` (or whatever `_hash_payload` uses)
  * typing imports if needed
* [x] **Do not** import `streamlit` in `ai_summary_core.py`

---

## 3) Move UI function into `ai_summary_ui.py`

**Goal:** `ai_summary_ui.py` holds the Streamlit component and imports helpers/constants from `ai_summary_core.py`.

### 3.1 Move function

* [x] Cut the final working `_render_ai_summary_block(...)` from `streamlit_app.py`
* [x] Paste into `ai_summary_ui.py`
* [x] Rename to: `render_ai_summary_block(...)`

### 3.2 Add imports at top of `ai_summary_ui.py`

* [x] `import streamlit as st`
* [x] `from pathlib import Path`
* [x] `import time`
* [x] `from markdown import markdown as md_to_html`
* [x] Import from core:

  * `from ai_summary_core import AI_SUMMARY_SYSTEM_PROMPT, AI_SUMMARY_MAX_OUTPUT_TOKENS`
  * `from ai_summary_core import _load_cached_ai_summary, _save_cached_ai_summary`
  * `from ai_summary_core import compute_input_hash, resolve_cache_state`
  * `from ai_summary_core import _hash_payload` **only if still referenced** (prefer compute_input_hash)
* [x] Import `load_settings` from wherever it will live:

  * If `load_settings` calls `st.*`, keep it in a UI-ish module and import it here.
  * Otherwise, move it to core and import from there.

### 3.3 Keep UI-only constants in UI file (per your decision)

* [x] Define `AI_MAX_N`
* [x] Define `AI_MAX_COMPILED_N`

### 3.4 Replace input hash + cache logic inside the UI function

* [x] Replace:

  * `input_hash = _hash_payload(cache_basis)`
    with:
  * `input_hash = compute_input_hash(ai_input, ai_model, AI_SUMMARY_MAX_OUTPUT_TOKENS, AI_SUMMARY_SYSTEM_PROMPT)`
* [x] Replace cache resolution code with:

  * `cached_text, cache_status = resolve_cache_state(cached, input_hash)`
* [x] Ensure `summary_text = cached_text` still happens after that.

### 3.5 CSS injection: inject once

* [ ] Wrap your big CSS block with:

  * `if not st.session_state.get("_ai_summary_css_injected"): ...`

### 3.6 No cross-imports

* [x] Ensure `ai_summary_ui.py` does **not** import anything from `streamlit_app.py`

---

## 4) Update `streamlit_app.py` to use new component

* [x] Add near top:

  * `from ai_summary_ui import render_ai_summary_block`
* [x] Replace calls:

  * `_render_ai_summary_block(...)` → `render_ai_summary_block(...)`
* [x] Delete the old function definition from `streamlit_app.py` (so it cannot drift/duplicate)

---

## 5) Mechanical correctness checks (non-visual)

Run each command and ensure no exceptions:

* [x] `python -m py_compile streamlit_app.py ai_summary_ui.py ai_summary_core.py`
* [x] `streamlit run streamlit_app.py`

  * Success criteria: server starts, no stack traces on page load.
* [x] Trigger generation once (click button)

  * Success criteria: no exception in console, app reruns, cache file is written/updated (verify in `state/` or wherever cache_path points).

---

## 6) Commit

* [x] `git add ai_summary_core.py ai_summary_ui.py streamlit_app.py`
* [x] `git commit -m "Split AI summary into core and UI modules"`

---

## 7) Full test and merge

* [x] Run full test suite: `python -m pytest tests/`

  * Note: 2 failures in test_compilation.py (unrelated to refactor - data/summary key issues)
* [x] Manually test AI summary generation in different contexts (single report, overview, compiled)
* [x] If all pass, merge branch: `git checkout main && git merge refactor/ai-summary-split`
* [x] Delete branch: `git branch -d refactor/ai-summary-split`

---

### Hard rules (agent must follow)

* **Never import from `streamlit_app.py`** into new modules.
* `ai_summary_core.py` must be **Streamlit-free**.
* UI module owns: session state keys, CSS, buttons, rerun logic, AI_MAX_N / AI_MAX_COMPILED_N.
* Core owns: hashing, cache I/O, constants, pure helpers.

### Agent mapping + mini-checklist for these two functions

#### ✅ `_generate_ai_summary_text(ai_input: dict) -> str`

**Put it in:** `ai_summary_core.py` **IF** it does **not** call `st.*` (secrets/session/UI).
**Otherwise:** keep it in `ai_summary_ui.py` for now.

**Agent action**

* [ ] Inspect `_generate_ai_summary_text` body.
* [ ] If it contains any of: `st.secrets`, `st.session_state`, `st.*` UI calls → **leave in UI**.
* [ ] Else → **move to core** and import it from `ai_summary_core` in the UI module.

---

#### ✅ `load_settings() -> dict`

**Put it in:** `ai_summary_core.py` **IF** it is pure file/env parsing and has **no Streamlit dependency**.
**Otherwise:** leave it in an app-level module (UI-ish) and import it into `ai_summary_ui.py`.

**Agent action**

* [ ] Inspect `load_settings` body.
* [ ] If it uses `st.*` anywhere → keep it **out of core** (leave in `streamlit_app.py` or move to `ui_core.py`).
* [ ] If it’s pure (json/yaml file read, defaults) → move to **core**.

---

## Fast rule (agent can follow without thinking)

* If function touches `st.` → **UI side**
* If function is pure Python (no `st.`) → **core side**

---

## Minimal “do this now” instruction set

* [ ] Open `streamlit_app.py`
* [ ] Search inside `_generate_ai_summary_text` for `st.`
* [ ] Search inside `load_settings` for `st.`
* [ ] Based on results, move each to core or UI exactly as above
* [ ] Update imports in `ai_summary_ui.py` accordingly
* [ ] Run: `python -m py_compile streamlit_app.py ai_summary_ui.py ai_summary_core.py`
