"""
Settings page view.
"""

import streamlit as st

from ui.components.page_header import render_page_header
from ui_core import DEFAULT_SETTINGS, load_settings, save_settings

from ui.navigation.breadcrumbs import build_breadcrumbs
from ui.navigation.state import snapshot_state


def render_settings_page():
    """Render the settings page."""
    # Canonical page layout: PageHeader, ActionBar (optional), content
    breadcrumbs = build_breadcrumbs(snapshot_state())
    render_page_header(
        path=breadcrumbs,
        title="Settings",
        subtitle="Configure application preferences and defaults"
    )

    settings = load_settings()
    scraper_settings = settings.get("scraper", {})
    ui_settings = settings.get("ui", {})
    ai_settings = settings.get("ai", {})

    with st.form("settings_form"):
        st.subheader("AI Settings")

        ai_model_options = ["gpt-5-mini", "gpt-5.1", "gpt-5.2"]
        current_model = ai_settings.get("model", "gpt-5-mini")
        model_index = ai_model_options.index(current_model) if current_model in ai_model_options else 0

        ai_model = st.selectbox(
            "AI Model for Summaries",
            options=ai_model_options,
            index=model_index,
            help="Select the OpenAI model to use for generating report summaries"
        )

        st.markdown("---")
        st.subheader("Default Search Parameters")

        col1, col2 = st.columns(2)

        with col1:
            default_keywords = st.text_input(
                "Default Keywords",
                value=ui_settings.get("default_keywords", "help desk it")
            )

        with col2:
            default_location = st.text_input(
                "Default Location",
                value=ui_settings.get("default_location", "Auburn NSW")
            )

        st.markdown("---")
        st.subheader("Scraper Defaults")

        col1, col2, col3 = st.columns(3)

        with col1:
            pages = st.number_input(
                "Default Max Pages",
                min_value=1,
                max_value=20,
                value=scraper_settings.get("pages", 3)
            )

            source = st.selectbox(
                "Default Source",
                options=["all", "seek", "jora"],
                index=["all", "seek", "jora"].index(scraper_settings.get("source", "all"))
            )

        with col2:
            workers = st.number_input(
                "Default Workers",
                min_value=1,
                max_value=20,
                value=scraper_settings.get("workers", 10),
                help="Recommended: 8-12 for 6-core/12-thread CPU, 4-6 for 4-core CPU"
            )

            delay = st.number_input(
                "Default Delay (seconds)",
                min_value=0.5,
                max_value=10.0,
                value=float(scraper_settings.get("delay", 1.5)),
                step=0.5
            )

        with col3:
            max_details = st.number_input(
                "Default Max Details",
                min_value=0,
                value=scraper_settings.get("max_details") or 0,
                help="0 = fetch all job details"
            )

            fuzzy = st.checkbox(
                "Enable Fuzzy Search by Default",
                value=scraper_settings.get("fuzzy", False)
            )

        col1, col2 = st.columns(2)

        with col1:
            visible = st.checkbox(
                "Show Browser by Default",
                value=scraper_settings.get("visible", False)
            )

        with col2:
            sequential = st.checkbox(
                "Sequential Mode by Default",
                value=scraper_settings.get("sequential", False)
            )

        st.markdown("---")

        col1, col2 = st.columns(2)

        with col1:
            if st.form_submit_button("💾 Save Settings", type="primary", use_container_width=True):
                new_settings = {
                    "scraper": {
                        "pages": pages,
                        "source": source,
                        "delay": delay,
                        "workers": workers,
                        "sequential": sequential,
                        "visible": visible,
                        "max_details": max_details if max_details > 0 else None,
                        "fuzzy": fuzzy
                    },
                    "ui": {
                        "default_keywords": default_keywords,
                        "default_location": default_location
                    },
                    "ai": {
                        "model": ai_model
                    },
                    # Preserve any existing bundles (or defaults) even though this form doesn't edit them.
                    "bundles": settings.get("bundles") or DEFAULT_SETTINGS.get("bundles", {}),
                }
                save_settings(new_settings)
                st.success("Settings saved!")
                st.rerun()

        with col2:
            if st.form_submit_button("🔄 Reset to Defaults", use_container_width=True):
                save_settings(DEFAULT_SETTINGS)
                st.success("Settings reset to defaults!")
                st.rerun()