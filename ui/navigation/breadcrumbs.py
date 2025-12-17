# ui/navigation/breadcrumbs.py
"""Breadcrumb building for navigation hierarchy."""

from pathlib import Path
from typing import Dict, Any, List

from .actions import navigate_to
from ui.io_cache import _get_run_search_meta


def build_breadcrumbs(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return breadcrumb metadata for the current navigation state."""

    crumbs: List[Dict[str, Any]] = []
    page = state.get("page", "reports")

    if page == "overview":
        crumbs.append({"label": "Overview", "on_click": None, "active": True})

    elif page == "reports":
        crumbs.append({"label": "Reports", "on_click": lambda: navigate_to("reports"), "active": False})

        view_mode = state.get("view_mode", "overview")
        selected_run = state.get("selected_run")

        if view_mode == "compiled_overview":
            crumbs.append({"label": "Compiled Review", "on_click": None, "active": True})
        elif selected_run:
            run_path = Path(selected_run)
            keywords, location = _get_run_search_meta(run_path)
            run_label = f"{keywords} — {location}" if keywords and location else run_path.name
            if len(run_label) > 40:
                run_label = run_label[:40] + "…"

            crumbs.append(
                {
                    "label": run_label,
                    "on_click": lambda: navigate_to(
                        "reports",
                        selected_run=selected_run,
                        view_mode="overview",
                        viewing_job_id=None,
                        selected_filters={},
                        filter_mode="any",
                        search_text="",
                    ),
                    "active": False,
                }
            )

            if view_mode in {"explorer", "job_detail"}:
                crumbs.append(
                    {
                        "label": "Jobs",
                        "on_click": lambda: navigate_to(
                            "reports",
                            selected_run=selected_run,
                            view_mode="explorer",
                            viewing_job_id=None,
                            selected_filters={},
                            filter_mode="any",
                            search_text="",
                        ),
                        "active": view_mode == "job_detail",
                    }
                )

            if view_mode == "job_detail":
                crumbs.append({"label": "Job Detail", "on_click": None, "active": True})

    elif page == "jobs":
        crumbs.append({"label": "Jobs", "on_click": None, "active": True})

    elif page == "new_run":
        crumbs.append({"label": "New Run", "on_click": None, "active": True})

    elif page == "settings":
        crumbs.append({"label": "Settings", "on_click": None, "active": True})

    # Mark trailing crumb active if none set
    if crumbs and not any(c.get("active") for c in crumbs):
        crumbs[-1]["active"] = True

    for crumb in crumbs:
        if crumb.get("active"):
            crumb["on_click"] = None

    return crumbs
