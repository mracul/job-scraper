"""Shared renderer for run and bundle lists.

This component renders compact, bordered rows with consistent columns for
both run and bundle contexts. Selection is handled outside the component via
the returned `selected_ids` set so views can drive selection-aware action
bars. Bundle rows can optionally show their child runs inline while reusing
the same row renderer for visual consistency.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import streamlit as st

from .status_badge import render_status_badge

Row = Dict[str, Any]


def render_run_list(
    rows: List[Row],
    *,
    mode: str,
    selected_ids: Iterable[str] | None = None,
    expanded_ids: Iterable[str] | None = None,
    child_lookup: Optional[Dict[str, List[Row]]] = None,
    selection_enabled: bool = True,
    on_open: Optional[callable] = None,
) -> Tuple[Set[str], Set[str]]:
    """Render a list of runs or bundles with shared styling.

    Args:
        rows: Items to render. Each row should include id, name, job_count,
            created (datetime | str | None), and status (str).
        mode: "runs" or "bundles" (used for key scoping).
        selected_ids: Optional iterable of ids that should start selected.
        expanded_ids: Optional iterable of bundle ids that should start expanded.
        child_lookup: Optional mapping of bundle_id -> list of child run rows.
        selection_enabled: Whether checkboxes should be interactive.
        on_open: Optional callback accepting a row dict when its name is clicked.

    Returns:
        A tuple of (selected_ids, expanded_ids) after handling widget state.
    """

    selected_ids = set(selected_ids or [])
    expanded_ids = set(expanded_ids or [])
    child_lookup = child_lookup or {}

    header_cols = st.columns([0.5, 3.0, 1.0, 1.4, 1.0, 0.9])
    if selection_enabled:
        header_cols[0].markdown("**Select**")
    else:
        header_cols[0].markdown("\u00a0")
    header_cols[1].markdown("**Name**")
    header_cols[2].markdown("**Jobs**")
    header_cols[3].markdown("**Created**")
    header_cols[4].markdown("**Status**")
    header_cols[5].markdown("**Actions**")
    st.divider()

    checkbox_keys: dict[str, str] = {}
    expand_keys: dict[str, str] = {}

    for row in rows:
        row_id = str(row.get("id"))
        is_selected = row_id in selected_ids
        is_expanded = row_id in expanded_ids
        has_children = bool(child_lookup.get(row_id))

        checkbox_keys[row_id] = _checkbox_key(mode, row_id)
        expand_keys[row_id] = _expand_key(mode, row_id)

        _render_row(
            row,
            mode=mode,
            selected=is_selected,
            expanded=is_expanded,
            has_children=has_children,
            selection_enabled=selection_enabled,
            on_open=on_open,
        )

        if is_expanded and has_children:
            with st.container(border=True):
                st.caption("Runs in bundle")
                child_rows = child_lookup[row_id]
                _render_child_rows(
                    child_rows,
                    mode=mode,
                    selected_ids=selected_ids,
                    selection_enabled=False,
                    on_open=on_open,
                )

        st.divider()

    # Recompute selection from widget state to keep persistence on rerun
    updated_selected: Set[str] = set()
    for row_id in checkbox_keys:
        key = checkbox_keys[row_id]
        if st.session_state.get(key, False):
            updated_selected.add(row_id)

    updated_expanded: Set[str] = set()
    for row_id in expand_keys:
        if st.session_state.get(expand_keys[row_id], False):
            updated_expanded.add(row_id)

    return updated_selected, updated_expanded


def _render_row(
    row: Row,
    *,
    mode: str,
    selected: bool,
    expanded: bool,
    has_children: bool,
    selection_enabled: bool,
    on_open: Optional[callable],
) -> None:
    caret = "▾" if expanded else "▸"
    created_label = _format_created(row.get("created"))
    job_count = row.get("job_count") or 0

    cols = st.columns([0.5, 3.0, 1.0, 1.4, 1.0, 0.9])

    with cols[0]:
        inner = st.columns([0.5, 0.5])
        with inner[0]:
            if has_children:
                st.toggle(
                    caret,
                    key=_expand_key(mode, str(row.get("id"))),
                    label_visibility="collapsed",
                    value=expanded,
                    disabled=not has_children,
                    help="Show runs in this bundle" if has_children else None,
                )
            else:
                st.markdown("\u00a0")
        with inner[1]:
            st.checkbox(
                "",
                key=_checkbox_key(mode, str(row.get("id"))),
                value=selected,
                disabled=not selection_enabled,
                label_visibility="collapsed",
                help="Select to compile or delete",
            )

    with cols[1]:
        label = row.get("name", "Run")
        subtitle = row.get("subtitle")
        if st.button(
            label,
            key=f"open_{mode}_{row.get('id')}",
            help="Open details",
        ):
            if on_open:
                on_open(row)
        if subtitle:
            st.caption(subtitle)

    cols[2].markdown(f"{job_count}")
    cols[3].markdown(created_label)

    with cols[4]:
        status = row.get("status") or ""
        status_text = row.get("status_text")
        render_status_badge(status or "generated", text=status_text or status)

    with cols[5]:
        action_help = row.get("action_help", "Open")
        if st.button("🔍", key=f"action_{mode}_{row.get('id')}", help=action_help):
            if on_open:
                on_open(row)


def _render_child_rows(
    child_rows: List[Row],
    *,
    mode: str,
    selected_ids: Set[str],
    selection_enabled: bool,
    on_open: Optional[callable],
) -> None:
    for child in child_rows:
        _render_row(
            child,
            mode=f"{mode}_child",
            selected=str(child.get("id")) in selected_ids,
            expanded=False,
            has_children=False,
            selection_enabled=selection_enabled,
            on_open=on_open,
        )


def _format_created(created: Any) -> str:
    if isinstance(created, datetime):
        return created.strftime("%b %d, %H:%M")
    if isinstance(created, str) and created:
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %H:%M")
        except Exception:
            return created[:16]
    return "—"


def _checkbox_key(mode: str, row_id: str) -> str:
    safe_id = _safe_key_fragment(row_id)
    return f"{mode}_select_{safe_id}"


def _expand_key(mode: str, row_id: str) -> str:
    safe_id = _safe_key_fragment(row_id)
    return f"{mode}_expand_{safe_id}"


def _safe_key_fragment(value: str) -> str:
    return value.replace("/", "_").replace("\\", "_")

