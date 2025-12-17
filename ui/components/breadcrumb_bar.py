import streamlit as st
from typing import List, Dict, Any


def render_breadcrumb_bar(path: List[Dict[str, Any]]) -> None:
    """Render a breadcrumb path without inline actions.

    Args:
        path: List of path items with keys:
            - label: str - Display label
            - on_click: callable - Click handler (ignored when active)
            - active: bool (optional) - Whether this is the active/current item
    """

    if not path:
        return

    cols = st.columns(len(path) * 2 - 1)

    for i, item in enumerate(path):
        label = item["label"]
        on_click = item.get("on_click")
        active = item.get("active", False)

        display_label = _shorten_label(label)
        help_text = label if display_label != label else None

        col_idx = i * 2
        with cols[col_idx]:
            if active or on_click is None:
                st.markdown(f"**{display_label}**", help=help_text)
            else:
                if st.button(display_label, key=f"breadcrumb_{i}", help=help_text):
                    on_click()

        if i < len(path) - 1:
            with cols[col_idx + 1]:
                st.markdown("›", help=None)


def _shorten_label(label: str, max_length: int = 30) -> str:
    """
    Shorten a label if it's too long, keeping it readable.

    Args:
        label: The original label
        max_length: Maximum length before shortening

    Returns:
        Shortened label if needed
    """
    if len(label) <= max_length:
        return label

    # Try to shorten at word boundaries
    words = label.split()
    if len(words) > 1:
        # Keep first and last word if possible
        if len(words[0]) + len(words[-1]) + 3 <= max_length:  # +3 for " … "
            return f"{words[0]} … {words[-1]}"

    # Fall back to simple truncation
    return label[:max_length - 3] + "…"