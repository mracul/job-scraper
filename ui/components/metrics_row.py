import streamlit as st
from typing import List, Dict, Any, Optional


def render_metrics_row(
    metrics: List[Dict[str, Any]],
    columns: Optional[int] = None
) -> None:
    """
    Render a row of metric cards.

    Args:
        metrics: List of metric dictionaries with keys:
            - label: str - Metric label
            - value: str/int/float - Metric value
            - delta: str/int/float (optional) - Change indicator
            - delta_color: str (optional) - 'normal', 'inverse', 'off'
            - help: str (optional) - Tooltip text
        columns: Number of columns (auto-calculated if None)
    """

    if not metrics:
        return

    # Auto-calculate columns if not specified
    if columns is None:
        columns = min(len(metrics), 4)  # Max 4 columns

    # Create columns
    cols = st.columns(columns)

    for i, metric in enumerate(metrics):
        col_idx = i % columns
        with cols[col_idx]:
            _render_metric_card(metric)


def _render_metric_card(metric: Dict[str, Any]) -> None:
    """Render a single metric card."""

    label = metric.get('label', '')
    value = metric.get('value', '')
    delta = metric.get('delta')
    delta_color = metric.get('delta_color', 'normal')
    help_text = metric.get('help')

    # Format value if it's a number
    if isinstance(value, (int, float)):
        if value >= 1000:
            value = f"{value:,.0f}"  # Add commas for thousands
        else:
            value = str(value)

    # Render metric
    st.metric(
        label=label,
        value=value,
        delta=delta,
        delta_color=delta_color,
        help=help_text
    )


def render_compact_metrics_row(
    metrics: List[Dict[str, Any]]
) -> None:
    """
    Render metrics in a more compact inline format.

    Args:
        metrics: Same as render_metrics_row
    """

    if not metrics:
        return

    # Render as inline text with separators
    metric_parts = []

    for metric in metrics:
        label = metric.get('label', '')
        value = metric.get('value', '')

        # Format value
        if isinstance(value, (int, float)):
            if value >= 1000:
                value = f"{value:,.0f}"
            else:
                value = str(value)

        delta = metric.get('delta')
        if delta is not None:
            if isinstance(delta, (int, float)):
                delta_str = f"{delta:+.1f}" if isinstance(delta, float) else f"{delta:+d}"
            else:
                delta_str = str(delta)

            # Color coding for delta
            delta_color = metric.get('delta_color', 'normal')
            if delta_color == 'inverse':
                color = "red" if delta.startswith('+') else "green"
            elif delta_color == 'off':
                color = "gray"
            else:  # normal
                color = "green" if delta.startswith('+') else "red"

            delta_html = f' <span style="color: {color}; font-size: 0.8em;">({delta_str})</span>'
        else:
            delta_html = ""

        metric_parts.append(f"**{label}:** {value}{delta_html}")

    # Join with separators
    metrics_text = " • ".join(metric_parts)
    st.markdown(metrics_text, unsafe_allow_html=True)