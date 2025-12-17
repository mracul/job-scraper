# ui/navigation/breadcrumbs.py
"""
Breadcrumb building for navigation hierarchy.
Provides deterministic breadcrumb generation based on current navigation state.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from .actions import navigate_to


from ui.io_cache import _get_run_search_meta


def build_breadcrumbs(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build breadcrumb navigation based on current state."""
    crumbs: List[Dict[str, Any]] = []
    page = state.get("page", "reports")

    if page == "reports":
        crumbs.append({
            "label": "Reports",
            "on_click": lambda: navigate_to("reports"),
            "active": False
        })

        view_mode = state.get("view_mode", "overview")
        selected_run = state.get("selected_run")

        if view_mode == "compiled_overview":
            crumbs.append({
                "label": "Compiled Review",
                "on_click": None,
                "active": True
            })
        elif selected_run:
            run_path = Path(selected_run)
            keywords, location = _get_run_search_meta(run_path)
            run_label = f"{keywords} — {location}" if keywords and location else run_path.name
            if len(run_label) > 25:
                run_label = run_label[:25] + "…"

            crumbs.append({
                "label": run_label,
                "on_click": lambda: navigate_to(
                    "reports",
                    selected_run=selected_run,
                    view_mode="overview",
                    viewing_job_id=None,
                    selected_filters={},
                    filter_mode="any",
                    search_text=""
                ),
                "active": False
            })

            if view_mode == "explorer":
                crumbs.append({
                    "label": "Jobs",
                    "on_click": lambda: navigate_to(
                        "reports",
                        selected_run=selected_run,
                        view_mode="explorer",
                        viewing_job_id=None,
                        selected_filters={},
                        filter_mode="any",
                        search_text=""
                    ),
                    "active": False
                })
            elif view_mode == "job_detail":
                crumbs.append({
                    "label": "Jobs",
                    "on_click": lambda: navigate_to(
                        "reports",
                        selected_run=selected_run,
                        view_mode="explorer",
                        viewing_job_id=None,
                        selected_filters={},
                        filter_mode="any",
                        search_text=""
                    ),
                    "active": False
                })
                crumbs.append({
                    "label": "Detail",
                    "on_click": None,
                    "active": True
                })

    elif page == "jobs":
        # Jobs page breadcrumb logic would go here if needed
        crumbs.append({
            "label": "Jobs",
            "on_click": None,
            "active": True
        })

    elif page == "new_run":
        crumbs.append({
            "label": "New Run",
            "on_click": None,
            "active": True
        })

    elif page == "settings":
        crumbs.append({
            "label": "Settings",
            "on_click": None,
            "active": True
        })

    elif page == "overview":
        crumbs.append({
            "label": "Overview",
            "on_click": None,
            "active": True
        })

    # Mark the last crumb as active if not already marked
    if crumbs and not any(crumb.get("active", False) for crumb in crumbs):
        crumbs[-1]["active"] = True

    return crumbs