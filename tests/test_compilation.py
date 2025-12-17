from __future__ import annotations

from pathlib import Path

import pytest

from streamlit_app import (
    CATEGORY_LABELS,
    _build_ai_summary_input,
    _merge_analyses,
    load_analysis,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _find_real_run_dirs_with_analysis() -> list[Path]:
    scraped = _repo_root() / "scraped_data"
    if not scraped.exists():
        return []
    runs: list[Path] = []
    for p in scraped.iterdir():
        if not p.is_dir():
            continue
        if (p / "requirements_analysis.json").exists():
            runs.append(p)
    runs.sort(key=lambda x: x.name)
    return runs


def _require_real_runs(min_count: int = 1) -> list[Path]:
    runs = _find_real_run_dirs_with_analysis()
    if len(runs) < min_count:
        pytest.skip(
            f"Need at least {min_count} real run(s) with requirements_analysis.json under scraped_data/"
        )
    return runs


def test_load_analysis_reads_real_json():
    run_dir = _require_real_runs(1)[0]
    loaded = load_analysis(run_dir)
    assert isinstance(loaded, dict)
    assert isinstance(loaded.get("total_jobs"), int)
    assert isinstance(loaded.get("summary"), dict)


def test_build_ai_summary_input_real_data_includes_all_categories_and_valid_pcts():
    run_dir = _require_real_runs(1)[0]
    analysis = load_analysis(run_dir)
    assert analysis is not None

    total_jobs = int(analysis.get("total_jobs", 0) or 0)
    summary = analysis.get("summary", {}) or analysis.get("presence", {}) or {}

    ai_input = _build_ai_summary_input(
        total_jobs=total_jobs,
        summary=summary,
        search_context={"run": run_dir.name},
        scope_label="single",
        top_n_per_category=50,
    )

    assert ai_input["scope"] == "single"
    assert ai_input["total_jobs"] == total_jobs

    # Stable schema: ALL categories always present
    assert set(ai_input["categories"].keys()) == set(CATEGORY_LABELS.keys())

    # For any included item, pct must match count/total_jobs (rounded to 1 dp), or 0 when total_jobs==0
    for cat_key in CATEGORY_LABELS.keys():
        cat = ai_input["categories"][cat_key]
        assert "label" in cat
        assert "total_unique" in cat
        assert "included" in cat
        assert "truncated" in cat
        assert "top" in cat
        assert isinstance(cat["top"], list)
        for item in cat["top"]:
            expected = round((float(item["count"]) / float(total_jobs) * 100.0), 1) if total_jobs else 0.0
            assert item["pct"] == expected


def test_merge_analyses_real_data_sums_totals_and_sample_terms():
    run_dirs = _require_real_runs(2)
    a1 = load_analysis(run_dirs[0])
    a2 = load_analysis(run_dirs[1])
    assert a1 is not None and a2 is not None

    merged = _merge_analyses([a1, a2])
    assert merged["total_jobs"] == int(a1.get("total_jobs", 0) or 0) + int(a2.get("total_jobs", 0) or 0)

    merged_summary = merged.get("summary", {}) or {}
    # Spot-check: for any category that has terms, verify up to 5 terms are correctly summed.
    checked = 0
    for cat_key in CATEGORY_LABELS.keys():
        s1 = (a1.get("summary", {}) or {}).get(cat_key, {}) or {}
        s2 = (a2.get("summary", {}) or {}).get(cat_key, {}) or {}
        union_terms = list(dict.fromkeys(list(s1.keys()) + list(s2.keys())))
        for term in union_terms[:5]:
            expected = int(s1.get(term, 0) or 0) + int(s2.get(term, 0) or 0)
            actual = int((merged_summary.get(cat_key, {}) or {}).get(term, 0) or 0)
            assert actual == expected
            checked += 1
    assert checked > 0


def test_compiled_pipeline_real_data_produces_ai_input_from_aggregated_counts():
    run_dirs = _require_real_runs(2)
    analyses = [load_analysis(run_dirs[0]), load_analysis(run_dirs[1])]
    assert all(a is not None for a in analyses)
    merged = _merge_analyses([a for a in analyses if a])

    ai_input = _build_ai_summary_input(
        total_jobs=merged["total_jobs"],
        summary=merged["summary"],
        search_context={"runs": [run_dirs[0].name, run_dirs[1].name]},
        scope_label="compiled",
        top_n_per_category=50,
    )

    assert ai_input["scope"] == "compiled"
    assert ai_input["total_jobs"] == merged["total_jobs"]
    assert set(ai_input["categories"].keys()) == set(CATEGORY_LABELS.keys())

    total_jobs = int(merged["total_jobs"] or 0)
    # Spot-check pct math in compiled context.
    for cat_key in CATEGORY_LABELS.keys():
        cat = ai_input["categories"][cat_key]
        for item in cat["top"][:5]:
            expected = round((float(item["count"]) / float(total_jobs) * 100.0), 1) if total_jobs else 0.0
            assert item["pct"] == expected
