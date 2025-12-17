"""
Category drilldown component for displaying category snapshots with drilldown options.
"""

import streamlit as st
from typing import Any, Callable, Dict, List


def render_category_drilldown(
    categories: List[Dict[str, Any]]
) -> None:
    """
    Render category drilldown with expanders and view options.

    Args:
        categories: List of category dicts with:
            - category: str (category key)
            - top_terms: List[Dict] with term/pct
            - on_view_breakdown: callable (optional)
    """
    st.subheader("📁 Category Snapshots")

    for cat_data in categories:
        category = cat_data.get("category", "")
        category_label = cat_data.get("category_label", category)
        top_terms = cat_data.get("top_terms", [])
        on_view_breakdown = cat_data.get("on_view_breakdown")

        with st.expander(f"**{category_label}**", expanded=False):
            if top_terms:
                # Show top 3 terms
                for i, term_data in enumerate(top_terms[:3]):
                    term = term_data.get("term", "")
                    pct = term_data.get("pct", 0)
                    st.markdown(f"• {term}: {pct:.1f}%")

                # Show view breakdown button if callback provided
                if on_view_breakdown and len(top_terms) > 3:
                    remaining = len(top_terms) - 3
                    if st.button(f"View all {remaining} more →", key=f"view_{category}"):
                        on_view_breakdown(category)
            else:
                st.caption("No data available for this category.")