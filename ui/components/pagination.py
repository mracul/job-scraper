import streamlit as st
from typing import Callable, Optional


def render_pagination(
    current_page: int,
    total_items: int,
    items_per_page: int = 50,
    on_page_change: Optional[Callable[[int], None]] = None
) -> int:
    """
    Render a simple pagination control with "Show X more" functionality.

    Args:
        current_page: Current page number (0-based)
        total_items: Total number of items
        items_per_page: Items per page
        on_page_change: Callback when page changes

    Returns:
        New current page number
    """

    total_pages = (total_items + items_per_page - 1) // items_per_page
    current_page = min(current_page, total_pages - 1) if total_pages > 0 else 0

    # Calculate current range
    start_item = current_page * items_per_page + 1
    end_item = min((current_page + 1) * items_per_page, total_items)

    # Display current range
    st.markdown(f"Showing {start_item}-{end_item} of {total_items}")

    # Pagination controls
    col1, col2, col3 = st.columns([1, 2, 1])

    # Previous button
    with col1:
        if current_page > 0:
            if st.button("← Previous", key="pagination_prev"):
                new_page = current_page - 1
                if on_page_change:
                    on_page_change(new_page)
                return new_page

    # Page info
    with col2:
        if total_pages > 1:
            st.markdown(f"Page {current_page + 1} of {total_pages}", help="Current page")
        else:
            st.markdown("All items shown")

    # Next/Show more button
    with col3:
        if current_page < total_pages - 1:
            remaining_items = total_items - end_item
            show_count = min(items_per_page, remaining_items)

            button_text = f"Show {show_count} more →" if show_count < items_per_page else "Next →"

            if st.button(button_text, key="pagination_next"):
                new_page = current_page + 1
                if on_page_change:
                    on_page_change(new_page)
                return new_page

    return current_page


def render_simple_load_more(
    loaded_count: int,
    total_items: int,
    load_increment: int = 50,
    on_load_more: Optional[Callable[[], None]] = None
) -> None:
    """
    Render a simple "Load more" button for progressive loading.

    Args:
        loaded_count: Number of items currently loaded
        total_items: Total number of items available
        load_increment: How many more to load
        on_load_more: Callback when load more is clicked
    """

    if loaded_count >= total_items:
        st.markdown(f"All {total_items} items loaded")
        return

    remaining = total_items - loaded_count
    load_count = min(load_increment, remaining)

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        if st.button(f"Show {load_count} more", use_container_width=True, key="load_more"):
            if on_load_more:
                on_load_more()