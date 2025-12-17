import re
import hashlib
from ui_core import _stable_json_dumps


def split_tldr(md: str):
    """
    Extract the TL;DR section (## TL;DR ...) and return (tldr_md, rest_md).
    Safe no-op if TL;DR not present.
    """
    if not md:
        return "", ""

    # Match any H2 or H3 line that begins with "TL;DR" (handles em-dash, en-dash, colon, etc.)
    m = re.search(r"(?ms)^#{2,3}\s+TL;DR[^\n]*\n.*?(?=^##\s+|\Z)", md)
    if not m:
        return "", md

    tldr = m.group(0).strip()
    rest = (md[:m.start()] + md[m.end():]).strip()
    return tldr, rest


def _truncate_text(text: str, *, max_chars: int, suffix: str) -> str:
    if not isinstance(text, str):
        return ""
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def _hash_payload(payload) -> str:
    raw = _stable_json_dumps(payload).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()