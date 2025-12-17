# ui/navigation/url_sync.py
"""
URL synchronization for navigation state.
Handles encoding/decoding navigation state to/from URL query parameters.
"""

import streamlit as st
import json
from typing import Dict, Any, Optional
from urllib.parse import parse_qs, urlencode

from .state import NAV_KEYS, snapshot_state, apply_state


def _get_query_params() -> Dict[str, Any]:
    """Get current URL query parameters."""
    query_params = st.query_params
    return dict(query_params) if query_params else {}


def _set_query_params(params: Dict[str, Any]) -> None:
    """Set URL query parameters."""
    # Clear existing params
    st.query_params.clear()
    # Set new params
    for key, value in params.items():
        if value is not None:
            st.query_params[key] = str(value)


def encode_state_for_url(state: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Encode navigation state for URL representation."""
    params = {}

    # Encode navigation state
    for key in NAV_KEYS:
        value = state.get(key)
        if value is not None:
            if isinstance(value, dict):
                params[key] = json.dumps(value, separators=(',', ':'))
            elif isinstance(value, list):
                params[key] = json.dumps(value, separators=(',', ':'))
            else:
                params[key] = str(value)

    # Add extra params if provided
    if extra:
        for key, value in extra.items():
            if value is not None:
                params[key] = str(value)

    return params


def apply_state_from_url() -> bool:
    """Apply navigation state from URL query parameters. Returns True if state changed."""
    params = _get_query_params()
    if not params:
        return False

    new_state = {}

    # Decode navigation state from URL
    for key in NAV_KEYS:
        if key in params:
            value_str = params[key]
            try:
                # Try to parse as JSON first (for dict/list values)
                new_state[key] = json.loads(value_str)
            except (json.JSONDecodeError, TypeError):
                # Fall back to string/int conversion
                if value_str.isdigit():
                    new_state[key] = int(value_str)
                elif value_str in ('true', 'false'):
                    new_state[key] = value_str == 'true'
                else:
                    new_state[key] = value_str

    # Apply the state if it's different
    current_state = snapshot_state()
    if new_state != {k: v for k, v in current_state.items() if k in new_state}:
        apply_state(new_state)
        return True

    return False


def sync_url_with_state(force: bool = False, extra_params: Optional[Dict[str, Any]] = None) -> None:
    """Sync current navigation state to URL query parameters."""
    current_state = snapshot_state()
    url_params = encode_state_for_url(current_state, extra_params)

    current_url_params = _get_query_params()

    # Only update if different or forced
    if force or url_params != current_url_params:
        _set_query_params(url_params)