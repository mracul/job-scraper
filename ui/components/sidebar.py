# ui/components/sidebar.py
"""
Sidebar component for global navigation and app status.
"""

import streamlit as st

from ui.navigation.actions import navigate_to
from ui_core import list_runs, load_run_state


def render_sidebar() -> None:
    """Render the application sidebar with navigation and status."""
    with st.sidebar:
        st.title("🔍 Job Scraper")
        st.markdown("---")

        # Show running indicator if scrape is in progress
        active_run = load_run_state()
        if active_run or st.session_state.run_process is not None:
            st.warning("🔄 Scrape running...")
            if st.button("View Progress", use_container_width=True, type="primary"):
                navigate_to("new_run")
            st.markdown("---")
        else:
            # Quick stats
            runs = list_runs()
            st.caption(f"📊 {len(runs)} report(s) available")

            if runs:
                total_jobs = sum(r["job_count"] for r in runs)
                st.caption(f"📋 {total_jobs} total jobs scraped")

        # Navigation
        nav_options = {
            "overview": "📈 Overview",
            "reports": "📂 Reports",
            "new_run": "🚀 New Run",
            "settings": "⚙️ Settings"
        }

        for key, label in nav_options.items():
            if st.button(label, use_container_width=True,
                        type="primary" if st.session_state.page == key else "secondary"):
                if key == "reports":
                    navigate_to(
                        "reports",
                        selected_run=None,
                        view_mode="overview",
                        viewing_job_id=None,
                        selected_filters={},
                        filter_mode="any",
                        search_text=""
                    )
                else:
                    navigate_to(key)

        st.markdown("---")