# ui/router.py
"""
Thin router for dispatching to page views.
Maps page names to their respective view functions.
"""

import streamlit as st

from ui.views.overview import render_overview_page
from ui.views.reports import render_reports_page
from ui.views.jobs import render_job_explorer, render_job_detail_view
from ui.views.new_run import render_new_run_page
from ui.views.settings import render_settings_page


# Route mapping: page name -> view function
ROUTES = {
    "overview": render_overview_page,
    "reports": render_reports_page,
    "jobs": render_job_explorer,  # This might need adjustment based on actual function names
    "new_run": render_new_run_page,
    "settings": render_settings_page,
}


def dispatch() -> None:
    """Dispatch to the appropriate view based on current page state."""
    page = st.session_state.get("page", "overview")
    view = ROUTES.get(page, render_overview_page)
    view()