"""
Trend section component for displaying market trends.
"""

import streamlit as st
from typing import Any, Dict, List, Optional


def render_trend_section(
    new_vs_existing: Optional[Dict[str, float]] = None,
    title_velocity: Optional[List[Dict[str, Any]]] = None
) -> None:
    """
    Render trend analysis section.

    Args:
        new_vs_existing: Dict with window_days, new_jobs_pct, existing_jobs_pct
        title_velocity: List of dicts with title and delta_pct
    """
    st.subheader("📈 Market Trends")

    if new_vs_existing is None and title_velocity is None:
        st.caption("Trend analysis not available yet.")
        return

    col1, col2 = st.columns(2)

    with col1:
        if new_vs_existing:
            window_days = new_vs_existing.get("window_days", 30)
            new_pct = new_vs_existing.get("new_jobs_pct", 0)
            existing_pct = new_vs_existing.get("existing_jobs_pct", 0)

            st.metric(
                f"New vs Existing ({window_days}d)",
                f"{new_pct:.1f}%",
                f"{existing_pct:.1f}% existing"
            )
        else:
            st.metric("New vs Existing", "—")

    with col2:
        if title_velocity:
            # Show top mover
            top_mover = max(title_velocity, key=lambda x: abs(x.get("delta_pct", 0)))
            title = top_mover.get("title", "Unknown")
            delta = top_mover.get("delta_pct", 0)

            st.metric(
                "Top Title Mover",
                title[:20] + ("..." if len(title) > 20 else ""),
                f"{delta:+.1f}%"
            )
        else:
            st.metric("Title Velocity", "—")