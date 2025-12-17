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
from ui.components.action_bar import render_action_bar
from ai_summary_ui import render_ai_summary_block
from ui_core import load_settings, list_runs
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

# Additional imports for overview functions
import hashlib
from collections import defaultdict
from ui_core import merge_analyses as _ui_merge_analyses, STATE_DIR
from ui.constants import AI_SUMMARY_TOP_N_SINGLE
from ui.constants import CATEGORY_LABELS

# Import job view functions
from ui.views.jobs import render_job_explorer, render_job_detail_view

# Import navigation functions
from ui.navigation.actions import navigate_to
from ui.navigation.breadcrumbs import build_breadcrumbs
from ui.navigation.state import snapshot_state

def render_breadcrumb():
    """Placeholder - will be imported from main app"""
    pass

# Other dependencies
STATE_DIR = Path("state")  # This should be imported properly


def render_reports_page():
    """Render the reports page."""
    _normalize_navigation_state()

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

    # Canonical page layout: PageHeader, ActionBar (optional), content
    breadcrumbs = build_breadcrumbs(snapshot_state())
    render_page_header(
        path=breadcrumbs,
        title="Reports",
        subtitle="Browse scrape runs. Select to view or compile results"
    )

    action_bar_placeholder = st.empty()

    if not runs:
        st.info("No reports found. Start a new scraping run to generate reports.")
        if st.button("🚀 Start New Run"):
            navigate_to("new_run")
        return

    st.session_state.setdefault("selected_reports", [])
    selected_paths: list[str] = []

    for run in runs:
        with st.container(border=True):
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
                if run["keywords"] and run["keywords"] != "Not specified":
                    label = f"**{run['keywords']}**"
                    if run["location"] and run["location"] != "Not specified":
                        label += f" — {run['location']}"
                else:
                    label = f"**{run['name']}**"

                st.markdown(label)

                meta_parts = []
                if run["job_count"]:
                    meta_parts.append(f"{run['job_count']} jobs")
                if run["timestamp"]:
                    meta_parts.append(run["timestamp"].strftime("%m/%d %H:%M"))
                meta_parts.append("✅" if run["has_analysis"] else "❌")

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
                        search_text="",
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
                        search_text="",
                    )
                    st.rerun()

    st.session_state.selected_reports = selected_paths

    compile_label = "Compile" if not selected_paths else f"Compile ({len(selected_paths)})"
    actions = [
        {
            "label": compile_label,
            "on_click": lambda: _handle_compile(selected_paths),
            "kind": "primary",
            "disabled": len(selected_paths) == 0,
            "help": "Select at least one report to compile",
        },
        {
            "label": "Delete",
            "on_click": lambda: _trigger_delete(selected_paths),
            "kind": "secondary",
            "disabled": len(selected_paths) == 0,
        },
        {
            "label": "Clear selection",
            "on_click": _clear_report_selection,
            "kind": "secondary",
            "disabled": len(selected_paths) == 0,
        },
    ]

    with action_bar_placeholder.container():
        render_action_bar(actions)

    st.caption("Tip: Use browser back/forward to move between views.")


def _handle_compile(selected_paths: list[str]) -> None:
    if not selected_paths:
        return
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


def _trigger_delete(selected_paths: list[str]) -> None:
    if not selected_paths:
        return
    st.session_state.delete_candidates = list(selected_paths)
    st.session_state.delete_modal_open = True
    st.rerun()


def _clear_report_selection() -> None:
    st.session_state.selected_reports = []
    st.rerun()

def render_report_overview():
    """Placeholder for render_report_overview - to be implemented"""
    st.info("Report overview rendering - to be extracted from streamlit_app.py")

def render_report_overview():
    """Render the overview of a selected report with charts."""
    run_path = Path(st.session_state.selected_run)
    analysis = load_analysis(run_path)
    
    # Get run metadata for breadcrumb
    keywords, location = _get_run_search_meta(run_path)
    run_display_name = f"{keywords} — {location}" if keywords and location else run_path.name
    
    # Canonical page layout: PageHeader, ActionBar (optional), content
    breadcrumbs = build_breadcrumbs(snapshot_state())
    render_page_header(
        path=breadcrumbs,
        title="Report Overview",
        subtitle=f"Analysis of {run_display_name}"
    )
    
    render_action_bar(
        actions=[
            {"label": "Open Job Explorer", "on_click": lambda: navigate_to(
                "reports",
                selected_run=st.session_state.selected_run,
                view_mode="explorer",
                viewing_job_id=None,
                selected_filters={},
                filter_mode="any",
                search_text=""
            ), "kind": "primary"}
        ]
    )
    
    if not analysis:
        st.warning("No analysis data found for this report. Run analysis first.")
        return
    
    summary = analysis.get("summary", {}) or analysis.get("presence", {})
    total_jobs = analysis.get("total_jobs", 0)
    
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Jobs", total_jobs)
    
    with col2:
        # Count unique companies from job_details
        job_details = analysis.get("job_details", [])
        unique_companies = len(set(j.get("company", "") for j in job_details))
        st.metric("Companies", unique_companies)
    
    with col3:
        # Top certification
        certs = summary.get("certifications", {})
        if certs:
            top_cert = max(certs, key=certs.get)
            st.metric("Top Cert", top_cert, f"{certs[top_cert]} jobs")
        else:
            st.metric("Top Cert", "N/A")
    
    with col4:
        # Top technical skill
        skills = summary.get("technical_skills", {})
        if skills:
            top_skill = max(skills, key=skills.get)
            st.metric("Top Skill", top_skill, f"{skills[top_skill]} jobs")
        else:
            st.metric("Top Skill", "N/A")
    
    st.markdown("---")

    # AI summary (single report)
    keywords, location = _get_run_search_meta(run_path)
    txt = load_requirements_analysis_txt(run_path)
    bundle = build_ai_bundle(
        scope="single",
        analysis_text=_truncate_text(
            txt.strip(),
            max_chars=80_000,
            suffix="\n\n[TRUNCATED: requirements_analysis.txt exceeded limit]",
        ),
        meta={
            "scope": "single",
            "run": run_path.name,
            "keywords": keywords,
            "location": location,
            "total_jobs": int(total_jobs or 0),
            "companies": int(unique_companies or 0),
        },
        limits={"top_n_per_category": AI_SUMMARY_TOP_N_SINGLE},
        category_labels=CATEGORY_LABELS,
    )
    cache_path = run_path / "ai_summary.json"
    render_ai_summary_block(cache_path=cache_path, ai_input=bundle)

    st.markdown("---")
    
    # Category charts in expanders with clickable requirements
    for category_key, category_label in CATEGORY_LABELS.items():
        data = summary.get(category_key, {})
        if not data:
            continue
        
        # Keep expander expanded if there's an active selection in this category
        has_selection = bool(st.session_state.get(f"report_selected_term_{category_key}"))
        
        with st.expander(f"{category_label} ({len(data)} items)", expanded=has_selection):
            # Prepare data for chart
            sorted_items_full = sorted(data.items(), key=lambda x: x[1], reverse=True)
            sorted_items = sorted_items_full[:15]  # Top 15
            df = pd.DataFrame([
                {"term": term, "count": count, "percentage": (count / total_jobs * 100) if total_jobs > 0 else 0}
                for term, count in sorted_items
            ])

            df_full = pd.DataFrame([
                {"term": term, "count": count, "percentage": (count / total_jobs * 100) if total_jobs > 0 else 0}
                for term, count in sorted_items_full
            ])
            
            if not df.empty:
                st.caption("Select a requirement row to view matching jobs:")
                table_df = df[["term", "count", "percentage"]].rename(
                    columns={"term": "Requirement", "count": "Jobs", "percentage": "% of Total"}
                )
                table_state = st.dataframe(
                    table_df,
                    hide_index=True,
                    use_container_width=True,
                    selection_mode="single-row",
                    on_select="rerun",
                    key=f"report_table_{category_key}",
                )

                selected_rows = []
                try:
                    selected_rows = (table_state.selection.rows or []) if table_state and table_state.selection else []
                except Exception:
                    selected_rows = []
                selected_term_key = f"report_selected_term_{category_key}"
                if selected_rows:
                    row_idx = selected_rows[0]
                    if 0 <= row_idx < len(df):
                        st.session_state[selected_term_key] = str(df.iloc[row_idx]["term"])

                selected_term = st.session_state.get(selected_term_key)
                if selected_term and st.button(
                    "View matching jobs",
                    type="primary",
                    use_container_width=True,
                    key=f"report_view_jobs_{category_key}",
                ):
                    navigate_to(
                        "reports",
                        selected_run=st.session_state.selected_run,
                        view_mode="explorer",
                        viewing_job_id=None,
                        selected_filters={category_key: [selected_term]},
                        filter_mode="any",
                        search_text="",
                    )
                    st.rerun()

                if len(sorted_items_full) > 15 and st.button(
                    "⤢ Expand list",
                    use_container_width=True,
                    key=f"report_expand_{category_key}",
                ):
                    if hasattr(st, "dialog"):
                        @st.dialog(f"{category_label} — All Items")
                        def _show_report_full_table(cat_key: str, df_all: pd.DataFrame):
                            st.caption("Select a requirement row to view matching jobs:")
                            table_df_full = df_all[["term", "count", "percentage"]].rename(
                                columns={"term": "Requirement", "count": "Jobs", "percentage": "% of Total"}
                            )
                            table_state_full = st.dataframe(
                                table_df_full,
                                hide_index=True,
                                use_container_width=True,
                                height=520,
                                selection_mode="single-row",
                                on_select="rerun",
                                key=f"report_table_full_{cat_key}",
                            )

                            selected_rows_full = []
                            try:
                                selected_rows_full = (
                                    (table_state_full.selection.rows or [])
                                    if table_state_full and table_state_full.selection
                                    else []
                                )
                            except Exception:
                                selected_rows_full = []
                            selected_term_key_full = f"report_selected_term_full_{cat_key}"
                            if selected_rows_full:
                                row_idx_full = selected_rows_full[0]
                                if 0 <= row_idx_full < len(df_all):
                                    st.session_state[selected_term_key_full] = str(df_all.iloc[row_idx_full]["term"])

                            selected_term_full = st.session_state.get(selected_term_key_full)
                            if selected_term_full and st.button(
                                "View matching jobs",
                                type="primary",
                                use_container_width=True,
                                key=f"report_view_jobs_full_{cat_key}",
                            ):
                                navigate_to(
                                    "reports",
                                    selected_run=st.session_state.selected_run,
                                    view_mode="explorer",
                                    viewing_job_id=None,
                                    selected_filters={cat_key: [selected_term_full]},
                                    filter_mode="any",
                                    search_text="",
                                )
                                st.rerun()

                        _show_report_full_table(category_key, df_full)
                    else:
                        with st.expander("All items", expanded=True):
                            table_df_full = df_full[["term", "count", "percentage"]].rename(
                                columns={"term": "Requirement", "count": "Jobs", "percentage": "% of Total"}
                            )
                            table_state_full = st.dataframe(
                                table_df_full,
                                hide_index=True,
                                use_container_width=True,
                                height=520,
                                selection_mode="single-row",
                                on_select="rerun",
                                key=f"report_table_full_{category_key}",
                            )

                            selected_rows_full = []
                            try:
                                selected_rows_full = (
                                    (table_state_full.selection.rows or [])
                                    if table_state_full and table_state_full.selection
                                    else []
                                )
                            except Exception:
                                selected_rows_full = []
                            selected_term_key_full = f"report_selected_term_full_{category_key}"
                            if selected_rows_full:
                                row_idx_full = selected_rows_full[0]
                                if 0 <= row_idx_full < len(df_full):
                                    st.session_state[selected_term_key_full] = str(df_full.iloc[row_idx_full]["term"])

                            selected_term_full = st.session_state.get(selected_term_key_full)
                            if selected_term_full and st.button(
                                "View matching jobs",
                                type="primary",
                                use_container_width=True,
                                key=f"report_view_jobs_full_{category_key}",
                            ):
                                navigate_to(
                                    "reports",
                                    selected_run=st.session_state.selected_run,
                                    view_mode="explorer",
                                    viewing_job_id=None,
                                    selected_filters={cat_key: [selected_term_full]},
                                    filter_mode="any",
                                    search_text="",
                                )
                                st.rerun()


def render_compiled_overview():
    """Render an aggregated overview across multiple selected runs."""
    # Canonical page layout: PageHeader, ActionBar (optional), content
    breadcrumbs = build_breadcrumbs(snapshot_state())
    render_page_header(
        path=breadcrumbs,
        title="Compiled Review",
        subtitle="Aggregated analysis across multiple reports"
    )

    # One-time notice set by the Reports page Compile(x) button.
    if st.session_state.get("compiled_preexisting"):
        st.info("Matching saved compiled report found; opening cached results.")
        st.session_state.compiled_preexisting = False

    run_paths = list(dict.fromkeys(Path(p) for p in (st.session_state.compiled_runs or [])))
    if not run_paths:
        st.info("No reports selected for compilation.")
        return

    run_names = [p.name for p in run_paths]
    fingerprint = build_runs_fingerprint(run_paths)
    report_path = compiled_report_path(STATE_DIR, run_names=run_names)

    cached_report = load_compiled_report(report_path)
    merged = None
    used_saved_compiled = False
    if cached_report and is_matching_compiled_report(cached_report, run_names=run_names, fingerprint=fingerprint):
        maybe_merged = cached_report.get("merged_analysis")
        if isinstance(maybe_merged, dict):
            merged = maybe_merged
            used_saved_compiled = True

    analyses: list[tuple[Path, dict | None]] = [(p, load_analysis(p)) for p in run_paths]
    if merged is None:
        merged = _merge_analyses([a for _, a in analyses if a])
        try:
            # Persist merged result so repeated compiled views are fast.
            payload = build_compiled_report_payload(
                run_names=run_names,
                fingerprint=fingerprint,
                merged_analysis=merged,
                name=(cached_report or {}).get("name") if isinstance(cached_report, dict) else None,
                created_at=(cached_report or {}).get("created_at") if isinstance(cached_report, dict) else None,
            )
            save_compiled_report_atomic(report_path, payload)
        except Exception:
            # Non-critical; compiled view should still work.
            pass

    total_jobs = merged.get("total_jobs", 0)
    summary = merged.get("summary", {})
    job_details = merged.get("job_details", [])
    unique_companies = len(set((j.get("company") or "").strip() for j in job_details if j.get("company")))

    run_term_index: dict[str, dict[str, list[tuple[int, Path]]]] = defaultdict(lambda: defaultdict(list))
    for run_path, analysis in analyses:
        if not analysis:
            continue
        for cat_key, items in (analysis.get("summary", {}) or analysis.get("presence", {}) or {}).items():
            for term, count in (items or {}).items():
                try:
                    run_term_index[cat_key][term].append((int(count), run_path))
                except Exception:
                    pass

    st.caption(f"Includes {len(run_paths)} report(s)")
    if used_saved_compiled:
        st.caption("Using saved compiled report (no re-merge needed).")
    for p in run_paths:
        st.caption(f"- {p.name}")

    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Jobs", total_jobs)
    with col2:
        st.metric("Companies", unique_companies)
    with col3:
        st.metric("Reports", len(run_paths))

    st.markdown("---")

    # AI summary (compiled)
    search_pairs = []
    for p in run_paths:
        kw, loc = _get_run_search_meta(p)
        if kw or loc:
            search_pairs.append({"keywords": kw, "location": loc, "run": p.name})

    # Prefer requirements_analysis.txt as the data source for the LLM.
    # For compiled summaries, concatenate per-run reports with lightweight headers.
    per_run_blocks: list[str] = []
    for run_path, analysis in analyses:
        txt = load_requirements_analysis_txt(run_path) or ""
        if not txt.strip():
            continue
        kw, loc = _get_run_search_meta(run_path)
        run_total = None
        try:
            run_total = int((analysis or {}).get("total_jobs", 0) or 0)
        except Exception:
            run_total = None
        header_lines = [
            f"RUN: {run_path.name}",
            f"KEYWORDS: {kw or ''}",
            f"LOCATION: {loc or ''}",
        ]
        if run_total is not None:
            header_lines.append(f"TOTAL_JOBS: {run_total}")
        header = "\n".join(header_lines).strip()
        per_run_blocks.append(f"{header}\n\n{txt.strip()}")

    combined_txt = "\n\n".join(per_run_blocks).strip()
    combined_txt = _truncate_text(
        combined_txt,
        max_chars=120_000,
        suffix="\n\n[TRUNCATED: combined requirements_analysis.txt exceeded limit]",
    )

    bundle = build_ai_bundle(
        scope="compiled",
        analysis_text=combined_txt,
        meta={
            "scope": "compiled",
            "runs": [p.name for p in run_paths],
            "search_terms": search_pairs,
            "total_jobs": int(total_jobs or 0),
            "companies": int(unique_companies or 0),
            "compiled_reports": int(len(run_paths)),
        },
        limits={"top_n_per_category": 25},  # Default for compiled
        category_labels=CATEGORY_LABELS,
    )
    compiled_key = hashlib.sha256("|".join(sorted(p.name for p in run_paths)).encode("utf-8")).hexdigest()[:16]
    cache_path = STATE_DIR / f"compiled_ai_summary_{compiled_key}.json"
    render_ai_summary_block(cache_path=cache_path, ai_input=bundle)

    st.markdown("---")

    for category_key, category_label in CATEGORY_LABELS.items():
        data = summary.get(category_key, {}) or {}
        if not data:
            continue

        # Keep expander expanded if there's an active selection in this category
        has_selection = bool(st.session_state.get(f"compiled_selected_term_{category_key}"))
        
        with st.expander(f"{category_label} ({len(data)} items)", expanded=has_selection):
            sorted_items_full = sorted(data.items(), key=lambda x: x[1], reverse=True)
            sorted_items = sorted_items_full[:15]
            df = pd.DataFrame(
                [
                    {
                        "term": term,
                        "count": count,
                        "percentage": (count / total_jobs * 100) if total_jobs > 0 else 0,
                    }
                    for term, count in sorted_items
                ]
            )

            # Full list for expanded view
            df_full = pd.DataFrame(
                [
                    {
                        "term": term,
                        "count": count,
                        "percentage": (count / total_jobs * 100) if total_jobs > 0 else 0,
                    }
                    for term, count in sorted_items_full
                ]
            )

            if df.empty:
                st.info("No data")
                continue

            st.caption("Select a requirement row to view matching jobs:")

            table_df = df[["term", "count", "percentage"]].rename(
                columns={"term": "Requirement", "count": "Jobs", "percentage": "% of Total"}
            )
            table_state = st.dataframe(
                table_df,
                hide_index=True,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun",
                key=f"compiled_table_{category_key}",
            )

            # Streamlit doesn't reliably support clicking Plotly axis labels in-app.
            # Instead, make the table rows clickable to navigate.
            selected_rows = []
            try:
                selected_rows = (table_state.selection.rows or []) if table_state and table_state.selection else []
            except Exception:
                selected_rows = []
            selected_term_key = f"compiled_selected_term_{category_key}"
            if selected_rows:
                row_idx = selected_rows[0]
                if 0 <= row_idx < len(df):
                    st.session_state[selected_term_key] = str(df.iloc[row_idx]["term"])

            selected_term = st.session_state.get(selected_term_key)
            if selected_term and st.button(
                "View matching jobs",
                type="primary",
                use_container_width=True,
                key=f"compiled_view_jobs_{category_key}",
            ):
                target_candidates = run_term_index.get(category_key, {}).get(selected_term, [])
                if target_candidates:
                    target_run = sorted(
                        target_candidates,
                        key=lambda t: (t[0], t[1].stat().st_mtime if t[1].exists() else 0),
                        reverse=True,
                    )[0][1]
                else:
                    target_run = run_paths[0]
                st.session_state.nav_origin = "compiled"
                navigate_to(
                    "reports",
                    selected_run=str(target_run),
                    view_mode="explorer",
                    viewing_job_id=None,
                    selected_filters={category_key: [selected_term]},
                    filter_mode="any",
                    search_text="",
                    # Keep compiled_runs so Back can return to compiled overview.
                    compiled_runs=list(st.session_state.get("compiled_runs") or []),
                )
                st.rerun()

            if len(sorted_items_full) > 15 and st.button(
                "⤢ Expand list",
                use_container_width=True,
                key=f"compiled_expand_{category_key}",
            ):
                if hasattr(st, "dialog"):
                    @st.dialog(f"{category_label} — All Items")
                    def _show_compiled_full_table(cat_key: str, df_all: pd.DataFrame):
                        st.caption("Select a requirement row to view matching jobs:")
                        table_df_full = df_all[["term", "count", "percentage"]].rename(
                            columns={"term": "Requirement", "count": "Jobs", "percentage": "% of Total"}
                        )
                        table_state_full = st.dataframe(
                            table_df_full,
                            hide_index=True,
                            use_container_width=True,
                            height=520,
                            selection_mode="single-row",
                            on_select="rerun",
                            key=f"compiled_table_full_{cat_key}",
                        )

                        selected_rows_full = []
                        try:
                            selected_rows_full = (
                                (table_state_full.selection.rows or [])
                                if table_state_full and table_state_full.selection
                                else []
                            )
                        except Exception:
                            selected_rows_full = []
                        selected_term_key_full = f"compiled_selected_term_full_{cat_key}"
                        if selected_rows_full:
                            row_idx_full = selected_rows_full[0]
                            if 0 <= row_idx_full < len(df_all):
                                st.session_state[selected_term_key_full] = str(df_all.iloc[row_idx_full]["term"])

                        selected_term_full = st.session_state.get(selected_term_key_full)
                        if selected_term_full and st.button(
                            "View matching jobs",
                            type="primary",
                            use_container_width=True,
                            key=f"compiled_view_jobs_full_{cat_key}",
                        ):
                            target_candidates_full = run_term_index.get(category_key, {}).get(selected_term_full, [])
                            if target_candidates_full:
                                target_run_full = sorted(
                                    target_candidates_full,
                                    key=lambda t: (t[0], t[1].stat().st_mtime if t[1].exists() else 0),
                                    reverse=True,
                                )[0][1]
                            else:
                                target_run_full = run_paths[0]
                            st.session_state.nav_origin = "compiled"
                            navigate_to(
                                "reports",
                                selected_run=str(target_run_full),
                                view_mode="explorer",
                                viewing_job_id=None,
                                selected_filters={cat_key: [selected_term_full]},
                                filter_mode="any",
                                search_text="",
                                compiled_runs=list(st.session_state.get("compiled_runs") or []),
                            )
                            st.rerun()

                    _show_compiled_full_table(category_key, df_full)
                else:
                    with st.expander("All items", expanded=True):
                        table_df_full = df_full[["term", "count", "percentage"]].rename(
                            columns={"term": "Requirement", "count": "Jobs", "percentage": "% of Total"}
                        )
                        table_state_full = st.dataframe(
                            table_df_full,
                            hide_index=True,
                            use_container_width=True,
                            height=520,
                            selection_mode="single-row",
                            on_select="rerun",
                            key=f"compiled_table_full_{category_key}",
                        )

                        selected_rows_full = []
                        try:
                            selected_rows_full = (
                                (table_state_full.selection.rows or [])
                                if table_state_full and table_state_full.selection
                                else []
                            )
                        except Exception:
                            selected_rows_full = []
                        selected_term_key_full = f"compiled_selected_term_full_{category_key}"
                        if selected_rows_full:
                            row_idx_full = selected_rows_full[0]
                            if 0 <= row_idx_full < len(df_full):
                                st.session_state[selected_term_key_full] = str(df_full.iloc[row_idx_full]["term"])

                        selected_term_full = st.session_state.get(selected_term_key_full)
                        if selected_term_full and st.button(
                            "View matching jobs",
                            type="primary",
                            use_container_width=True,
                            key=f"compiled_view_jobs_full_{category_key}",
                        ):
                            target_candidates_full = run_term_index.get(category_key, {}).get(selected_term_full, [])
                            if target_candidates_full:
                                target_run_full = sorted(
                                    target_candidates_full,
                                    key=lambda t: (t[0], t[1].stat().st_mtime if t[1].exists() else 0),
                                    reverse=True,
                                )[0][1]
                            else:
                                target_run_full = run_paths[0]
                            st.session_state.nav_origin = "compiled"
                            navigate_to(
                                "reports",
                                selected_run=str(target_run_full),
                                view_mode="explorer",
                                viewing_job_id=None,
                                selected_filters={cat_key: [selected_term_full]},
                                filter_mode="any",
                                search_text="",
                                compiled_runs=list(st.session_state.get("compiled_runs") or []),
                            )
                            st.rerun()


def render_job_detail_view():
    """Placeholder for render_job_detail_view - to be implemented"""
    st.info("Job detail view rendering - to be implemented")

def render_job_explorer():
    """Placeholder for render_job_explorer - to be implemented"""
    st.info("Job explorer rendering - to be implemented")

