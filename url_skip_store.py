"""Simple JSON-based store for tracking seen job URLs.

Used to skip already-scraped job listings across runs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Set

DEFAULT_STORE_PATH = Path(__file__).parent / "seen_urls.json"


def load_seen_urls(path: os.PathLike | str | None = None) -> Set[str]:
    """Load the set of previously seen job URLs from JSON.

    If the file doesn't exist or is invalid, returns an empty set.
    """
    store_path = Path(path) if path is not None else DEFAULT_STORE_PATH
    if not store_path.exists():
        return set()

    try:
        with store_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return set(str(u) for u in data)
        return set()
    except Exception:
        # Corrupt or unreadable file – fail soft and start fresh
        return set()


def save_seen_urls(urls: Iterable[str], path: os.PathLike | str | None = None) -> None:
    """Persist the set/list of URLs to JSON.

    Overwrites the file atomically where possible.
    """
    store_path = Path(path) if path is not None else DEFAULT_STORE_PATH
    store_path.parent.mkdir(parents=True, exist_ok=True)

    urls_list = sorted(set(str(u) for u in urls))

    tmp_path = store_path.with_suffix(store_path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(urls_list, f, indent=2)
    tmp_path.replace(store_path)


def add_urls(new_urls: Iterable[str], path: os.PathLike | str | None = None) -> None:
    """Convenience helper: load, update, save in one call."""
    seen = load_seen_urls(path)
    seen.update(str(u) for u in new_urls)
    save_seen_urls(seen, path)
