"""
Job Scraper - Streamlit UI
A web interface for running job scrapes and exploring results.
Phase 7.9: Thin Router + Full Navigation + Cleanup
"""

import streamlit as st
import json

# Import navigation system
from ui.navigation.state import defaults, normalize_state
from ui.navigation.url_sync import apply_state_from_url, sync_url_with_state

# Import router
from ui.router import dispatch

# Import sidebar
from ui.components.sidebar import render_sidebar


def init_session_state():
    """Initialize session state with navigation defaults."""
    # Set navigation defaults
    nav_defaults = defaults()
    for key, value in nav_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Initialize other app-specific state
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
    if "nav_seq" not in st.session_state:
        st.session_state.nav_seq = 0
    if "nav_origin" not in st.session_state:
        st.session_state.nav_origin = None
    if "overview_params" not in st.session_state:
        st.session_state.overview_params = None
    if "overview_cache_path" not in st.session_state:
        st.session_state.overview_cache_path = None
    if "overview_notice" not in st.session_state:
        st.session_state.overview_notice = None
    if "trigger_overview_generation" not in st.session_state:
        st.session_state.trigger_overview_generation = False
    if "trigger_overview_export" not in st.session_state:
        st.session_state.trigger_overview_export = False
    if "compiled_preexisting" not in st.session_state:
        st.session_state.compiled_preexisting = False


def inject_css():
    """Inject custom CSS for the application."""
    st.markdown("""
    <style>
    /* Custom styles for the job scraper app */
    .stButton button {
        border-radius: 6px;
    }
    .stTextInput input, .stNumberInput input, .stSelectbox select {
        border-radius: 4px;
    }
    </style>
    """, unsafe_allow_html=True)


def main():
    """Main entry point for the Streamlit app - thin router implementation."""
    st.set_page_config(
        page_title="Job Scraper",
        page_icon="🔍",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # One-time initialization
    init_session_state()
    inject_css()

    # Navigation sync: apply URL state early, before rendering sidebar
    params = st.query_params
    params_str = json.dumps(dict(params) if params else {}, sort_keys=True)

    if st.session_state.get("last_url_state") != params_str:
        state_changed = apply_state_from_url()
        st.session_state.last_url_state = params_str
        if state_changed:
            normalize_state()
            st.rerun()

    # Render global sidebar navigation
    render_sidebar()

    # Normalize state (optional but recommended)
    normalize_state()

    # Dispatch to the appropriate view
    dispatch()

    # Sync URL at end of run
    sync_url_with_state()


if __name__ == "__main__":
    main()
    SCRAPED_DATA_DIR,
    RUN_STATE_FILE,
    LOGS_DIR,
    OVERVIEW_DIR,
    OUTPUTS_DIR,
    CATEGORY_LABELS,
    DETAIL_FETCH_OPTIONS,
    DETAIL_FETCH_LABELS,
    DETAIL_FETCH_VALUES,
    FILTER_WIDGET_KEYS,
    AI_SUMMARY_MAX_OUTPUT_TOKENS,
    AI_SUMMARY_TOP_N_SINGLE,
    AI_SUMMARY_TOP_N_COMPILED,
    CUTOFF_PRESETS,
    CUTOFF_LABELS,
    CUTOFF_VALUES,
    HALFLIFE_PRESETS,
    HALFLIFE_LABELS,
    HALFLIFE_VALUES,
)


def _build_ai_summary_input(
    *,
    total_jobs: int,
    summary: dict,
    search_context: dict,
    scope_label: str,
    top_n_per_category: int = 25,
) -> dict:
    # Wrapper kept for backwards compatibility (tests import this symbol).
    return _ui_build_ai_summary_input(
        total_jobs=total_jobs,
        summary=summary,
        search_context=search_context,
        scope_label=scope_label,
        category_labels=CATEGORY_LABELS,
        top_n_per_category=top_n_per_category,
    )





# ============================================================================
# Settings Persistence
# ============================================================================


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
    create_time = None
    cmdline: list[str] | None = None
    try:
        import psutil

        proc = psutil.Process(pid)
        try:
            create_time = float(proc.create_time())
        except Exception:
            create_time = None
        try:
            cmdline = [str(x) for x in (proc.cmdline() or [])]
        except Exception:
            cmdline = None
    except Exception:
        create_time = None
        cmdline = None

    payload = {
        "pid": pid,
        "log_file": log_file,
        "started": datetime.now().isoformat(),
        "create_time": create_time,
        "cmd": cmdline,
    }
    with open(RUN_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f)


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
            # Protect against PID reuse by verifying create_time when available.
            try:
                proc = psutil.Process(int(pid))
                stored_ct = data.get("create_time")
                if stored_ct is not None:
                    try:
                        stored_ct_f = float(stored_ct)
                        live_ct_f = float(proc.create_time())
                        # create_time is in seconds since epoch; allow small clock/float tolerance.
                        if abs(live_ct_f - stored_ct_f) > 2.0:
                            return None
                    except Exception:
                        # If parsing fails, fall back to liveness only.
                        pass
            except Exception:
                # If we can't inspect the process, fall back to pid_exists.
                pass

            return data
    return None


def _find_latest_run_after(started_at: datetime | None) -> Path | None:
    """Find the newest report folder (assumes the latest is the one just completed)."""
    if not SCRAPED_DATA_DIR.exists():
        return None
    candidates: list[tuple[float, Path]] = []
    for folder in SCRAPED_DATA_DIR.iterdir():
        if not folder.is_dir():
            continue
        try:
            mtime = folder.stat().st_mtime
        except Exception:
            continue
        candidates.append((mtime, folder))

    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]


# ============================================================================
# Data Loading Utilities
# ============================================================================

@st.cache_data(ttl=30)
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
    if "nav_seq" not in st.session_state:
        st.session_state.nav_seq = 0
    if "nav_origin" not in st.session_state:
        # Used to control where "Back" returns (e.g. compiled overview).
        st.session_state.nav_origin = None
    if "overview_params" not in st.session_state:
        st.session_state.overview_params = None
    if "overview_cache_path" not in st.session_state:
        st.session_state.overview_cache_path = None
    if "overview_notice" not in st.session_state:
        st.session_state.overview_notice = None


def _get_query_params() -> dict:
    """Compatibility wrapper for query params across Streamlit versions."""
    try:
        return dict(st.query_params)
    except Exception:
        return st.experimental_get_query_params()


def _set_query_params(params: dict) -> None:
    """Compatibility wrapper for setting query params across Streamlit versions."""
    clean = {k: str(v) for k, v in params.items() if v is not None}

    try:
        st.query_params.clear()
        # Single batch update is more stable than key-by-key assignment in Streamlit 1.52.x
        st.query_params.update(clean)
    except Exception:
        st.experimental_set_query_params(**clean)


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


def _encode_state_for_url(state: dict, extra: dict | None = None) -> dict:
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

    # Extra params (e.g. nav marker)
    if extra:
        for k, v in extra.items():
            if v is None:
                continue
            params[k] = str(v)

    return params


def _apply_state_from_url() -> bool:
    """Apply navigation state from current URL query params (enables browser back/forward).
    
    Returns True if any session state was changed, False otherwise.
    """
    params = _get_query_params()
    state_changed = False

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

    if page and st.session_state.get("page") != page:
        st.session_state.page = page
        state_changed = True
    if view and st.session_state.get("view_mode") != view:
        st.session_state.view_mode = view
        state_changed = True
    if run is not None and st.session_state.get("selected_run") != run:
        st.session_state.selected_run = run
        state_changed = True

    if job is not None:
        try:
            job_id = int(job)
            if st.session_state.get("viewing_job_id") != job_id:
                st.session_state.viewing_job_id = job_id
                state_changed = True
        except Exception:
            if st.session_state.get("viewing_job_id") is not None:
                st.session_state.viewing_job_id = None
                state_changed = True
    elif st.session_state.get("viewing_job_id") is not None:
        st.session_state.viewing_job_id = None
        state_changed = True

    if match in {"any", "all"} and st.session_state.get("filter_mode") != match:
        st.session_state.filter_mode = match
        state_changed = True
    if q is not None and st.session_state.get("search_text") != q:
        st.session_state.search_text = q
        state_changed = True

    if filters_raw:
        try:
            parsed = json.loads(filters_raw)
            if isinstance(parsed, dict):
                new_filters = {k: list(v) for k, v in parsed.items() if isinstance(v, list)}
                if st.session_state.get("selected_filters") != new_filters:
                    st.session_state.selected_filters = new_filters
                    state_changed = True
        except Exception:
            pass

    if compiled_raw:
        try:
            parsed = json.loads(compiled_raw)
            if isinstance(parsed, list):
                new_compiled = [str(p) for p in parsed]
                if st.session_state.get("compiled_runs") != new_compiled:
                    st.session_state.compiled_runs = new_compiled
                    state_changed = True
        except Exception:
            pass
    elif st.session_state.get("compiled_runs"):
        st.session_state.compiled_runs = []
        state_changed = True

    return state_changed


def _sync_url_with_state(force: bool = False, extra_params: dict | None = None) -> None:
    """Push current state to URL. Use force=True to guarantee a history step."""
    desired = _encode_state_for_url(snapshot_state(), extra=extra_params)
    current = _get_query_params()

    # Normalize current params to str->str
    normalized: dict[str, str] = {}
    for k, v in current.items():
        if isinstance(v, list):
            normalized[k] = v[0] if v else ""
        else:
            normalized[k] = str(v)

    desired_norm = {k: str(v) for k, v in desired.items()}

    if force or normalized != desired_norm:
        _set_query_params(desired)


def _clear_report_filter_widgets() -> None:
    """Clear Streamlit widget keys used by the Job Explorer filters.

    This prevents stale widget state bleeding across run switches or view transitions.
    """
    for widget_key in FILTER_WIDGET_KEYS:
        st.session_state.pop(widget_key, None)
    # Separate widget key used for the explorer match-mode radio.
    st.session_state.pop("filter_mode_radio", None)


def _normalize_navigation_state() -> None:
    """Coerce session state into a consistent navigation state.

    Streamlit reruns + URL sync can leave stale combinations (e.g. job_detail with no
    job id). Normalizing prevents incorrect components rendering.
    """
    page = st.session_state.get("page") or "reports"
    st.session_state.page = page

    # Non-reports pages should never keep report/explorer sub-state.
    if page != "reports":
        st.session_state.selected_run = None
        st.session_state.view_mode = "overview"
        st.session_state.viewing_job_id = None
        st.session_state.selected_filters = {}
        st.session_state.filter_mode = "any"
        st.session_state.search_text = ""
        return

    # Reports page: validate view_mode.
    view_mode = st.session_state.get("view_mode") or "overview"
    allowed = {"overview", "explorer", "job_detail", "compiled_overview"}
    if view_mode not in allowed:
        view_mode = "overview"
    st.session_state.view_mode = view_mode

    selected_run = st.session_state.get("selected_run")

    # Views that require a run.
    if view_mode in {"overview", "explorer", "job_detail"} and not selected_run:
        st.session_state.view_mode = "overview"
        st.session_state.viewing_job_id = None
        st.session_state.selected_filters = {}
        st.session_state.filter_mode = "any"
        st.session_state.search_text = ""
        _clear_report_filter_widgets()
        return

    # Explorer: never keep a selected job.
    if st.session_state.view_mode == "explorer":
        st.session_state.viewing_job_id = None

    # Job detail requires a job id.
    if st.session_state.view_mode == "job_detail":
        job_id = st.session_state.get("viewing_job_id")
        if not isinstance(job_id, int) or job_id <= 0:
            st.session_state.view_mode = "overview"
            st.session_state.viewing_job_id = None

    # Non-job detail views should not keep a job id.
    if st.session_state.view_mode != "job_detail":
        st.session_state.viewing_job_id = None


def navigate_to(page: str, **kwargs):
    """Navigate to a page with optional state updates, syncing state to URL."""
    prev_selected_run = st.session_state.get("selected_run")

    st.session_state.page = page
    for key, value in kwargs.items():
        st.session_state[key] = value

    # If the run changes, clear filter state so widgets don't retain invalid selections across runs.
    if "selected_run" in kwargs and kwargs.get("selected_run") != prev_selected_run:
        if "selected_filters" not in kwargs:
            st.session_state.selected_filters = {}
        if "filter_mode" not in kwargs:
            st.session_state.filter_mode = "any"
        if "search_text" not in kwargs:
            st.session_state.search_text = ""
        _clear_report_filter_widgets()

    if "selected_filters" in kwargs:
        _clear_report_filter_widgets()

    _normalize_navigation_state()

    # Force a unique URL each explicit navigation (ensures browser history steps)
    st.session_state.nav_seq = st.session_state.get("nav_seq", 0) + 1
    _sync_url_with_state(force=True, extra_params={"nav": str(st.session_state.nav_seq)})

    st.rerun()


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
            st.markdown("---")
        else:
            # Quick stats
            runs = list_runs()
            st.caption(f"📊 {len(runs)} report(s) available")
            
            if runs:
                total_jobs = sum(r["job_count"] for r in runs)
                st.caption(f"📋 {total_jobs} total jobs scraped")
        
        # Navigation
        nav_options = {
            "overview": "📈 Overview",
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
        
        st.markdown("---")


def render_breadcrumb():
    """Render breadcrumb navigation using pills for consistent clickable trail."""
    crumbs: list[tuple[str, dict]] = []  # (label, nav_kwargs)

    if st.session_state.page == "reports":
        crumbs.append(("📂 Reports", {
            "selected_run": None,
            "view_mode": "overview",
            "viewing_job_id": None,
            "selected_filters": {},
            "filter_mode": "any",
            "search_text": "",
            "compiled_runs": [],
        }))

        if st.session_state.view_mode == "compiled_overview":
            crumbs.append(("Compiled Review", {"view_mode": "compiled_overview"}))
        elif st.session_state.selected_run:
            run_name = Path(st.session_state.selected_run).name
            run_label = run_name[:25] + "…" if len(run_name) > 25 else run_name
            crumbs.append((run_label, {
                "selected_run": st.session_state.selected_run,
                "view_mode": "overview",
                "viewing_job_id": None,
                "selected_filters": {},
                "filter_mode": "any",
                "search_text": "",
            }))

            if st.session_state.view_mode == "explorer":
                crumbs.append(("Jobs", {
                    "selected_run": st.session_state.selected_run,
                    "view_mode": "explorer",
                    "viewing_job_id": None,
                }))
            elif st.session_state.view_mode == "job_detail":
                crumbs.append(("Jobs", {
                    "selected_run": st.session_state.selected_run,
                    "view_mode": "explorer",
                    "viewing_job_id": None,
                }))
                crumbs.append(("Detail", {
                    "selected_run": st.session_state.selected_run,
                    "view_mode": "job_detail",
                    "viewing_job_id": st.session_state.viewing_job_id,
                }))
    elif st.session_state.page == "new_run":
        crumbs.append(("🚀 New Run", {}))
    elif st.session_state.page == "settings":
        crumbs.append(("⚙️ Settings", {}))
    elif st.session_state.page == "overview":
        crumbs.append(("📈 Overview", {}))

    if not crumbs:
        return

    labels = [c[0] for c in crumbs]
    current_idx = len(crumbs) - 1  # Last crumb is current location

    # `st.pills` is not available in all Streamlit versions.
    if hasattr(st, "pills"):
        selected = st.pills(
            "nav",
            labels,
            default=labels[current_idx],
            key="breadcrumb_pills",
            label_visibility="collapsed",
        )
    else:
        selected = st.selectbox(
            "nav",
            labels,
            index=current_idx,
            key="breadcrumb_select",
            label_visibility="collapsed",
        )

    # Navigate if user clicked a different crumb
    if selected and selected != labels[current_idx]:
        clicked_idx = labels.index(selected)
        nav_kwargs = crumbs[clicked_idx][1]
        navigate_to("reports", **nav_kwargs)


# ============================================================================
# Page: Reports
# ============================================================================

# render_reports_page() is now imported from ui.views.reports


# ============================================================================
# Page: Overview
# ============================================================================


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
        return

    selected_paths: list[str] = []

    for run in runs:
        col0, col1, col2, col3 = st.columns([0.6, 3, 1, 1])

        with col0:
            checked = st.checkbox(
                f"Select report: {run['name']}",
                value=(str(run["path"]) in st.session_state.selected_reports),
                key=f"sel_{run['name']}",
                label_visibility="hidden"
            )
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
                meta_parts.append(run["timestamp"].strftime("%m/%d %H:%M"))
            if run["has_analysis"]:
                meta_parts.append("✅")
            else:
                meta_parts.append("❌")
            
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

        st.divider()

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
            # Detect whether a matching compiled report already exists for this exact selection.
            # This avoids unnecessary compilation work and lets the compiled page show a clear notice.
            try:
                run_paths = [Path(p) for p in selected_paths]
                run_names = [p.name for p in run_paths]
                fingerprint = build_runs_fingerprint(run_paths)
                report_path = compiled_report_path(STATE_DIR, run_names=run_names)
                cached_report = load_compiled_report(report_path)
                st.session_state.compiled_preexisting = bool(
                    cached_report
                    and is_matching_compiled_report(cached_report, run_names=run_names, fingerprint=fingerprint)
                )
            except Exception:
                st.session_state.compiled_preexisting = False
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
        def _perform_delete() -> list[str]:
            deleted: list[str] = []
            for run_path in st.session_state.delete_candidates:
                path_obj = Path(run_path)
                try:
                    if path_obj.exists() and path_obj.is_dir():
                        shutil.rmtree(path_obj)
                        deleted.append(str(path_obj))
                except Exception:
                    pass

            # Clear cache so list updates immediately
            list_runs.clear()

            st.session_state.selected_reports = [p for p in st.session_state.selected_reports if p not in deleted]
            st.session_state.compiled_runs = [p for p in st.session_state.compiled_runs if p not in deleted]
            return deleted

        if hasattr(st, "dialog"):
            @st.dialog("Confirm deletion")
            def _delete_dialog():
                st.warning("⚠️ **Confirm Deletion**")
                st.write("This will permanently delete the selected report folders:")
                for run_path in st.session_state.delete_candidates:
                    st.write(f"• {Path(run_path).name}")

                col_confirm, col_cancel = st.columns(2)
                with col_confirm:
                    if st.button("✓ Confirm Delete", type="primary", use_container_width=True, key="dlg_confirm_delete"):
                        deleted = _perform_delete()
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
                    if st.button("✗ Cancel", use_container_width=True, key="dlg_cancel_delete"):
                        st.session_state.delete_modal_open = False
                        st.session_state.delete_candidates = []
                        st.rerun()

            _delete_dialog()
        else:
            st.markdown("---")
            st.warning("⚠️ **Confirm Deletion**")
            st.write("This will permanently delete the selected report folders:")
            for run_path in st.session_state.delete_candidates:
                st.write(f"• {Path(run_path).name}")
            col_confirm, col_cancel, _ = st.columns([1, 1, 2])
            with col_confirm:
                if st.button("✓ Confirm Delete", type="primary", use_container_width=True):
                    deleted = _perform_delete()
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
    # Wrapper kept for backwards compatibility (tests import this symbol).
    return _ui_merge_analyses(analyses, category_keys=CATEGORY_LABELS.keys())


def render_compiled_overview():
    """Render an aggregated overview across multiple selected runs."""
    st.header("🧩 Compiled Review")

    # One-time notice set by the Reports page Compile(x) button.
    if st.session_state.get("compiled_preexisting"):
        st.info("Matching saved compiled report found; opening cached results.")
        st.session_state.compiled_preexisting = False

    run_paths = list(dict.fromkeys(Path(p) for p in (st.session_state.compiled_runs or [])))
    if not run_paths:
        st.info("No reports selected for compilation.")
        return

    run_names = [p.name for p in run_paths]
    fingerprint = build_runs_fingerprint(run_paths)
    report_path = compiled_report_path(STATE_DIR, run_names=run_names)

    cached_report = load_compiled_report(report_path)
    merged = None
    used_saved_compiled = False
    if cached_report and is_matching_compiled_report(cached_report, run_names=run_names, fingerprint=fingerprint):
        maybe_merged = cached_report.get("merged_analysis")
        if isinstance(maybe_merged, dict):
            merged = maybe_merged
            used_saved_compiled = True

    analyses: list[tuple[Path, dict | None]] = [(p, load_analysis(p)) for p in run_paths]
    if merged is None:
        merged = _merge_analyses([a for _, a in analyses if a])
        try:
            # Persist merged result so repeated compiled views are fast.
            payload = build_compiled_report_payload(
                run_names=run_names,
                fingerprint=fingerprint,
                merged_analysis=merged,
                name=(cached_report or {}).get("name") if isinstance(cached_report, dict) else None,
                created_at=(cached_report or {}).get("created_at") if isinstance(cached_report, dict) else None,
            )
            save_compiled_report_atomic(report_path, payload)
        except Exception:
            # Non-critical; compiled view should still work.
            pass

    total_jobs = merged.get("total_jobs", 0)
    summary = merged.get("summary", {})
    job_details = merged.get("job_details", [])
    unique_companies = len(set((j.get("company") or "").strip() for j in job_details if j.get("company")))

    run_term_index: dict[str, dict[str, list[tuple[int, Path]]]] = defaultdict(lambda: defaultdict(list))
    for run_path, analysis in analyses:
        if not analysis:
            continue
        for cat_key, items in (analysis.get("summary", {}) or analysis.get("presence", {}) or {}).items():
            for term, count in (items or {}).items():
                try:
                    run_term_index[cat_key][term].append((int(count), run_path))
                except Exception:
                    pass

    st.caption(f"Includes {len(run_paths)} report(s)")
    if used_saved_compiled:
        st.caption("Using saved compiled report (no re-merge needed).")
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

    # AI summary (compiled)
    search_pairs = []
    for p in run_paths:
        kw, loc = _get_run_search_meta(p)
        if kw or loc:
            search_pairs.append({"keywords": kw, "location": loc, "run": p.name})

    # Prefer requirements_analysis.txt as the data source for the LLM.
    # For compiled summaries, concatenate per-run reports with lightweight headers.
    per_run_blocks: list[str] = []
    for run_path, analysis in analyses:
        txt = load_requirements_analysis_txt(run_path) or ""
        if not txt.strip():
            continue
        kw, loc = _get_run_search_meta(run_path)
        run_total = None
        try:
            run_total = int((analysis or {}).get("total_jobs", 0) or 0)
        except Exception:
            run_total = None
        header_lines = [
            f"RUN: {run_path.name}",
            f"KEYWORDS: {kw or ''}",
            f"LOCATION: {loc or ''}",
        ]
        if run_total is not None:
            header_lines.append(f"TOTAL_JOBS: {run_total}")
        header = "\n".join(header_lines).strip()
        per_run_blocks.append(f"{header}\n\n{txt.strip()}")

    combined_txt = "\n\n".join(per_run_blocks).strip()
    combined_txt = _truncate_text(
        combined_txt,
        max_chars=120_000,
        suffix="\n\n[TRUNCATED: combined requirements_analysis.txt exceeded limit]",
    )

    from ai.ai_payloads import build_ai_bundle
    bundle = build_ai_bundle(
        scope="compiled",
        analysis_text=combined_txt,
        meta={
            "scope": "compiled",
            "runs": [p.name for p in run_paths],
            "search_terms": search_pairs,
            "total_jobs": int(total_jobs or 0),
            "companies": int(unique_companies or 0),
            "compiled_reports": int(len(run_paths)),
        },
        limits={"top_n_per_category": 25},  # Default for compiled
        category_labels=CATEGORY_LABELS,
    )
    compiled_key = hashlib.sha256("|".join(sorted(p.name for p in run_paths)).encode("utf-8")).hexdigest()[:16]
    cache_path = STATE_DIR / f"compiled_ai_summary_{compiled_key}.json"
    render_ai_summary_block(cache_path=cache_path, ai_input=bundle)

    st.markdown("---")

    for category_key, category_label in CATEGORY_LABELS.items():
        data = summary.get(category_key, {}) or {}
        if not data:
            continue

        # Keep expander expanded if there's an active selection in this category
        has_selection = bool(st.session_state.get(f"compiled_selected_term_{category_key}"))
        
        with st.expander(f"{category_label} ({len(data)} items)", expanded=has_selection):
            sorted_items_full = sorted(data.items(), key=lambda x: x[1], reverse=True)
            sorted_items = sorted_items_full[:15]
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

            # Full list for expanded view
            df_full = pd.DataFrame(
                [
                    {
                        "term": term,
                        "count": count,
                        "percentage": (count / total_jobs * 100) if total_jobs > 0 else 0,
                    }
                    for term, count in sorted_items_full
                ]
            )

            if df.empty:
                st.info("No data")
                continue

            st.caption("Select a requirement row to view matching jobs:")

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
            selected_term_key = f"compiled_selected_term_{category_key}"
            if selected_rows:
                row_idx = selected_rows[0]
                if 0 <= row_idx < len(df):
                    st.session_state[selected_term_key] = str(df.iloc[row_idx]["term"])

            selected_term = st.session_state.get(selected_term_key)
            if selected_term and st.button(
                "View matching jobs",
                type="primary",
                use_container_width=True,
                key=f"compiled_view_jobs_{category_key}",
            ):
                target_candidates = run_term_index.get(category_key, {}).get(selected_term, [])
                if target_candidates:
                    target_run = sorted(
                        target_candidates,
                        key=lambda t: (t[0], t[1].stat().st_mtime if t[1].exists() else 0),
                        reverse=True,
                    )[0][1]
                else:
                    target_run = run_paths[0]
                st.session_state.nav_origin = "compiled"
                navigate_to(
                    "reports",
                    selected_run=str(target_run),
                    view_mode="explorer",
                    viewing_job_id=None,
                    selected_filters={category_key: [selected_term]},
                    filter_mode="any",
                    search_text="",
                    # Keep compiled_runs so Back can return to compiled overview.
                    compiled_runs=list(st.session_state.get("compiled_runs") or []),
                )
                st.rerun()

            if len(sorted_items_full) > 15 and st.button(
                "⤢ Expand list",
                use_container_width=True,
                key=f"compiled_expand_{category_key}",
            ):
                if hasattr(st, "dialog"):
                    @st.dialog(f"{category_label} — All Items")
                    def _show_compiled_full_table(cat_key: str, df_all: pd.DataFrame):
                        st.caption("Select a requirement row to view matching jobs:")
                        table_df_full = df_all[["term", "count", "percentage"]].rename(
                            columns={"term": "Requirement", "count": "Jobs", "percentage": "% of Total"}
                        )
                        table_state_full = st.dataframe(
                            table_df_full,
                            hide_index=True,
                            use_container_width=True,
                            height=520,
                            selection_mode="single-row",
                            on_select="rerun",
                            key=f"compiled_table_full_{cat_key}",
                        )

                        selected_rows_full = []
                        try:
                            selected_rows_full = (
                                (table_state_full.selection.rows or [])
                                if table_state_full and table_state_full.selection
                                else []
                            )
                        except Exception:
                            selected_rows_full = []
                        selected_term_key_full = f"compiled_selected_term_full_{cat_key}"
                        if selected_rows_full:
                            row_idx_full = selected_rows_full[0]
                            if 0 <= row_idx_full < len(df_all):
                                st.session_state[selected_term_key_full] = str(df_all.iloc[row_idx_full]["term"])

                        selected_term_full = st.session_state.get(selected_term_key_full)
                        if selected_term_full and st.button(
                            "View matching jobs",
                            type="primary",
                            use_container_width=True,
                            key=f"compiled_view_jobs_full_{cat_key}",
                        ):
                            target_candidates_full = run_term_index.get(cat_key, {}).get(selected_term_full, [])
                            if target_candidates_full:
                                target_run_full = sorted(
                                    target_candidates_full,
                                    key=lambda t: (t[0], t[1].stat().st_mtime if t[1].exists() else 0),
                                    reverse=True,
                                )[0][1]
                            else:
                                target_run_full = run_paths[0]
                            st.session_state.nav_origin = "compiled"
                            navigate_to(
                                "reports",
                                selected_run=str(target_run_full),
                                view_mode="explorer",
                                viewing_job_id=None,
                                selected_filters={cat_key: [selected_term_full]},
                                filter_mode="any",
                                search_text="",
                                compiled_runs=list(st.session_state.get("compiled_runs") or []),
                            )
                            st.rerun()

                    _show_compiled_full_table(category_key, df_full)
                else:
                    with st.expander("All items", expanded=True):
                        table_df_full = df_full[["term", "count", "percentage"]].rename(
                            columns={"term": "Requirement", "count": "Jobs", "percentage": "% of Total"}
                        )
                        table_state_full = st.dataframe(
                            table_df_full,
                            hide_index=True,
                            use_container_width=True,
                            height=520,
                            selection_mode="single-row",
                            on_select="rerun",
                            key=f"compiled_table_full_{category_key}",
                        )

                        selected_rows_full = []
                        try:
                            selected_rows_full = (
                                (table_state_full.selection.rows or [])
                                if table_state_full and table_state_full.selection
                                else []
                            )
                        except Exception:
                            selected_rows_full = []
                        selected_term_key_full = f"compiled_selected_term_full_{category_key}"
                        if selected_rows_full:
                            row_idx_full = selected_rows_full[0]
                            if 0 <= row_idx_full < len(df_full):
                                st.session_state[selected_term_key_full] = str(df_full.iloc[row_idx_full]["term"])

                        selected_term_full = st.session_state.get(selected_term_key_full)
                        if selected_term_full and st.button(
                            "View matching jobs",
                            type="primary",
                            use_container_width=True,
                            key=f"compiled_view_jobs_full_{category_key}",
                        ):
                            target_candidates_full = run_term_index.get(category_key, {}).get(selected_term_full, [])
                            if target_candidates_full:
                                target_run_full = sorted(
                                    target_candidates_full,
                                    key=lambda t: (t[0], t[1].stat().st_mtime if t[1].exists() else 0),
                                    reverse=True,
                                )[0][1]
                            else:
                                target_run_full = run_paths[0]
                            st.session_state.nav_origin = "compiled"
                            navigate_to(
                                "reports",
                                selected_run=str(target_run_full),
                                view_mode="explorer",
                                viewing_job_id=None,
                                selected_filters={category_key: [selected_term_full]},
                                filter_mode="any",
                                search_text="",
                                compiled_runs=list(st.session_state.get("compiled_runs") or []),
                            )
                            st.rerun()



# ============================================================================
# Page: Settings
# ============================================================================

def render_settings_page():
    
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
            str(Path(__file__).parent / "main.py"),
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
        
# ============================================================================
# Page: Settings
# ============================================================================

def render_settings_page():
    """Render the settings page."""
    # Canonical page layout: PageHeader, ActionBar (optional), content
    render_page_header(
        path=[{"label": "Settings", "active": True}],
        title="Settings",
        subtitle="Configure application preferences and defaults"
    )
    
    settings = load_settings()
    scraper_settings = settings.get("scraper", {})
    ui_settings = settings.get("ui", {})
    ai_settings = settings.get("ai", {})
    
    with st.form("settings_form"):
        st.subheader("AI Settings")
        
        ai_model_options = ["gpt-5-mini", "gpt-5.1", "gpt-5.2"]
        current_model = ai_settings.get("model", "gpt-5-mini")
        model_index = ai_model_options.index(current_model) if current_model in ai_model_options else 0
        
        ai_model = st.selectbox(
            "AI Model for Summaries",
            options=ai_model_options,
            index=model_index,
            help="Select the OpenAI model to use for generating report summaries"
        )
        
        st.markdown("---")
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
                    },
                    "ai": {
                        "model": ai_model
                    },
                    # Preserve any existing bundles (or defaults) even though this form doesn't edit them.
                    "bundles": settings.get("bundles") or DEFAULT_SETTINGS.get("bundles", {}),
                }
                save_settings(new_settings)
                st.success("Settings saved!")
                st.rerun()
        
        with col2:
            if st.form_submit_button("🔄 Reset to Defaults", use_container_width=True):
                save_settings(DEFAULT_SETTINGS)

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
    
    init_session_state()

    # URL-change detection (replaces popstate reload)
    params = _get_query_params()
    params_str = json.dumps(params, sort_keys=True)

    if st.session_state.get("last_url_state") != params_str:
        state_changed = _apply_state_from_url()
        st.session_state.last_url_state = params_str
        if state_changed:
            _normalize_navigation_state()
            st.rerun()

    render_sidebar()
    
    # Route to the appropriate page
    if st.session_state.page == "overview":
        render_overview_page()
    elif st.session_state.page == "reports":
        render_reports_page()
    elif st.session_state.page == "new_run":
        render_new_run_page()
    elif st.session_state.page == "settings":
        render_settings_page()
    else:
        render_reports_page()

    # Optional passive sync (only if you need it)
    # _sync_url_with_state(force=False)


if __name__ == "__main__":
    main()
