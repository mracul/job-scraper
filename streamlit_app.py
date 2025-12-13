"""
Job Scraper - Streamlit UI
A web interface for running job scrapes and exploring results.
"""

import streamlit as st
import streamlit.components.v1
import pandas as pd
import json
import os
import time
import subprocess
import sys
import shutil
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import plotly.express as px




# ============================================================================
# Configuration & Constants
# ============================================================================

SCRAPED_DATA_DIR = Path(__file__).parent / "scraped_data"
STATE_DIR = Path(__file__).parent / "state"
SETTINGS_FILE = STATE_DIR / "ui_settings.json"
RUN_STATE_FILE = STATE_DIR / "active_run.json"
LOGS_DIR = Path(__file__).parent / "logs"

DEFAULT_SETTINGS = {
    "scraper": {
        "pages": 3,
        "source": "all",
        "delay": 1.5,
        "workers": 10,
        "sequential": False,
        "visible": False,
        "max_details": None,
        "fuzzy": False
    },
    "ui": {
        "default_keywords": "help desk it",
        "default_location": "Auburn NSW"
    }
}

CATEGORY_LABELS = {
    "certifications": "🏆 Certifications",
    "education": "🎓 Education",
    "technical_skills": "💻 Technical Skills",
    "soft_skills": "🤝 Soft Skills",
    "experience": "📅 Experience",
    "support_levels": "🎯 Support Levels",
    "work_arrangements": "🏢 Work Arrangements",
    "benefits": "🎁 Benefits",
    "other_requirements": "📋 Other Requirements"
}
DETAIL_FETCH_OPTIONS = [
    ("Fetch all job details", None),
    ("Skip job details (only job cards)", 0),
]
DETAIL_FETCH_LABELS = [label for label, _ in DETAIL_FETCH_OPTIONS]
DETAIL_FETCH_VALUES = {label: value for label, value in DETAIL_FETCH_OPTIONS}
FILTER_WIDGET_KEYS = [f"filter_{cat_key}" for cat_key in CATEGORY_LABELS]

# ============================================================================
# Settings Persistence
# ============================================================================

def load_settings() -> dict:
    """Load settings from JSON file, with defaults fallback."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Merge with defaults to ensure all keys exist
            settings = DEFAULT_SETTINGS.copy()
            for section in ["scraper", "ui"]:
                if section in saved:
                    settings[section].update(saved[section])
            return settings
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict) -> None:
    """Save settings to JSON file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def _read_run_state_raw() -> dict | None:
    """Read persisted run state without validating PID liveness."""
    if not RUN_STATE_FILE.exists():
        return None
    try:
        with open(RUN_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_run_state(pid: int, log_file: str) -> None:
    """Persist running process info to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(RUN_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"pid": pid, "log_file": log_file, "started": datetime.now().isoformat()}, f)


def clear_run_state() -> None:
    """Remove persisted run state."""
    if RUN_STATE_FILE.exists():
        RUN_STATE_FILE.unlink(missing_ok=True)


def load_run_state() -> dict | None:
    """Load persisted run state and verify process is still running."""
    data = _read_run_state_raw()
    if not data:
        return None
    pid = data.get("pid")
    if pid:
        import psutil
        if psutil.pid_exists(pid):
            return data
    return None


def _find_latest_run_after(started_at: datetime | None) -> Path | None:
    """Best-effort: find newest report folder created after a given start time."""
    if not SCRAPED_DATA_DIR.exists():
        return None
    started_ts = started_at.timestamp() if started_at else None

    candidates: list[tuple[float, Path]] = []
    for folder in SCRAPED_DATA_DIR.iterdir():
        if not folder.is_dir():
            continue
        try:
            mtime = folder.stat().st_mtime
        except Exception:
            continue
        if started_ts is not None and mtime < (started_ts - 60):
            continue
        candidates.append((mtime, folder))

    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


# ============================================================================
# Data Loading Utilities
# ============================================================================

def list_runs() -> list[dict]:
    """List all scraping runs with metadata, newest first."""
    if not SCRAPED_DATA_DIR.exists():
        return []
    
    runs = []
    for folder in SCRAPED_DATA_DIR.iterdir():
        if not folder.is_dir():
            continue
        
        meta = {
            "path": folder,
            "name": folder.name,
            "keywords": None,
            "location": None,
            "job_count": 0,
            "timestamp": None,
            "has_analysis": False
        }
        
        # Parse timestamp from folder name
        parts = folder.name.rsplit("_", 2)
        if len(parts) >= 2:
            try:
                ts_str = f"{parts[-2]}_{parts[-1]}"
                meta["timestamp"] = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
            except ValueError:
                pass

        if meta["timestamp"] is None:
            meta["timestamp"] = datetime.fromtimestamp(folder.stat().st_mtime)
        
        # Read metadata from compiled_jobs.md header
        compiled_md = folder / "compiled_jobs.md"
        if compiled_md.exists():
            try:
                with open(compiled_md, "r", encoding="utf-8") as f:
                    for _ in range(10):
                        line = f.readline()
                        if not line:
                            break
                        if line.startswith("**Search Keywords:**"):
                            meta["keywords"] = line.replace("**Search Keywords:**", "").strip().rstrip("  ")
                        elif line.startswith("**Search Location:**"):
                            meta["location"] = line.replace("**Search Location:**", "").strip().rstrip("  ")
                        elif line.startswith("**Total Jobs:**"):
                            try:
                                meta["job_count"] = int(line.replace("**Total Jobs:**", "").strip())
                            except ValueError:
                                pass
            except Exception:
                pass
        
        # Check for analysis files
        meta["has_analysis"] = (folder / "requirements_analysis.json").exists()
        
        runs.append(meta)
    
    # Sort by timestamp descending
    runs.sort(key=lambda r: r["timestamp"] or datetime.min, reverse=True)
    return runs


def load_analysis(run_path: Path) -> dict | None:
    """Load requirements_analysis.json for a run."""
    analysis_file = run_path / "requirements_analysis.json"
    if not analysis_file.exists():
        return None
    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def load_jobs_csv(run_path: Path) -> pd.DataFrame | None:
    """Load all_jobs.csv as DataFrame."""
    csv_file = run_path / "all_jobs.csv"
    if not csv_file.exists():
        return None
    try:
        return pd.read_csv(csv_file)
    except Exception:
        return None


# ============================================================================
# Session State Helpers
# ============================================================================

def init_session_state():
    """Initialize session state variables."""
    if "page" not in st.session_state:
        st.session_state.page = "reports"
    if "selected_run" not in st.session_state:
        st.session_state.selected_run = None
    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "overview"  # overview, explorer, job_detail
    if "viewing_job_id" not in st.session_state:
        st.session_state.viewing_job_id = None
    if "selected_filters" not in st.session_state:
        st.session_state.selected_filters = {}  # {category: [terms]}
    if "filter_mode" not in st.session_state:
        st.session_state.filter_mode = "any"  # "any" or "all"
    if "search_text" not in st.session_state:
        st.session_state.search_text = ""
    if "selected_reports" not in st.session_state:
        st.session_state.selected_reports = []  # list[str] of run folder paths
    if "compiled_runs" not in st.session_state:
        st.session_state.compiled_runs = []  # list[str] of run folder paths
    if "run_process" not in st.session_state:
        st.session_state.run_process = None
    if "run_log_file" not in st.session_state:
        st.session_state.run_log_file = None
    if "delete_candidates" not in st.session_state:
        st.session_state.delete_candidates = []
    if "delete_modal_open" not in st.session_state:
        st.session_state.delete_modal_open = False
    if "last_url_state" not in st.session_state:
        st.session_state.last_url_state = None


def _get_query_params() -> dict:
    """Compatibility wrapper for query params across Streamlit versions."""
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()


def _set_query_params(params: dict) -> None:
    """Compatibility wrapper for setting query params across Streamlit versions."""
    try:
        st.query_params.clear()
        for k, v in params.items():
            if v is None:
                continue
            st.query_params[k] = str(v)
    except Exception:
        # experimental API expects lists
        st.experimental_set_query_params(**{k: str(v) for k, v in params.items() if v is not None})


def snapshot_state() -> dict:
    """Capture navigation state for URL + internal usage."""
    return {
        "page": st.session_state.page,
        "selected_run": st.session_state.selected_run,
        "view_mode": st.session_state.view_mode,
        "viewing_job_id": st.session_state.viewing_job_id,
        "selected_filters": {k: list(v) for k, v in st.session_state.selected_filters.items()},
        "filter_mode": st.session_state.filter_mode,
        "search_text": st.session_state.search_text,
        "compiled_runs": list(st.session_state.compiled_runs),
    }


def _encode_state_for_url(state: dict) -> dict:
    """Encode navigation state into a URL-safe query params dict."""
    params: dict[str, str] = {
        "page": state.get("page") or "reports",
        "view": state.get("view_mode") or "overview",
    }

    if state.get("selected_run"):
        params["run"] = state["selected_run"]
    if state.get("viewing_job_id"):
        params["job"] = str(state["viewing_job_id"])
    if state.get("filter_mode"):
        params["match"] = state["filter_mode"]
    if state.get("search_text"):
        params["q"] = state["search_text"]

    selected_filters = state.get("selected_filters") or {}
    if selected_filters:
        try:
            params["filters"] = json.dumps(selected_filters, separators=(",", ":"), ensure_ascii=False)
        except Exception:
            pass

    compiled_runs = state.get("compiled_runs") or []
    if compiled_runs:
        try:
            params["compiled"] = json.dumps(compiled_runs, separators=(",", ":"), ensure_ascii=False)
        except Exception:
            pass

    return params


def _apply_state_from_url() -> None:
    """Apply navigation state from current URL query params (enables browser back/forward)."""
    params = _get_query_params()

    def _param_value(key: str) -> str | None:
        value = params.get(key)
        if value is None:
            return None
        if isinstance(value, list):
            return value[0] if value else None
        # st.query_params can return a scalar or a list depending on version
        return str(value)

    page = _param_value("page")
    view = _param_value("view")
    run = _param_value("run")
    job = _param_value("job")
    match = _param_value("match")
    q = _param_value("q")
    filters_raw = _param_value("filters")
    compiled_raw = _param_value("compiled")

    if page:
        st.session_state.page = page
    if view:
        st.session_state.view_mode = view
    st.session_state.selected_run = run

    if job is not None:
        try:
            st.session_state.viewing_job_id = int(job)
        except Exception:
            st.session_state.viewing_job_id = None
    else:
        st.session_state.viewing_job_id = None

    if match in {"any", "all"}:
        st.session_state.filter_mode = match
    if q is not None:
        st.session_state.search_text = q

    if filters_raw:
        try:
            parsed = json.loads(filters_raw)
            if isinstance(parsed, dict):
                st.session_state.selected_filters = {k: list(v) for k, v in parsed.items() if isinstance(v, list)}
        except Exception:
            pass

    if compiled_raw:
        try:
            parsed = json.loads(compiled_raw)
            if isinstance(parsed, list):
                st.session_state.compiled_runs = [str(p) for p in parsed]
        except Exception:
            pass


def _sync_url_with_state() -> None:
    """Push current state to URL (creates browser history entries for back/forward)."""
    desired = _encode_state_for_url(snapshot_state())
    current = _get_query_params()

    # Normalize current params to str->str
    normalized: dict[str, str] = {}
    for k, v in current.items():
        if isinstance(v, list):
            normalized[k] = v[0] if v else ""
        else:
            normalized[k] = str(v)

    if normalized != {k: str(v) for k, v in desired.items()}:
        _set_query_params(desired)


def navigate_to(page: str, **kwargs):
    """Navigate to a page with optional state updates, syncing state to URL."""
    st.session_state.page = page
    for key, value in kwargs.items():
        st.session_state[key] = value

    if "selected_filters" in kwargs:
        for widget_key in FILTER_WIDGET_KEYS:
            st.session_state.pop(widget_key, None)

    _sync_url_with_state()


 


# ============================================================================
# UI Components
# ============================================================================

def render_sidebar():
    """Render the sidebar navigation."""
    with st.sidebar:
        st.title("🔍 Job Scraper")
        st.markdown("---")
        
        # Show running indicator if scrape is in progress
        active_run = load_run_state()
        if active_run or st.session_state.run_process is not None:
            st.warning("🔄 Scrape running...")
            if st.button("View Progress", use_container_width=True, type="primary"):
                navigate_to("new_run")
                st.rerun()
            st.markdown("---")
        
        # Navigation
        nav_options = {
            "reports": "📂 Reports",
            "new_run": "🚀 New Run",
            "settings": "⚙️ Settings"
        }
        
        for key, label in nav_options.items():
            if st.button(label, use_container_width=True, 
                        type="primary" if st.session_state.page == key else "secondary"):
                if key == "reports":
                    navigate_to(
                        "reports",
                        selected_run=None,
                        view_mode="overview",
                        viewing_job_id=None,
                        selected_filters={},
                        filter_mode="any",
                        search_text=""
                    )
                else:
                    navigate_to(key)
                st.rerun()
        
        st.markdown("---")
        
        # Quick stats
        runs = list_runs()
        st.caption(f"📊 {len(runs)} report(s) available")
        
        if runs:
            total_jobs = sum(r["job_count"] for r in runs)
            st.caption(f"📋 {total_jobs} total jobs scraped")


def render_breadcrumb():
    """Render breadcrumb navigation based on current state."""
    parts = []
    
    if st.session_state.page == "reports":
        parts.append("Reports")
        if st.session_state.view_mode == "compiled_overview":
            parts.append("Compiled Review")
        elif st.session_state.selected_run:
            run_name = Path(st.session_state.selected_run).name
            parts.append(run_name[:30] + "..." if len(run_name) > 30 else run_name)
            if st.session_state.view_mode == "explorer":
                parts.append("Job Explorer")
            elif st.session_state.view_mode == "job_detail":
                parts.append("Job Detail")
    elif st.session_state.page == "new_run":
        parts.append("New Run")
    elif st.session_state.page == "settings":
        parts.append("Settings")
    
    st.caption(" > ".join(parts))


def render_back_button():
    """Render a back button based on current navigation state."""
    if st.session_state.view_mode == "job_detail":
        if st.button("← Back to Job List", key="back_from_detail"):
            st.session_state.view_mode = "explorer"
            st.session_state.viewing_job_id = None
            _sync_url_with_state()
            st.rerun()
    elif st.session_state.view_mode == "explorer":
        if st.button("← Back to Overview", key="back_from_explorer"):
            st.session_state.view_mode = "overview"
            st.session_state.viewing_job_id = None
            _sync_url_with_state()
            st.rerun()
    elif st.session_state.view_mode == "compiled_overview":
        if st.button("← Back to Report List", key="back_from_compiled"):
            st.session_state.selected_run = None
            st.session_state.view_mode = "overview"
            st.session_state.viewing_job_id = None
            st.session_state.compiled_runs = []
            _sync_url_with_state()
            st.rerun()
    elif st.session_state.selected_run and st.session_state.view_mode == "overview":
        if st.button("← Back to Report List", key="back_from_overview"):
            st.session_state.selected_run = None
            st.session_state.view_mode = "overview"
            st.session_state.viewing_job_id = None
            _sync_url_with_state()
            st.rerun()


# ============================================================================
# Page: Reports
# ============================================================================

def render_reports_page():
    """Render the reports page."""
    render_breadcrumb()
    
    if st.session_state.view_mode == "compiled_overview":
        render_back_button()
        render_compiled_overview()
        return

    if st.session_state.selected_run:
        render_back_button()
        if st.session_state.view_mode == "job_detail":
            render_job_detail_view()
        elif st.session_state.view_mode == "explorer":
            render_job_explorer()
        else:
            render_report_overview()
    else:
        render_report_list()


def render_report_list():
    """Render the list of available reports."""
    runs = list_runs()
    
    # Header row with placeholders for compile/delete buttons (rendered after checkbox loop)
    header_col, compile_col, delete_col = st.columns([3, 1, 1])
    with header_col:
        st.header("📂 Reports")
    compile_placeholder = compile_col.empty()
    delete_placeholder = delete_col.empty()
    
    if not runs:
        st.info("No reports found. Start a new scraping run to generate reports.")
        if st.button("🚀 Start New Run"):
            navigate_to("new_run")
            st.rerun()
        return

    selected_paths: list[str] = []

    for run in runs:
        with st.container():
            col0, col1, col2, col3 = st.columns([0.6, 3, 1, 1])

            with col0:
                checked = st.checkbox("", value=(str(run["path"]) in st.session_state.selected_reports), key=f"sel_{run['name']}")
                if checked:
                    selected_paths.append(str(run["path"]))
            
            with col1:
                # Build display label
                if run["keywords"] and run["keywords"] != "Not specified":
                    label = f"**{run['keywords']}**"
                    if run["location"] and run["location"] != "Not specified":
                        label += f" — {run['location']}"
                else:
                    label = f"**{run['name']}**"
                
                st.markdown(label)
                
                # Metadata line
                meta_parts = []
                if run["job_count"]:
                    meta_parts.append(f"{run['job_count']} jobs")
                if run["timestamp"]:
                    meta_parts.append(run["timestamp"].strftime("%Y-%m-%d %H:%M"))
                if run["has_analysis"]:
                    meta_parts.append("✅ Analyzed")
                else:
                    meta_parts.append("⚠️ No analysis")
                
                st.caption(" • ".join(meta_parts))
            
            with col2:
                if st.button("View", key=f"view_{run['name']}", use_container_width=True):
                    navigate_to(
                        "reports",
                        selected_run=str(run["path"]),
                        view_mode="overview",
                        viewing_job_id=None,
                        selected_filters={},
                        filter_mode="any",
                        search_text=""
                    )
                    st.rerun()
            
            with col3:
                if st.button("Explore", key=f"explore_{run['name']}", use_container_width=True):
                    navigate_to(
                        "reports",
                        selected_run=str(run["path"]),
                        view_mode="explorer",
                        viewing_job_id=None,
                        selected_filters={},
                        filter_mode="any",
                        search_text=""
                    )
                    st.rerun()

            st.markdown("---")

    st.session_state.selected_reports = selected_paths

    # Render compile/delete buttons now that selection is determined
    compile_label = "🧩 Compile" if not selected_paths else f"🧩 Compile ({len(selected_paths)})"
    compile_disabled = len(selected_paths) == 0
    with compile_placeholder:
        if st.button(
            compile_label,
            key="compile_button",
            use_container_width=True,
            type="primary",
            disabled=compile_disabled,
        ):
            navigate_to(
                "reports",
                selected_run=None,
                view_mode="compiled_overview",
                viewing_job_id=None,
                compiled_runs=list(selected_paths),
            )
            st.rerun()
    delete_disabled = len(selected_paths) == 0
    with delete_placeholder:
        if st.button(
            "🗑️ Delete",
            key="multi_delete_button",
            use_container_width=True,
            disabled=delete_disabled,
        ):
            st.session_state.delete_candidates = list(selected_paths)
            st.session_state.delete_modal_open = True
            st.rerun()

    st.caption("Tip: Use browser back/forward to move between views.")

    # Confirmation dialog for deleting selected reports
    if st.session_state.delete_modal_open:
        st.markdown("---")
        st.warning("⚠️ **Confirm Deletion**")
        st.write("This will permanently delete the selected report folders:")
        for run_path in st.session_state.delete_candidates:
            st.write(f"• {Path(run_path).name}")
        col_confirm, col_cancel, _ = st.columns([1, 1, 2])
        with col_confirm:
            if st.button("✓ Confirm Delete", type="primary", use_container_width=True):
                deleted = []
                for run_path in st.session_state.delete_candidates:
                    path_obj = Path(run_path)
                    try:
                        if path_obj.exists() and path_obj.is_dir():
                            shutil.rmtree(path_obj)
                            deleted.append(str(path_obj))
                    except Exception:
                        pass
                st.session_state.selected_reports = [p for p in st.session_state.selected_reports if p not in deleted]
                st.session_state.compiled_runs = [p for p in st.session_state.compiled_runs if p not in deleted]
                if st.session_state.selected_run in deleted:
                    navigate_to(
                        "reports",
                        selected_run=None,
                        view_mode="overview",
                        viewing_job_id=None,
                        selected_filters={},
                        filter_mode="any",
                        search_text="",
                    )
                st.session_state.delete_candidates = []
                st.session_state.delete_modal_open = False
                st.rerun()
        with col_cancel:
            if st.button("✗ Cancel", use_container_width=True):
                st.session_state.delete_modal_open = False
                st.session_state.delete_candidates = []
                st.rerun()


def _merge_analyses(analyses: list[dict]) -> dict:
    """Merge multiple requirements_analysis.json payloads into a combined summary."""
    merged_summary: dict[str, dict[str, int]] = {k: {} for k in CATEGORY_LABELS.keys()}
    total_jobs = 0
    combined_job_details = []

    for analysis in analyses:
        if not analysis:
            continue
        total_jobs += int(analysis.get("total_jobs", 0) or 0)

        summary = analysis.get("summary", {}) or {}
        for cat in CATEGORY_LABELS.keys():
            items = summary.get(cat, {}) or {}
            bucket = merged_summary.setdefault(cat, {})
            for term, count in items.items():
                try:
                    bucket[term] = int(bucket.get(term, 0)) + int(count)
                except Exception:
                    pass

        # Keep job_details only for aggregate company stats (not used for job linking)
        combined_job_details.extend(analysis.get("job_details", []) or [])

    return {
        "summary": merged_summary,
        "total_jobs": total_jobs,
        "job_details": combined_job_details,
    }


def render_compiled_overview():
    """Render an aggregated overview across multiple selected runs."""
    st.header("🧩 Compiled Review")

    run_paths = list(dict.fromkeys(Path(p) for p in (st.session_state.compiled_runs or [])))
    if not run_paths:
        st.info("No reports selected for compilation.")
        return

    analyses: list[tuple[Path, dict | None]] = [(p, load_analysis(p)) for p in run_paths]
    merged = _merge_analyses([a for _, a in analyses if a])

    total_jobs = merged.get("total_jobs", 0)
    summary = merged.get("summary", {})
    job_details = merged.get("job_details", [])
    unique_companies = len(set((j.get("company") or "").strip() for j in job_details if j.get("company")))

    run_term_index: dict[str, dict[str, list[tuple[int, Path]]]] = defaultdict(lambda: defaultdict(list))
    for run_path, analysis in analyses:
        if not analysis:
            continue
        for cat_key, items in (analysis.get("summary", {}) or {}).items():
            for term, count in (items or {}).items():
                try:
                    run_term_index[cat_key][term].append((int(count), run_path))
                except Exception:
                    pass

    st.caption(f"Includes {len(run_paths)} report(s)")
    for p in run_paths:
        st.caption(f"- {p.name}")

    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Jobs", total_jobs)
    with col2:
        st.metric("Companies", unique_companies)
    with col3:
        st.metric("Reports", len(run_paths))

    st.markdown("---")

    for category_key, category_label in CATEGORY_LABELS.items():
        data = summary.get(category_key, {}) or {}
        if not data:
            continue

        with st.expander(f"{category_label} ({len(data)} items)", expanded=False):
            sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:15]
            df = pd.DataFrame(
                [
                    {
                        "term": term,
                        "count": count,
                        "percentage": (count / total_jobs * 100) if total_jobs > 0 else 0,
                    }
                    for term, count in sorted_items
                ]
            )

            if df.empty:
                st.info("No data")
                continue

            fig = px.bar(
                df,
                y="term",
                x="percentage",
                orientation="h",
                text=df.apply(lambda r: f"{r['count']} ({r['percentage']:.1f}%)", axis=1),
                labels={"term": "", "percentage": "% of Jobs"},
                height=max(300, len(df) * 25),
            )
            fig.update_layout(
                yaxis={"categoryorder": "total ascending"},
                showlegend=False,
                margin=dict(l=0, r=0, t=10, b=10),
                clickmode="event+select",
                dragmode="select",
            )
            fig.update_traces(textposition="outside")
            st.plotly_chart(fig, use_container_width=True)

            table_df = df[["term", "count", "percentage"]].rename(
                columns={"term": "Requirement", "count": "Jobs", "percentage": "% of Total"}
            )
            table_state = st.dataframe(
                table_df,
                hide_index=True,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun",
                key=f"compiled_table_{category_key}",
            )

            # Streamlit doesn't reliably support clicking Plotly axis labels in-app.
            # Instead, make the table rows clickable to navigate.
            selected_rows = []
            try:
                selected_rows = (table_state.selection.rows or []) if table_state and table_state.selection else []
            except Exception:
                selected_rows = []
            if selected_rows:
                row_idx = selected_rows[0]
                if 0 <= row_idx < len(df):
                    term_clicked = str(df.iloc[row_idx]["term"])
                    target_candidates = run_term_index.get(category_key, {}).get(term_clicked, [])
                    if target_candidates:
                        target_run = sorted(
                            target_candidates,
                            key=lambda t: (t[0], t[1].stat().st_mtime if t[1].exists() else 0),
                            reverse=True,
                        )[0][1]
                    else:
                        target_run = run_paths[0]
                    navigate_to(
                        "reports",
                        selected_run=str(target_run),
                        view_mode="explorer",
                        viewing_job_id=None,
                        selected_filters={category_key: [term_clicked]},
                        filter_mode="any",
                        search_text="",
                        compiled_runs=[],
                    )
                    st.rerun()

            st.caption("Click a requirement to view matching jobs:")
            cols = st.columns(min(4, len(sorted_items)))
            for idx, (term, count) in enumerate(sorted_items):
                col_idx = idx % len(cols)
                with cols[col_idx]:
                    if st.button(f"{term} ({count})", key=f"compiled_req_{category_key}_{term}", use_container_width=True):
                        target_candidates = run_term_index.get(category_key, {}).get(term, [])
                        target_run = None
                        if target_candidates:
                            target_run = sorted(
                                target_candidates,
                                key=lambda t: (t[0], t[1].stat().st_mtime if t[1].exists() else 0),
                                reverse=True,
                            )[0][1]
                        else:
                            target_run = run_paths[0]
                        navigate_to(
                            "reports",
                            selected_run=str(target_run),
                            view_mode="explorer",
                            viewing_job_id=None,
                            selected_filters={category_key: [term]},
                            filter_mode="any",
                            search_text="",
                            compiled_runs=[],
                        )
                        st.rerun()

            # (Plotly click-to-navigate removed; use table row selection above.)


def render_report_overview():
    """Render the overview of a selected report with charts."""
    run_path = Path(st.session_state.selected_run)
    analysis = load_analysis(run_path)
    
    st.header(f"📊 Report Overview")
    
    if not analysis:
        st.warning("No analysis data found for this report. Run analysis first.")
        return
    
    summary = analysis.get("summary", {})
    total_jobs = analysis.get("total_jobs", 0)
    
    # Summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Jobs", total_jobs)
    
    with col2:
        # Count unique companies from job_details
        job_details = analysis.get("job_details", [])
        unique_companies = len(set(j.get("company", "") for j in job_details))
        st.metric("Companies", unique_companies)
    
    with col3:
        # Top certification
        certs = summary.get("certifications", {})
        if certs:
            top_cert = max(certs, key=certs.get)
            st.metric("Top Cert", top_cert, f"{certs[top_cert]} jobs")
        else:
            st.metric("Top Cert", "N/A")
    
    with col4:
        # Top technical skill
        skills = summary.get("technical_skills", {})
        if skills:
            top_skill = max(skills, key=skills.get)
            st.metric("Top Skill", top_skill, f"{skills[top_skill]} jobs")
        else:
            st.metric("Top Skill", "N/A")
    
    st.markdown("---")
    
    # Button to go to Job Explorer
    if st.button("🔍 Open Job Explorer", type="primary"):
        navigate_to(
            "reports",
            selected_run=st.session_state.selected_run,
            view_mode="explorer",
            viewing_job_id=None,
            selected_filters={},
            filter_mode="any",
            search_text=""
        )
        st.rerun()
    
    st.markdown("---")
    
    # Category charts in expanders with clickable requirements
    for category_key, category_label in CATEGORY_LABELS.items():
        data = summary.get(category_key, {})
        if not data:
            continue
        
        with st.expander(f"{category_label} ({len(data)} items)", expanded=False):
            # Prepare data for chart
            sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)[:15]  # Top 15
            df = pd.DataFrame([
                {"term": term, "count": count, "percentage": (count / total_jobs * 100) if total_jobs > 0 else 0}
                for term, count in sorted_items
            ])
            
            if not df.empty:
                # Horizontal bar chart
                fig = px.bar(
                    df,
                    y="term",
                    x="percentage",
                    orientation="h",
                    text=df.apply(lambda r: f"{r['count']} ({r['percentage']:.1f}%)", axis=1),
                    labels={"term": "", "percentage": "% of Jobs"},
                    height=max(300, len(df) * 25)
                )
                fig.update_layout(
                    yaxis={"categoryorder": "total ascending"},
                    showlegend=False,
                    margin=dict(l=0, r=0, t=10, b=10),
                    clickmode="event+select",
                    dragmode="select",
                )
                fig.update_traces(textposition="outside")
                st.plotly_chart(fig, use_container_width=True)
                
                # Clickable requirement buttons (double-click effect via single click navigation)
                st.caption("Click a requirement to view matching jobs:")
                table_df = df[["term", "count", "percentage"]].rename(
                    columns={"term": "Requirement", "count": "Jobs", "percentage": "% of Total"}
                )
                table_state = st.dataframe(
                    table_df,
                    hide_index=True,
                    use_container_width=True,
                    selection_mode="single-row",
                    on_select="rerun",
                    key=f"report_table_{category_key}",
                )

                selected_rows = []
                try:
                    selected_rows = (table_state.selection.rows or []) if table_state and table_state.selection else []
                except Exception:
                    selected_rows = []
                if selected_rows:
                    row_idx = selected_rows[0]
                    if 0 <= row_idx < len(df):
                        term_clicked = str(df.iloc[row_idx]["term"])
                        navigate_to(
                            "reports",
                            selected_run=st.session_state.selected_run,
                            view_mode="explorer",
                            viewing_job_id=None,
                            selected_filters={category_key: [term_clicked]},
                            filter_mode="any",
                            search_text=""
                        )
                        st.rerun()

                cols = st.columns(min(4, len(sorted_items)))
                for idx, (term, count) in enumerate(sorted_items):
                    col_idx = idx % len(cols)
                    with cols[col_idx]:
                        if st.button(f"{term} ({count})", key=f"req_{category_key}_{term}", use_container_width=True):
                            navigate_to(
                                "reports",
                                selected_run=st.session_state.selected_run,
                                view_mode="explorer",
                                viewing_job_id=None,
                                selected_filters={category_key: [term]},
                                filter_mode="any",
                                search_text=""
                            )
                            st.rerun()
                # (Plotly click-to-navigate removed; use table row selection above.)


def render_job_explorer():
    """Render the job explorer with tag filtering."""
    run_path = Path(st.session_state.selected_run)
    analysis = load_analysis(run_path)
    jobs_df = load_jobs_csv(run_path)
    
    st.header("🔍 Job Explorer")
    
    if not analysis or jobs_df is None:
        st.warning("Missing data for job exploration.")
        return

    parsed_dates = (
        pd.to_datetime(jobs_df["date_posted"], errors="coerce")
        if "date_posted" in jobs_df.columns
        else pd.Series([pd.NaT] * len(jobs_df))
    )
    job_dates = {idx + 1: parsed_dates.iloc[idx] for idx in range(len(parsed_dates))}
    
    job_details = {j["id"]: j for j in analysis.get("job_details", [])}
    summary = analysis.get("summary", {})
    
    # Filters in sidebar (more room for results)
    with st.sidebar:
        with st.expander("Filters", expanded=True):
            filter_mode = st.radio(
                "Match mode",
                ["any", "all"],
                format_func=lambda x: "Match ANY tag" if x == "any" else "Match ALL tags",
                horizontal=False,
                key="filter_mode_radio",
            )
            st.session_state.filter_mode = filter_mode

            search_text = st.text_input("🔎 Search title/company", key="search_text")

            sort_options = ["Newest first", "Oldest first"]
            default_sort_label = "Newest first" if st.session_state.get("job_sort_order", "newest") == "newest" else "Oldest first"
            sort_label = st.selectbox(
                "Sort jobs by date",
                sort_options,
                index=sort_options.index(default_sort_label),
            )
            st.session_state.job_sort_order = "newest" if sort_label == "Newest first" else "oldest"

            st.markdown("**Select tags:**")
            categories = list(CATEGORY_LABELS.items())
            for cat_key, cat_label in categories:
                terms = list(summary.get(cat_key, {}).keys())
                if not terms:
                    continue
                selected = st.multiselect(
                    cat_label,
                    options=terms,
                    default=st.session_state.selected_filters.get(cat_key, []),
                    key=f"filter_{cat_key}",
                )
                st.session_state.selected_filters[cat_key] = selected

            if st.button("Clear Filters", use_container_width=True):
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

    # Keep URL synced with current filter state
    _sync_url_with_state()

    sort_order = st.session_state.get("job_sort_order", "newest")

    def _job_sort_key(job_id: int):
        dt = job_dates.get(job_id)
        if pd.isna(dt):
            return datetime.min
        return dt.to_pydatetime() if hasattr(dt, "to_pydatetime") else dt

    reverse_sort = sort_order == "newest"
    
    # Apply filters to get matching jobs
    all_selected_terms = []
    for cat, terms in st.session_state.selected_filters.items():
        for term in terms:
            all_selected_terms.append((cat, term))
    
    # Build job matching results
    job_matches = {}  # job_id -> set of matched (cat, term) tuples
    
    for job_id, job_data in job_details.items():
        reqs = job_data.get("requirements", {})
        matched = set()
        
        for cat, term in all_selected_terms:
            if term in reqs.get(cat, []):
                matched.add((cat, term))
        
        if matched or not all_selected_terms:
            job_matches[job_id] = matched
    
    # Filter by search text
    if search_text:
        search_lower = search_text.lower()
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
                if job_row is not None:
                    date_value = job_row.get("date_posted")
                    if pd.notna(date_value) and date_value:
                        date_text = str(date_value)
                
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    if st.button(f"{title} — {company}", key=f"job_title_{job_id}"):
                        navigate_to(
                            "reports",
                            selected_run=st.session_state.selected_run,
                            view_mode="job_detail",
                            viewing_job_id=job_id,
                        )
                        st.rerun()
                    if date_text:
                        st.caption(f"📅 {date_text}")
                
                with col2:
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


# ============================================================================
# Page: New Run
# ============================================================================

def render_new_run_page():
    """Render the new run configuration page."""
    render_breadcrumb()
    
    st.header("🚀 Start New Scraping Run")
    
    settings = load_settings()
    scraper_settings = settings.get("scraper", {})
    ui_settings = settings.get("ui", {})
    
    # Check if a run is in progress (either in session or persisted)
    if st.session_state.run_process is not None or load_run_state() is not None:
        render_run_progress()
        return
    
    with st.form("new_run_form"):
        st.subheader("Search Parameters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            keywords = st.text_input(
                "Job Keywords",
                value=ui_settings.get("default_keywords", "help desk it"),
                help="Job title or keywords to search for"
            )
        
        with col2:
            location = st.text_input(
                "Location",
                value=ui_settings.get("default_location", "Auburn NSW"),
                help="City, suburb, or region"
            )
        
        # Advanced settings in expander
        with st.expander("⚙️ Advanced Settings", expanded=False):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                pages = st.number_input(
                    "Max Pages",
                    min_value=1,
                    max_value=20,
                    value=scraper_settings.get("pages", 3),
                    help="Maximum pages to scrape per site"
                )
                
                source = st.selectbox(
                    "Source",
                    options=["all", "seek", "jora"],
                    index=["all", "seek", "jora"].index(scraper_settings.get("source", "all")),
                    help="Which job site(s) to scrape"
                )
            
            with col2:
                workers = st.number_input(
                    "Workers",
                    min_value=1,
                    max_value=20,
                    value=scraper_settings.get("workers", 10),
                    help="Parallel browser workers (recommended: 10 for 6-core CPU)"
                )
                
                delay = st.number_input(
                    "Delay (seconds)",
                    min_value=0.5,
                    max_value=10.0,
                    value=float(scraper_settings.get("delay", 1.5)),
                    step=0.5,
                    help="Delay between requests"
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
                    help="Fetch detail pages for every job or skip them to speed up scraping."
                )
                max_details = DETAIL_FETCH_VALUES[detail_choice_label]
                
                fuzzy = st.checkbox(
                    "Fuzzy Search",
                    value=scraper_settings.get("fuzzy", False),
                    help="Expand search with related terms"
                )
            
            col1, col2 = st.columns(2)
            
            with col1:
                visible = st.checkbox(
                    "Show Browser",
                    value=scraper_settings.get("visible", False),
                    help="Show browser window during scraping"
                )
            
            with col2:
                sequential = st.checkbox(
                    "Sequential Mode",
                    value=scraper_settings.get("sequential", False),
                    help="Fetch job details one at a time (slower but uses less resources)"
                )
        
        submitted = st.form_submit_button("🚀 Start Run", type="primary", use_container_width=True)
        
        if submitted:
            # Build command
            cmd = [
                sys.executable,
                "-u",
                str(Path(__file__).parent / "main.py"),
                "--keywords", keywords,
                "--location", location,
                "--pages", str(pages),
                "--source", source,
                "--workers", str(workers),
                "--delay", str(delay),
            ]
            
            if max_details and max_details > 0:
                cmd.extend(["--max-details", str(max_details)])
            
            if fuzzy:
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
                    cwd=str(Path(__file__).parent)
                )
            
            st.session_state.run_process = process
            st.session_state.run_log_file = str(log_file)
            save_run_state(process.pid, str(log_file))
            st.rerun()


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

    def _read_log_tail(path: Path, max_lines: int = 400) -> str:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
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
        
        # Show spinner
        with st.spinner("Running scraper... This may take a few minutes."):
            # Display log tail
            if log_file and Path(log_file).exists():
                log_content = _read_log_tail(Path(log_file), max_lines=400)
                if log_content.strip():
                    st.code(log_content, language="text")
                else:
                    st.caption("Waiting for output...")
            else:
                st.caption("Waiting for log file...")
        
        # Refresh button
        if st.button("🔄 Refresh"):
            st.rerun()
        
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
        
        # Auto-refresh
        st.markdown("*Page auto-refreshes every 1 second...*")
        import time
        time.sleep(1)
        st.rerun()
    
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
            if latest_report and st.button("📊 Review Report", type="primary", use_container_width=True):
                navigate_to(
                    "reports",
                    selected_run=str(latest_report),
                    view_mode="overview",
                    viewing_job_id=None,
                    selected_filters={},
                    filter_mode="any",
                    search_text="",
                )
                st.rerun()
        with col2:
            if st.button("📂 View Reports", use_container_width=True):
                navigate_to("reports")
                st.rerun()
        with col3:
            if st.button("🚀 Start Another Run", use_container_width=True):
                st.rerun()
        
        # Show final log
        if log_file and Path(log_file).exists():
            with open(log_file, "r", encoding="utf-8") as f:
                log_content = f.read()
            
            with st.expander("View Full Log", expanded=False):
                st.text_area("Log Output", log_content, height=400)
        
# ============================================================================
# Page: Settings
# ============================================================================

def render_settings_page():
    """Render the settings page."""
    render_breadcrumb()
    
    st.header("⚙️ Settings")
    
    settings = load_settings()
    scraper_settings = settings.get("scraper", {})
    ui_settings = settings.get("ui", {})
    
    with st.form("settings_form"):
        st.subheader("Default Search Parameters")
        
        col1, col2 = st.columns(2)
        
        with col1:
            default_keywords = st.text_input(
                "Default Keywords",
                value=ui_settings.get("default_keywords", "help desk it")
            )
        
        with col2:
            default_location = st.text_input(
                "Default Location",
                value=ui_settings.get("default_location", "Auburn NSW")
            )
        
        st.markdown("---")
        st.subheader("Scraper Defaults")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            pages = st.number_input(
                "Default Max Pages",
                min_value=1,
                max_value=20,
                value=scraper_settings.get("pages", 3)
            )
            
            source = st.selectbox(
                "Default Source",
                options=["all", "seek", "jora"],
                index=["all", "seek", "jora"].index(scraper_settings.get("source", "all"))
            )
        
        with col2:
            workers = st.number_input(
                "Default Workers",
                min_value=1,
                max_value=20,
                value=scraper_settings.get("workers", 10),
                help="Recommended: 8-12 for 6-core/12-thread CPU, 4-6 for 4-core CPU"
            )
            
            delay = st.number_input(
                "Default Delay (seconds)",
                min_value=0.5,
                max_value=10.0,
                value=float(scraper_settings.get("delay", 1.5)),
                step=0.5
            )
        
        with col3:
            max_details = st.number_input(
                "Default Max Details",
                min_value=0,
                value=scraper_settings.get("max_details") or 0,
                help="0 = fetch all job details"
            )
            
            fuzzy = st.checkbox(
                "Enable Fuzzy Search by Default",
                value=scraper_settings.get("fuzzy", False)
            )
        
        col1, col2 = st.columns(2)
        
        with col1:
            visible = st.checkbox(
                "Show Browser by Default",
                value=scraper_settings.get("visible", False)
            )
        
        with col2:
            sequential = st.checkbox(
                "Sequential Mode by Default",
                value=scraper_settings.get("sequential", False)
            )
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.form_submit_button("💾 Save Settings", type="primary", use_container_width=True):
                new_settings = {
                    "scraper": {
                        "pages": pages,
                        "source": source,
                        "delay": delay,
                        "workers": workers,
                        "sequential": sequential,
                        "visible": visible,
                        "max_details": max_details if max_details > 0 else None,
                        "fuzzy": fuzzy
                    },
                    "ui": {
                        "default_keywords": default_keywords,
                        "default_location": default_location
                    }
                }
                save_settings(new_settings)
                st.success("Settings saved!")
                st.rerun()
        
        with col2:
            if st.form_submit_button("🔄 Reset to Defaults", use_container_width=True):
                save_settings(DEFAULT_SETTINGS)
                st.success("Settings reset to defaults!")
                st.rerun()


# ============================================================================
# Main Application
# ============================================================================

def main():
    """Main entry point for the Streamlit app."""
    st.set_page_config(
        page_title="Job Scraper",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Inject JS to detect browser back/forward and reload page
    st.components.v1.html(
        """
        <script>
        window.addEventListener('popstate', function(event) {
            // Browser back/forward detected - reload to apply new URL state
            window.location.reload();
        });
        </script>
        """,
        height=0,
    )
    
    init_session_state()

    # Apply URL navigation state first so browser/mouse back-forward works.
    # We compare current URL params with last known state to detect external changes.
    current_url_state = str(_get_query_params())
    if st.session_state.last_url_state is None or st.session_state.last_url_state != current_url_state:
        _apply_state_from_url()
        st.session_state.last_url_state = current_url_state

    render_sidebar()
    
    # Route to the appropriate page
    if st.session_state.page == "reports":
        render_reports_page()
    elif st.session_state.page == "new_run":
        render_new_run_page()
    elif st.session_state.page == "settings":
        render_settings_page()
    else:
        render_reports_page()

    # Keep URL in sync with final state.
    _sync_url_with_state()
    st.session_state.last_url_state = str(_get_query_params())


if __name__ == "__main__":
    main()
