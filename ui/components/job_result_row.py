import streamlit as st
from typing import Dict, Any, Callable, Optional
from datetime import datetime, timedelta


def render_job_result_row(
    job: Dict[str, Any],
    on_job_click: Callable[[str], None],
    is_selected: bool = False,
    show_view_button: bool = False
) -> None:
    """
    Render a single job result row with metadata chips.

    Args:
        job: Job data dictionary
        on_job_click: Callback when job is clicked
        is_selected: Whether this job is selected
        show_view_button: Whether to show a view button instead of making row clickable
    """

    # Row container with optional selection styling
    row_style = "background-color: #f0f8ff;" if is_selected else ""

    with st.container():
        # Main content row
        if show_view_button:
            # Layout with view button on right
            col1, col2 = st.columns([5, 1])

            with col1:
                _render_job_content(job, on_job_click, clickable=False)

            with col2:
                if st.button("View", key=f"view_job_{job['id']}", use_container_width=True):
                    on_job_click(job['id'])
        else:
            # Clickable row
            _render_job_content(job, on_job_click, clickable=True)

        # Metadata chips row
        _render_job_metadata_chips(job)

        # Divider
        st.divider()


def _render_job_content(job: Dict[str, Any], on_job_click: Callable[[str], None], clickable: bool) -> None:
    """Render the main job content (title, company, description)."""

    job_id = job['id']
    title = job.get('title', 'Untitled Job')
    company = job.get('company', 'Unknown Company')
    description = job.get('description', '')

    if clickable:
        # Make the entire content clickable
        content = f"""
        <div style="cursor: pointer; padding: 10px; border-radius: 5px;" onclick="document.getElementById('job_click_{job_id}').click()">
            <h4 style="margin: 0; color: #1f77b4;">{title}</h4>
            <p style="margin: 5px 0; color: #666; font-weight: bold;">{company}</p>
            <p style="margin: 5px 0; color: #333;">{description[:200]}{'...' if len(description) > 200 else ''}</p>
        </div>
        """
        st.markdown(content, unsafe_allow_html=True)

        # Hidden button for click handling
        if st.button("", key=f"job_click_{job_id}", help="Click to view job details"):
            on_job_click(job_id)
    else:
        # Non-clickable content
        st.markdown(f"#### {title}")
        st.markdown(f"**{company}**")
        if description:
            st.markdown(f"{description[:200]}{'...' if len(description) > 200 else ''}")


def _render_job_metadata_chips(job: Dict[str, Any]) -> None:
    """Render metadata chips for the job."""

    chips = []

    # Source
    source = job.get('source', 'unknown')
    chips.append(_create_chip(f"📄 {source}", "source"))

    # Posted age
    posted_date = job.get('posted_date')
    if posted_date:
        age_text = _calculate_posted_age(posted_date)
        chips.append(_create_chip(f"🕒 {age_text}", "age"))

    # Work type
    work_type = job.get('work_type')
    if work_type:
        work_icon = {
            'full-time': '💼',
            'part-time': '⏰',
            'contract': '📝',
            'freelance': '💻',
            'internship': '🎓'
        }.get(work_type.lower(), '💼')
        chips.append(_create_chip(f"{work_icon} {work_type}", "work_type"))

    # Location type
    location_type = job.get('location_type', '').lower()
    if location_type in ['remote', 'hybrid', 'onsite']:
        location_icon = {
            'remote': '🏠',
            'hybrid': '🏢🏠',
            'onsite': '🏢'
        }[location_type]
        chips.append(_create_chip(f"{location_icon} {location_type}", "location"))

    # Salary
    salary = job.get('salary')
    if salary:
        chips.append(_create_chip(f"💰 {salary}", "salary"))

    # Render chips in a flex layout
    if chips:
        chips_html = '<div style="display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px;">' + ''.join(chips) + '</div>'
        st.markdown(chips_html, unsafe_allow_html=True)


def _create_chip(text: str, category: str) -> str:
    """Create a styled chip HTML element."""
    colors = {
        'source': '#e3f2fd',
        'age': '#fff3e0',
        'work_type': '#e8f5e8',
        'location': '#fce4ec',
        'salary': '#f3e5f5'
    }

    bg_color = colors.get(category, '#f5f5f5')
    text_color = '#333'

    return f"""
    <span style="
        background-color: {bg_color};
        color: {text_color};
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: 500;
        white-space: nowrap;
    ">{text}</span>
    """


def _calculate_posted_age(posted_date: str) -> str:
    """Calculate human-readable age from posted date."""
    try:
        if isinstance(posted_date, str):
            dt = datetime.fromisoformat(posted_date.replace('Z', '+00:00'))
        else:
            dt = posted_date

        now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
        diff = now - dt

        if diff.days == 0:
            hours = diff.seconds // 3600
            return f"{hours}h ago" if hours > 0 else "Just now"
        elif diff.days == 1:
            return "1d ago"
        elif diff.days < 7:
            return f"{diff.days}d ago"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"{weeks}w ago"
        else:
            months = diff.days // 30
            return f"{months}mo ago"
    except:
        return "Unknown"