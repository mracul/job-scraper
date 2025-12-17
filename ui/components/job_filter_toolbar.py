import streamlit as st
from typing import Dict, Any, Callable, Optional


def render_job_filter_toolbar(
    filters: Dict[str, Any],
    on_filters_change: Callable[[Dict[str, Any]], None],
    total_jobs: int,
    filtered_jobs: int
) -> None:
    """
    Render the job filter toolbar with search, sort, and filter controls.

    Args:
        filters: Current filter state dictionary
        on_filters_change: Callback when filters change
        total_jobs: Total number of jobs available
        filtered_jobs: Number of jobs after filtering
    """

    # Main toolbar container
    with st.container():
        # Top row: search and sort
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            search_query = st.text_input(
                "Search jobs",
                value=filters.get('search', ''),
                placeholder="Job title, company, or keywords",
                label_visibility="collapsed",
                key="job_search"
            )

        with col2:
            sort_options = [
                "Relevance",
                "Newest",
                "Oldest",
                "Salary: High to Low",
                "Salary: Low to High",
                "Company A-Z",
                "Company Z-A"
            ]
            current_sort = filters.get('sort', 'Relevance')
            sort_by = st.selectbox(
                "Sort by",
                options=sort_options,
                index=sort_options.index(current_sort) if current_sort in sort_options else 0,
                label_visibility="collapsed",
                key="job_sort"
            )

        with col3:
            match_mode = st.toggle(
                "Match all",
                value=filters.get('match_all', False),
                help="Match ALL keywords (AND) vs ANY keyword (OR)",
                key="match_mode"
            )

        # Second row: filter summary and clear
        col1, col2 = st.columns([4, 1])

        with col1:
            _render_filter_summary(filters, total_jobs, filtered_jobs)

        with col2:
            if any(v for k, v in filters.items() if k not in ['sort'] and v):
                if st.button("Clear filters", use_container_width=True, key="clear_filters"):
                    # Clear all filters except sort
                    new_filters = {'sort': filters.get('sort', 'Relevance')}
                    on_filters_change(new_filters)

        # Update filters if anything changed
        new_filters = filters.copy()
        new_filters['search'] = search_query
        new_filters['sort'] = sort_by
        new_filters['match_all'] = match_mode

        if new_filters != filters:
            on_filters_change(new_filters)


def _render_filter_summary(filters: Dict[str, Any], total_jobs: int, filtered_jobs: int) -> None:
    """Render filter summary with active filter chips."""

    active_filters = []

    if filters.get('search'):
        active_filters.append(f"search: '{filters['search']}'")

    if filters.get('match_all'):
        active_filters.append("match: all")
    else:
        active_filters.append("match: any")

    # Add more filter chips here as they are implemented
    # if filters.get('location'):
    #     active_filters.append(f"location: {filters['location']}")
    # if filters.get('work_type'):
    #     active_filters.append(f"type: {filters['work_type']}")

    # Results summary
    if filtered_jobs != total_jobs:
        summary_text = f"Showing {filtered_jobs} of {total_jobs} jobs"
    else:
        summary_text = f"{total_jobs} jobs"

    if active_filters:
        chips_text = " • ".join(active_filters)
        st.markdown(f"{summary_text} • {chips_text}")
    else:
        st.markdown(summary_text)

    # Active filters count chip
    if len(active_filters) > 0:
        st.markdown(
            f'<span style="background-color: #e3f2fd; color: #1976d2; padding: 2px 8px; border-radius: 12px; font-size: 0.8em;">{len(active_filters)} filters active</span>',
            unsafe_allow_html=True
        )