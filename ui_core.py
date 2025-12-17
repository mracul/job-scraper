from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path
import json
import copy
from datetime import datetime


# Settings management
STATE_DIR = Path(__file__).parent / "state"
SETTINGS_FILE = STATE_DIR / "ui_settings.json"

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
    },
    "ai": {
        "model": "gpt-5-mini"
    },
    "bundles": {
        "1️⃣ Core Entry-Level Catch-All (Daily)": [
            "IT Support",
            "Help Desk",
            "Service Desk",
        ],
        "2️⃣ Analyst / Corporate Titles (Daily)": [
            "Service Desk Analyst",
            "IT Support Analyst",
            "ICT Support",
        ],
        "3️⃣ Explicit Entry / Junior Signal (Daily)": [
            "Entry Level IT",
            "Junior IT",
            "Level 1 IT",
            "L1 Support",
        ],
        "4️⃣ Desktop / End-User Support (Every 2–3 Days)": [
            "Desktop Support",
            "End User Support",
            "Technical Support",
        ],
        "5️⃣ L1–L2 Hybrid / Stretch Roles (Every 2–3 Days)": [
            "Level 1/2 IT",
            "Level 2 IT",
            "Systems Support",
        ],
        "6️⃣ Microsoft Stack Signal (Weekly)": [
            "Microsoft 365 Support",
            "Active Directory Support",
            "Azure Support",
        ],
    }
}

def _stable_json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def load_settings() -> dict:
    """Load settings from JSON file, with defaults fallback."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Merge with defaults to ensure all keys exist
            settings = copy.deepcopy(DEFAULT_SETTINGS)
            for section in ["scraper", "ui", "ai", "bundles"]:
                if section in saved:
                    if isinstance(settings.get(section), dict) and isinstance(saved.get(section), dict):
                        settings[section].update(saved[section])
            return settings
        except Exception:
            pass
    return copy.deepcopy(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    """Save settings to JSON file."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


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

        summary = analysis.get("summary", {}) or analysis.get("presence", {}) or {}
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


def list_runs() -> list[dict]:
    """List all scraping runs with metadata, newest first."""
    SCRAPED_DATA_DIR = Path(__file__).parent / "scraped_data"
    
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
            "search_mode": None,
            "bundle_ids": [],
            "bundle_keywords": [],
            "job_count": 0,
            "timestamp": None,
            "has_analysis": False,
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
                    in_keyword_section = False
                    for _ in range(60):
                        line = f.readline()
                        if not line:
                            break

                        stripped = line.strip()
                        if stripped.startswith("**Search Keywords:**"):
                            meta["keywords"] = stripped.replace("**Search Keywords:**", "").strip().rstrip("  ")
                        elif stripped.startswith("**Search Location:**"):
                            meta["location"] = stripped.replace("**Search Location:**", "").strip().rstrip("  ")
                        elif stripped.startswith("**Search Mode:**"):
                            meta["search_mode"] = stripped.replace("**Search Mode:**", "").strip().lower()
                        elif stripped.startswith("**Bundle IDs:**"):
                            ids_raw = stripped.replace("**Bundle IDs:**", "").strip()
                            meta["bundle_ids"] = [p.strip() for p in ids_raw.split(",") if p.strip()]
                        elif stripped.startswith("**Keyword Phrases:**"):
                            in_keyword_section = True
                            continue
                        elif stripped.startswith("**Total Jobs:**"):
                            try:
                                meta["job_count"] = int(stripped.replace("**Total Jobs:**", "").strip())
                            except ValueError:
                                pass

                        if in_keyword_section and stripped.startswith("- "):
                            meta["bundle_keywords"].append(stripped[2:].strip())
                        elif in_keyword_section and (not stripped or stripped.startswith("**")):
                            in_keyword_section = False
            except Exception:
                pass

        # Check for analysis files
        meta["has_analysis"] = (folder / "requirements_analysis.json").exists()

        # Display-friendly name for UI rows
        if meta.get("search_mode") == "bundle" and meta.get("bundle_ids"):
            meta["display_name"] = meta["bundle_ids"][0]
        elif meta.get("keywords"):
            if meta.get("location") and meta.get("location") != "Not specified":
                meta["display_name"] = f"{meta['keywords']} — {meta['location']}"
            else:
                meta["display_name"] = meta["keywords"]
        else:
            meta["display_name"] = folder.name

        runs.append(meta)
    
    # Sort by timestamp descending
    runs.sort(key=lambda r: r["timestamp"] or datetime.min, reverse=True)
    return runs
