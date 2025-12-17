import json
from pathlib import Path
import pandas as pd
import streamlit as st


def _load_cached_ai_summary(cache_path: Path) -> dict | None:
    """Load cached AI summary with robust error handling."""
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Validate that it's a dict with required fields
        if isinstance(data, dict) and "summary" in data and "input_hash" in data:
            return data
        return None
    except (json.JSONDecodeError, IOError, OSError):
        # If file is corrupted, remove it so it can be regenerated
        try:
            cache_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def _save_cached_ai_summary(cache_path: Path, data: dict) -> None:
    """Save cached AI summary with robust error handling."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary file first, then rename for atomicity
        temp_path = cache_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.replace(cache_path)
    except Exception:
        # If saving fails, try the old method
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass  # Silently fail if caching is not possible


def _get_run_search_meta(run_path: Path) -> tuple[str | None, str | None]:
    """Try to read search keywords/location from compiled_jobs.md header."""
    md_path = run_path / "compiled_jobs.md"
    if not md_path.exists():
        return None, None
    keywords = None
    location = None
    try:
        with open(md_path, "r", encoding="utf-8", errors="replace") as f:
            for _ in range(60):
                line = f.readline()
                if not line:
                    break
                if line.startswith("**Search Keywords:**"):
                    keywords = line.replace("**Search Keywords:**", "").strip().rstrip("  ")
                elif line.startswith("**Search Location:**"):
                    location = line.replace("**Search Location:**", "").strip().rstrip("  ")
                if keywords and location:
                    break
    except Exception:
        return None, None
    return keywords, location


@st.cache_data
def _load_analysis_cached(analysis_file: str, mtime: float) -> dict | None:
    """Cached JSON loader keyed on (path, mtime) to avoid stale UI data."""
    try:
        with open(analysis_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def load_analysis(run_path: Path) -> dict | None:
    """Load requirements_analysis.json for a run."""
    analysis_file = run_path / "requirements_analysis.json"
    if not analysis_file.exists():
        return None
    try:
        mtime = float(analysis_file.stat().st_mtime)
    except Exception:
        mtime = 0.0
    return _load_analysis_cached(str(analysis_file), mtime)


@st.cache_data
def _load_text_file_cached(path: str, mtime: float) -> str | None:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return None


def load_requirements_analysis_txt(run_path: Path) -> str | None:
    """Load requirements_analysis.txt for a run (human-readable analysis)."""
    txt_file = run_path / "requirements_analysis.txt"
    if not txt_file.exists():
        return None
    try:
        mtime = float(txt_file.stat().st_mtime)
    except Exception:
        mtime = 0.0
    return _load_text_file_cached(str(txt_file), mtime)


@st.cache_data
def _load_jobs_csv_cached(csv_file: str, mtime: float) -> pd.DataFrame | None:
    """Cached CSV loader keyed on (path, mtime) to avoid stale UI data."""
    try:
        return pd.read_csv(csv_file)
    except Exception:
        return None


def load_jobs_csv(run_path: Path) -> pd.DataFrame | None:
    """Load all_jobs.csv as DataFrame."""
    csv_file = run_path / "all_jobs.csv"
    if not csv_file.exists():
        return None
    try:
        mtime = float(csv_file.stat().st_mtime)
    except Exception:
        mtime = 0.0
    return _load_jobs_csv_cached(str(csv_file), mtime)