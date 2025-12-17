import streamlit as st
from typing import List, Dict, Any, Optional
import plotly.graph_objects as go


def render_bar_rank_list(
    title: str,
    items: List[Dict[str, Any]],
    value_key: str = 'count',
    label_key: str = 'label',
    max_items: int = 10,
    show_other: bool = True,
    height: int = 300
) -> None:
    """
    Render a horizontal bar chart showing ranked items with optional "Other" category.

    Args:
        title: Chart title
        items: List of item dictionaries
        value_key: Key for the value to rank by
        label_key: Key for the label to display
        max_items: Maximum items to show individually
        show_other: Whether to show "Other" for remaining items
        height: Chart height in pixels
    """

    # Sort items by value descending
    sorted_items = sorted(items, key=lambda x: x.get(value_key, 0), reverse=True)

    # Split into top items and others
    top_items = sorted_items[:max_items]
    other_items = sorted_items[max_items:]

    # Calculate "Other" total if needed
    other_total = sum(item.get(value_key, 0) for item in other_items) if show_other and other_items else 0

    # Prepare data for plotting
    labels = [item.get(label_key, 'Unknown') for item in top_items]
    values = [item.get(value_key, 0) for item in top_items]

    if other_total > 0:
        labels.append("Other")
        values.append(other_total)

    # Create horizontal bar chart
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=values,
        y=labels,
        orientation='h',
        marker=dict(
            color='rgba(31, 119, 180, 0.8)',
            line=dict(color='rgba(31, 119, 180, 1.0)', width=1)
        ),
        text=[f"{v:,}" for v in values],  # Format with commas
        textposition='auto',
    ))

    fig.update_layout(
        title=title,
        xaxis_title="Count",
        yaxis_title="",
        height=height,
        margin=dict(l=0, r=0, t=40, b=0),
        showlegend=False
    )

    # Reverse y-axis so highest value is on top
    fig.update_yaxes(autorange="reversed")

    st.plotly_chart(fig, use_container_width=True)


def render_simple_rank_list(
    title: str,
    items: List[Dict[str, Any]],
    value_key: str = 'count',
    label_key: str = 'label',
    max_items: int = 10
) -> None:
    """
    Render a simple ranked list without charts.

    Args:
        title: List title
        items: List of item dictionaries
        value_key: Key for the value to rank by
        label_key: Key for the label to display
        max_items: Maximum items to show
    """

    st.markdown(f"**{title}**")

    # Sort items by value descending
    sorted_items = sorted(items, key=lambda x: x.get(value_key, 0), reverse=True)

    # Display top items
    for i, item in enumerate(sorted_items[:max_items], 1):
        label = item.get(label_key, 'Unknown')
        value = item.get(value_key, 0)

        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown(f"{i}. {label}")
        with col2:
            st.markdown(f"**{value:,}**")

    # Show "and X more" if truncated
    remaining = len(sorted_items) - max_items
    if remaining > 0:
        st.markdown(f"*...and {remaining} more*")