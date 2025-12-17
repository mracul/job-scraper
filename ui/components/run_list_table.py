import streamlit as st
from typing import List, Dict, Any, Callable, Optional, Tuple
import pandas as pd
from datetime import datetime


def render_run_list_table(
    runs: List[Dict[str, Any]],
    on_run_select: Callable[[str], None],
    on_run_delete: Callable[[str], None],
    on_bulk_compile: Callable[[List[str]], None],
    on_bulk_delete: Callable[[List[str]], None],
    selected_runs: Optional[List[str]] = None
) -> Tuple[List[str], Optional[str]]:
    """
    Render a compact table for displaying runs with selection, search, and sorting.

    Args:
        runs: List of run dictionaries with keys: id, title, job_count, timestamp, status
        on_run_select: Callback when a run is selected/opened
        on_run_delete: Callback when a run is deleted
        on_bulk_compile: Callback for bulk compile action
        on_bulk_delete: Callback for bulk delete action
        selected_runs: Currently selected run IDs

    Returns:
        Tuple of (selected_run_ids, search_query)
    """

    if selected_runs is None:
        selected_runs = []

    # Search and sort controls
    search_query = _render_search_and_sort_controls()

    # Filter runs based on search
    filtered_runs = _filter_runs(runs, search_query)

    # Selection state management
    all_selected = len(selected_runs) == len(filtered_runs) and len(filtered_runs) > 0
    some_selected = len(selected_runs) > 0

    # Header with select all checkbox
    col_check, col_title, col_jobs, col_timestamp, col_status, col_actions = st.columns([0.5, 3, 1, 1.5, 1, 0.8])

    with col_check:
        select_all = st.checkbox(
            "",
            value=all_selected,
            key="select_all_runs",
            help="Select all visible runs"
        )

        # Update selection based on select all
        if select_all and not all_selected:
            selected_runs = [run['id'] for run in filtered_runs]
        elif not select_all and all_selected:
            selected_runs = []

    with col_title:
        st.markdown("**Title**")
    with col_jobs:
        st.markdown("**Jobs**")
    with col_timestamp:
        st.markdown("**Created**")
    with col_status:
        st.markdown("**Status**")
    with col_actions:
        st.markdown("**Actions**")

    st.divider()

    # Render run rows
    for run in filtered_runs:
        run_id = run['id']
        is_selected = run_id in selected_runs

        cols = st.columns([0.5, 3, 1, 1.5, 1, 0.8])

        # Checkbox
        with cols[0]:
            if st.checkbox("", value=is_selected, key=f"select_{run_id}"):
                if run_id not in selected_runs:
                    selected_runs.append(run_id)
            else:
                if run_id in selected_runs:
                    selected_runs.remove(run_id)

        # Title (clickable)
        with cols[1]:
            title = run.get('title', f'Run {run_id}')
            if st.button(title, key=f"open_{run_id}", help="Open run details"):
                on_run_select(run_id)

        # Job count
        with cols[2]:
            job_count = run.get('job_count', 0)
            st.markdown(f"{job_count}")

        # Timestamp
        with cols[3]:
            timestamp = run.get('timestamp')
            if timestamp:
                if isinstance(timestamp, str):
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        display_time = dt.strftime("%b %d, %H:%M")
                    except:
                        display_time = timestamp[:16]  # Fallback
                else:
                    display_time = timestamp.strftime("%b %d, %H:%M")
                st.markdown(display_time)
            else:
                st.markdown("—")

        # Status
        with cols[4]:
            status = run.get('status', 'unknown')
            _render_status_in_table(status)

        # Actions menu
        with cols[5]:
            _render_run_actions_menu(run_id, on_run_delete)

        st.divider()

    # Bulk actions bar
    if selected_runs:
        from .bulk_action_bar import render_bulk_action_bar

        actions = [
            {
                'label': 'Compile',
                'on_click': lambda: on_bulk_compile(selected_runs),
                'kind': 'primary'
            },
            {
                'label': 'Delete',
                'on_click': lambda: on_bulk_delete(selected_runs),
                'kind': 'danger'
            }
        ]

        render_bulk_action_bar(
            selection_count=len(selected_runs),
            actions=actions,
            on_clear=lambda: selected_runs.clear()
        )

    return selected_runs, search_query


def _render_search_and_sort_controls() -> str:
    """Render search input and sort dropdown."""
    col1, col2 = st.columns([3, 1])

    with col1:
        search_query = st.text_input(
            "Search runs...",
            placeholder="Filter by title",
            label_visibility="collapsed",
            key="run_search"
        )

    with col2:
        sort_options = ["Newest", "Oldest", "Most Jobs", "Least Jobs", "Name A-Z", "Name Z-A"]
        st.selectbox(
            "Sort by",
            options=sort_options,
            index=0,
            label_visibility="collapsed",
            key="run_sort"
        )

    return search_query


def _filter_runs(runs: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
    """Filter runs based on search query."""
    if not query:
        return runs

    query_lower = query.lower()
    return [
        run for run in runs
        if query_lower in run.get('title', '').lower() or
           query_lower in str(run.get('id', '')).lower()
    ]


def _render_status_in_table(status: str) -> None:
    """Render status badge in table cell."""
    from .status_badge import render_status_badge

    # Use compact inline variant for table
    render_status_badge(status, size='sm', variant='inline')


def _render_run_actions_menu(run_id: str, on_delete: Callable[[str], None]) -> None:
    """Render actions menu for a run row."""
    with st.popover("⋯"):
        if st.button("View Details", key=f"view_{run_id}"):
            st.rerun()  # This would trigger the select callback

        st.divider()

        if st.button("Delete", key=f"delete_{run_id}", type="secondary"):
            on_delete(run_id)