"""
Action bar component for page-level actions.
"""

import streamlit as st
from typing import List, Dict, Optional, Any, Callable


def render_action_bar(
    actions: List[Dict[str, Any]],
    justify: str = "start",
    compact: bool = False
) -> None:
    """
    Render an action bar with standardized button styling and layout.

    Args:
        actions: List of action dictionaries with keys:
            - label: str - Button label
            - on_click: callable - Click handler function
            - kind: str (optional) - 'primary', 'secondary', 'danger', 'icon' (default: 'secondary')
            - icon: str (optional) - Icon name for icon-only buttons
            - disabled: bool (optional) - Whether button is disabled
            - help: str (optional) - Tooltip text
            - use_container_width: bool (optional) - Whether to use full width
        justify: How to justify the buttons ('start', 'center', 'end', 'space-between')
        compact: Whether to use compact spacing
    """
    if not actions:
        return

    # Group actions by priority
    primary_actions = []
    secondary_actions = []
    other_actions = []

    for action in actions:
        kind = action.get('kind', 'secondary')
        if kind == 'primary':
            primary_actions.append(action)
        elif kind == 'secondary':
            secondary_actions.append(action)
        else:
            other_actions.append(action)

    # Combine in order: primary, secondary, other
    ordered_actions = primary_actions + secondary_actions + other_actions

    # Create columns based on number of actions
    num_actions = len(ordered_actions)
    if num_actions == 0:
        return

    # For spacing, we'll use columns
    cols = st.columns(num_actions)

    for i, action in enumerate(ordered_actions):
        with cols[i]:
            button_type = "primary" if action.get('kind') == 'primary' else "secondary"
            if action.get('kind') == 'danger':
                button_type = "primary"  # Streamlit doesn't have danger, use primary with red styling

            # Handle different button types
            if action.get('kind') == 'icon':
                # Icon-only button
                icon = action.get('icon', '⚙️')
                if st.button(f"{icon} {action['label']}", key=f"action_{i}_{action['label']}",
                           help=action.get('help'), disabled=action.get('disabled', False)):
                    action['on_click']()
            else:
                # Regular button
                if st.button(action['label'], type=button_type, key=f"action_{i}_{action['label']}",
                           use_container_width=action.get('use_container_width', False),
                           disabled=action.get('disabled', False), help=action.get('help')):
                    action['on_click']()

    # Add some spacing after the action bar
    if not compact:
        st.markdown("")