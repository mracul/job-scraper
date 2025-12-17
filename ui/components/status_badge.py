import streamlit as st
from typing import Optional


def render_status_badge(
    state: str,
    text: Optional[str] = None,
    tooltip: Optional[str] = None,
    size: str = 'sm',
    variant: str = 'pill'
) -> None:
    """
    Render a status badge with consistent icon and text for the given state.

    Args:
        state: The status state ('cached', 'outdated', 'generated', 'dirty')
        text: Optional custom text to override default
        tooltip: Optional tooltip text
        size: Size variant ('sm', 'md', 'lg')
        variant: Visual variant ('pill', 'inline')
    """

    # Define canonical state mappings
    state_config = {
        'cached': {
            'icon': '✅',
            'text': 'cached',
            'color': 'green'
        },
        'outdated': {
            'icon': '⚠️',
            'text': 'outdated',
            'color': 'orange'
        },
        'generated': {
            'icon': 'ℹ️',
            'text': 'generated',
            'color': 'blue'
        },
        'dirty': {
            'icon': '●',
            'text': 'unsaved changes',
            'color': 'red'
        }
    }

    if state not in state_config:
        # Fallback for unknown states
        config = {
            'icon': '❓',
            'text': state,
            'color': 'gray'
        }
    else:
        config = state_config[state]

    # Use custom text if provided
    display_text = text if text is not None else config['text']

    # Build the badge content
    badge_content = f"{config['icon']} {display_text}"

    # Apply size styling
    size_styles = {
        'sm': 'font-size: 0.8em;',
        'md': 'font-size: 1em;',
        'lg': 'font-size: 1.2em;'
    }
    size_style = size_styles.get(size, size_styles['sm'])

    # Apply variant styling
    if variant == 'pill':
        # Pill style with background
        color_map = {
            'green': '#d4edda',
            'orange': '#fff3cd',
            'blue': '#cce7ff',
            'red': '#f8d7da',
            'gray': '#e2e3e5'
        }
        bg_color = color_map.get(config['color'], color_map['gray'])

        badge_html = f"""
        <span style="
            background-color: {bg_color};
            color: #333;
            padding: 2px 8px;
            border-radius: 12px;
            font-weight: 500;
            white-space: nowrap;
            display: inline-block;
            {size_style}
        " title="{tooltip or ''}">{badge_content}</span>
        """
    else:
        # Inline style (just text with icon)
        badge_html = f"""
        <span style="
            color: #666;
            font-weight: 500;
            white-space: nowrap;
            {size_style}
        " title="{tooltip or ''}">{badge_content}</span>
        """

    st.markdown(badge_html, unsafe_allow_html=True)