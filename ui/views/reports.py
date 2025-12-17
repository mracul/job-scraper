"""
Reports view module.
Contains all report-related rendering functions extracted from streamlit_app.py
"""

import streamlit as st
from pathlib import Path
import shutil
from datetime import datetime
from typing import List, Dict, Any

# Import dependencies
from ui.components.page_header import render_page_header
from ui.components.run_list_table import render_run_list_table
from ui.components.bulk_action_bar import render_bulk_action_bar
from ai_summary_ui import render_ai_summary_block
from ui_core import load_settings
from storage.compiled_report_store import (
    build_compiled_report_payload,
    build_runs_fingerprint,
    compiled_report_path,
    is_matching_compiled_report,
    load_compiled_report,
    save_compiled_report_atomic,
)
from ai.ai_payloads import build_ai_bundle
from ui.io_cache import (
    load_analysis,
    load_requirements_analysis_txt,
    _get_run_search_meta,
    _load_jobs_csv_cached,
    load_jobs_csv,
)
from ui.utils import _truncate_text
from ui.constants import CATEGORY_LABELS


"""
Reports view module.
Contains all report-related rendering functions extracted from streamlit_app.py
"""

import streamlit as st
from pathlib import Path
import shutil
from datetime import datetime
from typing import List, Dict, Any

# Import dependencies
from ui.components.page_header import render_page_header
from ui.components.run_list_table import render_run_list_table
from ui.components.bulk_action_bar import render_bulk_action_bar
from ai_summary_ui import render_ai_summary_block
from ui_core import load_settings
from storage.compiled_report_store import (
    build_compiled_report_payload,
    build_runs_fingerprint,
    compiled_report_path,
    is_matching_compiled_report,
    load_compiled_report,
    save_compiled_report_atomic,
)
from ai.ai_payloads import build_ai_bundle
from ui.io_cache import (
    load_analysis,
    load_requirements_analysis_txt,
    _get_run_search_meta,
    _load_jobs_csv_cached,
    load_jobs_csv,
)
from ui.utils import _truncate_text
from ui.constants import CATEGORY_LABELS

# Import functions that are still in streamlit_app.py
# These will need to be imported when this module is used
def list_runs():
    """Placeholder - will be imported from main app"""
    pass

def navigate_to(*args, **kwargs):
    """Placeholder - will be imported from main app"""
    pass

def _normalize_navigation_state():
    """Placeholder - will be imported from main app"""
    pass

def render_breadcrumb():
    """Placeholder - will be imported from main app"""
    pass

# Other dependencies
STATE_DIR = Path("state")  # This should be imported properly


def render_reports_page():
    """Render the reports page."""
    _normalize_navigation_state()
    render_breadcrumb()

    if st.session_state.view_mode == "compiled_overview":
        render_compiled_overview()
        return

    if st.session_state.selected_run:
        if st.session_state.view_mode == "job_detail":
            render_job_detail_view()
        elif st.session_state.view_mode == "explorer":
            render_job_explorer()
        else:
            render_report_overview()
    else:
        render_report_list()


def render_report_list():
    """Render the list of available reports."""
    runs = list_runs()

    # Header row with placeholders for compile/delete buttons (rendered after checkbox loop)
    header_col, compile_col, delete_col = st.columns([3, 1, 1])
    with header_col:
        st.header("📂 Reports")
    compile_placeholder = compile_col.empty()
    delete_placeholder = delete_col.empty()

    if not runs:
        st.info("No reports found. Start a new scraping run to generate reports.")
        if st.button("🚀 Start New Run"):
            navigate_to("new_run")
        return

    selected_paths: list[str] = []

    for run in runs:
        col0, col1, col2, col3 = st.columns([0.6, 3, 1, 1])

        with col0:
            checked = st.checkbox(
                f"Select report: {run['name']}",
                value=(str(run["path"]) in st.session_state.selected_reports),
                key=f"sel_{run['name']}",
                label_visibility="hidden"
            )
            if checked:
                selected_paths.append(str(run["path"]))

        with col1:
            # Build display label
            if run["keywords"] and run["keywords"] != "Not specified":
                label = f"**{run['keywords']}**"
                if run["location"] and run["location"] != "Not specified":
                    label += f" — {run['location']}"
            else:
                label = f"**{run['name']}**"

            st.markdown(label)

            # Metadata line
            meta_parts = []
            if run["job_count"]:
                meta_parts.append(f"{run['job_count']} jobs")
            if run["timestamp"]:
                meta_parts.append(run["timestamp"].strftime("%m/%d %H:%M"))
            if run["has_analysis"]:
                meta_parts.append("✅")
            else:
                meta_parts.append("❌")

            st.caption(" • ".join(meta_parts))
        with col2:
            if st.button("View", key=f"view_{run['name']}", use_container_width=True):
                navigate_to(
                    "reports",
                    selected_run=str(run["path"]),
                    view_mode="overview",
                    viewing_job_id=None,
                    selected_filters={},
                    filter_mode="any",
                    search_text=""
                )
                st.rerun()

        with col3:
            if st.button("Explore", key=f"explore_{run['name']}", use_container_width=True):
                navigate_to(
                    "reports",
                    selected_run=str(run["path"]),
                    view_mode="explorer",
                    viewing_job_id=None,
                    selected_filters={},
                    filter_mode="any",
                    search_text=""
                )
                st.rerun()

        st.divider()

    st.session_state.selected_reports = selected_paths

    # Render compile/delete buttons now that selection is determined
    compile_label = "🧩 Compile" if not selected_paths else f"🧩 Compile ({len(selected_paths)})"
    compile_disabled = len(selected_paths) == 0
    with compile_placeholder:
        if st.button(
            compile_label,
            key="compile_button",
            use_container_width=True,
            type="primary",
            disabled=compile_disabled,
        ):
            # Detect whether a matching compiled report already exists for this exact selection.
            # This avoids unnecessary compilation work and lets the compiled page show a clear notice.
            try:
                run_paths = [Path(p) for p in selected_paths]
                run_names = [p.name for p in run_paths]
                fingerprint = build_runs_fingerprint(run_paths)
                report_path = compiled_report_path(STATE_DIR, run_names=run_names)
                cached_report = load_compiled_report(report_path)
                st.session_state.compiled_preexisting = bool(
                    cached_report
                    and is_matching_compiled_report(cached_report, run_names=run_names, fingerprint=fingerprint)
                )
            except Exception:
                st.session_state.compiled_preexisting = False
            navigate_to(
                "reports",
                selected_run=None,
                view_mode="compiled_overview",
                viewing_job_id=None,
                compiled_runs=list(selected_paths),
            )
            st.rerun()
    delete_disabled = len(selected_paths) == 0
    with delete_placeholder:
        if st.button(
            "🗑️ Delete",
            key="multi_delete_button",
            use_container_width=True,
            disabled=delete_disabled,
        ):
            st.session_state.delete_candidates = list(selected_paths)
            st.session_state.delete_modal_open = True
            st.rerun()

    st.caption("Tip: Use browser back/forward to move between views.")

    # Confirmation dialog for deleting selected reports
    if st.session_state.delete_modal_open:
        def _perform_delete() -> list[str]:
            deleted: list[str] = []
            for run_path in st.session_state.delete_candidates:
                path_obj = Path(run_path)
                try:
                    if path_obj.exists() and path_obj.is_dir():
                        shutil.rmtree(path_obj)
                        deleted.append(str(path_obj))
                except Exception:
                    pass

            # Clear cache so list updates immediately
            list_runs.clear()

            st.session_state.selected_reports = [p for p in st.session_state.selected_reports if p not in deleted]
            st.session_state.compiled_runs = [p for p in st.session_state.compiled_runs if p not in deleted]
            return deleted

        if hasattr(st, "dialog"):
            @st.dialog("Confirm deletion")
            def _delete_dialog():
                st.warning("⚠️ **Confirm Deletion**")
                st.write("This will permanently delete the selected report folders:")
                for run_path in st.session_state.delete_candidates:
                    st.write(f"• {Path(run_path).name}")

                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("✓ Confirm Delete", type="primary", use_container_width=True, key="dlg_confirm_delete"):
                        deleted = _perform_delete()
                        if st.session_state.selected_run in deleted:
                            navigate_to(
                                "reports",
                                selected_run=None,
                                view_mode="overview",
                                viewing_job_id=None,
                                selected_filters={},
                                filter_mode="any",
                                search_text="",
                            )
                        st.session_state.delete_candidates = []
                        st.session_state.delete_modal_open = False
                        st.rerun()
                with col_cancel:
                    if st.button("✗ Cancel", use_container_width=True, key="dlg_cancel_delete"):
                        st.session_state.delete_modal_open = False
                        st.session_state.delete_candidates = []
                        st.rerun()

            _delete_dialog()
        else:
            st.markdown("---")
            st.warning("⚠️ **Confirm Deletion**")
            st.write("This will permanently delete the selected report folders:")
            for run_path in st.session_state.delete_candidates:
                st.write(f"• {Path(run_path).name}")
            col_confirm, col_cancel, _ = st.columns([1, 1, 2])
            with col_confirm:
                if st.button("✓ Confirm Delete", type="primary", use_container_width=True):
                    deleted = _perform_delete()
                    if st.session_state.selected_run in deleted:
                        navigate_to(
                            "reports",
                            selected_run=None,
                            view_mode="overview",
                            viewing_job_id=None,
                            selected_filters={},
                            filter_mode="any",
                            search_text="",
                        )
                    st.session_state.delete_candidates = []
                    st.session_state.delete_modal_open = False
                    st.rerun()
            with col_cancel:
                if st.button("✗ Cancel", use_container_width=True):
                    st.session_state.delete_modal_open = False
                    st.session_state.delete_candidates = []
                    st.rerun()


# TODO: Add render_report_overview and render_compiled_overview functions

def render_report_overview():
    """Placeholder for render_report_overview - to be implemented"""
    st.info("Report overview rendering - to be extracted from streamlit_app.py")

def render_compiled_overview():
    """Placeholder for render_compiled_overview - to be implemented"""
    st.info("Compiled overview rendering - to be extracted from streamlit_app.py")

def render_job_detail_view():
    """Placeholder for render_job_detail_view - to be implemented"""
    st.info("Job detail view rendering - to be implemented")

def render_job_explorer():
    """Placeholder for render_job_explorer - to be implemented"""
    st.info("Job explorer rendering - to be implemented")