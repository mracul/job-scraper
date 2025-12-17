import streamlit as st
from typing import List, Dict, Callable, Any


def render_breadcrumb_bar(
    path: List[Dict[str, Any]],
    actions: List[Dict[str, Any]]
) -> None:
    """
    Render a breadcrumb bar with hierarchical path and right-aligned actions.

    Args:
        path: List of path items with keys:
            - label: str - Display label
            - on_click: callable - Click handler
            - active: bool (optional) - Whether this is the active/current item
        actions: List of action items with keys:
            - label: str - Action label
            - on_click: callable - Click handler
            - icon: str (optional) - Icon emoji or text
    """

    # Create two columns: breadcrumbs on left, actions on right
    col1, col2 = st.columns([3, 1])

    with col1:
        # Render breadcrumbs
        breadcrumb_parts = []
        for i, item in enumerate(path):
            label = item["label"]
            on_click = item.get("on_click")
            active = item.get("active", False)

            # Shorten long labels for display
            display_label = _shorten_label(label)

            # Use tooltip for full label if shortened
            help_text = label if display_label != label else None

            if active:
                # Active item is not clickable, just display
                st.markdown(f"**{display_label}**", help=help_text)
            else:
                # Clickable breadcrumb
                if st.button(display_label, key=f"breadcrumb_{i}", help=help_text):
                    on_click()

            # Add separator if not the last item
            if i < len(path) - 1:
                st.markdown(" › ", unsafe_allow_html=True)

    with col2:
        # Render actions from right to left
        if actions:
            action_cols = st.columns(len(actions))
            for i, action in enumerate(actions):
                with action_cols[len(actions) - 1 - i]:  # Reverse order for right alignment
                    icon = action.get("icon", "")
                    label = action["label"]
                    on_click = action.get("on_click")

                    button_label = f"{icon} {label}" if icon else label

                    if st.button(button_label, key=f"action_{i}", use_container_width=True):
                        on_click()


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