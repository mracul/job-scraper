from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path


COMPILED_REPORTS_DIRNAME = "compiled_reports"
COMPILED_REPORT_VERSION = "1"


def compiled_report_id_for_run_names(run_names: list[str]) -> str:
    """Stable id for a compiled report based on selected run folder names."""
    raw = "|".join(sorted((n or "").strip() for n in run_names if (n or "").strip()))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def compiled_report_path(state_dir: Path, *, run_names: list[str]) -> Path:
    report_id = compiled_report_id_for_run_names(run_names)
    return state_dir / COMPILED_REPORTS_DIRNAME / f"compiled_{report_id}.json"


def build_runs_fingerprint(run_paths: list[Path]) -> list[dict]:
    """Fingerprint of selected runs that invalidates cached merged data when inputs change.

    Uses only lightweight filesystem stats (no JSON loading).
    """
    fingerprint: list[dict] = []
    for run_path in sorted(run_paths, key=lambda p: p.name):
        analysis_file = run_path / "requirements_analysis.json"
        has_analysis = analysis_file.exists()
        mtime = 0.0
        size = 0
        if has_analysis:
            try:
                stat = analysis_file.stat()
                mtime = float(stat.st_mtime)
                size = int(stat.st_size)
            except Exception:
                mtime = 0.0
                size = 0
        fingerprint.append(
            {
                "run": run_path.name,
                "has_analysis": bool(has_analysis),
                "analysis_mtime": mtime,
                "analysis_size": size,
            }
        )
    return fingerprint


def load_compiled_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def save_compiled_report_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd = None
    tmp_path = None
    try:
        fd, tmp = tempfile.mkstemp(prefix=path.stem + "_", suffix=".tmp", dir=str(path.parent))
        tmp_fd = fd
        tmp_path = tmp
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        tmp_fd = None
        os.replace(tmp, path)
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except Exception:
                pass
        if tmp_path is not None and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def is_matching_compiled_report(
    report: dict, *, run_names: list[str], fingerprint: list[dict]
) -> bool:
    if not report or not isinstance(report, dict):
        return False
    if str(report.get("version")) != COMPILED_REPORT_VERSION:
        return False

    expected_run_names = sorted((n or "").strip() for n in run_names if (n or "").strip())
    stored_run_names = report.get("run_names")
    if not isinstance(stored_run_names, list):
        return False
    stored_run_names_norm = sorted((str(n) or "").strip() for n in stored_run_names if (str(n) or "").strip())
    if stored_run_names_norm != expected_run_names:
        return False

    stored_fp = report.get("runs_fingerprint")
    if not isinstance(stored_fp, list):
        return False

    return stored_fp == fingerprint


def build_compiled_report_payload(
    *,
    run_names: list[str],
    fingerprint: list[dict],
    merged_analysis: dict,
    name: str | None = None,
    created_at: str | None = None,
) -> dict:
    now = datetime.now().isoformat()
    run_names_norm = sorted((n or "").strip() for n in run_names if (n or "").strip())

    report_id = compiled_report_id_for_run_names(run_names_norm)
    return {
        "version": COMPILED_REPORT_VERSION,
        "id": f"compiled_{report_id}",
        "name": name or f"Compiled ({len(run_names_norm)} runs)",
        "created_at": created_at or now,
        "updated_at": now,
        "run_names": run_names_norm,
        "runs_fingerprint": fingerprint,
        "merged_analysis": merged_analysis,
    }
