"""
AI Market Brief component for displaying structured AI analysis.
"""

import streamlit as st
from typing import List, Optional


def render_ai_market_brief(
    tldr: Optional[List[str]] = None,
    observations: Optional[List[str]] = None,
    risks: Optional[List[str]] = None,
    actions: Optional[List[str]] = None
) -> None:
    """
    Render AI market brief with structured sections.

    Args:
        tldr: List of 1-3 key takeaways
        observations: List of observations
        risks: List of risks
        actions: List of recommended actions
    """
    with st.expander("🤖 AI Market Brief", expanded=False):
        if not any([tldr, observations, risks, actions]):
            st.caption("AI analysis not available yet.")
            return

        if tldr:
            st.markdown("**TL;DR**")
            for item in tldr[:3]:  # Max 3 items
                st.markdown(f"• {item}")
            st.markdown("")

        if observations:
            st.markdown("**Key Observations**")
            for obs in observations:
                st.markdown(f"• {obs}")
            st.markdown("")

        if risks:
            st.markdown("**Risks & Challenges**")
            for risk in risks:
                st.markdown(f"• {risk}")
            st.markdown("")

        if actions:
            st.markdown("**Recommended Actions**")
            for action in actions:
                st.markdown(f"• {action}")