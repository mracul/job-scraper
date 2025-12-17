"""AI API payload construction and request handling."""

from typing import Dict, Any, List, Optional, Mapping, Iterable
from dataclasses import dataclass
import hashlib
import json


@dataclass
class AIPayload:
    """Container for AI API request components."""
    url: str
    headers: Dict[str, str]
    payload: Dict[str, Any]


@dataclass
class TruncationInfo:
    """Information about data truncation for UI display."""
    categories_truncated: bool
    total_categories: int
    included_categories: int
    terms_per_category_truncated: Dict[str, bool]
    total_terms_per_category: Dict[str, int]
    included_terms_per_category: Dict[str, int]


@dataclass
class UIModel:
    """Data model for UI rendering of AI summary context."""
    scope: str
    total_jobs: int
    search_context: Dict[str, Any]
    categories: Dict[str, Dict[str, Any]]
    analysis_text: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None


def build_ai_bundle(
    scope: str,
    *,
    analysis_text: Optional[str] = None,
    analysis_json: Optional[Dict[str, Any]] = None,
    overview: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
    limits: Optional[Dict[str, Any]] = None,
    category_labels: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Build comprehensive AI bundle containing LLM input, UI model, fingerprint, and truncation info.

    Args:
        scope: Label describing the scope (e.g., "single run", "compiled runs")
        analysis_text: Human-readable analysis text (preferred input)
        analysis_json: Structured analysis data (fallback/legacy)
        overview: Overview data with summary and search context
        meta: Metadata about the analysis
        limits: Configuration limits (top_n_per_category, etc.)
        category_labels: Mapping of category keys to display labels

    Returns:
        Dict containing:
        - llm_input: What gets sent to the LLM
        - ui_model: Data for UI rendering
        - fingerprint: Hash for caching
        - truncation: Explicit truncation information
    """
    # Extract parameters with defaults
    top_n_per_category = (limits or {}).get("top_n_per_category", 25)
    category_labels = category_labels or {}

    # Build UI model and truncation info
    ui_model, truncation = _build_ui_model_and_truncation(
        scope=scope,
        analysis_text=analysis_text,
        analysis_json=analysis_json,
        overview=overview,
        meta=meta,
        top_n_per_category=top_n_per_category,
        category_labels=category_labels,
    )

    # Build LLM input
    llm_input = _build_llm_input(
        analysis_text=analysis_text,
        analysis_json=analysis_json,
        ui_model=ui_model,
        meta=meta,
    )

    # Generate fingerprint for caching
    fingerprint = _generate_fingerprint(llm_input)

    return {
        "llm_input": llm_input,
        "ui_model": ui_model,
        "fingerprint": fingerprint,
        "truncation": truncation,
    }


def _build_ui_model_and_truncation(
    *,
    scope: str,
    analysis_text: Optional[str],
    analysis_json: Optional[Dict[str, Any]],
    overview: Optional[Dict[str, Any]],
    meta: Optional[Dict[str, Any]],
    top_n_per_category: int,
    category_labels: Mapping[str, str],
) -> tuple[UIModel, TruncationInfo]:
    """Build UI model and truncation info from input data."""
    # Extract data from overview or analysis_json
    total_jobs = 0
    summary = {}
    search_context = {}

    if overview:
        total_jobs = overview.get("total_jobs", 0)
        summary = overview.get("summary", {})
        search_context = overview.get("search", {})
    elif analysis_json:
        total_jobs = analysis_json.get("total_jobs", 0)
        summary = analysis_json.get("summary", {})
        search_context = analysis_json.get("search", {})

    # Build categories with truncation tracking
    categories_payload = {}
    terms_per_category_truncated = {}
    total_terms_per_category = {}
    included_terms_per_category = {}

    categories_truncated = False
    total_categories = len(category_labels)
    included_categories = 0

    for cat_key, cat_label in category_labels.items():
        items = (summary or {}).get(cat_key, {}) or {}
        total_terms = len(items)
        limit = max(1, int(top_n_per_category))
        top_items = sorted(items.items(), key=lambda t: t[1], reverse=True)[:limit] if items else []

        if total_terms > 0:
            included_categories += 1

        truncated = len(items) > len(top_items)
        categories_payload[cat_key] = {
            "label": cat_label,
            "total_unique": total_terms,
            "included": len(top_items),
            "truncated": truncated,
            "top": [
                {
                    "term": term,
                    "count": int(count),
                    "pct": round((float(count) / float(total_jobs) * 100.0), 1) if total_jobs else 0.0,
                }
                for term, count in top_items
            ],
        }

        terms_per_category_truncated[cat_key] = truncated
        total_terms_per_category[cat_key] = total_terms
        included_terms_per_category[cat_key] = len(top_items)

    ui_model = UIModel(
        scope=scope,
        total_jobs=int(total_jobs or 0),
        search_context=search_context,
        categories=categories_payload,
        analysis_text=analysis_text,
        meta=meta,
    )

    truncation = TruncationInfo(
        categories_truncated=categories_truncated,
        total_categories=total_categories,
        included_categories=included_categories,
        terms_per_category_truncated=terms_per_category_truncated,
        total_terms_per_category=total_terms_per_category,
        included_terms_per_category=included_terms_per_category,
    )

    return ui_model, truncation


def _build_llm_input(
    *,
    analysis_text: Optional[str],
    analysis_json: Optional[Dict[str, Any]],
    ui_model: UIModel,
    meta: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the input payload sent to the LLM."""
    if analysis_text:
        # Prefer human-readable analysis text
        user_prompt = (
            "Here is a job requirements analysis report for the user's search. "
            "Use ONLY the report text and the metadata block to produce the requested summary.\n\n"
            f"METADATA_JSON={json.dumps(meta if isinstance(meta, dict) else {}, indent=2)}\n\n"
            f"REQUIREMENTS_ANALYSIS_TXT=\n{analysis_text.strip()}"
        )
    else:
        # Fallback to structured JSON data
        user_prompt = (
            "Here is aggregated job-requirement data (counts and consolidated percentages) for the user's search. "
            "Use it to produce the requested summary.\n\n"
            f"DATA_JSON={json.dumps(ui_model.__dict__, indent=2)}"
        )

    return {
        "user_prompt": user_prompt,
        "system_prompt": None,  # Will be set when building actual API payload
        "context": {
            "scope": ui_model.scope,
            "total_jobs": ui_model.total_jobs,
            "search_context": ui_model.search_context,
        }
    }


def _generate_fingerprint(llm_input: Dict[str, Any]) -> str:
    """Generate a hash fingerprint for caching based on LLM input."""
    # Create a stable string representation for hashing
    fingerprint_data = {
        "user_prompt": llm_input.get("user_prompt", ""),
        "context": llm_input.get("context", {}),
    }
    fingerprint_str = json.dumps(fingerprint_data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(fingerprint_str.encode('utf-8')).hexdigest()[:16]


def build_openai_headers(api_key: str) -> Dict[str, str]:
    """Build headers for OpenAI API requests."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }


def build_openai_payload(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int
) -> Dict[str, Any]:
    """Build payload for OpenAI API requests."""
    return {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
        "max_output_tokens": max_output_tokens,
    }


def build_ai_request_payload(
    *,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_output_tokens: int
) -> AIPayload:
    """Build complete AI API request payload for OpenAI."""
    return AIPayload(
        url="https://api.openai.com/v1/responses",
        headers=build_openai_headers(api_key),
        payload=build_openai_payload(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_output_tokens=max_output_tokens
        )
    )


def extract_response_text(response_data: Dict[str, Any]) -> str:
    """Extract text content from OpenAI API response."""
    parts: List[str] = []
    for out in response_data.get("output", []) or []:
        for content in out.get("content", []) or []:
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content.get("text"))

    text = "".join(parts).strip()
    if not text:
        # Fallback for unexpected response shapes
        text = (response_data.get("output_text") or "").strip()

    return text