import streamlit as st
from typing import List, Dict, Optional, Any
from .breadcrumb_bar import render_breadcrumb_bar
from .status_badge import render_status_badge


def render_page_header(
    path: List[Dict[str, Any]],
    title: str,
    subtitle: Optional[str] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
    status: Optional[str] = None,
    compact: bool = False,
    divider: bool = True
) -> None:
    """
    Render a standardized page header with breadcrumb navigation, title, and actions.

    Args:
        path: Breadcrumb path items (passed to breadcrumb_bar)
        title: Main page title
        subtitle: Optional subtitle text
        actions: Optional list of action items with keys:
            - label: str - Action label
            - on_click: callable - Click handler
            - kind: str (optional) - 'primary', 'secondary', 'danger', 'icon'
            - icon: str (optional) - Icon for icon-only actions
        status: Optional status state for status badge
        compact: Whether to use compact spacing
        divider: Whether to show divider line after header
    """

    # Process actions to separate breadcrumb actions from header actions
    breadcrumb_actions = []
    header_actions = []

    if actions:
        for action in actions:
            # Header actions are those with specific kinds
            if 'kind' in action:
                header_actions.append(action)
            else:
                # Default to breadcrumb actions
                breadcrumb_actions.append(action)

    # Render breadcrumb bar with any non-header actions
    if path or breadcrumb_actions:
        render_breadcrumb_bar(path, breadcrumb_actions)

    # Main header content
    header_cols = st.columns([3, 1]) if header_actions else [1]

    with header_cols[0]:
        # Title and status
        title_cols = st.columns([4, 1]) if status else [1]

        with title_cols[0]:
            title_size = "h2" if not compact else "h3"
            st.markdown(f"## {title}", unsafe_allow_html=True)

            if subtitle:
                st.markdown(f"*{subtitle}*")

        if status:
            with title_cols[1]:
                render_status_badge(status)

    # Header actions (right side)
    if header_actions:
        with header_cols[1]:
            _render_header_actions(header_actions)

    # Divider
    if divider:
        st.divider()


def _render_header_actions(actions: List[Dict[str, Any]]) -> None:
    """
    Render header actions with proper hierarchy and styling.

    Action hierarchy: Primary (max 1), Secondary (max 2), then overflow menu.
    """

    # Separate actions by kind
    primary_actions = [a for a in actions if a.get('kind') == 'primary']
    secondary_actions = [a for a in actions if a.get('kind') == 'secondary']
    danger_actions = [a for a in actions if a.get('kind') == 'danger']
    icon_actions = [a for a in actions if a.get('kind') == 'icon']

    # Limit counts
    primary_actions = primary_actions[:1]  # Max 1 primary
    secondary_actions = secondary_actions[:2]  # Max 2 secondary

    # Combine in display order: primary, secondary, danger, icon
    display_actions = primary_actions + secondary_actions + danger_actions + icon_actions

    # Handle overflow if too many actions
    overflow_actions = []
    if len(display_actions) > 4:  # Arbitrary limit for overflow
        display_actions, overflow_actions = display_actions[:3], display_actions[3:]

    # Render actions
    if display_actions:
        cols = st.columns(len(display_actions))
        for i, action in enumerate(display_actions):
            with cols[i]:
                _render_action_button(action)

    # Render overflow menu if needed
    if overflow_actions:
        with st.columns(1)[0]:
            with st.popover("⋯"):
                for action in overflow_actions:
                    if st.button(action['label'], key=f"overflow_{action['label']}"):
                        action['on_click']()


def _render_action_button(action: Dict[str, Any]) -> None:
    """
    Render a single action button with appropriate styling based on kind.
    """
    kind = action.get('kind', 'secondary')
    label = action['label']
    on_click = action.get('on_click')
    icon = action.get('icon', '')

    button_label = f"{icon} {label}" if icon else label

    # Style based on kind
    if kind == 'primary':
        # Filled/accent button
        if st.button(button_label, type='primary', use_container_width=True):
            if on_click:
                on_click()
    elif kind == 'secondary':
        # Outline/muted button
        if st.button(button_label, use_container_width=True):
            if on_click:
                on_click()
    elif kind == 'danger':
        # Red outline/solid
        st.markdown(
            f'<style>.danger-btn {{ background-color: #dc3545; color: white; border: none; padding: 0.5em 1em; border-radius: 0.25em; }}</style>',
            unsafe_allow_html=True
        )
        if st.button(button_label, use_container_width=True):
            if on_click:
                on_click()
    elif kind == 'icon':
        # Icon-only utilities
        if st.button(icon or label, use_container_width=True):
            if on_click:
                on_click()