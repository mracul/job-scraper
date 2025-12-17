import streamlit as st
from typing import List, Dict, Callable, Any, Optional


def render_bulk_action_bar(
    selection_count: int,
    actions: List[Dict[str, Any]],
    on_clear: Optional[Callable] = None
) -> None:
    """
    Render a bulk action bar that appears when items are selected.

    Args:
        selection_count: Number of selected items
        actions: List of action items with keys:
            - label: str - Action label
            - on_click: callable - Click handler
            - kind: str (optional) - 'primary', 'danger', 'secondary'
            - disabled: bool (optional) - Whether action is disabled
            - disabled_reason: str (optional) - Reason why disabled (shows in tooltip)
        on_clear: Optional callback to clear selection
    """

    if selection_count <= 0:
        return

    # Container for the bulk action bar
    with st.container():
        # Selection count and clear button
        col1, col2 = st.columns([1, 3])

        with col1:
            st.markdown(f"**{selection_count} selected**")

        with col2:
            if on_clear and st.button("Clear", key="bulk_clear"):
                on_clear()

        st.divider()

        # Action buttons
        if actions:
            # Group actions by kind
            primary_actions = [a for a in actions if a.get('kind') == 'primary']
            danger_actions = [a for a in actions if a.get('kind') == 'danger']
            secondary_actions = [a for a in actions if a.get('kind') == 'secondary']

            # Layout: primary first, then danger, then secondary
            all_actions = primary_actions + danger_actions + secondary_actions

            if all_actions:
                cols = st.columns(len(all_actions))
                for i, action in enumerate(all_actions):
                    with cols[i]:
                        _render_bulk_action_button(action)


def _render_bulk_action_button(action: Dict[str, Any]) -> None:
    """
    Render a single bulk action button with appropriate styling.
    """
    label = action['label']
    on_click = action.get('on_click')
    kind = action.get('kind', 'secondary')
    disabled = action.get('disabled', False)
    disabled_reason = action.get('disabled_reason', '')

    # Determine button styling
    button_type = 'primary' if kind == 'primary' else 'secondary'

    # For danger actions, we'll use custom styling
    if kind == 'danger':
        # Custom danger button styling
        button_html = f"""
        <style>
        .danger-bulk-btn {{
            background-color: #dc3545;
            color: white;
            border: none;
            padding: 0.5em 1em;
            border-radius: 0.25em;
            cursor: pointer;
            font-size: 0.9em;
            width: 100%;
        }}
        .danger-bulk-btn:hover {{
            background-color: #c82333;
        }}
        .danger-bulk-btn:disabled {{
            background-color: #6c757d;
            cursor: not-allowed;
        }}
        </style>
        """

        if disabled:
            st.markdown(button_html, unsafe_allow_html=True)
            st.button(
                label,
                disabled=True,
                use_container_width=True,
                help=disabled_reason or "Action not available"
            )
        else:
            st.markdown(button_html, unsafe_allow_html=True)
            if st.button(label, use_container_width=True, help=disabled_reason):
                if on_click:
                    on_click()
    else:
        # Standard primary/secondary buttons
        if st.button(
            label,
            type=button_type,
            disabled=disabled,
            use_container_width=True,
            help=disabled_reason
        ):
            if on_click and not disabled:
                on_click()