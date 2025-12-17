from pathlib import Path
import time
import streamlit as st
import os
import requests
import re
from markdown import markdown as md_to_html

from ai_summary_core import (
    AI_SUMMARY_SYSTEM_PROMPT,
    AI_SUMMARY_MAX_OUTPUT_TOKENS,
    compute_input_hash,
    resolve_cache_state,
)
from ui.io_cache import _load_cached_ai_summary, _save_cached_ai_summary
from ui.utils import split_tldr
from ui_core import load_settings, _stable_json_dumps

# UI-only constants
AI_MAX_N = 50
AI_MAX_COMPILED_N = 75

def _dedent_accidental_codeblocks(md: str) -> str:
    """
    Remove leading 4 spaces that cause unintended markdown code blocks.
    Does NOT alter fenced code blocks ```...```.
    """
    if not md:
        return md

    out = []
    in_fence = False
    for line in md.splitlines():
        if re.match(r"^\s*```", line):
            in_fence = not in_fence
            out.append(line)
            continue

        if not in_fence and line.startswith("    "):
            out.append(line[4:])  # remove 4 leading spaces
        else:
            out.append(line)

    return "\n".join(out)

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

# --- AI Summary UI Block ---
def render_ai_summary_block(*, cache_path: Path, ai_input: dict, auto_generate: bool = True) -> None:
    import hashlib, re
    from datetime import datetime
    # ===== SETTINGS / HASH BASIS =====
    from ui_core import load_settings
    settings = load_settings()
    ai_model = settings.get("ai", {}).get("model", "gpt-5-mini")

    from ai_summary_core import _load_cached_ai_summary, _save_cached_ai_summary
    cached = _load_cached_ai_summary(cache_path)
    input_hash = compute_input_hash(ai_input, ai_model, AI_SUMMARY_MAX_OUTPUT_TOKENS, AI_SUMMARY_SYSTEM_PROMPT)

    # ===== CACHE STATE (single source of truth) =====
    cached_text, cache_status = resolve_cache_state(cached, input_hash)

    auto_key = f"ai_auto_{cache_path.name}_{input_hash[:8]}"
    inflight_key = f"ai_inflight_{cache_path.name}_{input_hash[:8]}"
    inflight_started_key = f"ai_inflight_started_{cache_path.name}_{input_hash[:8]}"

    summary_text = cached_text

    # ===== HELPERS =====
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

    def render_markdown_scroll(md: str, *, height_px: int = 260) -> None:
        md = _dedent_accidental_codeblocks(md or "")
        html = md_to_html(
            md or "_No further details._",
            extensions=["extra", "tables", "sane_lists", "nl2br"],
        )
        st.markdown(
            f"<div class='ai-scroll' style='max-height:{height_px}px'>{html}</div>",
            unsafe_allow_html=True,
        )

    # ===== AUTO-CLEAR STUCK INFLIGHT =====
    try:
        inflight_started = st.session_state.get(inflight_started_key)
        if st.session_state.get(inflight_key) and isinstance(inflight_started, (int, float)):
            import time
            if (time.time() - float(inflight_started)) > 300:
                st.session_state[inflight_key] = False
                st.session_state.pop(inflight_started_key, None)
    except Exception:
        pass

    # ===== AUTO GENERATE (keeps your behavior) =====
    if auto_generate and (not cached_text) and (not st.session_state.get(auto_key)):
        import time
        st.session_state[auto_key] = True
        st.session_state[inflight_key] = True
        st.session_state[inflight_started_key] = time.time()
        try:
            summary_text = _generate_ai_summary_text(ai_input)
            _save(summary_text)
            st.session_state[inflight_key] = False
            st.session_state.pop(inflight_started_key, None)
            st.rerun()  # no return needed after rerun
        except Exception as exc:
            st.session_state[inflight_key] = False
            st.session_state.pop(inflight_started_key, None)
            st.error(str(exc))
            summary_text = None

    # ===== CSS (ALWAYS injected once; not inside if-branches) =====
    if not st.session_state.get("_ai_summary_css_injected"):
        st.session_state["_ai_summary_css_injected"] = True
        st.markdown(r"""
<style>
/* ===== Pulse animation ===== */
@keyframes pulseGlow {
  0%   { box-shadow: 0 0 0 0 rgba(255,255,255,0.10); }
  50%  { box-shadow: 0 0 0 4px rgba(255,255,255,0.06); }
  100% { box-shadow: 0 0 0 0 rgba(255,255,255,0.10); }
}

/* Card pulse wrapper */
.ai-summary.pulsing {
  animation: pulseGlow 1.2s ease-in-out infinite;
  border-radius: 12px;
}

/* Button pulse */
.ai-pulse-button button {
  animation: pulseGlow 1.2s ease-in-out infinite;
}

/* Button polish */
div.stButton > button {
  height: 2.3rem;
  border-radius: 10px;
  padding: 0.1rem 0.4rem;
}

/* Scroll container: hard wrap + never exceed width */
.ai-summary .ai-scroll{
  max-height: 260px;
  overflow: auto;
  max-width: 100%;
  width: 100%;

  /* prevent margin-collapsing + stop headings "floating" upward */
  display: flow-root;

  /* give content a tiny top/bottom buffer */
  padding: 0.5rem 0;

  background: transparent;
  border: 0;
  border-radius: 0;
  box-shadow: none;
}

/* tame markdown heading spacing inside scroll container */
.ai-summary .ai-scroll h1,
.ai-summary .ai-scroll h2,
.ai-summary .ai-scroll h3,
.ai-summary .ai-scroll h4{
  margin: 0.6rem 0 0.25rem 0;
  line-height: 1.15;
}

/* ensure first element doesn't add extra top gap */
.ai-summary .ai-scroll > :first-child{
  margin-top: 0 !important;
}

.ai-summary .ai-scroll,
.ai-summary .ai-scroll *{
  max-width: 100% !important;
  box-sizing: border-box !important;
  white-space: normal !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}

/* Tables: contain them */
.ai-summary .ai-scroll table{
  display: block !important;
  width: 100% !important;
  max-width: 100% !important;
  overflow-x: auto !important;
  border-collapse: collapse;
}
.ai-summary .ai-scroll th,
.ai-summary .ai-scroll td{
  max-width: 24rem;
  white-space: normal !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}

/* Code blocks: wrap too */
.ai-summary .ai-scroll pre,
.ai-summary .ai-scroll code{
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
  word-break: break-word !important;
}

/* === AI SUMMARY MARKDOWN HARDENING === */
.ai-summary h1,
.ai-summary h2,
.ai-summary h3,
.ai-summary h4{
  margin-top: 1rem !important;
  margin-bottom: 0.4rem !important;
  line-height: 1.15;
}

/* Never allow headings to overlap previous content */
.ai-summary h1::before,
.ai-summary h2::before,
.ai-summary h3::before{
  content: "";
  display: block;
  height: 0;
  margin-top: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

    # ===== UI (ONE card ONLY; no duplicates) =====
    is_generating = bool(st.session_state.get(inflight_key))
    wrapper_class = "ai-summary pulsing" if is_generating else "ai-summary"
    st.markdown(f"<div class='{wrapper_class}'>", unsafe_allow_html=True)

    with st.container(border=True):
        left, right = st.columns([0.72, 0.28], vertical_alignment="center")

        with left:
            status = "• —"
            if is_generating:
                status = "• ⏳ generating"
            elif cache_status == "current":
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
            b1, b2, b3 = st.columns(3, vertical_alignment="center")

            # 1) Generate / Reset (pulses while generating)
            with b1:
                pulse_class = "ai-pulse-button" if is_generating else ""
                st.markdown(
                    f"<div class='{pulse_class}' style='display:flex;align-items:center;justify-content:center;height:100%;'>",
                    unsafe_allow_html=True
                )

                if is_generating:
                    if st.button(
                        "🔄",
                        use_container_width=True,
                        key=f"reset_{cache_path.name}_{input_hash[:8]}",
                        help="Reset stuck generation",
                    ):
                        st.session_state[inflight_key] = False
                        st.session_state.pop(inflight_started_key, None)
                        st.session_state[auto_key] = False
                        st.rerun()
                else:
                    label = "Generate" if not summary_text else "Regenerate"
                    if st.button(
                        "✨",
                        use_container_width=True,
                        key=f"gen_{cache_path.name}_{input_hash[:8]}",
                        help=f"{label} AI summary",
                    ):
                        import time
                        st.session_state[auto_key] = False
                        st.session_state[inflight_key] = True
                        st.session_state[inflight_started_key] = time.time()
                        try:
                            summary_text = _generate_ai_summary_text(ai_input)
                            _save(summary_text)
                            st.session_state[inflight_key] = False
                            st.session_state.pop(inflight_started_key, None)
                            st.rerun()
                        except Exception as e:
                            st.session_state[inflight_key] = False
                            st.session_state.pop(inflight_started_key, None)
                            st.error(str(e))

                st.markdown("</div>", unsafe_allow_html=True)

            # 2) Clear cache
            with b2:
                st.markdown(
                    "<div style='display:flex;align-items:center;justify-content:center;height:100%;'>",
                    unsafe_allow_html=True
                )
                disabled = not bool(cached_text)
                if st.button(
                    "🗑️",
                    use_container_width=True,
                    key=f"del_{cache_path.name}_{input_hash[:8]}",
                    help="Delete cached summary",
                    disabled=disabled,
                ):
                    try:
                        cache_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            # 3) Expand
            with b3:
                st.markdown(
                    "<div style='display:flex;align-items:center;justify-content:center;height:100%;'>",
                    unsafe_allow_html=True
                )
                disabled = not bool(summary_text)
                if st.button(
                    "⤢",
                    use_container_width=True,
                    key=f"expand_{cache_path.name}_{input_hash[:8]}",
                    help="Toggle expanded view",
                    disabled=disabled,
                ):
                    if hasattr(st, "dialog"):
                        @st.dialog("🤖 AI Summary")
                        def _show_ai_summary_dialog(text: str):
                            st.markdown(text)
                        _show_ai_summary_dialog(summary_text or "")
                    else:
                        with st.expander("AI Summary (expanded)", expanded=True):
                            st.markdown(summary_text or "")
                st.markdown("</div>", unsafe_allow_html=True)

        # Body (NO st.info; TL;DR shown if present)
        if summary_text:
            tldr_md, rest_md = split_tldr(summary_text)
            if tldr_md:
                render_markdown_scroll(tldr_md, height_px=100)
                st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
            render_markdown_scroll(rest_md, height_px=260)
        else:
            st.markdown("_No summary yet._")

    st.markdown("</div>", unsafe_allow_html=True)
