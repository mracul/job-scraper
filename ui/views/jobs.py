"""
Job Scraper - Jobs View
UI components for job explorer and job detail views.
"""

import streamlit as st
import pandas as pd
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Import data loading functions
from ui.io_cache import load_analysis, load_jobs_csv

# Import constants
from ui.constants import CATEGORY_LABELS


def navigate_to(*args, **kwargs):
    """Placeholder - will be imported from main app"""
    pass


def render_job_explorer():
    """Render the job explorer with tag filtering."""
    run_path = Path(st.session_state.selected_run)
    analysis = load_analysis(run_path)
    jobs_df = load_jobs_csv(run_path)

    st.header("🔍 Job Explorer")

    if not analysis or jobs_df is None:
        st.warning("Missing data for job exploration.")
        return

    # Calculate posting dates for sorting
    posting_dates = {}
    for idx in range(len(jobs_df)):
        job_row = jobs_df.iloc[idx]
        date_value = job_row.get("date_posted")
        if pd.notna(date_value) and date_value:
            try:
                # Extract scraping date from folder name (format: ..._YYYYMMDD_HHMMSS)
                folder_name = run_path.name
                date_match = re.search(r'_(\d{8})_', folder_name)
                if date_match:
                    scrape_date_str = date_match.group(1)
                    scrape_date = datetime.strptime(scrape_date_str, "%Y%m%d")

                    # Parse date_posted (e.g., "2d ago", "1w ago")
                    days_ago = 0
                    if "d ago" in date_value:
                        days_ago = int(re.search(r'(\d+)d ago', date_value).group(1))
                    elif "w ago" in date_value:
                        days_ago = int(re.search(r'(\d+)w ago', date_value).group(1)) * 7
                    elif "h ago" in date_value:
                        hours_ago = int(re.search(r'(\d+)h ago', date_value).group(1))
                        days_ago = hours_ago // 24

                    posting_date = scrape_date - pd.Timedelta(days=days_ago)
                    posting_dates[idx + 1] = posting_date  # job_id is 1-indexed
            except (ValueError, AttributeError):
                pass

    # Sort jobs by most recent date (newest first)
    reverse_sort = True

    def _job_sort_key(job_id: int):
        dt = posting_dates.get(job_id)
        if dt is None:
            return datetime.min if reverse_sort else datetime.max  # Unknown dates at end
        return dt

    # Get job data from analysis (for requirements)
    job_details = {j["id"]: j for j in analysis.get("job_details", [])}

    # Apply filters to get matching jobs
    all_selected_terms = []
    for cat, terms in st.session_state.selected_filters.items():
        for term in terms:
            all_selected_terms.append((cat, term))

    # Build job matching results
    job_matches = {}  # job_id -> set of matched (cat, term) tuples

    for job_id, job_data in job_details.items():
        reqs = job_data.get("requirements", {})
        presence_reqs = reqs.get("presence", {}) if isinstance(reqs, dict) else reqs
        matched = set()

        for cat, term in all_selected_terms:
            if term in presence_reqs.get(cat, []):
                matched.add((cat, term))

        if matched or not all_selected_terms:
            job_matches[job_id] = matched

    # Filter by search text
    if st.session_state.search_text:
        search_lower = st.session_state.search_text.lower()
        filtered_ids = set()
        for job_id in job_matches:
            job_data = job_details.get(job_id, {})
            title = (job_data.get("title") or "").lower()
            company = (job_data.get("company") or "").lower()
            if search_lower in title or search_lower in company:
                filtered_ids.add(job_id)
        job_matches = {k: v for k, v in job_matches.items() if k in filtered_ids}

    # Apply match mode filter
    if all_selected_terms:
        if st.session_state.filter_mode == "all":
            # Must match ALL selected tags
            required = set(all_selected_terms)
            job_matches = {k: v for k, v in job_matches.items() if v == required}
        else:
            # Must match ANY (at least one)
            job_matches = {k: v for k, v in job_matches.items() if v}

    # Group jobs by their matched tag combination
    groups = defaultdict(list)
    for job_id, matched_tags in job_matches.items():
        # Create a hashable key for the tag combination
        tag_key = tuple(sorted(matched_tags)) if matched_tags else (("_none", "All Jobs"),)
        groups[tag_key].append(job_id)

    # Sort groups by size descending
    sorted_groups = sorted(groups.items(), key=lambda x: len(x[1]), reverse=True)

    # Display active filters summary
    active_filters = []
    for cat, terms in st.session_state.selected_filters.items():
        for term in terms:
            active_filters.append((cat, term))
    if active_filters or st.session_state.search_text:
        col1, col2 = st.columns([3,1])
        with col1:
            filter_text = []
            if st.session_state.search_text:
                filter_text.append(f"🔎 {st.session_state.search_text}")
            for cat, term in active_filters:
                cat_label = CATEGORY_LABELS.get(cat, cat)
                filter_text.append(f"{cat_label}: {term}")
            if filter_text:
                st.caption("Active filters: " + " | ".join(filter_text))
        with col2:
            if st.button("Clear All", key="clear_filters_main"):
                navigate_to(
                    "reports",
                    selected_run=st.session_state.selected_run,
                    view_mode="explorer",
                    viewing_job_id=None,
                    selected_filters={},
                    filter_mode="any",
                    search_text="",
                )
                st.rerun()

    # Display results
    st.subheader(f"Results: {len(job_matches)} jobs")

    if not job_matches:
        st.info("No jobs match the current filters.")
        return

    for tag_key, job_ids in sorted_groups:
        # Build group header
        if tag_key == (("_none", "All Jobs"),):
            header = "All Jobs"
        else:
            tag_labels = [f"{t[1]}" for t in tag_key]
            header = ", ".join(tag_labels)

        with st.expander(f"**{header}** ({len(job_ids)} jobs)", expanded=True):
            for job_id in sorted(job_ids, key=_job_sort_key, reverse=reverse_sort):
                job_data = job_details.get(job_id, {})
                title = job_data.get("title", f"Job {job_id}")
                company = job_data.get("company", "Unknown")

                job_row = jobs_df.iloc[job_id - 1] if 0 <= job_id - 1 < len(jobs_df) else None
                date_text = None
                days_ago_text = ""
                if job_row is not None:
                    date_value = job_row.get("date_posted")
                    if pd.notna(date_value) and date_value:
                        date_text = str(date_value)
                        # Calculate days ago
                        try:
                            # Extract scraping date from folder name (format: ..._YYYYMMDD_HHMMSS)
                            folder_name = run_path.name
                            date_match = re.search(r'_(\d{8})_', folder_name)
                            if date_match:
                                scrape_date_str = date_match.group(1)
                                scrape_date = datetime.strptime(scrape_date_str, "%Y%m%d")

                                # Parse date_posted (e.g., "2d ago", "1w ago")
                                days_ago = 0
                                if "d ago" in date_value:
                                    days_ago = int(re.search(r'(\d+)d ago', date_value).group(1))
                                elif "w ago" in date_value:
                                    days_ago = int(re.search(r'(\d+)w ago', date_value).group(1)) * 7
                                elif "h ago" in date_value:
                                    hours_ago = int(re.search(r'(\d+)h ago', date_value).group(1))
                                    days_ago = hours_ago // 24

                                posting_date = scrape_date - pd.Timedelta(days=days_ago)
                                actual_days_ago = (datetime.now() - posting_date).days
                                if actual_days_ago == 0:
                                    days_ago_text = " (today)"
                                elif actual_days_ago == 1:
                                    days_ago_text = " (1 day ago)"
                                else:
                                    days_ago_text = f" ({actual_days_ago} days ago)"
                        except (ValueError, AttributeError):
                            pass  # Keep days_ago_text empty if parsing fails

                col1, col2, col3 = st.columns([0.25, 3, 1])

                with col1:
                    if days_ago_text:
                        st.caption(f"🕒{days_ago_text.strip(' ()')}")
                    elif date_text:
                        st.caption(f"📅 {date_text}")

                with col2:
                    if st.button(f"{title} — {company}", key=f"job_title_{job_id}"):
                        navigate_to(
                            "reports",
                            selected_run=st.session_state.selected_run,
                            view_mode="job_detail",
                            viewing_job_id=job_id,
                        )
                        st.rerun()

                with col3:
                    if st.button("View", key=f"view_job_{job_id}", use_container_width=True):
                        navigate_to(
                            "reports",
                            selected_run=st.session_state.selected_run,
                            view_mode="job_detail",
                            viewing_job_id=job_id,
                        )
                        st.rerun()


def render_job_detail_view():
    """Render detailed view of a single job."""
    run_path = Path(st.session_state.selected_run)
    analysis = load_analysis(run_path)
    jobs_df = load_jobs_csv(run_path)

    job_id = st.session_state.viewing_job_id

    if not analysis or jobs_df is None or job_id is None:
        st.warning("Job data not available.")
        return

    # Get job data from analysis (for requirements)
    job_details = {j["id"]: j for j in analysis.get("job_details", [])}
    job_meta = job_details.get(job_id, {})

    # Get full job data from CSV (for description, url, etc.)
    # CSV is 0-indexed, job_id is 1-indexed
    csv_idx = job_id - 1
    if csv_idx < 0 or csv_idx >= len(jobs_df):
        st.warning("Job not found in data.")
        return

    job_row = jobs_df.iloc[csv_idx]

    # Header card
    st.header(job_row.get("title", "Unknown Job"))
    st.subheader(f"🏢 {job_row.get('company', 'Unknown Company')}")

    # Metadata row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"📍 **Location:** {job_row.get('location', 'Not specified')}")
    with col2:
        salary = job_row.get("salary")
        if pd.notna(salary) and salary:
            st.markdown(f"💰 **Salary:** {salary}")
        else:
            st.markdown("💰 **Salary:** Not specified")
    with col3:
        date_posted = job_row.get("date_posted")
        if pd.notna(date_posted) and date_posted:
            st.markdown(f"📅 **Posted:** {date_posted}")
        else:
            st.markdown("📅 **Posted:** Not specified")
    with col4:
        st.markdown(f"🌐 **Source:** {job_row.get('source', 'Unknown')}")

    # Link to original
    url = job_row.get("url")
    if pd.notna(url) and url:
        st.markdown(f"### [🔗 Open Original Listing →]({url})")

    st.markdown("---")

    # Matched requirements as badges
    reqs = job_meta.get("requirements", {})
    if any(reqs.values()):
        st.subheader("🏷️ Matched Requirements")

        for cat_key, cat_label in CATEGORY_LABELS.items():
            terms = reqs.get(cat_key, [])
            if terms:
                st.markdown(f"**{cat_label}:**")
                badge_html = " ".join([f'`{term}`' for term in terms])
                st.markdown(badge_html)

        st.markdown("---")

    # Full description
    st.subheader("📄 Full Description")

    full_desc = job_row.get("full_description")
    short_desc = job_row.get("description")

    description = full_desc if pd.notna(full_desc) and full_desc else short_desc

    if pd.notna(description) and description:
        st.markdown(description)
    else:
        st.info("No description available.")