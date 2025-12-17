import streamlit as st
from typing import List, Dict, Optional, Any
from .breadcrumb_bar import render_breadcrumb_bar
from .status_badge import render_status_badge


def render_page_header(
    path: List[Dict[str, Any]],
    title: str,
    subtitle: Optional[str] = None,
    status: Optional[str] = None,
    compact: bool = False,
    divider: bool = True
) -> None:
    """
    Render a standardized page header with breadcrumb navigation, title, and status.

    Args:
        path: Breadcrumb path items (passed to breadcrumb_bar)
        title: Main page title
        subtitle: Optional subtitle text
        status: Optional status state for status badge
        compact: Whether to use compact spacing
        divider: Whether to show divider line after header
    """

    # Render breadcrumb bar
    if path:
        render_breadcrumb_bar(path)

    # Main header content
    title_col, badge_col = st.columns([5, 1])

    with title_col:
        st.markdown(f"## {title}")

        if subtitle:
            st.caption(subtitle)

    if status:
        with badge_col:
            render_status_badge(status)

    if divider:
        st.divider()