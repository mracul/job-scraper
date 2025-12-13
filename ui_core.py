from __future__ import annotations

from collections.abc import Iterable, Mapping


def build_ai_summary_input(
    *,
    total_jobs: int,
    summary: dict,
    search_context: dict,
    scope_label: str,
    category_labels: Mapping[str, str],
    top_n_per_category: int = 25,
) -> dict:
    """Build payload of tag percentages to feed to an LLM.

    Kept Streamlit-free so it can be tested/imported without UI concerns.
    """
    categories_payload: dict[str, dict] = {}
    limit = max(1, int(top_n_per_category))

    for cat_key, cat_label in category_labels.items():
        items = (summary or {}).get(cat_key, {}) or {}
        top_items = sorted(items.items(), key=lambda t: t[1], reverse=True)[:limit] if items else []
        categories_payload[cat_key] = {
            "label": cat_label,
            "total_unique": len(items),
            "included": len(top_items),
            "truncated": len(items) > len(top_items),
            "top": [
                {
                    "term": term,
                    "count": int(count),
                    "pct": round((float(count) / float(total_jobs) * 100.0), 1) if total_jobs else 0.0,
                }
                for term, count in top_items
            ],
        }

    return {
        "scope": scope_label,
        "total_jobs": int(total_jobs or 0),
        "search": search_context,
        "categories": categories_payload,
    }


def merge_analyses(analyses: list[dict], *, category_keys: Iterable[str]) -> dict:
    """Merge multiple requirements_analysis.json payloads into a combined summary."""
    keys = list(category_keys)
    merged_summary: dict[str, dict[str, int]] = {k: {} for k in keys}
    total_jobs = 0
    combined_job_details: list[dict] = []

    for analysis in analyses:
        if not analysis:
            continue
        total_jobs += int(analysis.get("total_jobs", 0) or 0)

        summary = analysis.get("summary", {}) or {}
        for cat in keys:
            items = summary.get(cat, {}) or {}
            bucket = merged_summary.setdefault(cat, {})
            for term, count in items.items():
                try:
                    bucket[term] = int(bucket.get(term, 0)) + int(count)
                except Exception:
                    pass

        combined_job_details.extend(analysis.get("job_details", []) or [])

    return {
        "summary": merged_summary,
        "total_jobs": total_jobs,
        "job_details": combined_job_details,
    }
