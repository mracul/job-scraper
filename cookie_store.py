"""Cookie persistence helpers for Selenium sessions.

Purpose:
- Allow manual, interactive login once (if a site requires it), then persist cookies.
- Reuse cookies in future runs to reduce auth prompts and access more pages.

Notes:
- Cookies can expire. If scraping starts failing or you get redirected to sign-in,
  delete the cookie file and log in again.
- This stores cookies locally as JSON. Treat the file as sensitive.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable


def _normalize_cookie(cookie: dict[str, Any]) -> dict[str, Any]:
    """Return a Selenium cookie dict with only serializable fields."""
    # Selenium accepts many keys; we'll store common ones.
    allowed = {
        "name",
        "value",
        "domain",
        "path",
        "expiry",
        "secure",
        "httpOnly",
        "sameSite",
    }
    return {k: cookie[k] for k in cookie.keys() & allowed}


def save_cookies(driver, cookie_path: os.PathLike | str) -> None:
    path = Path(cookie_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    cookies: Iterable[dict[str, Any]] = driver.get_cookies()
    data = [_normalize_cookie(c) for c in cookies]

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_cookies(driver, cookie_path: os.PathLike | str, base_url: str) -> bool:
    """Load cookies into driver.

    Returns True if cookies were loaded.
    """
    path = Path(cookie_path)
    if not path.exists():
        return False

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False

    if not isinstance(data, list):
        return False

    def _domain_to_url(domain: str) -> str:
        host = (domain or "").lstrip(".")
        if not host:
            return base_url
        return f"https://{host}/"

    # Group cookies by their declared domain; Cloudflare clearance cookies often use a parent domain.
    cookies_by_domain: dict[str, list[dict[str, Any]]] = {}
    for cookie in data:
        if not isinstance(cookie, dict):
            continue
        domain = str(cookie.get("domain") or "")
        cookies_by_domain.setdefault(domain, []).append(cookie)

    loaded_any = False

    # Add cookies domain-by-domain to avoid Selenium domain mismatch rejections.
    # Always try base_url domain first, then any others.
    ordered_domains: list[str] = []
    try:
        from urllib.parse import urlparse

        base_host = (urlparse(base_url).hostname or "")
        if base_host:
            ordered_domains.append(base_host)
    except Exception:
        pass

    # Append remaining cookie domains
    for d in cookies_by_domain.keys():
        if d and d.lstrip(".") not in ordered_domains:
            ordered_domains.append(d)

    # Ensure we have at least one navigation target
    if not ordered_domains:
        ordered_domains = [""]

    for domain in ordered_domains:
        try:
            driver.get(_domain_to_url(domain))
        except Exception:
            # If navigation fails, fall back to base_url
            try:
                driver.get(base_url)
            except Exception:
                pass

        for cookie in cookies_by_domain.get(domain, []):
            try:
                driver.add_cookie(cookie)
                loaded_any = True
            except Exception:
                # Some cookies can fail if domain mismatch or expired format
                continue

    if loaded_any:
        try:
            driver.get(base_url)
        except Exception:
            pass
    return loaded_any
