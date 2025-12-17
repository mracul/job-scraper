"""
Overview page view.
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

from ui.components.page_header import render_page_header
from ui.components.kpi_grid import render_kpi_grid
from ui.components.trend_section import render_trend_section
from ui.components.market_composition import render_market_composition
from ui.components.ai_market_brief import render_ai_market_brief
from ui.components.category_drilldown import render_category_drilldown
from ui.components.action_bar import render_action_bar
from pipeline.overview_builder import OverviewBuilder
from ui.io_cache import load_analysis
from ui.constants import CATEGORY_LABELS, CUTOFF_LABELS, HALFLIFE_LABELS, CUTOFF_VALUES, HALFLIFE_VALUES, OVERVIEW_DIR, OUTPUTS_DIR, SCRAPED_DATA_DIR
from ui.utils import _hash_payload
from ui.io_cache import _load_cached_ai_summary, load_analysis
from ai_summary_ui import render_ai_summary_block
from ai.ai_payloads import build_ai_bundle

from ui_core import list_runs

from ui.navigation.breadcrumbs import build_breadcrumbs
from ui.navigation.state import snapshot_state



def render_overview_page():
    """Render weighted statistical overview across runs."""
    # Canonical page layout: PageHeader, ActionBar (optional), content
    breadcrumbs = build_breadcrumbs(snapshot_state())
    render_page_header(
        path=breadcrumbs,
        title="Overview",
        subtitle="Statistical analysis across all job reports"
    )

    # ActionBar
    render_action_bar([
        {"label": "Generate", "on_click": lambda: st.session_state.update({"trigger_overview_generation": True}), "kind": "primary"},
        {"label": "Export", "on_click": lambda: st.session_state.update({"trigger_overview_export": True}), "kind": "secondary"}
    ])

    runs = list_runs()
    if not runs:
        st.info("No reports found yet. Start a new run to generate data.")
        return

    # ─────────────────────────────────────────────────────────────────────────
    # Parameters
    # ─────────────────────────────────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("### Parameters")
        col1, col2, col3 = st.columns([1.2, 1.2, 0.8])
        with col1:
            cutoff_choice = st.selectbox(
                "Cutoff",
                options=CUTOFF_LABELS,
                index=3,  # Default: 180d
                help="Include runs from the last N days (relative to most recent run).",
            )
        with col2:
            halflife_choice = st.selectbox(
                "Half-life",
                options=HALFLIFE_LABELS,
                index=2,  # Default: 30d
                help="Weight decay half-life. Older runs contribute less; halved every H days.",
            )
        with col3:
            top_n = st.number_input(
                "Top N",
                min_value=3,
                max_value=50,
                value=10,
                step=1,
                help="Show top N terms per category by weighted count.",
            )

    cutoff_days = CUTOFF_VALUES[cutoff_choice]
    half_life_days = HALFLIFE_VALUES[halflife_choice]

    # One-shot notices
    notice = st.session_state.get("overview_notice")
    if isinstance(notice, str) and notice:
        st.success(notice)
        st.session_state.overview_notice = None

    if generate:
        selected_runs = _runs_within_cutoff(runs, cutoff_days)
        builder = OverviewBuilder()
        payload = builder.build_overview_from_runs(
            runs=selected_runs,
            cutoff_days=cutoff_days,
            half_life_days=half_life_days,
            top_n=int(top_n),
        )
        payload["params"] = params
        _save_overview_cache(cache_file, payload)
        exported = _export_overview_files(payload=payload, params=params)
        st.session_state.overview_notice = (
            f"Exported: {Path(exported['md']).name}, {Path(exported['csv']).name}, {Path(exported['json']).name}"
        )
        st.session_state.overview_params = params
        st.session_state.overview_cache_path = str(cache_file)
        st.rerun()
        return

    if export_now and cached and cached.get("params") == params:
        exported = _export_overview_files(payload=cached, params=params)
        st.session_state.overview_notice = (
            f"Exported: {Path(exported['md']).name}, {Path(exported['csv']).name}, {Path(exported['json']).name}"
        )
        st.rerun()
        return

    # Validate cache
    if not cached or cached.get("params") != params:
        st.caption("Overview not generated for these settings yet. Click **Generate / Update**.")
        st.stop()

    meta = cached.get("meta") or {}
    runs_used = cached.get("runs") or []
    weighted_summary = cached.get("weighted_summary") or {}
    top_terms = cached.get("top_terms") or {}
    series = cached.get("series") or []

    # ─────────────────────────────────────────────────────────────────────────
    # Model explanation (UX copy)
    # ─────────────────────────────────────────────────────────────────────────
    max_ts = meta.get("max_ts", "")
    cutoff_date_str = ""
    if max_ts:
        try:
            max_dt = datetime.fromisoformat(max_ts)
            cutoff_dt = max_dt - pd.Timedelta(days=cutoff_days)
            cutoff_date_str = cutoff_dt.strftime("%Y-%m-%d")
        except Exception:
            cutoff_date_str = f"{cutoff_days}d ago"
    st.caption(f"Using runs since **{cutoff_date_str}**, weighted by recency (half-life: **{half_life_days}d**).")

    # ─────────────────────────────────────────────────────────────────────────
    # Window Summary
    # ─────────────────────────────────────────────────────────────────────────
    runs_count = len(runs_used)
    raw_jobs = int(meta.get("raw_jobs", 0) or 0)
    effective_jobs = float(meta.get("effective_jobs", 0) or 0)
    min_ts = meta.get("min_ts", "")
    max_ts_display = meta.get("max_ts", "")

    if min_ts and max_ts_display:
        time_span_label = f"{min_ts[:10]} → {max_ts_display[:10]}"
    else:
        time_span_label = "—"

    render_kpi_grid(
        effective_jobs=effective_jobs,
        runs_used=runs_count,
        time_span_label=time_span_label,
        median_post_age_days=None,  # Not available yet
        pct_new_jobs_30d=None  # Not available yet
    )

    st.caption(f"Cutoff: {cutoff_days}d | Half-life: {half_life_days}d | Top N: {top_n}")
    gen_at = cached.get("generated_at")
    if gen_at:
        st.caption(f"Generated: {gen_at}")

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────────
    # Market Trends (placeholder)
    # ─────────────────────────────────────────────────────────────────────────
    render_trend_section()

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────────
    # Market Context (support levels + work arrangements)
    # ─────────────────────────────────────────────────────────────────────────
    # Prepare data for market composition component
    support_levels = []
    work_arrangements = []

    support_data = weighted_summary.get("support_levels", {})
    for term, data in support_data.items():
        count = data.get("weighted_count", 0)
        if count > 0:
            pct = (count / effective_jobs) * 100 if effective_jobs > 0 else 0
            support_levels.append({"label": term, "pct": pct})

    work_data = weighted_summary.get("work_arrangements", {})
    for term, data in work_data.items():
        count = data.get("weighted_count", 0)
        if count > 0:
            pct = (count / effective_jobs) * 100 if effective_jobs > 0 else 0
            work_arrangements.append({"label": term, "pct": pct})

    render_market_composition(support_levels, work_arrangements)

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────────
    # Category Snapshots
    # ─────────────────────────────────────────────────────────────────────────
    # Prepare data for category drilldown component
    categories = []
    skip_cats = {"support_levels", "work_arrangements"}

    for cat_key, cat_label in CATEGORY_LABELS.items():
        if cat_key in skip_cats:
            continue
        cat_terms = top_terms.get(cat_key) or []
        if not cat_terms:
            continue

        # Convert top_terms format to expected format
        top_terms_formatted = []
        for term_data in cat_terms:
            term = term_data.get("term", "")
            weighted_count = term_data.get("weighted_count", 0)
            pct = (weighted_count / effective_jobs) * 100 if effective_jobs > 0 else 0
            top_terms_formatted.append({"term": term, "pct": pct})

        categories.append({
            "category": cat_key,
            "category_label": cat_label,
            "top_terms": top_terms_formatted,
            "on_view_breakdown": None  # Could add navigation later
        })

    render_category_drilldown(categories)

    st.markdown("---")

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────────
    # AI Market Brief
    # ─────────────────────────────────────────────────────────────────────────
    # TODO: Update AI generation to produce structured output (tldr, observations, risks, actions)
    # For now, using placeholder - will need to modify ai_summary_core.py to generate structured JSON
    render_ai_market_brief(
        tldr=["Market analysis shows strong demand for entry-level IT support roles",
              "Remote work arrangements dominate the market",
              "Certifications remain key differentiators"],
        observations=["Entry-level positions represent 45% of total opportunities",
                      "Help desk and service desk roles show consistent growth",
                      "Technical certifications (CompTIA, Microsoft) frequently mentioned"],
        risks=["High competition in entry-level segments",
               "Rapidly evolving technical requirements",
               "Location-based salary variations"],
        actions=["Focus on CompTIA A+ and Network+ certifications",
                 "Build experience with help desk ticketing systems",
                 "Develop strong communication and customer service skills"]
    )


def _overview_params(cutoff_days: int, half_life_days: int, top_n: int) -> dict:
    return {
        "cutoff_days": cutoff_days,
        "half_life_days": half_life_days,
        "top_n": top_n,
    }


def _overview_cache_file(params: dict) -> Path:
    key = f"{params['cutoff_days']}d_{params['half_life_days']}d_{params['top_n']}n"
    return OVERVIEW_DIR / f"overview_{key}.json"


def _load_overview_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_overview_cache(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _export_overview_files(*, payload: dict, params: dict) -> dict[str, str]:
    """Export overview data to files in outputs/ directory."""
    from ui_core import export_overview_files
    return export_overview_files(payload, params)


def _runs_within_cutoff(runs: list[dict], cutoff_days: int) -> list[dict]:
    """Filter runs to those within cutoff days of the most recent run."""
    if not runs:
        return []
    
    # Find the most recent run timestamp
    timestamps = [r.get("timestamp") for r in runs if r.get("timestamp")]
    if not timestamps:
        return []
    
    max_ts = max(timestamps)
    cutoff_ts = max_ts - pd.Timedelta(days=cutoff_days)
    
    return [r for r in runs if r.get("timestamp") and r.get("timestamp") >= cutoff_ts]