"""
Job Scraper - Streamlit UI
A web interface for running job scrapes and exploring results.
"""

import streamlit as st
import streamlit.components.v1
import pandas as pd
import requests
import json
import re
import os
import time
import subprocess
import sys
import shutil
import hashlib
import copy
from pathlib import Path
from datetime import datetime
from collections import defaultdict
import plotly.express as px

from ui_core import build_ai_summary_input as _ui_build_ai_summary_input
from ui_core import merge_analyses as _ui_merge_analyses

from compiled_report_store import (
    build_compiled_report_payload,
    build_runs_fingerprint,
    compiled_report_path,
    is_matching_compiled_report,
    load_compiled_report,
    save_compiled_report_atomic,
)


def split_tldr(md: str):
    """
    Extract the TL;DR section (## TL;DR ...) and return (tldr_md, rest_md).
    Safe no-op if TL;DR not present.
    """
    if not md:
        return "", ""

    m = re.search(r"(?ms)^##\s+TL;DR.*?(?=^##\s+|\Z)", md)
    if not m:
        return "", md

    tldr = m.group(0).strip()
    rest = (md[:m.start()] + md[m.end():]).strip()
    return tldr, rest


# ============================================================================
# Configuration & Constants
# ============================================================================

SCRAPED_DATA_DIR = Path(__file__).parent / "scraped_data"
STATE_DIR = Path(__file__).parent / "state"
SETTINGS_FILE = STATE_DIR / "ui_settings.json"
RUN_STATE_FILE = STATE_DIR / "active_run.json"
LOGS_DIR = Path(__file__).parent / "logs"
OVERVIEW_DIR = STATE_DIR / "overviews"
OUTPUTS_DIR = Path(__file__).parent / "outputs"

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


def _get_openai_api_key() -> str | None:
    """Get OpenAI API key from environment or Streamlit secrets."""
    # Prioritize environment variable (useful for local dev/overrides)
    env_value = os.getenv("OPENAI_API_KEY")
    if env_value:
        return env_value

    for key_name in ("OPENAI_API_KEY", "openai_api_key"):
        try:
            value = st.secrets.get(key_name)
        except Exception:
            value = None
        if value:
            return str(value)
    
    return None


def _stable_json_dumps(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash_payload(payload) -> str:
    raw = _stable_json_dumps(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


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


AI_SUMMARY_SYSTEM_PROMPT = """Good catch — yes, based on the **recent AI Summary / Streamlit card discussions**, a **TL;DR section absolutely belongs here**, and it should be **explicitly constrained** so it doesn’t undo all the discipline you built elsewhere.

Below is the **updated artifact**, with a **properly scoped TL;DR section** added and aligned with the “AI Summary” intent you’ve been using recently.

---

# IT Support / Help Desk Job Market Interpreter

**Role Definition & Output Contract**

You are a **career coach** helping people enter or progress in **IT Support and Help Desk roles**, using **aggregated job market data** to guide efficient, evidence-based decision-making.

You will be given:

* A **plain-text requirements analysis report** generated from job listings
  (includes categories, tags, counts, and percentages)
* A small **metadata JSON block**
  (search terms, location, run scope)

Your task is to **interpret the report** and translate it into **practical, market-aligned guidance** on where a candidate should focus their effort.

---

## Core Principles

* **Use only the provided data**

  * Do **not** introduce technologies, certifications, tools, or requirements that do not appear in the tags.
* **No hidden inference**

  * Do **not** infer “typical” expectations or industry norms unless directly supported by the data.
* **Percentages explain priority**

  * Use percentages to explain **relative demand and importance**, not to dump statistics.
* **Pattern over inventory**

  * Focus on **signals, trade-offs, and implications**, not exhaustive lists.
* **Grounded optimism**

  * Be realistic and encouraging, but **avoid certainty or guarantees**.

---

## Output Discipline (Strict)

* **Depth over breadth**

  * Identify the **top 3–5 strongest market signals** only.
  * Explicitly deprioritise weaker or fringe signals.
* **No repetition**

  * Do not restate the same implication across multiple sections.
* **No multi-phase roadmaps**

  * Do not introduce staged or long-term plans unless explicitly requested.
* **Bounded examples**

  * Use only a **few representative examples per theme**, always tied to percentages.
* **Truncation awareness**

  * If a category is truncated, explicitly note that **only top signals are visible**.

---

## TL;DR — Market Snapshot (Required)

Provide a **concise executive summary** intended for quick scanning or UI display.

**Rules for this section:**

* **3–5 bullet points only**
* Each bullet must:

  * Reflect a **strong signal** from the data
  * Use **plain language**
  * Avoid listing tools exhaustively
* No percentages unless they materially strengthen the point
* No advice phrased as guarantees

**Purpose:**

* Give the reader a **high-confidence orientation** before detail
* Serve as a **standalone AI summary** without replacing deeper sections

This section should be readable **in isolation**.

---

## 1. Market Signals & Direction

Explain:

* What the data suggests about **overall employer priorities**
* Whether demand is **concentrated around a few strong signals** or spread across many weaker ones
* What this implies about **how narrowly or broadly candidates should focus**

Avoid listing technologies here—focus on **direction and signal strength**.

---

## 2. Certifications & Credentials

Cover:

* Which certifications stand out **by relative demand**
* How a candidate might **sensibly prioritise** them (e.g., first vs later) based on:

  * Frequency
  * Alignment with entry-level or support responsibilities
* Frame certifications as **signals to employers**, not proof of competence

Do **not** recommend certifications that do not appear in the data.

---

## 3. Technical Skill Focus

Identify:

* The **most frequently appearing technical skills or tools**
* What those signals imply about the **types of problems the role is expected to solve**

  * e.g. account access issues, device configuration, endpoint troubleshooting, basic networking

Focus on **problem domains**, not tool mastery narratives.

---

## 4. Professional & Soft Skills

Explain:

* How soft skills appear **relative to technical requirements**
* What this suggests about:

  * Day-to-day work expectations
  * Hiring and screening priorities

Keep interpretation grounded in **relative frequency**, not opinion.

---

## 5. Practical Development Guidance

Translate the strongest signals into **concrete but bounded actions**:

* What to **prioritise learning or practising first**
* What kinds of **hands-on evidence** best align with the data

  * e.g. documented troubleshooting, ticket examples, lab notes
* What to **emphasise in resumes or interviews**, based on signal strength

Avoid:

* Long-term career speculation
* Pathways not supported by the data
* Over-engineering or exhaustive prep lists

---

## 6. Search Context

Briefly relate:

* The original **search terms and location**
* How they may explain or influence the observed demand patterns

Keep this short and contextual.

---

## Intent

Your goal is **not** to prescribe a single path.

Your goal is to help the reader:

* Allocate **time and energy efficiently**
* Focus on what the **market is demonstrably asking for**
* Make **informed trade-offs**, not chase completeness

---
If analysis approaches verbosity limits, prioritise TL;DR clarity and omit lower-priority sections rather than exceeding output bounds.
"""

AI_SUMMARY_MAX_OUTPUT_TOKENS = 2000
AI_SUMMARY_TOP_N_SINGLE = 50 #SINGLE SCRAPE RUN
AI_SUMMARY_TOP_N_COMPILED = 75 #COMPILED SCRAPE RUNS


def _fallback_summary_from_input(ai_input: dict) -> str:
    """Simple fallback when AI generation fails - just show error message."""
    total_jobs = ai_input.get("total_jobs", 0)
    return (
        f"⚠️ **AI summary generation failed.** Unable to analyze {total_jobs} job listings.\n\n"
        "Please check your OpenAI API key in Settings or try again later."
    )


def _generate_ai_summary_text(ai_input: dict) -> str:
    api_key = _get_openai_api_key()
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Add it to .streamlit/secrets.toml or env var.")

    settings = load_settings()
    ai_model = settings.get("ai", {}).get("model", "gpt-5-mini")

    # Prefer sending the human-readable analysis text (requirements_analysis.txt) plus metadata.
    # Backward-compatibility: some callers still pass structured JSON (categories/top terms).
    if isinstance(ai_input, dict) and isinstance(ai_input.get("analysis_text"), str):
        meta = ai_input.get("meta")
        user_prompt = (
            "Here is a job requirements analysis report for the user's search. "
            "Use ONLY the report text and the metadata block to produce the requested summary.\n\n"
            f"METADATA_JSON={_stable_json_dumps(meta if isinstance(meta, dict) else {})}\n\n"
            f"REQUIREMENTS_ANALYSIS_TXT=\n{ai_input.get('analysis_text','').strip()}"
        )
    else:
        user_prompt = (
            "Here is aggregated job-requirement data (counts and consolidated percentages) for the user's search. "
            "Use it to produce the requested summary.\n\n"
            f"DATA_JSON={_stable_json_dumps(ai_input)}"
        )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": ai_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": AI_SUMMARY_SYSTEM_PROMPT}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
        "max_output_tokens": AI_SUMMARY_MAX_OUTPUT_TOKENS,
    }

    url = "https://api.openai.com/v1/responses"
    backoff_seconds = 1.0
    resp = None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            resp = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=120,
            )
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(backoff_seconds)
                backoff_seconds *= 2
                continue
            raise RuntimeError(f"OpenAI request failed: {exc}")

        if resp.status_code in {429, 500, 502, 503, 504} and attempt < 2:
            time.sleep(backoff_seconds)
            backoff_seconds *= 2
            continue

        if resp.status_code >= 400:
            raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text[:400]}")
        break

    if resp is None:
        raise RuntimeError(f"OpenAI request failed: {last_error}")

    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"OpenAI API returned non-JSON response: {str(exc)[:200]}")
    parts: list[str] = []
    for out in data.get("output", []) or []:
        for content in out.get("content", []) or []:
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content.get("text"))
    text = "".join(parts).strip()
    if not text:
        # Fallback for unexpected response shapes
        text = (data.get("output_text") or "").strip()
    if not text:
        text = _fallback_summary_from_input(ai_input)
    return text


def _render_ai_summary_block(*, cache_path: Path, ai_input: dict, auto_generate: bool = True) -> None:
    import time, hashlib
    from datetime import datetime

    settings = load_settings()
    ai_model = settings.get("ai", {}).get("model", "gpt-5-mini")

    cache_basis = {
        "ai_input": ai_input,
        "model": ai_model,
        "max_output_tokens": AI_SUMMARY_MAX_OUTPUT_TOKENS,
        "system_prompt": AI_SUMMARY_SYSTEM_PROMPT,
    }

    cached = _load_cached_ai_summary(cache_path)
    input_hash = _hash_payload(cache_basis)

    cached_text = None
    cache_status = None
    if cached:
        if cached.get("input_hash") == input_hash:
            cached_text = cached.get("summary")
            cache_status = "current"
        elif cached.get("summary"):
            cached_text = cached.get("summary")
            cache_status = "outdated"

    auto_key = f"ai_auto_{cache_path.name}_{input_hash[:8]}"
    inflight_key = f"ai_inflight_{cache_path.name}_{input_hash[:8]}"
    inflight_started_key = f"ai_inflight_started_{cache_path.name}_{input_hash[:8]}"

    # Optional: remember whether the block is collapsed
    collapsed_key = f"ai_collapsed_{cache_path.name}_{input_hash[:8]}"
    if collapsed_key not in st.session_state:
        st.session_state[collapsed_key] = False

    summary_text = cached_text

    # Auto-clear stuck inflight
    try:
        inflight_started = st.session_state.get(inflight_started_key)
        if st.session_state.get(inflight_key) and isinstance(inflight_started, (int, float)):
            if (time.time() - float(inflight_started)) > 300:
                st.session_state[inflight_key] = False
                st.session_state.pop(inflight_started_key, None)
    except Exception:
        pass

    def _save(summary: str) -> None:
        _save_cached_ai_summary(
            cache_path,
            {
                "model": ai_model,
                "max_output_tokens": AI_SUMMARY_MAX_OUTPUT_TOKENS,
                "system_prompt_hash": hashlib.sha256(AI_SUMMARY_SYSTEM_PROMPT.encode("utf-8")).hexdigest()[:12],
                "generated_at": datetime.now().isoformat(),
                "input_hash": input_hash,
                "summary": summary,
            },
        )

    def _run_generation() -> str:
        with st.spinner("Generating summary..."):
            return _generate_ai_summary_text(ai_input)

    # ===== AUTO GENERATE (keep your behavior) =====
    if auto_generate and (not cached_text) and (not st.session_state.get(auto_key)):
        st.session_state[auto_key] = True
        st.session_state[inflight_key] = True
        st.session_state[inflight_started_key] = time.time()
        try:
            summary_text = _run_generation()
            _save(summary_text)
            st.session_state[inflight_key] = False
            st.session_state.pop(inflight_started_key, None)
            st.rerun()
            return
        except Exception as exc:
            st.session_state[inflight_key] = False
            st.session_state.pop(inflight_started_key, None)
            st.error(str(exc))
            summary_text = None

    st.markdown("""
    <style>
    /* --- AI Summary: remove the inner 'card' look --- */
    .ai-summary div[data-testid="stMarkdown"],
    .ai-summary div[data-testid="stMarkdownContainer"],
    .ai-summary div[data-testid="stMarkdownContainer"] > div,
    .ai-summary div[data-testid="stMarkdown"] > div {
    background: transparent !important;
    border: 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    }

    /* Sometimes the scroll container adds a background/radius */
    .ai-summary div[data-testid="stContainer"] {
    background: transparent !important;
    }

    /* Keep the outer bordered card intact: only flatten INNER wrappers */
    .ai-summary div[data-testid="stContainer"][style*="border"] {
    background: unset !important; /* don't break your card */
    }
    </style>
    """, unsafe_allow_html=True)


    # ===== UI CARD =====
    with st.container(border=True):
        # Header row (title + status on left, toolbar on right)
        left, right = st.columns([0.72, 0.28], vertical_alignment="center")

        with left:
            status = "• —"
            if cache_status == "current":
                status = "• ✅ cached"
            elif cache_status == "outdated":
                status = "• ⚠️ outdated"
            elif summary_text:
                status = "• ℹ️ generated"

            st.markdown(
                f"### 🤖 AI Summary <span style='opacity:0.6;font-size:0.85em;'>{status}</span>",
                unsafe_allow_html=True,
            )

        with right:
            b1, b2, b3 = st.columns(3)

            # 1) Generate / Regenerate (or reset if stuck)
            with b1:
                if st.session_state.get(inflight_key):
                    if st.button("🔄", use_container_width=True,
                                 key=f"reset_{cache_path.name}_{input_hash[:8]}",
                                 help="Reset stuck generation"):
                        st.session_state[inflight_key] = False
                        st.session_state.pop(inflight_started_key, None)
                        st.session_state[auto_key] = False
                        st.rerun()
                else:
                    label = "Generate" if not summary_text else "Regenerate"
                    if st.button("✨", use_container_width=True,
                                 key=f"gen_{cache_path.name}_{input_hash[:8]}",
                                 help=f"{label} AI summary"):
                        st.session_state[auto_key] = False
                        st.session_state[inflight_key] = True
                        st.session_state[inflight_started_key] = time.time()
                        try:
                            summary_text = _run_generation()
                            _save(summary_text)
                            st.session_state[inflight_key] = False
                            st.session_state.pop(inflight_started_key, None)
                            st.rerun()
                            return
                        except Exception as e:
                            st.session_state[inflight_key] = False
                            st.session_state.pop(inflight_started_key, None)
                            st.error(str(e))
                            summary_text = None

            # 2) Clear cache
            with b2:
                disabled = not bool(cached_text)
                if st.button("🗑️", use_container_width=True,
                             key=f"clr_{cache_path.name}_{input_hash[:8]}",
                             help="Clear cached summary",
                             disabled=disabled):
                    try:
                        cache_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    st.rerun()

            # 3) Expand (dialog) OR collapse toggle
            with b3:
                disabled = not bool(summary_text)
                if st.button("⤢", use_container_width=True,
                             key=f"exp_{cache_path.name}_{input_hash[:8]}",
                             help="Expand AI summary",
                             disabled=disabled):
                    if hasattr(st, "dialog"):
                        @st.dialog("🤖 AI Summary")
                        def _show_ai_summary_dialog(text: str):
                            st.markdown(text)
                        _show_ai_summary_dialog(summary_text or "")
                    else:
                        st.session_state[collapsed_key] = False  # ensure visible
                        with st.expander("AI Summary (expanded)", expanded=True):
                            st.markdown(summary_text or "")

        # Body
        if st.session_state.get(inflight_key):
            st.info("Generating summary…")

        if summary_text:
            tldr_md, rest_md = split_tldr(summary_text)

            # TL;DR always visible (no scroll)
            if tldr_md:
                st.markdown(tldr_md)
                st.markdown("---")  # subtle divider inside the card

            # Details scroll (NO border to avoid nesting)
            try:
                with st.container(height=260):
                    st.markdown(rest_md or "_No further details._")
            except TypeError:
                st.markdown(rest_md or "_No further details._")
        else:
            st.markdown("_No summary yet._")

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


def _truncate_text(text: str, *, max_chars: int, suffix: str) -> str:
    if not isinstance(text, str):
        return ""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def _build_ai_text_payload(*, analysis_text: str, meta: dict) -> dict:
    """Build the AI input payload for summary generation.

    The report text is the authoritative representation of the categorical data.
    """
    return {
        "analysis_text": str(analysis_text or ""),
        "meta": meta if isinstance(meta, dict) else {},
    }


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
    if "nav_origin" not in st.session_state:
        # Used to control where "Back" returns (e.g. compiled overview).
        st.session_state.nav_origin = None
    if "overview_params" not in st.session_state:
        st.session_state.overview_params = None
    if "overview_cache_path" not in st.session_state:
        st.session_state.overview_cache_path = None
    if "overview_notice" not in st.session_state:
        st.session_state.overview_notice = None


def _overview_params(cutoff_days: int, half_life_days: int, top_n: int) -> dict:
    return {
        "cutoff_days": int(cutoff_days),
        "half_life_days": int(half_life_days),
        "top_n": int(top_n),
    }


def _overview_cache_file(params: dict) -> Path:
    OVERVIEW_DIR.mkdir(parents=True, exist_ok=True)
    key = _hash_payload({"overview": params})[:16]
    return OVERVIEW_DIR / f"overview_{key}.json"


def _load_overview_cache(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _save_overview_cache(path: Path, data: dict) -> None:
    OVERVIEW_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _export_overview_files(*, payload: dict, params: dict) -> dict[str, str]:
    """Export overview artifacts to outputs/.

    Writes:
    - overview_<key>.json (full cached payload, plus AI summary text if available)
    - overview_<key>_series.csv (trend series)
    - overview_<key>.md (human-readable summary)
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    key = _hash_payload({"overview": params})[:16]
    json_path = OUTPUTS_DIR / f"overview_{key}.json"
    csv_path = OUTPUTS_DIR / f"overview_{key}_series.csv"
    md_path = OUTPUTS_DIR / f"overview_{key}.md"

    # Best-effort: include AI summary (if already generated)
    ai_cache = OVERVIEW_DIR / f"ai_{_hash_payload(params)[:16]}.json"
    ai_text: str | None = None
    cached_ai = _load_cached_ai_summary(ai_cache)
    if cached_ai and isinstance(cached_ai.get("summary"), str):
        ai_text = cached_ai.get("summary")

    export_payload = dict(payload)
    export_payload["ai_summary"] = ai_text
    export_payload["exported_at"] = datetime.now().isoformat()

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(export_payload, f, indent=2, ensure_ascii=False)

    # CSV series
    series = payload.get("series")
    if isinstance(series, list) and series:
        df = pd.DataFrame(series)
        # Ensure stable column order
        cols = [
            c
            for c in ["timestamp", "run", "run_order", "category", "term", "count", "pct", "total_jobs"]
            if c in df.columns
        ]
        if cols:
            df = df[cols]
        df.to_csv(csv_path, index=False)
    else:
        # Still create an empty CSV so exports are predictable
        pd.DataFrame(columns=["timestamp", "run", "run_order", "category", "term", "count", "pct", "total_jobs"]).to_csv(
            csv_path, index=False
        )

    # Markdown report
    meta = payload.get("meta") or {}
    runs_used = payload.get("runs") or []
    runs_count = len(runs_used) if isinstance(runs_used, list) else 0
    raw_jobs = int(meta.get("raw_jobs", 0) or 0)
    effective_jobs = float(meta.get("effective_jobs", 0) or 0)
    cutoff_days = meta.get("cutoff_days", "N/A")
    half_life_days = meta.get("half_life_days", "N/A")
    min_ts = meta.get("min_ts", "")
    max_ts = meta.get("max_ts", "")
    top_n = params.get("top_n", 10)

    lines: list[str] = []
    lines.append("# Job Market Overview (Weighted)")
    lines.append("")
    lines.append(f"**Cutoff:** {cutoff_days} days  ")
    lines.append(f"**Half-life:** {half_life_days} days  ")
    lines.append(f"**Top N terms/category:** {top_n}  ")
    lines.append(f"**Generated:** {payload.get('generated_at')}")
    lines.append("")
    lines.append("## Window Summary")
    lines.append("")
    lines.append(f"- Runs included: {runs_count}")
    lines.append(f"- Raw jobs scanned: {raw_jobs:,}")
    lines.append(f"- Effective jobs (weighted): {effective_jobs:,.1f}")
    if min_ts and max_ts:
        lines.append(f"- Window span: {min_ts[:10]} → {max_ts[:10]}")
    lines.append("")

    if isinstance(runs_used, list) and runs_used:
        lines.append("## Runs")
        lines.append("")
        for r in runs_used:
            name = r.get("name")
            ts = r.get("timestamp", "")[:10] if r.get("timestamp") else ""
            jobs = r.get("total_jobs") or r.get("job_count")
            weight = r.get("weight", 1.0)
            lines.append(f"- {name} ({jobs} jobs, weight: {weight:.3f}) — {ts}")
        lines.append("")

    # Weighted summary by category
    weighted_summary = payload.get("weighted_summary") or {}
    top_terms = payload.get("top_terms") or {}
    if weighted_summary:
        lines.append("## Weighted Summary")
        lines.append("")
        for cat_key, cat_label in CATEGORY_LABELS.items():
            terms = top_terms.get(cat_key, [])
            if not terms:
                continue
            cat_data = weighted_summary.get(cat_key, {})
            lines.append(f"### {cat_label}")
            lines.append("")
            lines.append("| Term | Weighted % | Weighted Count |")
            lines.append("|------|------------|----------------|")
            for term in terms:
                item = cat_data.get(term, {})
                w_pct = item.get("weighted_pct", 0)
                w_count = item.get("weighted_count", 0)
                lines.append(f"| {term} | {w_pct:.1f}% | {w_count:.1f} |")
            lines.append("")

    lines.append("## AI Summary")
    lines.append("")
    if ai_text:
        lines.append(ai_text.strip())
    else:
        lines.append("_AI summary not generated yet. Generate it from the Overview page, then export again._")
    lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {"json": str(json_path), "csv": str(csv_path), "md": str(md_path)}


def _runs_within_cutoff(runs: list[dict], cutoff_days: int) -> list[dict]:
    """Filter runs to those within cutoff_days of the most recent run."""
    if not runs:
        return []
    # Find t_ref = max timestamp among runs
    timestamps = []
    for r in runs:
        ts = r.get("timestamp")
        if isinstance(ts, datetime):
            timestamps.append(ts.timestamp())
    if not timestamps:
        return runs
    t_ref = max(timestamps)
    cutoff_ts = t_ref - (cutoff_days * 86400)
    selected = []
    for r in runs:
        ts = r.get("timestamp")
        if isinstance(ts, datetime):
            if ts.timestamp() >= cutoff_ts:
                selected.append(r)
    return selected


def _compute_run_weight(run_ts: datetime, t_ref: float, half_life_days: float) -> float:
    """Compute weight using half-life decay: w_i = 2^(-delta_i / H)."""
    delta_days = (t_ref - run_ts.timestamp()) / 86400.0
    return 2.0 ** (-delta_days / half_life_days)


def _build_overview_payload(*, runs: list[dict], cutoff_days: int, half_life_days: int, top_n: int) -> dict:
    """Build overview payload with weighted merge using half-life decay model.
    
    Weight formula: w_i = 2^(-delta_i / H)
    where delta_i = age in days from t_ref, H = half_life_days
    """
    usable_runs: list[dict] = []
    analyses: list[dict] = []
    run_timestamps: list[float] = []

    for r in runs:
        run_path = Path(r.get("path"))
        analysis = load_analysis(run_path)
        if not analysis:
            continue
        total_jobs = int(analysis.get("total_jobs", 0) or 0)
        summary = analysis.get("summary", {}) or analysis.get("presence", {}) or {}
        if not isinstance(summary, dict) or (not summary):
            continue
        run_ts = r.get("timestamp")
        if not isinstance(run_ts, datetime):
            continue
        run_timestamps.append(run_ts.timestamp())
        usable_runs.append(
            {
                "name": str(r.get("name") or run_path.name),
                "path": str(run_path),
                "timestamp": run_ts.isoformat(),
                "job_count": int(r.get("job_count", total_jobs) or total_jobs),
                "total_jobs": total_jobs,
            }
        )
        analyses.append({"total_jobs": total_jobs, "summary": summary, "timestamp": run_ts})

    if not usable_runs:
        return {
            "generated_at": datetime.now().isoformat(),
            "runs": [],
            "meta": {
                "cutoff_days": cutoff_days,
                "half_life_days": half_life_days,
                "raw_jobs": 0,
                "effective_jobs": 0.0,
                "min_ts": None,
                "max_ts": None,
            },
            "weighted_summary": {},
            "top_terms": {},
            "series": [],
        }

    # t_ref = max timestamp among usable runs
    t_ref = max(run_timestamps)
    t_ref_dt = datetime.fromtimestamp(t_ref)
    min_ts = min(run_timestamps)
    min_ts_dt = datetime.fromtimestamp(min_ts)

    # Compute weights and weighted merge
    raw_jobs = 0
    effective_jobs = 0.0
    weighted_counts: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for analysis in analyses:
        run_ts = analysis["timestamp"]
        total_jobs = analysis["total_jobs"]
        summary = analysis["summary"]
        weight = _compute_run_weight(run_ts, t_ref, half_life_days)

        raw_jobs += total_jobs
        effective_jobs += weight * total_jobs

        for cat_key in CATEGORY_LABELS.keys():
            cat_map = summary.get(cat_key, {}) or {}
            if not isinstance(cat_map, dict):
                continue
            for term, count in cat_map.items():
                try:
                    c = int(count or 0)
                except (ValueError, TypeError):
                    c = 0
                weighted_counts[cat_key][term] += weight * c

    # Build weighted summary (weighted_pct = weighted_count / effective_jobs)
    weighted_summary: dict[str, dict[str, dict]] = {}
    for cat_key, terms_map in weighted_counts.items():
        weighted_summary[cat_key] = {}
        for term, w_count in terms_map.items():
            w_pct = (w_count / effective_jobs * 100.0) if effective_jobs > 0 else 0.0
            weighted_summary[cat_key][term] = {
                "weighted_count": round(w_count, 2),
                "weighted_pct": round(w_pct, 2),
            }

    # Decide top-N terms per category by weighted count
    top_terms_by_cat: dict[str, list[str]] = {}
    limit = max(1, int(top_n))
    for cat_key in CATEGORY_LABELS.keys():
        items = weighted_summary.get(cat_key, {})
        if not items:
            top_terms_by_cat[cat_key] = []
            continue
        ranked = sorted(items.items(), key=lambda t: t[1].get("weighted_count", 0), reverse=True)
        top_terms_by_cat[cat_key] = [str(term) for term, _ in ranked[:limit]]

    # Add weights to usable_runs for reference
    for r in usable_runs:
        ts_str = r.get("timestamp")
        if ts_str:
            try:
                run_dt = datetime.fromisoformat(ts_str)
                r["weight"] = round(_compute_run_weight(run_dt, t_ref, half_life_days), 4)
            except Exception:
                r["weight"] = 1.0

    # Build per-run time series (for delta computation and heatmaps)
    per_run_rows: list[dict] = []
    for idx, r in enumerate(usable_runs):
        run_path = Path(r["path"])
        analysis = load_analysis(run_path) or {}
        total_jobs = int(analysis.get("total_jobs", 0) or 0)
        summary = analysis.get("summary", {}) or analysis.get("presence", {}) or {}
        run_ts_str = r.get("timestamp")
        run_label = r["name"]
        run_order = idx

        for cat_key, terms in top_terms_by_cat.items():
            cat_map = (summary.get(cat_key, {}) or {}) if isinstance(summary, dict) else {}
            if not isinstance(cat_map, dict):
                continue
            for term in terms:
                count = int(cat_map.get(term, 0) or 0)
                pct = round((float(count) / float(total_jobs) * 100.0), 2) if total_jobs else 0.0
                per_run_rows.append(
                    {
                        "category": cat_key,
                        "term": term,
                        "run": run_label,
                        "run_order": run_order,
                        "timestamp": run_ts_str,
                        "count": count,
                        "pct": pct,
                        "total_jobs": total_jobs,
                    }
                )

    return {
        "generated_at": datetime.now().isoformat(),
        "runs": usable_runs,
        "meta": {
            "cutoff_days": cutoff_days,
            "half_life_days": half_life_days,
            "raw_jobs": raw_jobs,
            "effective_jobs": round(effective_jobs, 2),
            "min_ts": min_ts_dt.isoformat(),
            "max_ts": t_ref_dt.isoformat(),
        },
        "weighted_summary": weighted_summary,
        "top_terms": top_terms_by_cat,
        "series": per_run_rows,
    }


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
                st.rerun()
        
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
        st.rerun()


# ============================================================================
# Page: Reports
# ============================================================================

def render_reports_page():
    """Render the reports page."""
    _normalize_navigation_state()
    render_breadcrumb()

    if st.session_state.view_mode == "compiled_overview":
        render_compiled_overview()
        return

    if st.session_state.selected_run:
        if st.session_state.view_mode == "job_detail":
            render_job_detail_view()
        elif st.session_state.view_mode == "explorer":
            render_job_explorer()
        else:
            render_report_overview()
    else:
        render_report_list()


# ============================================================================
# Page: Overview
# ============================================================================

CUTOFF_PRESETS = [
    ("7d", 7),
    ("30d", 30),
    ("90d", 90),
    ("180d", 180),
    ("365d", 365),
]
CUTOFF_LABELS = [label for label, _ in CUTOFF_PRESETS]
CUTOFF_VALUES = {label: value for label, value in CUTOFF_PRESETS}

HALFLIFE_PRESETS = [
    ("7d", 7),
    ("14d", 14),
    ("30d", 30),
    ("60d", 60),
    ("90d", 90),
]
HALFLIFE_LABELS = [label for label, _ in HALFLIFE_PRESETS]
HALFLIFE_VALUES = {label: value for label, value in HALFLIFE_PRESETS}


def _render_market_context_bars(weighted_summary: dict, effective_jobs: float) -> None:
    """Render market context (support levels + work arrangements) as progress bars."""
    st.subheader("📊 Market Context")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Support Levels**")
        support_data = weighted_summary.get("support_levels", {})
        if support_data:
            # Sort by weighted_pct descending
            sorted_items = sorted(support_data.items(), key=lambda x: x[1].get("weighted_pct", 0), reverse=True)
            for term, data in sorted_items[:6]:
                pct = data.get("weighted_pct", 0)
                st.progress(min(pct / 100.0, 1.0), text=f"{term}: {pct:.1f}%")
        else:
            st.caption("No support level data available.")

    with col2:
        st.markdown("**Work Arrangements**")
        work_data = weighted_summary.get("work_arrangements", {})
        if work_data:
            sorted_items = sorted(work_data.items(), key=lambda x: x[1].get("weighted_pct", 0), reverse=True)
            for term, data in sorted_items[:6]:
                pct = data.get("weighted_pct", 0)
                st.progress(min(pct / 100.0, 1.0), text=f"{term}: {pct:.1f}%")
        else:
            st.caption("No work arrangement data available.")


def _render_category_snapshot(
    cat_key: str,
    cat_label: str,
    weighted_summary: dict,
    top_terms: list[str],
    series: list[dict] | None = None,
) -> None:
    """Render a category as a simple snapshot table.

    `series` is accepted for forward-compatibility (some callers pass it) but is
    not currently used by the table snapshot view.
    """
    cat_data = weighted_summary.get(cat_key, {})
    if not cat_data or not top_terms:
        return

    with st.expander(cat_label, expanded=False):
        table_data = []
        for term in top_terms:
            item = cat_data.get(term, {})
            w_pct = item.get("weighted_pct", 0)
            w_count = item.get("weighted_count", 0)
            table_data.append(
                {
                    "Term": term,
                    "Weighted %": f"{w_pct:.1f}%",
                    "W.Count": f"{w_count:.1f}",
                }
            )
        df_table = pd.DataFrame(table_data)
        st.dataframe(df_table, use_container_width=True, hide_index=True)
        st.caption(f"Top {len(top_terms)} shown by weighted count.")


def render_overview_page():
    """Render weighted statistical overview across runs."""
    render_breadcrumb()
    st.header("📈 Overview")

    runs = list_runs()
    if not runs:
        st.info("No reports found yet. Start a new run to generate data.")
        return

    # ─────────────────────────────────────────────────────────────────────────
    # Controls
    # ─────────────────────────────────────────────────────────────────────────
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

    btn_col1, btn_col2 = st.columns([1, 1])
    with btn_col1:
        generate = st.button("🔄 Generate / Update", type="primary", use_container_width=True)
    with btn_col2:
        params = _overview_params(cutoff_days, half_life_days, int(top_n))
        cache_file = _overview_cache_file(params)
        cached = _load_overview_cache(cache_file)
        export_disabled = (not cached) or (cached.get("params") != params)
        export_now = st.button(
            "💾 Export files",
            disabled=export_disabled,
            use_container_width=True,
            help="Writes JSON + CSV + Markdown to outputs/.",
        )

    # One-shot notices
    notice = st.session_state.get("overview_notice")
    if isinstance(notice, str) and notice:
        st.success(notice)
        st.session_state.overview_notice = None

    if generate:
        selected_runs = _runs_within_cutoff(runs, cutoff_days)
        payload = _build_overview_payload(
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
    # Summary Metrics Block
    # ─────────────────────────────────────────────────────────────────────────
    st.subheader("📋 Window Summary")
    runs_count = len(runs_used)
    raw_jobs = int(meta.get("raw_jobs", 0) or 0)
    effective_jobs = float(meta.get("effective_jobs", 0) or 0)
    min_ts = meta.get("min_ts", "")
    max_ts_display = meta.get("max_ts", "")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Runs", runs_count)
    m2.metric("Raw jobs", f"{raw_jobs:,}")
    m3.metric("Effective jobs", f"{effective_jobs:,.0f}")
    if min_ts and max_ts_display:
        span = f"{min_ts[:10]} → {max_ts_display[:10]}"
    else:
        span = "—"
    m4.metric("Span", span)

    st.caption(f"Cutoff: {cutoff_days}d | Half-life: {half_life_days}d | Top N: {top_n}")
    gen_at = cached.get("generated_at")
    if gen_at:
        st.caption(f"Generated: {gen_at}")

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────────
    # Market Context (support levels + work arrangements)
    # ─────────────────────────────────────────────────────────────────────────
    _render_market_context_bars(weighted_summary, effective_jobs)

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────────
    # Category Snapshots (tables default, with view toggle)
    # ─────────────────────────────────────────────────────────────────────────
    st.subheader("📁 Category Snapshots")

    # Exclude market context categories (already shown above)
    skip_cats = {"support_levels", "work_arrangements"}
    for cat_key, cat_label in CATEGORY_LABELS.items():
        if cat_key in skip_cats:
            continue
        cat_terms = top_terms.get(cat_key) or []
        if not cat_terms:
            continue
        _render_category_snapshot(cat_key, cat_label, weighted_summary, cat_terms, series)

    st.markdown("---")

    # ─────────────────────────────────────────────────────────────────────────
    # AI Summary (collapsed)
    # ─────────────────────────────────────────────────────────────────────────
    with st.expander("🤖 AI Summary (Interpretation)", expanded=False):
        # Build AI input from weighted summary
        # Convert weighted_summary to simple counts for AI input
        simple_summary = {}
        for cat_key, terms_map in weighted_summary.items():
            simple_summary[cat_key] = {term: int(data.get("weighted_count", 0)) for term, data in terms_map.items()}

        ai_input = _build_ai_summary_input(
            total_jobs=int(effective_jobs),
            summary=simple_summary,
            search_context={
                "window": f"Last {cutoff_days} days (half-life {half_life_days}d)",
                "runs": [r.get("name") for r in runs_used],
            },
            scope_label=f"overview_{cutoff_days}d_hl{half_life_days}d",
            top_n_per_category=int(top_n),
        )
        ai_cache = OVERVIEW_DIR / f"ai_{_hash_payload(params)[:16]}.json"
        _render_ai_summary_block(cache_path=ai_cache, ai_input=ai_input, auto_generate=False)


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

    ai_input = _build_ai_text_payload(
        analysis_text=combined_txt,
        meta={
            "scope": "compiled",
            "runs": [p.name for p in run_paths],
            "search_terms": search_pairs,
            "total_jobs": int(total_jobs or 0),
            "companies": int(unique_companies or 0),
            "compiled_reports": int(len(run_paths)),
        },
    )
    compiled_key = hashlib.sha256("|".join(sorted(p.name for p in run_paths)).encode("utf-8")).hexdigest()[:16]
    cache_path = STATE_DIR / f"compiled_ai_summary_{compiled_key}.json"
    _render_ai_summary_block(cache_path=cache_path, ai_input=ai_input)

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



def render_report_overview():
    """Render the overview of a selected report with charts."""
    run_path = Path(st.session_state.selected_run)
    analysis = load_analysis(run_path)
    
    st.header(f"📊 Report Overview")
    
    if not analysis:
        st.warning("No analysis data found for this report. Run analysis first.")
        return
    
    summary = analysis.get("summary", {}) or analysis.get("presence", {})
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
    
    with st.container(border=True):
        c1, c2 = st.columns([0.7, 0.3], vertical_alignment="center")
        with c1:
            st.markdown("### 🔎 Explore matched jobs")
            st.caption("Filter, open source links, and review which requirements triggered matches.")
        with c2:
            if st.button("Open Job Explorer", type="primary", use_container_width=True):
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

    # AI summary (single report)
    keywords, location = _get_run_search_meta(run_path)
    txt = load_requirements_analysis_txt(run_path)
    if txt and txt.strip():
        ai_input = _build_ai_text_payload(
            analysis_text=_truncate_text(
                txt.strip(),
                max_chars=80_000,
                suffix="\n\n[TRUNCATED: requirements_analysis.txt exceeded limit]",
            ),
            meta={
                "scope": "single",
                "run": run_path.name,
                "keywords": keywords,
                "location": location,
                "total_jobs": int(total_jobs or 0),
                "companies": int(unique_companies or 0),
            },
        )
    else:
        # Fallback for older runs missing requirements_analysis.txt
        ai_input = _build_ai_summary_input(
            total_jobs=total_jobs,
            summary=summary,
            search_context={
                "run": run_path.name,
                "keywords": keywords,
                "location": location,
            },
            scope_label="single",
            top_n_per_category=AI_SUMMARY_TOP_N_SINGLE,
        )
    cache_path = run_path / "ai_summary.json"
    _render_ai_summary_block(cache_path=cache_path, ai_input=ai_input)

    st.markdown("---")
    
    # Category charts in expanders with clickable requirements
    for category_key, category_label in CATEGORY_LABELS.items():
        data = summary.get(category_key, {})
        if not data:
            continue
        
        # Keep expander expanded if there's an active selection in this category
        has_selection = bool(st.session_state.get(f"report_selected_term_{category_key}"))
        
        with st.expander(f"{category_label} ({len(data)} items)", expanded=has_selection):
            # Prepare data for chart
            sorted_items_full = sorted(data.items(), key=lambda x: x[1], reverse=True)
            sorted_items = sorted_items_full[:15]  # Top 15
            df = pd.DataFrame([
                {"term": term, "count": count, "percentage": (count / total_jobs * 100) if total_jobs > 0 else 0}
                for term, count in sorted_items
            ])

            df_full = pd.DataFrame([
                {"term": term, "count": count, "percentage": (count / total_jobs * 100) if total_jobs > 0 else 0}
                for term, count in sorted_items_full
            ])
            
            if not df.empty:
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
                    key=f"report_table_{category_key}",
                )

                selected_rows = []
                try:
                    selected_rows = (table_state.selection.rows or []) if table_state and table_state.selection else []
                except Exception:
                    selected_rows = []
                selected_term_key = f"report_selected_term_{category_key}"
                if selected_rows:
                    row_idx = selected_rows[0]
                    if 0 <= row_idx < len(df):
                        st.session_state[selected_term_key] = str(df.iloc[row_idx]["term"])

                selected_term = st.session_state.get(selected_term_key)
                if selected_term and st.button(
                    "View matching jobs",
                    type="primary",
                    use_container_width=True,
                    key=f"report_view_jobs_{category_key}",
                ):
                    navigate_to(
                        "reports",
                        selected_run=st.session_state.selected_run,
                        view_mode="explorer",
                        viewing_job_id=None,
                        selected_filters={category_key: [selected_term]},
                        filter_mode="any",
                        search_text="",
                    )
                    st.rerun()

                if len(sorted_items_full) > 15 and st.button(
                    "⤢ Expand list",
                    use_container_width=True,
                    key=f"report_expand_{category_key}",
                ):
                    if hasattr(st, "dialog"):
                        @st.dialog(f"{category_label} — All Items")
                        def _show_report_full_table(cat_key: str, df_all: pd.DataFrame):
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
                                key=f"report_table_full_{cat_key}",
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
                            selected_term_key_full = f"report_selected_term_full_{cat_key}"
                            if selected_rows_full:
                                row_idx_full = selected_rows_full[0]
                                if 0 <= row_idx_full < len(df_all):
                                    st.session_state[selected_term_key_full] = str(df_all.iloc[row_idx_full]["term"])

                            selected_term_full = st.session_state.get(selected_term_key_full)
                            if selected_term_full and st.button(
                                "View matching jobs",
                                type="primary",
                                use_container_width=True,
                                key=f"report_view_jobs_full_{cat_key}",
                            ):
                                navigate_to(
                                    "reports",
                                    selected_run=st.session_state.selected_run,
                                    view_mode="explorer",
                                    viewing_job_id=None,
                                    selected_filters={cat_key: [selected_term_full]},
                                    filter_mode="any",
                                    search_text="",
                                )
                                st.rerun()

                        _show_report_full_table(category_key, df_full)
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
                                key=f"report_table_full_{category_key}",
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
                            selected_term_key_full = f"report_selected_term_full_{category_key}"
                            if selected_rows_full:
                                row_idx_full = selected_rows_full[0]
                                if 0 <= row_idx_full < len(df_full):
                                    st.session_state[selected_term_key_full] = str(df_full.iloc[row_idx_full]["term"])

                            selected_term_full = st.session_state.get(selected_term_key_full)
                            if selected_term_full and st.button(
                                "View matching jobs",
                                type="primary",
                                use_container_width=True,
                                key=f"report_view_jobs_full_{category_key}",
                            ):
                                navigate_to(
                                    "reports",
                                    selected_run=st.session_state.selected_run,
                                    view_mode="explorer",
                                    viewing_job_id=None,
                                    selected_filters={category_key: [selected_term_full]},
                                    filter_mode="any",
                                    search_text="",
                                )
                                st.rerun()


def render_job_explorer():
    """Render the job explorer with tag filtering."""
    run_path = Path(st.session_state.selected_run)
    analysis = load_analysis(run_path)
    jobs_df = load_jobs_csv(run_path)
    
    st.header("🔍 Job Explorer")
    
    if not analysis or jobs_df is None:
        st.warning("Missing data for job exploration.")
        return

    # Calculate posting dates for sorting
    posting_dates = {}
    for idx in range(len(jobs_df)):
        job_row = jobs_df.iloc[idx]
        date_value = job_row.get("date_posted")
        if pd.notna(date_value) and date_value:
            try:
                # Extract scraping date from folder name (format: ..._YYYYMMDD_HHMMSS)
                folder_name = run_path.name
                date_match = re.search(r'_(\d{8})_', folder_name)
                if date_match:
                    scrape_date_str = date_match.group(1)
                    scrape_date = datetime.strptime(scrape_date_str, "%Y%m%d")
                    
                    # Parse date_posted (e.g., "2d ago", "1w ago")
                    days_ago = 0
                    if "d ago" in date_value:
                        days_ago = int(re.search(r'(\d+)d ago', date_value).group(1))
                    elif "w ago" in date_value:
                        days_ago = int(re.search(r'(\d+)w ago', date_value).group(1)) * 7
                    elif "h ago" in date_value:
                        hours_ago = int(re.search(r'(\d+)h ago', date_value).group(1))
                        days_ago = hours_ago // 24
                    
                    posting_date = scrape_date - pd.Timedelta(days=days_ago)
                    posting_dates[idx + 1] = posting_date  # job_id is 1-indexed
            except (ValueError, AttributeError):
                pass
    
    # Sort jobs by most recent date (newest first)
    reverse_sort = True
    
    def _job_sort_key(job_id: int):
        dt = posting_dates.get(job_id)
        if dt is None:
            return datetime.min if reverse_sort else datetime.max  # Unknown dates at end
        return dt
    
    # Get job data from analysis (for requirements)
    job_details = {j["id"]: j for j in analysis.get("job_details", [])}
    
    # Apply filters to get matching jobs
    all_selected_terms = []
    for cat, terms in st.session_state.selected_filters.items():
        for term in terms:
            all_selected_terms.append((cat, term))
    
    # Build job matching results
    job_matches = {}  # job_id -> set of matched (cat, term) tuples
    
    for job_id, job_data in job_details.items():
        reqs = job_data.get("requirements", {})
        presence_reqs = reqs.get("presence", {}) if isinstance(reqs, dict) else reqs
        matched = set()
        
        for cat, term in all_selected_terms:
            if term in presence_reqs.get(cat, []):
                matched.add((cat, term))
        
        if matched or not all_selected_terms:
            job_matches[job_id] = matched
    
    # Filter by search text
    if st.session_state.search_text:
        search_lower = st.session_state.search_text.lower()
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
    
    # Display active filters summary
    active_filters = []
    for cat, terms in st.session_state.selected_filters.items():
        for term in terms:
            active_filters.append((cat, term))
    if active_filters or st.session_state.search_text:
        col1, col2 = st.columns([3,1])
        with col1:
            filter_text = []
            if st.session_state.search_text:
                filter_text.append(f"🔎 {st.session_state.search_text}")
            for cat, term in active_filters:
                cat_label = CATEGORY_LABELS.get(cat, cat)
                filter_text.append(f"{cat_label}: {term}")
            if filter_text:
                st.caption("Active filters: " + " | ".join(filter_text))
        with col2:
            if st.button("Clear All", key="clear_filters_main"):
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
                days_ago_text = ""
                if job_row is not None:
                    date_value = job_row.get("date_posted")
                    if pd.notna(date_value) and date_value:
                        date_text = str(date_value)
                        # Calculate days ago
                        try:
                            # Extract scraping date from folder name (format: ..._YYYYMMDD_HHMMSS)
                            folder_name = run_path.name
                            date_match = re.search(r'_(\d{8})_', folder_name)
                            if date_match:
                                scrape_date_str = date_match.group(1)
                                scrape_date = datetime.strptime(scrape_date_str, "%Y%m%d")
                                
                                # Parse date_posted (e.g., "2d ago", "1w ago")
                                days_ago = 0
                                if "d ago" in date_value:
                                    days_ago = int(re.search(r'(\d+)d ago', date_value).group(1))
                                elif "w ago" in date_value:
                                    days_ago = int(re.search(r'(\d+)w ago', date_value).group(1)) * 7
                                elif "h ago" in date_value:
                                    hours_ago = int(re.search(r'(\d+)h ago', date_value).group(1))
                                    days_ago = hours_ago // 24
                                
                                posting_date = scrape_date - pd.Timedelta(days=days_ago)
                                actual_days_ago = (datetime.now() - posting_date).days
                                if actual_days_ago == 0:
                                    days_ago_text = " (today)"
                                elif actual_days_ago == 1:
                                    days_ago_text = " (1 day ago)"
                                else:
                                    days_ago_text = f" ({actual_days_ago} days ago)"
                        except (ValueError, AttributeError):
                            pass  # Keep days_ago_text empty if parsing fails

                col1, col2, col3 = st.columns([0.25, 3, 1])

                with col1:
                    if days_ago_text:
                        st.caption(f"🕒{days_ago_text.strip(' ()')}")
                    elif date_text:
                        st.caption(f"📅 {date_text}")

                with col2:
                    if st.button(f"{title} — {company}", key=f"job_title_{job_id}"):
                        navigate_to(
                            "reports",
                            selected_run=st.session_state.selected_run,
                            view_mode="job_detail",
                            viewing_job_id=job_id,
                        )
                        st.rerun()

                with col3:
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
        _normalize_navigation_state()
        st.session_state.last_url_state = current_url_state

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

    # Keep URL in sync with final state.
    _sync_url_with_state()
    st.session_state.last_url_state = str(_get_query_params())


if __name__ == "__main__":
    main()
