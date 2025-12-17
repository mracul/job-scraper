# --- AI Summary UI Block ---
def _render_ai_summary_block(*, cache_path: Path, ai_input: dict, auto_generate: bool = True) -> None:
    import hashlib, re
    from datetime import datetime
    # ===== SETTINGS / HASH BASIS =====
    from .streamlit_app import load_settings, _stable_json_dumps
    settings = load_settings()
    ai_model = settings.get("ai", {}).get("model", "gpt-5-mini")

    cache_basis = {
        "ai_input": ai_input,
        "model": ai_model,
        "max_output_tokens": AI_SUMMARY_MAX_OUTPUT_TOKENS,
        "system_prompt": AI_SUMMARY_SYSTEM_PROMPT,
    }

    from ai_summary_core import _load_cached_ai_summary, _save_cached_ai_summary, _hash_payload
    cached = _load_cached_ai_summary(cache_path)
    input_hash = _hash_payload(cache_basis)

    # ===== CACHE STATE (single source of truth) =====
    cached_text = None
    cache_status = None  # "current" | "outdated" | None

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

    def split_tldr(md: str):
        if not md:
            return "", ""
        m = re.search(r"(?ms)^#{2,3}\s+TL;DR[^\n]*\n.*?(?=^##\s+|\Z)", md)
        if not m:
            return "", md
        tldr = m.group(0).strip()
        rest = (md[:m.start()] + md[m.end():]).strip()
        return tldr, rest

    def render_markdown_scroll(md: str, *, height_px: int = 260) -> None:
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
  padding: 0.25rem 0;
  background: transparent;
  border: 0;
  border-radius: 0;
  box-shadow: none;
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
            b1, b2, b3 = st.columns(3)

            # 1) Generate / Reset (pulses while generating)
            with b1:
                pulse_class = "ai-pulse-button" if is_generating else ""
                st.markdown(f"<div class='{pulse_class}'>", unsafe_allow_html=True)

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
                disabled = not bool(cached_text)
                if st.button(
                    "🗑️",
                    use_container_width=True,
                    key=f"clr_{cache_path.name}_{input_hash[:8]}",
                    help="Clear cached summary",
                    disabled=disabled,
                ):
                    try:
                        cache_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                    st.rerun()

            # 3) Expand
            with b3:
                disabled = not bool(summary_text)
                if st.button(
                    "⤢",
                    use_container_width=True,
                    key=f"exp_{cache_path.name}_{input_hash[:8]}",
                    help="Expand AI summary",
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

        # Body (NO st.info; TL;DR shown if present)
        if summary_text:
            tldr_md, rest_md = split_tldr(summary_text)
            if tldr_md:
                st.markdown(tldr_md)
                st.markdown("---")
            render_markdown_scroll(rest_md, height_px=260)
        else:
            st.markdown("_No summary yet._")

    st.markdown("</div>", unsafe_allow_html=True)
from pathlib import Path
import time
import streamlit as st
from markdown import markdown as md_to_html

from ai_summary_core import (
    AI_SUMMARY_SYSTEM_PROMPT,
    AI_SUMMARY_MAX_OUTPUT_TOKENS,
    _load_cached_ai_summary,
    _save_cached_ai_summary,
    compute_input_hash,
    resolve_cache_state,
)

# UI-only constants
AI_MAX_N = 50
AI_MAX_COMPILED_N = 75


def _fallback_summary_from_input(ai_input: dict) -> str:
    """Simple fallback when AI generation fails - just show error message."""
    total_jobs = ai_input.get("total_jobs", 0)
    return (
        f"⚠️ **AI summary generation failed.** Unable to analyze {total_jobs} job listings.\n\n"
        "Please check your OpenAI API key in Settings or try again later."
    )

def _generate_ai_summary_text(ai_input: dict) -> str:
    import requests, time
    from .streamlit_app import load_settings, _stable_json_dumps
    api_key = None
    try:
        from .streamlit_app import _get_openai_api_key
        api_key = _get_openai_api_key()
    except Exception:
        pass
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
    last_error = None
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
    parts = []
    for out in data.get("output", []) or []:
        for content in out.get("content", []) or []:
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(content.get("text"))
    text = "".join(parts).strip()
    if not text:
        text = (data.get("output_text") or "").strip()
    if not text:
        text = _fallback_summary_from_input(ai_input)
    return text
