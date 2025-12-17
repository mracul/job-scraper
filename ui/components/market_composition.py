"""
Market composition component for displaying support levels and work arrangements.
"""

import streamlit as st
from typing import Any, Dict, List


def render_market_composition(
    support_levels: List[Dict[str, Any]],
    work_arrangements: List[Dict[str, Any]]
) -> None:
    """
    Render market composition bars for support levels and work arrangements.

    Args:
        support_levels: List of dicts with 'label' and 'pct' keys
        work_arrangements: List of dicts with 'label' and 'pct' keys
    """
    st.subheader("🏢 Market Context")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Support Levels**")
        if support_levels:
            # Sort by percentage descending
            sorted_levels = sorted(support_levels, key=lambda x: x.get("pct", 0), reverse=True)
            for item in sorted_levels[:6]:  # Show top 6
                label = item.get("label", "")
                pct = item.get("pct", 0)
                st.progress(min(pct / 100.0, 1.0), text=f"{label}: {pct:.1f}%")
        else:
            st.caption("No support level data available.")

    with col2:
        st.markdown("**Work Arrangements**")
        if work_arrangements:
            # Sort by percentage descending
            sorted_arrangements = sorted(work_arrangements, key=lambda x: x.get("pct", 0), reverse=True)
            for item in sorted_arrangements[:6]:  # Show top 6
                label = item.get("label", "")
                pct = item.get("pct", 0)
                st.progress(min(pct / 100.0, 1.0), text=f"{label}: {pct:.1f}%")
        else:
            st.caption("No work arrangement data available.")