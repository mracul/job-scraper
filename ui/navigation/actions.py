# ui/navigation/actions.py
"""
Navigation actions for the job scraper app.
Centralized functions for changing navigation state and URL.
"""

from typing import Optional

from .state import apply_state, defaults, _st
from .url_sync import sync_url_with_state


def navigate_to(page: str, **kwargs) -> None:
    """Navigate to a page with optional state parameters."""
    st = _st()
    # Start with defaults for the target page
    new_state = defaults()
    new_state["page"] = page

    # Apply any provided kwargs
    for key, value in kwargs.items():
        new_state[key] = value

    # Apply the new state
    apply_state(new_state)

    # Sync to URL
    sync_url_with_state()

    # Trigger rerun to show new page
    st.rerun()


def open_report(run_id: str) -> None:
    """Navigate to a specific report overview."""
    navigate_to(
        "reports",
        selected_run=run_id,
        view_mode="overview",
        viewing_job_id=None,
        selected_filters={},
        filter_mode="any",
        search_text=""
    )


def open_jobs(run_id: str) -> None:
    """Navigate to the jobs explorer for a specific run."""
    navigate_to(
        "reports",
        selected_run=run_id,
        view_mode="explorer",
        viewing_job_id=None,
        selected_filters={},
        filter_mode="any",
        search_text=""
    )


def open_job_detail(run_id: str, job_id: int) -> None:
    """Navigate to a specific job detail view."""
    navigate_to(
        "reports",
        selected_run=run_id,
        view_mode="job_detail",
        viewing_job_id=job_id,
        selected_filters={},
        filter_mode="any",
        search_text=""
    )


def back_to_reports() -> None:
    """Navigate back to the reports list."""
    navigate_to(
        "reports",
        selected_run=None,
        view_mode="overview",
        viewing_job_id=None,
        selected_filters={},
        filter_mode="any",
        search_text=""
    )