import streamlit as st
from typing import Dict, List, Any, Callable, Optional


def render_category_snapshot_row(
    category_name: str,
    top_terms: List[str],
    total_terms: int,
    is_truncated: bool,
    on_view_all: Optional[Callable[[str], None]] = None,
    max_display_terms: int = 3
) -> None:
    """
    Render a category snapshot row showing category name, top terms, and view all option.

    Args:
        category_name: Name of the category (e.g., "Skills", "Companies")
        top_terms: List of top term strings to display
        total_terms: Total number of terms in this category
        is_truncated: Whether the terms were truncated (topN applied)
        on_view_all: Callback when "View all" is clicked
        max_display_terms: Maximum terms to show before "View all"
    """

    # Main row container
    col1, col2 = st.columns([1, 3])

    with col1:
        # Category name
        st.markdown(f"**{category_name}**")

        # Term count and truncation indicator
        if is_truncated:
            st.markdown(f"*{total_terms} total • truncated*")
        else:
            st.markdown(f"*{total_terms} terms*")

    with col2:
        # Top terms as chips
        display_terms = top_terms[:max_display_terms]
        chips = []

        for term in display_terms:
            chips.append(_create_term_chip(term))

        # Render chips
        if chips:
            chips_html = '<div style="display: flex; gap: 6px; flex-wrap: wrap; align-items: center;">' + ''.join(chips)
            chips_html += '</div>'
            st.markdown(chips_html, unsafe_allow_html=True)

        # View all button if there are more terms or if truncated
        show_view_all = len(top_terms) > max_display_terms or is_truncated

        if show_view_all and on_view_all:
            remaining = total_terms - len(display_terms) if is_truncated else len(top_terms) - max_display_terms
            if remaining > 0:
                if st.button(f"View all ({total_terms})", key=f"view_all_{category_name}", help=f"Show all {total_terms} terms"):
                    on_view_all(category_name)


def _create_term_chip(term: str) -> str:
    """Create a styled chip for a term."""
    # Simple chip styling
    return f"""
    <span style="
        background-color: #e3f2fd;
        color: #1976d2;
        padding: 4px 10px;
        border-radius: 16px;
        font-size: 0.85em;
        font-weight: 500;
        white-space: nowrap;
        display: inline-block;
    ">{term}</span>
    """


def render_category_snapshot_expanded(
    category_name: str,
    all_terms: List[Dict[str, Any]],
    on_collapse: Optional[Callable[[], None]] = None
) -> None:
    """
    Render an expanded view of all terms in a category.

    Args:
        category_name: Name of the category
        all_terms: List of term dictionaries with 'term' and 'count' keys
        on_collapse: Callback to collapse back to snapshot view
    """

    st.markdown(f"### {category_name}")

    if on_collapse:
        if st.button("← Back to overview", key=f"collapse_{category_name}"):
            on_collapse()

    # Sort terms by count descending
    sorted_terms = sorted(all_terms, key=lambda x: x.get('count', 0), reverse=True)

    # Display as a ranked list
    for i, term_data in enumerate(sorted_terms, 1):
        term = term_data.get('term', 'Unknown')
        count = term_data.get('count', 0)

        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"{i}. {term}")
        with col2:
            st.markdown(f"*{count}*")

    st.divider()