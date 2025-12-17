from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, Optional
import hashlib
import json


# --- Core constants and helpers (no Streamlit imports allowed) ---

AI_SUMMARY_SYSTEM_PROMPT = """
# (Paste the full prompt here in next step)
"""

AI_SUMMARY_MAX_OUTPUT_TOKENS = 2000

def _hash_payload(payload) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _load_cached_ai_summary(cache_path: Path) -> dict | None:
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "summary" in data and "input_hash" in data:
            return data
        return None
    except (json.JSONDecodeError, IOError, OSError):
        try:
            cache_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None

def _save_cached_ai_summary(cache_path: Path, data: dict) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = cache_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.replace(cache_path)
    except Exception:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def compute_input_hash(ai_input: dict, model: str, max_output_tokens: int, system_prompt: str) -> str:
    payload = {
        "ai_input": ai_input,
        "model": model,
        "max_output_tokens": max_output_tokens,
        "system_prompt": system_prompt,
    }
    return _hash_payload(payload)

# Core wrapper for generation: accepts a callable (e.g., from UI)
def generate_ai_summary(ai_input: dict, generate_fn) -> str:
    """
    Core entrypoint for AI summary generation. Accepts a callable (generate_fn) for actual generation logic.
    This allows the UI to pass its own function (e.g., _generate_ai_summary_text).
    """
    return generate_fn(ai_input)

def resolve_cache_state(cached: dict | None, input_hash: str) -> tuple[str | None, str | None]:
    if not cached:
        return None, None
    if cached.get("input_hash") == input_hash:
        return cached.get("summary"), "current"
    if cached.get("summary"):
        return cached.get("summary"), "outdated"
    return None, None

# _generate_ai_summary_text will be moved here if it does not use st.*
