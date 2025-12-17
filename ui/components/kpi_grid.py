"""
KPI Grid component for displaying key performance indicators.
"""

import streamlit as st
from typing import Optional


def render_kpi_grid(
    effective_jobs: float,
    runs_used: int,
    time_span_label: str,
    median_post_age_days: Optional[float] = None,
    pct_new_jobs_30d: Optional[float] = None
) -> None:
    """
    Render a grid of KPI cards.

    Args:
        effective_jobs: Total effective jobs (weighted)
        runs_used: Number of runs included
        time_span_label: Time span description
        median_post_age_days: Median job posting age in days (optional)
        pct_new_jobs_30d: Percentage of jobs posted in last 30 days (optional)
    """
    st.subheader("📋 Window Summary")

    # Create 4 columns for KPIs
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Runs", runs_used)

    with col2:
        st.metric("Effective Jobs", f"{effective_jobs:,.0f}")

    with col3:
        st.metric("Time Span", time_span_label)

    with col4:
        if median_post_age_days is not None:
            st.metric("Median Age", f"{median_post_age_days:.0f}d")
        elif pct_new_jobs_30d is not None:
            st.metric("New (30d)", f"{pct_new_jobs_30d:.1f}%")
        else:
            st.metric("Median Age", "—")