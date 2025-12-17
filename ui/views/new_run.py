"""
New Run page view.
"""

import streamlit as st
import json
import re
import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path

from ui.components.page_header import render_page_header
from ui.constants import SCRAPED_DATA_DIR, LOGS_DIR
from ui_core import DEFAULT_SETTINGS, load_settings
from ui.run_state import load_run_state, save_run_state, clear_run_state, _read_run_state_raw
from ui.navigation.actions import navigate_to
from ui.navigation.breadcrumbs import build_breadcrumbs
from ui.navigation.state import snapshot_state


DETAIL_FETCH_LABELS = ["Fetch All", "Skip Details"]
DETAIL_FETCH_VALUES = [None, 0]


def _find_latest_run_after(started_at):
    """Find the most recent run folder created after the given timestamp."""
    if not SCRAPED_DATA_DIR.exists():
        return None

    latest_folder = None
    latest_time = None

    for folder in SCRAPED_DATA_DIR.iterdir():
        if not folder.is_dir():
            continue

        # Extract timestamp from folder name
        timestamp_match = re.search(r'_(\d{8}_\d{6})$', folder.name)
        if timestamp_match:
            timestamp_str = timestamp_match.group(1)
            try:
                folder_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                if started_at is None or folder_time >= started_at:
                    if latest_time is None or folder_time > latest_time:
                        latest_time = folder_time
                        latest_folder = folder
            except ValueError:
                pass

    return latest_folder


def render_run_progress():
    """Render the progress of a running scrape."""
    process = st.session_state.run_process
    log_file = st.session_state.run_log_file
    pid = None
    started_at = None

    # If we lost the process handle (navigated away), try to recover from persisted state
    if process is None:
        run_state_raw = _read_run_state_raw() or {}
        pid = run_state_raw.get("pid")
        log_file = run_state_raw.get("log_file") or log_file
        started_raw = run_state_raw.get("started")
        if isinstance(started_raw, str):
            try:
                started_at = datetime.fromisoformat(started_raw)
            except Exception:
                started_at = None
        st.session_state.run_log_file = log_file
    else:
        run_state_raw = _read_run_state_raw() or {}
        started_raw = run_state_raw.get("started")
        if isinstance(started_raw, str):
            try:
                started_at = datetime.fromisoformat(started_raw)
            except Exception:
                started_at = None

    def _read_log_tail(path: Path, max_lines: int = 400, max_bytes: int = 120_000) -> str:
        """Read the last N lines efficiently without loading the whole file."""
        try:
            if not path.exists():
                return ""

            with open(path, "rb") as f:
                try:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    start = max(0, size - max_bytes)
                    f.seek(start, os.SEEK_SET)
                except Exception:
                    # If seek fails, fall back to reading whole file.
                    f.seek(0)

                chunk = f.read()
            text = chunk.decode("utf-8", errors="replace")
            lines = text.splitlines(True)  # keepends
            if len(lines) <= max_lines:
                return "".join(lines)
            return "".join(lines[-max_lines:])
        except Exception:
            return ""

    def _is_running() -> bool:
        if process is not None:
            return process.poll() is None
        if pid:
            import psutil
            return psutil.pid_exists(pid)
        return False

    # Check if process is still running
    if _is_running():
        st.info("🔄 Scraping in progress...")

        # Cancel button
        if st.button("❌ Cancel Run"):
            if process is not None:
                process.terminate()
            elif pid:
                import psutil
                try:
                    psutil.Process(pid).terminate()
                except Exception:
                    pass
            st.session_state.run_process = None
            clear_run_state()
            st.warning("Run cancelled.")
            st.rerun()

        # Display log tail with live updates
        st.markdown("**Live Log Output:**")
        log_placeholder = st.empty()

        # Continuous update loop
        while _is_running():
            if log_file and Path(log_file).exists():
                log_content = _read_log_tail(Path(log_file), max_lines=100)
                if log_content.strip():
                    # Re-render container to update content and auto-scroll (st.code usually scrolls to end or keeps position)
                    with log_placeholder.container(height=250):
                        st.code(log_content, language="text")
                else:
                    log_placeholder.caption("Waiting for output...")
            else:
                log_placeholder.caption("Waiting for log file...")

            time.sleep(1)

        # Process finished, rerun to show results
        st.rerun()
        return

    else:
        # Process finished
        return_code = None
        if process is not None:
            return_code = process.returncode
        st.session_state.run_process = None
        clear_run_state()

        if return_code == 0:
            st.success("✅ Scraping completed successfully!")
        elif return_code is not None:
            st.error(f"❌ Scraping failed with exit code {return_code}")
        else:
            st.success("✅ Scraping completed!")

        latest_report = _find_latest_run_after(started_at)

        col1, col2, col3 = st.columns(3)
        with col1:
            if latest_report:
                st.button(
                    "📊 Review Report",
                    type="primary",
                    use_container_width=True,
                    on_click=navigate_to,
                    args=("reports",),
                    kwargs={
                        "selected_run": str(latest_report).replace(os.sep, "/"),
                        "view_mode": "overview",
                        "viewing_job_id": None,
                        "selected_filters": {},
                        "filter_mode": "any",
                        "search_text": "",
                    },
                )
        with col2:
            if st.button("📂 View Reports", use_container_width=True):
                navigate_to("reports")
        with col3:
            if st.button("🚀 Start Another Run", use_container_width=True):
                st.rerun()

        # Show final log
        if log_file and Path(log_file).exists():
            with open(log_file, "r", encoding="utf-8") as f:
                log_content = f.read()

            with st.expander("View Full Log", expanded=False):
                st.text_area("Log Output", log_content, height=400)


def render_new_run_page():
    """Render the new run configuration page."""
    # Canonical page layout: PageHeader, ActionBar (optional), content
    breadcrumbs = build_breadcrumbs(snapshot_state())
    render_page_header(
        path=breadcrumbs,
        title="Start New Scraping Run",
        subtitle="Configure and launch a new job scraping operation"
    )

    settings = load_settings()
    scraper_settings = settings.get("scraper", {})
    ui_settings = settings.get("ui", {})

    # Check if a run is in progress (either in session or persisted)
    if st.session_state.run_process is not None or load_run_state() is not None:
        render_run_progress()
        return

    # ─────────────────────────────────────────────────────────────────────────
    # Search Mode Selection
    # ─────────────────────────────────────────────────────────────────────────
    search_mode = st.radio(
        "Search Mode",
        ["Single Search", "Bundle Search"],
        horizontal=True,
        key="new_run_search_mode",
        help="Single Search: one keyword phrase. Bundle Search: multiple keyword phrases combined."
    )

    # ─────────────────────────────────────────────────────────────────────────
    # Search Parameters Section
    # ─────────────────────────────────────────────────────────────────────────
    if search_mode == "Single Search":
        st.subheader("🔎 Search Parameters")

    # Get bundles from settings
    bundles = settings.get("bundles", DEFAULT_SETTINGS.get("bundles", {}))

    if search_mode == "Single Search":
        col1, col2 = st.columns(2)

        with col1:
            keywords = st.text_input(
                "Job Keywords",
                value=ui_settings.get("default_keywords", "help desk it"),
                help="Job title or keywords to search for",
                key="new_run_keywords"
            )

        with col2:
            location = st.text_input(
                "Location",
                value=ui_settings.get("default_location", "Auburn NSW"),
                help="City, suburb, or region",
                key="new_run_location"
            )

        keywords_list = None  # Not using bundle mode
        bundle_ids = None

    else:  # Bundle Search
        # Bundle selection
        bundle_names = list(bundles.keys())

        if not bundle_names:
            st.warning("No bundles configured. Add bundles in Settings or use Single Search mode.")
            return

        # Create bundle table with checkboxes
        st.subheader("📦 Select Bundles")

        # Get last run times for each bundle
        bundle_last_runs = {}
        for bundle_name in bundle_names:
            # Clean bundle name for folder matching
            clean_name = re.sub(r'^\d+️⃣\s+', '', bundle_name)
            clean_name = re.sub(r'\s*\([^)]*\)\s*$', '', clean_name)
            clean_name = clean_name.strip()[:25].replace(' ', '_')
            clean_name = re.sub(r'[<>:"/\\|?*]', '', clean_name)

            # Find most recent folder with this bundle name
            latest_time = None
            if SCRAPED_DATA_DIR.exists():
                for folder in SCRAPED_DATA_DIR.iterdir():
                    if folder.is_dir() and folder.name.startswith(clean_name + '_'):
                        # Extract timestamp from folder name
                        timestamp_match = re.search(r'_(\d{8}_\d{6})$', folder.name)
                        if timestamp_match:
                            timestamp_str = timestamp_match.group(1)
                            try:
                                folder_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                                if latest_time is None or folder_time > latest_time:
                                    latest_time = folder_time
                            except ValueError:
                                pass

            bundle_last_runs[bundle_name] = latest_time

        # Display bundles in a table format
        selected_bundles = []
        for bundle_name in bundle_names:
            col1, col2, col3 = st.columns([0.5, 3, 1.5])

            with col1:
                checkbox_key = f"bundle_checkbox_{bundle_name.replace(' ', '_').replace('(', '').replace(')', '')}"
                is_selected = st.checkbox(
                    f"Select {bundle_name}",
                    key=checkbox_key,
                    label_visibility="hidden"
                )
                if is_selected:
                    selected_bundles.append(bundle_name)

            with col2:
                st.markdown(f"**{bundle_name}**")

            with col3:
                last_run = bundle_last_runs.get(bundle_name)
                if last_run:
                    st.caption(f"🕒 {last_run.strftime('%Y-%m-%d %H:%M')}")
                else:
                    st.caption("Never run")

        st.caption("Each phrase runs as a separate scrape; results are merged with early dedup.")

        # Show what keywords are in the selected bundles
        if selected_bundles:
            all_keywords = []
            for bundle_name in selected_bundles:
                all_keywords.extend(bundles.get(bundle_name, []))

            with st.expander(f"📋 Keywords in selected bundle(s) ({len(all_keywords)} total)", expanded=False):
                for bundle_name in selected_bundles:
                    bundle_keywords = bundles.get(bundle_name, [])
                    st.markdown(f"**{bundle_name}:** {', '.join(bundle_keywords)}")

        location = st.text_input(
            "Location",
            value=ui_settings.get("default_location", "Auburn NSW"),
            help="City, suburb, or region",
            key="new_run_location_bundle"
        )

        # Prepare bundle data for command
        keywords_list = []
        bundle_ids = []
        for bundle_name in selected_bundles:
            bundle_keywords = bundles.get(bundle_name, [])
            keywords_list.extend(bundle_keywords)
            bundle_ids.append(bundle_name)

        keywords = None  # Not using single keyword mode

    # ─────────────────────────────────────────────────────────────────────────
    # Scraping Options Section
    # ─────────────────────────────────────────────────────────────────────────
    with st.expander("⚙️ Scraping Options", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            pages = st.number_input(
                "Max Pages",
                min_value=1,
                max_value=20,
                value=scraper_settings.get("pages", 3),
                help="Maximum pages to scrape per site",
                key="new_run_pages"
            )

            source = st.selectbox(
                "Source",
                options=["all", "seek", "jora"],
                index=["all", "seek", "jora"].index(scraper_settings.get("source", "all")),
                help="Which job site(s) to scrape",
                key="new_run_source"
            )

        with col2:
            workers = st.number_input(
                "Workers",
                min_value=1,
                max_value=20,
                value=scraper_settings.get("workers", 10),
                help="Parallel browser workers (recommended: 10 for 6-core CPU)",
                key="new_run_workers"
            )

            delay = st.number_input(
                "Delay (seconds)",
                min_value=0.5,
                max_value=10.0,
                value=float(scraper_settings.get("delay", 1.5)),
                step=0.5,
                help="Delay between requests",
                key="new_run_delay"
            )

        with col3:
            max_details_setting = scraper_settings.get("max_details")
            fetch_all_by_default = max_details_setting is None or (
                isinstance(max_details_setting, int) and max_details_setting != 0
            )
            detail_choice_index = 0 if fetch_all_by_default else 1
            detail_choice_label = st.selectbox(
                "Max Details",
                options=DETAIL_FETCH_LABELS,
                index=detail_choice_index,
                help="Fetch detail pages for every job or skip them to speed up scraping.",
                key="new_run_max_details"
            )
            max_details = DETAIL_FETCH_VALUES[detail_choice_label]

            fuzzy = st.checkbox(
                "Fuzzy Search",
                value=scraper_settings.get("fuzzy", False),
                help="Expand search with related terms",
                key="new_run_fuzzy"
            )

        col1, col2 = st.columns(2)

        with col1:
            visible = st.checkbox(
                "Show Browser",
                value=scraper_settings.get("visible", False),
                help="Show browser window during scraping",
                key="new_run_visible"
            )

        with col2:
            sequential = st.checkbox(
                "Sequential Mode",
                value=scraper_settings.get("sequential", False),
                help="Fetch job details one at a time (slower but uses less resources)",
                key="new_run_sequential"
            )

    # ─────────────────────────────────────────────────────────────────────────
    # Submit Section (visually separated)
    # ─────────────────────────────────────────────────────────────────────────
    st.markdown("---")

    # Validation
    can_submit = True
    if search_mode == "Single Search":
        if not keywords or not keywords.strip():
            can_submit = False
    else:  # Bundle Search
        if not keywords_list:
            can_submit = False

    if not location or not location.strip():
        can_submit = False

    if st.button("🚀 Start Run", type="primary", use_container_width=True, disabled=not can_submit):
        # Build command
        cmd = [
            sys.executable,
            "-u",
            str(Path(__file__).parent.parent / "main.py"),
            "--location", location,
            "--pages", str(pages),
            "--source", source,
            "--workers", str(workers),
            "--delay", str(delay),
        ]

        # Add keywords based on search mode
        if search_mode == "Single Search":
            cmd.extend(["--keywords", keywords])
        else:
            # Bundle mode: use --keywords-list
            cmd.extend(["--keywords-list", json.dumps(keywords_list)])
            if bundle_ids:
                cmd.extend(["--bundle-ids", ",".join(bundle_ids)])

        if max_details and max_details > 0:
            cmd.extend(["--max-details", str(max_details)])

        if fuzzy and search_mode == "Single Search":
            cmd.append("--fuzzy")
        else:
            cmd.append("--no-fuzzy")

        if visible:
            cmd.append("--visible")

        if sequential:
            cmd.append("--sequential")

        # Create log file
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOGS_DIR / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        # Start process
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"

        with open(log_file, "w", encoding="utf-8") as f:
            process = subprocess.Popen(
                cmd,
                stdout=f,
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                cwd=str(Path(__file__).parent.parent)
            )

        st.session_state.run_process = process
        st.session_state.run_log_file = str(log_file)
        save_run_state(process.pid, str(log_file))
        st.rerun()