"""
Job Scraper - Streamlit UI
A web interface for running job scrapes and exploring results.
Phase 7.9: Thin Router + Full Navigation + Cleanup
"""

from __future__ import annotations

import json

import streamlit as st

from ui.components.sidebar import render_sidebar
from ui.constants import (
    CATEGORY_LABELS,
)
from ui.navigation.state import defaults, normalize_state
from ui.navigation.url_sync import apply_state_from_url, sync_url_with_state
from ui.router import dispatch
from ui.io_cache import load_analysis
from ui_core import build_ai_summary_input as _ui_build_ai_summary_input
from ui_core import merge_analyses as _ui_merge_analyses


# ============================================================================
# Session State
# ============================================================================


def init_session_state() -> None:
    """Initialize session state with navigation defaults and app flags."""
    nav_defaults = defaults()
    for key, value in nav_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if "run_process" not in st.session_state:
        st.session_state.run_process = None
    if "run_log_file" not in st.session_state:
        st.session_state.run_log_file = None
    if "delete_candidates" not in st.session_state:
        st.session_state.delete_candidates = []
    if "delete_modal_open" not in st.session_state:
        st.session_state.delete_modal_open = False
    if "last_url_state" not in st.session_state:
        st.session_state.last_url_state = None
    if "nav_seq" not in st.session_state:
        st.session_state.nav_seq = 0
    if "nav_origin" not in st.session_state:
        st.session_state.nav_origin = None
    if "overview_params" not in st.session_state:
        st.session_state.overview_params = None
    if "overview_cache_path" not in st.session_state:
        st.session_state.overview_cache_path = None
    if "overview_notice" not in st.session_state:
        st.session_state.overview_notice = None
    if "trigger_overview_generation" not in st.session_state:
        st.session_state.trigger_overview_generation = False
    if "trigger_overview_export" not in st.session_state:
        st.session_state.trigger_overview_export = False
    if "compiled_preexisting" not in st.session_state:
        st.session_state.compiled_preexisting = False


# ============================================================================
# UI Chrome
# ============================================================================


def inject_css() -> None:
    """Inject custom CSS for the application."""
    st.markdown(
        """
    <style>
    /* Custom styles for the job scraper app */
    .stButton button {
        border-radius: 6px;
    }
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        border-radius: 4px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    """Main entry point for the Streamlit app - thin router implementation."""
    st.set_page_config(
        page_title="Job Scraper",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # One-time initialization
    init_session_state()
    inject_css()

    # Navigation sync: apply URL state early, before rendering sidebar
    params = st.query_params
    params_str = json.dumps(dict(params) if params else {}, sort_keys=True)

    if st.session_state.get("last_url_state") != params_str:
        state_changed = apply_state_from_url()
        st.session_state.last_url_state = params_str
        if state_changed:
            normalize_state()
            st.rerun()

    # Render global sidebar navigation
    render_sidebar()

    # Normalize state (optional but recommended)
    normalize_state()

    # Dispatch to the appropriate view
    dispatch()

    # Sync URL at end of run
    sync_url_with_state()


# ============================================================================
# Test-facing wrappers
# ============================================================================


def _build_ai_summary_input(
    *,
    total_jobs: int,
    summary: dict,
    search_context: dict,
    scope_label: str,
    top_n_per_category: int = 25,
) -> dict:
    """Wrapper kept for backwards compatibility with tests."""
    return _ui_build_ai_summary_input(
        total_jobs=total_jobs,
        summary=summary,
        search_context=search_context,
        scope_label=scope_label,
        category_labels=CATEGORY_LABELS,
        top_n_per_category=top_n_per_category,
    )


def _merge_analyses(analyses: list[dict]) -> dict:
    """Merge multiple analyses using shared UI constants."""
    return _ui_merge_analyses(analyses, category_keys=CATEGORY_LABELS.keys())


if __name__ == "__main__":
    main()
