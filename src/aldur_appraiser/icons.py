"""Base-currency icon for the inline overlay (e.g. the Exalted Orb image).

The inline chips show a value as "<n> [base-icon]". We need just the one base
icon, whose URL the leagues endpoint provides; it's downloaded once and cached
on disk. Best-effort: any failure returns None and the overlay falls back to a
text-only chip.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import httpx

from aldur_appraiser.config import cache_dir
from aldur_appraiser.pricing.client import fetch_base_icon_url

_TIMEOUT = 15.0


def _icons_dir() -> Path:
    d = cache_dir() / "icons"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _download(url: str) -> Path | None:
    name = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16] + ".png"
    path = _icons_dir() / name
    if path.exists() and path.stat().st_size > 0:
        return path
    try:
        resp = httpx.get(url, timeout=_TIMEOUT, follow_redirects=True)
        resp.raise_for_status()
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(resp.content)
        tmp.replace(path)
        return path
    except (httpx.HTTPError, OSError):
        return None


def base_icon_path(realm: str, league: str) -> Path | None:
    """Local path to the league's base-currency icon, downloading if needed."""
    try:
        url = fetch_base_icon_url(realm, league)
    except Exception:  # noqa: BLE001 - icon is cosmetic; never block on it
        return None
    return _download(url) if url else None
