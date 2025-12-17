# ui/navigation/state.py
"""
Centralized navigation state management for the job scraper app.
Defines the canonical navigation state keys and provides state manipulation functions.
"""

import streamlit as st
from typing import Dict, Any, Set

# Canonical navigation state keys
NAV_KEYS: Set[str] = {
    "page",            # "overview" | "reports" | "jobs" | "new_run" | "settings"
    "view_mode",       # e.g. "overview" | "detail" | "jobs"
    "selected_run",    # run id/slug
    "compiled_runs",   # list[str]
    "viewing_job_id",  # int | None
    "filter_mode",     # "any" | "all"
    "search_text",     # str
    "selected_filters" # dict[str, list[str]]
}


def snapshot_state() -> Dict[str, Any]:
    """Return a snapshot of only the navigation state keys."""
    return {key: st.session_state.get(key) for key in NAV_KEYS}


def apply_state(patch: Dict[str, Any]) -> None:
    """Apply a patch to session state, only for navigation keys."""
    for key, value in patch.items():
        if key in NAV_KEYS:
            st.session_state[key] = value


def normalize_state() -> None:
    """Coerce session state into a consistent navigation state.

    Streamlit reruns + URL sync can leave stale combinations (e.g. job_detail with no
    job id). Normalizing prevents incorrect components rendering.
    """
    page = st.session_state.get("page") or "reports"
    st.session_state.page = page

    # Non-reports pages should never keep report/explorer sub-state.
    if page != "reports":
        st.session_state.selected_run = None
        st.session_state.view_mode = "overview"
        st.session_state.viewing_job_id = None
        st.session_state.selected_filters = {}
        st.session_state.filter_mode = "any"
        st.session_state.search_text = ""
        return

    # Reports page: validate view_mode.
    view_mode = st.session_state.get("view_mode") or "overview"
    allowed = {"overview", "explorer", "job_detail", "compiled_overview"}
    if view_mode not in allowed:
        view_mode = "overview"
    st.session_state.view_mode = view_mode

    selected_run = st.session_state.get("selected_run")

    # Views that require a run.
    if view_mode in {"overview", "explorer", "job_detail"} and not selected_run:
        st.session_state.view_mode = "overview"
        st.session_state.viewing_job_id = None
        st.session_state.selected_filters = {}
        st.session_state.filter_mode = "any"
        st.session_state.search_text = ""
        _clear_report_filter_widgets()
        return

    # Explorer: never keep a selected job.
    if st.session_state.view_mode == "explorer":
        st.session_state.viewing_job_id = None

    # Job detail requires a job id.
    if st.session_state.view_mode == "job_detail":
        job_id = st.session_state.get("viewing_job_id")
        if not isinstance(job_id, int) or job_id <= 0:
            st.session_state.view_mode = "overview"
            st.session_state.viewing_job_id = None

    # Non-job detail views should not keep a job id.
    if st.session_state.view_mode != "job_detail":
        st.session_state.viewing_job_id = None


def defaults() -> Dict[str, Any]:
    """Return default values for navigation state."""
    return {
        "page": "reports",
        "selected_run": None,
        "view_mode": "overview",  # overview, explorer, job_detail
        "viewing_job_id": None,
        "selected_filters": {},  # {category: [terms]}
        "filter_mode": "any",  # "any" or "all"
        "search_text": "",
        "compiled_runs": [],  # list[str] of run folder paths
    }


def _clear_report_filter_widgets() -> None:
    """Clear any cached filter widget state."""
    # This function is kept for compatibility with existing code
    pass